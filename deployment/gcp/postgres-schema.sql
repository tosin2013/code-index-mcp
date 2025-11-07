-- PostgreSQL Schema for Code Index MCP (Local Development)
-- Compatible with pgvector extension
-- AlloyDB-specific features replaced with stubs

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables
DROP TABLE IF EXISTS code_chunks CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS schema_version CASCADE;

-- Users table
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

-- Projects table
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
CREATE INDEX idx_projects_name ON projects(project_name);

-- Code chunks table
CREATE TABLE code_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    chunk_type VARCHAR(50),
    chunk_name VARCHAR(255),
    language VARCHAR(50),
    line_start INTEGER,
    line_end INTEGER,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding vector(768),
    symbols JSONB,
    -- Git metadata for delta-based synchronization (git-sync ingestion)
    commit_hash VARCHAR(40),
    branch_name VARCHAR(255),
    author_name VARCHAR(255),
    commit_timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, content_hash)
);

CREATE INDEX idx_code_chunks_project ON code_chunks(project_id);
CREATE INDEX idx_code_chunks_user ON code_chunks(user_id);
CREATE INDEX idx_code_chunks_file_path ON code_chunks(file_path);
CREATE INDEX idx_code_chunks_language ON code_chunks(language);
CREATE INDEX idx_code_chunks_hash ON code_chunks(content_hash);
-- Git metadata indexes for efficient git-sync queries
CREATE INDEX idx_code_chunks_commit_hash ON code_chunks(commit_hash);
CREATE INDEX idx_code_chunks_branch ON code_chunks(branch_name);

-- Vector similarity index (HNSW for fast approximate nearest neighbor)
CREATE INDEX idx_code_chunks_embedding ON code_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Enable Row Level Security
ALTER TABLE code_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

-- RLS Policies
DROP POLICY IF EXISTS user_code_access ON code_chunks;
CREATE POLICY user_code_access ON code_chunks
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS user_project_access ON projects;
CREATE POLICY user_project_access ON projects
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- PostgreSQL-compatible stub functions (AlloyDB uses google_ml_integration)
CREATE OR REPLACE FUNCTION generate_code_embedding(code_text TEXT)
RETURNS vector(768)
LANGUAGE SQL
AS $$
    -- Stub: Returns zero vector for local development
    -- Production AlloyDB: embedding('text-embedding-004', code_text)
    SELECT ARRAY(SELECT 0::float4 FROM generate_series(1, 768))::vector(768)
$$;

CREATE OR REPLACE FUNCTION generate_query_embedding(query_text TEXT)
RETURNS vector(768)
LANGUAGE SQL
AS $$
    -- Stub: Returns zero vector for local development
    -- Production AlloyDB: embedding('text-embedding-004', query_text)
    SELECT ARRAY(SELECT 0::float4 FROM generate_series(1, 768))::vector(768)
$$;

CREATE OR REPLACE FUNCTION semantic_code_search(
    query_embedding vector(768),
    match_count INTEGER DEFAULT 10,
    filter_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    file_path TEXT,
    chunk_name TEXT,
    similarity FLOAT
)
LANGUAGE SQL
AS $$
    -- Stub: Returns empty results for local development
    -- Production uses full vector similarity search
    SELECT 
        cc.chunk_id,
        cc.file_path,
        cc.chunk_name,
        0.0::float as similarity
    FROM code_chunks cc
    WHERE FALSE -- Return no results in stub
    LIMIT 0
$$;

-- Utility view for chunk statistics
CREATE OR REPLACE VIEW chunk_stats AS
SELECT 
    p.project_name,
    p.user_id,
    COUNT(*) as total_chunks,
    COUNT(DISTINCT cc.file_path) as total_files,
    COUNT(DISTINCT cc.language) as languages_count,
    AVG(cc.line_end - cc.line_start + 1) as avg_lines_per_chunk
FROM code_chunks cc
JOIN projects p ON cc.project_id = p.project_id
GROUP BY p.project_id, p.project_name, p.user_id;

-- Schema version tracking
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_version (version, description) VALUES
    (1, 'Initial schema with pgvector support'),
    (2, 'Added RLS policies for multi-tenancy'),
    (3, 'Added git metadata columns for delta-based git-sync ingestion');

-- Success message
DO $$
BEGIN
    RAISE NOTICE '======================================';
    RAISE NOTICE 'Local PostgreSQL Schema Setup Complete!';
    RAISE NOTICE '======================================';
    RAISE NOTICE 'Tables: users, projects, code_chunks';
    RAISE NOTICE 'Extensions: vector, uuid-ossp';
    RAISE NOTICE 'Vector Index: HNSW (m=16, ef_construction=64)';
    RAISE NOTICE 'RLS: Enabled for multi-tenancy';
    RAISE NOTICE '======================================';
END $$;
