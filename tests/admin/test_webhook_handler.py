"""
Unit tests for WebhookHandler.

Tests:
- GitHub signature verification
- GitLab token verification
- Gitea signature verification
- Rate limiting
- Webhook payload processing
- Error handling

Run with:
    pytest tests/admin/test_webhook_handler.py -v
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.code_index_mcp.admin.webhook_handler import WebhookError, WebhookHandler


@pytest.fixture
def webhook_handler():
    """Create WebhookHandler with test secrets."""
    return WebhookHandler(
        github_secret="test-github-secret",
        gitlab_secret="test-gitlab-token",
        gitea_secret="test-gitea-secret",
    )


@pytest.fixture
def github_push_payload():
    """Sample GitHub push webhook payload."""
    return {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "user/test-repo",
            "clone_url": "https://github.com/user/test-repo.git",
        },
        "commits": [{"id": "abc123", "message": "Test commit"}],
    }


@pytest.fixture
def gitlab_push_payload():
    """Sample GitLab push webhook payload."""
    return {
        "ref": "refs/heads/main",
        "project": {
            "path_with_namespace": "user/test-project",
            "git_http_url": "https://gitlab.com/user/test-project.git",
        },
        "commits": [{"id": "def456", "message": "Test commit"}],
    }


@pytest.fixture
def gitea_push_payload():
    """Sample Gitea push webhook payload."""
    return {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "user/test-app",
            "clone_url": "https://gitea.example.com/user/test-app.git",
        },
        "commits": [{"id": "ghi789", "message": "Test commit"}],
    }


class TestGitHubSignatureVerification:
    """Test GitHub HMAC-SHA256 signature verification."""

    def test_valid_signature(self, webhook_handler):
        """Test verification with valid GitHub signature."""
        payload = b'{"test": "data"}'
        secret = "test-github-secret"

        # Generate valid signature
        signature_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        signature_header = f"sha256={signature_hex}"

        assert webhook_handler.verify_github_signature(payload, signature_header) is True

    def test_invalid_signature(self, webhook_handler):
        """Test rejection of invalid GitHub signature."""
        payload = b'{"test": "data"}'
        invalid_signature = "sha256=invalid_hex_digest"

        assert webhook_handler.verify_github_signature(payload, invalid_signature) is False

    def test_missing_signature(self, webhook_handler):
        """Test rejection when signature header is missing."""
        payload = b'{"test": "data"}'

        assert webhook_handler.verify_github_signature(payload, "") is False
        assert webhook_handler.verify_github_signature(payload, None) is False

    def test_wrong_signature_format(self, webhook_handler):
        """Test rejection of incorrectly formatted signature."""
        payload = b'{"test": "data"}'
        wrong_format = "sha1=abc123"  # Wrong algorithm

        assert webhook_handler.verify_github_signature(payload, wrong_format) is False

    def test_tampered_payload(self, webhook_handler):
        """Test detection of tampered payload."""
        original_payload = b'{"test": "data"}'
        tampered_payload = b'{"test": "malicious"}'
        secret = "test-github-secret"

        # Generate signature for original payload
        signature_hex = hmac.new(
            secret.encode("utf-8"), original_payload, hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={signature_hex}"

        # Verify with tampered payload (should fail)
        assert webhook_handler.verify_github_signature(tampered_payload, signature_header) is False


class TestGitLabTokenVerification:
    """Test GitLab token verification."""

    def test_valid_token(self, webhook_handler):
        """Test verification with valid GitLab token."""
        assert webhook_handler.verify_gitlab_token("test-gitlab-token") is True

    def test_invalid_token(self, webhook_handler):
        """Test rejection of invalid GitLab token."""
        assert webhook_handler.verify_gitlab_token("wrong-token") is False

    def test_missing_token(self, webhook_handler):
        """Test rejection when token is missing."""
        assert webhook_handler.verify_gitlab_token("") is False
        assert webhook_handler.verify_gitlab_token(None) is False

    def test_empty_secret(self):
        """Test behavior when GitLab secret not configured."""
        handler = WebhookHandler(gitlab_secret=None)
        assert handler.verify_gitlab_token("any-token") is False


class TestGiteaSignatureVerification:
    """Test Gitea HMAC-SHA256 signature verification."""

    def test_valid_signature(self, webhook_handler):
        """Test verification with valid Gitea signature."""
        payload = b'{"test": "data"}'
        secret = "test-gitea-secret"

        # Generate valid signature (no prefix for Gitea)
        signature_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        assert webhook_handler.verify_gitea_signature(payload, signature_hex) is True

    def test_invalid_signature(self, webhook_handler):
        """Test rejection of invalid Gitea signature."""
        payload = b'{"test": "data"}'
        invalid_signature = "invalid_hex_digest"

        assert webhook_handler.verify_gitea_signature(payload, invalid_signature) is False

    def test_missing_signature(self, webhook_handler):
        """Test rejection when signature is missing."""
        payload = b'{"test": "data"}'

        assert webhook_handler.verify_gitea_signature(payload, "") is False
        assert webhook_handler.verify_gitea_signature(payload, None) is False


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_no_rate_limit_first_call(self, webhook_handler):
        """Test no rate limit on first webhook call."""
        assert webhook_handler.should_rate_limit("github.com/user/repo") is False

    def test_rate_limit_rapid_calls(self, webhook_handler):
        """Test rate limiting on rapid consecutive calls."""
        repo_key = "github.com/user/repo"

        # First call - not rate limited
        assert webhook_handler.should_rate_limit(repo_key) is False
        webhook_handler.mark_webhook_processed(repo_key)

        # Immediate second call - should be rate limited
        assert webhook_handler.should_rate_limit(repo_key) is True

    def test_rate_limit_expires(self, webhook_handler):
        """Test rate limit expires after minimum interval."""
        repo_key = "github.com/user/repo"

        # Mark as processed in the past
        past_time = datetime.now() - timedelta(seconds=webhook_handler.min_interval_seconds + 1)
        webhook_handler.recent_webhooks[repo_key] = past_time

        # Should not be rate limited after interval expires
        assert webhook_handler.should_rate_limit(repo_key) is False

    def test_different_repos_not_rate_limited(self, webhook_handler):
        """Test different repositories are tracked separately."""
        webhook_handler.mark_webhook_processed("github.com/user/repo1")

        # Different repo should not be rate limited
        assert webhook_handler.should_rate_limit("github.com/user/repo2") is False


class TestGitHubWebhookHandling:
    """Test GitHub webhook processing."""

    @pytest.mark.asyncio
    @patch.object(WebhookHandler, "_sync_repository", new_callable=AsyncMock)
    async def test_handle_push_event(self, mock_sync, webhook_handler, github_push_payload):
        """Test handling valid GitHub push event."""
        result = await webhook_handler.handle_github_webhook(
            payload=github_push_payload, signature="valid", event_type="push"
        )

        assert result["status"] == "accepted"
        assert result["repo"] == "user/test-repo"
        assert result["branch"] == "main"
        assert result["commits"] == 1

        # Verify sync was triggered
        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_ignore_non_push_event(self, webhook_handler, github_push_payload):
        """Test ignoring non-push events."""
        result = await webhook_handler.handle_github_webhook(
            payload=github_push_payload, signature="valid", event_type="pull_request"
        )

        assert result["status"] == "ignored"
        assert "pull_request" in result["reason"]

    @pytest.mark.asyncio
    async def test_error_missing_repo_url(self, webhook_handler):
        """Test error handling for missing repository URL."""
        invalid_payload = {"ref": "refs/heads/main", "repository": {}}

        result = await webhook_handler.handle_github_webhook(
            payload=invalid_payload, signature="valid", event_type="push"
        )

        assert result["status"] == "error"
        assert "repository URL" in result["reason"]

    @pytest.mark.asyncio
    async def test_rate_limiting_github(self, webhook_handler, github_push_payload):
        """Test rate limiting for GitHub webhooks."""
        # First call
        result1 = await webhook_handler.handle_github_webhook(
            payload=github_push_payload, signature="valid", event_type="push"
        )
        assert result1["status"] == "accepted"

        # Immediate second call - should be rate limited
        result2 = await webhook_handler.handle_github_webhook(
            payload=github_push_payload, signature="valid", event_type="push"
        )
        assert result2["status"] == "rate_limited"


class TestGitLabWebhookHandling:
    """Test GitLab webhook processing."""

    @pytest.mark.asyncio
    @patch.object(WebhookHandler, "_sync_repository", new_callable=AsyncMock)
    async def test_handle_push_event(self, mock_sync, webhook_handler, gitlab_push_payload):
        """Test handling valid GitLab push event."""
        result = await webhook_handler.handle_gitlab_webhook(
            payload=gitlab_push_payload, token="valid", event_type="Push Hook"
        )

        assert result["status"] == "accepted"
        assert result["repo"] == "user/test-project"
        assert result["branch"] == "main"
        assert result["commits"] == 1

        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_ignore_non_push_event(self, webhook_handler, gitlab_push_payload):
        """Test ignoring non-push events."""
        result = await webhook_handler.handle_gitlab_webhook(
            payload=gitlab_push_payload, token="valid", event_type="Merge Request Hook"
        )

        assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_error_missing_repo_url(self, webhook_handler):
        """Test error handling for missing repository URL."""
        invalid_payload = {"ref": "refs/heads/main", "project": {}}

        result = await webhook_handler.handle_gitlab_webhook(
            payload=invalid_payload, token="valid", event_type="Push Hook"
        )

        assert result["status"] == "error"


class TestGiteaWebhookHandling:
    """Test Gitea webhook processing."""

    @pytest.mark.asyncio
    @patch.object(WebhookHandler, "_sync_repository", new_callable=AsyncMock)
    async def test_handle_push_event(self, mock_sync, webhook_handler, gitea_push_payload):
        """Test handling valid Gitea push event."""
        result = await webhook_handler.handle_gitea_webhook(
            payload=gitea_push_payload, signature="valid", event_type="push"
        )

        assert result["status"] == "accepted"
        assert result["repo"] == "user/test-app"
        assert result["branch"] == "main"
        assert result["commits"] == 1

        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_ignore_non_push_event(self, webhook_handler, gitea_push_payload):
        """Test ignoring non-push events."""
        result = await webhook_handler.handle_gitea_webhook(
            payload=gitea_push_payload, signature="valid", event_type="pull_request"
        )

        assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_rate_limiting_gitea(self, webhook_handler, gitea_push_payload):
        """Test rate limiting for Gitea webhooks."""
        # First call
        result1 = await webhook_handler.handle_gitea_webhook(
            payload=gitea_push_payload, signature="valid", event_type="push"
        )
        assert result1["status"] == "accepted"

        # Immediate second call - should be rate limited
        result2 = await webhook_handler.handle_gitea_webhook(
            payload=gitea_push_payload, signature="valid", event_type="push"
        )
        assert result2["status"] == "rate_limited"


class TestBackgroundSync:
    """Test background repository synchronization."""

    @pytest.mark.asyncio
    @patch("src.code_index_mcp.ingestion.git_manager.GitRepositoryManager")
    @patch("src.code_index_mcp.ingestion.pipeline.ingest_directory")
    @patch.dict(
        "os.environ",
        {"ALLOYDB_CONNECTION_STRING": "postgresql://test", "GCS_GIT_BUCKET": "test-bucket"},
    )
    async def test_sync_repository_clone(
        self, mock_ingest, mock_git_manager_class, webhook_handler
    ):
        """Test background sync for initial clone."""
        # Mock GitRepositoryManager
        mock_manager = AsyncMock()
        mock_manager.sync_repository = AsyncMock(
            return_value={
                "sync_type": "clone",
                "local_path": "/tmp/test-repo",
                "files_changed": None,
                "repo_info": {"platform": "github", "owner": "user", "repo": "test"},
            }
        )
        mock_git_manager_class.return_value = mock_manager

        # Mock ingest_directory
        mock_stats = Mock()
        mock_stats.to_dict.return_value = {"chunks_created": 10}
        mock_ingest.return_value = mock_stats

        # Call background sync
        await webhook_handler._sync_repository(
            git_url="https://github.com/user/test.git",
            branch="main",
            project_name="test",
            platform="github",
        )

        # Verify GitRepositoryManager called
        mock_manager.sync_repository.assert_called_once()

        # Verify ingestion called
        mock_ingest.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.code_index_mcp.ingestion.git_manager.GitRepositoryManager")
    @patch("src.code_index_mcp.ingestion.pipeline.ingest_directory")
    @patch.dict(
        "os.environ",
        {"ALLOYDB_CONNECTION_STRING": "postgresql://test", "GCS_GIT_BUCKET": "test-bucket"},
    )
    async def test_sync_repository_no_changes(
        self, mock_ingest, mock_git_manager_class, webhook_handler
    ):
        """Test background sync skips ingestion when no files changed."""
        # Mock GitRepositoryManager
        mock_manager = AsyncMock()
        mock_manager.sync_repository = AsyncMock(
            return_value={
                "sync_type": "pull",
                "local_path": "/tmp/test-repo",
                "files_changed": 0,  # No changes
                "repo_info": {"platform": "github", "owner": "user", "repo": "test"},
            }
        )
        mock_git_manager_class.return_value = mock_manager

        # Call background sync
        await webhook_handler._sync_repository(
            git_url="https://github.com/user/test.git",
            branch="main",
            project_name="test",
            platform="github",
        )

        # Verify ingestion NOT called (no changes)
        mock_ingest.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
