#!/bin/bash
# Test Enhanced ADR Schema with pgvector Best Practices

echo "🧪 Testing Enhanced ADR Schema..."
echo ""

export POSTGRES_CONNECTION="postgresql://code_index_admin:local_dev_password@localhost:5432/code_index"

# Apply the enhanced ADR schema
echo "1. Applying enhanced ADR schema..."
psql "$POSTGRES_CONNECTION" -f adr-schema-enhanced.sql

echo ""
echo "2. Verifying ADR table and indexes..."
psql "$POSTGRES_CONNECTION" -c "
    SELECT
        tablename,
        indexname,
        indexdef
    FROM pg_indexes
    WHERE tablename = 'adrs'
    ORDER BY indexname;
"

echo ""
echo "3. Sample ADRs loaded:"
psql "$POSTGRES_CONNECTION" -c "
    SELECT
        adr_number,
        title,
        status,
        decision_category,
        array_length(technology_stack, 1) as tech_count
    FROM adrs
    ORDER BY adr_number;
"

echo ""
echo "4. Testing hybrid search function (semantic + metadata filter)..."
echo "   Query: Find 'deployment' decisions in 'deployment' category"
psql "$POSTGRES_CONNECTION" -c "
    -- Generate a mock embedding for testing
    WITH mock_query AS (
        SELECT embedding
        FROM adrs
        WHERE adr_number = 2  -- Use deployment ADR's embedding
    )
    SELECT
        adr_number,
        title,
        status,
        category,
        ROUND(similarity_score::numeric, 3) as score
    FROM search_adrs(
        (SELECT embedding FROM mock_query),
        'deployment',  -- Filter by category BEFORE vector search
        'accepted',    -- Filter by status
        NULL,          -- No technology filter
        5              -- Top 5 results
    );
"

echo ""
echo "5. Testing find_similar_adrs function..."
echo "   Query: Find ADRs similar to ADR #1 (PostgreSQL/pgvector decision)"
psql "$POSTGRES_CONNECTION" -c "
    SELECT
        similar_adr_number,
        title,
        status,
        ROUND(similarity_score::numeric, 3) as score
    FROM find_similar_adrs(1, 3);
"

echo ""
echo "6. Testing find_impacted_adrs function..."
echo "   Query: Find ADRs impacted by changes to 'mcp-server'"
psql "$POSTGRES_CONNECTION" -c "
    SELECT
        adr_number,
        title,
        status,
        decision_category
    FROM find_impacted_adrs('mcp-server', NULL);
"

echo ""
echo "7. Testing ADR relationships view..."
psql "$POSTGRES_CONNECTION" -c "
    SELECT * FROM adr_relationships LIMIT 5;
"

echo ""
echo "8. Performance Analysis - Index Usage"
echo "   EXPLAIN ANALYZE for hybrid search:"
psql "$POSTGRES_CONNECTION" -c "
    EXPLAIN ANALYZE
    SELECT
        adr_number,
        title,
        (1 - (embedding <=> (SELECT embedding FROM adrs WHERE adr_number = 1))) as score
    FROM adrs
    WHERE
        decision_category = 'architecture'  -- B-tree index filter FIRST
        AND status = 'accepted'              -- B-tree index filter FIRST
        AND embedding IS NOT NULL
    ORDER BY embedding <=> (SELECT embedding FROM adrs WHERE adr_number = 1)
    LIMIT 5;
"

echo ""
echo "✅ Enhanced ADR Schema Testing Complete!"
echo ""
echo "Key Performance Features Demonstrated:"
echo "  ✓ Hybrid search with pre-filtering (B-tree indexes)"
echo "  ✓ Semantic similarity search (HNSW index)"
echo "  ✓ Impact analysis (GIN indexes on arrays)"
echo "  ✓ ADR relationship tracking"
echo ""
echo "Performance Benefits vs. Normalized Schema:"
echo "  • No JOINs needed (denormalized design)"
echo "  • Pre-filtering reduces vector search candidate set"
echo "  • Strongly-typed columns enable efficient B-tree indexes"
echo "  • GIN indexes enable fast array membership queries"
echo ""
