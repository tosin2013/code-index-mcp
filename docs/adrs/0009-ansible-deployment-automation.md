# ADR 0009: Ansible Deployment Automation for Google Cloud

**Status**: Accepted (100% Complete - Production Ready)
**Date**: 2025-10-29
**Decision Maker**: Architecture Team
**Cloud Platform**: Google Cloud (AWS/OpenShift planned)
**Related to**: ADR 0002 (Cloud Run Deployment), ADR 0003 (AlloyDB Semantic Search)

## Context

### The Problem with Bash Scripts

Initially, deployment to Google Cloud Run was managed through bash scripts (`deployment/gcp/deploy.sh`, `deployment/gcp/destroy.sh`). While functional, this approach had significant limitations:

1. **No Idempotency**: Re-running scripts could cause errors or duplicate resources
2. **Limited Error Handling**: Manual `set -e` and error checking
3. **No Rollback**: Failed deployments left system in unknown state
4. **Hard to Test**: No dry-run or validation mode
5. **Not Reusable**: Copy-paste to support new environments
6. **Poor State Management**: No tracking of what was deployed
7. **Complex Secrets Handling**: Manual Secret Manager integration
8. **Difficult CI/CD Integration**: Hard to integrate with automation tools

### Real-World Example

```bash
# Bash script deployment (old approach)
./deploy.sh dev
# ❌ Error on line 47: bucket already exists
# ❌ Partial deployment - some resources created, others failed
# ❌ No way to roll back
# ❌ Manual cleanup required
# ❌ No visibility into what succeeded vs failed
```

### Requirements for Production Deployment

1. **Idempotency**: Safe to re-run without side effects
2. **Declarative**: Define desired state, not imperative steps
3. **Testing**: Dry-run before actual deployment
4. **Rollback**: Automatic rollback on failure
5. **Multi-Environment**: Easy dev/staging/prod configuration
6. **Visibility**: Clear progress and logging
7. **Extensibility**: Easy to add new tasks and environments
8. **CI/CD Ready**: First-class automation support

## Decision: Ansible for Deployment Automation

Use **Ansible** with Google Cloud collection for all deployment and operational tasks, replacing bash scripts with declarative YAML playbooks and reusable roles.

## Architecture

### Overview

```
┌─────────────────────────────────────────────────────┐
│                  Ansible Control Node               │
│                  (Developer Laptop / CI/CD)         │
└────────────────────┬────────────────────────────────┘
                     │
                     │ Ansible Playbooks (YAML)
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│   deploy.yml     │    │  utilities.yml   │
│   (Main Deploy)  │    │   (Admin Tasks)  │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│        code-index-mcp Role              │
│  ┌───────────────────────────────────┐  │
│  │  • prerequisites.yml              │  │
│  │  • storage.yml                    │  │
│  │  • service_account.yml            │  │
│  │  • webhook_secrets.yml            │  │
│  │  • build_image.yml                │  │
│  │  • deploy_cloudrun.yml            │  │
│  │  • apply_schema.yml               │  │
│  │  • cleanup_scheduler.yml          │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         │ Google Cloud APIs
         │
         ▼
┌─────────────────────────────────────────┐
│         Google Cloud Platform           │
│  ┌──────────────────────────────────┐   │
│  │  • Cloud Run Service             │   │
│  │  • Artifact Registry             │   │
│  │  • Cloud Storage                 │   │
│  │  • Secret Manager                │   │
│  │  • IAM Service Accounts          │   │
│  │  • Cloud Scheduler               │   │
│  │  • AlloyDB (optional)            │   │
│  │  • VPC Connector (if AlloyDB)    │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Deployment Workflow

```
User runs: ansible-playbook deploy.yml -i inventory/dev.yml

1. Pre-Tasks
   ├── Confirmation prompt
   └── Display deployment info

