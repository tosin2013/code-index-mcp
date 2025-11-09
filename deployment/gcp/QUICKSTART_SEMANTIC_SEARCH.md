# 🚀 Quick Start: Semantic Search Deployment

**Deploy semantic search to Cloud Run in 3 steps (~30 minutes, ~$100/month)**

---

## Step 1: Provision AlloyDB (~15-20 min)

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp

# Provision AlloyDB cluster and instance
./setup-alloydb.sh dev

# Create connection string secret (with URL-encoded password)
./create-connection-string-secret.sh dev
```

**What this does**:
- Creates AlloyDB cluster + instance (2 vCPU, 8GB RAM)
- **URL-encodes password** (handles special characters like `@`, `(`, `:`, `<`)
- Stores connection string in Secret Manager

**Why URL encoding?** AlloyDB passwords may contain special characters that break connection strings. See [ADR 0003](../../docs/adrs/0003-google-cloud-code-ingestion-with-alloydb.md#implementation-notes) for details.

---

### Step 1.5: Apply Database Schema

Choose **one** of the following methods to apply the schema with pgvector:

#### Option A: Local Schema Application (requires psql)

```bash
# Apply schema using local psql + Cloud SQL Proxy
./apply-schema.sh
```

**Requirements**:
- `psql` installed locally
- Downloads `cloud-sql-proxy` automatically if not present
- Applies schema from `alloydb-schema.sql` file

**What this does**:
- Starts Cloud SQL Proxy to connect to AlloyDB
- Applies schema with pgvector extension
- Creates tables: `code_chunks`, `projects`
- Sets up Row-Level Security (RLS) policies
- Creates HNSW vector index for semantic search

---

#### Option B: Cloud Run Job (no local dependencies)

```bash
# Apply schema using Cloud Run Job
./apply-schema-job.sh dev
```

**Advantages**:
- ✅ No local `psql` required
- ✅ Runs in cloud with VPC access to AlloyDB
- ✅ Self-contained with automatic cleanup
- ✅ Same schema as Option A

**What this does**:
- Builds Docker image with schema applier
- Creates temporary Cloud Run Job
- Executes schema application
- Verifies tables and functions created
- Cleans up job after completion

**Choose this if**: You don't have PostgreSQL tools installed locally or prefer cloud-native execution.

---

## Step 2: Create VPC Connector (~5 min)

```bash
gcloud compute networks vpc-access connectors create alloydb-connector \
    --region=us-east1 \
    --network=default \
    --range=10.8.0.0/28
```

**What this does**: Allows Cloud Run to connect to AlloyDB's private network

---

## Step 3: Deploy with Semantic Search (~10 min)

```bash
# Deploy Cloud Run with AlloyDB enabled
./deploy.sh dev --with-alloydb
```

**That's it!** The script will:
- ✅ Build Docker image with latest code
- ✅ Deploy to Cloud Run with AlloyDB connection
- ✅ Configure VPC networking
- ✅ Print Claude Desktop config

---

## Configure Claude Desktop

Copy the config printed by the deployment script:

**File**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://your-service.run.app/sse",
      "transport": "sse"
    }
  }
}
```

**Restart Claude Desktop** (Cmd+Q, then reopen)

---

## Test It!

In Claude Desktop, try these examples:

### 1. Ingest Your Code

```
Use the ingest_code_for_search tool to ingest my project.

Parameters:
- directory_path: /path/to/your/project
- project_name: my-api
```

### 2. Semantic Search

```
Use semantic_search_code to find "JWT authentication with token refresh" in python
```

### 3. Find Similar Code

```
Use find_similar_code to find code similar to:

def authenticate(user, password):
    token = verify(user, password)
    return token
```

### 4. Get Help

For comprehensive documentation, ask Claude to reference:
```
@guide://semantic-search-ingestion
```

This MCP resource provides:
- Usage examples and best practices
- Chunking strategy recommendations
- Cost estimation
- Troubleshooting guide

---

## 💰 Costs

| Component | Monthly Cost |
|-----------|-------------|
| Cloud Run | ~$1-5 |
| AlloyDB (dev) | ~$100 |
| VPC Connector | ~$1 |
| Vertex AI | ~$0.025 per 1M chars |
| **Total** | **~$102-106** |

---

## Stop Billing

```bash
./destroy.sh dev
```

**Warning**: Deletes everything!

---

## Troubleshooting

**"AlloyDB not configured"** → Check secret exists:
```bash
gcloud secrets versions access latest --secret=alloydb-connection-string
```

**"Invalid integer value for port"** → Password needs URL encoding:
```bash
# Recreate the connection string with URL encoding
./create-connection-string-secret.sh dev

# Redeploy Cloud Run to pick up new secret
./deploy.sh dev --with-alloydb
```

**Tools not in Claude** → Verify service URL in config, restart Claude Desktop

**Connection refused** → Check VPC connector:
```bash
gcloud compute networks vpc-access connectors list --region=us-east1
```

---

## Next Steps

- **Task 11**: Performance tuning (HNSW optimization, caching)
- **Task 12**: Integration testing (load testing, security review)
- **Production**: Use `./deploy.sh prod --with-alloydb`

---

**Total Time**: ~30 minutes  
**Total Cost**: ~$100/month

That's it! You now have semantic code search in Claude Desktop 🎉

