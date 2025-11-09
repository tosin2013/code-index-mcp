"""
Base Storage Adapter Interface for Code Index MCP Server.

Defines the abstract interface that all storage backends must implement.
This ensures consistent behavior across local filesystem, GCS, S3, and ODF.

Confidence: 95% - Interface design based on proven patterns
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, List, Optional


class StorageError(Exception):
    """Base exception for storage operations."""

    pass


@dataclass
class FileMetadata:
    """Metadata for a stored file."""

    path: str
    size: int
    modified_time: str
    content_type: Optional[str] = None
    etag: Optional[str] = None

    def is_directory(self) -> bool:
        """Check if this represents a directory."""
        return self.path.endswith("/")


class BaseStorageAdapter(ABC):
    """
    Abstract base class for storage adapters.

    All storage implementations (GCS, S3, ODF, local) must implement
    this interface to ensure consistent behavior across deployment modes.

    Design Principles:
    - Async I/O for all operations (non-blocking)
    - Stream-based uploads/downloads (memory efficient)
    - User namespace isolation (multi-tenant support)
    - Consistent error handling (StorageError hierarchy)

    Path Format:
    - Relative paths: "src/main.py", "docs/README.md"
    - Directory paths: "src/", "docs/" (trailing slash)
    - No leading slashes

    Namespace Isolation:
    - User files stored under: users/{user_id}/{project_name}/
    - Indexes stored under: users/{user_id}/{project_name}/.indexes/
    - Settings stored under: users/{user_id}/{project_name}/.settings/
    """

    @abstractmethod
    async def upload_file(
        self, path: str, content: bytes, content_type: Optional[str] = None
    ) -> FileMetadata:
        """
        Upload a file to storage.

        Args:
            path: Relative path within project (e.g., "src/main.py")
            content: File content as bytes
            content_type: MIME type (optional, auto-detected if None)

        Returns:
            FileMetadata with upload details

        Raises:
            StorageError: If upload fails
        """
        pass

    @abstractmethod
    async def download_file(self, path: str) -> bytes:
        """
        Download a file from storage.

        Args:
            path: Relative path within project

        Returns:
            File content as bytes

        Raises:
            StorageError: If file not found or download fails
        """
        pass

    @abstractmethod
    async def list_files(self, prefix: str = "", recursive: bool = True) -> List[FileMetadata]:
        """
        List files in storage.

        Args:
            prefix: Directory prefix (e.g., "src/")
            recursive: Include subdirectories

        Returns:
            List of FileMetadata objects

        Raises:
            StorageError: If listing fails
        """
        pass

    @abstractmethod
    async def delete_file(self, path: str) -> None:
        """
        Delete a file from storage.

        Args:
            path: Relative path within project

        Raises:
            StorageError: If deletion fails
        """
        pass

    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """
        Check if a file exists.

        Args:
            path: Relative path within project

        Returns:
            True if file exists
        """
        pass

    @abstractmethod
    async def get_file_metadata(self, path: str) -> FileMetadata:
        """
        Get metadata for a file.

        Args:
            path: Relative path within project

        Returns:
            FileMetadata object

        Raises:
            StorageError: If file not found
        """
        pass

    @abstractmethod
    def get_full_path(self, path: str) -> str:
        """
        Get the full storage path including namespace.

        Args:
            path: Relative path within project

        Returns:
            Full path with namespace prefix

        Example:
            "src/main.py" → "users/user123/myproject/src/main.py"
        """
        pass


class StreamUploadMixin:
    """
    Mixin for stream-based uploads (large files).

    Optional: Implement this if the storage backend supports
    efficient streaming without loading entire file into memory.
    """

    async def upload_file_stream(
        self, path: str, stream: AsyncIterator[bytes], content_type: Optional[str] = None
    ) -> FileMetadata:
        """
        Upload a file using a stream.

        Args:
            path: Relative path
            stream: Async iterator yielding chunks
            content_type: MIME type (optional)

        Returns:
            FileMetadata
        """
        raise NotImplementedError("Stream upload not supported")

    async def download_file_stream(self, path: str) -> AsyncIterator[bytes]:
        """
        Download a file as a stream.

        Args:
            path: Relative path

        Yields:
            Chunks of file content
        """
        raise NotImplementedError("Stream download not supported")
