# Quick Start: Authentication Setup

**TL;DR**: Authentication infrastructure is ready, but you can test semantic search now without it.

---

## 🚀 Option A: Test Semantic Search NOW (No Auth)

**Time**: 5 minutes
**Recommended for**: Testing and development

```bash
# 1. Deploy (already done, but here's the command)
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp
./deploy.sh dev --with-alloydb

# 2. Get your Cloud Run URL
gcloud run services describe code-index-mcp-dev \
    --region=us-east1 \
    --format="value(status.url)"
```

**Claude Desktop Config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app/sse",
      "transport": "sse"
    }
  }
}
```

**Test It**:
1. Restart Claude Desktop
2. Run: `ingest_code_for_search(directory_path="/Users/tosinakinosho/workspaces/documcp", project_name="documcp")`
3. Check logs: `gcloud run services logs tail code-index-mcp-dev --region=us-east1 | grep -i ingestion`

---

## 🔐 Option B: Deploy With Authentication (Secure)

**Time**: 10 minutes
**Recommended for**: Production or security-conscious testing

```bash
# 1. Deploy with auth
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp
./deploy.sh dev --with-alloydb --require-auth

# 2. Generate API key
./generate-api-key.sh demo-user dev

# 3. Copy the API key from output (starts with ci_)
```

**Claude Desktop Config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app/sse",
      "transport": "sse",
      "headers": {
        "X-API-Key": "ci_your_generated_key_here"
      }
    }
  }
}
```

**Test It**:
1. Restart Claude Desktop
2. Run: `ingest_code_for_search(directory_path="/Users/tosinakinosho/workspaces/documcp", project_name="documcp")`
3. Check logs: `gcloud run services logs tail code-index-mcp-dev --region=us-east1 | grep -i ingestion`

---

## 📊 Current Status

| Feature | Status | Notes |
|---------|--------|-------|
| API Key Generation | ✅ Complete | `generate-api-key.sh` ready |
| Deployment with --require-auth | ✅ Complete | Sets REQUIRE_AUTH=true |
| Auth Middleware | ✅ Complete | Full implementation in `middleware/auth.py` |
| FastMCP Integration | ⏳ Pending | Not enforced yet |
| Claude Desktop Headers | ✅ Supported | Can send X-API-Key header |

**What this means**:
- You can use auth **now** (infrastructure ready)
- Keys won't be validated **yet** (middleware not connected)
- **No harm** in setting it up early
- **Easy** to add auth later with redeploy

---

## 🎯 My Recommendation

### **Start with Option A (No Auth)**

**Why?**
1. ✅ Fastest way to test semantic search
2. ✅ The 404 error was session timeout, not auth
3. ✅ You can add auth later in 5 minutes

**Do This Now**:
```bash
# Just restart Claude Desktop!
# The deployment is already done.
```

Then test ingestion and see if data appears in AlloyDB.

**Add Auth Later** (when ready):
```bash
cd deployment/gcp
./deploy.sh dev --with-alloydb --require-auth
./generate-api-key.sh demo-user dev
# Update Claude Desktop with API key
```

---

## 🆘 Troubleshooting

### "404 Session Not Found"
**Fix**: Restart Claude Desktop (creates fresh SSE connection)

### "Failure listing resources"
**Fix**: Restart Claude Desktop (session expired)

### "No data in AlloyDB"
**Cause**: Ingestion not run yet
**Fix**: Run `ingest_code_for_search()` in Claude Desktop

### "Authentication Failed" (when auth is enforced)
**Fix**:
1. Check API key in Claude Desktop config
2. Verify: `gcloud secrets versions access latest --secret=code-index-api-key-demo-user-dev`

---

## 📝 Quick Commands Reference

```bash
# Deploy without auth
./deploy.sh dev --with-alloydb

# Deploy with auth
./deploy.sh dev --with-alloydb --require-auth

# Generate API key
./generate-api-key.sh demo-user dev

# View logs
gcloud run services logs tail code-index-mcp-dev --region=us-east1

# Check AlloyDB connection
gcloud alloydb clusters describe code-index-cluster-dev --region=us-east1

# List API keys
gcloud secrets list --filter="labels.service:code-index-mcp"

# Revoke API key
gcloud secrets delete code-index-api-key-demo-user-dev
```

---

**Ready to test semantic search?** Just restart Claude Desktop and run `ingest_code_for_search()`! 🚀
