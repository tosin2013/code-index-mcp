# Deployment Test Guide - Google Cloud Run

**Project**: tosinscloud
**Region**: us-east1
**Environment**: dev (recommended for first deployment)
**Date**: October 24, 2025

---

## Pre-Deployment Checklist

Before running `./deploy.sh`, verify:

- [x] gcloud CLI installed and authenticated
- [x] Project configured: `tosinscloud`
- [x] Scripts executable (`chmod +x *.sh`)
- [ ] Billing enabled on project
- [ ] Required APIs will be auto-enabled (or manually enable)

### Manual API Enable (Optional - deploy.sh does this)

```bash
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    cloudscheduler.googleapis.com \
    --project=tosinscloud
```

---

## Deployment Steps

### Step 1: Deploy to Development

```bash
cd deployment/gcp
./deploy.sh dev
```

**Expected Output**:
```
[INFO] Starting deployment to Google Cloud Run
[INFO] Checking prerequisites...
[SUCCESS] Prerequisites checked
[INFO] Project ID: tosinscloud
[INFO] Environment: dev
[INFO] Region: us-east1
[INFO] Enabling required GCP APIs...
[INFO] Enabling run.googleapis.com...
...
[SUCCESS] Deployed to Cloud Run
[SUCCESS] Service URL: https://code-index-mcp-dev-xxxxx-uc.a.run.app
```

**Time**: ~5-10 minutes (first time)
**Cost**: ~$0 (Cloud Build free tier: 120 build-minutes/day)

### Step 2: Test Health Endpoint

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe code-index-mcp-dev \
    --region=us-east1 \
    --format="value(status.url)")

echo "Service URL: $SERVICE_URL"

# Test health
curl $SERVICE_URL/health
```

**Expected**: HTTP 200 OK with health status

### Step 3: Create API Key

```bash
# Create API key for yourself
./setup-secrets.sh YOUR_NAME read,write

# Copy the API key shown (starts with ci_)
API_KEY="ci_your_generated_key_here"
```

**Expected Output**:
```
[SUCCESS] API Key Created Successfully

User ID:     YOUR_NAME
Permissions: read,write
Secret Name: code-index-api-key-YOUR_NAME

