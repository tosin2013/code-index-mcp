-- Enhanced ADR Schema with pgvector Best Practices
-- Based on: https://www.timescale.com/blog/pgvector-for-semantic-search-performance-best-practices/

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ADR table with denormalized design for JOIN-free queries
CREATE TABLE IF NOT EXISTS adrs (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adr_number INTEGER UNIQUE NOT NULL,

    -- Core ADR fields
    title TEXT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('proposed', 'accepted', 'superseded', 'deprecated', 'rejected')),
    content TEXT NOT NULL,

    -- Vector embedding (768 dimensions for text-embedding-004)
    embedding vector(768),

    -- Strongly-typed metadata columns (KEY: enables efficient B-tree filtering)
    decision_category VARCHAR(50),  -- 'architecture', 'deployment', 'security', 'performance'
    technology_stack TEXT[],        -- e.g., {'PostgreSQL', 'pgvector', 'Cloud Run'}
    impacted_services TEXT[],       -- e.g., {'mcp-server', 'ingestion-pipeline'}
    decision_level VARCHAR(20),     -- 'strategic', 'tactical', 'operational'

    -- Provenance (similar to article's repository tracking)
    supersedes_adr INTEGER,         -- ADR number this replaces
    superseded_by_adr INTEGER,      -- ADR number that replaces this
    related_adrs INTEGER[],         -- Related ADR numbers

    -- Flexible JSONB for additional metadata
    metadata JSONB DEFAULT '{}',    -- links, references, stakeholders, costs

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    decided_at TIMESTAMPTZ
);

-- HNSW vector index (primary similarity search)
-- Article recommendation: Use for approximate nearest neighbor search
CREATE INDEX adrs_embedding_hnsw_idx ON adrs
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- B-tree indexes on strongly-typed columns (KEY: pre-filter before vector search)
-- Article insight: These enable PostgreSQL to reduce candidate set before expensive distance calc
CREATE INDEX adrs_status_idx ON adrs(status);
CREATE INDEX adrs_category_idx ON adrs(decision_category);
CREATE INDEX adrs_level_idx ON adrs(decision_level);
CREATE INDEX adrs_decided_at_idx ON adrs(decided_at);

-- GIN indexes for array columns (efficient "contains" queries)
CREATE INDEX adrs_technology_gin_idx ON adrs USING GIN(technology_stack);
CREATE INDEX adrs_services_gin_idx ON adrs USING GIN(impacted_services);
CREATE INDEX adrs_related_gin_idx ON adrs USING GIN(related_adrs);

-- GIN index on JSONB for flexible metadata queries
CREATE INDEX adrs_metadata_gin_idx ON adrs USING GIN(metadata);

-- View for ADR relationships
CREATE OR REPLACE VIEW adr_relationships AS
SELECT
    a1.adr_number AS from_adr,
    a1.title AS from_title,
    a2.adr_number AS to_adr,
    a2.title AS to_title,
    CASE
        WHEN a1.supersedes_adr = a2.adr_number THEN 'supersedes'
        WHEN a1.superseded_by_adr = a2.adr_number THEN 'superseded_by'
        WHEN a2.adr_number = ANY(a1.related_adrs) THEN 'related_to'
    END AS relationship_type
FROM adrs a1
JOIN adrs a2 ON (
    a1.supersedes_adr = a2.adr_number
    OR a1.superseded_by_adr = a2.adr_number
    OR a2.adr_number = ANY(a1.related_adrs)
);

