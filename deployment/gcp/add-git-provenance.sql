-- Phase 1: Add Git Provenance to code_chunks
-- Based on Section 5 recommendations: https://www.timescale.com/blog/pgvector-for-semantic-search-performance-best-practices/

-- Add Git metadata columns to code_chunks
ALTER TABLE code_chunks
ADD COLUMN IF NOT EXISTS commit_hash VARCHAR(40),
ADD COLUMN IF NOT EXISTS branch_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS author_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS commit_timestamp TIMESTAMPTZ;

-- Create composite index for efficient delta-sync operations
-- This enables fast deletion of chunks when files change between commits
CREATE INDEX IF NOT EXISTS idx_code_chunks_git_provenance
ON code_chunks(project_id, commit_hash, file_path);

-- Add index on commit_timestamp for temporal queries
CREATE INDEX IF NOT EXISTS idx_code_chunks_commit_timestamp
ON code_chunks(commit_timestamp);

-- Update projects table to track current commit
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS current_commit_hash VARCHAR(40),
ADD COLUMN IF NOT EXISTS current_branch VARCHAR(100) DEFAULT 'main';

-- View for tracking Git sync status
CREATE OR REPLACE VIEW git_sync_status AS
SELECT
    p.project_name,
    p.user_id,
    p.current_commit_hash,
    p.current_branch,
    COUNT(DISTINCT c.commit_hash) as unique_commits_indexed,
    MAX(c.commit_timestamp) as latest_commit_indexed,
    COUNT(c.chunk_id) as total_chunks
FROM projects p
LEFT JOIN code_chunks c ON p.project_id = c.project_id
GROUP BY p.project_id, p.project_name, p.user_id, p.current_commit_hash, p.current_branch;

-- Function for delta-sync cleanup (delete chunks from old file versions)
CREATE OR REPLACE FUNCTION delete_old_file_chunks(
    p_project_id UUID,
    p_file_path TEXT,
    p_exclude_commit_hash VARCHAR(40)
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    -- Delete all chunks for this file EXCEPT the current commit
    DELETE FROM code_chunks
    WHERE
        project_id = p_project_id
        AND file_path = p_file_path
        AND (commit_hash IS DISTINCT FROM p_exclude_commit_hash);

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RETURN v_deleted_count;
END;
$$;

-- Function to get modified files between commits (for delta-sync)
CREATE OR REPLACE FUNCTION get_files_needing_reindex(
    p_project_id UUID,
    p_old_commit VARCHAR(40),
    p_new_commit VARCHAR(40)
)
RETURNS TABLE (
    file_path TEXT,
    chunk_count BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Return all files that exist in the old commit but need updating
    RETURN QUERY
    SELECT
        c.file_path,
        COUNT(*) as chunk_count
    FROM code_chunks c
    WHERE
        c.project_id = p_project_id
        AND c.commit_hash = p_old_commit
    GROUP BY c.file_path;
END;
$$;

COMMENT ON COLUMN code_chunks.commit_hash IS 'Git commit SHA-1 hash (40 chars) - enables delta-based synchronization';
COMMENT ON COLUMN code_chunks.branch_name IS 'Git branch name this chunk was indexed from';
COMMENT ON COLUMN code_chunks.author_name IS 'Git commit author - useful for UI display';
COMMENT ON COLUMN code_chunks.commit_timestamp IS 'Git commit timestamp - enables temporal queries';
COMMENT ON INDEX idx_code_chunks_git_provenance IS 'Composite index for efficient delta-sync: delete old file versions during Git updates';
COMMENT ON FUNCTION delete_old_file_chunks IS 'Delta-sync helper: removes old chunks when file changes between commits';
COMMENT ON VIEW git_sync_status IS 'Shows Git sync status per project: current commit, indexed commits, chunk count';

-- Completion notice
DO $$
BEGIN
    RAISE NOTICE '==========================================';
    RAISE NOTICE 'Git Provenance Schema Enhancement Applied!';
    RAISE NOTICE '==========================================';
    RAISE NOTICE 'New Columns:';
    RAISE NOTICE '  • commit_hash (VARCHAR 40)';
    RAISE NOTICE '  • branch_name (VARCHAR 100)';
    RAISE NOTICE '  • author_name (VARCHAR 255)';
    RAISE NOTICE '  • commit_timestamp (TIMESTAMPTZ)';
    RAISE NOTICE '';
    RAISE NOTICE 'New Indexes:';
    RAISE NOTICE '  • idx_code_chunks_git_provenance';
    RAISE NOTICE '  • idx_code_chunks_commit_timestamp';
    RAISE NOTICE '';
    RAISE NOTICE 'New Functions:';
    RAISE NOTICE '  • delete_old_file_chunks()';
    RAISE NOTICE '  • get_files_needing_reindex()';
    RAISE NOTICE '';
    RAISE NOTICE 'New Views:';
    RAISE NOTICE '  • git_sync_status';
    RAISE NOTICE '==========================================';
END $$;
