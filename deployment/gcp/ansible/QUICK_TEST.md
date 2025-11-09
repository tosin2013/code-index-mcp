# Quick Test - Use Your Current Project

**⚡ Fastest way to test Ansible deployment in your current GCP project**

---

## 🚀 One-Command Test

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp/ansible

# Check your current project
gcloud config get-value project

# Run test (uses your current project automatically)
./test-clean-project.sh
```

**That's it!** The script will:
1. ✅ Use your current logged-in GCP project
2. ✅ Deploy everything (Cloud Run, buckets, secrets, etc.)
3. ✅ Verify it all works
4. ✅ Clean up resources automatically

**Duration**: ~20-25 minutes  
**Cost**: ~$0.50-2.00 (deleted after test)

---

## 📝 What Gets Created & Deleted

### Created During Test
- Cloud Run service: `code-index-mcp-test`
- GCS buckets: `code-index-projects-test-*`, `code-index-git-repos-test-*`
- Service account: `code-index-cloudrun-test@*.iam.gserviceaccount.com`
- Webhook secrets: 3 secrets in Secret Manager
- Docker image in Artifact Registry

### Automatically Deleted After Test
- ✅ Cloud Run service
- ✅ GCS buckets (with all data)
- ✅ Docker images
- ✅ Webhook secrets
- ✅ Service account
- ✅ Artifact Registry repository

**Nothing left behind!** (unless you use `--skip-cleanup`)

---

## ✅ Success Looks Like This

At the end, you'll see:

```
[2025-10-29 12:34:56] ✅ Pre-flight checks passed
[2025-10-29 12:35:00] ✅ Using project: tosinscloud
[2025-10-29 12:40:30] ✅ Deployment completed successfully
[2025-10-29 12:45:00] ✅ Health endpoint responding
[2025-10-29 12:45:05] ✅ SSE endpoint responding
[2025-10-29 12:45:10] ✅ Service account created
[2025-10-29 12:45:15] ✅ GCS buckets created (2)
[2025-10-29 12:45:20] ✅ Webhook secrets created (3)
[2025-10-29 12:45:25] ✅ Deployment verification passed
[2025-10-29 12:50:00] ✅ API key generation successful
[2025-10-29 12:55:00] ✅ Cleanup completed
[2025-10-29 12:55:05] ✅ All tests passed successfully!
```

---

## 🚨 If Something Goes Wrong

### "API not enabled"
```bash
gcloud services enable run.googleapis.com storage-api.googleapis.com
```

### "Permission denied"
```bash
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/owner"
```

### "Build failed"
```bash
# Test Docker build locally first
cd /Users/tosinakinosho/workspaces/code-index-mcp
docker build -t test .
```

---

## 🎯 After Successful Test

### Keep Resources for Testing
```bash
# Skip cleanup phase
./test-clean-project.sh --skip-cleanup
```

Then manually test:
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe code-index-mcp-test \
  --region=us-east1 --format='value(status.url)')

# Test health
curl "$SERVICE_URL/health"

# Test SSE
curl -N -H "Accept: text/event-stream" "$SERVICE_URL/sse"
```

Cleanup later:
```bash
ansible-playbook utilities.yml -i inventory/test.yml \
  -e "operation=teardown auto_approve=true delete_buckets=true"
```

---

## 📊 What Gets Tested

| Component | Test |
|-----------|------|
| **Ansible** | ✅ Playbook execution, idempotency |
| **GCP APIs** | ✅ Enablement, authentication |
| **Cloud Run** | ✅ Service deployment, health checks |
| **Docker** | ✅ Build, push to registry |
| **Storage** | ✅ Bucket creation, lifecycle policies |
| **IAM** | ✅ Service account, roles |
| **Secrets** | ✅ Secret Manager integration |
| **Networking** | ✅ HTTPS endpoints, SSE |

---

## 🎓 Your Current Project Info

Check what will be used:

```bash
# Project ID
gcloud config get-value project

# Account
gcloud config get-value account

# Region (hardcoded to us-east1 in test)
echo "us-east1"

# Billing status
gcloud billing projects describe $(gcloud config get-value project) \
  --format='value(billingEnabled)'
```

---

## ⏱️ Timeline

```
0:00  - Start test
0:01  - Check prerequisites ✅
0:02  - Confirm project ✅
0:03  - Dry-run test (no charges)
0:05  - Start deployment
0:07  - Enable APIs
0:10  - Build Docker image
0:15  - Deploy Cloud Run
0:18  - Verify deployment ✅
0:20  - Test utilities ✅
0:22  - Cleanup resources
0:25  - Done! ✅
```

---

## 📝 Log File

All output is saved to:
```
deployment/gcp/ansible/test-deployment-TIMESTAMP.log
```

Review it if anything fails:
```bash
cat test-deployment-*.log | grep -E "ERROR|FAIL"
```

---

## 🔄 Test Options

```bash
# Full test (default)
./test-clean-project.sh

# Skip cleanup (keep resources)
./test-clean-project.sh --skip-cleanup

# Skip dry-run (faster)
./test-clean-project.sh --skip-dryrun

# Skip utilities test
./test-clean-project.sh --skip-utilities

# Show help
./test-clean-project.sh --help
```

---

## 💰 Cost Breakdown

| Resource | Duration | Cost |
|----------|----------|------|
| API calls | 1 min | $0.00 |
| Cloud Build | 5-8 min | $0.50 |
| Cloud Run | 15 min | $0.10 |
| Storage | 20 min | $0.02 |
| **Total** | **~25 min** | **~$0.62** |

**After cleanup**: $0.00/month (nothing left running)

---

## 🎯 Bottom Line

**To test right now:**

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp/ansible
./test-clean-project.sh
```

**Expected result**: Everything deploys, verifies, and cleans up automatically in ~25 minutes.

**Your project**: Used as-is (the script detects it automatically)

**Risk**: Very low (everything is deleted after test)

---

**Ready to run? Just execute the command above!** 🚀







