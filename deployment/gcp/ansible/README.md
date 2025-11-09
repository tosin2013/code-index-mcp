---
# Code Index MCP - Ansible Deployment

Ansible role for deploying Code Index MCP Server to Google Cloud Run with optional AlloyDB integration.

## Architecture

- **Infrastructure**: Terraform provisions AlloyDB database
- **Application Deployment**: Ansible deploys Cloud Run service and configuration
- **Separation of Concerns**: Infrastructure-as-Code (Terraform) + Configuration Management (Ansible)

## Prerequisites

### Required Tools

```bash
# Ansible
pip install ansible

# Google Cloud SDK
brew install google-cloud-sdk  # macOS
# or download from https://cloud.google.com/sdk/docs/install

# Docker (for local builds)
brew install docker  # macOS

# Terraform (for AlloyDB provisioning)
brew install terraform  # macOS
```

### Required Ansible Collections

```bash
ansible-galaxy collection install google.cloud
ansible-galaxy collection install community.docker
```

### GCP Authentication

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set project
gcloud config set project YOUR_PROJECT_ID
```

## Quick Start

### 1. Provision AlloyDB (if using semantic search)

```bash
cd ../alloydb
terraform init
terraform apply
```

### 2. Configure Inventory

Edit `inventory/dev.yml` or `inventory/prod.yml`:

```yaml
all:
  vars:
    gcp_project_id: "YOUR_PROJECT_ID"
    gcp_region: "us-east1"
    with_alloydb: true  # Set to false to skip AlloyDB
```

### 3. Deploy

```bash
# Development environment
ansible-playbook deploy.yml -i inventory/dev.yml

# Production environment
ansible-playbook deploy.yml -i inventory/prod.yml
```

## Usage Examples

### Deploy to Development

```bash
ansible-playbook deploy.yml -i inventory/dev.yml
```

### Deploy Only Build and Cloud Run (skip schema)

```bash
ansible-playbook deploy.yml -i inventory/dev.yml --tags build,deploy
```

### Apply Only Database Schema

```bash
ansible-playbook deploy.yml -i inventory/dev.yml --tags schema
```

### Skip Schema Application

```bash
ansible-playbook deploy.yml -i inventory/dev.yml --skip-tags schema
```

### Dry Run

```bash
ansible-playbook deploy.yml -i inventory/dev.yml --check
```

### Verbose Output

```bash
ansible-playbook deploy.yml -i inventory/dev.yml -vv
```

## Utility Operations

In addition to deployment, there are utility operations for managing your deployment:

### Generate API Key

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key user_id=alice"
```

### Query Database

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=query_database"
```

### Verify Schema

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=verify_schema"
```

### Test Connection

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=test_connection"
```

### Teardown Resources

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown"
```

For complete utility documentation, see [UTILITIES.md](UTILITIES.md).

## Available Tags

- `prerequisites` - API enablement, registry setup
- `storage` - GCS bucket creation
- `iam` - Service account setup
- `secrets` - Webhook secret management
- `build` - Docker image building
- `deploy` - Cloud Run deployment
- `cloudrun` - Cloud Run specific tasks
- `schema` - Database schema application
- `database` - Database-related tasks
- `cleanup` - Cleanup scheduler setup
- `scheduler` - Cloud Scheduler tasks

## Configuration

### Environment Variables

Set in `inventory/{env}.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `gcp_project_id` | GCP Project ID | Required |
| `gcp_region` | Deployment region | `us-east1` |
| `environment` | Environment name | `dev` |
| `with_alloydb` | Enable AlloyDB | `true` |
| `cloudrun_cpu` | Cloud Run CPU | `2` |
| `cloudrun_memory` | Cloud Run memory | `2Gi` |
| `cloudrun_min_instances` | Min instances | `0` |
| `cloudrun_max_instances` | Max instances | `10` |

### AlloyDB Configuration

If `with_alloydb: true`:
- Ensures VPC connector exists
- Applies database schema
- Configures Cloud Run VPC access
- Sets AlloyDB connection secret

### Development vs Production

**Development (`inventory/dev.yml`)**:
- Smaller resources (1 CPU, 1Gi memory)
- Allow unauthenticated access
- Debug logging
- No auto-cleanup
- Aggressive bucket lifecycle (7 days)

**Production (`inventory/prod.yml`)**:
- Larger resources (4 CPU, 4Gi memory)
- Require authentication
- Info logging
- Auto-cleanup enabled
- Long bucket lifecycle (365 days)
- Min 1 instance (keep warm)
- Tracing enabled

## Role Structure

```
ansible/
├── deploy.yml                 # Main playbook
├── inventory/
│   ├── dev.yml               # Development inventory
│   └── prod.yml              # Production inventory
└── roles/
    └── code-index-mcp/
        ├── defaults/
        │   └── main.yml      # Default variables
        ├── tasks/
        │   ├── main.yml      # Main tasks orchestration
        │   ├── prerequisites.yml    # API enablement
        │   ├── storage.yml          # GCS buckets
        │   ├── service_account.yml  # IAM setup
        │   ├── webhook_secrets.yml  # Secret management
        │   ├── build_image.yml      # Docker build
        │   ├── deploy_cloudrun.yml  # Cloud Run deployment
        │   ├── apply_schema.yml     # Database schema
        │   └── cleanup_scheduler.yml # Auto-cleanup
        └── templates/
            ├── apply_schema.py.j2   # Schema applier
            └── Dockerfile.schema.j2  # Schema job image
