# Git-Sync Implementation Guide

**Status**: Schema ✅ | Pipeline ✅ | Delta-Sync ⏳

---

## Overview

This guide shows how to implement **delta-based Git synchronization** for 255x faster updates and 500x cost savings compared to full re-indexing.

**What's Been Done:**
1. ✅ Added Git provenance columns to `code_chunks` table
2. ✅ Updated ingestion pipeline to accept Git metadata
3. ⏳ Next: Implement delta-based sync for webhooks

---

## Part 1: Using the Enhanced Ingestion Pipeline

### Example: Ingest with Git Metadata

```python
from code_index_mcp.ingestion.pipeline import ingest_directory
from uuid import UUID
import subprocess
from datetime import datetime

# Get Git metadata
def get_git_metadata(repo_path: str) -> dict:
    """Extract Git metadata from repository."""
    import os
    os.chdir(repo_path)

    commit_hash = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD']
    ).decode().strip()

    branch_name = subprocess.check_output(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
    ).decode().strip()

    author_name = subprocess.check_output(
        ['git', 'log', '-1', '--format=%an']
    ).decode().strip()

    commit_timestamp = subprocess.check_output(
        ['git', 'log', '-1', '--format=%cI']
    ).decode().strip()

    return {
        'commit_hash': commit_hash,
        'branch_name': branch_name,
        'author_name': author_name,
        'commit_timestamp': commit_timestamp
    }

# Ingest with Git metadata
git_meta = get_git_metadata('/path/to/repo')

stats = ingest_directory(
    directory_path='/path/to/repo',
    user_id=UUID('your-user-uuid'),
    project_name='my-project',
    db_connection_string='postgresql://...',
    commit_hash=git_meta['commit_hash'],
    branch_name=git_meta['branch_name'],
    author_name=git_meta['author_name'],
    commit_timestamp=git_meta['commit_timestamp']
)

print(f"Ingested {stats.chunks_inserted} chunks from commit {git_meta['commit_hash'][:8]}")
```

---

## Part 2: Delta-Based Sync Implementation

### Step 1: Create Git Helper Module

Create `src/code_index_mcp/ingestion/git_sync.py`:

```python
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
```

### Step 2: Create Delta-Sync Function

Add to `git_sync.py`:

```python
from uuid import UUID
from .pipeline import IngestionPipeline, IngestionStats
import psycopg2


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
```

### Step 3: Add Webhook Handler

Create `src/code_index_mcp/admin/webhook_handlers.py`:

```python
"""
Webhook handlers for Git-sync automation.

Supports GitHub, GitLab, Gitea push events.
"""

from fastapi import Request, HTTPException, Header
from typing import Optional
import hmac
import hashlib
import logging

from ..ingestion.git_sync import delta_sync_repository

logger = logging.getLogger(__name__)


async def handle_github_webhook(
    request: Request,
    signature: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    webhook_secret: str = None
):
    """
    Handle GitHub push webhook for automatic delta-sync.

    Webhook URL: https://your-server.run.app/webhook/github
    Secret: Set GITHUB_WEBHOOK_SECRET environment variable
    """
    body = await request.body()

    # Verify signature
    if webhook_secret:
        expected_sig = 'sha256=' + hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature or '', expected_sig):
            raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse payload
    import json
    payload = json.loads(body)

    # Extract commit info
    repo_url = payload['repository']['clone_url']
    old_commit = payload['before']
    new_commit = payload['after']
    branch = payload['ref'].split('/')[-1]  # refs/heads/main -> main

    # TODO: Map repo_url to user_id and project_name
    # This requires a repo_mappings table or similar

    logger.info(
        f"GitHub push: {repo_url} {branch} "
        f"{old_commit[:8]}..{new_commit[:8]}"
    )

    # Trigger delta-sync
    # result = delta_sync_repository(...)

    return {
        'status': 'received',
        'repo': repo_url,
        'branch': branch,
        'commits': f"{old_commit[:8]}..{new_commit[:8]}"
    }
```

