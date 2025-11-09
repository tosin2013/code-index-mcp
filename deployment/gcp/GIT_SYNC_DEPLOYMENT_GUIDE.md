# Git-Sync Deployment and Testing Guide

This guide walks you through deploying the Git-Sync feature to Google Cloud Run and testing the end-to-end workflow.

## Prerequisites

- ✅ Git-Sync code implementation complete (Phases 1-4)
- ✅ Deployment scripts updated (Phase 5)
- ✅ GCP project configured: `gcloud config set project YOUR-PROJECT-ID`
- ✅ Authenticated: `gcloud auth login`
- ✅ Docker installed (for local testing)

## Phase 5: Deployment Steps

### Step 1: Setup Webhook Secrets

Before deploying, generate webhook secrets for each Git platform you plan to use:

```bash
cd deployment/gcp

# Setup all platforms (GitHub, GitLab, Gitea)
./setup-webhook-secrets.sh

# Or setup individual platforms
./setup-webhook-secrets.sh github
./setup-webhook-secrets.sh gitlab
./setup-webhook-secrets.sh gitea
```

**What this does:**
- Generates secure random secrets (64 characters)
- Stores them in Google Secret Manager
- Grants Cloud Run service account access
- Displays webhook configuration URLs

**Copy the secrets shown!** You'll need them when configuring webhooks in Step 4.

### Step 2: Deploy to Cloud Run

Deploy the MCP server with Git-sync support:

```bash
cd deployment/gcp

# Basic deployment (no AlloyDB)
./deploy.sh dev

# With semantic search (requires AlloyDB setup)
./deploy.sh dev --with-alloydb

# With authentication
./deploy.sh dev --require-auth
```

**What this does:**
- Creates two GCS buckets:
  - `code-index-projects-{project-id}` - User projects and indexes
  - `code-index-git-repos-{project-id}` - Git repository clones
- Builds Docker image with git support
- Deploys to Cloud Run with webhook secrets
- Sets up automatic cleanup job
- Displays service URL and webhook endpoints

**Expected output:**
```
========================================
  Deployment Complete!
========================================

Environment:     dev
Project ID:      your-project-id
Region:          us-east1
Service Name:    code-index-mcp-dev
Service URL:     https://code-index-mcp-dev-xxxx.run.app
Storage Bucket:  gs://code-index-projects-your-project-id
Git Bucket:      gs://code-index-git-repos-your-project-id

Git-Sync Webhooks:
  ✓ Github: https://code-index-mcp-dev-xxxx.run.app/webhook/github
  ✓ Gitlab: https://code-index-mcp-dev-xxxx.run.app/webhook/gitlab
  ✓ Gitea: https://code-index-mcp-dev-xxxx.run.app/webhook/gitea
```

### Step 3: Test Basic Connectivity

Test that the server is running:

```bash
# Get your service URL from deployment output
SERVICE_URL="https://code-index-mcp-dev-xxxx.run.app"

# Test health endpoint
curl -f "$SERVICE_URL/health"

# Expected: {"status": "healthy"}
```

### Step 4: Test Git Ingestion (Initial Clone)

Test the `ingest_code_from_git` MCP tool:

#### Option A: Using MCP Inspector (Recommended)

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector with your service
npx @modelcontextprotocol/inspector \
  --transport sse \
  --url "$SERVICE_URL/sse"

# In the inspector web UI:
# 1. Go to Tools tab
# 2. Find "ingest_code_from_git"
# 3. Fill in parameters:
{
  "git_url": "https://github.com/anthropics/anthropic-sdk-python",
  "project_name": "anthropic-sdk",
  "branch": "main"
}
```

#### Option B: Using curl (Direct API call)

```bash
# For public repository
curl -X POST "$SERVICE_URL/tools/ingest_code_from_git" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/anthropics/anthropic-sdk-python",
    "project_name": "anthropic-sdk",
    "branch": "main"
  }'

# For private repository (with auth token)
curl -X POST "$SERVICE_URL/tools/ingest_code_from_git" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/your-org/private-repo",
    "project_name": "private-repo",
    "branch": "main",
    "auth_token": "ghp_xxxxxxxxxxxxxxxxxxxxx"
  }'
```

**Expected output:**
```json
{
  "success": true,
  "sync_type": "clone",
  "repository": "anthropics/anthropic-sdk-python",
  "branch": "main",
  "local_path": "/tmp/git-xxxxx",
  "ingestion_stats": {
    "chunks_created": 245,
    "files_processed": 87,
    "duration_seconds": 12.5
  }
}
```

**What to verify:**
- ✅ Repository cloned successfully
- ✅ Files processed and chunked
- ✅ Chunks stored in AlloyDB (if enabled)
- ✅ Repository backed up to GCS (`gs://code-index-git-repos-*/repos/github.com/...`)