-- Hybrid search function (semantic + metadata filtering)
-- Article's key recommendation: Filter first, then vector search on smaller set
CREATE OR REPLACE FUNCTION search_adrs(
    p_query_embedding vector(768),
    p_category VARCHAR(50) DEFAULT NULL,
    p_status VARCHAR(20) DEFAULT NULL,
    p_technology TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    adr_number INTEGER,
    title TEXT,
    status VARCHAR(20),
    category VARCHAR(50),
    content_preview TEXT,
    technologies TEXT[],
    similarity_score FLOAT,
    decided_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.adr_number,
        a.title,
        a.status,
        a.decision_category,
        LEFT(a.content, 200) AS content_preview,
        a.technology_stack,
        (1 - (a.embedding <=> p_query_embedding)) AS similarity_score,
        a.decided_at
    FROM adrs a
    WHERE
        -- Pre-filtering on indexed columns (KEY: happens before vector search)
        (p_category IS NULL OR a.decision_category = p_category)
        AND (p_status IS NULL OR a.status = p_status)
        AND (p_technology IS NULL OR p_technology = ANY(a.technology_stack))
        AND a.embedding IS NOT NULL
    ORDER BY a.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$;

-- Find similar ADRs by content (pure semantic search)
CREATE OR REPLACE FUNCTION find_similar_adrs(
    p_adr_number INTEGER,
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    similar_adr_number INTEGER,
    title TEXT,
    status VARCHAR(20),
    similarity_score FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_embedding vector(768);
BEGIN
    -- Get embedding of source ADR
    SELECT embedding INTO v_embedding
    FROM adrs
    WHERE adr_number = p_adr_number;

    IF v_embedding IS NULL THEN
        RAISE EXCEPTION 'ADR % not found or has no embedding', p_adr_number;
    END IF;

    -- Find similar ADRs
    RETURN QUERY
    SELECT
        a.adr_number,
        a.title,
        a.status,
        (1 - (a.embedding <=> v_embedding)) AS similarity_score
    FROM adrs a
    WHERE
        a.adr_number != p_adr_number
        AND a.embedding IS NOT NULL
    ORDER BY a.embedding <=> v_embedding
    LIMIT p_limit;
END;
$$;

-- Find ADRs impacted by code changes
CREATE OR REPLACE FUNCTION find_impacted_adrs(
    p_service_name TEXT,
    p_technology TEXT DEFAULT NULL
)
RETURNS TABLE (
    adr_number INTEGER,
    title TEXT,
    status VARCHAR(20),
    decision_category VARCHAR(50)
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.adr_number,
        a.title,
        a.status,
        a.decision_category
    FROM adrs a
    WHERE
        p_service_name = ANY(a.impacted_services)
        AND (p_technology IS NULL OR p_technology = ANY(a.technology_stack))
        AND a.status IN ('accepted', 'proposed')
    ORDER BY a.decided_at DESC NULLS LAST;
END;
$$;

-- Get ADR decision history
CREATE OR REPLACE FUNCTION get_adr_history(
    p_technology TEXT DEFAULT NULL,
    p_category VARCHAR(50) DEFAULT NULL
)
RETURNS TABLE (
    adr_number INTEGER,
    title TEXT,
    status VARCHAR(20),
    decided_at TIMESTAMPTZ,
    technologies TEXT[],
    superseded_by INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.adr_number,
        a.title,
        a.status,
        a.decided_at,
        a.technology_stack,
        a.superseded_by_adr
    FROM adrs a
    WHERE
        (p_technology IS NULL OR p_technology = ANY(a.technology_stack))
        AND (p_category IS NULL OR a.decision_category = p_category)
    ORDER BY a.decided_at DESC NULLS LAST;
END;
$$;

-- Comments for documentation
COMMENT ON TABLE adrs IS 'Architectural Decision Records with vector embeddings for semantic search';
COMMENT ON COLUMN adrs.embedding IS '768-dimensional embedding from Vertex AI text-embedding-004';
COMMENT ON COLUMN adrs.technology_stack IS 'Technologies involved in this decision (enables GIN index filtering)';
COMMENT ON COLUMN adrs.decision_category IS 'Category for efficient B-tree filtering before vector search';
COMMENT ON INDEX adrs_embedding_hnsw_idx IS 'HNSW index for approximate nearest neighbor search (m=16, ef_construction=64)';
COMMENT ON INDEX adrs_category_idx IS 'B-tree index enables pre-filtering before vector search (performance critical)';
COMMENT ON FUNCTION search_adrs IS 'Hybrid search: filters on indexed columns first, then vector similarity on reduced set';

-- Sample data for testing
INSERT INTO adrs (adr_number, title, status, decision_category, technology_stack, impacted_services, content, decided_at)
VALUES
    (1, 'Use PostgreSQL with pgvector for semantic search', 'accepted', 'architecture',
     ARRAY['PostgreSQL', 'pgvector', 'Vertex AI'], ARRAY['mcp-server', 'ingestion-pipeline'],
     'We will use PostgreSQL with the pgvector extension for storing and querying code embeddings. This provides a balance between vector search performance and relational query capabilities.',
     NOW() - INTERVAL '10 days'),

    (2, 'Deploy MCP server to Cloud Run', 'accepted', 'deployment',
     ARRAY['Cloud Run', 'Docker', 'GCP'], ARRAY['mcp-server'],
     'The MCP server will be deployed as a containerized service on Google Cloud Run for serverless scaling and cost efficiency.',
     NOW() - INTERVAL '8 days'),

    (3, 'Use HNSW index for vector similarity search', 'accepted', 'performance',
     ARRAY['pgvector', 'PostgreSQL'], ARRAY['mcp-server'],
     'HNSW (Hierarchical Navigable Small World) index provides better recall than IVFFlat for our use case with acceptable build time.',
     NOW() - INTERVAL '5 days'),

    (4, 'Implement local PostgreSQL for development', 'accepted', 'architecture',
     ARRAY['PostgreSQL', 'Docker', 'pgvector'], ARRAY['mcp-server', 'ingestion-pipeline'],
     'Use local PostgreSQL with Docker Compose for development and validation before deploying to AlloyDB. This reduces cloud costs and enables faster iteration.',
     NOW()),

    (5, 'Use separate ADR table with denormalized schema', 'proposed', 'architecture',
     ARRAY['PostgreSQL', 'pgvector'], ARRAY['mcp-server'],
     'Store ADRs in a separate denormalized table to avoid JOINs and enable efficient hybrid search with strongly-typed metadata columns.',
     NULL);

ON CONFLICT (adr_number) DO NOTHING;

-- Completion notice
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Enhanced ADR Schema Created Successfully!';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Features:';
    RAISE NOTICE '  ✓ Denormalized table (no JOINs needed)';
    RAISE NOTICE '  ✓ Strongly-typed metadata columns';
    RAISE NOTICE '  ✓ B-tree indexes for pre-filtering';
    RAISE NOTICE '  ✓ HNSW vector index for similarity';
    RAISE NOTICE '  ✓ GIN indexes for array queries';
    RAISE NOTICE '  ✓ Hybrid search function';
    RAISE NOTICE '  ✓ ADR relationship tracking';
    RAISE NOTICE '  ✓ 5 sample ADRs loaded';
    RAISE NOTICE '============================================';
END $$;
