# MCP Testing Integration Plan - tosin2013.mcp_audit

This document provides a comprehensive plan for integrating the **tosin2013.mcp_audit** Ansible collection into our Code Index MCP testing workflow.

## Executive Summary

We are adopting the **tosin2013.mcp_audit** Ansible collection (v1.1.0+) for automated testing and validation of our Code Index MCP server. This collection provides:

- ✅ **Automated MCP Testing**: Systematic testing of all MCP tools, resources, and prompts
- ✅ **Multi-Transport Support**: stdio (local), HTTP/SSE (cloud)
- ✅ **Multi-Platform**: Google Cloud, AWS, OpenShift
- ✅ **LLM Integration Testing**: End-to-end validation with real LLMs (100+ providers via LiteLLM)
- ✅ **CI/CD Ready**: Native GitHub Actions/GitLab CI integration
- ✅ **Professional Grade**: Production-ready testing framework from Ansible Galaxy

**Collection**: https://galaxy.ansible.com/ui/repo/published/tosin2013/mcp_audit/
**GitHub**: https://github.com/tosin2013/ansible-collection-mcp-audit

## What is tosin2013.mcp_audit?

An Ansible collection specifically designed for testing and auditing Model Context Protocol (MCP) servers. Key features:

### Available Modules

1. **mcp_server_info** - Discover server capabilities and metadata
2. **mcp_test_tool** - Test individual MCP tools with expected results
3. **mcp_test_resource** - Test MCP resource retrieval
4. **mcp_test_prompt** - Test prompt templates
5. **mcp_test_suite** - Run comprehensive test suites with reporting
6. **mcp_test_llm_integration** - End-to-end testing with real LLMs

### Supported Features

- **Transport Protocols**: stdio, SSE (Server-Sent Events), HTTP
- **Programming Languages**: Python and TypeScript MCP servers
- **LLM Providers**: Ollama, OpenRouter, OpenAI, Anthropic, vLLM, and 100+ via LiteLLM
- **Platform Compatibility**: RHEL 9/10, Python 3.10+, ansible-core 2.15+
- **Result Formats**: JSON, YAML, structured reports

## Integration with Our Project

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              Our Code Index MCP Project                 │
│                                                         │
│  ┌──────────────────┐      ┌──────────────────┐        │
│  │  Deployment      │      │  Testing         │        │
│  │  (ADR 0009)      │─────▶│  (ADR 0010)      │        │
│  │                  │      │                  │        │
│  │  Ansible:        │      │  Ansible:        │        │
│  │  • Deploy GCP    │      │  • mcp_audit     │        │
│  │  • Deploy AWS    │      │  • Local tests   │        │
│  │  • Deploy OS     │      │  • Cloud tests   │        │
│  └──────────────────┘      │  • LLM tests     │        │
│                            └──────────────────┘        │
│                                     │                   │
└─────────────────────────────────────┼───────────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────┐
                        │  tosin2013.mcp_audit    │
                        │  Collection             │
                        │  • 6 modules            │
                        │  • Multi-transport      │
                        │  • LLM integration      │
                        └─────────────────────────┘
