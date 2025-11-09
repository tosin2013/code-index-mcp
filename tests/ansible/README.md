# MCP Server Testing with Ansible

This directory contains Ansible playbooks for automated testing and validation of the Code Index MCP server using the **tosin2013.mcp_audit** Ansible collection.

## Overview

These playbooks test the MCP server across multiple:
- **Transports**: stdio (local), HTTP/SSE (cloud)
- **Environments**: Development, staging, production
- **Platforms**: Google Cloud Run, AWS Lambda (planned), OpenShift (planned)
- **Integration**: End-to-end testing with real LLMs

## Quick Start

### 1. Install Dependencies

```bash
# Install Ansible (if not already installed)
pip install ansible

# Install required Ansible collections
ansible-galaxy collection install -r requirements.yml
```

### 2. Run Local Tests (stdio mode)

```bash
# Test the MCP server running locally
ansible-playbook test-local.yml -i inventory/local.yml
```

Expected output:
```
PLAY [Test Code Index MCP Server - Local stdio Mode] *******************

TASK [Get server information] *******************************************
ok: [localhost]

TASK [Test set_project_path tool] ***************************************
ok: [localhost]

...

PLAY RECAP **************************************************************
localhost : ok=12   changed=2   unreachable=0   failed=0   skipped=0
```

### 3. Run Cloud Tests (HTTP/SSE mode)

```bash
# Set environment variables
export CLOUDRUN_SERVICE_URL="https://code-index-mcp-dev-xxxxx.run.app"
export MCP_API_KEY_DEV="ci_your_api_key_here"

# Test cloud deployment
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
```

## Directory Structure

```
tests/ansible/
├── README.md                    # This file
├── requirements.yml             # Ansible Galaxy dependencies
├── ansible.cfg                  # Ansible configuration
├── inventory/
│   ├── local.yml               # Local stdio testing
│   ├── gcp-dev.yml             # GCP dev environment
│   ├── gcp-staging.yml         # GCP staging
│   └── gcp-prod.yml            # GCP production
├── test-local.yml              # Local stdio test playbook
├── test-cloud.yml              # Cloud HTTP/SSE test playbook
├── test-llm-integration.yml    # LLM end-to-end tests
├── test-regression.yml         # Full regression suite
└── vars/
    ├── expected_tools.yml      # Expected tool list
    └── test_data.yml           # Test input data
```

## Available Playbooks

### test-local.yml
Tests MCP server running locally via stdio transport.

**What it tests:**
- Server discovery and capabilities
- set_project_path tool
- refresh_index tool
- find_files tool
- search_code_advanced tool
- File resource retrieval

**Usage:**
```bash
ansible-playbook test-local.yml -i inventory/local.yml
```

**Requirements:**
- Code Index MCP server installed locally
- Python environment with MCP dependencies

### test-cloud.yml
Tests MCP server deployed to cloud via HTTP/SSE transport.

**What it tests:**
- Server discovery via SSE
- semantic_search_code tool (cloud-only)
- find_similar_code tool (cloud-only)
- ingest_code_from_git tool (cloud-only)
- All metadata tools (search, find, summary)

**Usage:**
```bash
# Set environment variables first
export CLOUDRUN_SERVICE_URL="https://your-service.run.app"
export MCP_API_KEY="ci_your_api_key"

ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
```

**Requirements:**
- MCP server deployed to Cloud Run/Lambda/OpenShift
- Valid API key
- Network access to cloud endpoint

### test-llm-integration.yml
End-to-end testing with real LLMs calling MCP tools.

**What it tests:**
- LLM → MCP server connection
- LLM tool schema interpretation
- Tool invocation from natural language prompts
- Response validation

**Supported LLM Providers:**
- Ollama (local, no API key)
- OpenRouter (Anthropic Claude, OpenAI GPT, etc.)
- vLLM (custom endpoints)

