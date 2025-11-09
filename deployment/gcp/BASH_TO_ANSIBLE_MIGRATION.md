# Bash Scripts → Ansible Migration

**Date**: October 29, 2025
**Status**: ✅ Complete

---

## Summary

All bash deployment and utility scripts have been migrated to Ansible roles. This provides better idempotency, error handling, testing, and maintainability.

## Migration Map

### Deployment Scripts → Ansible Role: code-index-mcp

| Old Bash Script | New Ansible Task | Location |
|----------------|------------------|----------|
| `deploy.sh` | `deploy_cloudrun.yml` | `ansible/roles/code-index-mcp/tasks/` |
| `apply-schema-job.sh` | `apply_schema.yml` | `ansible/roles/code-index-mcp/tasks/` |
| `apply-schema.sh` | Integrated into `apply_schema.yml` | `ansible/roles/code-index-mcp/tasks/` |
| `setup-service-account.sh` | `service_account.yml` | `ansible/roles/code-index-mcp/tasks/` |
| `setup-secrets.sh` | `webhook_secrets.yml` | `ansible/roles/code-index-mcp/tasks/` |
| `setup-webhook-secrets.sh` | `webhook_secrets.yml` | `ansible/roles/code-index-mcp/tasks/` |

**Usage:**
```bash
cd deployment/gcp/ansible

# Full deployment
ansible-playbook deploy.yml -i inventory/dev.yml

# Apply schema only
ansible-playbook deploy.yml -i inventory/dev.yml --tags schema

# Deploy without schema
ansible-playbook deploy.yml -i inventory/dev.yml --skip-tags schema
```

---

### Utility Scripts → Ansible Role: utilities

| Old Bash Script | New Ansible Task | Location |
|----------------|------------------|----------|
| `generate-api-key.sh` | `generate_api_key.yml` | `ansible/roles/utilities/tasks/` |
| `query-database.sh` | `query_database.yml` | `ansible/roles/utilities/tasks/` |
| `verify-schema.sh` | `verify_schema.yml` | `ansible/roles/utilities/tasks/` |
| `test-alloydb-connection.sh` | `test_connection.yml` | `ansible/roles/utilities/tasks/` |
| `destroy.sh` | `teardown.yml` | `ansible/roles/utilities/tasks/` |

**Usage:**
```bash
cd deployment/gcp/ansible

# Generate API key
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=generate_api_key user_id=alice"

# Query database
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=query_database"

# Test connection
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=test_connection"

# Teardown
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=teardown"
```

---

### AlloyDB Scripts → Terraform (No Change)

| Bash Script | Migration Status | Notes |
|------------|------------------|-------|
| `setup-alloydb.sh` | ❌ Removed | Use `terraform apply` instead |
| `destroy-alloydb.sh` | ❌ Removed | Use `terraform destroy` instead |
| `create-connection-string-secret.sh` | ❌ Removed | Terraform handles this |

**Rationale**: AlloyDB is infrastructure (long-lived, rarely changes) → Keep in Terraform

**Usage:**
```bash
cd deployment/gcp

# Provision AlloyDB
terraform init
terraform apply

# Destroy AlloyDB
terraform destroy
```

---

### Migration Scripts → Completed (Removed)

| Bash Script | Status | Notes |
|------------|--------|-------|
| `apply-git-provenance-job.sh` | ✅ Completed & Removed | One-time migration, no longer needed |
| `apply-git-provenance-migration.sh` | ✅ Completed & Removed | One-time migration, no longer needed |

---

### Test Scripts → Kept for Local Development

| Bash Script | Status | Notes |
|------------|--------|-------|
| `test-local.sh` | ✅ Kept | Local docker-compose testing |
| `test-local-postgres.sh` | ✅ Kept | Local PostgreSQL testing |
| `test-adr-schema.sh` | ✅ Kept | Schema validation testing |
| `test-cleanup-local.sh` | ✅ Kept | Local cleanup testing |