```

### How It Complements ADR 0009 (Ansible Deployment)

| Phase | ADR 0009 (Deployment) | ADR 0010 (Testing) |
|-------|----------------------|-------------------|
| **1. Deploy** | ✅ `ansible-playbook deploy.yml` | - |
| **2. Validate** | - | ✅ `ansible-playbook test-cloud.yml` |
| **3. Pass/Fail** | - | ✅ Green: promote to staging |
| **4. Staging Deploy** | ✅ `ansible-playbook deploy.yml -i staging` | - |
| **5. Staging Test** | - | ✅ `ansible-playbook test-regression.yml` |
| **6. Production** | ✅ Deploy if tests pass | ✅ Final validation |

**Key Benefit**: Every deployment is automatically validated before promotion.

## What We've Created

### 1. ADR 0010: MCP Server Testing with Ansible

**Location**: `docs/adrs/0010-mcp-server-testing-with-ansible.md`

**Contents**:
- Complete testing strategy and rationale
- Architecture diagrams and workflows
- Comparison: Manual vs Automated testing
- Integration with deployment (ADR 0009)
- CI/CD pipeline examples
- Implementation status and roadmap

**Key Decisions**:
- ✅ Use tosin2013.mcp_audit for all MCP testing
- ✅ Test both stdio (local) and HTTP/SSE (cloud) transports
- ✅ Integrate LLM testing with Ollama (free) and OpenRouter (paid)
- ✅ Run regression suite before production deployments

### 2. Test Infrastructure

**Location**: `tests/ansible/`

**Created Files**:
```
tests/ansible/
├── README.md                    ✅ Complete testing documentation
├── requirements.yml             ✅ Ansible Galaxy dependencies
├── ansible.cfg                  ✅ Ansible configuration
├── inventory/
│   ├── local.yml               ✅ Local stdio testing config
│   └── gcp-dev.yml             ✅ GCP cloud testing config
└── test-local.yml              ✅ Local stdio test playbook
```

**Test Coverage**:
- ✅ Server discovery and capabilities
- ✅ set_project_path tool
- ✅ refresh_index tool
- ✅ find_files tool
- ✅ search_code_advanced tool
- ✅ File resource retrieval
- 🚧 Cloud-specific tools (semantic search, git ingestion)
- 🚧 LLM integration tests

### 3. Updated ADR Index

**Location**: `docs/adrs/README.md`

**Updates**:
- ✅ Added ADR 0010 to quick reference table
- ✅ Updated decision timeline with DevOps & Automation section
- ✅ Documented relationship between ADR 0009 (deployment) and ADR 0010 (testing)

## Quick Start Guide

### Installation

```bash
# 1. Install Ansible (if not already installed)
pip install ansible

# 2. Install required collections
cd tests/ansible
ansible-galaxy collection install -r requirements.yml
```

This installs:
- `tosin2013.mcp_audit` (v1.1.0+) - MCP testing modules
- `google.cloud` - For GCP cloud testing
- `community.general` - General utilities

### Run Your First Test

#### Local Testing (stdio mode)

```bash
# Test the MCP server running locally
cd tests/ansible
ansible-playbook test-local.yml -i inventory/local.yml
```

**Expected Output**:
```
PLAY [Test Code Index MCP Server - Local stdio Mode] *******************

TASK [Get server information] *******************************************
ok: [localhost]

TASK [Validate server basic info] ***************************************
ok: [localhost] => {
    "msg": "✅ Server info validation passed"
}

TASK [Test set_project_path tool] ***************************************
ok: [localhost]

...

PLAY RECAP **************************************************************
localhost : ok=12   changed=2   unreachable=0   failed=0
```

#### Cloud Testing (HTTP/SSE mode)

```bash
# 1. Set environment variables
export CLOUDRUN_SERVICE_URL="https://code-index-mcp-dev-xxxxx.run.app"
export MCP_API_KEY_DEV="ci_your_api_key_here"

# 2. Update inventory with your values
vim inventory/gcp-dev.yml

# 3. Run cloud tests
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
```

**Note**: Cloud tests require a deployed MCP server (see ADR 0009).

## Integration Workflow

### Development Workflow

```bash
# 1. Make code changes
vim src/code_index_mcp/server.py

# 2. Test locally (fast feedback)
cd tests/ansible
ansible-playbook test-local.yml -i inventory/local.yml

# 3. If local tests pass, deploy to dev
cd ../../deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml

# 4. Test dev deployment
cd ../../tests/ansible
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml

# 5. If all tests pass, commit
git add .
git commit -m "feat: Add new MCP tool with tests"
```

### CI/CD Workflow

**GitHub Actions** (recommended):
```yaml
# .github/workflows/test-and-deploy.yml
name: Test and Deploy

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test-local:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: |
          pip install ansible
          ansible-galaxy collection install -r tests/ansible/requirements.yml
          pip install -e .
      - name: Run local tests
        run: |
          cd tests/ansible
          ansible-playbook test-local.yml -i inventory/local.yml

  deploy-dev:
    needs: test-local
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to dev
        run: |
          cd deployment/gcp/ansible
          ansible-playbook deploy.yml -i inventory/dev.yml
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_SA_KEY }}

  test-cloud:
    needs: deploy-dev
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Test cloud deployment
        run: |
          cd tests/ansible
          ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
        env:
          CLOUDRUN_SERVICE_URL: ${{ needs.deploy-dev.outputs.service_url }}
          MCP_API_KEY: ${{ secrets.MCP_API_KEY_DEV }}

  # Only deploy to production if all tests pass
  deploy-production:
    needs: test-cloud
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to production
        run: |
          cd deployment/gcp/ansible
          ansible-playbook deploy.yml -i inventory/prod.yml