**Usage:**
```bash
# With Ollama (local, free)
ansible-playbook test-llm-integration.yml -i inventory/gcp-dev.yml \
  -e "llm_provider=ollama llm_model=llama3.2"

# With OpenRouter (requires API key)
export OPENROUTER_API_KEY="sk-or-xxxxx"
ansible-playbook test-llm-integration.yml -i inventory/gcp-dev.yml \
  -e "llm_provider=openrouter llm_model=anthropic/claude-3.5-sonnet"
```

### test-regression.yml
Comprehensive regression test suite for all MCP functionality.

**What it tests:**
- All tools systematically
- All resource types
- Expected result validation
- Error handling

**Usage:**
```bash
ansible-playbook test-regression.yml -i inventory/gcp-staging.yml
```

**Generates:**
- YAML test report with pass/fail details
- Summary statistics
- Timestamp and environment info

## Configuration

### Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `CLOUDRUN_SERVICE_URL` | Cloud Run service URL | Cloud tests | `https://service.run.app` |
| `MCP_API_KEY` | MCP server API key | Cloud tests | `ci_abc123...` |
| `OPENROUTER_API_KEY` | OpenRouter API key | LLM tests | `sk-or-xxxxx` |
| `OLLAMA_BASE_URL` | Ollama server URL | Ollama tests | `http://localhost:11434` |

### Inventory Variables

#### local.yml (stdio testing)
```yaml
transport: stdio
mcp_server_command: "{{ ansible_python_interpreter }}"
mcp_server_args:
  - "-m"
  - "code_index_mcp.server"
test_project_path: "/tmp/code-index-mcp-test-project"
```

#### gcp-dev.yml (cloud testing)
```yaml
transport: sse
gcp_project_id: "your-project-dev"
gcp_region: "us-east1"
mcp_server_url: "{{ lookup('env', 'CLOUDRUN_SERVICE_URL_DEV') }}"
api_key: "{{ lookup('env', 'MCP_API_KEY_DEV') }}"
run_llm_tests: true
ollama_available: true
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Test MCP Server

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  test-local:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install ansible
          ansible-galaxy collection install -r tests/ansible/requirements.yml

      - name: Install MCP server
        run: pip install -e .

      - name: Run local tests
        run: |
          cd tests/ansible
          ansible-playbook test-local.yml -i inventory/local.yml

  test-cloud:
    needs: test-local
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3

      - name: Install Ansible
        run: |
          pip install ansible
          ansible-galaxy collection install -r tests/ansible/requirements.yml

      - name: Deploy to dev
        run: |
          cd deployment/gcp/ansible
          ansible-playbook deploy.yml -i inventory/dev.yml
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_SA_KEY }}

      - name: Test cloud deployment
        run: |
          cd tests/ansible
          ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
        env:
          CLOUDRUN_SERVICE_URL: ${{ needs.deploy.outputs.service_url }}
          MCP_API_KEY: ${{ secrets.MCP_API_KEY_DEV }}

      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: test-reports
          path: tests/ansible/test-report-*.yml
```

### GitLab CI

```yaml
stages:
  - test-local
  - deploy-dev
  - test-cloud

test:local:
  stage: test-local
  image: python:3.11
  script:
    - pip install ansible
    - ansible-galaxy collection install -r tests/ansible/requirements.yml
    - pip install -e .
    - cd tests/ansible
    - ansible-playbook test-local.yml -i inventory/local.yml

deploy:dev:
  stage: deploy-dev
  image: python:3.11
  script:
    - pip install ansible
    - ansible-galaxy collection install google.cloud
    - cd deployment/gcp/ansible
    - ansible-playbook deploy.yml -i inventory/dev.yml
  only:
    - main

test:cloud:
  stage: test-cloud
  image: python:3.11
  script:
    - pip install ansible
    - ansible-galaxy collection install -r tests/ansible/requirements.yml
    - cd tests/ansible
    - ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
  variables:
    CLOUDRUN_SERVICE_URL: $CLOUDRUN_SERVICE_URL_DEV
    MCP_API_KEY: $MCP_API_KEY_DEV
  only:
    - main
```

## Test Reports

Test playbooks generate YAML reports with detailed results:

