# End-to-End Testing Plan: Clean Teardown, Deploy, and Test

## Executive Summary

This document outlines the plan to create a comprehensive end-to-end (E2E) testing playbook that:
1. **Tears down** AlloyDB cluster and Cloud Run service
2. **Redeploys** infrastructure from scratch
3. **Tests** code ingestion and semantic search functionality
4. **Validates** the complete pipeline works correctly

## Current State Analysis

### ✅ What We Have

1. **Terraform Infrastructure** (`deployment/gcp/alloydb-dev.tf`)
   - AlloyDB cluster configuration
   - VPC network and peering
   - Database instance
   - Currently deployed and in READY state

2. **Ansible Deployment** (`deployment/gcp/ansible/deploy.yml`)
   - Cloud Run service deployment
   - API key generation
   - Bucket creation
   - Webhook configuration

3. **Ansible Teardown** (`deployment/gcp/ansible/utilities.yml`)
   - Deletes Cloud Run service ✅
   - Deletes container images ✅
   - Deletes Cloud Scheduler jobs ✅
   - Deletes GCS buckets (optional) ✅
   - **Does NOT delete AlloyDB** ❌

4. **Semantic Search E2E Test** (`tests/ansible/test-semantic-search-e2e.yml`)
   - Tests code ingestion from Git
   - Tests semantic search queries
   - Tests code similarity search
   - Generates performance metrics
   - **Assumes infrastructure exists** (no teardown/redeploy)

### ❌ What's Missing

1. **AlloyDB Teardown Automation**
   - No automated Terraform destroy for AlloyDB
   - Manual `terraform destroy` required

2. **AlloyDB Redeployment Automation**
   - No automated Terraform apply for AlloyDB
   - Manual provisioning required

3. **Integrated E2E Test Playbook**
   - No single playbook that does: teardown → deploy → test
   - Tests assume infrastructure already exists

4. **Database State Reset**
   - No automated way to clear AlloyDB data between tests
   - No schema re-application automation

## Proposed Architecture

### E2E Testing Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Pre-Flight Checks                                   │
│  - Verify Terraform installed                                │
│  - Verify Ansible installed                                  │
│  - Verify gcloud authenticated                               │
│  - Verify required collections installed                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Teardown (Clean Slate)                             │
│  - Delete Cloud Run service (Ansible)                        │
│  - Delete container images (Ansible)                         │
│  - Delete GCS buckets (Ansible, optional)                    │
│  - Destroy AlloyDB cluster (Terraform)                       │
│  - Destroy VPC network (Terraform)                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Deployment (Fresh Infrastructure)                   │
│  - Apply Terraform (AlloyDB + VPC)                           │
│  - Wait for AlloyDB to be READY                             │
│  - Run Ansible deployment (Cloud Run)                        │
│  - Apply database schema                                     │
│  - Seed test user                                            │
│  - Generate test API keys                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Validation                                          │
│  - Test Cloud Run health endpoint                            │
│  - Test AlloyDB connectivity                                 │
│  - Verify schema applied correctly                           │
│  - Test MCP server discovery                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 5: Functional Testing                                  │
│  - Ingest code from Git repository                           │
│  - Wait for ingestion to complete                            │
│  - Run semantic search queries                               │
│  - Test code similarity search                               │
│  - Verify results accuracy                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 6: Performance Metrics                                 │
│  - Collect ingestion time                                    │
│  - Collect search latency                                    │
│  - Collect resource usage                                    │
│  - Generate test report                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 7: Optional Cleanup                                    │
│  - Offer to keep infrastructure (for debugging)              │
│  - Or tear down everything                                   │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### 1. Create Terraform Wrapper Scripts

**File**: `deployment/gcp/terraform-alloydb.sh`

```bash
#!/bin/bash
# Wrapper script for Terraform operations on AlloyDB

OPERATION=$1  # apply, destroy, plan
ENV=${2:-dev}

case $OPERATION in
  apply)
    terraform apply -var="environment=$ENV" -auto-approve
    ;;
  destroy)
    terraform destroy -var="environment=$ENV" -auto-approve
    ;;
  plan)
    terraform plan -var="environment=$ENV"
    ;;
  *)
    echo "Usage: $0 {apply|destroy|plan} [environment]"
    exit 1
    ;;
esac
```

**Benefits**:
- Standardizes Terraform operations
- Easy to call from Ansible
- Environment-specific configurations

### 2. Create Ansible Role for Terraform Operations

**File**: `deployment/gcp/ansible/roles/terraform/tasks/main.yml`