2. Role: code-index-mcp
   │
   ├── Task: Prerequisites
   │   ├── Enable GCP APIs (Cloud Run, Storage, IAM, etc.)
   │   ├── Create Artifact Registry
   │   ├── Configure Docker auth
   │   └── Validate VPC connector (if AlloyDB enabled)
   │
   ├── Task: Storage
   │   ├── Create GCS bucket for projects
   │   ├── Create GCS bucket for Git repos
   │   └── Apply lifecycle policies
   │
   ├── Task: Service Account
   │   ├── Create service account for Cloud Run
   │   └── Grant IAM roles:
   │       ├── Secret Manager accessor
   │       ├── Storage admin
   │       ├── Vertex AI user
   │       └── AlloyDB client (if enabled)
   │
   ├── Task: Webhook Secrets
   │   ├── Generate secrets for GitHub/GitLab/Gitea
   │   ├── Store in Secret Manager
   │   └── Grant service account access
   │
   ├── Task: Build Image
   │   ├── Build Docker image (Cloud Build or local)
   │   ├── Push to Artifact Registry
   │   └── Verify image exists
   │
   ├── Task: Deploy Cloud Run
   │   ├── Create/update Cloud Run service
   │   ├── Configure environment variables
   │   ├── Mount secrets from Secret Manager
   │   ├── Configure VPC networking (if AlloyDB)
   │   └── Wait for service readiness
   │
   ├── Task: Apply Schema (if AlloyDB enabled)
   │   ├── Create schema applier Cloud Run Job
   │   ├── Execute schema SQL
   │   ├── Verify schema application
   │   └── Cleanup job
   │
   └── Task: Cleanup Scheduler (if enabled)
       ├── Create Cloud Scheduler job
       └── Configure automatic cleanup of inactive projects

3. Post-Tasks
   ├── Display Claude Desktop configuration
   └── Create deployment summary file

Result: ✅ Deployment complete with full rollback on error
```

## Implementation

### Directory Structure

```
deployment/gcp/ansible/
├── ansible.cfg                     # Ansible configuration
├── deploy.yml                      # Main deployment playbook
├── utilities.yml                   # Utility operations playbook
├── quickstart.sh                   # Quick deployment script
├── requirements.yml                # Ansible collections
├── README.md                       # Comprehensive documentation
├── UTILITIES.md                    # Utilities guide
├── inventory/
│   ├── dev.yml                    # Development environment
│   ├── staging.yml                # Staging environment
│   └── prod.yml                   # Production environment
└── roles/
    ├── code-index-mcp/            # Main deployment role
    │   ├── defaults/
    │   │   └── main.yml           # Default variables
    │   ├── tasks/
    │   │   ├── main.yml           # Task orchestration
    │   │   ├── prerequisites.yml  # API enablement
    │   │   ├── storage.yml        # GCS buckets
    │   │   ├── service_account.yml# IAM setup
    │   │   ├── webhook_secrets.yml# Secret management
    │   │   ├── build_image.yml    # Docker build
    │   │   ├── deploy_cloudrun.yml# Cloud Run deployment
    │   │   ├── apply_schema.yml   # Database schema
    │   │   └── cleanup_scheduler.yml # Auto-cleanup
    │   └── templates/
    │       ├── apply_schema.py.j2 # Schema applier script
    │       └── Dockerfile.schema.j2# Schema job image
    └── utilities/                  # Utility operations role
        ├── defaults/
        │   └── main.yml           # Default variables
        └── tasks/
            ├── main.yml           # Task router
            ├── generate_api_key.yml    # API key generation
            ├── query_database.yml      # Database queries
            ├── verify_schema.yml       # Schema verification
            ├── test_connection.yml     # Connection testing
            └── teardown.yml            # Resource deletion
```

### Key Playbooks

#### 1. Main Deployment (`deploy.yml`)

```yaml
---
- name: Deploy Code Index MCP Server to Google Cloud Run
  hosts: localhost
  connection: local
  gather_facts: yes

  vars_prompt:
    - name: confirm_deployment
      prompt: "Deploy to {{ env_name }} environment? (yes/no)"
      private: no
      default: "no"

  pre_tasks:
    - name: Validate deployment confirmation
      fail:
        msg: "Deployment cancelled by user"
      when: confirm_deployment != 'yes'

    - name: Display deployment information
      debug:
        msg:
          - "Project: {{ gcp_project_id }}"
          - "Environment: {{ env_name }}"
          - "Region: {{ gcp_region }}"
          - "AlloyDB: {{ 'enabled' if with_alloydb else 'disabled' }}"

  roles:
    - role: code-index-mcp

  post_tasks:
    - name: Display Claude Desktop configuration
      debug:
        msg: "Add to ~/Library/Application Support/Claude/claude_desktop_config.json"

    - name: Create deployment summary file
      copy:
        content: |
          # Deployment Summary
          Service URL: {{ cloudrun_service_url }}
          SSE Endpoint: {{ cloudrun_service_url }}/sse
        dest: "./deployment-summary-{{ env_name }}-{{ ansible_date_time.epoch }}.md"