**Why keep these?**
- Used for local development without cloud costs
- Developers need quick local testing before deploying
- Not deployment-critical, won't interfere with production

---

## Benefits of Ansible Migration

### 1. Idempotency

**Before (Bash)**:
```bash
# May fail if service already exists
gcloud run services create code-index-mcp ...
```

**After (Ansible)**:
```yaml
# Automatically detects if service exists and updates it
- name: Deploy Cloud Run service
  ansible.builtin.shell: |
    gcloud run deploy {{ service_name }} ...
  register: deploy_result
  changed_when: "'Deploying' in deploy_result.stderr"
```

### 2. Error Handling

**Before (Bash)**:
```bash
set -e  # Stop on any error
gcloud run deploy ... || exit 1
```

**After (Ansible)**:
```yaml
- name: Deploy Cloud Run service
  ansible.builtin.shell: ...
  register: deploy_result
  failed_when: deploy_result.rc != 0
  retries: 3
  delay: 10
```

### 3. Environment Management

**Before (Bash)**:
```bash
if [ "$ENVIRONMENT" == "prod" ]; then
  CPU="4"
else
  CPU="2"
fi
```

**After (Ansible)**:
```yaml
# inventory/prod.yml
cloudrun_cpu: "4"

# inventory/dev.yml
cloudrun_cpu: "2"
```

### 4. Testing

**Before (Bash)**:
```bash
# No built-in testing
./deploy.sh dev  # Hope it works!
```

**After (Ansible)**:
```bash
# Dry run - see what would change
ansible-playbook deploy.yml -i inventory/dev.yml --check

# Syntax validation
ansible-playbook deploy.yml --syntax-check

# List tasks
ansible-playbook deploy.yml --list-tasks
```

### 5. Selective Execution

**Before (Bash)**:
```bash
# Run entire script or manually comment out sections
./deploy.sh dev
```

**After (Ansible)**:
```bash
# Run specific parts
ansible-playbook deploy.yml -i inventory/dev.yml --tags build,deploy
ansible-playbook deploy.yml -i inventory/dev.yml --skip-tags schema
```

---

## Quick Reference

### Old Command → New Command

#### Deployment

```bash
# OLD
./deploy.sh dev --with-alloydb

# NEW
cd ansible && ansible-playbook deploy.yml -i inventory/dev.yml
```

#### Schema Application

```bash
# OLD
./apply-schema-job.sh dev

# NEW
cd ansible && ansible-playbook deploy.yml -i inventory/dev.yml --tags schema
```

#### API Key Generation

```bash
# OLD
./generate-api-key.sh alice dev

# NEW
cd ansible && ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key user_id=alice"
```

#### Database Query

```bash
# OLD
./query-database.sh

# NEW
cd ansible && ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=query_database"
```

#### Connection Test

```bash
# OLD
./test-alloydb-connection.sh

# NEW
cd ansible && ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=test_connection"
```

#### Teardown

```bash
# OLD
./destroy.sh dev

# NEW
cd ansible && ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown"
```

#### AlloyDB Setup/Teardown

```bash
# OLD
./setup-alloydb.sh dev
./destroy-alloydb.sh dev

# NEW
terraform init
terraform apply
terraform destroy
```

---

## Migration Checklist

### ✅ Completed

- [x] Created Ansible role: `code-index-mcp`
- [x] Created Ansible role: `utilities`
- [x] Migrated all deployment scripts
- [x] Migrated all utility scripts
- [x] Created environment inventories (dev, prod)
- [x] Removed deprecated bash scripts
- [x] Created comprehensive documentation
- [x] Added quick start script (`quickstart.sh`)
- [x] Created utilities guide

### 📝 Documentation

- [x] Main deployment README
- [x] Ansible migration guide
- [x] Deployment summary
- [x] Utilities guide
- [x] Bash-to-Ansible migration map (this document)

---

## Troubleshooting

### "I used to run ./deploy.sh, what now?"

```bash
cd deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml
```

Or use the quick start:
```bash
cd deployment/gcp/ansible
./quickstart.sh
```