```yaml
---
# Terraform operations wrapper for Ansible

- name: Run Terraform operation
  ansible.builtin.command:
    cmd: "terraform {{ terraform_operation }} -auto-approve"
    chdir: "{{ terraform_directory }}"
  register: terraform_result
  changed_when: "'Apply complete' in terraform_result.stdout"

- name: Display Terraform output
  ansible.builtin.debug:
    var: terraform_result.stdout_lines
```

### 3. Create Database Reset Utility

**File**: `deployment/gcp/ansible/roles/utilities/tasks/reset_database.yml`

```yaml
---
# Reset AlloyDB database to clean state

- name: Truncate all tables (except migrations)
  ansible.builtin.shell: |
    psql "{{ alloydb_connection_string }}" << EOF
    TRUNCATE TABLE code_chunks CASCADE;
    TRUNCATE TABLE code_projects CASCADE;
    TRUNCATE TABLE git_sync_state CASCADE;
    DELETE FROM users WHERE user_id != 'system';
    EOF
  register: truncate_result

- name: Verify tables empty
  ansible.builtin.shell: |
    psql "{{ alloydb_connection_string }}" -c "SELECT
      (SELECT COUNT(*) FROM code_chunks) as chunks,
      (SELECT COUNT(*) FROM code_projects) as projects,
      (SELECT COUNT(*) FROM git_sync_state) as git_state"
  register: verify_empty
```

### 4. Create Master E2E Playbook

**File**: `tests/ansible/test-e2e-full-redeploy.yml`

