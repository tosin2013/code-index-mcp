# CI/CD Pipeline Setup Guide - Google Cloud Platform

**Platform**: Google Cloud Platform (GCP)
**Reference**: [ADR 0011 - CI/CD Pipeline and Security Architecture](adrs/0011-cicd-pipeline-and-security-architecture.md)

> **Note**: This guide is specific to GCP deployments. For other platforms, see:
> - [AWS Setup Guide](CI_CD_SETUP_GUIDE_AWS.md) *(Coming Soon)*
> - [OpenShift Setup Guide](CI_CD_SETUP_GUIDE_OPENSHIFT.md) *(Coming Soon)*

This guide walks you through setting up the automated CI/CD pipeline for Code Index MCP on **Google Cloud Platform** using GitHub Actions with OIDC Workload Identity (keyless authentication).

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Step 1: OIDC Workload Identity Setup](#step-1-oidc-workload-identity-setup)
- [Step 2: Configure GitHub Secrets](#step-2-configure-github-secrets)
- [Step 3: Configure GitHub Environments](#step-3-configure-github-environments)
- [Step 4: Test the Pipeline](#step-4-test-the-pipeline)
- [Workflow Reference](#workflow-reference)
- [Troubleshooting](#troubleshooting)

## Overview

The CI/CD pipeline provides:

- **Automated Security Scanning**: Gitleaks, Trivy, Bandit on every push/PR
- **Automated Deployment**: Build → Test → Deploy on merge to main/develop
- **Safe Deletion**: Manual approval-gated infrastructure deletion
- **Keyless Authentication**: OIDC Workload Identity (no service account keys)
- **Multi-Environment**: dev, staging, prod with environment protection

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Developer Push/PR                                           │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Security Scanning (security-scan.yml)             │
│  - Gitleaks (secrets detection)                             │
│  - Trivy (vulnerability scanning)                           │
│  - Bandit (Python security linting)                         │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: Testing                                            │
│  - Unit tests (pytest)                                       │
│  - Integration tests                                         │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: Build & Push                                       │
│  - Docker build (multi-stage)                                │
│  - Push to GCP Artifact Registry                            │
│  - Tag with commit SHA                                       │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 4: Deploy Infrastructure (Terraform)                  │
│  - terraform init, plan, apply                               │
│  - VPC, AlloyDB, Cloud Scheduler                            │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 5: Deploy Application (Ansible)                       │
│  - Cloud Run service deployment                              │
│  - Environment configuration                                 │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 6: Verification (MCP Tests)                           │
│  - MCP tool validation (ADR 0010)                           │
│  - Health checks                                             │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. GCP Project Setup

You need a GCP project with the following APIs enabled:

```bash
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  storage-api.googleapis.com \
  alloydb.googleapis.com \
  compute.googleapis.com \
  servicenetworking.googleapis.com
```

### 2. Create GCS Buckets

```bash
# Terraform state bucket
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-east1"

gsutil mb -p $GCP_PROJECT_ID -l $GCP_REGION gs://${GCP_PROJECT_ID}-terraform-state

# Audit logs bucket
gsutil mb -p $GCP_PROJECT_ID -l $GCP_REGION gs://${GCP_PROJECT_ID}-audit-logs

# Enable versioning for state bucket
gsutil versioning set on gs://${GCP_PROJECT_ID}-terraform-state
```

### 3. Create Artifact Registry Repository

```bash
gcloud artifacts repositories create code-index-mcp \
  --repository-format=docker \
  --location=$GCP_REGION \
  --description="Code Index MCP container images"
```

## Step 1: OIDC Workload Identity Setup

**IMPORTANT**: This enables keyless authentication from GitHub Actions to GCP (no service account keys needed).

### 1.1 Create Workload Identity Pool

```bash
export GCP_PROJECT_ID="your-project-id"
export GITHUB_REPO="your-github-username/code-index-mcp"

# Create pool
gcloud iam workload-identity-pools create "github-actions-pool" \
  --project="${GCP_PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Get the pool ID (save this for later)
export WORKLOAD_IDENTITY_POOL_ID=$(gcloud iam workload-identity-pools describe "github-actions-pool" \
  --project="${GCP_PROJECT_ID}" \
  --location="global" \
  --format="value(name)")

echo "Workload Identity Pool ID: $WORKLOAD_IDENTITY_POOL_ID"
```

### 1.2 Create OIDC Provider

```bash
# Create OIDC provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="${GCP_PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Get the full provider name (save this for GitHub secrets)
export WORKLOAD_IDENTITY_PROVIDER=$(gcloud iam workload-identity-pools providers describe "github-provider" \
  --project="${GCP_PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --format="value(name)")

echo "Workload Identity Provider: $WORKLOAD_IDENTITY_PROVIDER"
```

### 1.3 Create Service Account for GitHub Actions

```bash
# Create service account
gcloud iam service-accounts create github-actions \
  --project="${GCP_PROJECT_ID}" \
  --display-name="GitHub Actions Deployment"

export SERVICE_ACCOUNT_EMAIL="github-actions@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# Grant necessary roles
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/secretmanager.admin"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/cloudscheduler.admin"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/alloydb.admin"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/compute.networkAdmin"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/iam.serviceAccountUser"
```

### 1.4 Allow GitHub Actions to Impersonate Service Account

```bash
# Allow GitHub Actions from your repository to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT_EMAIL}" \
  --project="${GCP_PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${GITHUB_REPO}"

echo "✅ OIDC Workload Identity setup complete!"
echo ""
echo "Save these values for GitHub Secrets:"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER: $WORKLOAD_IDENTITY_PROVIDER"
echo "GCP_SERVICE_ACCOUNT: $SERVICE_ACCOUNT_EMAIL"
```

## Step 2: Configure GitHub Secrets

Navigate to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret.

Add the following secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider` | Full OIDC provider path from Step 1.2 |
| `GCP_SERVICE_ACCOUNT` | `github-actions@PROJECT_ID.iam.gserviceaccount.com` | Service account email from Step 1.3 |
| `GCP_PROJECT_ID` | `your-project-id` | Your GCP project ID |
| `GCP_TERRAFORM_STATE_BUCKET` | `your-project-id-terraform-state` | GCS bucket for Terraform state |
| `GCP_AUDIT_BUCKET` | `your-project-id-audit-logs` | GCS bucket for audit logs |
| `MCP_API_KEY_DEV` | `ci_xxxxxxxxxxxx` | MCP API key for dev environment testing |

### How to Get These Values:

```bash
# Get project number (needed for WORKLOAD_IDENTITY_PROVIDER)
gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)"

# Verify WORKLOAD_IDENTITY_PROVIDER format
echo $WORKLOAD_IDENTITY_PROVIDER

# Verify SERVICE_ACCOUNT
echo $SERVICE_ACCOUNT_EMAIL

# Generate MCP API key (run after first deployment)
cd deployment/gcp/ansible
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=generate_api_key" -e "user_email=test@example.com"
```

## Step 3: Configure GitHub Environments

GitHub Environments provide protection rules and secrets scoping.

### 3.1 Create Environments

Go to: Repository → Settings → Environments → New environment

Create these environments:

1. **dev**
   - No protection rules needed
   - Used for automatic deployments from `develop` branch

2. **staging**
   - Protection rules:
     - ✅ Required reviewers: 1 reviewer
   - Used for automatic deployments from `main` branch

3. **prod** (future)
   - Protection rules:
     - ✅ Required reviewers: 2 reviewers
     - ✅ Wait timer: 5 minutes
   - Used for manual deployments only

4. **delete-dev**
   - Protection rules:
     - ✅ Required reviewers: 1 reviewer
   - Used for deletion workflow approval

5. **delete-staging**
   - Protection rules:
     - ✅ Required reviewers: 2 reviewers
   - Used for deletion workflow approval

### 3.2 Environment-Specific Secrets (Optional)

You can override repository secrets per environment if needed:

- Navigate to the environment
- Add environment secrets with the same names as repository secrets
- Environment secrets take precedence

## Step 4: Test the Pipeline

### 4.1 Test Security Scanning

Create a test branch and trigger security scans:

```bash
git checkout -b test-security-scan
git push origin test-security-scan

# Create a PR to trigger security-scan.yml
# Check GitHub Actions tab for results
```

Expected results:
- ✅ Gitleaks: No secrets detected
- ✅ Trivy: No critical/high vulnerabilities
- ✅ Bandit: No security issues

### 4.2 Test Deployment Workflow (Manual)

Trigger a manual deployment to dev:

1. Go to: Repository → Actions → "Deploy to Google Cloud Platform"
2. Click "Run workflow"
3. Select:
   - Branch: `main`
   - Environment: `dev`
   - Skip tests: `false`
4. Click "Run workflow"

Monitor the pipeline stages:

1. Security scans (reuses security-scan.yml)
2. Unit and integration tests
3. Container image build and push
4. Infrastructure deployment (Terraform)
5. Application deployment (Ansible)
6. MCP validation tests

Expected duration: **10-15 minutes**

### 4.3 Test Automatic Deployment

Merge a PR to `develop` or `main`:

```bash
# This will automatically trigger deployment
git checkout develop
git merge test-security-scan
git push origin develop

# Watch GitHub Actions tab for automatic deployment to dev
```

### 4.4 Test Deletion Workflow

**CAUTION**: This will delete your dev environment.

1. Go to: Repository → Actions → "Delete GCP Infrastructure"
2. Click "Run workflow"
3. Fill in:
   - Environment: `dev`
   - Confirmation: `DELETE` (exact, case-sensitive)
   - Reason: `Testing deletion workflow`
4. Click "Run workflow"
5. Wait for approval request
6. Approve the deletion (if you're a reviewer)

The workflow will:
- Validate inputs
- Wait for manual approval
- Create audit log in GCS
- Inventory resources
- Teardown application (Ansible)
- Destroy infrastructure (Terraform)
- Archive state files

## Workflow Reference

### security-scan.yml

**Triggers**:
- Push to `main`, `develop`, `master`
- Pull requests to `main`, `develop`, `master`
- Manual trigger

**Jobs**:
- `gitleaks`: Secret detection
- `trivy`: Vulnerability scanning (dependencies + Docker images)
- `bandit`: Python security linting
- `summary`: Aggregated results

**Failure Conditions**:
- Secrets detected by Gitleaks → ❌ Block merge
- CRITICAL/HIGH vulnerabilities found by Trivy → ❌ Block merge
- Bandit issues → ⚠️ Warning (doesn't block)

### deploy-gcp.yml

**Triggers**:
- Push to `main` → staging (automatic)
- Push to `develop` → dev (automatic)
- Manual trigger → any environment

**Inputs** (manual trigger only):
- `environment`: dev/staging/prod
- `skip_tests`: true/false (default: false)

**Stages**:
1. Security scans (calls security-scan.yml)
2. Tests (pytest)
3. Build (Docker → Artifact Registry)
4. Deploy Infrastructure (Terraform)
5. Deploy Application (Ansible)
6. Verify (MCP tests)

**Outputs**:
- Container image tag
- Service URL
- Deployment summary

### delete-gcp.yml

**Triggers**:
- Manual only (workflow_dispatch)

**Inputs**:
- `environment`: dev/staging (prod blocked by default)
- `confirmation`: Must type "DELETE" exactly
- `reason`: Required for audit trail
- `force_production`: Override production block (requires special approval)

**Stages**:
1. Validate inputs
2. Manual approval gate
3. Create audit log
4. Inventory resources
5. Teardown application
6. Destroy infrastructure
7. Archive state files

**Protection**:
- Production deletions blocked unless `force_production=true`
- Manual approval required for all deletions
- Audit logs stored in GCS
- State files archived (not deleted)

## Troubleshooting

### Error: "Failed to authenticate with GCP"

**Cause**: OIDC Workload Identity configuration issue.

**Solution**:

```bash
# Verify Workload Identity Pool exists
gcloud iam workload-identity-pools describe "github-actions-pool" \
  --project="${GCP_PROJECT_ID}" \
  --location="global"

# Verify provider exists
gcloud iam workload-identity-pools providers describe "github-provider" \
  --project="${GCP_PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-actions-pool"

# Check service account permissions
gcloud projects get-iam-policy $GCP_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:github-actions@*"

# Verify GitHub secret GCP_WORKLOAD_IDENTITY_PROVIDER matches
echo $WORKLOAD_IDENTITY_PROVIDER
```

### Error: "Terraform backend initialization failed"

**Cause**: Terraform state bucket doesn't exist or wrong permissions.

**Solution**:

```bash
# Check if bucket exists
gsutil ls -p $GCP_PROJECT_ID | grep terraform-state

# If missing, create it
gsutil mb -p $GCP_PROJECT_ID -l $GCP_REGION gs://${GCP_PROJECT_ID}-terraform-state
gsutil versioning set on gs://${GCP_PROJECT_ID}-terraform-state

# Grant service account access
gsutil iam ch serviceAccount:github-actions@${GCP_PROJECT_ID}.iam.gserviceaccount.com:objectAdmin \
  gs://${GCP_PROJECT_ID}-terraform-state
```

### Error: "Container image push failed"

**Cause**: Artifact Registry repository doesn't exist or wrong permissions.

**Solution**:

```bash
# Check if repository exists
gcloud artifacts repositories describe code-index-mcp \
  --location=$GCP_REGION

# If missing, create it
gcloud artifacts repositories create code-index-mcp \
  --repository-format=docker \
  --location=$GCP_REGION

# Grant service account push permissions
gcloud artifacts repositories add-iam-policy-binding code-index-mcp \
  --location=$GCP_REGION \
  --member=serviceAccount:github-actions@${GCP_PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/artifactregistry.writer
```

### Error: "Security scan failed - secrets detected"

**Cause**: Gitleaks detected potential secrets in code.

**Solution**:

1. Review the Gitleaks output in GitHub Actions logs
2. If it's a false positive (e.g., example/test data):
   - Add pattern to `.gitleaks.toml` allowlist
   - Example: `'''ci_example[A-Za-z0-9]+'''`
3. If it's a real secret:
   - **DO NOT COMMIT IT**
   - Remove from code immediately
   - Rotate the secret (generate new one)
   - Use GitHub Secrets or GCP Secret Manager instead
   - Rewrite git history if already committed:
     ```bash
     git filter-branch --force --index-filter \
       "git rm --cached --ignore-unmatch path/to/file" \
       --prune-empty --tag-name-filter cat -- --all
     ```

### Error: "Trivy found vulnerabilities"

**Cause**: Dependencies or Docker base images have known CVEs.

**Solution**:

```bash
# Run Trivy locally to see details
docker run --rm -v $(pwd):/src aquasec/trivy fs /src

# For Python dependencies
pip install safety
safety check --json

# Update vulnerable dependencies
uv sync --upgrade

# If false positive, add to trivy.yaml:
# vulnerability:
#   ignorefile: .trivyignore
```

### Error: "MCP validation tests failed"

**Cause**: Deployed service not responding correctly to MCP tool calls.

**Solution**:

```bash
# Check Cloud Run logs
gcloud run services logs read code-index-mcp-dev --region=$GCP_REGION --limit=50

# Test MCP endpoint manually
export CLOUDRUN_SERVICE_URL=$(gcloud run services describe code-index-mcp-dev \
  --region=$GCP_REGION --format='value(status.url)')
export MCP_API_KEY="ci_your_api_key_here"

curl -H "X-API-Key: $MCP_API_KEY" $CLOUDRUN_SERVICE_URL/sse

# Run MCP tests locally
cd tests/ansible
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
```

### Error: "Terraform apply failed"

**Cause**: Resource quota exceeded or conflicting resources.

**Solution**:

```bash
# Check quota
gcloud compute project-info describe --project=$GCP_PROJECT_ID

# View Terraform error details in GitHub Actions logs
# Common issues:
# - AlloyDB cluster already exists → terraform import
# - VPC peering conflict → delete old peering first
# - IP range overlap → change CIDR in terraform vars

# Import existing resources if needed
cd deployment/gcp/terraform
terraform import google_alloydb_cluster.main projects/$GCP_PROJECT_ID/locations/$GCP_REGION/clusters/code-index-mcp-dev
```

## Best Practices

### 1. Branch Strategy

- **`develop`** → auto-deploys to **dev** environment
- **`main`** → auto-deploys to **staging** environment
- **Manual trigger** → for **prod** deployments

### 2. Secrets Management

- ✅ **DO**: Use GitHub Secrets for all credentials
- ✅ **DO**: Use GCP Secret Manager for runtime secrets
- ✅ **DO**: Rotate secrets regularly
- ❌ **DON'T**: Commit secrets to git (Gitleaks will catch this)
- ❌ **DON'T**: Use service account keys (use OIDC instead)

### 3. Testing

- Always run security scans before merging
- Test in `dev` before promoting to `staging`
- Run MCP validation tests after every deployment
- Monitor Cloud Run logs for errors

### 4. Cost Management

- Use `dev` environment for testing (cheaper config)
- Delete `dev` environment when not in use
- `staging` and `prod` should scale to zero when idle
- Monitor costs with GCP billing alerts

### 5. Rollback

If deployment fails or introduces bugs:

```bash
# Option 1: Redeploy previous working version
# Find the commit SHA of the working version
git log --oneline

# Manually trigger deployment with that SHA's image tag
# Go to Actions → Deploy to GCP → Run workflow
# The image tag format is: {environment}-{sha}

# Option 2: Use Terraform state to rollback infrastructure
cd deployment/gcp/terraform
terraform state list
terraform state show google_cloud_run_service.main

# Option 3: Use Ansible to redeploy previous version
cd deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml \
  -e "container_image=$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/code-index-mcp/server:dev-abc123"
```

## Next Steps

After pipeline setup is complete:

1. ✅ Merge security configuration to `main`
2. ✅ Test automatic deployment to `dev`
3. ✅ Configure monitoring and alerting
4. ✅ Set up Slack/email notifications for pipeline failures
5. ✅ Document rollback procedures
6. ✅ Train team on pipeline usage

## Support

For issues or questions:

- **GitHub Issues**: [Repository Issues](https://github.com/johnhuang316/code-index-mcp/issues)
- **Documentation**: See [ADR 0011](adrs/0011-cicd-pipeline-and-security-architecture.md)
- **Security**: Report via GitHub Security tab (for vulnerabilities)

---

**Last Updated**: November 14, 2025
**Version**: 1.0.0
**Author**: Code Index MCP Team