```

## Test Scenarios by Environment

### Local Development (stdio)

**What to test**:
- ✅ All metadata-based tools (search, find, index)
- ✅ File resource retrieval
- ✅ Server capabilities
- ❌ Semantic search (requires cloud AlloyDB)
- ❌ Git ingestion (requires cloud storage)

**Command**:
```bash
ansible-playbook test-local.yml -i inventory/local.yml
```

### Cloud Development (HTTP/SSE)

**What to test**:
- ✅ All metadata-based tools
- ✅ Semantic search (if AlloyDB deployed)
- ✅ Git ingestion (if cloud storage configured)
- ✅ LLM integration (if enabled)
- ✅ Multi-user isolation

**Command**:
```bash
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
```

### Staging/Pre-Production

**What to test**:
- ✅ Full regression suite
- ✅ LLM integration with multiple providers
- ✅ Performance benchmarks
- ✅ Security validation

**Command**:
```bash
ansible-playbook test-regression.yml -i inventory/gcp-staging.yml
```

### Production

**What to test**:
- ✅ Smoke tests (basic functionality)
- ✅ Critical path validation
- ✅ Performance monitoring

**Command**:
```bash
ansible-playbook test-cloud.yml -i inventory/gcp-prod.yml \
  --tags smoke
```

## LLM Integration Testing

One of the most powerful features of mcp_audit is end-to-end LLM testing.

### With Ollama (Local, Free)

```bash
# 1. Start Ollama locally
ollama serve

# 2. Pull a model
ollama pull llama3.2

# 3. Run LLM integration tests
cd tests/ansible
ansible-playbook test-llm-integration.yml -i inventory/gcp-dev.yml \
  -e "llm_provider=ollama" \
  -e "llm_model=llama3.2" \
  -e "llm_base_url=http://localhost:11434"
```

**Test validates**:
- ✅ LLM can connect to MCP server
- ✅ LLM correctly interprets tool schemas
- ✅ LLM calls appropriate tools for prompts
- ✅ MCP server returns valid responses

### With OpenRouter (Cloud, Paid)

```bash
# 1. Set API key
export OPENROUTER_API_KEY="sk-or-xxxxx"

# 2. Run tests with Claude 3.5 Sonnet
ansible-playbook test-llm-integration.yml -i inventory/gcp-dev.yml \
  -e "llm_provider=openrouter" \
  -e "llm_model=anthropic/claude-3.5-sonnet"
```

**Supported Providers** (100+ via LiteLLM):
- Anthropic Claude (via OpenRouter)
- OpenAI GPT
- Google Gemini
- Meta Llama (via OpenRouter)
- Mistral AI
- vLLM (custom endpoints)
- And many more...

## Roadmap

### Phase 1: Foundation (✅ Complete)
- ✅ Install mcp_audit collection
- ✅ Create ADR 0010
- ✅ Set up test infrastructure
- ✅ Create test-local.yml playbook
- ✅ Update documentation

### Phase 2: Local Testing (🚧 In Progress)
- ✅ Test all metadata tools
- 🚧 Test resource retrieval
- 🚧 Create comprehensive test suite
- 🚧 Validate against multiple projects

### Phase 3: Cloud Testing (📋 Planned)
- Create test-cloud.yml playbook
- Test HTTP/SSE transport
- Test semantic search tools (when AlloyDB deployed)
- Test git ingestion
- Validate multi-user isolation

### Phase 4: LLM Integration (📋 Planned)
- Create test-llm-integration.yml playbook
- Set up Ollama local testing
- Configure OpenRouter integration
- Test with multiple LLM providers
- Validate tool calling accuracy

### Phase 5: Regression Suite (📋 Planned)
- Create test-regression.yml playbook
- Define comprehensive test cases
- Set up baseline metrics
- Integrate with CI/CD
- Establish SLOs (Service Level Objectives)

### Phase 6: Production Deployment (📋 Planned)
- Production test playbooks
- Monitoring and alerting integration
- Performance benchmarking
- Security validation
- Documentation for operations team

## Best Practices

### 1. Always Test Locally First

```bash
# Fast, free, no cloud costs
ansible-playbook test-local.yml -i inventory/local.yml
```

### 2. Use Different API Keys Per Environment

```bash
# Never share API keys between environments
export MCP_API_KEY_DEV="ci_dev_key"
export MCP_API_KEY_STAGING="ci_staging_key"
export MCP_API_KEY_PROD="ci_prod_key"
```

### 3. Run Regression Before Production

```bash
# Catch issues before they hit production
ansible-playbook test-regression.yml -i inventory/gcp-staging.yml

