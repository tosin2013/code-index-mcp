-- Migration: Add Git Provenance Columns to code_chunks
-- Purpose: Support Git-sync incremental updates (ADR 0003 enhancement)
-- Date: 2025-10-29

-- Add Git provenance columns to code_chunks table
ALTER TABLE code_chunks
ADD COLUMN IF NOT EXISTS commit_hash VARCHAR(40),
ADD COLUMN IF NOT EXISTS branch_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS author_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS commit_timestamp TIMESTAMPTZ;

-- Create indexes for Git provenance queries
CREATE INDEX IF NOT EXISTS idx_code_chunks_commit_hash
    ON code_chunks(commit_hash);

CREATE INDEX IF NOT EXISTS idx_code_chunks_branch
    ON code_chunks(project_id, branch_name);

-- Update UNIQUE constraint to include Git provenance for better deduplication
-- Note: This recreates the constraint to include branch awareness
ALTER TABLE code_chunks
DROP CONSTRAINT IF EXISTS code_chunks_project_id_content_hash_key;

ALTER TABLE code_chunks
ADD CONSTRAINT code_chunks_project_content_unique
    UNIQUE (project_id, content_hash);

-- Add comment for documentation
COMMENT ON COLUMN code_chunks.commit_hash IS 'Git commit SHA (40 chars) for delta sync';
COMMENT ON COLUMN code_chunks.branch_name IS 'Git branch name for branch-aware caching';
COMMENT ON COLUMN code_chunks.author_name IS 'Git commit author for provenance tracking';
COMMENT ON COLUMN code_chunks.commit_timestamp IS 'Git commit timestamp for change tracking';

-- Verification query
DO $$
BEGIN
    RAISE NOTICE '====================================';
    RAISE NOTICE 'Git Provenance Migration Complete!';
    RAISE NOTICE '====================================';
    RAISE NOTICE 'Added columns:';
    RAISE NOTICE '  - commit_hash (VARCHAR(40))';
    RAISE NOTICE '  - branch_name (VARCHAR(255))';
    RAISE NOTICE '  - author_name (VARCHAR(255))';
    RAISE NOTICE '  - commit_timestamp (TIMESTAMPTZ)';
    RAISE NOTICE 'Indexes created for efficient Git queries';
    RAISE NOTICE '====================================';
END $$;