```

## Workflow

1. **Prerequisites** (`prerequisites.yml`)
   - Enable required GCP APIs
   - Create Artifact Registry
   - Configure Docker authentication
   - Validate VPC connector (if AlloyDB enabled)

2. **Storage Setup** (`storage.yml`)
   - Create GCS buckets for projects and Git repos
   - Apply lifecycle policies

3. **Service Account** (`service_account.yml`)
   - Create service account for Cloud Run
   - Grant required IAM roles (Secret Manager, Storage, AI Platform, AlloyDB)

4. **Webhook Secrets** (`webhook_secrets.yml`)
   - Generate webhook secrets for GitHub/GitLab/Gitea
   - Store in Secret Manager
   - Grant service account access

5. **Build Image** (`build_image.yml`)
   - Build Docker image via Cloud Build or locally
   - Push to Artifact Registry
   - Verify image exists

6. **Deploy Cloud Run** (`deploy_cloudrun.yml`)
   - Deploy service with environment variables
   - Configure VPC networking (if AlloyDB)
   - Set secrets from Secret Manager
   - Wait for service readiness

7. **Apply Schema** (`apply_schema.yml`) - if AlloyDB enabled
   - Create schema applier job
   - Execute schema via Cloud Run Job
   - Verify schema application
   - Cleanup job

8. **Cleanup Scheduler** (`cleanup_scheduler.yml`) - if enabled
   - Create Cloud Scheduler job
   - Configure automatic cleanup of inactive projects

## Outputs

### Deployment Summary

A deployment summary file is created:
```
deployment-summary-{env}-{timestamp}.md
```

Contains:
- Service URL and SSE endpoint
- Claude Desktop configuration
- Resource details
- Next steps

### Claude Desktop Configuration

After successful deployment:

```json
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://your-service.run.app/sse",
      "transport": "sse"
    }
  }
}
```

Add to: `~/Library/Application Support/Claude/claude_desktop_config.json`

## Troubleshooting

### Check Deployment Status

```bash
gcloud run services describe code-index-mcp-dev \
  --region=us-east1 \
  --format='value(status.url,status.conditions[0].status)'
```

### View Logs

```bash
gcloud run services logs read code-index-mcp-dev --region=us-east1
```

### Test Service

```bash
curl https://your-service.run.app/health
```

### Verify AlloyDB Connection

```bash
# Check if VPC connector exists
gcloud compute networks vpc-access connectors list --region=us-east1

# Check AlloyDB secret
gcloud secrets versions access latest --secret=alloydb-connection-string
```

### Common Issues

**"VPC connector not found"**
- Solution: Provision AlloyDB with Terraform first
- Or set `with_alloydb: false` in inventory

**"Permission denied"**
- Solution: Check service account IAM roles
- Run: `gcloud projects get-iam-policy PROJECT_ID`

**"Build failed"**
- Solution: Check Dockerfile exists at project root
- Verify Docker authentication: `gcloud auth configure-docker`

**"Schema application failed"**
- Solution: Check AlloyDB connectivity
- Verify VPC connector is READY
- Check secret exists: `gcloud secrets describe alloydb-connection-string`

## Cost Estimates

### Development

| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (minimal usage) | ~$5 |
| AlloyDB (2 vCPU, 16 GB) | ~$164 |
| Storage (10 GB) | ~$2 |
| VPC Connector | ~$7 |
| **Total** | **~$178/month** |

### Production

| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (with traffic) | ~$20-50 |
| AlloyDB (4 vCPU, 32 GB) | ~$350 |
| Storage (100 GB) | ~$20 |
| VPC Connector | ~$7 |
| **Total** | **~$397-427/month** |

## Comparison: Bash Scripts vs Ansible

### Why Ansible?

| Feature | Bash Scripts | Ansible |
|---------|--------------|---------|
| **Idempotency** | Manual checks | Built-in |
| **Error Handling** | Manual `set -e` | Comprehensive |
| **Rollback** | Manual | Automatic |
| **State Management** | None | Declarative |
| **Testing** | Difficult | `--check` mode |
| **Reusability** | Copy-paste | Roles & collections |
| **Documentation** | Comments | Self-documenting YAML |
| **Parallelism** | Manual | Automatic |
| **Secrets** | Plaintext or manual | Vault integration |

### Migration Benefits

1. **Idempotency**: Re-running is safe
2. **Consistency**: Same result every time
3. **Extensibility**: Easy to add new environments
4. **Visibility**: Clear task progress
5. **Maintainability**: YAML vs complex bash
6. **Testing**: Dry-run before deployment
7. **CI/CD Integration**: Ansible Tower/AWX support

## Integration with Terraform

### Recommended Workflow

```bash
# 1. Provision infrastructure with Terraform
cd ../alloydb
terraform init
terraform apply

# 2. Deploy application with Ansible
cd ../ansible
ansible-playbook deploy.yml -i inventory/prod.yml

# 3. Verify deployment
curl https://your-service.run.app/health
```

### State Management

- **Terraform**: Manages infrastructure state (AlloyDB, VPC, networks)
- **Ansible**: Manages configuration state (Cloud Run, secrets, schemas)
- **No Overlap**: Clean separation of responsibilities

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Ansible
        run: pip install ansible

      - name: Install collections
        run: |
          ansible-galaxy collection install google.cloud
          ansible-galaxy collection install community.docker

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Deploy
        run: |
          cd deployment/gcp/ansible
          ansible-playbook deploy.yml -i inventory/prod.yml
```

## Support

For issues or questions:
- Check [Troubleshooting](#troubleshooting) section
- Review Ansible output with `-vv` flag
- Check Cloud Run logs
- Open issue at: [GitHub Issues](https://github.com/your-repo/issues)

---

**Status**: Production-ready ✅
**Last Updated**: October 29, 2025
**Maintained By**: Code Index MCP Team
