# Local Development with PostgreSQL + pgvector

This guide explains how to run code-index-mcp locally with a PostgreSQL database that mimics AlloyDB's pgvector capabilities.

## Why PostgreSQL Locally Instead of AlloyDB?

**AlloyDB cannot run locally** - it's a Google Cloud managed service only. For local development:
- ✅ **PostgreSQL + pgvector**: 99% compatible with AlloyDB
- ✅ **Free and fast**: Runs on your MacBook via Docker
- ✅ **Same SQL schema**: Uses the exact same `alloydb-schema.sql`
- ✅ **Same embedding search**: pgvector extension works identically

**Pattern**: PostgreSQL for local dev → AlloyDB for production

## Quick Start

### 1. Start PostgreSQL

```bash
# Start PostgreSQL with pgvector
docker compose up -d postgres

# Check it's running
docker compose ps
docker compose logs postgres
```

**What happens**:
- PostgreSQL 16 with pgvector extension starts on port 5432
- Schema automatically applied from `deployment/gcp/alloydb-schema.sql`
- Tables created: `projects`, `code_chunks`, `users`
- Ready for semantic search testing

### 2. Verify Database Setup

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U postgres -d code_index

# Check tables
\dt

# Check pgvector extension
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

# Exit
\q
```

Expected output:
```
             List of relations
 Schema |     Name     | Type  |  Owner
--------+--------------+-------+----------
 public | code_chunks  | table | postgres
 public | projects     | table | postgres
 public | users        | table | postgres
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.local.example .env.local

# Edit with your settings
vim .env.local
```

Key settings:
```bash
DATABASE_URL=postgresql://postgres:localdevpass@localhost:5432/code_index
USE_MOCK_EMBEDDINGS=true  # Free, no GCP needed
MCP_TRANSPORT=stdio  # Local mode
```

### 4. Run MCP Server Locally

```bash
# Activate venv
source .venv/bin/activate

# Run server
uv run code-index-mcp
```

### 5. Test Semantic Search

```bash
# In another terminal, run tests
cd tests/ansible
ansible-playbook test-local.yml -i inventory/local.yml
```

## Optional: pgAdmin (Database UI)

```bash
# Start PostgreSQL + pgAdmin
docker compose --profile tools up -d

# Open pgAdmin
open http://localhost:5050

# Login: admin@code-index.local / admin
```

Add server in pgAdmin:
- Host: postgres
- Port: 5432
- Database: code_index
- Username: postgres
- Password: localdevpass

## Database Operations

### Reset Database

```bash
# Stop and remove containers
docker compose down

# Remove data volumes
docker volume rm code-index-mcp_postgres-data

# Restart (schema will be reapplied)
docker compose up -d postgres
```

### View Logs

```bash
# All services
docker compose logs -f

# Just PostgreSQL
docker compose logs -f postgres
```

### Stop Services

```bash
# Stop but keep data
docker compose stop

# Stop and remove containers (keeps volumes)
docker compose down

# Stop and remove everything including data
docker compose down -v
```

## Connection Strings

**Local PostgreSQL**:
```
postgresql://postgres:localdevpass@localhost:5432/code_index
```

**Production AlloyDB** (from Secret Manager):
```
postgresql://postgres:SECURE_PASSWORD@10.22.0.2:5432/code_index
```

## Testing Workflow

### 1. Test Metadata-Only Features (No Database)

```bash
# These work without PostgreSQL
uv run code-index-mcp

# Test in MCP Inspector
npx @modelcontextprotocol/inspector uv run code-index-mcp

# Try tools: set_project_path, find_files, search_code_advanced
```

### 2. Test Semantic Search (Requires PostgreSQL)

```bash
# Start PostgreSQL
docker compose up -d postgres

# Run server
uv run code-index-mcp

# Test semantic search tools:
# - semantic_search_code()
# - ingest_code_from_git()
# - find_similar_code()
```

### 3. Test Cloud Deployment (Requires AlloyDB)

```bash
# Deploy to GCP
cd deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml

# Test cloud
cd tests/ansible
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
```

## Troubleshooting

### Port 5432 Already in Use

```bash
# Check what's using port 5432
lsof -i :5432

# If it's another postgres, stop it
brew services stop postgresql@16

# Or change port in docker-compose.yml:
# ports:
#   - "5433:5432"  # Expose on 5433 instead
```

### Schema Not Applied

```bash
# Check if schema file exists
ls -la deployment/gcp/alloydb-schema.sql

# Manually apply schema
docker compose exec postgres psql -U postgres -d code_index < deployment/gcp/alloydb-schema.sql
```

### Connection Refused

```bash
# Wait for PostgreSQL to start (takes ~5-10 seconds)
docker compose logs postgres | grep "database system is ready"

# Check health
docker compose exec postgres pg_isready -U postgres
```

### Reset Everything

```bash
# Nuclear option: remove everything
docker compose down -v
docker volume prune -f
docker compose up -d postgres
```

## Performance Notes

- **Local PostgreSQL**: Fast, no network latency, perfect for development
- **AlloyDB**: Production-grade, auto-scaling, optimized for large datasets
- **Code Compatibility**: Same SQL, same tools, seamless transition

## Next Steps

1. **Local Development**: Use PostgreSQL via Docker Compose
2. **Deploy to Cloud**: Use AlloyDB for production (see `docs/DEPLOYMENT.md`)
3. **Testing**: Use Ansible test suites (see `docs/E2E_TESTING_GUIDE.md`)

## FAQ

**Q: Can I use AlloyDB locally?**
A: No, AlloyDB is cloud-only. Use PostgreSQL + pgvector locally instead.

**Q: Will my code work the same on AlloyDB?**
A: Yes! PostgreSQL with pgvector is 99% compatible with AlloyDB for our use case.

**Q: Do I need GCP credentials for local development?**
A: No if you use `USE_MOCK_EMBEDDINGS=true`. Yes if you want real Vertex AI embeddings.

**Q: How do I apply schema changes?**
A: Edit `deployment/gcp/alloydb-schema.sql`, then restart PostgreSQL container (it auto-applies).
