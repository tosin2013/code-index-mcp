"""
Code ingestion module for semantic search.

This module handles chunking code into searchable units, extracting metadata,
generating embeddings, and storing in AlloyDB for vector search.

Phase 3A - Git-Sync:
- GitRepositoryManager: Manages Git repositories with Cloud Storage backend
- Supports GitHub, GitLab, Bitbucket, Gitea
- Auto-sync via webhooks
"""

from .chunker import ChunkStrategy, CodeChunk, CodeChunker, chunk_directory, chunk_file
from .git_manager import GitManagerError, GitRepositoryInfo, GitRepositoryManager
from .pipeline import IngestionPipeline, IngestionStats, ingest_directory, ingest_files

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
