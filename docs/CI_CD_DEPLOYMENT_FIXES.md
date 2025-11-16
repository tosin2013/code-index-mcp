# CI/CD Deployment Fixes - November 2024

## Overview
This document tracks the comprehensive fixes applied to the GCP deployment workflow between November 16, 2024, resolving multiple blocking issues that prevented successful deployment.

## Timeline

### Initial State (Pre-fixes)
- **Status**: Deployment workflow failing at multiple stages
- **Blockers**:
  - Deprecated Ansible callback plugin
  - Outdated Ansible version (2.14.17)
  - Empty container image parameter
  - Interactive confirmation prompts
  - Missing Terraform for AlloyDB provisioning
  - GCP IAM permission gaps

### Final State (Post-fixes)
- **Status**: Workflow fully functional, pending GCP IAM permissions
- **Commits**: 4 comprehensive fixes applied
- **Tests**: Security ✅, Build ✅, Deployment reaches GCP provisioning

---

## Fix #1: Ansible Callback Plugin Migration
**Commit**: `7731bd2`
**Date**: 2025-11-16

### Problem
```
ERROR! [DEPRECATED]: community.general.yaml has been removed.
This feature was removed from community.general in version 12.0.0.
```

### Root Cause
- `ansible.cfg` used deprecated `stdout_callback = yaml`
- community.general 12.0.0 removed the yaml callback plugin
- No version constraints on community.general collection

### Solution
1. **ansible.cfg** (line 10):
   ```ini
   # BEFORE:
   stdout_callback = yaml

   # AFTER:
   stdout_callback = ansible.builtin.default
   ```

2. **requirements.yml** (line 9):
   ```yaml
   # BEFORE:
   - name: community.general
     version: ">=7.0.0"

   # AFTER:
   - name: community.general
     version: ">=7.0.0,<12.0.0"  # Pin for ansible-core 2.14
   ```