---

## Part 3: Performance Comparison

### Scenario: 2 Changed Files in 1,000-File Repository

**Full Re-index (Current):**
```
1. DELETE all 50,000 chunks             → 30 seconds
2. Process all 1,000 files              → 5 minutes
3. Generate 50,000 embeddings           → 10 minutes
4. INSERT 50,000 chunks                 → 2 minutes
----------------------------------------
Total: ~17 minutes
Cost: $5-10 (Vertex AI embeddings)
```

**Delta-Sync (With Git Provenance):**
```
1. git diff old..new                    → 1 second
2. DELETE 100 chunks (2 files)          → 0.1 seconds
3. Process 2 files                      → 1 second
4. Generate 100 embeddings              → 2 seconds
5. INSERT 100 chunks                    → 0.1 seconds
----------------------------------------
Total: ~4 seconds
Cost: $0.01 (Vertex AI embeddings)

Improvement: 255x faster, 500x cheaper
```

---

## Part 4: Testing the Implementation

### Test 1: Manual Delta-Sync

```python
from code_index_mcp.ingestion.git_sync import delta_sync_repository
from uuid import UUID

result = delta_sync_repository(
    repo_path='/path/to/repo',
    old_commit='abc123',  # Get from git log
    new_commit='HEAD',
    user_id=UUID('your-user-uuid'),
    project_name='test-project',
    db_connection_string='postgresql://code_index_admin:local_dev_password@localhost:5432/code_index',
    use_mock_embedder=True  # For testing
)

print(result)
```

### Test 2: Verify Git Metadata

```sql
-- Check Git metadata in database
SELECT
    file_path,
    commit_hash,
    branch_name,
    author_name,
    commit_timestamp
FROM code_chunks
WHERE project_id = 'your-project-id'
ORDER BY commit_timestamp DESC
LIMIT 10;

-- Check git_sync_status view
SELECT * FROM git_sync_status
WHERE project_name = 'test-project';
```

### Test 3: Query Files by Commit

```sql
-- Find all chunks from a specific commit
SELECT file_path, chunk_name, chunk_type
FROM code_chunks
WHERE commit_hash = 'abc123...'
AND project_id = 'your-project-id';

-- Compare chunks between commits
SELECT
    old.file_path,
    old.chunk_name,
    old.commit_hash as old_commit,
    new.commit_hash as new_commit,
    old.content != new.content as content_changed
FROM code_chunks old
JOIN code_chunks new ON
    old.project_id = new.project_id
    AND old.file_path = new.file_path
    AND old.chunk_name = new.chunk_name
WHERE
    old.commit_hash = 'old_commit_sha'
    AND new.commit_hash = 'new_commit_sha';
```

---

## Part 5: Next Steps

1. **Create `git_sync.py` module** with helper functions
2. **Add webhook handler** to FastAPI server
3. **Test delta-sync** with real repository
4. **Deploy to Cloud Run** with webhook URL
5. **Configure GitHub webhook** to trigger auto-sync

---

## Reference: Database Helper Functions

The schema includes these helper functions for delta-sync:

```sql
-- Delete old chunks when file changes
SELECT delete_old_file_chunks(
    project_id := 'uuid',
    file_path := 'src/main.py',
    exclude_commit_hash := 'new_commit_sha'
);

-- Get files needing reindex
SELECT * FROM get_files_needing_reindex(
    project_id := 'uuid',
    old_commit := 'abc123',
    new_commit := 'def456'
);

-- Check sync status
SELECT * FROM git_sync_status
WHERE project_name = 'my-project';
```

---

## Summary

✅ **Schema enhanced** with Git provenance columns
✅ **Pipeline updated** to accept Git metadata
⏳ **Next:** Implement `git_sync.py` and webhook handler

**Key Benefit:** 255x faster updates, 500x cost savings vs. full re-indexing
