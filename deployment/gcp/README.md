# GCP Deployment

This directory contains infrastructure and deployment automation for Code Index MCP on Google Cloud Platform.

## Quick Start

**NEW: Automated end-to-end deployment** (recommended):

```bash
# One command to deploy everything
./deploy-lifecycle.sh --user-email your@email.com
```

This automated script handles the complete deployment lifecycle including prerequisites checking, security setup, infrastructure deployment, verification, and API key generation. Deployment takes ~30-40 minutes.

See [DEPLOYMENT_LIFECYCLE.md](../../DEPLOYMENT_LIFECYCLE.md) for detailed documentation.

**Alternative: Manual Ansible deployment**:

```bash
cd ansible
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes"
```

## Directory Structure

```
deployment/gcp/
├── deploy-lifecycle.sh         # 🚀 NEW: End-to-end automated deployment
│
├── ansible/                    # 🛠️ Application deployment automation
│   ├── deploy.yml             # Main deployment playbook
│   ├── utilities.yml          # Utility operations
│   ├── quickstart.sh          # Interactive setup
│   ├── README.md              # Complete deployment guide
│   └── roles/                 # Ansible roles
│
├── terraform/                  # 🔧 Infrastructure (AlloyDB, VPC)
│   ├── main.tf
│   ├── alloydb-schema.sql
│   └── ...
│
├── test-*.sh                   # 🧪 Local development tests
│
└── docs/                       # 📚 Documentation
    ├── ANSIBLE_DEPLOYMENT_SUMMARY.md
    ├── ANSIBLE_MIGRATION_GUIDE.md
    └── BASH_TO_ANSIBLE_MIGRATION.md
```

## Deployment Methods

### 1. Automated End-to-End (Recommended) 🚀

**NEW**: The `deploy-lifecycle.sh` script automates the complete deployment lifecycle.

**Use when**:
- First-time deployment
- Complete environment setup needed
- Want guided deployment with verification
- CI/CD automation

**Features**:
- ✅ Prerequisites checking (gcloud, ansible, terraform, etc.)
- ✅ GCP authentication verification
- ✅ Pre-commit hooks setup
- ✅ Complete infrastructure deployment
- ✅ Automatic verification
- ✅ API key generation
- ✅ Claude Desktop configuration

**Quick commands**:
```bash
# Basic deployment
./deploy-lifecycle.sh --user-email admin@example.com

# Deploy to specific environment
./deploy-lifecycle.sh \
  --environment staging \
  --project-id my-project \
  --user-email admin@example.com

# Fully automated (CI/CD)
./deploy-lifecycle.sh \
  --user-email ci@example.com \
  --auto-approve
```

**Documentation**:
- [DEPLOYMENT_LIFECYCLE.md](../../DEPLOYMENT_LIFECYCLE.md) - Complete guide
- Script includes `--help` for all options

### 2. Ansible (Manual Method) 🛠️

**For**: Fine-grained control, partial deployments, utilities

**Use when**:
- Deploying only Cloud Run service
- Running specific utility operations
- Troubleshooting or debugging
- Need customization

**Documentation**:
- [ansible/README.md](ansible/README.md) - Complete deployment guide
- [ansible/UTILITIES.md](ansible/UTILITIES.md) - Utility operations
- [ANSIBLE_DEPLOYMENT_SUMMARY.md](ANSIBLE_DEPLOYMENT_SUMMARY.md) - Overview

**Quick commands**:
```bash
cd ansible

# Deploy everything
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes"

# Generate API key
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key" \
  -e "user_email=alice@example.com"

# Test database connection
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=test_connection"
```

### 3. Terraform (Infrastructure) 🔧

**For**: Long-lived infrastructure (AlloyDB, VPC, network)

**Use when**:
- Provisioning AlloyDB database cluster
- Setting up VPC networking
- Creating infrastructure resources

**Documentation**:
- [terraform/README.md](terraform/README.md) (if exists)

**Quick commands**:
```bash
cd terraform

# Provision AlloyDB
terraform init
terraform apply

# Destroy AlloyDB
terraform destroy
```

## Common Workflows

### Initial Setup (Recommended: Automated)

**Easiest way** - One command for complete setup:

```bash
# Automated end-to-end deployment
./deploy-lifecycle.sh --user-email admin@example.com
```

This handles everything: prerequisites, infrastructure, deployment, verification, and API key generation.

**Manual way** - Step-by-step control:

```bash
# 1. Provision infrastructure (handled by Ansible now)
cd ansible
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes"

# 2. Generate API key
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key" \
  -e "user_email=admin@example.com"
```

### Update Deployment

```bash
cd ansible
ansible-playbook deploy.yml -i inventory/dev.yml
```

### Generate User API Key

```bash
cd ansible
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key user_id=john-doe"
```

### Check Database Health