### Step 5: Verify Repository Storage in GCS

Check that the repository was backed up to Cloud Storage:

```bash
# List repositories in Git bucket
gsutil ls -r gs://code-index-git-repos-your-project-id/repos/

# Expected:
# gs://code-index-git-repos-your-project-id/repos/github.com/anthropics/anthropic-sdk-python/
```

### Step 6: Configure Webhooks in Git Platform

Configure webhooks to enable automatic sync on push:

#### GitHub Webhook Setup

1. Go to your repository on GitHub
2. Navigate to: **Settings → Webhooks → Add webhook**
3. Configure:
   - **Payload URL**: `https://code-index-mcp-dev-xxxx.run.app/webhook/github`
   - **Content type**: `application/json`
   - **Secret**: [Paste secret from Step 1]
   - **Events**: Select "Just the push event"
   - **Active**: ✅ Checked
4. Click "Add webhook"
5. GitHub will send a test ping - verify it succeeds

#### GitLab Webhook Setup

1. Go to your project on GitLab
2. Navigate to: **Settings → Webhooks**
3. Configure:
   - **URL**: `https://code-index-mcp-dev-xxxx.run.app/webhook/gitlab`
   - **Secret token**: [Paste secret from Step 1]
   - **Trigger**: ✅ Push events only
   - **Enable SSL verification**: ✅ Checked
4. Click "Add webhook"
5. Click "Test" → "Push events" to verify

#### Gitea Webhook Setup

1. Go to your repository on Gitea
2. Navigate to: **Settings → Webhooks → Add Webhook → Gitea**
3. Configure:
   - **Target URL**: `https://code-index-mcp-dev-xxxx.run.app/webhook/gitea`
   - **HTTP Method**: `POST`
   - **POST Content Type**: `application/json`
   - **Secret**: [Paste secret from Step 1]
   - **Trigger On**: ✅ Push events only
   - **Active**: ✅ Checked
4. Click "Add Webhook"
5. Click "Test Delivery" to verify

### Step 7: Test Webhook Auto-Sync

Test incremental updates via webhooks:

1. **Make a change** to your repository:
   ```bash
   cd /path/to/your/repo
   echo "# Test change" >> README.md
   git add README.md
   git commit -m "Test webhook sync"
   git push origin main
   ```

2. **Verify webhook received**:
   ```bash
   # View Cloud Run logs
   gcloud run services logs tail code-index-mcp-dev --region=us-east1

   # Look for:
   # [WEBHOOK] Received GitHub push webhook for user/repo
   # [GIT-SYNC] Pulling changes for github.com/user/repo
   # [GIT-SYNC] Changed files: 1
   # [INGESTION] Re-ingesting changed files...
   ```

3. **Check webhook delivery** in Git platform:
   - GitHub: Go to webhook → Recent Deliveries
   - GitLab: Go to webhook → Recent events
   - Gitea: Go to webhook → Recent Deliveries

**Expected webhook response:**
```json
{
  "status": "accepted",
  "repo": "user/repo",
  "branch": "main",
  "commits": 1,
  "message": "Webhook processed successfully, sync in progress"
}
```

### Step 8: Verify Incremental Update

Test that only changed files were re-ingested:

```bash
# Call ingest_code_from_git again
curl -X POST "$SERVICE_URL/tools/ingest_code_from_git" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/user/repo",
    "project_name": "your-project"
  }'

# Expected output:
{
  "success": true,
  "sync_type": "pull",  # <-- Note: "pull" not "clone"
  "files_changed": 1,   # <-- Only 1 file updated
  "changed_files": ["README.md"],
  "ingestion_stats": {
    "chunks_created": 2,  # <-- Only changed chunks
    "duration_seconds": 0.8  # <-- Much faster!
  }
}
```

**What to verify:**
- ✅ `sync_type` is "pull" (not "clone")
- ✅ Only changed files listed
- ✅ Faster ingestion (< 1 second vs 10+ seconds)
- ✅ Existing chunks preserved

### Step 9: Test Rate Limiting

Test that rapid webhooks are rate-limited:

```bash
# Push twice rapidly
cd /path/to/your/repo
echo "# Change 1" >> README.md && git add . && git commit -m "1" && git push
echo "# Change 2" >> README.md && git add . && git commit -m "2" && git push

# Check logs - second webhook should be rate-limited
gcloud run services logs tail code-index-mcp-dev --region=us-east1

# Look for:
# [WEBHOOK] Webhook for user/repo rate limited (30s minimum interval)
```

### Step 10: Test Error Handling

Test that invalid webhooks are rejected:

