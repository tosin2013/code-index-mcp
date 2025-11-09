# AlloyDB Schema Application Status

## Current Situation

**AlloyDB is deployed and running**, but the schema has **not yet been applied** due to network access challenges.

## The Network Access Challenge

AlloyDB runs on a **private IP (10.22.0.2)** within your VPC. To apply the schema, you need to connect from an environment that has VPC access:

### ❌ Environments That DON'T Work

1. **Local MacBook**: Can't reach private VPC IPs
2. **Google Cloud Shell**: Runs in Google's managed network, no VPC peering

### ✅ Environments That DO Work

1. **GCE VM in the same VPC** (recommended for manual schema application)
2. **Cloud Run Job with VPC Connector** (automated, but requires proper configuration)
3. **Cloud Build with VPC Connector** (CI/CD pipelines)

## Solutions

### Option 1: GCE VM (Quick Manual Fix) - 5 minutes

**Best for**: One-time schema application right now

```bash
# 1. Create a temporary GCE VM in the VPC
gcloud compute instances create schema-applier-temp \
  --zone=us-east1-b \
  --machine-type=e2-micro \
  --network=default \
  --subnet=default \
  --scopes=cloud-platform

# 2. SSH into the VM
gcloud compute ssh schema-applier-temp --zone=us-east1-b

# 3. Install dependencies
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install psycopg2-binary

# 4. Upload and run the script
# (Exit SSH, then from local machine:)
gcloud compute scp deployment/gcp/apply_alloydb_schema.py schema-applier-temp:~ --zone=us-east1-b
gcloud compute scp deployment/gcp/alloydb-schema.sql schema-applier-temp:~ --zone=us-east1-b

# 5. SSH back and run
gcloud compute ssh schema-applier-temp --zone=us-east1-b
python3 apply_alloydb_schema.py

# 6. Delete the VM when done
exit
gcloud compute instances delete schema-applier-temp --zone=us-east1-b --quiet
```

### Option 2: Cloud Run Job (Automated)  - 10 minutes

**Best for**: Repeatable automation

The Ansible deployment already includes this, but it failed due to authentication issues. To fix:

```bash
cd deployment/gcp/ansible

# Update the Cloud Run Job to use proper VPC connector and secrets
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=apply_schema"
```

**Current blocker**: Cloud Run Job needs:
- ✅ VPC connector configured
- ✅ Secret Manager access
- ❌ AlloyDB pg_hba.conf needs to allow connections from VPC subnet

### Option 3: PostgreSQL Docker Compose (Local Development) ✅ READY

**Best for**: Daily development work

```bash
# Start local PostgreSQL (AlloyDB-compatible)
docker compose up -d postgres

# Schema is auto-applied!
# Test semantic search locally
uv run code-index-mcp
```

See `docs/LOCAL_DEVELOPMENT.md` for full guide.

## Recommended Approach

### For Immediate Testing (Today)

**Use Option 1 (GCE VM)** to apply schema to AlloyDB:
1. Takes 5 minutes
2. One-time manual process
3. Gets you unblocked immediately

### For Daily Development (Going Forward)

**Use Option 3 (Docker Compose)** for local development:
1. PostgreSQL + pgvector locally
2. Same schema, same tools
3. No cloud costs, instant startup

### For Production (After Testing)

Keep using AlloyDB in production - it's already deployed and will work great once schema is applied.

## Files Created

### Local Development
- ✅ `docker-compose.yml` - PostgreSQL + pgvector setup
- ✅ `.env.local.example` - Local environment template
- ✅ `docs/LOCAL_DEVELOPMENT.md` - Complete local dev guide

### AlloyDB Schema Application
- ✅ `deployment/gcp/apply_alloydb_schema.py` - Standalone schema application script
- ✅ `deployment/gcp/ansible/roles/utilities/tasks/apply_schema.yml` - Automated Ansible approach
- ✅ `deployment/gcp/ansible/roles/utilities/files/apply_schema_cloudshell.sh` - Cloud Shell attempt (didn't work)

## Next Steps

1. **Apply AlloyDB Schema** (choose one):
   - Option 1: GCE VM (fastest, manual)
   - Option 2: Fix Cloud Run Job (automated, needs pg_hba fix)

2. **Test Locally**:
   ```bash
   docker compose up -d postgres
   uv run code-index-mcp
   cd tests/ansible && ansible-playbook test-local.yml -i inventory/local.yml
   ```

3. **Test Cloud**:
   ```bash
   cd tests/ansible
   ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
   ```

4. **Validate Semantic Search**:
   ```bash
   # Ingest test repository
   # Then run semantic queries
   ```

## Summary

**Local Development**: ✅ Ready (PostgreSQL Docker Compose)
**AlloyDB Deployment**: ✅ Running (schema pending)
**Schema Application**: ⚠️ Manual step needed (GCE VM recommended)
**Testing Framework**: ✅ Ready (Ansible test suites)

**Estimated Time to Full Functionality**: 5 minutes (if using GCE VM option)
