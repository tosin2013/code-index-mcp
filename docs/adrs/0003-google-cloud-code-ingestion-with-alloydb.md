# ADR 0003: Google Cloud Code Ingestion with AlloyDB Vector Search

**Status**: In Progress (83% Complete - Code Ready, Awaiting AlloyDB Provisioning)
**Date**: 2025-10-24 (Original), Updated 2025-10-29
**Decision Maker**: Architecture Team
**Cloud Platform**: Google Cloud
**Related to**: ADR 0001 (HTTP Transport), ADR 0002 (Cloud Run Deployment), ADR 0008 (Git-Sync Ingestion)

## Context

Currently, code-index-mcp builds **metadata indexes** (file paths, symbols, imports) but does **NOT ingest or store actual code content** for semantic search. Users have requested the ability to:

1. **Semantic search**: Find code by meaning, not just keywords
2. **Code similarity**: Find similar implementations across repositories
3. **Smart context retrieval**: Auto-populate LLM context with relevant code
4. **Cross-repository analysis**: Compare patterns across multiple projects

For **Google Cloud deployments**, we should leverage native GCP services rather than bringing external dependencies.

## Decision: AlloyDB with pgvector for Vector Search

Use **AlloyDB for PostgreSQL** with the `pgvector` extension and `google_ml_integration` for embedding generation via Vertex AI.

### Why AlloyDB?

1. **Native PostgreSQL compatibility** - Works with existing PostgreSQL tools and ORMs
2. **Built-in vector search** - pgvector extension included by default
3. **Vertex AI integration** - `google_ml_integration` extension for seamless embeddings
4. **High performance** - ScaNN, HNSW, IVF indexes for fast similarity search
5. **Managed service** - Automatic backups, HA, scaling
6. **Cost-effective** - Pay for actual usage, no separate vector DB infrastructure

## Architecture

### Google Cloud-Native Stack

```
┌──────────────────┐
│   Cloud Run      │
│   MCP Server     │
└────────┬─────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────────┐  ┌──────────────────┐
│  Cloud Storage  │  │    AlloyDB       │
│  - Raw code     │  │  - Code chunks   │
│  - Archives     │  │  - Embeddings    │
└─────────────────┘  │  - Metadata      │
                     └────────┬─────────┘
                              │
                              │ google_ml_integration
                              ▼
                     ┌──────────────────┐
                     │   Vertex AI      │
                     │   Embeddings     │
                     └──────────────────┘
```

### Data Flow

```
1. User uploads code
   ↓
2. Store raw code in Cloud Storage
   ↓
3. Chunk code (functions, classes, files)
   ↓
4. Generate embeddings via Vertex AI
   ↓
5. Store in AlloyDB (code + vectors)
   ↓
6. User queries: "Find authentication code"
   ↓
7. Query embedding generated
   ↓
8. Vector similarity search in AlloyDB
   ↓
9. Return relevant code chunks
```

## AlloyDB Schema Design

### Tables

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS google_ml_integration;

-- Users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    storage_quota_gb INTEGER DEFAULT 50
);

-- Projects table
CREATE TABLE projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    project_name VARCHAR(255) NOT NULL,
    gcs_bucket VARCHAR(255) NOT NULL,
    gcs_prefix VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_indexed_at TIMESTAMPTZ,
    UNIQUE(user_id, project_name)
);

-- Code chunks table with vector embeddings
CREATE TABLE code_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    chunk_type VARCHAR(50) NOT NULL, -- 'function', 'class', 'file', 'block'
    chunk_name VARCHAR(255),
    line_start INTEGER,
    line_end INTEGER,
    language VARCHAR(50),
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- SHA256 for deduplication

    -- Vector embedding (768 dimensions for text-embedding-004 by default, configurable to 1536)
    embedding vector(768),

    -- Metadata
    symbols JSONB, -- extracted symbols, imports, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Indexes
    UNIQUE(project_id, content_hash)
);

