# Git-Sync Deployment Checklist

Use this checklist to track your deployment progress.

## Pre-Deployment

### Prerequisites
- [ ] GCP account with billing enabled
- [ ] `gcloud` CLI installed and authenticated
- [ ] Project configured: `gcloud config set project YOUR-PROJECT-ID`
- [ ] Docker installed (optional, for local testing)

### Review Documentation
- [ ] Read [QUICK_DEPLOY.md](QUICK_DEPLOY.md) for overview
- [ ] Read [GIT_SYNC_DEPLOYMENT_GUIDE.md](GIT_SYNC_DEPLOYMENT_GUIDE.md) for details
- [ ] Review [deploy.sh](deploy.sh) script
- [ ] Review [setup-webhook-secrets.sh](setup-webhook-secrets.sh) script

## Step 1: Setup Webhook Secrets (~2 minutes)

```bash
cd deployment/gcp
./setup-webhook-secrets.sh
```

### Checklist
- [ ] Script executed successfully
- [ ] GitHub webhook secret generated and displayed
- [ ] GitLab webhook secret generated and displayed
- [ ] Gitea webhook secret generated and displayed
- [ ] Secrets stored in Google Secret Manager
- [ ] Service account granted access to secrets

### Outputs to Save
```
GitHub Secret: _______________________________________________________
GitLab Secret: _______________________________________________________
Gitea Secret:  _______________________________________________________
```

## Step 2: Deploy to Cloud Run (~3 minutes)

```bash
./deploy.sh dev
```

### Checklist
- [ ] APIs enabled successfully
- [ ] Project bucket created: `code-index-projects-{project-id}`
- [ ] Git bucket created: `code-index-git-repos-{project-id}`
- [ ] Docker image built via Cloud Build
- [ ] Service deployed to Cloud Run
- [ ] Health check passed
- [ ] Cleanup job created

### Outputs to Save
```
Service URL: __________________________________________________________
Webhook URLs:
  GitHub:  __________________________________________________________
  GitLab:  __________________________________________________________
  Gitea:   __________________________________________________________
```

## Step 3: Test Basic Connectivity (~30 seconds)

```bash
SERVICE_URL="https://code-index-mcp-dev-xxxx.run.app"
curl -f "$SERVICE_URL/health"
```

### Checklist
- [ ] Health endpoint returns `{"status": "healthy"}`
- [ ] Service responding within 1-2 seconds
- [ ] No errors in Cloud Run logs

## Step 4: Test Git Ingestion (~2 minutes)

### Test with Public Repository

```bash
curl -X POST "$SERVICE_URL/tools/ingest_code_from_git" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/anthropics/anthropic-sdk-python",
    "project_name": "test-anthropic-sdk"
  }'
```

### Checklist
- [ ] Repository cloned successfully
- [ ] Files processed and chunked
- [ ] Response includes `"sync_type": "clone"`
- [ ] Response includes ingestion stats
- [ ] Repository backed up to GCS
- [ ] No errors in Cloud Run logs

### Test with Your Repository (Optional)

```bash
curl -X POST "$SERVICE_URL/tools/ingest_code_from_git" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/YOUR_ORG/YOUR_REPO",
    "project_name": "your-project",
    "auth_token": "ghp_xxxxxxxxxxxxx"
  }'
```

### Checklist
- [ ] Private repository cloned successfully
- [ ] Authentication token worked
- [ ] Files processed correctly

## Step 5: Verify Repository Storage (~1 minute)

```bash
gsutil ls -r gs://code-index-git-repos-*/repos/
```

### Checklist
- [ ] Repository visible in GCS bucket
- [ ] Correct path: `repos/{platform}/{owner}/{repo}/`
- [ ] `.git` directory present
- [ ] Source files present

## Step 6: Configure GitHub Webhook (~2 minutes)

1. Go to repository: **Settings → Webhooks → Add webhook**

### Configuration
- [ ] Payload URL: `https://your-service.run.app/webhook/github`
- [ ] Content type: `application/json`
- [ ] Secret: [Paste GitHub secret from Step 1]
- [ ] Events: ✅ Just the push event
- [ ] Active: ✅ Checked
- [ ] Webhook created successfully
- [ ] Test ping succeeded (green checkmark)

### Test Webhook Delivery
- [ ] Recent Deliveries shows test ping
- [ ] Response status: 200 OK
- [ ] Response body: `{"status": "ignored", "reason": "Not a push event"}`

## Step 7: Configure GitLab Webhook (~2 minutes)

1. Go to project: **Settings → Webhooks**

### Configuration
- [ ] URL: `https://your-service.run.app/webhook/gitlab`
- [ ] Secret token: [Paste GitLab secret from Step 1]
- [ ] Trigger: ✅ Push events only
- [ ] Enable SSL verification: ✅ Checked
- [ ] Webhook created successfully
- [ ] Test → Push events succeeded

### Test Webhook Delivery
- [ ] Recent events shows test push
- [ ] Status: 200
- [ ] Response body includes `"status": "ignored"`

## Step 8: Configure Gitea Webhook (~2 minutes)

1. Go to repository: **Settings → Webhooks → Add Webhook → Gitea**

### Configuration
- [ ] Target URL: `https://your-service.run.app/webhook/gitea`
- [ ] HTTP Method: POST
- [ ] POST Content Type: `application/json`
- [ ] Secret: [Paste Gitea secret from Step 1]
- [ ] Trigger On: ✅ Push events only
- [ ] Active: ✅ Checked
- [ ] Webhook created successfully
- [ ] Test Delivery succeeded

### Test Webhook Delivery
- [ ] Recent Deliveries shows test delivery
- [ ] Status: 200 OK
- [ ] Response includes `"status": "ignored"`

