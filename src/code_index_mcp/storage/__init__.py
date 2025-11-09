"""
Storage package for Code Index MCP Server.

This package provides cloud storage adapters for HTTP mode:
- Google Cloud Storage (GCS) - ADR 0002
- AWS S3 - ADR 0006 (future)
- OpenShift ODF S3 - ADR 0007 (future)

Architecture:
- BaseStorageAdapter: Abstract interface for all storage backends
- GCSAdapter: Google Cloud Storage implementation
- S3Adapter: AWS S3 implementation (future)
- ODFAdapter: OpenShift Data Foundation S3 (future)

Usage:
    # Local mode (default)
    from pathlib import Path
    storage = LocalFileSystem(Path("/path/to/project"))

    # Cloud mode (GCS)
    storage = GCSAdapter(
        bucket="code-index-projects",
        user_id="user123",
        project_id="my-gcp-project"
    )

    # Operations (same interface for all adapters)
    await storage.upload_file("src/main.py", content)
    content = await storage.download_file("src/main.py")
    files = await storage.list_files("src/")
"""

from .base_adapter import BaseStorageAdapter, StorageError
from .gcs_adapter import GCSAdapter

__all__ = ["BaseStorageAdapter", "StorageError", "GCSAdapter"]
