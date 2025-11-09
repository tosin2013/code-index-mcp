# End-to-End Testing Guide

## Overview

This guide explains how to use the E2E testing infrastructure for Code Index MCP, which provides two testing modes:

1. **Fast E2E Test** (DB Reset) - ~5-10 minutes, ~$0.05 per run
2. **Full E2E Test** (Teardown + Redeploy) - ~25-35 minutes, ~$0.25-0.50 per run

## Quick Start

### Prerequisites

```bash
# Install Ansible
pip install ansible

# Install required collections
ansible-galaxy collection install google.cloud
ansible-galaxy collection install community.docker
ansible-galaxy collection install tosin2013.mcp_audit

# Authenticate to GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Running Fast E2E Test (Recommended for CI/CD)

```bash
cd tests/ansible
ansible-playbook test-e2e-db-reset.yml -i inventory/dev.yml
```

**What it does:**
- ✅ Resets database (truncates all tables)
- ✅ Tests code ingestion from Git
- ✅ Tests semantic search queries
- ✅ Generates test report
- ⚡ Fast: ~5-10 minutes
- 💰 Cheap: ~$0.05 per run

**When to use:**
- CI/CD pipelines
- Regression testing
- Quick validation
- Development testing

### Running Full E2E Test (Recommended for Weekly Validation)

```bash
cd tests/ansible
ansible-playbook test-e2e-full-redeploy.yml -i inventory/dev.yml
```

**What it does:**
- 🔥 **DESTRUCTIVE**: Deletes AlloyDB (~$180/month resource!)
- 🔥 Deletes Cloud Run service
- 🔥 Deletes GCS buckets
- ✅ Redeploys everything from scratch
- ✅ Tests code ingestion from Git
- ✅ Tests semantic search queries
- ✅ Generates comprehensive test report
- ⏱️ Slow: ~25-35 minutes
- 💰 Moderate: ~$0.25-0.50 per run

**When to use:**
- Weekly scheduled validation
- After major infrastructure changes
- Before production deployment
- When you suspect infrastructure corruption

## Test Comparison

| Feature | Fast E2E | Full E2E |
|---------|----------|----------|
| **Duration** | ~5-10 minutes | ~25-35 minutes |
| **Cost** | ~$0.05 | ~$0.25-0.50 |
| **Infrastructure** | Preserved | Redeployed |
| **Database** | Reset (truncate) | Recreated |
| **AlloyDB** | Kept running | Destroyed + Rebuilt |
| **Cloud Run** | Kept running | Destroyed + Rebuilt |
| **Use Case** | CI/CD, frequent testing | Weekly, major changes |
| **Risk** | Low (no deletion) | High (full teardown) |

## CI/CD Integration

### GitHub Actions

The E2E tests are integrated into GitHub Actions:

**Automatic Triggers:**
- ✅ **Weekly**: Full E2E test every Monday at 2 AM UTC
- ✅ **Pull Requests**: Fast E2E test on PRs affecting deployment/ingestion code

**Manual Triggers:**
```bash
# Via GitHub UI: Actions → E2E Test → Run workflow
# Choose: fast or full
# Choose: dev or staging
```

**Required Secrets:**
- `GCP_SA_KEY`: Service account JSON key
- `GCP_PROJECT_ID`: Your GCP project ID

### GitLab CI

```yaml
# .gitlab-ci.yml
e2e-fast:
  stage: test
  script:
    - pip install ansible
    - ansible-galaxy collection install google.cloud tosin2013.mcp_audit
    - cd tests/ansible
    - ansible-playbook test-e2e-db-reset.yml -i inventory/dev.yml
  only:
    - merge_requests
    - main

e2e-full:
  stage: test
  script:
    - pip install ansible
    - ansible-galaxy collection install google.cloud tosin2013.mcp_audit
    - cd tests/ansible
    - ansible-playbook test-e2e-full-redeploy.yml -i inventory/dev.yml
  when: manual  # Require manual trigger
  only:
    - schedules  # Weekly schedule
