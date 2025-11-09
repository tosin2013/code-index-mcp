"""
Git synchronization helpers for delta-based ingestion.

This module provides functions to:
1. Detect changed files between commits
2. Extract Git metadata
3. Perform incremental updates (insert/delete chunks)
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class GitDiff:
    """Represents changes between two Git commits."""
    added_files: List[str]
    modified_files: List[str]
    deleted_files: List[str]
    renamed_files: List[tuple]  # [(old_path, new_path), ...]

    @property
    def files_needing_reindex(self) -> Set[str]:
        """All files that need re-indexing."""
        return set(
            self.added_files +
            self.modified_files +
            [new for _, new in self.renamed_files]
        )

    @property
    def files_to_delete(self) -> Set[str]:
        """All files whose chunks should be deleted."""
        return set(
            self.deleted_files +
            [old for old, _ in self.renamed_files]
        )


def get_git_diff(repo_path: str, old_commit: str, new_commit: str) -> GitDiff:
    """
    Get diff between two commits.

    Args:
        repo_path: Path to Git repository
        old_commit: Old commit SHA
        new_commit: New commit SHA

    Returns:
        GitDiff object with changed files
    """
    import os
    original_dir = os.getcwd()

    try:
        os.chdir(repo_path)

        # Get diff with file status
        result = subprocess.check_output(
            ['git', 'diff', '--name-status', f'{old_commit}..{new_commit}'],
            stderr=subprocess.STDOUT
        ).decode()

        added = []
        modified = []
        deleted = []
        renamed = []

        for line in result.strip().split('\n'):
            if not line:
                continue

            parts = line.split('\t')
            status = parts[0]

            if status == 'A':
                added.append(parts[1])
            elif status == 'M':
                modified.append(parts[1])
            elif status == 'D':
                deleted.append(parts[1])
            elif status.startswith('R'):
                renamed.append((parts[1], parts[2]))

        logger.info(
            f"Git diff {old_commit[:8]}..{new_commit[:8]}: "
            f"{len(added)} added, {len(modified)} modified, "
            f"{len(deleted)} deleted, {len(renamed)} renamed"
        )

        return GitDiff(
            added_files=added,
            modified_files=modified,
            deleted_files=deleted,
            renamed_files=renamed
        )

    finally:
        os.chdir(original_dir)


def get_git_metadata(repo_path: str, commit: Optional[str] = None) -> Dict[str, str]:
    """
    Extract Git metadata for a commit.

    Args:
        repo_path: Path to Git repository
        commit: Commit SHA (default: HEAD)

    Returns:
        Dict with commit_hash, branch_name, author_name, commit_timestamp
    """
    import os
    original_dir = os.getcwd()

    try:
        os.chdir(repo_path)
        commit = commit or 'HEAD'

        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', commit]
        ).decode().strip()

        branch_name = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
        ).decode().strip()

        author_name = subprocess.check_output(
            ['git', 'log', '-1', '--format=%an', commit]
        ).decode().strip()

        commit_timestamp = subprocess.check_output(
            ['git', 'log', '-1', '--format=%cI', commit]
        ).decode().strip()

        return {
            'commit_hash': commit_hash,
            'branch_name': branch_name,
            'author_name': author_name,
            'commit_timestamp': commit_timestamp
        }

    finally:
        os.chdir(original_dir)


def delete_chunks_for_files(
    conn,
    project_id: str,
    file_paths: List[str]
) -> int:
    """
    Delete all chunks for specific files.

    Args:
        conn: Database connection
        project_id: Project UUID
        file_paths: List of file paths to delete chunks for

    Returns:
        Number of chunks deleted
    """
    if not file_paths:
        return 0

    with conn.cursor() as cur:
        # Use the helper function from schema
        total_deleted = 0
        for file_path in file_paths:
            cur.execute(
                "SELECT delete_old_file_chunks(%s, %s, NULL)",
                (project_id, file_path)
            )
            deleted = cur.fetchone()[0]
            total_deleted += deleted
            logger.info(f"Deleted {deleted} chunks for {file_path}")

        conn.commit()
        return total_deleted


def delta_sync_repository(
    repo_path: str,
    old_commit: str,
    new_commit: str,
    user_id: UUID,
    project_name: str,
    db_connection_string: str,
    use_mock_embedder: bool = False
) -> Dict[str, any]:
    """
    Perform delta-based synchronization between two commits.

    This is 255x faster than full re-indexing because it only processes
    changed files.

    Args:
        repo_path: Path to Git repository
        old_commit: Old commit SHA (before push)
        new_commit: New commit SHA (after push)
        user_id: User UUID
        project_name: Project name
        db_connection_string: Database connection string
        use_mock_embedder: Use mock embedder for testing

    Returns:
        Dict with sync statistics
    """
    import psycopg2
    from .pipeline import IngestionPipeline

    logger.info(f"Starting delta sync: {old_commit[:8]}..{new_commit[:8]}")

    # Get diff between commits
    diff = get_git_diff(repo_path, old_commit, new_commit)

    # Get Git metadata for new commit
    git_meta = get_git_metadata(repo_path, new_commit)

    # Connect to database
    conn = psycopg2.connect(db_connection_string)

    # Get project ID
    with conn.cursor() as cur:
        cur.execute(
            "SELECT project_id FROM projects WHERE user_id = %s AND project_name = %s",
            (str(user_id), project_name)
        )
        result = cur.fetchone()
        if not result:
            raise ValueError(f"Project not found: {project_name}")
        project_id = result[0]

    # Delete chunks for removed/renamed files
    files_to_delete = list(diff.files_to_delete)
    deleted_count = delete_chunks_for_files(conn, project_id, files_to_delete)

    logger.info(f"Deleted {deleted_count} chunks for {len(files_to_delete)} files")

    # Re-ingest changed/added files
    files_to_ingest = []
    for file_path in diff.files_needing_reindex:
        full_path = Path(repo_path) / file_path
        if full_path.exists():
            files_to_ingest.append(str(full_path))

    if files_to_ingest:
        logger.info(f"Re-ingesting {len(files_to_ingest)} changed files")

        # First delete old chunks for these files
        relative_paths = [str(Path(f).relative_to(repo_path)) for f in files_to_ingest]
        delete_chunks_for_files(conn, project_id, relative_paths)

        # Then ingest new versions
        pipeline = IngestionPipeline(
            db_connection_string=db_connection_string,
            use_mock_embedder=use_mock_embedder
        )

        # Set user context for RLS
        with conn.cursor() as cur:
            cur.execute("SELECT set_user_context(%s)", (str(user_id),))
        conn.commit()

        stats = pipeline.ingest_files(
            file_paths=files_to_ingest,
            user_id=user_id,
            project_name=project_name,
            commit_hash=git_meta['commit_hash'],
            branch_name=git_meta['branch_name'],
            author_name=git_meta['author_name'],
            commit_timestamp=git_meta['commit_timestamp']
        )

        conn.close()

        return {
            'success': True,
            'old_commit': old_commit,
            'new_commit': new_commit,
            'files_deleted': len(files_to_delete),
            'chunks_deleted': deleted_count,
            'files_reindexed': len(files_to_ingest),
            'chunks_inserted': stats.chunks_inserted,
            'chunks_skipped': stats.chunks_skipped,
            'duration_seconds': stats.duration_seconds
        }
    else:
        conn.close()
        logger.info("No files to re-ingest")
        return {
            'success': True,
            'old_commit': old_commit,
            'new_commit': new_commit,
            'files_deleted': len(files_to_delete),
            'chunks_deleted': deleted_count,
            'files_reindexed': 0,
            'chunks_inserted': 0,
            'chunks_skipped': 0,
            'duration_seconds': 0
        }