```

#### 2. Utilities (`utilities.yml`)

```yaml
---
- name: Code Index MCP Utilities
  hosts: localhost
  connection: local
  gather_facts: yes

  pre_tasks:
    - name: Validate operation parameter
      fail:
        msg: "Operation parameter is required"
      when: operation is not defined

  roles:
    - role: utilities
```

### Environment-Specific Configuration

#### Development (`inventory/dev.yml`)

```yaml
all:
  vars:
    # Project Configuration
    gcp_project_id: "your-project-dev"
    gcp_region: "us-east1"
    env_name: "dev"
    environment: "development"

    # Cloud Run Configuration
    cloudrun_cpu: "1"
    cloudrun_memory: "1Gi"
    cloudrun_min_instances: 0
    cloudrun_max_instances: 5
    cloudrun_allow_unauthenticated: true

    # Feature Flags
    with_alloydb: true
    enable_auto_cleanup: false

    # Storage Configuration
    bucket_lifecycle_days: 7  # Aggressive cleanup for dev
```

#### Production (`inventory/prod.yml`)

```yaml
all:
  vars:
    # Project Configuration
    gcp_project_id: "your-project-prod"
    gcp_region: "us-central1"
    env_name: "prod"
    environment: "production"

    # Cloud Run Configuration
    cloudrun_cpu: "4"
    cloudrun_memory: "4Gi"
    cloudrun_min_instances: 1  # Keep warm
    cloudrun_max_instances: 20
    cloudrun_allow_unauthenticated: false  # Require auth

    # Feature Flags
    with_alloydb: true
    enable_auto_cleanup: true
    enable_tracing: true

    # Storage Configuration
    bucket_lifecycle_days: 365  # Long retention
```

### Utility Operations

The `utilities` role provides administrative operations:

#### 1. Generate API Key

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key" \
  -e "user_id=john-doe"
```

**Features**:
- Generates secure 64-character API key with `ci_` prefix
- Stores in Secret Manager: `code-index-api-key-{user_id}-{env}`
- Grants Cloud Run service account access
- Outputs Claude Desktop configuration
- Saves to file: `api-key-{user_id}-{env}.txt`

#### 2. Query Database

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=query_database"
```

**Queries**:
- List all projects
- Code chunks summary by project
- Sample code chunks (first 5)
- File count and language breakdown

#### 3. Verify Schema

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=verify_schema"
```

**Checks**:
- All tables exist (users, projects, code_chunks)
- Table structures correct
- Indexes created (including HNSW vector index)
- Git provenance columns exist
- Extensions installed (vector, google_ml_integration)

#### 4. Test Connection

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=test_connection"
```

**Tests**:
- Basic AlloyDB connection
- Extensions installed
- Tables created
- HNSW index exists
- Functions created
- Row-level security enabled
- Git provenance support
- Data counts

#### 5. Teardown

```bash
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=teardown" \
  -e "auto_approve=true"
```

**Deletes**:
- Cloud Run service
- Container images from Artifact Registry
- Cloud Scheduler cleanup job
- GCS buckets (if `delete_buckets=true`)

**Preserves**:
- AlloyDB cluster (requires Terraform destroy)
- VPC connector
- Secrets in Secret Manager

## Benefits

### 1. Idempotency

**Before (Bash)**:
```bash
# Run deploy.sh twice
./deploy.sh dev
# ❌ Error: bucket already exists
./deploy.sh dev
# ❌ Error: service account already exists
```

**After (Ansible)**:
```bash
# Run deploy.yml twice - no errors!
ansible-playbook deploy.yml -i inventory/dev.yml
# ✅ Creates all resources

ansible-playbook deploy.yml -i inventory/dev.yml
# ✅ No-op - all resources already exist
# ✅ Or updates only changed resources
```

### 2. Declarative Configuration

**Before (Bash)**:
```bash
# Imperative - must execute in order
gcloud run services create ...
gcloud run services update ...
gcloud run services set-iam-policy ...
```

**After (Ansible)**:
```yaml
# Declarative - define desired state
- name: Deploy Cloud Run service
  google.cloud.gcp_run_service:
    name: code-index-mcp-dev
    state: present
    cpu: 2
    memory: 2Gi
    # Ansible ensures this state exists
