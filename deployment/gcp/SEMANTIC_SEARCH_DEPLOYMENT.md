# 🚀 Semantic Search Deployment Guide

**Complete guide to deploy semantic search to Cloud Run with AlloyDB**

---

## 📋 Prerequisites

- ✅ Phase 2A completed (Cloud Run deployed)
- ✅ New semantic search code committed
- ✅ GCP project with billing enabled
- ✅ gcloud CLI authenticated

---

## 💰 Cost Summary

| Component | Cost |
|-----------|------|
| Cloud Run (existing) | ~$1-5/month |
| AlloyDB (2 vCPU, dev) | ~$100/month |
| VPC Connector | ~$0.90/month |
| Vertex AI (one-time ingestion) | ~$0.025 per 1M chars |
| **Total** | **~$102-106/month** |

---

## 🚀 Deployment Steps

### **Step 1: Provision AlloyDB** (~15-20 minutes)

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp

# Provision AlloyDB dev instance
./setup-alloydb.sh dev
```

**What this does**:
- ✅ Creates AlloyDB cluster
- ✅ Creates AlloyDB instance (2 vCPU, 8GB RAM)
- ✅ Sets up VPC peering
- ✅ Initializes database schema
- ✅ Stores connection string in Secret Manager

**Output**:
```
✅ AlloyDB provisioned successfully!
Connection string stored in Secret Manager: alloydb-connection-string
```

---

### **Step 2: Create VPC Connector** (~5 minutes)

Cloud Run needs a VPC connector to reach AlloyDB's private IP:

```bash
# Set your project and region
PROJECT_ID=$(gcloud config get-value project)
REGION="us-east1"

# Create VPC connector
gcloud compute networks vpc-access connectors create alloydb-connector \
    --region=$REGION \
    --network=default \
    --range=10.8.0.0/28 \
    --project=$PROJECT_ID
```

**Expected output**:
```
Created connector [alloydb-connector].
```

---

### **Step 3: Update Cloud Run Deployment** (~10 minutes)

Now we need to redeploy Cloud Run with:
1. Latest code (semantic search tools)
2. VPC connector
3. AlloyDB connection string

#### **3a. Ensure dependencies are installed**

Check `pyproject.toml` has GCP dependencies:

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp
grep -A5 "\[project.optional-dependencies.gcp\]" pyproject.toml
```

Should show:
```toml
[project.optional-dependencies.gcp]
dependencies = [
    "google-cloud-storage>=2.10.0",
    "google-cloud-secret-manager>=2.16.0",
    "psycopg2-binary>=2.9.0",  # ← This is needed!
    "google-cloud-aiplatform>=1.38.0"
]
```

#### **3b. Modify deploy.sh to add VPC and AlloyDB**

We need to update the existing `deploy.sh` to add VPC connector and AlloyDB secret:

```bash
# Open deploy.sh
nano deployment/gcp/deploy.sh
```

Find the Cloud Run deployment section (around line 159-170) and update it:

**BEFORE** (lines 159-170):
```bash
    # Deploy Cloud Run service
    gcloud run deploy "$SERVICE_NAME" \
        --image="$IMAGE_NAME" \
        --platform=managed \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --allow-unauthenticated \
        --set-env-vars="$ENV_VARS" \
        --memory=512Mi \
        --cpu=1 \
        --max-instances=10 \
        --timeout=300
```

**AFTER** (add VPC connector and AlloyDB secret):
```bash
    # Deploy Cloud Run service
    gcloud run deploy "$SERVICE_NAME" \
        --image="$IMAGE_NAME" \
        --platform=managed \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --allow-unauthenticated \
        --set-env-vars="$ENV_VARS" \
        --set-secrets="ALLOYDB_CONNECTION_STRING=alloydb-connection-string:latest" \
        --vpc-connector=alloydb-connector \
        --vpc-egress=private-ranges-only \
        --memory=1Gi \
        --cpu=1 \
        --max-instances=10 \
        --timeout=300
```

**Changes made**:
- Added `--set-secrets` to inject AlloyDB connection string
- Added `--vpc-connector` to connect to AlloyDB's private network
- Added `--vpc-egress=private-ranges-only` for security
- Increased memory to 1Gi (needed for embeddings)

#### **3c. Deploy updated Cloud Run**

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp

# Deploy with updated configuration
./deploy.sh dev
```

**Expected output**:
```
✅ Deployment Complete!
Service URL: https://code-index-mcp-dev-xxxxx.run.app
```

---

### **Step 4: Test the Deployment** (~5 minutes)

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe code-index-mcp-dev \
    --region=us-east1 \
    --format="value(status.url)")

# Test health endpoint
curl $SERVICE_URL/health

# Test SSE endpoint
curl $SERVICE_URL/sse
```

**Expected response**:
```json
{
  "status": "healthy",
  "mcp_transport": "http",
  "alloydb_connected": true  ← Should be true!
}
```

---

### **Step 5: Configure Claude Desktop** (~2 minutes)

Edit Claude Desktop config:

```bash
# macOS
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Linux
nano ~/.config/Claude/claude_desktop_config.json
```

Add this configuration:

```json
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://code-index-mcp-dev-xxxxx.run.app/sse",
      "transport": "sse"
    }
  }
}
```