```bash
cd ansible
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=test_connection"
```

### Teardown Application (Keep Database)

```bash
cd ansible
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown"
```

### Full Teardown (Including Database)

```bash
# 1. Delete application
cd ansible
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown delete_buckets=true auto_approve=true"

# 2. Destroy infrastructure
cd ../terraform
terraform destroy
```

## Migration from Bash Scripts

All bash deployment scripts have been migrated to Ansible. See:
- [BASH_TO_ANSIBLE_MIGRATION.md](BASH_TO_ANSIBLE_MIGRATION.md) - Complete migration guide
- [ANSIBLE_MIGRATION_GUIDE.md](ANSIBLE_MIGRATION_GUIDE.md) - Detailed comparison

**Old command → New command:**

```bash
# OLD: ./deploy.sh dev --with-alloydb
# NEW:
cd ansible && ansible-playbook deploy.yml -i inventory/dev.yml

# OLD: ./generate-api-key.sh alice dev
# NEW:
cd ansible && ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key user_id=alice"

# OLD: ./destroy.sh dev
# NEW:
cd ansible && ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown"
```

## Testing

Local testing scripts are preserved for development:

```bash
# Test local Docker setup
./test-local.sh

# Test local PostgreSQL
./test-local-postgres.sh

# Test schema validation
./test-adr-schema.sh
```

## Documentation

### Deployment Guides
- [ansible/README.md](ansible/README.md) - Complete Ansible deployment guide
- [ansible/UTILITIES.md](ansible/UTILITIES.md) - Utility operations guide
- [ansible/quickstart.sh](ansible/quickstart.sh) - Interactive setup script

### Architecture & Migration
- [ANSIBLE_DEPLOYMENT_SUMMARY.md](ANSIBLE_DEPLOYMENT_SUMMARY.md) - System overview
- [ANSIBLE_MIGRATION_GUIDE.md](ANSIBLE_MIGRATION_GUIDE.md) - Bash to Ansible migration
- [BASH_TO_ANSIBLE_MIGRATION.md](BASH_TO_ANSIBLE_MIGRATION.md) - Command mapping

## Troubleshooting

### "I used to run ./deploy.sh, what now?"

```bash
cd ansible
ansible-playbook deploy.yml -i inventory/dev.yml
```

Or use the interactive setup:
```bash
cd ansible
./quickstart.sh
```

### "Where did my bash script go?"

See [BASH_TO_ANSIBLE_MIGRATION.md](BASH_TO_ANSIBLE_MIGRATION.md) for the complete mapping.

### "How do I test without deploying?"

```bash
cd ansible
ansible-playbook deploy.yml -i inventory/dev.yml --check
```

### "I need help!"

1. Read [ansible/README.md](ansible/README.md) - Complete deployment guide
2. Check [ansible/UTILITIES.md](ansible/UTILITIES.md) - Utility operations
3. See [BASH_TO_ANSIBLE_MIGRATION.md](BASH_TO_ANSIBLE_MIGRATION.md) - Command mapping

## Architecture

### Separation of Concerns

```
┌─────────────────────────────────────────┐
│         Infrastructure Layer            │
│         (Terraform)                     │
│  • AlloyDB cluster & instance           │
│  • VPC network & subnets                │
│  • Private service connection           │
│  • Static infrastructure                │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      Application/Config Layer           │
│      (Ansible)                          │
│  • Cloud Run deployment                 │
│  • Docker image building                │
│  • GCS bucket management                │
│  • Secret management                    │
│  • Schema application                   │
│  • Runtime configuration                │
└─────────────────────────────────────────┘
```

**Why this split?**
- **Terraform**: Infrastructure is long-lived, rarely changed (~monthly)
- **Ansible**: Application is frequently deployed, updated (~daily)

## Cost Estimates

### Development
- Cloud Run: ~$5/month (scales to zero)
- AlloyDB: ~$180/month (2 vCPU, 16 GB)
- Storage: ~$2/month
- VPC Connector: ~$7/month
- **Total**: ~$194/month

### Production
- Cloud Run: ~$20-50/month (with traffic)
- AlloyDB: ~$350/month (4 vCPU, 32 GB)
- Storage: ~$20/month
- VPC Connector: ~$7/month
- **Total**: ~$397-427/month

To minimize costs:
- Scale Cloud Run to zero when idle (dev default)
- Use smaller AlloyDB instance for dev
- Enable automatic cleanup of old data

## Support

For issues or questions:
- Check [ansible/README.md](ansible/README.md) for detailed guide
- Review [BASH_TO_ANSIBLE_MIGRATION.md](BASH_TO_ANSIBLE_MIGRATION.md) for command mapping
- Run with `-vvv` for debug output

---

**Last Updated**: October 29, 2025
**Maintained By**: Code Index MCP Team
