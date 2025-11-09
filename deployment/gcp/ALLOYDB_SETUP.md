# AlloyDB Setup Guide - Code Index MCP

**Phase 3A: Semantic Search with AlloyDB + Vertex AI**

This guide walks you through setting up AlloyDB for semantic code search capabilities.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Cost Breakdown](#cost-breakdown)
4. [Quick Start](#quick-start)
5. [Manual Setup](#manual-setup)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Scaling to Production](#scaling-to-production)

---

## 🔍 Overview

**What we're building:**
- **AlloyDB PostgreSQL** with pgvector for vector embeddings
- **Vertex AI** integration for generating code embeddings
- **Semantic search** - Find code by meaning, not just keywords
- **Code similarity** - Find similar implementations across projects

**Architecture:**
```
Cloud Run MCP Server
        ↓
    AlloyDB (PostgreSQL + pgvector)
        ↓
    Vertex AI (text-embedding-004)
```

---

## ✅ Prerequisites

### 1. **Tools Required**

```bash
# Install Terraform
brew install terraform  # macOS
# or visit: https://www.terraform.io/downloads

# Install PostgreSQL client
brew install postgresql  # macOS
sudo apt-get install postgresql-client  # Ubuntu
```

### 2. **GCP Requirements**

- ✅ Google Cloud Project (same as Cloud Run)
- ✅ Billing enabled
- ✅ gcloud CLI authenticated
- ✅ Project set: `gcloud config set project YOUR_PROJECT_ID`

### 3. **APIs to Enable**

Will be enabled automatically by setup script:
- AlloyDB API
- Service Networking API
- VPC Access API
- Compute Engine API
- Vertex AI API

---

## 💰 Cost Breakdown

### Development Instance (Recommended to start)

| Resource | Specification | Monthly Cost |
|----------|--------------|--------------|
| AlloyDB Instance | 1 vCPU, 8 GB RAM | ~$82 |
| Storage | 10 GB SSD | ~$2 |
| Backups | 7 daily backups | ~$1 |
| VPC Connector | For Cloud Run | ~$7 |
| Network Egress | Estimated | ~$5 |
| **Total** | | **~$97-100/month** |

### Production Instance (Scale up later)

| Resource | Specification | Monthly Cost |
|----------|--------------|--------------|
| AlloyDB Instance | 2 vCPU, 16 GB RAM | ~$200 |
| Storage | 100 GB SSD | ~$20 |
| Backups | 7 daily backups | ~$2 |
| VPC Connector | For Cloud Run | ~$7 |
| Network Egress | Estimated | ~$10 |
| **Total** | | **~$239/month** |

### One-Time Costs

- **Embedding Generation**: ~$0.025 per 1M characters
- **Example**: 100k lines of code ≈ 5M characters ≈ **$0.125 one-time**

**Note**: Embeddings are cached, so you only pay once per code chunk.

---

## 🚀 Quick Start

### Option A: Automated Setup (Recommended)

```bash
cd deployment/gcp

# Run the setup script
./setup-alloydb.sh dev

# This will:
# 1. Enable required GCP APIs
# 2. Provision AlloyDB cluster (10-15 minutes)
# 3. Create database schema
# 4. Set up VPC connector
# 5. Configure Cloud Run
```

**Output**: Configuration saved to `.env.alloydb`

### Option B: Manual Setup

See [Manual Setup](#manual-setup) section below.

---

## 📝 Manual Setup

If you prefer manual control:

### Step 1: Initialize Terraform

```bash
cd deployment/gcp
terraform init
```

### Step 2: Plan Infrastructure

```bash
terraform plan \
  -var="project_id=$(gcloud config get-value project)" \
  -var="region=us-east1" \
  -var="environment=dev" \
  -out=tfplan
```

Review the plan carefully. Expected resources:
- 1 AlloyDB cluster
- 1 AlloyDB primary instance
- 1 VPC network
- 1 VPC subnet
- 1 Private Service Connection
- 1 VPC Access Connector
- 1 Secret (database password)

### Step 3: Apply Infrastructure

```bash
terraform apply tfplan
```

**This takes 10-15 minutes.** AlloyDB clusters take time to provision.

### Step 4: Get Connection Details

```bash
# Get instance IP
INSTANCE_IP=$(terraform output -raw primary_instance_ip)

# Get password secret name
PASSWORD_SECRET=$(terraform output -raw database_password_secret)

# Retrieve password
DB_PASSWORD=$(gcloud secrets versions access latest --secret="$PASSWORD_SECRET")

# Connection string
echo "postgresql://code_index_admin:$DB_PASSWORD@$INSTANCE_IP:5432/postgres"
```

### Step 5: Apply Database Schema

```bash
# Apply schema
PGPASSWORD="$DB_PASSWORD" psql \
  -h "$INSTANCE_IP" \
  -U code_index_admin \
  -d postgres \
  -f alloydb-schema.sql
```

**Expected output**:
```
CREATE EXTENSION
CREATE EXTENSION
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE INDEX
...
NOTICE: AlloyDB Schema Setup Complete!
```

---

## 🧪 Testing

### Test 1: Basic Connection

```bash
./test-alloydb-connection.sh
```

**Expected output**:
```
[SUCCESS] ✓ Connection successful
[SUCCESS] ✓ Extensions installed (vector, google_ml_integration)
[SUCCESS] ✓ Tables created (users, projects, code_chunks)
[SUCCESS] ✓ HNSW vector index created
[SUCCESS] ✓ Functions created
[SUCCESS] ✓ Embedding generation working
[SUCCESS] ✓ Row-level security enabled
```

### Test 2: Manual SQL Test

```bash
# Get connection info
source .env.alloydb
DB_PASSWORD=$(gcloud secrets versions access latest --secret="$ALLOYDB_PASSWORD_SECRET")

# Connect with psql
PGPASSWORD="$DB_PASSWORD" psql \
  -h "$ALLOYDB_INSTANCE_IP" \
  -U code_index_admin \
  -d postgres
```

**Try these queries**:

```sql
-- Check tables
\dt

-- Check extensions
SELECT extname FROM pg_extension;

-- Check vector index
\d code_chunks

-- Test embedding function (requires Vertex AI)
SELECT generate_code_embedding('def hello(): print("world")');

-- Query test data
SELECT * FROM users;
```

### Test 3: Cloud Run Connection

Update Cloud Run to use VPC connector:

```bash
gcloud run services update code-index-mcp-dev \
  --region=us-east1 \
  --vpc-connector=$(terraform output -raw vpc_connector_name) \
  --vpc-egress=private-ranges-only
```

---

## 🚨 Troubleshooting

### Issue: "Terraform command not found"

**Solution**:
```bash
# macOS
brew install terraform

# Ubuntu
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

### Issue: "psql command not found"

**Solution**:
```bash
# macOS
brew install postgresql

# Ubuntu
sudo apt-get install postgresql-client
```

### Issue: "Connection refused"

**Causes**:
1. VPC not configured correctly
2. Cloud Run not using VPC connector
3. Firewall rules

**Solution**:
```bash
# Check VPC connector
gcloud compute networks vpc-access connectors list --region=us-east1

# Verify Cloud Run is using connector
gcloud run services describe code-index-mcp-dev \
  --region=us-east1 \
  --format="value(spec.template.spec.containers[0].vpcAccess)"
```

### Issue: "Embedding generation failed"

**Cause**: Vertex AI not enabled or IAM permissions missing

**Solution**:
```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Grant permissions to service account
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member="serviceAccount:$(gcloud config get-value project)@appspot.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### Issue: "High costs"

**Causes**:
- AlloyDB running 24/7 (by design)
- Unused storage
- Too many backups

**Solutions**:
```bash
# 1. Delete development instance when not in use
terraform destroy

# 2. Reduce backup retention
# Edit alloydb-dev.tf, change:
#   quantity_based_retention { count = 7 }
# to:
#   quantity_based_retention { count = 3 }

# 3. Use smaller instance
# Edit alloydb-dev.tf, change cpu_count to 1 (already minimal)
```

---

## 📈 Scaling to Production

When ready for production traffic:

### Option 1: Scale Up Existing Instance

```bash
# Stop accepting new traffic
terraform destroy

# Edit alloydb-dev.tf
# Change:
#   cpu_count = 1  →  cpu_count = 2
#   (8 GB RAM auto-scales with CPU)

# Reprovision
terraform apply
```

### Option 2: Create Production Instance

```bash
# Create production configuration
cp alloydb-dev.tf alloydb-prod.tf

# Edit alloydb-prod.tf:
# - Set cpu_count = 2
# - Set availability_type = "REGIONAL"  # High availability
# - Increase backup retention

# Deploy production
terraform workspace new production
terraform apply -var="environment=prod"
```

### Performance Tuning

**1. Adjust HNSW Index Parameters**:

```sql
-- Drop existing index
DROP INDEX code_chunks_embedding_idx;

-- Recreate with production settings
CREATE INDEX code_chunks_embedding_idx ON code_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128);  -- Higher quality

-- Set query-time parameter
SET hnsw.ef_search = 64;  -- Balance speed/quality
```

**2. Add Read Replicas** (for high-traffic):

```hcl
# In alloydb-prod.tf, add:
resource "google_alloydb_instance" "read_replica" {
  cluster       = google_alloydb_cluster.code_index_cluster.name
  instance_id   = "code-index-replica-${var.environment}"
  instance_type = "READ_POOL"

  machine_config {
    cpu_count = 2
  }

  read_pool_config {
    node_count = 2  # 2 read replicas
  }
}
```

**Cost**: +$200/month per read replica

---

## 📚 Related Documentation

- [ADR 0003: AlloyDB Architecture](../docs/adrs/0003-google-cloud-code-ingestion-with-alloydb.md)
- [AlloyDB Official Docs](https://cloud.google.com/alloydb/docs)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Vertex AI Embeddings](https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings)

---

## 🔐 Security Best Practices

### 1. **Network Security**

✅ **Done automatically**:
- Private IP only (no public access)
- VPC peering
- Service networking

### 2. **Access Control**

```sql
-- Create application user (limited permissions)
CREATE USER code_index_app WITH PASSWORD 'secure_password';

-- Grant only necessary permissions
GRANT CONNECT ON DATABASE postgres TO code_index_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO code_index_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO code_index_app;

-- Use this user in production, not code_index_admin
```

### 3. **Row-Level Security**

Already enabled! Each user can only access their own data.

```sql
-- Test RLS
SELECT set_user_context('user-uuid-here');
SELECT * FROM code_chunks;  -- Only sees their own data
```

### 4. **Audit Logging**

```bash
# Enable audit logs
gcloud alloydb clusters update code-index-cluster-dev \
  --region=us-east1 \
  --audit-log-config=all_queries
```

---

## 🎯 Next Steps

After AlloyDB is set up:

1. ✅ **Test connection** - Run `./test-alloydb-connection.sh`
2. ⏳ **Update MCP server** - Add AlloyDB connection logic
3. ⏳ **Implement ingestion** - Code chunking + embedding generation
4. ⏳ **Add search tools** - `semantic_search_code()`, `find_similar_code()`
5. ⏳ **Test end-to-end** - Upload code, search, verify results

---

**Last Updated**: October 25, 2025
**Version**: Development (Phase 3A)
**Environment**: Google Cloud
**Cost**: ~$100/month (dev), ~$220/month (prod)

**Questions?** Refer to [Troubleshooting](#troubleshooting) or check [ADR 0003](../docs/adrs/0003-google-cloud-code-ingestion-with-alloydb.md).
