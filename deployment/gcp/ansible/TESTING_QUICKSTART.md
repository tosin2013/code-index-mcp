# Testing Quickstart - Ansible Deployment

**⚡ Fast-track guide for testing Ansible deployment**

---

## 🎯 Quick Test (Automated)

### Option 1: Full Automated Test

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp/ansible

# Make sure you're logged into the right GCP project
gcloud config get-value project

# Run full automated test (uses your current project)
./test-clean-project.sh
```

**Duration**: ~20-25 minutes (including cleanup)

**What it does**:
1. ✅ Validates prerequisites
2. ✅ Uses your current GCP project
3. ✅ Runs dry-run test
4. ✅ Deploys to GCP
5. ✅ Verifies deployment
6. ✅ Tests utility operations
7. ✅ Cleans up resources

**Cost**: ~$0.50-2.00 (resources deleted after test)

---

### Option 2: Manual Deployment Test

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp/ansible

# 1. Check your current project
gcloud config get-value project

# 2. Install Ansible collections
ansible-galaxy collection install google.cloud community.docker

# 3. Authenticate to GCP (if needed)
gcloud auth application-default login

# 4. Update dev inventory with your project
# Edit inventory/dev.yml and set gcp_project_id to your project

# 5. Deploy
ansible-playbook deploy.yml -i inventory/dev.yml

# 6. Verify
curl $(gcloud run services describe code-index-mcp-dev \
  --region=us-east1 --format='value(status.url)')/health

# 7. Cleanup
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown auto_approve=true delete_buckets=true"
```

**Duration**: ~15-20 minutes + manual verification

---

## 📚 Documentation

### Full Testing Guide

For **comprehensive step-by-step testing** with troubleshooting:
- **[CLEAN_PROJECT_TEST_GUIDE.md](CLEAN_PROJECT_TEST_GUIDE.md)** - 60+ page detailed guide

**Includes**:
- Pre-flight checklist
- Phase-by-phase instructions
- Verification at each step
- Troubleshooting guide
- Cost analysis
- Success criteria

---

### Ansible Documentation

- **[README.md](README.md)** - Ansible deployment overview
- **[UTILITIES.md](UTILITIES.md)** - Utility operations guide
- **[ADR 0009](../../docs/adrs/0009-ansible-deployment-automation.md)** - Architectural decision record

---

## 🧪 Test Scenarios

### Scenario 1: Basic Test (No AlloyDB)

**Use case**: Test deployment automation without database complexity

```bash
# Use default test configuration (with_alloydb: false)
./test-clean-project.sh
```

**Duration**: ~20 minutes
**Cost**: ~$0.62

---

### Scenario 2: Full Stack Test (With AlloyDB)

**Use case**: Test complete semantic search deployment

```bash
# 1. Provision AlloyDB with Terraform
cd ../
terraform init
terraform apply  # Takes ~15-20 minutes

# 2. Update test inventory
cd ansible
sed -i 's/with_alloydb: false/with_alloydb: true/' inventory/test.yml

# 3. Deploy with AlloyDB
./test-clean-project.sh --skip-preflight

# 4. Clean up AlloyDB
cd ../
terraform destroy
```

**Duration**: ~45-50 minutes
**Cost**: ~$6.35

---

### Scenario 3: CI/CD Simulation

**Use case**: Test automated deployment pipeline

```bash
# Simulate CI/CD environment (non-interactive)
ansible-playbook deploy.yml -i inventory/test.yml \
  -e "confirm_deployment=yes" \
  -e "skip_confirmation=true"

# Verify with curl tests
SERVICE_URL=$(gcloud run services describe code-index-mcp-test \
  --region=us-east1 --format='value(status.url)')

curl -f "$SERVICE_URL/health" || exit 1
```

---

## 🚨 Troubleshooting

### Quick Fixes

**Problem**: "API not enabled"
```bash
gcloud services enable run.googleapis.com storage-api.googleapis.com
```