-- Vector similarity index (HNSW for high performance)
CREATE INDEX code_chunks_embedding_idx ON code_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Additional indexes
CREATE INDEX idx_project_chunks ON code_chunks(project_id);
CREATE INDEX idx_file_path ON code_chunks(file_path);
CREATE INDEX idx_language ON code_chunks(language);
CREATE INDEX idx_chunk_type ON code_chunks(chunk_type);
```

### Embedding Generation Function

```sql
-- Generate embeddings using Vertex AI
CREATE OR REPLACE FUNCTION generate_code_embedding(code_text TEXT)
RETURNS vector(768)
AS $$
SELECT embedding('text-embedding-004', code_text)::vector(768)
$$ LANGUAGE SQL;

-- Trigger to auto-generate embeddings on insert
CREATE OR REPLACE FUNCTION auto_generate_embedding()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.embedding IS NULL THEN
        NEW.embedding := generate_code_embedding(NEW.content);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER code_chunks_embedding_trigger
BEFORE INSERT OR UPDATE ON code_chunks
FOR EACH ROW
WHEN (NEW.embedding IS NULL)
EXECUTE FUNCTION auto_generate_embedding();
```

## MCP Tool Implementation

### Ingestion Methods

**RECOMMENDED: Git-Sync Ingestion** (See ADR 0008)
- 99% token savings vs file upload
- 95% faster incremental updates
- Auto-sync via webhooks on git push
- Supports GitHub, GitLab, Bitbucket, Gitea

```python
# Use this method for cloud deployments
ingest_code_from_git(
    git_url="https://github.com/user/repo",
    project_name="my-project",
    auth_token="ghp_xxxx"  # For private repos
)
```

**Legacy: File Upload Ingestion** (Deprecated for cloud mode)
- Use only for local/stdio mode
- High token consumption
- See implementation below

### New Tools for Code Ingestion

```python
# In server.py

@mcp.tool()
@handle_mcp_tool_errors(return_type='dict')
def ingest_project_code(
    ctx: Context,
    project_name: str,
    gcs_path: str = None,
    git_url: str = None,
    chunk_strategy: str = "function"  # or "file", "semantic"
) -> Dict[str, Any]:
    """
    Ingest code from GCS or git repository into AlloyDB for semantic search.

    Args:
        project_name: Unique project identifier
        gcs_path: GCS path (gs://bucket/path) if code already in GCS
        git_url: Git repository URL to clone and ingest
        chunk_strategy: How to split code (function, file, semantic)

    Returns:
        Ingestion status and statistics
    """
    from google.cloud import alloydb, storage
    import hashlib

    user_id = ctx.request_context.user_id

    # 1. Download/sync code to GCS if needed
    if git_url:
        gcs_path = clone_to_gcs(git_url, user_id, project_name)

    # 2. Create project entry
    db = get_alloydb_connection()
    project_id = db.execute(
        "INSERT INTO projects (user_id, project_name, gcs_bucket, gcs_prefix) "
        "VALUES (%s, %s, %s, %s) RETURNING project_id",
        (user_id, project_name, extract_bucket(gcs_path), extract_prefix(gcs_path))
    ).fetchone()[0]

    # 3. Chunk code
    chunks = chunk_codebase(gcs_path, strategy=chunk_strategy)

    # 4. Insert chunks (embeddings auto-generated by trigger)
    inserted = 0
    for chunk in chunks:
        content_hash = hashlib.sha256(chunk['content'].encode()).hexdigest()

        try:
            db.execute(
                "INSERT INTO code_chunks "
                "(project_id, file_path, chunk_type, chunk_name, line_start, line_end, "
                " language, content, content_hash, symbols) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (project_id, chunk['file_path'], chunk['type'], chunk['name'],
                 chunk['line_start'], chunk['line_end'], chunk['language'],
                 chunk['content'], content_hash, json.dumps(chunk['symbols']))
            )
            inserted += 1
        except IntegrityError:
            # Duplicate content_hash, skip
            pass

    db.commit()

    return {
        "status": "success",
        "project_id": str(project_id),
        "chunks_inserted": inserted,
        "chunks_skipped": len(chunks) - inserted
    }