```bash
# Test with invalid signature
curl -X POST "$SERVICE_URL/webhook/github" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=invalid" \
  -d '{"ref": "refs/heads/main"}'

# Expected: 401 Unauthorized
```

## End-to-End Test Checklist

### ✅ Deployment
- [ ] Webhook secrets created in Secret Manager
- [ ] Cloud Run service deployed successfully
- [ ] GCS buckets created (projects + git)
- [ ] Service URL accessible
- [ ] Health check passes

### ✅ Initial Ingestion
- [ ] `ingest_code_from_git` clones repository
- [ ] Files processed and chunked
- [ ] Repository backed up to GCS
- [ ] Chunks stored in AlloyDB (if enabled)

### ✅ Webhook Configuration
- [ ] Webhooks configured in Git platforms
- [ ] Webhook secrets stored securely
- [ ] Test webhook delivery succeeds

### ✅ Auto-Sync
- [ ] Push event triggers webhook
- [ ] Webhook signature verified
- [ ] Repository pulled (not cloned)
- [ ] Only changed files re-ingested
- [ ] Incremental update faster (< 1s vs 10s+)

### ✅ Rate Limiting
- [ ] Rapid webhooks rate-limited (30s minimum)
- [ ] Rate limit message in logs

### ✅ Error Handling
- [ ] Invalid signatures rejected (401)
- [ ] Non-push events ignored
- [ ] Missing fields handled gracefully

## Performance Metrics

Expected performance improvements:

| Metric | Legacy (file upload) | Git-Sync |
|--------|---------------------|----------|
| Initial ingestion | 30-60s | 10-20s |
| Incremental update | 30-60s | 0.5-2s |
| Token usage | ~10,000 tokens | ~100 tokens |
| Network transfer | Full codebase | Changed files only |
| User effort | Manual copy-paste | Automatic on push |

## Troubleshooting

### Issue: Webhook returns 401 Unauthorized

**Cause:** Webhook secret mismatch

**Fix:**
1. Regenerate secret: `./setup-webhook-secrets.sh github`
2. Update webhook in Git platform
3. Re-deploy: `./deploy.sh dev`

### Issue: Repository not backed up to GCS

**Cause:** GCS bucket permissions or missing GCS_GIT_BUCKET env var

**Fix:**
```bash
# Verify bucket exists
gsutil ls gs://code-index-git-repos-your-project-id

# Re-deploy with correct bucket
./deploy.sh dev
```

### Issue: Webhook processed but no sync

**Cause:** Background sync failed, check logs

**Fix:**
```bash
# View detailed logs
gcloud run services logs tail code-index-mcp-dev \
  --region=us-east1 \
  --format="table(timestamp,textPayload)"

# Look for errors in [GIT-SYNC] or [INGESTION] logs
```

### Issue: Rate limiting too aggressive

**Cause:** Default 30s minimum interval

**Fix:** Adjust `min_interval_seconds` in `webhook_handler.py`:
```python
# src/code_index_mcp/admin/webhook_handler.py:24
self.min_interval_seconds = 30  # Increase to 60 or 120
```

## Monitoring and Maintenance

### View Logs
```bash
# Tail logs in real-time
gcloud run services logs tail code-index-mcp-dev --region=us-east1

# Filter for webhook events
gcloud run services logs read code-index-mcp-dev \
  --region=us-east1 \
  --filter='textPayload=~"WEBHOOK"'

# Filter for Git-sync events
gcloud run services logs read code-index-mcp-dev \
  --region=us-east1 \
  --filter='textPayload=~"GIT-SYNC"'
```

### View Metrics
```bash
# Cloud Run metrics dashboard
gcloud run services describe code-index-mcp-dev \
  --region=us-east1 \
  --format="value(status.url)"

# Open in browser: [URL]/metrics
```

### Cost Monitoring
```bash
# Estimate monthly costs
# - Cloud Run: ~$5-20/month (serverless, scales to zero)
# - Cloud Storage: ~$1-5/month (depends on repo sizes)
# - Secret Manager: ~$0.06/month (3 secrets)
# - Cloud Scheduler: ~$0.10/month (1 job)
# Total: ~$6-25/month
```

## Next Steps

After successful deployment and testing:

1. **Configure Claude Desktop** with your service URL
2. **Add more repositories** via `ingest_code_from_git`
3. **Enable AlloyDB** for semantic search (if not already enabled)
4. **Set up production deployment** with `./deploy.sh prod --require-auth`
5. **Monitor webhook activity** and adjust rate limits as needed

## Success Criteria

✅ All tests passed
✅ Webhooks configured and verified
✅ Auto-sync working on push
✅ 95%+ faster incremental updates
✅ 99%+ token savings vs file upload
✅ No manual file uploads needed

**Congratulations! Git-Sync is fully operational! 🎉**