# Only deploy to prod if tests pass
if [ $? -eq 0 ]; then
    cd ../../deployment/gcp/ansible
    ansible-playbook deploy.yml -i inventory/prod.yml
fi
```

### 4. Use Ollama for Cost-Free LLM Testing

```bash
# Ollama runs locally, no API costs
ansible-playbook test-llm-integration.yml \
  -e "llm_provider=ollama" \
  -e "llm_model=llama3.2"

# Save OpenRouter for critical production tests
```

### 5. Store Test Results

```bash
# Save test reports for trend analysis
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml | \
  tee test-report-$(date +%Y%m%d-%H%M%S).log
```

## Troubleshooting

### Collection Not Found

```bash
ERROR! couldn't resolve module 'tosin2013.mcp_audit.mcp_server_info'
```

**Solution**:
```bash
ansible-galaxy collection install tosin2013.mcp_audit
```

### Connection Refused (Cloud Tests)

```bash
FAILED! => {"msg": "Connection refused"}
```

**Checklist**:
1. Is CLOUDRUN_SERVICE_URL correct?
2. Is the service deployed?
3. Is the API key valid?
4. Check network/firewall

### Tool Not Found

```bash
FAILED! => {"msg": "Tool 'semantic_search_code' not available"}
```

**Causes**:
1. stdio mode: semantic search only works in cloud (requires AlloyDB)
2. Cloud mode: AlloyDB not deployed
3. Version mismatch

## Resources

### Documentation
- **ADR 0010**: Full testing strategy (docs/adrs/0010-mcp-server-testing-with-ansible.md)
- **Test README**: Testing guide (tests/ansible/README.md)
- **ADR 0009**: Deployment automation (docs/adrs/0009-ansible-deployment-automation.md)

### Collection Documentation
- **Ansible Galaxy**: https://galaxy.ansible.com/ui/repo/published/tosin2013/mcp_audit/
- **GitHub**: https://github.com/tosin2013/ansible-collection-mcp-audit
- **README**: https://github.com/tosin2013/ansible-collection-mcp-audit/blob/main/README.md
- **AGENTS.md**: AI agent coding guide

### MCP Resources
- **MCP Protocol**: https://modelcontextprotocol.io/
- **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
- **LiteLLM**: https://docs.litellm.ai/ (LLM provider integration)

## Next Steps

1. **Install the collection**:
   ```bash
   cd tests/ansible
   ansible-galaxy collection install -r requirements.yml
   ```

2. **Run your first test**:
   ```bash
   ansible-playbook test-local.yml -i inventory/local.yml
   ```

3. **Review the results** and iterate on test coverage

4. **Integrate with CI/CD** using the GitHub Actions example

5. **Deploy to cloud** and run cloud tests

6. **Set up LLM testing** with Ollama

7. **Build comprehensive regression suite**

---

**Status**: ADR 0010 Accepted ✅
**Implementation**: Phase 1 Complete, Phase 2-6 Planned
**Last Updated**: November 2, 2025
**Maintained By**: Code Index MCP Team
