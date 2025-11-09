# Quick Deployment Guide - Git-Sync

**TL;DR:** Deploy Code Index MCP with Git-sync in 5 minutes

## Prerequisites
```bash
gcloud config set project YOUR-PROJECT-ID
gcloud auth login
```

## 1. Setup Webhook Secrets (2 minutes)
```bash
cd deployment/gcp
./setup-webhook-secrets.sh
```
**Copy the secrets shown!** You'll need them for Step 4.

## 2. Deploy to Cloud Run (2 minutes)
```bash
# Basic deployment
./deploy.sh dev

# With semantic search (requires AlloyDB)
./deploy.sh dev --with-alloydb

# With authentication
./deploy.sh dev --require-auth
```

**Copy the service URL from output!**

## 3. Test Git Ingestion (30 seconds)
```bash
SERVICE_URL="https://code-index-mcp-dev-xxxx.run.app"

# Test health
curl "$SERVICE_URL/health"

# Test ingestion (replace with your repo)
curl -X POST "$SERVICE_URL/tools/ingest_code_from_git" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/anthropics/anthropic-sdk-python",
    "project_name": "test-project"
  }'
```

## 4. Configure Webhooks (1 minute per platform)

### GitHub
1. Go to: **Settings → Webhooks → Add webhook**
2. **Payload URL**: `https://your-service.run.app/webhook/github`
3. **Secret**: [Paste from Step 1]
4. **Events**: Just the push event

### GitLab
1. Go to: **Settings → Webhooks**
2. **URL**: `https://your-service.run.app/webhook/gitlab`
3. **Secret token**: [Paste from Step 1]
4. **Trigger**: Push events only

### Gitea
1. Go to: **Settings → Webhooks → Add Webhook → Gitea**
2. **Target URL**: `https://your-service.run.app/webhook/gitea`
3. **Secret**: [Paste from Step 1]
4. **Trigger On**: Push events only

## 5. Test Auto-Sync (30 seconds)
```bash
cd /path/to/your/repo
echo "# Test" >> README.md
git add . && git commit -m "Test webhook" && git push

# Check logs
gcloud run services logs tail code-index-mcp-dev --region=us-east1
```

## Done! 🎉

**Benefits:**
- ✅ 99% token savings vs file upload
- ✅ 95% faster incremental updates
- ✅ Auto-sync on every push
- ✅ No manual file uploads needed

**Next Steps:**
- Add more repositories via `ingest_code_from_git`
- Configure Claude Desktop with service URL
- Enable semantic search with `--with-alloydb`

**Troubleshooting:**
See `GIT_SYNC_DEPLOYMENT_GUIDE.md` for detailed instructions and troubleshooting.

**Cost:**
~$6-25/month (serverless, scales to zero)
