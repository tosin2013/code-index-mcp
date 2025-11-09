# 🐘 Local PostgreSQL Development Guide

**Purpose**: Validate code ingestion and semantic search locally before deploying to AlloyDB.

---

## ✅ What's Working

- **PostgreSQL 16** with **pgvector 0.8.1**
- All tables created: `users`, `projects`, `code_chunks`
- HNSW vector index configured (768 dimensions)
- Row-Level Security enabled
- Semantic search function ready
- Test user: `dev@localhost` (UUID: `b662bc28-c198-4a0f-b995-a1136bf5ee11`)

**Connection**: `postgresql://code_index_admin:local_dev_password@localhost:5432/code_index`

---

## 🚀 Quick Start

### 1. Start PostgreSQL
```bash
cd deployment/gcp
docker-compose up -d
```

### 2. Verify Setup
```bash
./test-local-postgres.sh
```

### 3. Configure MCP Server for Local Testing
Create `.env.local`:

```bash
# Local PostgreSQL connection
DATABASE_URL=postgresql://code_index_admin:local_dev_password@localhost:5432/code_index

# Use mock embeddings for faster testing (optional)
USE_MOCK_EMBEDDINGS=true

# Or use real Vertex AI embeddings
# GCP_PROJECT_ID=your-project
# USE_MOCK_EMBEDDINGS=false
```

---

## 📊 Database Schema

### Tables

**users**
- `user_id` (UUID, PK)
- `email`, `api_key_hash`
- `storage_quota_gb`, `is_active`

**projects**
- `project_id` (UUID, PK)
- `user_id` (FK → users)
- `project_name`, `total_chunks`, `total_files`
- `last_indexed_at`

**code_chunks** (Main table)
- `chunk_id` (UUID, PK)
- `project_id` (FK → projects)
- `file_path`, `chunk_type`, `chunk_name`
- `line_start`, `line_end`, `language`
- `content`, `content_hash` (SHA256)
- `embedding` (vector[768]) - **pgvector**
- `symbols` (JSONB)

### Indexes

- HNSW vector index: `code_chunks_embedding_idx`
  - Metric: Cosine distance (`vector_cosine_ops`)
  - Parameters: `m=16`, `ef_construction=64`

---

## 🧪 Testing Workflow

### Step 1: Test Code Chunking

```python
from src.code_index_mcp.ingestion.chunker import CodeChunker

chunker = CodeChunker()
chunks = chunker.chunk_file("/path/to/file.py", "python")

print(f"Created {len(chunks)} chunks")
for chunk in chunks[:3]:
    print(f"  - {chunk.chunk_type}: {chunk.chunk_name} ({chunk.line_start}-{chunk.line_end})")
```

### Step 2: Test Embedding Generation (Mock)

```python
from src.code_index_mcp.embeddings.mock import MockEmbedder

embedder = MockEmbedder()
embedding = embedder.embed_text("def hello(): pass")

print(f"Embedding shape: {len(embedding)} dimensions")
```

### Step 3: Test Database Ingestion

```python
import asyncpg
import asyncio

async def test_ingestion():
    conn = await asyncpg.connect(
        "postgresql://code_index_admin:local_dev_password@localhost:5432/code_index"
    )

    # Get test user
    user = await conn.fetchrow("SELECT user_id FROM users WHERE email = 'dev@localhost'")

    # Create project
    project = await conn.fetchrow("""
        INSERT INTO projects (user_id, project_name)
        VALUES ($1, 'test-project')
        ON CONFLICT (user_id, project_name) DO UPDATE SET updated_at = NOW()
        RETURNING project_id
    """, user['user_id'])

    # Insert chunk with embedding
    embedding = [0.1] * 768  # Mock embedding
    await conn.execute("""
        INSERT INTO code_chunks
        (project_id, file_path, chunk_type, chunk_name, content, content_hash, embedding)
        VALUES ($1, 'test.py', 'function', 'test_func', 'def test_func(): pass', 'abc123', $2)
    """, project['project_id'], embedding)

    # Verify
    count = await conn.fetchval("SELECT COUNT(*) FROM code_chunks WHERE project_id = $1", project['project_id'])
    print(f"✅ Inserted {count} chunk(s)")

    await conn.close()

asyncio.run(test_ingestion())
```

### Step 4: Test Semantic Search

```python
async def test_search():
    conn = await asyncpg.connect("postgresql://code_index_admin:local_dev_password@localhost:5432/code_index")

    user = await conn.fetchrow("SELECT user_id FROM users WHERE email = 'dev@localhost'")
    query_embedding = [0.1] * 768  # Should match our test chunk

    results = await conn.fetch("""
        SELECT * FROM semantic_search_code($1, $2, 'test-project', NULL, 5)
    """, user['user_id'], query_embedding)

    for row in results:
        print(f"Found: {row['file_path']}:{row['chunk_name']} (score: {row['similarity_score']:.3f})")

    await conn.close()

asyncio.run(test_search())
```

---

## 🔄 Local → AlloyDB Migration

Once local testing passes:

1. **Export schema** (already compatible):
   ```bash
   cp local-postgres-schema.sql alloydb-schema.sql
   # Add google_ml_integration extension
   ```

2. **Deploy to AlloyDB**:
   ```bash
   ./apply-schema-job.sh dev  # Uses Cloud Run Job
   ```

3. **Update MCP server** with AlloyDB connection:
   ```bash
   ./deploy.sh dev --with-alloydb
   ```

---

## 🎯 Use Case: ADR Research & Updates

### Store ADRs in PostgreSQL

```sql
-- Create ADR table (future enhancement)
CREATE TABLE IF NOT EXISTS adrs (
    adr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adr_number INTEGER UNIQUE NOT NULL,
    title TEXT NOT NULL,
    status VARCHAR(20), -- 'proposed', 'accepted', 'superseded', 'deprecated'
    content TEXT NOT NULL,
    embedding vector(768),
    metadata JSONB, -- links, tags, references
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX adrs_embedding_idx ON adrs
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### Semantic ADR Search
```python
# Find related ADRs for a new decision
results = await conn.fetch("""
    SELECT adr_number, title, status,
           (1 - (embedding <=> $1)) AS similarity
    FROM adrs
    WHERE status = 'accepted'
    ORDER BY embedding <=> $1
    LIMIT 5
""", decision_embedding)
```

### Auto-Update ADRs with Research
```python
# MCP server can:
# 1. Search ADRs semantically
# 2. Find related research/code changes
# 3. Suggest ADR updates
# 4. Track ADR evolution over time
```

---

## 🛠️ Maintenance

### View Logs
```bash
docker-compose logs -f postgres
```

### Connect to Database
```bash
psql postgresql://code_index_admin:local_dev_password@localhost:5432/code_index
```

### Reset Database
```bash
docker-compose down -v  # Deletes all data
docker-compose up -d    # Fresh start with schema
```

### Stop PostgreSQL
```bash
docker-compose down  # Keeps data
```

---

## 📈 Next Steps

1. **Test ingestion pipeline** with real code
2. **Validate semantic search** accuracy
3. **Benchmark performance** (HNSW tuning)
4. **Add ADR table** for research workflow
5. **Deploy to AlloyDB** when ready

---

## 💡 Benefits of Local Testing

- ✅ **99% faster iteration** (no cloud deployment)
- ✅ **Zero cloud costs** during development
- ✅ **Easy debugging** with direct database access
- ✅ **Validate schema** before AlloyDB deployment
- ✅ **Test ADR research** workflow locally

---

**Connection String**: `postgresql://code_index_admin:local_dev_password@localhost:5432/code_index`