```

## Test Architecture

### Fast E2E Test Flow

```
┌─────────────────────────────────────────┐
│ 1. Pre-Flight Checks                    │
│    - Verify AlloyDB running             │
│    - Verify Cloud Run running           │
│    - Test health endpoint               │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 2. Database Reset                       │
│    - Truncate code_chunks               │
│    - Truncate code_projects             │
│    - Truncate git_sync_state            │
│    - Delete non-system users            │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 3. Get Test API Key                     │
│    - Seed test user (if needed)         │
│    - Generate API key                   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 4. MCP Server Discovery                 │
│    - Discover available tools           │
│    - Verify semantic search available   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 5. Functional Testing                   │
│    - Ingest code from Git               │
│    - Run semantic search queries        │
│    - Validate results                   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 6. Performance Metrics                  │
│    - Calculate test duration            │
│    - Calculate search latency           │
│    - Generate test report               │
└─────────────────────────────────────────┘
```

### Full E2E Test Flow

```
┌─────────────────────────────────────────┐
│ 1. Pre-Flight Checks                    │
│    - Verify Terraform installed         │
│    - Verify gcloud authenticated        │
│    - Verify Ansible collections         │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 2. Teardown Infrastructure              │
│    - Delete Cloud Run (Ansible)         │
│    - Delete GCS buckets                 │
│    - Destroy AlloyDB (Terraform)        │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 3. Deploy Infrastructure                │
│    - Deploy AlloyDB (Terraform)         │
│    - Wait for AlloyDB READY             │
│    - Deploy Cloud Run (Ansible)         │
│    - Apply database schema              │
│    - Seed test user                     │
│    - Generate API key                   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 4. Validation                           │
│    - Test Cloud Run health              │
│    - Test AlloyDB connectivity          │
│    - Discover MCP server                │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 5. Functional Testing                   │
│    - Ingest code from Git               │
│    - Run semantic search queries        │
│    - Validate results                   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 6. Performance Metrics                  │
│    - Calculate total test time          │
│    - Generate comprehensive report      │
└─────────────────────────────────────────┘
```

## Utilities

### Terraform Wrapper Script

Direct access to Terraform operations:

```bash
# Apply AlloyDB infrastructure
./deployment/gcp/terraform-alloydb.sh apply dev

# Destroy AlloyDB infrastructure
./deployment/gcp/terraform-alloydb.sh destroy dev

# Plan changes
./deployment/gcp/terraform-alloydb.sh plan dev

# Check AlloyDB status
./deployment/gcp/terraform-alloydb.sh status dev

# Validate Terraform configuration
./deployment/gcp/terraform-alloydb.sh validate
```

### Database Reset Utility

Reset database without redeploying infrastructure:

```bash
cd deployment/gcp/ansible

# Reset with confirmation
ansible-playbook utilities.yml \
  -i inventory/dev.yml \
  -e "operation=reset_database"

# Reset without confirmation (CI/CD)
ansible-playbook utilities.yml \
  -i inventory/dev.yml \
  -e "operation=reset_database" \
  -e "auto_approve=true"
```

## Test Reports

### Report Location

Test reports are saved in the `tests/ansible/` directory:

- **Fast E2E**: `fast-e2e-test-report-<timestamp>.md`
- **Full E2E**: `e2e-test-report-<timestamp>.md`

### Report Contents

Each report includes:

1. **Test Metadata**
   - Test type
   - Date and time
   - Environment
   - GCP project

2. **Test Phases**
   - Pre-flight checks
   - Teardown (full E2E only)
   - Deployment (full E2E only)
   - Database reset (fast E2E only)
   - Validation
   - Functional testing

3. **Performance Metrics**
   - Total test duration
   - Database reset time (fast E2E)
   - Ingestion time
   - Average search time
   - Total searches performed
   - Results returned

4. **Semantic Search Results**
   - Each query executed
   - Results found
   - Top match file path
   - Similarity scores

### Example Report

```markdown
# Code Index MCP - Fast E2E Test Report

**Test Type**: Database Reset + Functional Test
**Date**: 2025-11-04T12:34:56Z
**Environment**: dev
**Project**: my-gcp-project

## Test Phases

| Phase | Status |
|-------|--------|
| Pre-Flight Checks | ✅ PASS |
| Database Reset | ✅ PASS |
| Functional Testing | ✅ PASS |

## Performance Metrics

- **Total Test Duration**: 487s
- **Database Reset Time**: 12s
- **Code Ingestion Time**: 234s
- **Average Search Time**: 1.23s
- **Total Searches Performed**: 3
- **Results Returned**: 13