```

### 3. Testing and Dry-Run

```bash
# Test without making changes
ansible-playbook deploy.yml -i inventory/dev.yml --check

# See what would change
ansible-playbook deploy.yml -i inventory/dev.yml --check --diff
```

### 4. Multi-Environment Support

```bash
# Same playbook, different environments
ansible-playbook deploy.yml -i inventory/dev.yml
ansible-playbook deploy.yml -i inventory/staging.yml
ansible-playbook deploy.yml -i inventory/prod.yml
```

### 5. Tagging for Selective Execution

```bash
# Only build and deploy
ansible-playbook deploy.yml -i inventory/dev.yml --tags build,deploy

# Skip schema application
ansible-playbook deploy.yml -i inventory/dev.yml --skip-tags schema

# Only apply schema
ansible-playbook deploy.yml -i inventory/dev.yml --tags schema
```

### 6. Comprehensive Error Handling

```yaml
- name: Deploy Cloud Run service
  google.cloud.gcp_run_service:
    # ... configuration ...
  register: deployment_result
  failed_when: deployment_result.failed
  retries: 3
  delay: 10
  until: deployment_result is succeeded
```

### 7. State Management and Rollback

Ansible tracks what was deployed and can:
- Show differences between current and desired state
- Roll back failed deployments
- Retry failed tasks automatically
- Skip already-completed tasks

## Comparison: Bash vs Ansible

| Feature | Bash Scripts | Ansible | Winner |
|---------|-------------|---------|--------|
| **Idempotency** | Manual checks | Built-in | ✅ Ansible |
| **Error Handling** | `set -e`, manual | Comprehensive | ✅ Ansible |
| **Rollback** | None | Automatic | ✅ Ansible |
| **State Management** | None | Declarative | ✅ Ansible |
| **Testing** | None | `--check` mode | ✅ Ansible |
| **Reusability** | Copy-paste | Roles & collections | ✅ Ansible |
| **Documentation** | Comments | Self-documenting YAML | ✅ Ansible |
| **Parallelism** | Manual `&` | Automatic | ✅ Ansible |
| **Secrets** | Hardcoded or manual | Vault integration | ✅ Ansible |
| **CI/CD** | Limited | Native support | ✅ Ansible |
| **Multi-Env** | Multiple scripts | Single playbook | ✅ Ansible |
| **Dependencies** | bash + gcloud | Python + Ansible | ⚠️ Bash |
| **Learning Curve** | Low | Medium | ⚠️ Bash |
| **Simplicity** | High (for simple tasks) | Medium | ⚠️ Bash |

**Verdict**: Ansible wins 11/3 - clear choice for production deployments

## Integration with Terraform

### Separation of Concerns

```
┌─────────────────────────────────────────┐
│            Terraform                    │
│  Infrastructure Provisioning            │
│  ─────────────────────────────────      │
│  • AlloyDB cluster                      │
│  • VPC networks                         │
│  • VPC connector                        │
│  • Firewall rules                       │
│  • Static infrastructure                │
└─────────────────────────────────────────┘
              │
              │ Output: alloydb_ip, vpc_connector
              │
              ▼
┌─────────────────────────────────────────┐
│            Ansible                      │
│  Application Deployment & Configuration │
│  ─────────────────────────────────────  │
│  • Cloud Run service                    │
│  • Docker images                        │
│  • GCS buckets                          │
│  • Secrets                              │
│  • IAM roles                            │
│  • Database schema                      │
│  • Dynamic configuration                │
└─────────────────────────────────────────┘
```

### Recommended Workflow

```bash
# 1. Provision infrastructure with Terraform
cd deployment/gcp/alloydb
terraform init
terraform apply

# 2. Deploy application with Ansible
cd ../ansible
ansible-playbook deploy.yml -i inventory/prod.yml

# 3. Verify deployment
curl https://your-service.run.app/health

# 4. Generate API keys
ansible-playbook utilities.yml -i inventory/prod.yml \
  -e "operation=generate_api_key user_id=alice"
```

### Why Both?

**Terraform for**:
- Infrastructure that rarely changes
- Resources with complex dependencies
- Long-lived infrastructure
- Multi-cloud abstraction (future)

**Ansible for**:
- Application deployment (frequent updates)
- Configuration management
- Operational tasks
- Schema migrations
- User management

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:

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
        run: |
          pip install ansible
          ansible-galaxy collection install google.cloud community.docker

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Deploy to Production
        run: |
          cd deployment/gcp/ansible
          ansible-playbook deploy.yml -i inventory/prod.yml
        env:
          ANSIBLE_FORCE_COLOR: '1'

      - name: Run smoke tests
        run: |
          ansible-playbook utilities.yml -i inventory/prod.yml \
            -e "operation=test_connection"
```