**Replace** `xxxxx` with your actual service URL!

**Restart Claude Desktop** for changes to take effect.

---

### **Step 6: Test Semantic Search in Claude Desktop** 🎉

Open Claude Desktop and try these commands:

#### **Test 1: Check available tools**
```
What MCP tools do you have available?
```

You should see:
- ✅ `semantic_search_code`
- ✅ `find_similar_code`
- ✅ `ingest_code_for_search`

#### **Test 2: Ingest code**
```
Use ingest_code_for_search to ingest code from /path/to/your/project
```

**Expected response**:
```json
{
  "status": "success",
  "project_name": "your-project",
  "files_processed": 42,
  "chunks_created": 287,
  "embeddings_generated": 287,
  "duration_seconds": 15.3
}
```

#### **Test 3: Semantic search**
```
Use semantic_search_code to find "JWT authentication" code
```

**Expected response**:
```json
[
  {
    "chunk_id": "uuid-123",
    "file_path": "auth/jwt.py",
    "function_name": "verify_jwt_token",
    "code": "def verify_jwt_token(token: str) -> User:\n    ...",
    "similarity": 0.92,
    "language": "python"
  }
]
```

#### **Test 4: Find similar code**
```
Use find_similar_code to find code similar to:
def authenticate(user, password):
    return verify_password(user, password)
```

**Expected response**: List of similar authentication functions

---

## 🔧 Troubleshooting

### **Issue 1: "AlloyDB not configured"**

**Symptom**: MCP tools return mock mode message

**Solution**:
```bash
# Check if secret exists
gcloud secrets versions access latest --secret=alloydb-connection-string

# Re-deploy Cloud Run with correct secret
cd deployment/gcp && ./deploy.sh dev
```

### **Issue 2: "Connection refused" to AlloyDB**

**Symptom**: Database connection errors in logs

**Solution**:
```bash
# Check VPC connector exists
gcloud compute networks vpc-access connectors list --region=us-east1

# Verify Cloud Run has vpc-connector configured
gcloud run services describe code-index-mcp-dev \
    --region=us-east1 \
    --format="value(spec.template.spec.containers[0].resources.vpcAccess.connector)"
```

### **Issue 3: Tools not appearing in Claude Desktop**

**Symptom**: Claude says "I don't have those tools"

**Solution**:
1. Check Claude Desktop config file has correct URL
2. Restart Claude Desktop completely (Cmd+Q, then reopen)
3. Test SSE endpoint manually:
   ```bash
   curl https://your-service.run.app/sse
   ```

### **Issue 4: High costs**

**Symptom**: Unexpected high bills

**Solution**:
```bash
# Check AlloyDB is in dev mode (2 vCPU only)
gcloud alloydb instances describe code-index-instance-dev \
    --cluster=code-index-cluster-dev \
    --region=us-east1

# Set up budget alerts
gcloud billing budgets create \
    --billing-account=YOUR-BILLING-ACCOUNT \
    --display-name="Code Index MCP Budget" \
    --budget-amount=150USD \
    --threshold-rule=percent=80
```

---

## 📊 Monitoring

### **View Cloud Run Logs**

```bash
# Tail logs in real-time
gcloud run services logs tail code-index-mcp-dev --region=us-east1

# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=code-index-mcp-dev" \
    --limit=50 \
    --format=json
```

### **Check AlloyDB Performance**

```bash
# View AlloyDB metrics in Cloud Console
gcloud monitoring dashboards list --filter="displayName:AlloyDB"
```

### **Monitor Costs**

```bash
# View current month costs
gcloud billing accounts list

# Export to BigQuery for detailed analysis
gcloud billing accounts set-usage-export \
    --billing-account=YOUR-BILLING-ACCOUNT \
    --bigquery-table=YOUR-PROJECT.billing.usage
```

---

## 🛑 Teardown (Stop Billing)

To stop incurring costs:

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp

# Delete everything (AlloyDB + Cloud Run + Storage)
./destroy.sh dev
```

**Warning**: This deletes all data!

---

## 📚 Next Steps

Once deployed and tested:

1. **Performance Tuning** (Task 11)
   - Optimize HNSW index parameters
   - Add query result caching
   - Test with large codebase

2. **Integration Testing** (Task 12)
   - End-to-end ingestion test
   - Search quality evaluation
   - Load testing

3. **Production Deployment**
   - Use `./deploy.sh prod` for production
   - Increase AlloyDB to 4+ vCPUs
   - Set up monitoring and alerts

---

## 🎉 Success Criteria

You'll know it's working when:

- ✅ Cloud Run is deployed and healthy
- ✅ AlloyDB is provisioned and accessible
- ✅ VPC connector connects Cloud Run to AlloyDB
- ✅ Claude Desktop shows 3 new semantic search tools
- ✅ You can ingest code and search by meaning
- ✅ Search results return relevant code chunks

---

**Questions? Check**:
- `docs/DEPLOYMENT.md` - General deployment guide
- `docs/adrs/0003-google-cloud-code-ingestion-with-alloydb.md` - Architecture decisions
- `docs/TROUBLESHOOTING_GUIDE.md` - Common issues

**Estimated total time**: 30-40 minutes  
**Monthly cost**: ~$102-106/month