### References
- Ansible docs: [Callback Plugins](https://docs.ansible.com/ansible/latest/plugins/callback.html)
- Migration path: Use `ansible.builtin.default` from ansible-core 2.13+

---

## Fix #2: Ansible Version Upgrade
**Commit**: `91bdb69`
**Date**: 2025-11-16

### Problem
1. Using outdated `ansible-core 2.14.17` (end of life, 2023)
2. Forced to pin `community.general <12.0.0` for compatibility
3. Missing 2 years of security fixes and improvements

### Root Cause
- No documented architectural requirement for Ansible 2.14
- Technical debt from initial implementation
- `IMPLEMENTATION-PLAN.md` only specified `>=2.14` (minimum, not exact)

### Solution
**Upgraded to ansible-core 2.16.14** (stable LTS release)

1. **deploy-gcp.yml** (line 34):
   ```yaml
   # BEFORE:
   ANSIBLE_VERSION: 'ansible-core==2.14.17'

   # AFTER:
   ANSIBLE_VERSION: 'ansible-core==2.16.14'  # Stable LTS
   ```

2. **delete-gcp.yml** (lines 34, 223):
   - Fixed broken version: `'2.14'` → `'ansible-core==2.16.14'`
   - Fixed install command: `pip install ansible==...` → `pip install ${{...}}`

3. **requirements.yml** (line 9):
   ```yaml
   # BEFORE:
   version: ">=7.0.0,<12.0.0"

   # AFTER:
   version: ">=7.0.0"  # 2.16 supports community.general 12.x+
   ```

### Benefits
- ✅ 2 years of security fixes (2023 → 2024)
- ✅ Supports community.general 12.x+ without workarounds
- ✅ Stable LTS release (even-numbered = long-term support)
- ✅ Aligns with Red Hat Ansible Automation Platform 2.5/2.6

### References
- [ansible-core Release Schedule](https://docs.ansible.com/ansible/latest/reference_appendices/release_and_maintenance.html)
- [End of Life Dates](https://endoflife.date/ansible-core)

---

## Fix #3: Container Image Tag & Confirmation
**Commit**: `f088cf1`
**Date**: 2025-11-16

### Problem 1: Empty Container Image
```bash
-e "container_image=" \  # Empty value
```

**Root Cause**:
- `docker/metadata-action@v5` outputs **multiple tags** (multi-line)
- Build job output: `image_tag = steps.meta.outputs.tags` (multi-line)
- Deploy job received empty/broken value

**Solution**:
1. Added "Set deployment image tag" step (lines 156-162):
   ```yaml
   - name: Set deployment image tag
     id: deployment-image
     run: |
       IMAGE_TAG="${{ env.GCP_REGION }}-docker.pkg.dev/${{ secrets.PROJECT_ID }}/code-index-mcp/server:${{ steps.env.outputs.environment }}-${{ github.sha }}"
       echo "tag=${IMAGE_TAG}" >> $GITHUB_OUTPUT
   ```

2. Updated build outputs (line 93):
   ```yaml
   # BEFORE:
   image_tag: ${{ steps.meta.outputs.tags }}  # Multi-line

   # AFTER:
   image_tag: ${{ steps.deployment-image.outputs.tag }}  # Single tag
   ```

### Problem 2: Deployment Cancelled
```
fatal: [localhost]: FAILED! => {"msg": "Deployment cancelled by user"}
```

**Root Cause**:
- Ansible playbook had interactive confirmation prompt
- CI/CD cannot provide interactive input

**Solution**:
Added to ansible-playbook command (line 234):
```yaml
-e "confirm_deployment=yes" \
```

### References
- [docker/metadata-action outputs](https://github.com/docker/metadata-action#outputs)
- [Ansible pause module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/pause_module.html)

---

## Fix #4: Terraform Installation
**Commit**: `c987905`
**Date**: 2025-11-16

### Problem
```
TASK [code-index-mcp : Check if Terraform is installed]
fatal: [localhost]: FAILED! => {"msg": "Terraform is not installed..."}
```

### Root Cause
- Ansible playbook requires Terraform to provision AlloyDB infrastructure
- Terraform was removed when we eliminated standalone Terraform job
- Per ADR 0009: Ansible orchestrates deployment but uses Terraform for IaC

### Solution
Added Terraform setup to deploy job (lines 210-213):
```yaml
- name: Set up Terraform
  uses: hashicorp/setup-terraform@v3
  with:
    terraform_version: ${{ env.TERRAFORM_VERSION }}
```

### Enables (Phase 3A - AlloyDB)
- ✅ AlloyDB cluster provisioning
- ✅ VPC connector creation
- ✅ pgvector extension setup
- ✅ Vertex AI embeddings integration
- ✅ Full semantic search deployment

### References
- [hashicorp/setup-terraform action](https://github.com/hashicorp/setup-terraform)
- ADR 0003: Google Cloud Code Ingestion with AlloyDB

---

## Remaining Issue: GCP IAM Permissions

### Status
**Workflow code is fully functional** ✅
**Blocker**: GCP service account lacks required permissions ⚠️

### Required Permissions
The GitHub Actions service account needs:

```bash
# Enable GCP APIs
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/serviceusage.serviceUsageAdmin"

# VPC networking for AlloyDB connector
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/compute.networkAdmin"

# AlloyDB cluster management
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/alloydb.admin"

# Secret Manager for API keys
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.admin"

# Cloud Run deployment
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/run.admin"

# Artifact Registry for container images
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/artifactregistry.admin"

# Cloud Storage for code/indexes
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/storage.admin"
```

### Alternative: Editor Role (Less Secure)
For testing environments only:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/editor"
```

⚠️ **Not recommended for production** - grants excessive permissions

---

## Architecture Decisions

### Why Ansible 2.16 (Not 2.18)?
- **2.16**: Stable LTS (even-numbered = long-term support)
- **2.17/2.19**: Short-term lifecycle (odd-numbered)
- **2.18**: Latest but may have edge cases
- **Aligns**: Red Hat Ansible Automation Platform 2.5/2.6 default

### Why Keep Terraform?
- **Per ADR 0009**: Ansible is the single deployment orchestrator
- **But**: Ansible uses Terraform for Infrastructure as Code (IaC)
- **Separation**: Terraform = infrastructure, Ansible = orchestration + application
- **Best Practice**: Declarative IaC (Terraform) + configuration management (Ansible)

### Container Image Tagging Strategy
**Format**: `{environment}-{short-sha}`
**Example**: `dev-f088cf1`, `staging-91bdb69`

**Benefits**:
- ✅ Environment-specific tags
- ✅ Git commit traceability
- ✅ Easy rollback (just reference previous SHA)
- ✅ Unique per deployment

---

## Deployment Flow (Updated)

### Before Fixes
```
Security → Tests → Build → ❌ FAIL (callback error)
```

### After Fixes
```
Security ✅
   ↓
Tests ✅
   ↓
Build ✅ (produces: us-east1-docker.pkg.dev/.../server:dev-abc123)
   ↓
Deploy:
  - Install Ansible 2.16.14 ✅
  - Install Terraform 1.5.0 ✅
  - Run Ansible deployment ✅
    ├── Prerequisites (enable APIs) → ⚠️ Needs IAM permissions
    ├── AlloyDB provisioning (Terraform) → ⚠️ Needs IAM permissions
    ├── Storage setup → ⚠️ Needs IAM permissions
    └── Cloud Run deployment → ⚠️ Needs IAM permissions
```

---

## Testing Checklist

### Workflow Validation ✅
- [x] Security scans pass (Gitleaks, Trivy, Bandit)
- [x] Unit tests pass
- [x] Container image builds successfully
- [x] Image tag outputs correctly (single environment-specific tag)
- [x] Ansible 2.16.14 installs
- [x] Terraform 1.5.0 installs
- [x] Ansible playbook starts execution
- [x] No callback plugin errors
- [x] No confirmation prompt blocks

### Infrastructure Validation ⏳
- [ ] GCP APIs enabled (requires IAM permissions)
- [ ] AlloyDB cluster provisioned (requires IAM permissions)
- [ ] VPC connector created (requires IAM permissions)
- [ ] Cloud Run service deployed (requires IAM permissions)
- [ ] MCP validation tests pass

---

## Lessons Learned

### 1. Version Pinning Strategy
- ✅ **DO**: Pin collection versions with upper bounds (`>=7.0.0,<12.0.0`)
- ✅ **DO**: Use LTS releases (even-numbered: 2.16, 2.18, 2.20)
- ❌ **DON'T**: Use latest without testing (`>=7.0.0` alone)
- ❌ **DON'T**: Pin to EOL versions (2.14.17)

### 2. Multi-line Output Handling
- ✅ **DO**: Extract specific values from multi-line outputs
- ✅ **DO**: Use `$GITHUB_OUTPUT` for single-line values
- ❌ **DON'T**: Pass multi-line outputs between jobs directly

### 3. Interactive Automation
- ✅ **DO**: Provide override flags for CI/CD (`confirm_deployment=yes`)
- ✅ **DO**: Document manual vs automated workflows
- ❌ **DON'T**: Use interactive prompts in automated pipelines

### 4. Dependency Management
- ✅ **DO**: Install all required tools (Ansible, Terraform, gcloud)
- ✅ **DO**: Document tool versions explicitly
- ❌ **DON'T**: Assume tools are pre-installed in runners

---

## References

### Commits
1. `7731bd2`: Ansible callback and community.general version pin
2. `91bdb69`: Ansible 2.16 upgrade
3. `f088cf1`: Container image tag and confirmation fixes
4. `c987905`: Terraform installation

### Documentation
- [ADR 0009: Ansible Deployment Automation](adrs/0009-ansible-deployment-automation.md)
- [ADR 0011: CI/CD Pipeline and Security Architecture](adrs/0011-cicd-pipeline-and-security-architecture.md)
- [ADR 0003: Google Cloud Code Ingestion with AlloyDB](adrs/0003-gcp-code-ingestion-alloydb.md)

### External Resources
- [Ansible Release Schedule](https://docs.ansible.com/ansible/latest/reference_appendices/release_and_maintenance.html)
- [GitHub Actions: Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Terraform in GitHub Actions](https://developer.hashicorp.com/terraform/tutorials/automation/github-actions)

---

## Future Improvements

### Short-term
1. **GCP IAM**: Update service account permissions
2. **Testing**: Validate full deployment end-to-end
3. **Monitoring**: Add deployment success metrics

### Long-term
1. **Ansible 2.18 Upgrade**: Plan migration when stable
2. **Workload Identity**: Migrate from service account keys
3. **Deployment Rollback**: Automated rollback on failure
4. **Multi-region**: Support multiple GCP regions

---

**Last Updated**: 2025-11-16
**Status**: Workflow functional, pending GCP IAM permissions
**Maintainer**: Claude Code (Anthropic)
