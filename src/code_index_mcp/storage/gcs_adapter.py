"""
Google Cloud Storage Adapter for Code Index MCP Server.

Implements BaseStorageAdapter for Google Cloud Storage (GCS) with:
- User namespace isolation (users/{user_id}/{project_name}/)
- Workload Identity integration (no service account keys)
- Stream-based uploads for large files
- Lifecycle policies for automatic cleanup

Confidence: 85% - Core logic solid, needs GCS testing
"""

import os
import logging
import mimetypes
from typing import List, Optional, AsyncIterator
from datetime import datetime

# Conditional import for Google Cloud Storage
try:
    from google.cloud import storage
    from google.cloud.exceptions import NotFound, GoogleCloudError
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    storage = None
    NotFound = Exception
    GoogleCloudError = Exception

from .base_adapter import (
    BaseStorageAdapter,
    FileMetadata,
    StorageError,
    StreamUploadMixin
)

logger = logging.getLogger(__name__)


class GCSAdapter(BaseStorageAdapter, StreamUploadMixin):
    """
    Google Cloud Storage adapter with user namespace isolation.
    
    Architecture:
    - Bucket: code-index-projects (or custom)
    - Namespace: users/{user_id}/{project_name}/
    - Indexes: users/{user_id}/{project_name}/.indexes/
    - Settings: users/{user_id}/{project_name}/.settings/
    
    Usage:
        adapter = GCSAdapter(
            bucket="code-index-projects",
            user_id="user123",
            project_name="myproject",
            project_id="my-gcp-project"  # Optional, from env if not provided
        )
        
        # Upload file
        await adapter.upload_file("src/main.py", content)
        
        # Download file
        content = await adapter.download_file("src/main.py")
        
        # List files
        files = await adapter.list_files("src/", recursive=True)
    
    Security:
    - Workload Identity (preferred): No credentials in code
    - Service Account: Via GOOGLE_APPLICATION_CREDENTIALS env var
    - User isolation: Automatic namespace prefixing
    """
    
    def __init__(
        self,
        bucket: str,
        user_id: str,
        project_name: str,
        project_id: Optional[str] = None
    ):
        """
        Initialize GCS adapter with user namespace.
        
        Args:
            bucket: GCS bucket name (e.g., "code-index-projects")
            user_id: User identifier for namespace isolation
            project_name: Project name within user namespace
            project_id: GCP project ID (optional, from env if not provided)
        
        Raises:
            ValueError: If Google Cloud Storage not installed
            StorageError: If bucket not accessible
        """
        if not GOOGLE_CLOUD_AVAILABLE:
            raise ValueError(
                "Google Cloud Storage not installed. "
                "Install with: pip install google-cloud-storage"
            )
        
        self.bucket_name = bucket
        self.user_id = user_id
        self.project_name = project_name
        self.project_id = project_id or os.getenv('GCP_PROJECT_ID')
        
        # Namespace prefix for user isolation
        self.namespace_prefix = f"users/{user_id}/{project_name}/"
        
        # Initialize GCS client
        try:
            if self.project_id:
                self.client = storage.Client(project=self.project_id)
            else:
                # Use application default credentials
                self.client = storage.Client()
            
            self.bucket = self.client.bucket(bucket)
            
            # Verify bucket exists (don't create to avoid permission issues)
            if not self.bucket.exists():
                raise StorageError(
                    f"Bucket '{bucket}' does not exist. "
                    f"Create it first with: gsutil mb gs://{bucket}"
                )
            
            logger.info(
                f"Initialized GCS adapter: "
                f"bucket={bucket}, namespace={self.namespace_prefix}"
            )
            
        except GoogleCloudError as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise StorageError(f"GCS initialization failed: {e}")
    
    def get_full_path(self, path: str) -> str:
        """
        Get full GCS path with namespace prefix.
        
        Args:
            path: Relative path (e.g., "src/main.py")
        
        Returns:
            Full path (e.g., "users/user123/myproject/src/main.py")
        """
        # Remove leading slash if present
        path = path.lstrip('/')
        return f"{self.namespace_prefix}{path}"
    
    async def upload_file(
        self,
        path: str,
        content: bytes,
        content_type: Optional[str] = None
    ) -> FileMetadata:
        """
        Upload a file to GCS.
        
        Implementation:
        1. Get full path with namespace
        2. Detect content type if not provided
        3. Create blob and upload
        4. Return metadata
        
        Confidence: 90% - Standard GCS upload pattern
        """
        try:
            full_path = self.get_full_path(path)
            blob = self.bucket.blob(full_path)
            
            # Auto-detect content type
            if not content_type:
                content_type, _ = mimetypes.guess_type(path)
                content_type = content_type or 'application/octet-stream'
            
            # Upload content
            blob.upload_from_string(content, content_type=content_type)
            
            # Get metadata after upload
            blob.reload()
            
            return FileMetadata(
                path=path,
                size=blob.size,
                modified_time=blob.updated.isoformat() if blob.updated else datetime.utcnow().isoformat(),
                content_type=blob.content_type,
                etag=blob.etag
            )
            
        except GoogleCloudError as e:
            logger.error(f"Failed to upload {path}: {e}")
            raise StorageError(f"Upload failed: {e}")
    
    async def download_file(self, path: str) -> bytes:
        """
        Download a file from GCS.
        
        Confidence: 95% - Standard GCS download pattern
        """
        try:
            full_path = self.get_full_path(path)
            blob = self.bucket.blob(full_path)
            
            if not blob.exists():
                raise StorageError(f"File not found: {path}")
            
            return blob.download_as_bytes()
            
        except NotFound:
            raise StorageError(f"File not found: {path}")
        except GoogleCloudError as e:
            logger.error(f"Failed to download {path}: {e}")
            raise StorageError(f"Download failed: {e}")
    
    async def list_files(
        self,
        prefix: str = "",
        recursive: bool = True
    ) -> List[FileMetadata]:
        """
        List files in GCS with namespace prefix.
        
        Args:
            prefix: Directory prefix within namespace (e.g., "src/")
            recursive: Include subdirectories
        
        Returns:
            List of FileMetadata objects
        
        Implementation:
        1. Build full prefix with namespace
        2. List blobs with prefix
        3. Filter by delimiter if not recursive
        4. Convert to FileMetadata
        
        Confidence: 88% - GCS pagination needs testing at scale
        """
        try:
            # Build full prefix
            full_prefix = self.get_full_path(prefix)
            
            # List blobs
            if recursive:
                blobs = self.client.list_blobs(
                    self.bucket_name,
                    prefix=full_prefix
                )
            else:
                # Use delimiter for non-recursive listing
                blobs = self.client.list_blobs(
                    self.bucket_name,
                    prefix=full_prefix,
                    delimiter='/'
                )
            
            # Convert to FileMetadata
            files = []
            for blob in blobs:
                # Remove namespace prefix from path
                relative_path = blob.name[len(self.namespace_prefix):]
                
                files.append(FileMetadata(
                    path=relative_path,
                    size=blob.size or 0,
                    modified_time=blob.updated.isoformat() if blob.updated else "",
                    content_type=blob.content_type,
                    etag=blob.etag
                ))
            
            return files
            
        except GoogleCloudError as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            raise StorageError(f"List files failed: {e}")
    
    async def delete_file(self, path: str) -> None:
        """
        Delete a file from GCS.
        
        Confidence: 95% - Standard GCS delete pattern
        """
        try:
            full_path = self.get_full_path(path)
            blob = self.bucket.blob(full_path)
            
            if not blob.exists():
                logger.warning(f"File not found for deletion: {path}")
                return
            
            blob.delete()
            logger.info(f"Deleted file: {path}")
            
        except GoogleCloudError as e:
            logger.error(f"Failed to delete {path}: {e}")
            raise StorageError(f"Delete failed: {e}")
    
    async def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in GCS.
        
        Confidence: 98% - Simple existence check
        """
        try:
            full_path = self.get_full_path(path)
            blob = self.bucket.blob(full_path)
            return blob.exists()
        except GoogleCloudError as e:
            logger.error(f"Failed to check existence of {path}: {e}")
            return False
    
    async def get_file_metadata(self, path: str) -> FileMetadata:
        """
        Get metadata for a file without downloading content.
        
        Confidence: 92% - Standard GCS metadata access
        """
        try:
            full_path = self.get_full_path(path)
            blob = self.bucket.blob(full_path)
            
            if not blob.exists():
                raise StorageError(f"File not found: {path}")
            
            # Reload to get fresh metadata
            blob.reload()
            
            return FileMetadata(
                path=path,
                size=blob.size or 0,
                modified_time=blob.updated.isoformat() if blob.updated else "",
                content_type=blob.content_type,
                etag=blob.etag
            )
            
        except NotFound:
            raise StorageError(f"File not found: {path}")
        except GoogleCloudError as e:
            logger.error(f"Failed to get metadata for {path}: {e}")
            raise StorageError(f"Get metadata failed: {e}")
    
    # Stream upload/download for large files (optional optimization)
    
    async def upload_file_stream(
        self,
        path: str,
        stream: AsyncIterator[bytes],
        content_type: Optional[str] = None
    ) -> FileMetadata:
        """
        Upload a file using a stream (for large files).
        
        Note: This is an optimization for files > 10MB.
        For smaller files, use upload_file().
        
        Confidence: 82% - Needs testing with large files
        """
        try:
            full_path = self.get_full_path(path)
            blob = self.bucket.blob(full_path)
            
            if not content_type:
                content_type, _ = mimetypes.guess_type(path)
                content_type = content_type or 'application/octet-stream'
            
            # GCS doesn't support async streaming directly,
            # so we accumulate chunks (future: use resumable uploads)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)
            
            content = b''.join(chunks)
            blob.upload_from_string(content, content_type=content_type)
            blob.reload()
            
            return FileMetadata(
                path=path,
                size=blob.size,
                modified_time=blob.updated.isoformat() if blob.updated else datetime.utcnow().isoformat(),
                content_type=blob.content_type,
                etag=blob.etag
            )
            
        except GoogleCloudError as e:
            logger.error(f"Failed to stream upload {path}: {e}")
            raise StorageError(f"Stream upload failed: {e}")
    
    async def download_file_stream(
        self,
        path: str,
        chunk_size: int = 1024 * 1024  # 1MB chunks
    ) -> AsyncIterator[bytes]:
        """
        Download a file as a stream (for large files).
        
        Confidence: 80% - Async stream conversion needs testing
        """
        try:
            full_path = self.get_full_path(path)
            blob = self.bucket.blob(full_path)
            
            if not blob.exists():
                raise StorageError(f"File not found: {path}")
            
            # Download in chunks
            # Note: google-cloud-storage doesn't support async streaming,
            # so we download synchronously and yield chunks
            content = blob.download_as_bytes()
            
            # Yield chunks
            for i in range(0, len(content), chunk_size):
                yield content[i:i + chunk_size]
                
        except NotFound:
            raise StorageError(f"File not found: {path}")
        except GoogleCloudError as e:
            logger.error(f"Failed to stream download {path}: {e}")
            raise StorageError(f"Stream download failed: {e}")
    
    def get_public_url(self, path: str, expiration_seconds: int = 3600) -> str:
        """
        Generate a signed URL for temporary public access.
        
        Args:
            path: Relative path
            expiration_seconds: URL validity duration (default: 1 hour)
        
        Returns:
            Signed URL
        
        Note: Requires service account credentials with signing permission.
        With Workload Identity, this may not work. Use Cloud Run service URLs instead.
        
        Confidence: 70% - Signing requires specific credentials
        """
        try:
            full_path = self.get_full_path(path)
            blob = self.bucket.blob(full_path)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=expiration_seconds,
                method="GET"
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {path}: {e}")
            raise StorageError(
                f"Signed URL generation failed: {e}. "
                f"Ensure service account has signing permissions."
            )


# Export public API
__all__ = ['GCSAdapter']



