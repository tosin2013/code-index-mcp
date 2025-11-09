-- AlloyDB Schema for Code Index MCP
-- Based on ADR 0003: Google Cloud Code Ingestion with AlloyDB
--
-- Run with:
--   psql -h INSTANCE_IP -U code_index_admin -d postgres -f alloydb-schema.sql

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS google_ml_integration;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- DROP EXISTING TABLES (for schema updates)
-- =============================================================================
DROP TABLE IF EXISTS code_chunks CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS schema_version CASCADE;

-- =============================================================================
-- USERS TABLE
-- =============================================================================
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    storage_quota_gb INTEGER DEFAULT 50,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_api_key_hash ON users(api_key_hash);

-- =============================================================================
-- PROJECTS TABLE
-- =============================================================================
CREATE TABLE projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    project_name VARCHAR(255) NOT NULL,
    gcs_bucket VARCHAR(255) NOT NULL,
    gcs_prefix VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_indexed_at TIMESTAMPTZ,
    total_chunks INTEGER DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    UNIQUE(user_id, project_name)
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_last_indexed ON projects(last_indexed_at);

-- =============================================================================
-- CODE_CHUNKS TABLE (Main table with vector embeddings)
-- =============================================================================
CREATE TABLE code_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,

    -- File information
    file_path TEXT NOT NULL,
    chunk_type VARCHAR(50) NOT NULL, -- 'function', 'class', 'file', 'block'
    chunk_name VARCHAR(255),
    line_start INTEGER,
    line_end INTEGER,
    language VARCHAR(50),

    -- Code content
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- SHA256 for deduplication

    -- Vector embedding (768 dimensions for text-embedding-004)
    -- Note: Can be 1536 for higher quality, adjust based on needs
    embedding vector(768),

    -- Metadata
    symbols JSONB, -- extracted symbols, imports, function calls, etc.

    -- Git provenance (for tracking code source)
    commit_hash VARCHAR(40), -- Git commit SHA
    branch_name VARCHAR(255), -- Git branch name
    author_name VARCHAR(255), -- Git commit author
    commit_timestamp TIMESTAMPTZ, -- Git commit timestamp

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Deduplication constraint
    UNIQUE(project_id, content_hash)
);

-- Indexes for code_chunks
CREATE INDEX idx_code_chunks_project ON code_chunks(project_id);
CREATE INDEX idx_code_chunks_user ON code_chunks(user_id);
CREATE INDEX idx_code_chunks_file_path ON code_chunks(file_path);
CREATE INDEX idx_code_chunks_language ON code_chunks(language);
CREATE INDEX idx_code_chunks_chunk_type ON code_chunks(chunk_type);
CREATE INDEX idx_code_chunks_content_hash ON code_chunks(content_hash);

-- HNSW index for vector similarity search
-- m: Number of connections per layer (16 is good for dev, 32-48 for prod)
-- ef_construction: Build-time quality (64 for dev, 128-256 for prod)
CREATE INDEX code_chunks_embedding_idx ON code_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- EMBEDDING GENERATION FUNCTIONS
-- =============================================================================

-- Generate embedding using Vertex AI text-embedding-004
-- Note: Requires google_ml_integration extension and proper IAM permissions
CREATE OR REPLACE FUNCTION generate_code_embedding(code_text TEXT)
RETURNS vector(768)
LANGUAGE SQL
AS $$
    SELECT embedding('text-embedding-004', code_text)::vector(768)
$$;

-- Trigger to auto-generate embeddings on insert/update
CREATE OR REPLACE FUNCTION auto_generate_embedding()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Only generate if embedding is NULL or content changed
    IF NEW.embedding IS NULL OR (TG_OP = 'UPDATE' AND NEW.content <> OLD.content) THEN
        BEGIN
            NEW.embedding := generate_code_embedding(NEW.content);
        EXCEPTION
            WHEN OTHERS THEN
                -- Log error but don't fail the insert
                RAISE WARNING 'Failed to generate embedding: %', SQLERRM;
                -- Embedding stays NULL, can be retried later
        END;
    END IF;

    -- Update timestamp
    NEW.updated_at := NOW();

    RETURN NEW;
END;
$$;

CREATE TRIGGER code_chunks_embedding_trigger
BEFORE INSERT OR UPDATE ON code_chunks
FOR EACH ROW
EXECUTE FUNCTION auto_generate_embedding();

-- =============================================================================
-- ROW LEVEL SECURITY (Multi-tenancy)
-- =============================================================================

-- Enable RLS on code_chunks
ALTER TABLE code_chunks ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own projects' chunks
CREATE POLICY user_code_access ON code_chunks
FOR ALL
USING (
    project_id IN (
        SELECT project_id
        FROM projects
        WHERE user_id = current_setting('app.user_id', true)::UUID
    )
);

-- Enable RLS on projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own projects
CREATE POLICY user_project_access ON projects
FOR ALL
USING (user_id = current_setting('app.user_id', true)::UUID);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Set user context for RLS (call this at start of each session)
CREATE OR REPLACE FUNCTION set_user_context(p_user_id UUID)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM set_config('app.user_id', p_user_id::TEXT, false);
END;
$$;