## Step 9: Test Auto-Sync (~2 minutes)

### Make a Test Commit

```bash
cd /path/to/your/repo
echo "# Test Git-sync" >> README.md
git add README.md
git commit -m "Test webhook auto-sync"
git push origin main
```

### Verify Webhook Received
- [ ] Webhook delivery shows in Git platform (200 OK)
- [ ] Response: `{"status": "accepted", "repo": "...", "commits": 1}`

### Check Cloud Run Logs

```bash
gcloud run services logs tail code-index-mcp-dev --region=us-east1
```

- [ ] `[WEBHOOK] Received {platform} push webhook for {repo}`
- [ ] `[GIT-SYNC] Pulling changes for {platform}/{owner}/{repo}`
- [ ] `[GIT-SYNC] Changed files: 1`
- [ ] `[INGESTION] Re-ingesting changed files...`
- [ ] No errors in logs

## Step 10: Test Incremental Update (~1 minute)

### Call ingest_code_from_git Again

```bash
curl -X POST "$SERVICE_URL/tools/ingest_code_from_git" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/your-org/your-repo",
    "project_name": "your-project"
  }'
```

### Verify Incremental Update
- [ ] Response shows `"sync_type": "pull"` (not "clone")
- [ ] `"files_changed": 1` (only the changed file)
- [ ] `"changed_files": ["README.md"]`
- [ ] Duration < 2 seconds (much faster than initial clone)

## Step 11: Test Rate Limiting (~1 minute)

### Push Twice Rapidly

```bash
cd /path/to/your/repo
echo "# Change 1" >> README.md && git add . && git commit -m "1" && git push
echo "# Change 2" >> README.md && git add . && git commit -m "2" && git push
```

### Verify Rate Limiting
- [ ] First webhook: `{"status": "accepted"}`
- [ ] Second webhook: `{"status": "rate_limited"}`
- [ ] Logs show: `Webhook for {repo} rate limited (30s minimum interval)`

## Step 12: Test Error Handling (~1 minute)

### Test Invalid Signature

```bash
curl -X POST "$SERVICE_URL/webhook/github" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=invalid" \
  -d '{"ref": "refs/heads/main"}'
```

### Verify Rejection
- [ ] Response status: 401 Unauthorized
- [ ] Response body: `{"detail": "Invalid signature"}`
- [ ] Logs show signature verification failure

## Final Verification

### All Systems Operational
- [ ] Health check: ✅
- [ ] Git ingestion: ✅
- [ ] Repository storage: ✅
- [ ] Webhooks configured: ✅
- [ ] Auto-sync working: ✅
- [ ] Incremental updates: ✅
- [ ] Rate limiting: ✅
- [ ] Error handling: ✅

### Performance Metrics Met
- [ ] Initial clone: < 20 seconds
- [ ] Incremental update: < 2 seconds
- [ ] Webhook response: < 3 seconds
- [ ] Token savings: 99% vs file upload

## Troubleshooting

### If Health Check Fails
1. Check Cloud Run logs: `gcloud run services logs tail code-index-mcp-dev`
2. Verify service is deployed: `gcloud run services list`
3. Check for startup errors in logs

### If Git Ingestion Fails
1. Check logs for Git errors
2. Verify GCS bucket exists and is accessible
3. Test with public repository first
4. Check auth token if using private repo

### If Webhook Returns 401
1. Verify webhook secret matches what was configured
2. Re-run `./setup-webhook-secrets.sh` to regenerate
3. Update webhook configuration in Git platform
4. Re-deploy: `./deploy.sh dev`

### If Auto-Sync Doesn't Work
1. Check webhook delivery in Git platform
2. Verify webhook response is 200 OK
3. Check Cloud Run logs for background sync errors
4. Verify webhook secret is correctly configured

## Cost Monitoring

### Expected Monthly Costs
- Cloud Run: $6-25 (serverless, scales to zero)
- Cloud Storage: $1-5 (depends on repo sizes)
- Secret Manager: $0.06 (3 secrets)
- Cloud Scheduler: $0.10 (1 cleanup job)
- **Total: ~$7-30/month**

### Monitor Costs
```bash
# View current month's costs
gcloud billing accounts list
gcloud billing projects describe YOUR-PROJECT-ID
```

## Post-Deployment

### Configure Claude Desktop (Optional)
- [ ] Add service URL to `claude_desktop_config.json`
- [ ] Test connection from Claude Desktop
- [ ] Verify MCP tools are available

### Add More Repositories
- [ ] Ingest additional repositories via `ingest_code_from_git`
- [ ] Configure webhooks for each repository
- [ ] Verify auto-sync for all repositories

### Enable AlloyDB Semantic Search (Optional)
- [ ] Run `./setup-alloydb.sh dev`
- [ ] Re-deploy with `./deploy.sh dev --with-alloydb`
- [ ] Test semantic search tools

### Setup Production (Optional)
- [ ] Generate production webhook secrets
- [ ] Deploy to production: `./deploy.sh prod --require-auth`
- [ ] Configure production webhooks
- [ ] Set up monitoring and alerts

## Success! 🎉

All tests passed! Your Git-Sync deployment is fully operational.

**Next Steps:**
1. Share service URL with your team
2. Configure Claude Desktop clients
3. Start using semantic code search
4. Monitor usage and costs

**Support:**
- Documentation: [GIT_SYNC_DEPLOYMENT_GUIDE.md](GIT_SYNC_DEPLOYMENT_GUIDE.md)
- Issues: Report via GitHub issues
- Logs: `gcloud run services logs tail code-index-mcp-dev`

---

**Deployment Date:** _____________
**Deployed By:** _____________
**Service URL:** _____________