## Semantic Search Results

### Query 1: "API client authentication and configuration"
- **Status**: ✅ PASS
- **Results Found**: 5
- **Top Match**: src/anthropic/client.py
- **Similarity Score**: 0.89

...
```

## Troubleshooting

### Test Failures

**Problem**: Fast E2E test fails with "AlloyDB not READY"

**Solution**:
```bash
# Check AlloyDB status
gcloud alloydb clusters describe code-index-cluster-dev \
  --region=us-east1 \
  --format='value(state)'

# If not READY, wait or run full E2E test
```

**Problem**: Full E2E test times out during AlloyDB provisioning

**Solution**:
- AlloyDB provisioning can take 15-20 minutes
- Check GCP Console for provisioning status
- Increase timeout in playbook if needed:
  ```yaml
  timeout: 2400  # 40 minutes
  ```

**Problem**: Semantic search returns no results

**Solution**:
```bash
# Check if ingestion actually succeeded
cd deployment/gcp/ansible
ansible-playbook utilities.yml \
  -i inventory/dev.yml \
  -e "operation=query_database"

# Verify code_chunks table has data
```

### Infrastructure Issues

**Problem**: "AlloyDB cluster not found"

**Solution**:
```bash
# Check if cluster exists
gcloud alloydb clusters list --region=us-east1

# If not, run full E2E test to redeploy
cd tests/ansible
ansible-playbook test-e2e-full-redeploy.yml -i inventory/dev.yml
```

**Problem**: Cloud Run service not responding

**Solution**:
```bash
# Check service status
gcloud run services describe code-index-mcp-dev --region=us-east1

# Check logs
gcloud run services logs read code-index-mcp-dev --region=us-east1

# Redeploy if needed
cd deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes"
```

## Cost Optimization

### Monthly Cost Estimates

**Scenario 1: Continuous Integration**
- 20 fast E2E tests/month: $1.00
- 4 full E2E tests/month: $1.00
- **Total**: **~$2.00/month**

**Scenario 2: Weekly Validation**
- 4 fast E2E tests/month: $0.20
- 1 full E2E test/month: $0.25
- **Total**: **~$0.45/month**

**Scenario 3: On-Demand Only**
- Run tests as needed
- **Total**: **$0.05-0.50 per test**

### Cost Reduction Tips

1. **Use Fast E2E for CI/CD**: Save 80% on testing costs
2. **Schedule Full E2E weekly**: Once per week is sufficient
3. **Clean up after testing**: Set `cleanup_after_test: true` in playbook
4. **Use staging environment**: Smaller AlloyDB instance for testing

## Best Practices

### Development Workflow

```bash
# 1. Make code changes
# 2. Run fast E2E test locally
cd tests/ansible
ansible-playbook test-e2e-db-reset.yml -i inventory/dev.yml

# 3. If passing, commit and push
git add .
git commit -m "feat: add new semantic search feature"
git push

# 4. CI/CD runs fast E2E automatically on PR
# 5. Weekly full E2E validates infrastructure
```

### Pre-Production Checklist

Before deploying to production:

- [ ] Fast E2E tests passing on staging
- [ ] Full E2E test passed within last week
- [ ] No manual infrastructure changes since last test
- [ ] Test reports reviewed and approved
- [ ] Performance metrics within acceptable range

## Advanced Usage

### Custom Test Queries

Edit `semantic_queries` in playbook:

```yaml
semantic_queries:
  - query: "Your custom query here"
    language: "python"
    top_k: 5
  - query: "Another test query"
    language: "typescript"
    top_k: 10
```

### Custom Test Repository

Change test repository:

```yaml
test_git_url: "https://github.com/your-org/your-repo"
test_project_name: "your-test-project"
```

### Skip Cleanup (Keep Infrastructure)

For debugging, keep infrastructure after full E2E test:

```bash
ansible-playbook test-e2e-full-redeploy.yml \
  -i inventory/dev.yml \
  -e "cleanup_after_test=false"
```

## Support

For issues or questions:

1. Check test reports in `tests/ansible/`
2. Review GCP logs: `gcloud run services logs read`
3. Check AlloyDB status: `./deployment/gcp/terraform-alloydb.sh status dev`
4. Open GitHub issue with test report attached

---

**Last Updated**: 2025-11-04
**Version**: 1.0.0
