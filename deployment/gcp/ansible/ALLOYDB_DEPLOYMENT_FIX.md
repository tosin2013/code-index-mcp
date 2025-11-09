# AlloyDB Deployment Fix - Correct Task Order

## Problem Identified

The Ansible playbook was attempting to:
1. ❌ Deploy Cloud Run service (with AlloyDB connection settings)
2. ❌ Apply AlloyDB schema

But AlloyDB didn't exist yet! This caused deployment failures.

## Root Cause

The playbook assumed AlloyDB was **already provisioned manually** via Terraform, but didn't include AlloyDB provisioning in the automated deployment flow.

## Solution Implemented

### 1. Created AlloyDB Provisioning Task
**File**: `roles/code-index-mcp/tasks/provision_alloydb.yml`

Integrates Terraform to provision:
- AlloyDB cluster and primary instance
- VPC network and subnet
- VPC Connector for Cloud Run
- Password stored in Secret Manager
- Automatic waiting for AlloyDB to be READY

**Features**:
- Checks if Terraform state exists (idempotent)
- Displays cost estimates (~$179-185/month)
- 30-minute async timeout for provisioning
- Waits for AlloyDB state = READY before continuing

### 2. Reordered Deployment Tasks
**File**: `roles/code-index-mcp/tasks/main.yml`

**Old Order**:
1. Prerequisites
2. Storage, Service Account, Secrets
3. Build & Deploy Cloud Run ❌ (AlloyDB doesn't exist!)
4. Apply Schema ❌ (Too late!)

**New Order**:
1. Prerequisites
2. **Provision AlloyDB** ✅ (Terraform creates infrastructure)
3. **Apply Schema** ✅ (Database is ready)
4. Storage, Service Account, Secrets
5. Build & Deploy Cloud Run ✅ (Connects to ready AlloyDB)

### 3. Fixed Schema Application
**Files**: 
- `roles/code-index-mcp/tasks/apply_schema.yml`
- `roles/code-index-mcp/templates/Dockerfile.schema.j2`
- `roles/code-index-mcp/templates/apply_schema.py.j2`

**Fixes**:
- Copy schema file to `/tmp/alloydb-schema.sql` (Docker build context)
- Update Dockerfile to copy from correct path
- Update Python script to read from `/app/alloydb-schema.sql`

### 4. Fixed Prerequisites Check
**File**: `roles/code-index-mcp/tasks/prerequisites.yml`

**Before**: Failed if VPC connector didn't exist
**After**: Displays status (will be created by Terraform)

## Testing

Run the fixed deployment:

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp/ansible

# Full deployment with AlloyDB
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes"
```

## Expected Flow

```
1. Prerequisites (5 min)
   ├── Enable GCP APIs
   ├── Create Artifact Registry
   └── Check VPC Connector (will be created)

2. Provision AlloyDB (15-20 min) ← NEW!
   ├── Run Terraform init/plan/apply
   ├── Create AlloyDB cluster + instance
   ├── Create VPC network + connector
   ├── Store password in Secret Manager
   └── Wait for READY state

3. Apply Schema (2 min) ← MOVED UP!
   ├── Build schema applier Docker image
   ├── Push to Artifact Registry
   ├── Create Cloud Run job
   └── Execute schema application

4. Storage Setup (2 min)
   └── Create GCS buckets with lifecycle

5. Service Account (1 min)
   └── Grant IAM roles

6. Webhook Secrets (1 min)
   └── Create/validate secrets

7. Build Image (5 min)
   └── Build & push Docker image

8. Deploy Cloud Run (3 min)
   └── Deploy with AlloyDB connection

Total: ~30-35 minutes for fresh deployment
Total: ~10-15 minutes for updates (AlloyDB already exists)
```

## Cost Impact

**Development AlloyDB** (~$179-185/month):
- AlloyDB Instance (2 vCPU, 16 GB RAM): $164/month
- Storage (10 GB SSD): $2/month
- Backups (7 daily): $1/month
- VPC Connector: $7/month
- Network Egress: $5/month (estimated)

**Note**: This is in addition to Cloud Run costs (~$220/month for always-on).

## Verification

After deployment completes:

```bash
# Check AlloyDB status
gcloud alloydb instances list --region=us-east1

# Check schema was applied
gcloud run jobs executions list --region=us-east1

# Check Cloud Run service
gcloud run services describe code-index-mcp-dev --region=us-east1
```

## Cleanup

To destroy AlloyDB infrastructure:

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp
terraform destroy -var="project_id=YOUR_PROJECT_ID"
```

## Files Modified

1. ✅ `roles/code-index-mcp/tasks/provision_alloydb.yml` (NEW)
2. ✅ `roles/code-index-mcp/tasks/main.yml` (reordered)
3. ✅ `roles/code-index-mcp/tasks/apply_schema.yml` (copy schema to build context)
4. ✅ `roles/code-index-mcp/templates/Dockerfile.schema.j2` (fixed path)
5. ✅ `roles/code-index-mcp/templates/apply_schema.py.j2` (fixed path)
6. ✅ `roles/code-index-mcp/tasks/prerequisites.yml` (removed blocking check)

## Summary

✅ **The deployment flow is now correct**: AlloyDB is provisioned BEFORE Cloud Run deployment attempts to connect to it.

✅ **Idempotent**: Safe to run multiple times (Terraform checks existing state)

✅ **Integrated**: No manual Terraform commands needed

✅ **Validated**: Prerequisites check without blocking