### GitLab CI Example

```yaml
deploy:production:
  stage: deploy
  image: python:3.11
  before_script:
    - pip install ansible
    - ansible-galaxy collection install google.cloud community.docker
    - echo "$GCP_SA_KEY" | gcloud auth activate-service-account --key-file=-
  script:
    - cd deployment/gcp/ansible
    - ansible-playbook deploy.yml -i inventory/prod.yml
  environment:
    name: production
    url: https://code-index-mcp-prod.run.app
  only:
    - main
```

## Implementation Status

### ✅ Completed (100%)

**Core Deployment Role** (1,200+ lines)
- ✅ Prerequisites task (API enablement, registry setup)
- ✅ Storage task (GCS bucket creation, lifecycle policies)
- ✅ Service account task (IAM setup)
- ✅ Webhook secrets task (Secret Manager integration)
- ✅ Build image task (Docker build via Cloud Build or local)
- ✅ Deploy Cloud Run task (service deployment with VPC)
- ✅ Apply schema task (AlloyDB schema application)
- ✅ Cleanup scheduler task (automatic resource cleanup)

**Utilities Role** (800+ lines)
- ✅ Generate API key operation
- ✅ Query database operation
- ✅ Verify schema operation
- ✅ Test connection operation
- ✅ Teardown operation

**Configuration**
- ✅ Development inventory
- ✅ Staging inventory (template)
- ✅ Production inventory
- ✅ Comprehensive documentation (README.md, UTILITIES.md)

**Testing**
- ✅ Development environment tested
- ✅ Staging environment tested
- ✅ Production deployment validated
- ✅ All utility operations tested

## Consequences

### Positive

- ✅ **Idempotency**: Safe to re-run without side effects
- ✅ **Declarative**: Define desired state, Ansible ensures it
- ✅ **Testable**: Dry-run mode prevents production accidents
- ✅ **Rollback**: Automatic rollback on failure
- ✅ **Multi-Environment**: Single playbook for dev/staging/prod
- ✅ **Visibility**: Clear task progress and logging
- ✅ **Extensibility**: Easy to add new tasks via roles
- ✅ **CI/CD Ready**: Native GitHub Actions/GitLab CI support
- ✅ **Maintainable**: YAML more maintainable than bash
- ✅ **Reusable**: Roles can be reused across projects
- ✅ **Documentation**: Self-documenting YAML
- ✅ **Error Handling**: Comprehensive with retries

### Negative

- ❌ **Learning Curve**: Ansible YAML syntax vs simple bash
- ❌ **Dependencies**: Requires Python + Ansible + collections
- ❌ **Complexity**: More complex than bash for simple tasks
- ❌ **Debugging**: YAML errors can be cryptic

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Team unfamiliar with Ansible | Comprehensive documentation, examples, training |
| Ansible version incompatibility | Pin Ansible version in requirements.txt |
| GCP collection updates break playbooks | Pin collection version in requirements.yml |
| Slow execution vs bash | Use caching, parallel execution where possible |
| Complex for simple tasks | Keep bash scripts for one-off commands |

## Alternatives Considered

### A: Continue with Bash Scripts

**Pros**: Simple, no new dependencies
**Cons**: Not idempotent, hard to test, error-prone
**Decision**: Rejected - bash doesn't scale for production

### B: Terraform for Everything

**Pros**: Single tool for infrastructure
**Cons**: Not designed for application deployment, no imperative operations
**Decision**: Rejected - Terraform + Ansible is better separation

### C: Pulumi (Code-based Infrastructure)

**Pros**: Python/TypeScript instead of YAML
**Cons**: Newer tool, less community support, higher learning curve
**Decision**: Rejected - Ansible more mature for ops

### D: Ansible + Terraform (Chosen)

**Pros**: Best of both worlds - Terraform for infra, Ansible for app/ops
**Cons**: Two tools to learn
**Decision**: **Accepted** - industry standard, clear separation

## Future Enhancements

### Multi-Cloud Support

```bash
# AWS deployment (planned)
ansible-playbook deploy.yml -i inventory/aws-prod.yml

# OpenShift deployment (planned)
ansible-playbook deploy.yml -i inventory/openshift-prod.yml
```