```yaml
---
# Comprehensive E2E Test: Teardown → Deploy → Test
# WARNING: This is DESTRUCTIVE and will delete AlloyDB!

- name: Code Index MCP - Full End-to-End Test
  hosts: localhost
  connection: local
  gather_facts: yes

  vars:
    # Test configuration
    test_git_url: "https://github.com/anthropics/anthropic-sdk-python"
    test_project_name: "e2e-test-{{ ansible_date_time.epoch }}"

    # Directories
    terraform_dir: "../../deployment/gcp"
    ansible_dir: "../../deployment/gcp/ansible"

    # Cleanup options
    teardown_alloydb: true
    cleanup_after_test: false  # Keep resources for debugging by default

  pre_tasks:
    - name: Display WARNING
      ansible.builtin.debug:
        msg:
          - "╔════════════════════════════════════════════════════════╗"
          - "║  ⚠️  DESTRUCTIVE E2E TEST - READ CAREFULLY  ⚠️         ║"
          - "╚════════════════════════════════════════════════════════╝"
          - ""
          - "This playbook will:"
          - "  1. DELETE AlloyDB cluster (~$180/month when running)"
          - "  2. DELETE Cloud Run service"
          - "  3. DELETE all GCS buckets (ALL DATA LOST)"
          - "  4. REDEPLOY everything from scratch"
          - "  5. Run full semantic search tests"
          - ""
          - "Estimated time: 25-35 minutes"
          - "Cost: ~$0.50-1.00 for test duration"
          - ""
          - "Environment: {{ env_name }}"
          - "Project: {{ gcp_project_id }}"
          - ""

    - name: Confirm destructive test
      ansible.builtin.pause:
        prompt: |
          Type 'I understand and want to proceed' to continue
          (Press Ctrl+C to cancel)
      register: confirm_e2e

    - name: Validate confirmation
      ansible.builtin.fail:
        msg: "Test cancelled - confirmation required"
      when: confirm_e2e.user_input != 'I understand and want to proceed'

  tasks:
    # ========================================================================
    # PHASE 1: Pre-Flight Checks
    # ========================================================================
    - name: Phase 1 - Pre-Flight Checks
      block:
        - name: Check Terraform installed
          ansible.builtin.command: terraform version
          register: tf_version
          changed_when: false

        - name: Check gcloud authenticated
          ansible.builtin.command: gcloud auth list
          register: gcloud_auth
          changed_when: false

        - name: Display pre-flight results
          ansible.builtin.debug:
            msg:
              - "✅ Pre-flight checks passed"
              - "Terraform: {{ tf_version.stdout_lines[0] }}"
              - "GCloud: Authenticated"

    # ========================================================================
    # PHASE 2: Teardown
    # ========================================================================
    - name: Phase 2 - Teardown Infrastructure
      block:
        - name: Teardown Cloud Run (Ansible)
          ansible.builtin.command:
            cmd: |
              ansible-playbook utilities.yml
              -i inventory/{{ env_name }}.yml
              -e "operation=teardown"
              -e "auto_approve=true"
              -e "delete_buckets=true"
            chdir: "{{ ansible_dir }}"
          register: ansible_teardown

        - name: Destroy AlloyDB (Terraform)
          ansible.builtin.command:
            cmd: terraform destroy -auto-approve
            chdir: "{{ terraform_dir }}"
          register: terraform_destroy
          when: teardown_alloydb | bool

        - name: Display teardown results
          ansible.builtin.debug:
            msg:
              - "✅ Teardown complete"
              - "Cloud Run: Deleted"
              - "AlloyDB: {{ 'Deleted' if teardown_alloydb else 'Preserved' }}"

    # ========================================================================
    # PHASE 3: Deployment
    # ========================================================================
    - name: Phase 3 - Deploy Infrastructure
      block:
        - name: Deploy AlloyDB (Terraform)
          ansible.builtin.command:
            cmd: terraform apply -auto-approve
            chdir: "{{ terraform_dir }}"
          register: terraform_apply
          timeout: 1800  # 30 minutes for AlloyDB provisioning

        - name: Wait for AlloyDB to be READY
          ansible.builtin.command:
            cmd: |
              gcloud alloydb clusters describe code-index-cluster-{{ env_name }}
              --region={{ gcp_region }}
              --format='value(state)'
          register: cluster_state
          until: cluster_state.stdout == 'READY'
          retries: 60
          delay: 30

        - name: Deploy Cloud Run (Ansible)
          ansible.builtin.command:
            cmd: |
              ansible-playbook deploy.yml
              -i inventory/{{ env_name }}.yml
              -e "confirm_deployment=yes"
            chdir: "{{ ansible_dir }}"
          register: ansible_deploy

        - name: Apply database schema
          ansible.builtin.command:
            cmd: |
              ansible-playbook utilities.yml
              -i inventory/{{ env_name }}.yml
              -e "operation=apply_schema"
            chdir: "{{ ansible_dir }}"
          register: schema_apply

        - name: Seed test user
          ansible.builtin.command:
            cmd: |
              ansible-playbook utilities.yml
              -i inventory/{{ env_name }}.yml
              -e "operation=seed_test_user"
            chdir: "{{ ansible_dir }}"
          register: seed_user

        - name: Generate test API key
          ansible.builtin.command:
            cmd: |
              ansible-playbook utilities.yml
              -i inventory/{{ env_name }}.yml
              -e "operation=generate_api_key"
              -e "user_id=e2e-test"
            chdir: "{{ ansible_dir }}"
          register: api_key_gen

        - name: Read generated API key
          ansible.builtin.slurp:
            src: "{{ ansible_dir }}/api-key-e2e-test-{{ env_name }}.txt"
          register: api_key_file

        - name: Set API key fact
          ansible.builtin.set_fact:
            test_api_key: "{{ api_key_file.content | b64decode | trim }}"

    # ========================================================================
    # PHASE 4: Validation
    # ========================================================================
    - name: Phase 4 - Validate Deployment
      block:
        - name: Get Cloud Run service URL
          ansible.builtin.command:
            cmd: |
              gcloud run services describe code-index-mcp-{{ env_name }}
              --region={{ gcp_region }}
              --format='value(status.url)'
          register: service_url

        - name: Test health endpoint
          ansible.builtin.uri:
            url: "{{ service_url.stdout }}/health"
            method: GET
            status_code: 200
          register: health_check

        - name: Test AlloyDB connectivity
          ansible.builtin.command:
            cmd: |
              ansible-playbook utilities.yml
              -i inventory/{{ env_name }}.yml
              -e "operation=test_connection"
            chdir: "{{ ansible_dir }}"
          register: db_test

    # ========================================================================
    # PHASE 5: Functional Testing (Semantic Search E2E)
    # ========================================================================
    - name: Phase 5 - Run Semantic Search Tests
      ansible.builtin.include_role:
        name: ../../tests/ansible/test-semantic-search-e2e.yml
      vars:
        mcp_server_url: "{{ service_url.stdout }}"
        api_key: "{{ test_api_key }}"

    # ========================================================================
    # PHASE 6: Performance Metrics
    # ========================================================================
    - name: Phase 6 - Collect Metrics
      block:
        - name: Calculate total test time
          ansible.builtin.set_fact:
            total_test_time: "{{ (ansible_date_time.epoch | int) - (test_start_time | int) }}"

        - name: Generate comprehensive report
          ansible.builtin.template:
            src: e2e-report.md.j2
            dest: "./e2e-test-report-{{ ansible_date_time.epoch }}.md"

  post_tasks:
    - name: Display test summary
      ansible.builtin.debug:
        msg:
          - "╔════════════════════════════════════════════════════════╗"
          - "║  ✅ E2E TEST COMPLETE                                  ║"
          - "╚════════════════════════════════════════════════════════╝"
          - ""
          - "Test Duration: {{ total_test_time }} seconds"
          - "Report: ./e2e-test-report-{{ ansible_date_time.epoch }}.md"
          - ""
          - "{{ 'Infrastructure kept for debugging' if not cleanup_after_test else 'Infrastructure cleaned up' }}"

    - name: Optional cleanup
      when: cleanup_after_test | bool
      ansible.builtin.include_tasks: phase2_teardown.yml
```

