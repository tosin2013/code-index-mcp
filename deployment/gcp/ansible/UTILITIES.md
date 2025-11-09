# Ansible Utilities Guide

This guide covers the utility operations available through Ansible for managing your Code Index MCP deployment.

## Overview

The utilities role provides common administrative tasks:
- **API Key Generation**: Create user API keys for MCP access
- **Database Queries**: Query AlloyDB for data inspection
- **Schema Verification**: Verify database schema is correct
- **Connection Testing**: Test AlloyDB connectivity
- **Teardown**: Delete all cloud resources

## Quick Start

All utilities are run through the `utilities.yml` playbook:

```bash
cd deployment/gcp/ansible
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=OPERATION_NAME"
```

## Available Operations

### 1. Generate API Key

Create a new API key for a user:

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key" \
  -e "user_id=john-doe"
```

**Parameters:**
- `user_id` (required): Unique identifier for the user
- `save_to_file` (optional): Save API key to file (default: true)

**Output:**
- API key saved to `api-key-{user_id}-{environment}.txt`
- Claude Desktop configuration provided
- Secret stored in GCP Secret Manager

**Example output:**
```
API Key: ci_a1b2c3d4e5f6...
Secret Name: code-index-api-key-john-doe-dev

Claude Desktop Configuration:
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://code-index-mcp-dev-*.run.app/sse",
      "transport": "sse",
      "headers": {
        "X-API-Key": "ci_a1b2c3d4e5f6..."
      }
    }
  }
}
```

### 2. Query Database

Query AlloyDB for data inspection:

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=query_database"
```

**Parameters:**
- `query_method` (optional): `cloud_run_job` (default) or `vm`

**What it queries:**
- All projects
- Code chunks summary by project
- Sample code chunks (first 5)

**Example output:**
```
PROJECTS:
project_id | project_name | language   | created_at
-----------|--------------|------------|-------------------
abc123     | my-app       | python     | 2025-10-29

CODE CHUNKS SUMMARY:
project_name | chunk_count | file_count | languages
-------------|-------------|------------|-----------
my-app       | 1,234       | 56         | python

SAMPLE CHUNKS:
file_path         | function_name    | language | code_preview
------------------|------------------|----------|----------------
src/main.py       | main             | python   | def main():...
src/auth.py       | authenticate     | python   | def authen...
```

### 3. Verify Schema

Verify that the AlloyDB schema is correctly set up:

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=verify_schema"
```

**What it checks:**
- All tables exist (users, projects, code_chunks)
- Table structures are correct
- Indexes are created (including HNSW vector index)
- Git provenance columns exist

**Example output:**
```
Database Tables:
- users
- projects
- code_chunks

code_chunks Table Structure:
column_name        | data_type      | is_nullable
-------------------|----------------|------------
chunk_id           | uuid           | NO
project_id         | uuid           | NO
file_path          | varchar(1024)  | NO
code               | text           | NO
embedding          | vector(768)    | YES
commit_hash        | varchar(40)    | YES
branch_name        | varchar(255)   | YES
...

Indexes:
- code_chunks_embedding_idx (HNSW)
- idx_code_chunks_commit_hash
- idx_code_chunks_branch
```

### 4. Test Connection

Comprehensive AlloyDB connection testing:

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=test_connection"
```

**Tests performed:**
1. Basic connection
2. Extensions installed (vector, google_ml_integration)
3. Tables created (users, projects, code_chunks)
4. HNSW vector index exists
5. Functions created (generate_code_embedding, semantic_search_code)
6. Row-level security enabled
7. Git provenance columns exist
8. Data counts

**Example output:**
```
Test Summary:
Connection: ✓ PASS
Extensions: ✓ PASS (vector, google_ml_integration)
Tables: ✓ PASS (users, projects, code_chunks)
HNSW Index: ✓ PASS
Functions: ✓ PASS
Row-Level Security: ✓ PASS
Git Provenance Columns: ✓ PASS

Data Counts:
users: 3
projects: 5
code_chunks: 12,456
```

### 5. Teardown

Delete all cloud resources:

```bash
# With confirmation prompt
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown"

# Auto-approve (no prompt)
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown" \
  -e "auto_approve=true"

# Delete buckets too (DANGEROUS - all data lost!)
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown" \
  -e "auto_approve=true" \
  -e "delete_buckets=true"
```

**Parameters:**
- `auto_approve` (optional): Skip confirmation prompt (default: false)
- `delete_buckets` (optional): Delete GCS buckets (default: false)

**What it deletes:**
- Cloud Run service
- Container images from Artifact Registry
- Cloud Scheduler cleanup job
- GCS buckets (if `delete_buckets=true`)

**What it DOES NOT delete:**
- AlloyDB cluster and instance (~$180-200/month)
- VPC connector
- Secrets in Secret Manager

**To delete AlloyDB:**
```bash
cd deployment/gcp
terraform destroy
```

## Common Use Cases

### Generate API keys for multiple users

```bash
for user in alice bob charlie; do
  ansible-playbook utilities.yml -i inventory/prod.yml \
    -e "operation=generate_api_key" \
    -e "user_id=$user"
done
```

### Check database health

```bash
# Quick health check
ansible-playbook utilities.yml -i inventory/prod.yml \
  -e "operation=test_connection"

# Detailed inspection
ansible-playbook utilities.yml -i inventory/prod.yml \
  -e "operation=query_database"
```

### Verify schema after migration

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=verify_schema"
```

### Clean up dev environment

```bash
# Delete everything except buckets
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown" \
  -e "auto_approve=true"

# Delete everything including buckets
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown" \
  -e "auto_approve=true" \
  -e "delete_buckets=true"
```

## Troubleshooting

### "Operation parameter is required"

Make sure to specify the `-e "operation=OPERATION_NAME"` parameter:
```bash
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=test_connection"
```

### "VPC connector not found"

The AlloyDB infrastructure must be provisioned first:
```bash
cd deployment/gcp
terraform init
terraform apply
```

### "Service account not found"

Deploy the main application first:
```bash
ansible-playbook deploy.yml -i inventory/dev.yml
```

### "Permission denied" errors

Make sure you're authenticated to GCP:
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

## Advanced Usage

### Custom query method

Use temporary VM instead of Cloud Run Job:
```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=query_database" \
  -e "query_method=vm"
```

### Specify AlloyDB IP

Override the default AlloyDB IP:
```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=test_connection" \
  -e "alloydb_ip=10.175.0.3"
```

### Save API key to custom location

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key" \
  -e "user_id=john" \
  -e "save_to_file=true"
```

## Security Notes

### API Keys
- API keys are stored in GCP Secret Manager
- Keys are automatically granted to the Cloud Run service account
- Keys are 64 characters long with `ci_` prefix
- Never commit API keys to version control

### Database Access
- All database operations use VPC connector for secure access
- Connections use IAM authentication where possible
- Passwords are retrieved from Secret Manager, never hardcoded

### Teardown
- Teardown requires explicit confirmation unless `auto_approve=true`
- Buckets are preserved by default to prevent accidental data loss
- AlloyDB is never automatically deleted (requires manual `terraform destroy`)

## See Also

- [Main Deployment Guide](README.md) - Full deployment documentation
- [Migration Guide](../ANSIBLE_MIGRATION_GUIDE.md) - Migration from bash scripts
- [Deployment Summary](../ANSIBLE_DEPLOYMENT_SUMMARY.md) - Complete system overview