API Key (copy this - it won't be shown again):
ci_0123456789abcdef...
```

### Step 4: Test with API Key

```bash
# Set your API key
API_KEY="ci_your_generated_key_here"

# Test with X-API-Key header
curl -H "X-API-Key: $API_KEY" $SERVICE_URL/tools

# Test with Bearer token
curl -H "Authorization: Bearer $API_KEY" $SERVICE_URL/tools
```

**Expected**: JSON response with available MCP tools

### Step 5: View Logs

```bash
# Tail logs
gcloud run services logs tail code-index-mcp-dev --region=us-east1

# Filter for your requests
gcloud run services logs tail code-index-mcp-dev \
    --region=us-east1 \
    --log-filter="httpRequest.path=/tools"
```

### Step 6: Test Storage Integration

```bash
# Check if bucket was created
gsutil ls gs://code-index-projects-tosinscloud

# Check lifecycle rules
gsutil lifecycle get gs://code-index-projects-tosinscloud

# Test file upload (via API)
# This requires MCP client integration - see WEEK1_COMPLETION_REPORT.md
```

---

## Verification Checklist

After deployment, verify:

- [ ] Cloud Run service is running
  ```bash
  gcloud run services describe code-index-mcp-dev --region=us-east1
  ```

- [ ] GCS bucket exists with lifecycle rules
  ```bash
  gsutil ls gs://code-index-projects-tosinscloud
  gsutil lifecycle get gs://code-index-projects-tosinscloud
  ```

- [ ] Secrets created in Secret Manager
  ```bash
  gcloud secrets list --filter="labels.service=code-index-mcp"
  ```

- [ ] Cloud Scheduler job created
  ```bash
  gcloud scheduler jobs describe code-index-cleanup-dev --location=us-east1
  ```

- [ ] Health endpoint returns 200
  ```bash
  curl -f $SERVICE_URL/health
  ```

- [ ] Authentication works with API key
  ```bash
  curl -H "X-API-Key: $API_KEY" $SERVICE_URL/tools
  ```

---

## Common Issues & Solutions

### Issue: "Permission denied" during deployment

**Solution**:
```bash
# Check current account
gcloud auth list

# Re-authenticate if needed
gcloud auth login

# Verify IAM permissions
gcloud projects get-iam-policy tosinscloud \
    --flatten="bindings[].members" \
    --filter="bindings.members:$(gcloud config get-value account)"
```

**Required Roles**:
- `roles/run.admin`
- `roles/storage.admin`
- `roles/secretmanager.admin`
- `roles/cloudscheduler.admin`
- `roles/cloudbuild.builds.editor`

### Issue: Build fails with "dependency resolution error"

**Solution**:
```bash
# Check pyproject.toml is valid
cd ../..
python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"

# Test build locally
docker build -t test-build -f deployment/gcp/Dockerfile .
```

### Issue: Service starts but health check fails

**Solution**:
```bash
# Check logs for errors
gcloud run services logs tail code-index-mcp-dev \
    --region=us-east1 \
    --log-filter="severity>=ERROR"

# Check if MCP_TRANSPORT is set
gcloud run services describe code-index-mcp-dev \
    --region=us-east1 \
    --format="value(spec.template.spec.containers[0].env)"
```

### Issue: "Bucket already exists" error

**Solution**:
```bash
# Bucket names are globally unique across all GCP projects
# The script uses: code-index-projects-{project-id}
# This should be unique, but if not, edit deploy.sh line 19:

BUCKET_NAME="code-index-projects-tosinscloud-unique-suffix"
```

### Issue: Cold start is slow (>10 seconds)

**Expected**: First request after idle may take 5-10 seconds

**Solutions**:
1. Set min-instances=1 (costs ~$10/month):
   ```bash
   gcloud run services update code-index-mcp-dev \
       --region=us-east1 \
       --min-instances=1
   ```

2. Or accept cold starts for dev (scale-to-zero saves money)

---

## Cost Monitoring

### View Current Costs

```bash
# View billing
gcloud billing accounts list

# View project costs (Cloud Console)
# https://console.cloud.google.com/billing/tosinscloud
```

### Set Budget Alert

```bash
# Get billing account ID
BILLING_ACCOUNT=$(gcloud billing projects describe tosinscloud \
    --format="value(billingAccountName)")

# Create $20/month budget with alerts
gcloud billing budgets create \
    --billing-account=$BILLING_ACCOUNT \
    --display-name="Code Index MCP Dev Budget" \
    --budget-amount=20 \
    --threshold-rule=percent=50 \
    --threshold-rule=percent=100
```

---

## Cleanup (When Done Testing)

### Option 1: Keep Storage, Delete Service

```bash
./destroy.sh dev
```

This deletes:
- ✅ Cloud Run service
- ✅ Container images
- ✅ Cloud Scheduler job
- ❌ GCS bucket (keeps data)

**Cost after**: ~$0.50-1/month (storage only)

### Option 2: Delete Everything

```bash
./destroy.sh dev --delete-bucket
```

This deletes:
- ✅ Cloud Run service
- ✅ Container images
- ✅ Cloud Scheduler job
- ✅ GCS bucket (**ALL DATA LOST**)

**Cost after**: $0/month

---

## Next Steps

After successful deployment:

1. **Week 2, Task 4**: Implement automatic cleanup logic
   - `src/code_index_mcp/admin/cleanup.py`
   - Cloud Scheduler integration

2. **Week 2, Task 5**: Testing & Documentation
   - End-to-end integration tests
   - User onboarding guide
   - Performance benchmarks

3. **Production Deployment**:
   ```bash
   ./deploy.sh prod
   ```

---

## Success Criteria ✅

**Task 3 is complete when:**

- [x] Dockerfile created (multi-stage, optimized)
- [x] deploy.sh created (automated deployment)
- [x] destroy.sh created (cleanup script)
- [x] lifecycle.json created (GCS policies)
- [x] setup-secrets.sh created (API key provisioning)
- [ ] **Test deployment succeeds** ← **YOU ARE HERE**
- [ ] Health check passes
- [ ] API authentication works
- [ ] Storage bucket created with lifecycle
- [ ] Scheduler job created

**Run the deployment now to complete Task 3!**

```bash
cd deployment/gcp
./deploy.sh dev
```

---

**Estimated Deployment Time**: 5-10 minutes
**Estimated Cost**: $0 (free tier) to $2.50/month (dev usage)
**Confidence**: 88% (scripts validated, ready for real deployment)
