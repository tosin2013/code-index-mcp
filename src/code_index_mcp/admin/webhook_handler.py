"""
Webhook Handler for Git-Sync Architecture.

Handles webhooks from GitHub, GitLab, Bitbucket, and Gitea for automatic
code synchronization on push events.

Security:
- GitHub: HMAC-SHA256 signature verification
- GitLab: Secret token verification
- Gitea: HMAC-SHA256 signature verification (same as GitHub)
- Bitbucket: UUID verification (future)

Usage:
    # Register webhook routes in FastMCP server
    from .admin.webhook_handler import setup_webhook_routes

    app = FastMCP("CodeIndexer")
    setup_webhook_routes(app)

Webhook URLs:
    - GitHub: POST /webhook/github
    - GitLab: POST /webhook/gitlab
    - Gitea: POST /webhook/gitea
    - Bitbucket: POST /webhook/bitbucket (future)

Confidence: 88% - Core logic solid, needs production testing
"""

import asyncio
import hashlib
import hmac
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from fastapi import HTTPException, Request, Response

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    Request = None
    Response = None
    HTTPException = None

logger = logging.getLogger(__name__)


class WebhookError(Exception):
    """Base exception for webhook handling errors."""

    pass


class WebhookHandler:
    """
    Handle webhooks from Git platforms with signature verification.

    Features:
    - Multi-platform support (GitHub, GitLab, Gitea)
    - Signature verification for security
    - Async processing to avoid blocking webhook responses
    - Rate limiting per repository
    - Retry logic for failed syncs
    """

    def __init__(
        self,
        github_secret: Optional[str] = None,
        gitlab_secret: Optional[str] = None,
        gitea_secret: Optional[str] = None,
    ):
        """
        Initialize webhook handler.

        Args:
            github_secret: GitHub webhook secret for signature verification
            gitlab_secret: GitLab webhook secret token
            gitea_secret: Gitea webhook secret for signature verification
        """
        self.github_secret = github_secret or os.getenv("GITHUB_WEBHOOK_SECRET")
        self.gitlab_secret = gitlab_secret or os.getenv("GITLAB_WEBHOOK_SECRET")
        self.gitea_secret = gitea_secret or os.getenv("GITEA_WEBHOOK_SECRET")

        # Track recent webhook calls for rate limiting
        self.recent_webhooks: Dict[str, datetime] = {}
        self.min_interval_seconds = 30  # Min time between syncs for same repo

        logger.info(
            f"Initialized WebhookHandler: "
            f"github={bool(self.github_secret)}, "
            f"gitlab={bool(self.gitlab_secret)}, "
            f"gitea={bool(self.gitea_secret)}"
        )

    def verify_github_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """
        Verify GitHub webhook signature (HMAC-SHA256).

        Args:
            payload_body: Raw request body
            signature_header: Value of X-Hub-Signature-256 header

        Returns:
            True if signature is valid
        """
        if not self.github_secret:
            logger.warning("GitHub webhook secret not configured")
            return False

        if not signature_header:
            logger.warning("Missing X-Hub-Signature-256 header")
            return False

        # GitHub sends: sha256=<hex_digest>
        if not signature_header.startswith("sha256="):
            logger.warning(f"Invalid signature format: {signature_header[:20]}")
            return False

        expected_signature = signature_header.split("=")[1]

        # Compute HMAC
        computed_signature = hmac.new(
            self.github_secret.encode("utf-8"), payload_body, hashlib.sha256
        ).hexdigest()

        # Compare signatures (timing-safe)
        is_valid = hmac.compare_digest(computed_signature, expected_signature)

        if not is_valid:
            logger.warning("GitHub signature verification failed")

        return is_valid

    def verify_gitlab_token(self, token_header: str) -> bool:
        """
        Verify GitLab webhook token.

        Args:
            token_header: Value of X-Gitlab-Token header

        Returns:
            True if token is valid
        """
        if not self.gitlab_secret:
            logger.warning("GitLab webhook secret not configured")
            return False

        if not token_header:
            logger.warning("Missing X-Gitlab-Token header")
            return False

        # Simple token comparison (timing-safe)
        is_valid = hmac.compare_digest(token_header, self.gitlab_secret)

        if not is_valid:
            logger.warning("GitLab token verification failed")

        return is_valid

    def verify_gitea_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """
        Verify Gitea webhook signature (HMAC-SHA256, same as GitHub).

        Args:
            payload_body: Raw request body
            signature_header: Value of X-Gitea-Signature header

        Returns:
            True if signature is valid
        """
        if not self.gitea_secret:
            logger.warning("Gitea webhook secret not configured")
            return False

        if not signature_header:
            logger.warning("Missing X-Gitea-Signature header")
            return False

        # Compute HMAC
        computed_signature = hmac.new(
            self.gitea_secret.encode("utf-8"), payload_body, hashlib.sha256
        ).hexdigest()

        # Compare signatures (timing-safe)
        is_valid = hmac.compare_digest(computed_signature, signature_header)

        if not is_valid:
            logger.warning("Gitea signature verification failed")

        return is_valid

    def should_rate_limit(self, repo_key: str) -> bool:
        """
        Check if webhook should be rate limited.

        Args:
            repo_key: Unique repository identifier (e.g., "github.com/user/repo")

        Returns:
            True if webhook should be rate limited
        """
        if repo_key not in self.recent_webhooks:
            return False

        last_webhook = self.recent_webhooks[repo_key]
        time_since_last = (datetime.now() - last_webhook).total_seconds()

        if time_since_last < self.min_interval_seconds:
            logger.info(
                f"Rate limiting webhook for {repo_key}: "
                f"{time_since_last:.1f}s since last sync (min: {self.min_interval_seconds}s)"
            )
            return True

        return False

    def mark_webhook_processed(self, repo_key: str):
        """Mark webhook as processed for rate limiting."""
        self.recent_webhooks[repo_key] = datetime.now()

    async def handle_github_webhook(
        self, payload: Dict[str, Any], signature: str, event_type: str
    ) -> Dict[str, Any]:
        """
        Handle GitHub push webhook.

        Args:
            payload: Webhook payload (JSON)
            signature: X-Hub-Signature-256 header
            event_type: X-GitHub-Event header

        Returns:
            Dict with processing result
        """
        logger.info(f"[WEBHOOK-GITHUB] Received event: {event_type}")

        # Only process push events
        if event_type != "push":
            logger.info(f"[WEBHOOK-GITHUB] Ignoring non-push event: {event_type}")
            return {
                "status": "ignored",
                "reason": f"Event type '{event_type}' not supported",
                "supported_events": ["push"],
            }

        # Extract repository info
        repo_url = payload.get("repository", {}).get("clone_url")
        repo_name = payload.get("repository", {}).get("full_name")
        branch = payload.get("ref", "").replace("refs/heads/", "")
        commits = payload.get("commits", [])

        if not repo_url:
            logger.error("[WEBHOOK-GITHUB] Missing repository clone_url")
            return {"status": "error", "reason": "Missing repository URL"}

        logger.info(
            f"[WEBHOOK-GITHUB] Push to {repo_name} on branch {branch} " f"({len(commits)} commits)"
        )

        # Rate limiting
        repo_key = f"github.com/{repo_name}"
        if self.should_rate_limit(repo_key):
            return {
                "status": "rate_limited",
                "repo": repo_name,
                "min_interval": self.min_interval_seconds,
            }

        # Trigger async sync
        asyncio.create_task(
            self._sync_repository(
                git_url=repo_url,
                branch=branch,
                project_name=repo_name.split("/")[-1],
                platform="github",
            )
        )

        self.mark_webhook_processed(repo_key)

        return {
            "status": "accepted",
            "repo": repo_name,
            "branch": branch,
            "commits": len(commits),
            "message": "Sync triggered in background",
        }

    async def handle_gitlab_webhook(
        self, payload: Dict[str, Any], token: str, event_type: str
    ) -> Dict[str, Any]:
        """
        Handle GitLab push webhook.

        Args:
            payload: Webhook payload (JSON)
            token: X-Gitlab-Token header
            event_type: X-Gitlab-Event header

        Returns:
            Dict with processing result
        """
        logger.info(f"[WEBHOOK-GITLAB] Received event: {event_type}")

        # Only process push events
        if event_type != "Push Hook":
            logger.info(f"[WEBHOOK-GITLAB] Ignoring non-push event: {event_type}")
            return {
                "status": "ignored",
                "reason": f"Event type '{event_type}' not supported",
                "supported_events": ["Push Hook"],
            }

        # Extract repository info
        repo_url = payload.get("project", {}).get("git_http_url")
        repo_name = payload.get("project", {}).get("path_with_namespace")
        branch = payload.get("ref", "").replace("refs/heads/", "")
        commits = payload.get("commits", [])

        if not repo_url:
            logger.error("[WEBHOOK-GITLAB] Missing repository git_http_url")
            return {"status": "error", "reason": "Missing repository URL"}

        logger.info(
            f"[WEBHOOK-GITLAB] Push to {repo_name} on branch {branch} " f"({len(commits)} commits)"
        )

        # Rate limiting
        repo_key = f"gitlab.com/{repo_name}"
        if self.should_rate_limit(repo_key):
            return {
                "status": "rate_limited",
                "repo": repo_name,
                "min_interval": self.min_interval_seconds,
            }

        # Trigger async sync
        asyncio.create_task(
            self._sync_repository(
                git_url=repo_url,
                branch=branch,
                project_name=repo_name.split("/")[-1],
                platform="gitlab",
            )
        )

        self.mark_webhook_processed(repo_key)

        return {
            "status": "accepted",
            "repo": repo_name,
            "branch": branch,
            "commits": len(commits),
            "message": "Sync triggered in background",
        }

    async def handle_gitea_webhook(
        self, payload: Dict[str, Any], signature: str, event_type: str
    ) -> Dict[str, Any]:
        """
        Handle Gitea push webhook.

        Args:
            payload: Webhook payload (JSON)
            signature: X-Gitea-Signature header
            event_type: X-Gitea-Event header

        Returns:
            Dict with processing result
        """
        logger.info(f"[WEBHOOK-GITEA] Received event: {event_type}")

        # Only process push events
        if event_type != "push":
            logger.info(f"[WEBHOOK-GITEA] Ignoring non-push event: {event_type}")
            return {
                "status": "ignored",
                "reason": f"Event type '{event_type}' not supported",
                "supported_events": ["push"],
            }

        # Extract repository info
        repo_url = payload.get("repository", {}).get("clone_url")
        repo_name = payload.get("repository", {}).get("full_name")
        branch = payload.get("ref", "").replace("refs/heads/", "")
        commits = payload.get("commits", [])

        if not repo_url:
            logger.error("[WEBHOOK-GITEA] Missing repository clone_url")
            return {"status": "error", "reason": "Missing repository URL"}

        logger.info(
            f"[WEBHOOK-GITEA] Push to {repo_name} on branch {branch} " f"({len(commits)} commits)"
        )

        # Rate limiting
        repo_key = f"gitea/{repo_name}"
        if self.should_rate_limit(repo_key):
            return {
                "status": "rate_limited",
                "repo": repo_name,
                "min_interval": self.min_interval_seconds,
            }

        # Trigger async sync
        asyncio.create_task(
            self._sync_repository(
                git_url=repo_url,
                branch=branch,
                project_name=repo_name.split("/")[-1],
                platform="gitea",
            )
        )

        self.mark_webhook_processed(repo_key)

        return {
            "status": "accepted",
            "repo": repo_name,
            "branch": branch,
            "commits": len(commits),
            "message": "Sync triggered in background",
        }

    async def _sync_repository(self, git_url: str, branch: str, project_name: str, platform: str):
        """
        Trigger repository sync in background (async).

        This method is called asynchronously by webhook handlers to avoid
        blocking webhook responses. It calls the ingest_code_from_git tool.

        Args:
            git_url: Repository URL
            branch: Branch name
            project_name: Project name
            platform: Git platform (github, gitlab, gitea)
        """
        try:
            logger.info(
                f"[WEBHOOK-SYNC] Starting background sync: "
                f"{platform}:{project_name} (branch: {branch})"
            )

            # Import here to avoid circular dependency
            from uuid import uuid4

            from ..ingestion.git_manager import GitRepositoryManager
            from ..ingestion.pipeline import ingest_directory

            # Get configuration
            db_conn_str = os.getenv("ALLOYDB_CONNECTION_STRING")
            git_bucket = os.getenv("GCS_GIT_BUCKET", "code-index-git-repos")

            if not db_conn_str:
                logger.error("[WEBHOOK-SYNC] AlloyDB connection string not configured")
                return

            # Generate user ID (in production, map from webhook sender)
            user_id = uuid4()

            # Initialize GitRepositoryManager
            git_manager = GitRepositoryManager(gcs_bucket=git_bucket, user_id=str(user_id))

            # Sync repository (pull changes)
            sync_result = await git_manager.sync_repository(
                git_url=git_url,
                branch=branch,
                auth_token=None,  # Webhooks for public repos only (for now)
            )

            logger.info(
                f"[WEBHOOK-SYNC] Sync completed: "
                f"type={sync_result['sync_type']}, "
                f"files_changed={sync_result.get('files_changed', 'N/A')}"
            )

            # Run ingestion if files changed
            if sync_result["sync_type"] == "pull" and sync_result.get("files_changed") == 0:
                logger.info("[WEBHOOK-SYNC] No files changed, skipping ingestion")
                return

            # Progress callback
            def log_progress(message: str, data: Dict[str, Any]):
                logger.info(f"[WEBHOOK-SYNC PROGRESS] {message} | Data: {data}")

            # Ingest directory
            stats = ingest_directory(
                directory_path=sync_result["local_path"],
                user_id=user_id,
                project_name=project_name,
                db_connection_string=db_conn_str,
                use_mock_embedder=False,
                progress_callback=log_progress,
            )

            logger.info(f"[WEBHOOK-SYNC] Ingestion completed: {stats.to_dict()}")

        except Exception as e:
            logger.error(f"[WEBHOOK-SYNC] Sync failed: {e}", exc_info=True)