### "Where did my bash script go?"

Check the [Migration Map](#migration-map) above to find the equivalent Ansible command.

### "I need to run just one part of deployment"

Use tags:
```bash
# Just build image
ansible-playbook deploy.yml -i inventory/dev.yml --tags build

# Just deploy Cloud Run
ansible-playbook deploy.yml -i inventory/dev.yml --tags deploy

# Everything except schema
ansible-playbook deploy.yml -i inventory/dev.yml --skip-tags schema
```

### "How do I test without actually deploying?"

```bash
# Dry run (check mode)
ansible-playbook deploy.yml -i inventory/dev.yml --check
```

### "I want to see what will happen"

```bash
# List all tasks
ansible-playbook deploy.yml --list-tasks

# Verbose output
ansible-playbook deploy.yml -i inventory/dev.yml -vvv
```

---

## Repository Structure After Migration

```
deployment/gcp/
├── ansible/                          # 🆕 PRIMARY DEPLOYMENT METHOD
│   ├── deploy.yml                   # Main deployment playbook
│   ├── utilities.yml                # Utilities playbook
│   ├── quickstart.sh                # Interactive setup
│   ├── README.md                    # Full deployment guide
│   ├── UTILITIES.md                 # Utilities guide
│   ├── ansible.cfg                  # Ansible configuration
│   ├── requirements.yml             # Required Ansible collections
│   ├── inventory/
│   │   ├── dev.yml                  # Development environment
│   │   └── prod.yml                 # Production environment
│   └── roles/
│       ├── code-index-mcp/          # Main deployment role
│       │   ├── defaults/main.yml
│       │   ├── tasks/
│       │   │   ├── main.yml
│       │   │   ├── prerequisites.yml
│       │   │   ├── storage.yml
│       │   │   ├── service_account.yml
│       │   │   ├── webhook_secrets.yml
│       │   │   ├── build_image.yml
│       │   │   ├── deploy_cloudrun.yml
│       │   │   ├── apply_schema.yml
│       │   │   └── cleanup_scheduler.yml
│       │   └── templates/
│       │       ├── apply_schema.py.j2
│       │       └── Dockerfile.schema.j2
│       └── utilities/                # Utilities role
│           ├── defaults/main.yml
│           └── tasks/
│               ├── main.yml
│               ├── generate_api_key.yml
│               ├── query_database.yml
│               ├── verify_schema.yml
│               ├── test_connection.yml
│               └── teardown.yml
│
├── terraform/                        # 🔧 INFRASTRUCTURE (AlloyDB)
│   ├── main.tf                      # Terraform configuration
│   ├── variables.tf
│   ├── outputs.tf
│   └── alloydb-schema.sql
│
├── test-*.sh                         # ✅ KEPT for local development
│
├── ANSIBLE_MIGRATION_GUIDE.md       # Migration from bash
├── ANSIBLE_DEPLOYMENT_SUMMARY.md    # Complete overview
└── BASH_TO_ANSIBLE_MIGRATION.md     # This document
```

---

## Next Steps

1. **Try the new Ansible deployment**:
   ```bash
   cd deployment/gcp/ansible
   ./quickstart.sh
   ```

2. **Read the full documentation**:
   - [README.md](ansible/README.md) - Complete deployment guide
   - [UTILITIES.md](ansible/UTILITIES.md) - Utility operations
   - [ANSIBLE_MIGRATION_GUIDE.md](ANSIBLE_MIGRATION_GUIDE.md) - Detailed migration guide

3. **Test your workflows**:
   ```bash
   # Dry run
   ansible-playbook deploy.yml -i inventory/dev.yml --check

   # List tasks
   ansible-playbook deploy.yml --list-tasks

   # Deploy
   ansible-playbook deploy.yml -i inventory/dev.yml
   ```

---

**Migration completed successfully!** 🎉

All bash scripts have been replaced with Ansible for better maintainability, testability, and reliability.

---

**Last Updated**: October 29, 2025
**Maintained By**: Code Index MCP Team
