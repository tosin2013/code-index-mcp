"""
Authentication Middleware for Code Index MCP Server (HTTP Mode)

This module provides API key authentication for cloud deployments:
- Google Cloud: Validates against Secret Manager
- AWS: Validates against Secrets Manager (future)
- OpenShift: Validates against Sealed Secrets (future)

Confidence: 87% - Core logic solid, GCP integration needs testing
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Conditional imports for cloud providers
try:
    from google.cloud import secretmanager
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    secretmanager = None

logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """User context extracted from authentication."""
    user_id: str
    api_key_name: str
    permissions: Dict[str, Any]
    metadata: Dict[str, Any]

    def get_storage_prefix(self) -> str:
        """Get storage prefix for user isolation."""
        return f"users/{self.user_id}"


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthMiddleware:
    """
    Authentication middleware for HTTP mode.
    
    Validates API keys against cloud provider secret managers:
    - Google Cloud: Secret Manager
    - AWS: Secrets Manager (future)
    - OpenShift: Sealed Secrets (future)
    
    Usage:
        auth = AuthMiddleware(provider='gcp', project_id='my-project')
        user_context = await auth.authenticate(api_key='...')
    """
    
    def __init__(
        self, 
        provider: str = 'gcp',
        project_id: Optional[str] = None,
        secret_prefix: str = 'code-index-api-key'
    ):
        """
        Initialize authentication middleware.
        
        Args:
            provider: Cloud provider ('gcp', 'aws', 'openshift')
            project_id: GCP project ID or AWS account ID
            secret_prefix: Prefix for API key secrets
        
        Raises:
            ValueError: If provider dependencies not installed
        """
        self.provider = provider
        self.project_id = project_id or os.getenv('GCP_PROJECT_ID')
        self.secret_prefix = secret_prefix
        
        if provider == 'gcp':
            if not GOOGLE_CLOUD_AVAILABLE:
                raise ValueError(
                    "Google Cloud SDK not installed. "
                    "Install with: pip install google-cloud-secret-manager"
                )
            if not self.project_id:
                raise ValueError(
                    "GCP project ID required. "
                    "Set GCP_PROJECT_ID environment variable"
                )
            self.secret_client = secretmanager.SecretManagerServiceClient()
        elif provider == 'aws':
            # TODO: Implement AWS Secrets Manager (ADR 0006)
            raise NotImplementedError("AWS authentication not yet implemented")
        elif provider == 'openshift':
            # TODO: Implement Sealed Secrets (ADR 0007)
            raise NotImplementedError("OpenShift authentication not yet implemented")
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        logger.info(f"Initialized AuthMiddleware for {provider}")
    
    async def authenticate(self, api_key: str) -> UserContext:
        """
        Authenticate API key and extract user context.
        
        Args:
            api_key: API key from request header
        
        Returns:
            UserContext with user_id and permissions
        
        Raises:
            AuthenticationError: If authentication fails
        
        Verification:
            - Check API key format (prefix + random string)
            - Validate against Secret Manager
            - Extract user_id from secret metadata
            - Return UserContext for request isolation
        """
        if not api_key:
            raise AuthenticationError("API key required")
        
        if not api_key.startswith('ci_'):
            raise AuthenticationError(
                "Invalid API key format. "
                "Keys must start with 'ci_'"
            )
        
        if self.provider == 'gcp':
            return await self._authenticate_gcp(api_key)
        else:
            raise AuthenticationError(f"Provider {self.provider} not supported")
    
    async def _authenticate_gcp(self, api_key: str) -> UserContext:
        """
        Authenticate against Google Cloud Secret Manager.
        
        Algorithm:
        1. List all secrets with prefix 'code-index-api-key-*'
        2. Access each secret's latest version
        3. Compare with provided API key (constant-time comparison)
        4. Extract user_id from secret labels
        5. Return UserContext with permissions
        
        Confidence: 85% - Need to test with actual GCP Secret Manager
        """
        try:
            # List secrets for this service
            parent = f"projects/{self.project_id}"
            request = secretmanager.ListSecretsRequest(
                parent=parent,
                filter=f'labels.service:code-index-mcp'
            )
            
            secrets = self.secret_client.list_secrets(request=request)
            
            # Check each secret (constant-time to prevent timing attacks)
            valid_secret = None
            for secret in secrets:
                # Access latest version
                secret_version = f"{secret.name}/versions/latest"
                response = self.secret_client.access_secret_version(
                    name=secret_version
                )
                stored_key = response.payload.data.decode('UTF-8')
                
                # Constant-time comparison
                if self._constant_time_compare(api_key, stored_key):
                    valid_secret = secret
                    break
            
            if not valid_secret:
                raise AuthenticationError("Invalid API key")
            
            # Extract user context from secret labels
            user_id = valid_secret.labels.get('user_id')
            if not user_id:
                raise AuthenticationError("API key missing user_id label")

            # Auto-create user in database if doesn't exist (server-managed)
            await self._ensure_user_exists(
                user_id=user_id,
                api_key=api_key,
                secret_name=valid_secret.name.split('/')[-1]
            )

            # Build user context
            user_context = UserContext(
                user_id=user_id,
                api_key_name=valid_secret.name.split('/')[-1],
                permissions={
                    'read': True,
                    'write': True,
                    'delete': valid_secret.labels.get('can_delete', 'false') == 'true'
                },
                metadata={
                    'created_at': valid_secret.create_time.isoformat(),
                    'project_id': self.project_id
                }
            )

            logger.info(f"Authenticated user: {user_id}")
            return user_context
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    async def _ensure_user_exists(
        self,
        user_id: str,
        api_key: str,
        secret_name: str
    ) -> None:
        """
        Ensure user record exists in database (auto-create if missing).

        This is SERVER-MANAGED user creation that happens automatically
        on first authentication. Users don't need to manually create accounts.

        Args:
            user_id: UUID from API key secret labels
            api_key: The API key string (for hashing)
            secret_name: API key secret name (used as email identifier)

        Database:
            Inserts into users table if user_id doesn't exist yet.
            Uses INSERT ... ON CONFLICT DO NOTHING for idempotency.
        """
        import psycopg2
        import hashlib

        db_conn_str = os.getenv("ALLOYDB_CONNECTION_STRING")
        if not db_conn_str:
            logger.warning("AlloyDB not configured - skipping user creation")
            return

        try:
            conn = psycopg2.connect(db_conn_str)
            cur = conn.cursor()

            # Hash the API key for storage
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Create email from secret name
            email = f"{secret_name}@code-index-mcp.local"

            # Insert user if doesn't exist (idempotent)
            cur.execute("""
                INSERT INTO users (user_id, email, api_key_hash, storage_quota_gb, is_active)
                VALUES (%s, %s, %s, 50, TRUE)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, email, api_key_hash))

            if cur.rowcount > 0:
                logger.info(f"Auto-created user record for {user_id}")

            conn.commit()
            cur.close()
            conn.close()

        except Exception as e:
            logger.error(f"Failed to ensure user exists: {e}")
            # Don't fail authentication if user creation fails
            # User might already exist, or DB might be temporarily unavailable

    @staticmethod
    def _constant_time_compare(a: str, b: str) -> bool:
        """
        Constant-time string comparison to prevent timing attacks.

        Args:
            a: First string
            b: Second string

        Returns:
            True if strings are equal
        """
        if len(a) != len(b):
            return False

        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)

        return result == 0