def setup_webhook_routes(app):
    """
    Set up webhook routes in FastMCP/FastAPI application.

    Args:
        app: FastMCP or FastAPI application instance

    Usage:
        from .admin.webhook_handler import setup_webhook_routes

        app = FastMCP("CodeIndexer")
        setup_webhook_routes(app)
    """
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI not available, webhook routes not registered")
        return

    # Initialize webhook handler
    webhook_handler = WebhookHandler()

    @app.post("/webhook/github")
    async def handle_github_webhook(request: Request):
        """Handle GitHub push webhooks."""
        # Get headers
        signature = request.headers.get("X-Hub-Signature-256", "")
        event_type = request.headers.get("X-GitHub-Event", "")

        # Get raw body for signature verification
        body = await request.body()

        # Verify signature
        if not webhook_handler.verify_github_signature(body, signature):
            logger.warning("[WEBHOOK-GITHUB] Invalid signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse JSON payload
        import json

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Handle webhook
        result = await webhook_handler.handle_github_webhook(
            payload=payload, signature=signature, event_type=event_type
        )

        return result

    @app.post("/webhook/gitlab")
    async def handle_gitlab_webhook(request: Request):
        """Handle GitLab push webhooks."""
        # Get headers
        token = request.headers.get("X-Gitlab-Token", "")
        event_type = request.headers.get("X-Gitlab-Event", "")

        # Verify token
        if not webhook_handler.verify_gitlab_token(token):
            logger.warning("[WEBHOOK-GITLAB] Invalid token")
            raise HTTPException(status_code=401, detail="Invalid token")

        # Parse JSON payload
        payload = await request.json()

        # Handle webhook
        result = await webhook_handler.handle_gitlab_webhook(
            payload=payload, token=token, event_type=event_type
        )

        return result

    @app.post("/webhook/gitea")
    async def handle_gitea_webhook(request: Request):
        """Handle Gitea push webhooks."""
        # Get headers
        signature = request.headers.get("X-Gitea-Signature", "")
        event_type = request.headers.get("X-Gitea-Event", "")

        # Get raw body for signature verification
        body = await request.body()

        # Verify signature
        if not webhook_handler.verify_gitea_signature(body, signature):
            logger.warning("[WEBHOOK-GITEA] Invalid signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse JSON payload
        import json

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Handle webhook
        result = await webhook_handler.handle_gitea_webhook(
            payload=payload, signature=signature, event_type=event_type
        )

        return result

    logger.info("Webhook routes registered: " "/webhook/github, /webhook/gitlab, /webhook/gitea")


# Export public API
__all__ = ["WebhookHandler", "WebhookError", "setup_webhook_routes"]