```yaml
# test-report-1699564800.yml
test_suite: code-index-mcp-regression
timestamp: 2025-11-02T14:30:00Z
environment: gcp-dev
transport: sse

summary:
  total_tests: 12
  passed: 11
  failed: 1
  skipped: 0

tests:
  - name: "Server Discovery"
    status: passed
    duration_ms: 245

  - name: "Semantic Search - Python Functions"
    status: passed
    duration_ms: 1823
    result:
      results_count: 15
      top_score: 0.92

  - name: "Git Ingestion"
    status: failed
    error: "Repository not found: https://invalid.git"
    duration_ms: 1024

server_info:
  server_name: CodeIndexer
  protocol_version: 2024-11-05
  capabilities:
    tools: 15
    resources: 2
```

## Troubleshooting

### Error: Collection not found

```bash
ERROR! couldn't resolve module/action 'tosin2013.mcp_audit.mcp_server_info'
```

**Solution:**
```bash
ansible-galaxy collection install tosin2013.mcp_audit
```

### Error: Connection refused (cloud tests)

```bash
FAILED! => {"msg": "Connection to https://service.run.app failed"}
```

**Checklist:**
1. Is CLOUDRUN_SERVICE_URL correct?
2. Is the service deployed and running?
3. Is the API key valid?
4. Check firewall/network settings

### Error: API key invalid

```bash
FAILED! => {"msg": "Unauthorized: Invalid API key"}
```

**Solution:**
```bash
# Generate new API key
cd deployment/gcp/ansible
ansible-playbook utilities.yml -i inventory/dev.yml \
  -e "operation=generate_api_key user_id=test-user"

# Copy the generated key to environment
export MCP_API_KEY="ci_new_key_here"
```

### Error: Tool not found

```bash
FAILED! => {"msg": "Tool 'semantic_search_code' not available"}
```

**Possible causes:**
1. **stdio mode**: semantic_search_code only works in cloud mode (requires AlloyDB)
2. **Cloud mode**: AlloyDB not deployed or not connected
3. **Version mismatch**: Server version doesn't have this tool

**Solution:**
```bash
# Check what tools are available
ansible-playbook test-local.yml -i inventory/local.yml --tags server_info

# For cloud semantic search, ensure AlloyDB is deployed
cd deployment/gcp/alloydb
terraform apply
```

## Best Practices

### 1. Always test locally first
```bash
# Local tests are fast and free
ansible-playbook test-local.yml -i inventory/local.yml

# Only run cloud tests after local tests pass
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
```

### 2. Use different API keys per environment
```bash
# Dev
export MCP_API_KEY_DEV="ci_dev_key"

# Staging
export MCP_API_KEY_STAGING="ci_staging_key"

# Production
export MCP_API_KEY_PROD="ci_prod_key"
```

### 3. Run regression suite before production deployment
```bash
# Test staging thoroughly
ansible-playbook test-regression.yml -i inventory/gcp-staging.yml

# If all tests pass, deploy to production
cd ../../deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/prod.yml
```

### 4. Use Ollama for cost-free LLM testing
```bash
# Start Ollama locally
ollama serve

# Pull model
ollama pull llama3.2

# Test with Ollama (no API costs)
ansible-playbook test-llm-integration.yml -i inventory/gcp-dev.yml \
  -e "llm_provider=ollama llm_model=llama3.2"
```

## Related Documentation

- **ADR 0010**: MCP Server Testing Strategy (docs/adrs/0010-mcp-server-testing-with-ansible.md)
- **ADR 0009**: Ansible Deployment Automation (docs/adrs/0009-ansible-deployment-automation.md)
- **ADR 0001**: MCP Transport Protocols (docs/adrs/0001-mcp-stdio-protocol-cloud-deployment-constraints.md)
- **Collection Docs**: https://github.com/tosin2013/ansible-collection-mcp-audit

## Support

**Issues**: https://github.com/tosin2013/ansible-collection-mcp-audit/issues
**Discussions**: https://github.com/tosin2013/ansible-collection-mcp-audit/discussions

---

**Last Updated**: November 2, 2025
**Maintained By**: Code Index MCP Team