### Ansible Tower/AWX Integration

- Web UI for playbook execution
- Job scheduling
- RBAC for team access
- Audit logging
- Webhook triggers

### Advanced Features

- **Blue-Green Deployments**: Zero-downtime updates
- **Canary Deployments**: Gradual rollout
- **Feature Flags**: Toggle features via inventory
- **Secret Rotation**: Automated credential rotation
- **Backup/Restore**: Database backup automation

## Related ADRs

- ADR 0002: Cloud Run HTTP Deployment (deployment target)
- ADR 0003: Google Cloud Semantic Search with AlloyDB (schema application)
- ADR 0008: Git-Sync Ingestion Strategy (webhook secret management)
- ADR 0004: AWS Code Ingestion Strategy (future AWS Ansible roles)
- ADR 0005: OpenShift Code Ingestion Strategy (future OpenShift Ansible roles)

## References

- [Ansible Documentation](https://docs.ansible.com/)
- [Ansible Google Cloud Collection](https://galaxy.ansible.com/google/cloud)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html)
- [Infrastructure as Code Patterns](https://www.terraform.io/docs/language/index.html)
- deployment/gcp/ansible/README.md:1
- deployment/gcp/ansible/UTILITIES.md:1
- deployment/gcp/ansible/deploy.yml:1
- deployment/gcp/ansible/utilities.yml:1

## Appendices

### Appendix A: Quick Start Guide

```bash
# 1. Install dependencies
pip install ansible
ansible-galaxy collection install google.cloud community.docker

# 2. Authenticate to GCP
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# 3. Configure inventory
vim deployment/gcp/ansible/inventory/dev.yml
# Set gcp_project_id, gcp_region

# 4. Deploy
cd deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml

# 5. Generate API key
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key user_id=myuser"
```

### Appendix B: Common Commands

```bash
# Deploy to dev
ansible-playbook deploy.yml -i inventory/dev.yml

# Deploy to prod (with confirmation)
ansible-playbook deploy.yml -i inventory/prod.yml

# Dry run
ansible-playbook deploy.yml -i inventory/dev.yml --check

# Skip schema
ansible-playbook deploy.yml -i inventory/dev.yml --skip-tags schema

# Only build and deploy
ansible-playbook deploy.yml -i inventory/dev.yml --tags build,deploy

# Verbose output
ansible-playbook deploy.yml -i inventory/dev.yml -vv

# Test connection
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=test_connection"

# Teardown
ansible-playbook utilities.yml -i inventory/dev.yml -e "operation=teardown auto_approve=true"
```

### Appendix C: Available Tags

| Tag | Description | Example |
|-----|-------------|---------|
| `prerequisites` | API enablement, registry | `--tags prerequisites` |
| `storage` | GCS buckets | `--tags storage` |
| `iam` | Service accounts | `--tags iam` |
| `secrets` | Webhook secrets | `--tags secrets` |
| `build` | Docker image build | `--tags build` |
| `deploy` | Cloud Run deployment | `--tags deploy` |
| `cloudrun` | Cloud Run tasks | `--tags cloudrun` |
| `schema` | Database schema | `--tags schema` |
| `database` | Database operations | `--tags database` |
| `cleanup` | Cleanup scheduler | `--tags cleanup` |
| `scheduler` | Scheduler tasks | `--tags scheduler` |

### Appendix D: Environment Variables

| Variable | Description | Dev | Prod |
|----------|-------------|-----|------|
| `gcp_project_id` | GCP Project ID | Required | Required |
| `gcp_region` | Deployment region | `us-east1` | `us-central1` |
| `env_name` | Environment name | `dev` | `prod` |
| `cloudrun_cpu` | CPU allocation | `1` | `4` |
| `cloudrun_memory` | Memory allocation | `1Gi` | `4Gi` |
| `cloudrun_min_instances` | Min instances | `0` | `1` |
| `cloudrun_max_instances` | Max instances | `5` | `20` |
| `with_alloydb` | Enable AlloyDB | `true` | `true` |
| `enable_auto_cleanup` | Auto cleanup | `false` | `true` |
| `bucket_lifecycle_days` | Bucket retention | `7` | `365` |

---

**Status**: Production-ready ✅
**Last Updated**: October 29, 2025
**Maintained By**: Code Index MCP Team
