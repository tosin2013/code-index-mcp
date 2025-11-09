# Deployment Lifecycle Guide

**For New Users**: This guide demonstrates the complete repeatable deployment lifecycle for Code Index MCP on Google Cloud Platform.

## Table of Contents

1. [Quick Start (Automated Deployment)](#quick-start-automated-deployment)
2. [Prerequisites](#prerequisites)
3. [Security Setup (Pre-commit Hooks)](#security-setup-pre-commit-hooks)
4. [Initial Deployment](#initial-deployment)
5. [Verification](#verification)
6. [Using the Deployment](#using-the-deployment)
7. [Cleanup/Teardown](#cleanupteardown)
8. [Redeployment (Proving Repeatability)](#redeployment-proving-repeatability)
9. [Cost Management](#cost-management)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start (Automated Deployment)

**NEW**: We now provide a fully automated end-to-end deployment script that handles the entire deployment lifecycle!

### One-Command Deployment

```bash
# Navigate to the deployment directory
cd deployment/gcp

# Run the automated deployment script
./deploy-lifecycle.sh --user-email your@email.com
```

That's it! The script will:
- ✅ Check all prerequisites (gcloud, ansible, terraform, etc.)
- ✅ Verify GCP authentication and project setup
- ✅ Set up pre-commit hooks for security
- ✅ Deploy the complete infrastructure (AlloyDB, Cloud Run, Storage)
- ✅ Verify deployment health
- ✅ Generate your API key
- ✅ Provide Claude Desktop configuration

**Deployment time**: ~30-40 minutes (fully automated)

### Script Options

```bash
./deploy-lifecycle.sh [OPTIONS]

Options:
  --environment ENV    Deployment environment (dev/staging/prod) [default: dev]
  --project-id ID      GCP project ID [uses gcloud config if not specified]
  --region REGION      GCP region [default: us-east1]
  --user-email EMAIL   Email for API key generation [required]
  --skip-hooks         Skip pre-commit hooks setup
  --auto-approve       Skip confirmation prompts (use with caution)
  --help               Show detailed help
```

### Examples

```bash
# Basic deployment to dev environment
./deploy-lifecycle.sh --user-email admin@example.com

# Deploy to staging with specific project
./deploy-lifecycle.sh \
  --environment staging \
  --project-id my-gcp-project \
  --user-email admin@example.com

# Fully automated (no prompts) - CI/CD use case
./deploy-lifecycle.sh \
  --user-email ci@example.com \
  --auto-approve
```

### What the Script Does

The automated script executes all steps from this guide:

1. **Prerequisites Check**: Verifies all required tools are installed
2. **GCP Configuration**: Validates authentication and project setup
3. **Security Setup**: Installs and tests pre-commit hooks
4. **Infrastructure Deployment**: Runs Ansible playbook to deploy:
   - AlloyDB cluster and instance
   - Cloud Run service
   - VPC connector
   - Storage buckets
   - Secrets and IAM
5. **Verification**: Health checks on all deployed resources
6. **API Key Generation**: Creates and securely stores API key
7. **Configuration Output**: Provides ready-to-use Claude Desktop config

### Manual Deployment

If you prefer to understand each step or customize the deployment, continue reading the detailed manual deployment sections below.

---

## Prerequisites

### Required Tools

```bash
# Install required tools
brew install pre-commit gitleaks ansible terraform
```

### Required Software Versions

- **Python**: 3.11+
- **Ansible**: 2.14+
- **Terraform**: 1.5+
- **gcloud CLI**: Latest
- **Pre-commit**: 3.0+
- **Gitleaks**: 8.0+

### GCP Project Setup

```bash
# Authenticate with GCP
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable billing (required for deployment)
# Visit: https://console.cloud.google.com/billing
```

---

## Security Setup (Pre-commit Hooks)

**CRITICAL**: Set up pre-commit hooks BEFORE making any commits to prevent credential leaks.

### 1. Install Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install the hooks
pre-commit install
```

### 2. Verify Gitleaks Configuration

The repository includes:
- `.pre-commit-config.yaml` - Pre-commit hook configuration
- `.gitleaks.toml` - Secret detection rules
- `.gitignore` - Credential exclusions

### 3. Test the Hooks

```bash
# Run hooks on all files
pre-commit run --all-files

# Expected output:
# Gitleaks secret detection....................................Passed
# Black code formatter.........................................Passed
# isort import sorting.........................................Passed
# check-yaml...................................................Passed
# Terraform format.............................................Passed
# Bandit security checks.......................................Passed
```

### 4. What's Protected

The pre-commit hooks detect and block:
- ✅ MCP API keys (ci_* prefix)
- ✅ Database connection strings
- ✅ GCP service account keys
- ✅ Webhook secrets (GitHub, GitLab, Gitea)
- ✅ Private keys (.pem, .key files)
- ✅ Environment variables (.env files)

---

## Initial Deployment

### 1. Navigate to Ansible Directory

```bash
cd deployment/gcp/ansible
```

### 2. Review Deployment Configuration

```bash
# View the inventory for dev environment
cat inventory/dev.yml

# Key settings:
# - project_id: Your GCP project
# - environment: dev
# - region: us-east1
# - enable_alloydb: true
```

### 3. Deploy Full Stack

```bash
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes"
```

**What gets deployed:**

1. **Prerequisites**
   - Enable required GCP APIs (Cloud Run, AlloyDB, Secret Manager, etc.)
   - Create Artifact Registry repository
   - Configure Docker authentication

2. **AlloyDB (Vector Database)**
   - Terraform provisions AlloyDB cluster (~20-30 minutes)
   - Create database instance (2 vCPU, 16 GB RAM)
   - Set up VPC connector for private networking
   - Apply database schema (users, projects, code_chunks tables)

3. **Storage**
   - Create GCS buckets for projects and Git repositories
   - Configure lifecycle policies (auto-cleanup after 90 days)

4. **Service Account**
   - Create service account with least privilege
   - Grant roles: Secret Manager, Storage, AI Platform, AlloyDB Client

5. **Webhook Secrets**
   - Generate secrets for GitHub, GitLab, Gitea webhooks
   - Store in Secret Manager

6. **Docker Image**
   - Build container image using Cloud Build
   - Push to Artifact Registry

7. **Cloud Run Service**
   - Deploy MCP server with HTTP/SSE transport
   - Configure environment variables
   - Set up authentication
   - Allocate resources (1 vCPU, 2 GB RAM)

**Deployment Time**: ~25-35 minutes (AlloyDB provisioning is the slowest part)

### 4. Monitor Deployment Progress

The playbook provides real-time feedback:

```
PLAY [Deploy Code Index MCP Server to Google Cloud Run] ************************

TASK [Display deployment information] ******************************************
ok: [localhost] =>
  msg:
  - ===================================
  - Code Index MCP Deployment
  - ===================================
  - 'Project: YOUR_PROJECT'
  - 'Environment: dev'
  - 'Region: us-east1'
  - ===================================

[... Terraform provisioning AlloyDB ...]
[... Building Docker image ...]
[... Deploying Cloud Run service ...]

TASK [code-index-mcp : Display deployment success] *****************************
ok: [localhost] =>
  msg:
  - ✅ Cloud Run service deployed successfully
  - 'Service: code-index-mcp-dev'
  - 'URL: https://code-index-mcp-dev-XXXXX.us-east1.run.app'

PLAY RECAP *********************************************************************
localhost                  : ok=79   changed=16   unreachable=0    failed=0
```

---

## Verification

### 1. Check Service Health

```bash
# Test the SSE endpoint (should return HTTP 200)
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" \
  "https://code-index-mcp-dev-XXXXX.us-east1.run.app/sse"

# Expected: HTTP Status: 200
```

### 2. Verify AlloyDB

```bash
# Check AlloyDB cluster status
gcloud alloydb clusters describe code-index-cluster-dev \
  --region=us-east1 --project=YOUR_PROJECT

# Expected: state: READY
```

### 3. Verify Database Schema

```bash
cd deployment/gcp/ansible
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=verify_schema"
```

### 4. Generate Test API Key

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key" \
  -e "user_email=test@example.com"

# Save the API key (ci_XXXX...) for testing
```

---

## Using the Deployment

### Configure Claude Desktop

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://code-index-mcp-dev-XXXXX.us-east1.run.app/sse",
      "transport": "sse",
      "headers": {
        "X-API-Key": "ci_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Test the MCP Tools

Use Claude Desktop to test:

1. **Git Ingestion** (Recommended):
   ```
   ingest_code_from_git(git_url="https://github.com/your/repo")
   ```

2. **Semantic Search**:
   ```
   semantic_search_code(query="authentication logic", language="python")
   ```

---

## Cleanup/Teardown

**WARNING**: This deletes all deployed resources and data!

### Full Teardown (Recommended for Testing)

```bash
cd deployment/gcp/ansible

# Step 1: Delete Cloud Run service and GCS buckets
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e '{"operation": "teardown", "auto_approve": true, "delete_buckets": true}'

# Step 2: Destroy AlloyDB infrastructure with Terraform
cd ..  # Go to deployment/gcp/
terraform destroy -auto-approve \
  -var="project_id=YOUR_PROJECT" \
  -var="environment=dev" \
  -var="region=us-east1"
```

**What gets deleted:**

1. **Ansible Teardown**:
   - Cloud Run service
   - Container images
   - Cloud Scheduler cleanup jobs
   - GCS buckets (if delete_buckets=true)

2. **Terraform Destroy**:
   - AlloyDB cluster and instance
   - VPC connector
   - Network and subnet
   - Secrets (AlloyDB password)

**Teardown Time**: ~5-10 minutes

### Verify Complete Cleanup

```bash
# Check Cloud Run services (should be empty)
gcloud run services list --region=us-east1

# Check AlloyDB clusters (should be empty)
gcloud alloydb clusters list --region=us-east1

# Check buckets (should be deleted)
gsutil ls gs://code-index-projects-YOUR_PROJECT/
gsutil ls gs://code-index-git-repos-YOUR_PROJECT/
```

**Expected**: All commands return no resources or "Not found" errors.

---

## Redeployment (Proving Repeatability)

This demonstrates the deployment is **fully repeatable** for new users.

### Complete Lifecycle Test

```bash
# 1. Ensure clean state (run cleanup if needed)
cd deployment/gcp/ansible
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e '{"operation": "teardown", "auto_approve": true, "delete_buckets": true}'

cd ..
terraform destroy -auto-approve \
  -var="project_id=YOUR_PROJECT" \
  -var="environment=dev" \
  -var="region=us-east1"

# 2. Wait for cleanup to complete (~5 minutes)

# 3. Redeploy from scratch
cd ansible
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes"

# 4. Verify deployment (~25-35 minutes)
# - Check service health
# - Generate new API key
# - Test semantic search

# ✅ Success: Deployment is repeatable!
```

---

## Cost Management

### Monthly Cost Breakdown (Dev Environment)

| Resource | Cost/Month |
|----------|-----------|
| AlloyDB (2 vCPU, 16 GB) | $164 |
| Cloud Run (1 vCPU, 2 GB) | $20-40 |
| Storage (100 GB) | $2-5 |
| VPC Connector | $7 |
| Network | $5 |
| **Total** | **~$200-220/month** |

### Cost Optimization

1. **Auto-scale to Zero**:
   - Cloud Run scales to 0 when idle (no requests)
   - Only pay for actual usage

2. **Automatic Cleanup**:
   - Cloud Scheduler runs daily cleanup
   - Deletes projects inactive >90 days
   - Configurable retention in `lifecycle-policy.json`

3. **Stop AlloyDB When Not Needed**:
   ```bash
   # Stop AlloyDB instance (saves ~$164/month)
   gcloud alloydb instances update code-index-primary-dev \
     --cluster=code-index-cluster-dev \
     --region=us-east1 \
     --availability-type=ZONAL
   ```

4. **Complete Teardown** (saves 100%):
   - Use teardown procedure above
   - Redeploy when needed (~30 minutes)

---

## Troubleshooting

### Deployment Issues

#### Error: Terraform State Locked

```bash
# Force unlock (only if safe)
cd deployment/gcp
terraform force-unlock LOCK_ID
```

#### Error: AlloyDB Provisioning Timeout

```bash
# Check AlloyDB status
gcloud alloydb clusters describe code-index-cluster-dev --region=us-east1

# If stuck in CREATING state for >30 minutes:
# 1. Cancel the deployment
# 2. Run terraform destroy
# 3. Retry deployment
```

#### Error: API Not Enabled

```bash
# Manually enable required APIs
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  alloydb.googleapis.com \
  aiplatform.googleapis.com
```

### Cleanup Issues

#### Error: Terraform Destroy Fails

```bash
# Common issue: Resources still in use
# Solution: Run Ansible teardown FIRST, then Terraform destroy

# Step 1: Delete Cloud Run
cd deployment/gcp/ansible
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e '{"operation": "teardown", "auto_approve": true}'

# Step 2: Wait 2 minutes for cleanup

# Step 3: Destroy infrastructure
cd ..
terraform destroy -auto-approve \
  -var="project_id=YOUR_PROJECT" \
  -var="environment=dev" \
  -var="region=us-east1"
```

#### Error: Bucket Not Empty

```bash
# Force delete bucket contents
gsutil -m rm -r gs://code-index-projects-YOUR_PROJECT/**
gsutil -m rm -r gs://code-index-git-repos-YOUR_PROJECT/**

# Then retry teardown
```

### Pre-commit Hook Issues

#### Error: check-yaml Failed

```bash
# Common issue: Invalid YAML syntax
# Solution: Fix YAML file or skip hook temporarily
SKIP=check-yaml git commit -m "message"
```

#### Error: Gitleaks False Positive

Add the pattern to `.gitleaks.toml` allowlist:

```toml
[allowlist]
regexes = [
    '''your_false_positive_pattern''',
]
```

Then re-run:
```bash
pre-commit run gitleaks --all-files
```

---

## Quick Reference

### Deployment Commands

```bash
# Deploy
cd deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes"

# Teardown
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e '{"operation": "teardown", "auto_approve": true, "delete_buckets": true}'
cd .. && terraform destroy -auto-approve \
  -var="project_id=YOUR_PROJECT" -var="environment=dev" -var="region=us-east1"

# Generate API Key
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key" -e "user_email=USER@example.com"

# Verify Schema
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=verify_schema"

# Query Database
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=query_database" -e "query=SELECT COUNT(*) FROM code_chunks"
```

### Service URLs

- **Cloud Run Service**: `https://code-index-mcp-dev-XXXXX.us-east1.run.app`
- **SSE Endpoint**: `https://code-index-mcp-dev-XXXXX.us-east1.run.app/sse`
- **GCP Console**: `https://console.cloud.google.com/run?project=YOUR_PROJECT`
- **AlloyDB Console**: `https://console.cloud.google.com/alloydb?project=YOUR_PROJECT`

### Security Checklist

- [ ] Pre-commit hooks installed (`pre-commit install`)
- [ ] Gitleaks tested (`pre-commit run gitleaks --all-files`)
- [ ] No credentials in `.gitignore` excluded files
- [ ] API keys stored in Secret Manager (never in code)
- [ ] Service account uses least privilege
- [ ] Cloud Run requires authentication
- [ ] AlloyDB in private VPC (no public IP)

---

## Getting Help

- **Documentation**: See `docs/` directory for detailed guides
- **ADRs**: Architecture Decision Records in `docs/adrs/`
- **Issues**: GitHub Issues for bug reports
- **Slack/Discord**: (Add your community links here)

---

## Next Steps After Deployment

1. **Generate API Key**: For your users
2. **Configure Claude Desktop**: With the service URL
3. **Test Ingestion**: Start with a small public repo
4. **Test Search**: Query your ingested code
5. **Set Up Monitoring**: GCP Monitoring/Logging
6. **Configure Alerts**: Budget alerts, error alerts
7. **Plan Backup Strategy**: Regular database backups

**Congratulations! You now have a fully functional, repeatable Code Index MCP deployment!** 🎉