### 5. Create Simplified E2E Playbook (Database Reset Only)

**File**: `tests/ansible/test-e2e-db-reset.yml`

For faster testing, create a lighter version that:
- ✅ Resets database state (truncate tables)
- ✅ Keeps AlloyDB and Cloud Run running
- ✅ Runs semantic search tests
- ⚡ Much faster (~5-10 minutes vs 25-35 minutes)

This is ideal for:
- Regression testing
- CI/CD pipelines
- Quick validation

### 6. Create CI/CD Integration

**File**: `.github/workflows/e2e-test-alloydb.yml`

```yaml
name: E2E Test - AlloyDB Semantic Search

on:
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Monday at 2 AM
  workflow_dispatch:     # Manual trigger
    inputs:
      full_redeploy:
        description: 'Full redeploy (teardown + deploy)'
        type: boolean
        default: false

jobs:
  e2e-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup gcloud
        uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ secrets.GCP_PROJECT_ID }}

      - name: Install dependencies
        run: |
          pip install ansible
          ansible-galaxy collection install google.cloud
          ansible-galaxy collection install tosin2013.mcp_audit

      - name: Run E2E test (Full redeploy)
        if: github.event.inputs.full_redeploy == 'true'
        run: |
          cd tests/ansible
          ansible-playbook test-e2e-full-redeploy.yml \
            -i inventory/dev.yml \
            -e "confirm_e2e='I understand and want to proceed'"

      - name: Run E2E test (DB reset only)
        if: github.event.inputs.full_redeploy != 'true'
        run: |
          cd tests/ansible
          ansible-playbook test-e2e-db-reset.yml \
            -i inventory/dev.yml

      - name: Upload test report
        uses: actions/upload-artifact@v3
        with:
          name: e2e-test-report
          path: tests/ansible/e2e-test-report-*.md
```

## Cost Analysis

### Full Redeploy E2E Test
- **AlloyDB provisioning**: ~15-20 minutes (no charge for provisioning)
- **AlloyDB running time**: ~30 minutes (~$0.20)
- **Cloud Run**: ~$0.05
- **Cloud Storage**: ~$0.01
- **Total per test**: **~$0.25-0.30**

### Database Reset E2E Test
- **AlloyDB already running**: No provisioning delay
- **Test duration**: ~5-10 minutes
- **Total per test**: **~$0.05-0.10**

### Monthly Cost (if running weekly)
- 4 full tests/month: ~$1.20
- 20 quick tests/month: ~$1.50
- **Total**: **~$2.70/month**

## Timeline

### Week 1: Foundation
- [ ] Day 1-2: Create Terraform wrapper scripts
- [ ] Day 3: Create Ansible Terraform role
- [ ] Day 4-5: Create database reset utility

### Week 2: Core E2E Playbook
- [ ] Day 1-3: Build full E2E playbook
- [ ] Day 4-5: Test and debug

### Week 3: Optimization
- [ ] Day 1-2: Create DB reset variant
- [ ] Day 3-4: CI/CD integration
- [ ] Day 5: Documentation and training

## Success Criteria

1. ✅ **Automated Teardown**: Complete destruction of AlloyDB + Cloud Run
2. ✅ **Automated Deploy**: Provision AlloyDB, deploy Cloud Run, apply schema
3. ✅ **Functional Tests**: Ingest code, run semantic search, validate results
4. ✅ **Report Generation**: Markdown report with metrics and status
5. ✅ **CI/CD Ready**: GitHub Actions workflow
6. ✅ **Cost Effective**: <$1 per full test run
7. ✅ **Time Efficient**: <35 minutes for full redeploy

## Risk Mitigation

### Risk: Accidental Production Teardown
**Mitigation**:
- Require explicit confirmation
- Environment-specific inventories
- Production inventory requires manual approval

### Risk: Long Test Duration
**Mitigation**:
- Create DB reset variant (5-10 min)
- Reserve full redeploy for weekly scheduled tests
- Use DB reset for CI/CD

### Risk: AlloyDB Provisioning Failures
**Mitigation**:
- Increase Terraform timeout to 30 minutes
- Add retry logic
- Detailed error logging

## Next Steps

1. **Review and Approve** this plan
2. **Assign ownership** for each phase
3. **Create GitHub issues** for tracking
4. **Start Week 1 implementation**

---

**Questions or Feedback?** Open an issue or comment on this document.
