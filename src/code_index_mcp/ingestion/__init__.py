"""
Code ingestion module for semantic search.

This module handles chunking code into searchable units, extracting metadata,
generating embeddings, and storing in AlloyDB for vector search.

Phase 3A - Git-Sync:
- GitRepositoryManager: Manages Git repositories with Cloud Storage backend
- Supports GitHub, GitLab, Bitbucket, Gitea
- Auto-sync via webhooks
"""

from .chunker import (
    CodeChunk,
    ChunkStrategy,
    CodeChunker,
    chunk_file,
    chunk_directory,
)

from .pipeline import (
    IngestionPipeline,
    IngestionStats,
    ingest_directory,
    ingest_files,
)

from .git_manager import (
    GitRepositoryManager,
    GitRepositoryInfo,
    GitManagerError,
)

__all__ = [
    "CodeChunk",
    "ChunkStrategy",
    "CodeChunker",
    "chunk_file",
    "chunk_directory",
    "IngestionPipeline",
    "IngestionStats",
    "ingest_directory",
    "ingest_files",
    "GitRepositoryManager",
    "GitRepositoryInfo",
    "GitManagerError",
]