@mcp.tool()
@handle_mcp_tool_errors(return_type='list')
def semantic_search_code(
    ctx: Context,
    query: str,
    project_name: str = None,
    language: str = None,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Search code by semantic meaning using vector similarity.

    Args:
        query: Natural language query (e.g., "authentication logic")
        project_name: Filter to specific project (optional)
        language: Filter by programming language (optional)
        top_k: Number of results to return

    Returns:
        List of code chunks with similarity scores
    """
    user_id = ctx.request_context.user_id
    db = get_alloydb_connection()

    # Generate query embedding
    query_embedding = db.execute(
        "SELECT embedding('text-embedding-004', %s)::vector(768)",
        (query,)
    ).fetchone()[0]

    # Build WHERE clause
    where_clauses = ["p.user_id = %s"]
    params = [user_id]

    if project_name:
        where_clauses.append("p.project_name = %s")
        params.append(project_name)

    if language:
        where_clauses.append("c.language = %s")
        params.append(language)

    where_sql = " AND ".join(where_clauses)
    params.extend([query_embedding, top_k])

    # Vector similarity search
    results = db.execute(f"""
        SELECT
            c.chunk_id,
            c.file_path,
            c.chunk_name,
            c.chunk_type,
            c.line_start,
            c.line_end,
            c.language,
            c.content,
            c.symbols,
            1 - (c.embedding <=> %s) AS similarity_score,
            p.project_name
        FROM code_chunks c
        JOIN projects p ON c.project_id = p.project_id
        WHERE {where_sql}
        ORDER BY c.embedding <=> %s
        LIMIT %s
    """, tuple(params)).fetchall()

    return [
        {
            "chunk_id": str(row[0]),
            "file_path": row[1],
            "chunk_name": row[2],
            "chunk_type": row[3],
            "line_range": f"{row[4]}-{row[5]}",
            "language": row[6],
            "content": row[7],
            "symbols": row[8],
            "similarity_score": float(row[9]),
            "project_name": row[10]
        }
        for row in results
    ]

@mcp.tool()
@handle_mcp_tool_errors(return_type='list')
def find_similar_code(
    ctx: Context,
    code_snippet: str,
    project_name: str = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Find code chunks similar to the provided code snippet.

    Args:
        code_snippet: Code to find similar implementations of
        project_name: Filter to specific project (optional)
        top_k: Number of results

    Returns:
        Similar code chunks with similarity scores
    """
    # Similar to semantic_search_code but embeds code directly
    return semantic_search_code(
        ctx=ctx,
        query=code_snippet,
        project_name=project_name,
        top_k=top_k
    )
```

## Chunking Strategy

### Function-Level Chunking (Recommended)

```python
def chunk_function(file_path: str, function_node: ASTNode) -> Dict:
    """Extract a function as a chunk"""
    return {
        "file_path": file_path,
        "type": "function",
        "name": function_node.name,
        "line_start": function_node.line_start,
        "line_end": function_node.line_end,
        "language": detect_language(file_path),
        "content": function_node.text,
        "symbols": {
            "function_name": function_node.name,
            "parameters": function_node.parameters,
            "return_type": function_node.return_type,
            "calls": extract_function_calls(function_node)
        }
    }
```

## Vertex AI Embedding Models

### Recommended: text-embedding-004

```python
# Model configuration
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMENSIONS = 768  # or 1536 for higher quality

# Batch processing for efficiency
def generate_embeddings_batch(texts: List[str]) -> List[vector]:
    """Generate embeddings for multiple texts efficiently"""
    from vertexai.language_models import TextEmbeddingModel

    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    embeddings = model.get_embeddings(texts)

    return [emb.values for emb in embeddings]
```

### Cost Optimization

```python
# Cache embeddings for unchanged code
def get_or_generate_embedding(content: str, content_hash: str) -> vector:
    # Check if embedding exists
    existing = db.execute(
        "SELECT embedding FROM code_chunks WHERE content_hash = %s",
        (content_hash,)
    ).fetchone()

    if existing:
        return existing[0]  # Reuse existing embedding

    # Generate new embedding
    return generate_embedding(content)
```

## Performance Optimization

### Index Tuning

```sql
-- HNSW index parameters
-- m: Number of connections per layer (16 is good default)
-- ef_construction: Build-time quality (64-128 for production)

CREATE INDEX code_chunks_embedding_idx ON code_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- For query time, set ef_search
SET hnsw.ef_search = 40; -- Higher = more accurate but slower
```

### Query Optimization

```sql
-- Hybrid search: Vector similarity + metadata filters
SELECT *
FROM code_chunks
WHERE
    project_id = 'uuid-here'
    AND language = 'python'
    AND embedding <=> query_vector < 0.3  -- Cosine distance threshold
ORDER BY embedding <=> query_vector
LIMIT 10;
```

## Cost Analysis

### AlloyDB Pricing (us-central1)

| Resource | Specification | Monthly Cost |
|----------|--------------|--------------|
| AlloyDB Instance | 2 vCPU, 16 GB RAM | ~$200/month |
| Storage | 100 GB SSD | ~$20/month |
| **Total Base Cost** | | **~$220/month** |

### Vertex AI Embedding Costs

| Model | Cost per 1M characters |
|-------|----------------------|
| text-embedding-004 | $0.025 |

**Example**: 100k LOC ≈ 5M characters ≈ $0.125 one-time

### Total Monthly Cost (10-user team)

- AlloyDB: $220
- Storage (GCS): $5
- Embeddings (incremental): $1-5
- **Total: ~$230/month**

**Cost Optimization:**
- Use AlloyDB read replicas for read-heavy workloads
- Enable auto-scaling for primary instance
- Archive old embeddings to Cloud Storage

## Security Considerations

### Data Protection

1. **Encryption at Rest**
   - AlloyDB automatically encrypts data using Google-managed keys
   - Optional: Customer-managed encryption keys (CMEK)

2. **Network Security**
   - AlloyDB private IP only (no public internet access)
   - VPC Service Controls for additional isolation
   - Private Service Connect for secure connectivity

3. **Access Control**
   ```sql
   -- Row-level security for multi-tenancy
   ALTER TABLE code_chunks ENABLE ROW LEVEL SECURITY;

   CREATE POLICY user_code_access ON code_chunks
   FOR ALL
   USING (
       project_id IN (
           SELECT project_id FROM projects
           WHERE user_id = current_setting('app.user_id')::UUID
       )
   );
   ```

### API Key Management

```python
# Set user context for RLS
def set_user_context(db_conn, user_id: str):
    db_conn.execute(
        "SELECT set_config('app.user_id', %s, false)",
        (user_id,)
    )
```

## Implementation Status

### ✅ Completed Tasks (83% of Phase 3A)

**Task 7: Code Chunking** (Complete - 673 lines)
- ✅ Implemented in `src/code_index_mcp/ingestion/chunker.py`
- ✅ AST-based Python parsing with tree-sitter fallback
- ✅ 4 chunking strategies (FUNCTION, CLASS, FILE, SEMANTIC)
- ✅ Rich metadata extraction (imports, docstrings, parameters, calls)
- ✅ SHA256 content hashing for deduplication
- ✅ Test coverage: 4/4 tests passing
- ✅ Real-world testing: 140 chunks from 12 files

**Task 8: Vertex AI Integration** (Complete - 495 lines)
- ✅ Implemented in `src/code_index_mcp/embeddings/vertex_ai.py`
- ✅ `text-embedding-004` model integration (768 dimensions)
- ✅ Single and batch embedding generation
- ✅ Rate limiting (300 requests/min)
- ✅ Retry logic (3x exponential backoff)
- ✅ Mock embedder for local testing ($0 cost)
- ✅ Test coverage: 5/5 tests passing

**Task 9: Ingestion Pipeline** (Complete - 695 lines)
- ✅ Implemented in `src/code_index_mcp/ingestion/pipeline.py`
- ✅ `IngestionPipeline` class for orchestration
- ✅ Batch processing (50 chunks per batch)
- ✅ Progress tracking with callbacks
- ✅ Database operations with RLS support
- ✅ Deduplication via SHA256 content hash
- ✅ Rollback on errors
- ✅ Test coverage: 11/11 tests passing

**Task 10: Semantic Search + MCP Tools** (Complete - 715 lines)
- ✅ Implemented in `src/code_index_mcp/services/semantic_search_service.py`
- ✅ `SemanticSearchService` with vector similarity search
- ✅ `semantic_search()` - Natural language code search
- ✅ `find_similar_code()` - Find similar implementations
- ✅ `hybrid_search()` - Semantic + keyword filtering
- ✅ `search_by_function_name()` - Function name search
- ✅ Mock mode for testing without GCP/AlloyDB
- ✅ MCP tool integration in `server.py` (3 new tools)
- ✅ Test coverage: 21/21 tests passing

**Task 6: AlloyDB Infrastructure** (Complete - 1,583 lines)
- ✅ Terraform configuration in `deployment/gcp/alloydb/`
- ✅ SQL schema with pgvector and HNSW indexes
- ✅ Row-level security policies
- ✅ Automated provisioning scripts
- ✅ Connection management with URL encoding

**Git-Sync Integration** (Complete - 3,500 lines)
- ✅ Implemented in `src/code_index_mcp/ingestion/git_manager.py`
- ✅ Support for 4 Git platforms (GitHub, GitLab, Bitbucket, Gitea)
- ✅ Webhook handlers in `src/code_index_mcp/admin/webhook_handler.py`
- ✅ 99% token savings vs file upload
- ✅ 95% faster incremental updates
- ✅ Auto-sync via webhooks
- ✅ Test coverage: 54/54 tests passing

### ⏳ Pending Tasks

**Phase 1: AlloyDB Setup**
- ⏳ Provision AlloyDB cluster in GCP project
  - Infrastructure code ready
  - Requires manual execution: `cd deployment/gcp/alloydb && ./setup-alloydb.sh dev`
- [ ] Integration testing with real AlloyDB instance

**Phase 2: Production Hardening**
- [ ] Load testing with large codebase (10k+ files)
- [ ] Performance benchmarking and optimization
- [ ] HNSW index parameter tuning
- [ ] Connection pooling (pgbouncer)
- [ ] Monitoring and alerting setup

### Code Statistics

| Component | Production | Tests | Infrastructure | Total |
|-----------|-----------|-------|----------------|-------|
| Task 7: Chunking | 690 lines | 95 lines | - | 785 lines |
| Task 8: Vertex AI | 510 lines | 95 lines | - | 605 lines |
| Task 9: Pipeline | 695 lines | 507 lines | - | 1,202 lines |
| Task 10: Search + MCP | 715 lines | 696 lines | - | 1,411 lines |
| Task 6: AlloyDB Infra | - | - | 1,583 lines | 1,583 lines |
| Git-Sync | 1,850 lines | 1,040 lines | 610 lines | 3,500 lines |
| **Total** | **4,460 lines** | **2,433 lines** | **2,193 lines** | **9,086 lines** |

### Test Coverage

| Task | Test File | Tests | Status |
|------|-----------|-------|--------|
| Task 7 | `test_chunker.py` | 4 tests | ✅ 4/4 passed |
| Task 8 | `test_embeddings.py` | 5 tests | ✅ 5/5 passed |
| Task 9 | `test_pipeline.py` | 11 tests | ✅ 11/11 passed |
| Task 10 (Service) | `test_semantic_search.py` | 11 tests | ✅ 11/11 passed |
| Task 10 (MCP) | `test_mcp_semantic_search_tools.py` | 10 tests | ✅ 10/10 passed |
| Git-Sync | Multiple test files | 54 tests | ✅ 54/54 passed |
| **Total** | **10 test files** | **95 tests** | **✅ 95/95 passed (100%)** |

## Implementation Notes

### Critical: URL-Encode Database Passwords

**Issue**: AlloyDB passwords generated by Terraform may contain special characters that break PostgreSQL connection strings.

**Problem**: If the password contains characters like `@`, `(`, `)`, `:`, `<`, `>`, etc., the connection string parser will fail with errors like:
```
psycopg2.OperationalError: invalid integer value "..." for connection option "port"
```

**Solution**: Always URL-encode the password when storing the connection string in Secret Manager:

```python
from urllib.parse import quote_plus

# Original password with special characters
password = "***REMOVED***"

# URL-encode the password
encoded_password = quote_plus(password)
# Result: "u0kJ6MZX%40eAzCuw%28Hr1-JkogKiDB%3At%3CH"

# Build connection string with encoded password
connection_string = f"postgresql://{user}:{encoded_password}@{host}:{port}/{database}"
```

**Common characters to encode**:
- `@` → `%40`
- `(` → `%28`
- `)` → `%29`
- `:` → `%3A`
- `<` → `%3C`
- `>` → `%3E`
- `/` → `%2F`
- `?` → `%3F`
- `#` → `%23`

**When to apply**:
- When storing `ALLOYDB_CONNECTION_STRING` in Secret Manager
- After provisioning AlloyDB with Terraform
- Any time the password is updated

**Verification**:
```bash
# Check if password is URL-encoded in the secret
gcloud secrets versions access latest --secret="alloydb-connection-string"

# Should see %XX sequences for special characters
# Correct:   postgresql://user:pass%40word@host:5432/db
# Incorrect: postgresql://user:pass@word@host:5432/db
```

**Critical**: Always use `echo -n` (not `echo`) when storing secrets to prevent trailing newlines:

```bash
# WRONG - adds trailing newline → database "postgres\n" does not exist
echo "postgresql://..." | gcloud secrets versions add alloydb-connection-string --data-file=-

# CORRECT - no trailing newline
echo -n "postgresql://..." | gcloud secrets versions add alloydb-connection-string --data-file=-
```

**Reference**: [RFC 3986 - URL Encoding](https://datatracker.ietf.org/doc/html/rfc3986#section-2.1)

## Consequences

### Positive
- ✅ Native GCP integration (AlloyDB, Vertex AI, Cloud Storage)
- ✅ High performance vector search (HNSW indexes)
- ✅ Managed service (backups, HA, scaling)
- ✅ PostgreSQL compatibility (familiar tools/ORMs)
- ✅ Built-in security (encryption, VPC, IAM)
- ✅ Cost-effective for GCP-native deployments

### Negative
- ❌ GCP-specific (not portable to other clouds)
- ❌ Higher base cost than ChromaDB (~$220/month vs $0)
- ❌ AlloyDB minimum instance size (can't scale below 2 vCPU)
- ❌ Requires VPC setup and networking knowledge

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| High AlloyDB costs | Use read replicas, auto-scaling; archive old data |
| Vendor lock-in | Document migration path; keep ingestion logic modular |
| Embedding API limits | Batch requests, cache results, rate limit |
| Network complexity | Use Terraform for IaC, document setup clearly |

## Alternatives Considered

### A: ChromaDB (Generic, Cloud-Agnostic)
- **Pros**: Portable, lightweight, no DB management
- **Cons**: Separate infrastructure, less integration, no SQL
- **Decision**: Good for local/stdio mode, but AlloyDB better for GCP

### B: Cloud SQL + pgvector
- **Pros**: Cheaper ($50/month), same pgvector
- **Cons**: Slower, less optimized for vectors, no Vertex AI integration
- **Decision**: Acceptable for small teams, but AlloyDB better at scale

### C: Vertex AI Vector Search (Managed)
- **Pros**: Fully managed, optimized for ML
- **Cons**: Expensive, less flexible, no SQL queries
- **Decision**: Over-engineered for our use case

## Related ADRs
- ADR 0001: MCP Transport Protocols
- ADR 0002: Cloud Run HTTP Deployment
- ADR 0004: AWS Code Ingestion Strategy (Aurora PostgreSQL + Bedrock)
- ADR 0005: OpenShift Code Ingestion Strategy (Milvus + PostgreSQL)

## References
- [AlloyDB Vector Embeddings](https://cloud.google.com/alloydb/docs/ai/work-with-embeddings)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Vertex AI Text Embeddings](https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings)
- [AlloyDB Pricing](https://cloud.google.com/alloydb/pricing)
