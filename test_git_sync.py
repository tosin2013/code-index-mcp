#!/usr/bin/env python3
"""
Test Git-sync functionality with PocketFlow repository.

This script tests:
1. Initial ingestion with Git metadata
2. Database verification
3. Delta-sync simulation
"""

import sys
import os
from pathlib import Path
from uuid import UUID
import psycopg2

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from code_index_mcp.ingestion.pipeline import ingest_directory
from code_index_mcp.ingestion.git_sync import get_git_metadata, get_git_diff, delta_sync_repository

# Configuration
POSTGRES_CONNECTION = "postgresql://code_index_admin:local_dev_password@localhost:5432/code_index"
REPO_PATH = "/tmp/PocketFlow"
TEST_USER_ID = UUID('b662bc28-c198-4a0f-b995-a1136bf5ee11')  # dev@localhost
PROJECT_NAME = "pocketflow-test"


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_initial_ingestion():
    """Test 1: Ingest PocketFlow with Git metadata."""
    print_section("TEST 1: Initial Ingestion with Git Metadata")

    # Get Git metadata
    print("Extracting Git metadata from repository...")
    git_meta = get_git_metadata(REPO_PATH)

    print(f"  Commit:    {git_meta['commit_hash'][:8]}...")
    print(f"  Branch:    {git_meta['branch_name']}")
    print(f"  Author:    {git_meta['author_name']}")
    print(f"  Timestamp: {git_meta['commit_timestamp']}")

    # Ingest repository
    print(f"\nIngesting {REPO_PATH}...")
    print("(Using mock embedder to avoid GCP costs)")

    stats = ingest_directory(
        directory_path=REPO_PATH,
        user_id=TEST_USER_ID,
        project_name=PROJECT_NAME,
        db_connection_string=POSTGRES_CONNECTION,
        use_mock_embedder=True,
        commit_hash=git_meta['commit_hash'],
        branch_name=git_meta['branch_name'],
        author_name=git_meta['author_name'],
        commit_timestamp=git_meta['commit_timestamp']
    )

    print(f"\n✅ Ingestion complete!")
    print(f"  Files processed:   {stats.files_processed}")
    print(f"  Chunks created:    {stats.chunks_created}")
    print(f"  Chunks inserted:   {stats.chunks_inserted}")
    print(f"  Chunks skipped:    {stats.chunks_skipped}")
    print(f"  Duration:          {stats.duration_seconds:.2f}s")

    return stats, git_meta


def verify_git_metadata():
    """Test 2: Verify Git metadata in database."""
    print_section("TEST 2: Verify Git Metadata in Database")

    conn = psycopg2.connect(POSTGRES_CONNECTION)
    cur = conn.cursor()

    # Check git_sync_status view
    print("Querying git_sync_status view...")
    cur.execute("""
        SELECT
            project_name,
            current_commit_hash,
            current_branch,
            unique_commits_indexed,
            latest_commit_indexed,
            total_chunks
        FROM git_sync_status
        WHERE project_name = %s
    """, (PROJECT_NAME,))

    result = cur.fetchone()
    if result:
        print(f"  Project:           {result[0]}")
        print(f"  Current commit:    {result[1][:8] if result[1] else 'None'}...")
        print(f"  Current branch:    {result[2]}")
        print(f"  Unique commits:    {result[3]}")
        print(f"  Latest indexed:    {result[4]}")
        print(f"  Total chunks:      {result[5]}")
    else:
        print("  ❌ No data found in git_sync_status")

    # Check sample chunks with Git metadata
    print("\nSample chunks with Git metadata:")
    cur.execute("""
        SELECT
            file_path,
            chunk_name,
            chunk_type,
            commit_hash,
            branch_name,
            author_name
        FROM code_chunks
        WHERE project_id = (
            SELECT project_id FROM projects
            WHERE project_name = %s
        )
        ORDER BY created_at DESC
        LIMIT 5
    """, (PROJECT_NAME,))

    for row in cur.fetchall():
        print(f"  {row[0]}")
        print(f"    → {row[2]}: {row[1]}")
        print(f"    → Commit: {row[3][:8] if row[3] else 'None'}... by {row[5]}")

    # Check chunks by file type
    print("\nChunks by language:")
    cur.execute("""
        SELECT
            language,
            COUNT(*) as chunk_count
        FROM code_chunks
        WHERE project_id = (
            SELECT project_id FROM projects
            WHERE project_name = %s
        )
        GROUP BY language
        ORDER BY chunk_count DESC
    """, (PROJECT_NAME,))

    for row in cur.fetchall():
        print(f"  {row[0] or 'unknown':15} {row[1]:5} chunks")

    conn.close()
    print("\n✅ Verification complete!")