-- Search code by semantic similarity
CREATE OR REPLACE FUNCTION semantic_search_code(
    p_user_id UUID,
    p_query TEXT,
    p_project_name TEXT DEFAULT NULL,
    p_language TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    chunk_id UUID,
    project_name VARCHAR(255),
    file_path TEXT,
    chunk_name VARCHAR(255),
    chunk_type VARCHAR(50),
    line_range TEXT,
    language VARCHAR(50),
    content TEXT,
    symbols JSONB,
    similarity_score FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
    query_embedding vector(768);
BEGIN
    -- Set user context for RLS
    PERFORM set_user_context(p_user_id);

    -- Generate query embedding
    query_embedding := generate_code_embedding(p_query);

    -- Perform vector similarity search
    RETURN QUERY
    SELECT
        c.chunk_id,
        p.project_name,
        c.file_path,
        c.chunk_name,
        c.chunk_type,
        CONCAT(c.line_start::TEXT, '-', c.line_end::TEXT) AS line_range,
        c.language,
        c.content,
        c.symbols,
        (1 - (c.embedding <=> query_embedding)) AS similarity_score
    FROM code_chunks c
    JOIN projects p ON c.project_id = p.project_id
    WHERE
        p.user_id = p_user_id
        AND (p_project_name IS NULL OR p.project_name = p_project_name)
        AND (p_language IS NULL OR c.language = p_language)
        AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> query_embedding
    LIMIT p_limit;
END;
$$;

-- Get project statistics
CREATE OR REPLACE FUNCTION get_project_stats(p_project_id UUID)
RETURNS TABLE (
    total_chunks BIGINT,
    total_files BIGINT,
    languages JSONB,
    chunk_types JSONB,
    avg_chunk_size FLOAT
)
LANGUAGE sql
AS $$
    SELECT
        COUNT(*)::BIGINT AS total_chunks,
        COUNT(DISTINCT file_path)::BIGINT AS total_files,
        jsonb_object_agg(language, lang_count) AS languages,
        jsonb_object_agg(chunk_type, type_count) AS chunk_types,
        AVG(LENGTH(content))::FLOAT AS avg_chunk_size
    FROM (
        SELECT
            language,
            chunk_type,
            content,
            file_path,
            COUNT(*) OVER (PARTITION BY language) AS lang_count,
            COUNT(*) OVER (PARTITION BY chunk_type) AS type_count
        FROM code_chunks
        WHERE project_id = p_project_id
    ) subq
    GROUP BY ()
$$;

-- =============================================================================
-- MAINTENANCE FUNCTIONS
-- =============================================================================

-- Regenerate embeddings for chunks with NULL embeddings
CREATE OR REPLACE FUNCTION regenerate_null_embeddings(p_project_id UUID DEFAULT NULL)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    updated_count INTEGER := 0;
BEGIN
    UPDATE code_chunks
    SET updated_at = NOW() -- Trigger will regenerate embedding
    WHERE
        embedding IS NULL
        AND (p_project_id IS NULL OR project_id = p_project_id);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$;

-- Vacuum and analyze tables for performance
CREATE OR REPLACE FUNCTION maintenance_vacuum()
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    VACUUM ANALYZE users;
    VACUUM ANALYZE projects;
    VACUUM ANALYZE code_chunks;
END;
$$;

-- =============================================================================
-- VIEWS
-- =============================================================================

-- View: Project overview with statistics
CREATE OR REPLACE VIEW project_overview AS
SELECT
    p.project_id,
    p.user_id,
    p.project_name,
    p.last_indexed_at,
    COUNT(c.chunk_id) AS total_chunks,
    COUNT(DISTINCT c.file_path) AS total_files,
    COUNT(DISTINCT c.language) AS language_count,
    MAX(c.updated_at) AS last_chunk_update
FROM projects p
LEFT JOIN code_chunks c ON p.project_id = c.project_id
GROUP BY p.project_id, p.user_id, p.project_name, p.last_indexed_at;

-- =============================================================================
-- GRANTS (Adjust as needed for your setup)
-- =============================================================================

-- Grant permissions to application user
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO code_index_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO code_index_app;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO code_index_app;

-- =============================================================================
-- INITIAL DATA
-- =============================================================================

-- Insert a test user (for development only)
INSERT INTO users (email, api_key_hash, storage_quota_gb)
VALUES ('dev@code-index-mcp.local', 'test_hash_dev_only', 100)
ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- SCHEMA VERSION
-- =============================================================================
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_version (version, description)
VALUES (1, 'Initial schema: users, projects, code_chunks with vector embeddings')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
-- COMPLETION MESSAGE
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '======================================';
    RAISE NOTICE 'AlloyDB Schema Setup Complete!';
    RAISE NOTICE '======================================';
    RAISE NOTICE 'Tables created: users, projects, code_chunks';
    RAISE NOTICE 'Extensions: vector, google_ml_integration';
    RAISE NOTICE 'Indexes: HNSW vector index (m=16, ef_construction=64)';
    RAISE NOTICE 'RLS: Enabled for multi-tenancy';
    RAISE NOTICE 'Functions: semantic_search_code, generate_code_embedding';
    RAISE NOTICE '======================================';
END $$;