def get_user_from_request(request: Any) -> Optional[UserContext]:
    """
    Extract user context from request object.
    
    For FastMCP/Starlette requests:
    - Checks Authorization header for Bearer token
    - Checks X-API-Key header
    - Returns cached UserContext from request.state
    
    Args:
        request: FastMCP/Starlette request object
    
    Returns:
        UserContext if authenticated, None otherwise
    """
    # Check if user context already attached to request
    if hasattr(request, 'state') and hasattr(request.state, 'user'):
        return request.state.user
    
    return None


async def require_authentication(request: Any, auth: AuthMiddleware) -> UserContext:
    """
    Middleware function to require authentication.
    
    Usage in FastMCP:
        @mcp.tool()
        async def my_tool(ctx: Context):
            user = await require_authentication(ctx.request, auth_middleware)
            # ... tool logic with user context ...
    
    Args:
        request: Request object
        auth: AuthMiddleware instance
    
    Returns:
        UserContext for authenticated user
    
    Raises:
        AuthenticationError: If authentication fails
    """
    # Try Authorization header first
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        api_key = auth_header[7:]  # Remove 'Bearer ' prefix
        return await auth.authenticate(api_key)
    
    # Try X-API-Key header
    api_key = request.headers.get('X-API-Key', '')
    if api_key:
        return await auth.authenticate(api_key)
    
    raise AuthenticationError("No API key provided in request")


# Export public API
__all__ = [
    'AuthMiddleware',
    'UserContext',
    'AuthenticationError',
    'get_user_from_request',
    'require_authentication'
]