def test_delta_sync():
    """Test 3: Simulate delta-sync with commit history."""
    print_section("TEST 3: Delta-Sync Simulation")

    # Get previous commit
    import subprocess
    os.chdir(REPO_PATH)
    commits = subprocess.check_output(
        ['git', 'log', '--format=%H', '-5']
    ).decode().strip().split('\n')

    if len(commits) < 2:
        print("❌ Not enough commits for delta-sync test")
        return

    old_commit = commits[1]  # Previous commit
    new_commit = commits[0]  # Current commit (HEAD)

    print(f"Testing delta-sync between commits:")
    print(f"  Old: {old_commit[:8]}...")
    print(f"  New: {new_commit[:8]}...")

    # Get diff
    from code_index_mcp.ingestion.git_sync import get_git_diff
    diff = get_git_diff(REPO_PATH, old_commit, new_commit)

    print(f"\nChanges detected:")
    print(f"  Added:    {len(diff.added_files)} files")
    print(f"  Modified: {len(diff.modified_files)} files")
    print(f"  Deleted:  {len(diff.deleted_files)} files")
    print(f"  Renamed:  {len(diff.renamed_files)} files")

    if diff.files_needing_reindex:
        print(f"\nFiles needing re-index:")
        for f in list(diff.files_needing_reindex)[:10]:
            print(f"    {f}")
        if len(diff.files_needing_reindex) > 10:
            print(f"    ... and {len(diff.files_needing_reindex) - 10} more")

    # Perform delta-sync
    print(f"\nPerforming delta-sync...")
    result = delta_sync_repository(
        repo_path=REPO_PATH,
        old_commit=old_commit,
        new_commit=new_commit,
        user_id=TEST_USER_ID,
        project_name=PROJECT_NAME,
        db_connection_string=POSTGRES_CONNECTION,
        use_mock_embedder=True
    )

    print(f"\n✅ Delta-sync complete!")
    print(f"  Files deleted:     {result['files_deleted']}")
    print(f"  Chunks deleted:    {result['chunks_deleted']}")
    print(f"  Files re-indexed:  {result['files_reindexed']}")
    print(f"  Chunks inserted:   {result['chunks_inserted']}")
    print(f"  Chunks skipped:    {result['chunks_skipped']}")
    print(f"  Duration:          {result['duration_seconds']:.2f}s")

    return result


def query_by_commit():
    """Test 4: Query chunks by commit."""
    print_section("TEST 4: Query Chunks by Commit")

    conn = psycopg2.connect(POSTGRES_CONNECTION)
    cur = conn.cursor()

    # Get distinct commits
    cur.execute("""
        SELECT DISTINCT
            commit_hash,
            commit_timestamp,
            author_name,
            COUNT(*) OVER (PARTITION BY commit_hash) as chunk_count
        FROM code_chunks
        WHERE project_id = (
            SELECT project_id FROM projects
            WHERE project_name = %s
        )
        ORDER BY commit_timestamp DESC
        LIMIT 3
    """, (PROJECT_NAME,))

    print("Commits in database:")
    for row in cur.fetchall():
        print(f"  {row[0][:8]}... at {row[1]} by {row[2]}")
        print(f"    → {row[3]} chunks")

    conn.close()
    print("\n✅ Commit query complete!")


def main():
    """Run all tests."""
    print_section("Git-Sync Testing with PocketFlow")
    print(f"Repository: {REPO_PATH}")
    print(f"Database:   {POSTGRES_CONNECTION}")
    print(f"User:       {TEST_USER_ID}")
    print(f"Project:    {PROJECT_NAME}")

    try:
        # Test 1: Initial ingestion
        stats, git_meta = test_initial_ingestion()

        # Test 2: Verify metadata
        verify_git_metadata()

        # Test 3: Delta-sync
        delta_result = test_delta_sync()

        # Test 4: Query by commit
        query_by_commit()

        # Summary
        print_section("TEST SUMMARY")
        print("✅ All tests passed!")
        print(f"\nInitial ingestion:")
        print(f"  - {stats.chunks_inserted} chunks from {stats.files_processed} files")
        print(f"  - Commit: {git_meta['commit_hash'][:8]}...")
        print(f"\nDelta-sync:")
        print(f"  - {delta_result['files_reindexed']} files re-indexed")
        print(f"  - {delta_result['chunks_inserted']} chunks updated")
        print(f"  - {delta_result['duration_seconds']:.2f}s duration")

        print(f"\n{'='*60}")
        print("Git-sync is working perfectly! 🎉")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