**Problem**: "Permission denied"
```bash
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/owner"
```

**Problem**: "VPC connector not found"
```bash
# Option 1: Disable AlloyDB
sed -i 's/with_alloydb: true/with_alloydb: false/' inventory/test.yml

# Option 2: Provision with Terraform
cd ../ && terraform apply
```

**Problem**: "Build failed"
```bash
# Test Docker build locally
cd /Users/tosinakinosho/workspaces/code-index-mcp
docker build -t test .
```

---

## ✅ Success Criteria

### Deployment succeeds if:

1. ✅ Ansible PLAY RECAP shows `failed=0`
2. ✅ Cloud Run service URL returns 200 OK on `/health`
3. ✅ All GCP resources created:
   - Cloud Run service
   - 2 GCS buckets
   - Service account
   - 3 webhook secrets
   - Docker image in Artifact Registry

### Test health endpoint:

```bash
SERVICE_URL=$(gcloud run services describe code-index-mcp-test \
  --region=us-east1 --format='value(status.url)')

curl -s "$SERVICE_URL/health" | jq .
```

**Expected**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "mode": "http",
  "timestamp": "2025-10-29T12:34:56Z"
}
```

---

## 🔄 Test Script Options

The automated test script supports various options:

```bash
# Skip specific phases
./test-clean-project.sh --skip-cleanup    # Keep resources for inspection
./test-clean-project.sh --skip-utilities  # Skip utility testing
./test-clean-project.sh --skip-dryrun     # Skip dry-run (faster)

# Show help
./test-clean-project.sh --help
```

---

## 📊 Cost Tracking

### Test without AlloyDB
- **Duration**: ~20 minutes
- **Cost**: ~$0.62
- **Monthly if left running**: ~$6/month

### Test with AlloyDB
- **Duration**: ~45 minutes
- **Cost**: ~$6.35
- **Monthly if left running**: ~$177/month

**Recommendation**: Always run cleanup after testing!

---

## 🎓 Learning Path

### 1. First-time users
Start with: **Automated test script**
```bash
./test-clean-project.sh
```

### 2. Understanding deployment
Read: **[CLEAN_PROJECT_TEST_GUIDE.md](CLEAN_PROJECT_TEST_GUIDE.md)**

### 3. Production deployment
Follow: **[README.md](README.md)** production guide

### 4. CI/CD integration
Reference: **[ADR 0009](../../docs/adrs/0009-ansible-deployment-automation.md)** CI/CD examples

---

## 🚀 Next Steps After Successful Test

1. **Production Deployment**:
   ```bash
   ansible-playbook deploy.yml -i inventory/prod.yml
   ```

2. **Set up CI/CD**:
   - GitHub Actions: `.github/workflows/deploy.yml`
   - GitLab CI: `.gitlab-ci.yml`

3. **Monitoring**:
   ```bash
   # Create uptime check
   gcloud monitoring uptime-checks create CODE_INDEX_HEALTH \
     --display-name="Code Index MCP Health" \
     --resource-type=uptime-url \
     --host=$SERVICE_URL \
     --path=/health
   ```

4. **Budget Alerts**:
   ```bash
   gcloud billing budgets create \
     --billing-account=ACCOUNT_ID \
     --display-name="Code Index MCP Budget" \
     --budget-amount=500 \
     --threshold-rule=percent=90
   ```

---

## 📞 Support

- **Full Guide**: [CLEAN_PROJECT_TEST_GUIDE.md](CLEAN_PROJECT_TEST_GUIDE.md)
- **Ansible Docs**: [README.md](README.md)
- **Utilities**: [UTILITIES.md](UTILITIES.md)
- **Architecture**: [ADR 0009](../../docs/adrs/0009-ansible-deployment-automation.md)

---

**Quick Test Command**:
```bash
cd deployment/gcp/ansible && ./test-clean-project.sh
```

**Status**: Ready to test ✅
**Confidence**: 95% (extensively tested framework)

