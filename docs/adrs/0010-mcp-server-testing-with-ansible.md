# ADR 0010: MCP Server Testing and Validation with Ansible

**Status**: Accepted
**Date**: 2025-11-02
**Decision Maker**: Architecture Team
**Testing Framework**: tosin2013.mcp_audit (Ansible Collection)
**Related to**: ADR 0009 (Ansible Deployment Automation), ADR 0001 (MCP Transport Protocols)

## Context

### The Problem with Manual MCP Testing

After deploying our Code Index MCP server to Google Cloud Run (ADR 0002), AWS Lambda (ADR 0006), or OpenShift (ADR 0007), we need **automated validation** that the server works correctly across:

1. **Multiple Transports**: stdio (local), HTTP/SSE (cloud)
2. **Tool Invocations**: All MCP tools return correct results
3. **Resource Retrieval**: File content resources work properly
4. **End-to-End Flows**: LLM → MCP tool → Result validation
5. **Multi-Environment**: Dev, staging, production consistency
6. **Regression Prevention**: Deployments don't break existing functionality

**Current Manual Testing**:
```bash
# ❌ Manual, error-prone, not repeatable
curl https://code-index-mcp-dev.run.app/sse
# Manually construct MCP JSON-RPC requests
# Copy-paste tool arguments
# Manually validate response structure
# No systematic coverage of all tools
# No LLM integration testing
```

**Problems**:
- ❌ No systematic test coverage
- ❌ Not repeatable across environments
- ❌ Manual validation of complex JSON responses
- ❌ No regression testing
- ❌ No CI/CD integration
- ❌ Can't test stdio transport in cloud
- ❌ No end-to-end LLM testing

### Requirements for Production Testing

1. **Automated**: Run tests without manual intervention
2. **Comprehensive**: Test all tools, resources, prompts
3. **Multi-Transport**: stdio, HTTP/SSE
4. **Multi-Environment**: Dev, staging, production
5. **CI/CD Integration**: Run on every deployment
6. **End-to-End**: Test with real LLMs (Ollama, OpenRouter, etc.)
7. **Regression Prevention**: Detect breaking changes
8. **Clear Reports**: JSON/YAML test results

## Decision: Use tosin2013.mcp_audit Ansible Collection

Use the **tosin2013.mcp_audit** Ansible collection (v1.1.0+) for automated testing and validation of our Code Index MCP server across all deployment targets.

**Collection**: https://galaxy.ansible.com/ui/repo/published/tosin2013/mcp_audit/
**GitHub**: https://github.com/tosin2013/ansible-collection-mcp-audit
**License**: GPL-3.0-or-later (compatible with our project)

## Architecture

### Overview

```
┌─────────────────────────────────────────────────────┐
│              Ansible Control Node                   │
│         (Developer Laptop / CI/CD Runner)           │
└────────────────────┬────────────────────────────────┘
                     │
                     │ Test Playbooks (YAML)
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│  test_local.yml  │    │  test_cloud.yml  │
│  (stdio mode)    │    │  (HTTP/SSE mode) │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         │ tosin2013.mcp_audit   │
         │    collection         │
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  Local Process   │    │  Cloud Service   │
│  ─────────────   │    │  ─────────────   │
│  code-index-mcp  │    │  Cloud Run       │
│  (stdio)         │    │  Lambda          │
│                  │    │  OpenShift Pod   │
└──────────────────┘    └──────────────────┘
         │                       │
         │ MCP JSON-RPC          │
         ▼                       ▼
┌─────────────────────────────────────────┐
│         Test Assertions                 │
│  ✅ Tool responses valid                │
│  ✅ Resources return file content       │
│  ✅ Search returns correct results      │
│  ✅ LLM integration works end-to-end    │
└─────────────────────────────────────────┘
```

### Testing Workflow

```
1. Deploy MCP Server (via ADR 0009 Ansible playbooks)
   ├── Google Cloud Run (HTTP/SSE)
   ├── AWS Lambda (HTTP/SSE)
   └── OpenShift Pod (HTTP/SSE)

2. Run Test Suite (this ADR)
   │
   ├── Phase 1: Server Discovery
   │   └── tosin2013.mcp_audit.mcp_server_info
   │       ├── Validate server capabilities
   │       ├── Check protocol version
   │       └── Enumerate available tools/resources
   │
   ├── Phase 2: Tool Testing
   │   └── tosin2013.mcp_audit.mcp_test_tool
   │       ├── test semantic_search_code
   │       ├── test find_similar_code
   │       ├── test ingest_code_from_git
   │       ├── test search_code_advanced
   │       ├── test find_files
   │       └── test get_file_summary
   │
   ├── Phase 3: Resource Testing
   │   └── tosin2013.mcp_audit.mcp_test_resource
   │       ├── test file content retrieval
   │       └── test resource URI patterns
   │
   ├── Phase 4: End-to-End LLM Testing
   │   └── tosin2013.mcp_audit.mcp_test_llm_integration
   │       ├── Ollama (local, no API key)
   │       ├── OpenRouter (API key)
   │       └── vLLM (custom endpoint)
   │
   └── Phase 5: Regression Suite
       └── tosin2013.mcp_audit.mcp_test_suite
           ├── Run all tests in sequence
           ├── Generate comprehensive report
           └── Fail on any test failure

3. Report Results
   └── JSON/YAML test results
       ├── Store in artifacts
       ├── Notify on failures
       └── Track trends over time
```

## Implementation

### Directory Structure

```
tests/ansible/
├── README.md                           # Testing documentation
├── requirements.yml                    # Ansible Galaxy dependencies
├── ansible.cfg                         # Ansible configuration
├── inventory/
│   ├── local.yml                      # Local stdio testing
│   ├── gcp-dev.yml                    # GCP dev environment
│   ├── gcp-staging.yml                # GCP staging
│   ├── gcp-prod.yml                   # GCP production
│   ├── aws-dev.yml                    # AWS dev (future)
│   └── openshift-prod.yml             # OpenShift prod (future)
├── test-local.yml                     # Local stdio test playbook
├── test-cloud.yml                     # Cloud HTTP/SSE test playbook
├── test-llm-integration.yml           # LLM end-to-end tests
├── test-regression.yml                # Full regression suite
└── vars/
    ├── expected_tools.yml             # Expected tool list
    ├── test_data.yml                  # Test input data
    └── llm_credentials.yml            # LLM API keys (encrypted)
```

### Installation

```bash
# Install the mcp_audit collection from Ansible Galaxy
ansible-galaxy collection install tosin2013.mcp_audit

# Or install from requirements.yml
# requirements.yml:
# collections:
#   - name: tosin2013.mcp_audit
#     version: ">=1.1.0"

ansible-galaxy collection install -r requirements.yml
```

### Test Playbooks

#### 1. Local Testing (stdio mode)

`tests/ansible/test-local.yml`:
```yaml
---
- name: Test Code Index MCP Server - Local stdio Mode
  hosts: localhost
  connection: local
  gather_facts: yes

  vars:
    # Path to local MCP server script
    mcp_server_command: "{{ ansible_python_interpreter }}"
    mcp_server_args:
      - "-m"
      - "code_index_mcp.server"

  tasks:
    - name: Get server information
      tosin2013.mcp_audit.mcp_server_info:
        transport: stdio
        server_command: "{{ mcp_server_command }}"
        server_args: "{{ mcp_server_args }}"
      register: server_info

    - name: Validate server capabilities
      ansible.builtin.assert:
        that:
          - server_info.success
          - server_info.server_info.server_name == "CodeIndexer"
          - server_info.server_info.capabilities.tools is defined
          - server_info.server_info.capabilities.resources is defined
        msg: "Server info validation failed"

    - name: Test set_project_path tool
      tosin2013.mcp_audit.mcp_test_tool:
        transport: stdio
        server_command: "{{ mcp_server_command }}"
        server_args: "{{ mcp_server_args }}"
        tool_name: set_project_path
        tool_arguments:
          path: "/tmp/test-project"
      register: set_path_result

    - name: Validate set_project_path response
      ansible.builtin.assert:
        that:
          - set_path_result.success
          - set_path_result.test_passed
        msg: "set_project_path test failed"

    - name: Test search_code_advanced tool
      tosin2013.mcp_audit.mcp_test_tool:
        transport: stdio
        server_command: "{{ mcp_server_command }}"
        server_args: "{{ mcp_server_args }}"
        tool_name: search_code_advanced
        tool_arguments:
          query: "def.*main"
          use_regex: true
      register: search_result

    - name: Validate search results structure
      ansible.builtin.assert:
        that:
          - search_result.success
          - search_result.tool_result is defined
        msg: "search_code_advanced test failed"

    - name: Test file resource retrieval
      tosin2013.mcp_audit.mcp_test_resource:
        transport: stdio
        server_command: "{{ mcp_server_command }}"
        server_args: "{{ mcp_server_args }}"
        resource_uri: "file:///tmp/test-project/src/main.py"
      register: resource_result

    - name: Validate resource content
      ansible.builtin.assert:
        that:
          - resource_result.success
          - resource_result.resource_content is defined
        msg: "Resource retrieval test failed"
```

#### 2. Cloud Testing (HTTP/SSE mode)

`tests/ansible/test-cloud.yml`:
```yaml
---
- name: Test Code Index MCP Server - Cloud HTTP/SSE Mode
  hosts: localhost
  connection: local
  gather_facts: yes

  vars:
    # Cloud Run service URL (from deployment)
    mcp_server_url: "{{ lookup('env', 'CLOUDRUN_SERVICE_URL') }}"
    api_key: "{{ lookup('env', 'MCP_API_KEY') }}"

  tasks:
    - name: Validate environment variables
      ansible.builtin.assert:
        that:
          - mcp_server_url | length > 0
          - api_key | length > 0
        msg: "CLOUDRUN_SERVICE_URL and MCP_API_KEY must be set"

    - name: Get server information via SSE
      tosin2013.mcp_audit.mcp_server_info:
        transport: sse
        server_url: "{{ mcp_server_url }}/sse"
        headers:
          Authorization: "Bearer {{ api_key }}"
      register: server_info

    - name: Validate server capabilities
      ansible.builtin.assert:
        that:
          - server_info.success
          - server_info.server_info.server_name == "CodeIndexer"
        msg: "Server info validation failed"

    - name: Test semantic_search_code tool (Cloud-only)
      tosin2013.mcp_audit.mcp_test_tool:
        transport: sse
        server_url: "{{ mcp_server_url }}/sse"
        headers:
          Authorization: "Bearer {{ api_key }}"
        tool_name: semantic_search_code
        tool_arguments:
          query: "authentication logic"
          language: "python"
          top_k: 10
      register: semantic_search

    - name: Validate semantic search results
      ansible.builtin.assert:
        that:
          - semantic_search.success
          - semantic_search.test_passed
          - semantic_search.tool_result.results | length > 0
        msg: "semantic_search_code test failed"

    - name: Test ingest_code_from_git tool
      tosin2013.mcp_audit.mcp_test_tool:
        transport: sse
        server_url: "{{ mcp_server_url }}/sse"
        headers:
          Authorization: "Bearer {{ api_key }}"
        tool_name: ingest_code_from_git
        tool_arguments:
          git_url: "https://github.com/anthropics/anthropic-sdk-python"
          project_name: "anthropic-sdk-test"
          branch: "main"
      register: git_ingest

    - name: Validate git ingestion
      ansible.builtin.assert:
        that:
          - git_ingest.success
          - git_ingest.tool_result.chunks_ingested > 0
        msg: "ingest_code_from_git test failed"
```

#### 3. LLM Integration Testing

`tests/ansible/test-llm-integration.yml`:
```yaml
---
- name: Test Code Index MCP - LLM Integration (End-to-End)
  hosts: localhost
  connection: local
  gather_facts: yes

  vars:
    mcp_server_url: "{{ lookup('env', 'CLOUDRUN_SERVICE_URL') }}"
    api_key: "{{ lookup('env', 'MCP_API_KEY') }}"
    # LLM credentials (store in Ansible Vault)
    openrouter_api_key: "{{ lookup('ansible.builtin.env', 'OPENROUTER_API_KEY') }}"

  tasks:
    - name: Test with Ollama (no API key needed)
      tosin2013.mcp_audit.mcp_test_llm_integration:
        transport: sse
        server_url: "{{ mcp_server_url }}/sse"
        headers:
          Authorization: "Bearer {{ api_key }}"
        llm_provider: ollama
        llm_model: llama3.2
        llm_base_url: http://localhost:11434
        test_prompt: "Search for authentication functions in the codebase"
        expected_tool: semantic_search_code
        validate_tool_called: true
      register: ollama_test
      when: ollama_available | default(false)

    - name: Test with OpenRouter (API key required)
      tosin2013.mcp_audit.mcp_test_llm_integration:
        transport: sse
        server_url: "{{ mcp_server_url }}/sse"
        headers:
          Authorization: "Bearer {{ api_key }}"
        llm_provider: openrouter
        llm_model: anthropic/claude-3.5-sonnet
        llm_api_key: "{{ openrouter_api_key }}"
        test_prompt: "Find files containing database migration code"
        expected_tool: search_code_advanced
        validate_tool_called: true
      register: openrouter_test
      when: openrouter_api_key | length > 0

    - name: Validate LLM integration results
      ansible.builtin.assert:
        that:
          - ollama_test.success or openrouter_test.success
          - (ollama_test.tool_called | default(false)) or (openrouter_test.tool_called | default(false))
        msg: "LLM integration test failed"
```

#### 4. Full Regression Suite

`tests/ansible/test-regression.yml`:
```yaml
---
- name: Code Index MCP - Full Regression Test Suite
  hosts: localhost
  connection: local
  gather_facts: yes

  vars:
    mcp_server_url: "{{ lookup('env', 'CLOUDRUN_SERVICE_URL') }}"
    api_key: "{{ lookup('env', 'MCP_API_KEY') }}"

  tasks:
    - name: Run comprehensive test suite
      tosin2013.mcp_audit.mcp_test_suite:
        transport: sse
        server_url: "{{ mcp_server_url }}/sse"
        headers:
          Authorization: "Bearer {{ api_key }}"
        tests:
          - name: "Server Discovery"
            type: server_info
            expected_server_name: "CodeIndexer"

          - name: "Semantic Search - Python Functions"
            type: tool
            tool_name: semantic_search_code
            arguments:
              query: "function that handles user authentication"
              language: "python"
              top_k: 5
            expected_result:
              results: []  # Should have at least one result

          - name: "Code Search - Regex Pattern"
            type: tool
            tool_name: search_code_advanced
            arguments:
              query: "class.*Service"
              use_regex: true
            expected_result:
              results: []

          - name: "File Discovery"
            type: tool
            tool_name: find_files
            arguments:
              pattern: "*.py"
            expected_result:
              files: []

          - name: "File Summary"
            type: tool
            tool_name: get_file_summary
            arguments:
              file_path: "src/code_index_mcp/server.py"
            expected_result:
              summary: {}

          - name: "Git Ingestion"
            type: tool
            tool_name: ingest_code_from_git
            arguments:
              git_url: "https://github.com/anthropics/anthropic-sdk-python"
              project_name: "anthropic-sdk-regression"
            expected_result:
              chunks_ingested: 0  # Should be > 0

        report_format: yaml
        fail_on_error: true
      register: regression_results

    - name: Display test summary
      ansible.builtin.debug:
        msg:
          - "Tests Run: {{ regression_results.tests_run }}"
          - "Tests Passed: {{ regression_results.tests_passed }}"
          - "Tests Failed: {{ regression_results.tests_failed }}"

    - name: Save test report
      ansible.builtin.copy:
        content: "{{ regression_results.report }}"
        dest: "./test-report-{{ ansible_date_time.epoch }}.yml"

    - name: Fail if any tests failed
      ansible.builtin.fail:
        msg: "{{ regression_results.tests_failed }} tests failed"
      when: regression_results.tests_failed > 0
```

### Inventory Configuration

#### Local Testing (`inventory/local.yml`)

```yaml
all:
  vars:
    transport: stdio
    mcp_server_command: "{{ ansible_python_interpreter }}"
    mcp_server_args:
      - "-m"
      - "code_index_mcp.server"
```

#### GCP Development (`inventory/gcp-dev.yml`)

```yaml
all:
  vars:
    transport: sse
    gcp_project_id: "your-project-dev"
    gcp_region: "us-east1"
    env_name: "dev"

    # Cloud Run service URL (from terraform output or ansible deploy)
    mcp_server_url: "https://code-index-mcp-dev-xxxx.run.app"

    # API key (from Secret Manager or ansible generate_api_key)
    api_key: "{{ lookup('ansible.builtin.env', 'MCP_API_KEY_DEV') }}"

    # LLM testing
    ollama_available: true
    ollama_base_url: "http://localhost:11434"
```

#### GCP Production (`inventory/gcp-prod.yml`)

```yaml
all:
  vars:
    transport: sse
    gcp_project_id: "your-project-prod"
    gcp_region: "us-central1"
    env_name: "prod"

    mcp_server_url: "https://code-index-mcp-prod-xxxx.run.app"
    api_key: "{{ lookup('ansible.builtin.env', 'MCP_API_KEY_PROD') }}"

    # Production LLM testing (more thorough)
    openrouter_api_key: "{{ lookup('ansible.builtin.env', 'OPENROUTER_API_KEY') }}"
    run_llm_tests: true
```

## Benefits

### 1. Automated Validation

**Before (Manual)**:
```bash
# ❌ Manual cURL requests, error-prone
curl -X POST https://server.run.app/sse \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":...}'
# ❌ Copy-paste JSON, easy to make mistakes
# ❌ No validation of response structure
```

**After (Ansible)**:
```bash
# ✅ Declarative, repeatable, validated
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
# ✅ All tools tested systematically
# ✅ Response structure validated
# ✅ Results saved for analysis
```

### 2. Multi-Transport Testing

```yaml
# Same test playbook, different transports
- include_tasks: test_semantic_search.yml
  vars:
    transport: stdio  # Local testing

- include_tasks: test_semantic_search.yml
  vars:
    transport: sse    # Cloud testing
```

### 3. CI/CD Integration

**GitHub Actions Example**:
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
      - name: Install Ansible
        run: |
          pip install ansible
          ansible-galaxy collection install tosin2013.mcp_audit

      - name: Run local tests
        run: |
          cd tests/ansible
          ansible-playbook test-local.yml -i inventory/local.yml

  test-cloud:
    needs: test-local
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install Ansible
        run: |
          pip install ansible
          ansible-galaxy collection install tosin2013.mcp_audit

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
          CLOUDRUN_SERVICE_URL: ${{ steps.deploy.outputs.service_url }}
          MCP_API_KEY: ${{ secrets.MCP_API_KEY_DEV }}

      - name: Upload test results
        uses: actions/upload-artifact@v3
        with:
          name: test-reports
          path: tests/ansible/test-report-*.yml
```

### 4. Regression Prevention

```bash
# Run full regression suite before promoting to production
ansible-playbook test-regression.yml -i inventory/gcp-staging.yml

# If tests pass, promote to production
ansible-playbook deploy.yml -i inventory/prod.yml
```

### 5. LLM Integration Validation

```bash
# Test that LLMs can successfully call our MCP tools
ansible-playbook test-llm-integration.yml -i inventory/gcp-dev.yml

# Validates:
# ✅ LLM can connect to MCP server
# ✅ LLM correctly interprets tool schemas
# ✅ LLM calls appropriate tools for user prompts
# ✅ MCP server returns valid responses
# ✅ End-to-end flow works
```

## Comparison: Manual vs Automated Testing

| Feature | Manual Testing | Ansible Automated | Winner |
|---------|---------------|------------------|--------|
| **Repeatability** | Manual cURL | Declarative YAML | ✅ Ansible |
| **Coverage** | Ad-hoc | Systematic | ✅ Ansible |
| **Validation** | Manual inspection | Automated assertions | ✅ Ansible |
| **Multi-Environment** | Different scripts | Same playbook | ✅ Ansible |
| **CI/CD Integration** | Difficult | Native | ✅ Ansible |
| **LLM Testing** | Not practical | Built-in | ✅ Ansible |
| **Regression Testing** | Manual checklist | Automated suite | ✅ Ansible |
| **Reporting** | Manual notes | JSON/YAML reports | ✅ Ansible |
| **Setup Time** | Low | Medium | ⚠️ Manual |
| **Learning Curve** | Low | Medium | ⚠️ Manual |

**Verdict**: Ansible wins 8/2 - essential for production MCP servers

## Integration with ADR 0009 (Deployment)

### Combined Workflow

```bash
# 1. Deploy to dev (ADR 0009)
cd deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml

# 2. Test deployment (this ADR)
cd ../../tests/ansible
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml

# 3. If tests pass, deploy to staging
cd ../../deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/staging.yml

# 4. Test staging
cd ../../tests/ansible
ansible-playbook test-regression.yml -i inventory/gcp-staging.yml

# 5. If all tests pass, deploy to production
cd ../../deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/prod.yml

# 6. Final production validation
cd ../../tests/ansible
ansible-playbook test-cloud.yml -i inventory/gcp-prod.yml
```

### CI/CD Pipeline Integration

```
┌─────────────────────────────────────────┐
│          CI/CD Pipeline                 │
│  ─────────────────────────────────────  │
│  1. Code commit to main branch          │
│  2. Build Docker image                  │
│  3. Deploy to dev (ADR 0009)            │
│  4. Test dev deployment (ADR 0010) ◄──┐ │
│     ├── If pass: continue              │ │
│     └── If fail: abort, notify         │ │
│  5. Deploy to staging (ADR 0009)       │ │
│  6. Test staging (ADR 0010) ◄──────────┤ │
│     ├── If pass: continue              │ │
│     └── If fail: abort, notify         │ │
│  7. Manual approval                    │ │
│  8. Deploy to production (ADR 0009)    │ │
│  9. Test production (ADR 0010) ◄───────┘ │
│     ├── If pass: success notification   │
│     └── If fail: rollback, alert        │
└─────────────────────────────────────────┘
```

## Implementation Status

### ✅ Phase 1: Collection Setup (Complete)
- ✅ Install tosin2013.mcp_audit v1.1.0
- ✅ Verify compatibility with Python 3.11+
- ✅ Test collection modules locally

### 🚧 Phase 2: Local Testing (In Progress)
- ✅ Create test-local.yml playbook
- ✅ Create inventory/local.yml
- 🚧 Test all stdio tools
- 🚧 Validate local test coverage

### 📋 Phase 3: Cloud Testing (Planned)
- Create test-cloud.yml playbook
- Create GCP inventories (dev/staging/prod)
- Test HTTP/SSE transport
- Validate cloud-specific tools (semantic search, git ingestion)

### 📋 Phase 4: LLM Integration (Planned)
- Create test-llm-integration.yml
- Configure Ollama for local testing
- Set up OpenRouter credentials (Vault)
- Test end-to-end LLM → MCP flows

### 📋 Phase 5: Regression Suite (Planned)
- Create test-regression.yml
- Define comprehensive test cases
- Set up CI/CD integration
- Establish baseline metrics

### 📋 Phase 6: Documentation (Planned)
- Create tests/ansible/README.md
- Document test playbooks
- Add troubleshooting guide
- Create runbook for test failures

## Consequences

### Positive

- ✅ **Automated Validation**: Every deployment automatically tested
- ✅ **Regression Prevention**: Breaking changes caught before production
- ✅ **Multi-Environment**: Consistent testing across dev/staging/prod
- ✅ **CI/CD Ready**: Native integration with GitHub Actions/GitLab CI
- ✅ **LLM Testing**: End-to-end validation with real LLMs
- ✅ **Comprehensive**: All tools, resources, transports tested
- ✅ **Repeatable**: Same tests run identically every time
- ✅ **Reporting**: JSON/YAML reports for trend analysis
- ✅ **No Manual Work**: Eliminates error-prone manual testing
- ✅ **Professional**: Production-grade testing framework

### Negative

- ❌ **Learning Curve**: Team must learn mcp_audit collection
- ❌ **Dependencies**: Requires Ansible + mcp_audit collection
- ❌ **Test Maintenance**: Playbooks need updates when tools change
- ❌ **Execution Time**: Full regression suite may take 5-10 minutes
- ❌ **LLM Costs**: OpenRouter tests incur API costs

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| mcp_audit collection updates break tests | Pin collection version in requirements.yml |
| LLM API costs too high | Use Ollama for most tests, OpenRouter only for critical flows |
| Tests too slow for rapid iteration | Provide quick smoke test playbook for fast feedback |
| False positives in test assertions | Use expected_result carefully, test edge cases |
| Test infrastructure different from production | Use identical transport (HTTP/SSE) in tests and prod |

## Alternatives Considered

### A: Continue with Manual Testing

**Pros**: No new dependencies, simple
**Cons**: Error-prone, not repeatable, no CI/CD integration
**Decision**: Rejected - manual testing doesn't scale

### B: Write Custom Python Test Scripts

**Pros**: Full control, no Ansible needed
**Cons**: Reinventing the wheel, no multi-transport support
**Decision**: Rejected - mcp_audit already provides this

### C: Use MCP Inspector for Testing

**Pros**: Official MCP tool, interactive
**Cons**: Not automatable, manual only, no CI/CD integration
**Decision**: Rejected - Inspector is for development, not CI/CD

### D: Use tosin2013.mcp_audit (Chosen)

**Pros**: Purpose-built for MCP testing, multi-transport, LLM integration, CI/CD ready
**Cons**: Additional dependency, learning curve
**Decision**: **Accepted** - best fit for automated MCP testing

## Future Enhancements

### 1. Performance Testing

```yaml
- name: Load test semantic search
  tosin2013.mcp_audit.mcp_performance_test:
    transport: sse
    server_url: "{{ mcp_server_url }}"
    tool_name: semantic_search_code
    concurrent_requests: 100
    duration_seconds: 60
    expected_p95_latency_ms: 500
```

### 2. Multi-Cloud Testing

```bash
# Test same playbook on all cloud providers
ansible-playbook test-cloud.yml -i inventory/gcp-prod.yml
ansible-playbook test-cloud.yml -i inventory/aws-prod.yml
ansible-playbook test-cloud.yml -i inventory/openshift-prod.yml
```

### 3. Chaos Engineering

```yaml
- name: Test resilience under network failures
  block:
    - name: Introduce network latency
      # Inject delays via chaos toolkit

    - name: Test MCP server under degraded conditions
      tosin2013.mcp_audit.mcp_test_tool:
        # Should still work, just slower
```

### 4. Security Testing

```yaml
- name: Test authentication enforcement
  tosin2013.mcp_audit.mcp_test_tool:
    transport: sse
    server_url: "{{ mcp_server_url }}"
    headers: {}  # No API key
    tool_name: semantic_search_code
    expect_failure: true
    expected_error: "Unauthorized"
```

## Related ADRs

- **ADR 0001**: MCP Transport Protocols (defines stdio/HTTP/SSE transports we test)
- **ADR 0009**: Ansible Deployment Automation (deployment that this testing validates)
- **ADR 0002**: Cloud Run HTTP Deployment (GCP cloud testing target)
- **ADR 0006**: AWS HTTP Deployment (future AWS testing target)
- **ADR 0007**: OpenShift HTTP Deployment (future OpenShift testing target)

## References

- **Collection**: https://galaxy.ansible.com/ui/repo/published/tosin2013/mcp_audit/
- **GitHub**: https://github.com/tosin2013/ansible-collection-mcp-audit
- **Documentation**: https://github.com/tosin2013/ansible-collection-mcp-audit/blob/main/README.md
- **Module Docs**: Collection includes full module documentation
- **MCP Protocol**: https://modelcontextprotocol.io/
- **LiteLLM**: https://docs.litellm.ai/ (LLM integration provider)

## Quick Start

```bash
# 1. Install collection
ansible-galaxy collection install tosin2013.mcp_audit

# 2. Test local server
cd tests/ansible
ansible-playbook test-local.yml -i inventory/local.yml

# 3. Test cloud deployment
export CLOUDRUN_SERVICE_URL="https://your-service.run.app"
export MCP_API_KEY="ci_your_api_key"
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml

# 4. Run full regression suite
ansible-playbook test-regression.yml -i inventory/gcp-staging.yml
```

---

**Status**: Accepted ✅
**Implementation**: Phase 1 complete, Phase 2-6 planned
**Last Updated**: November 2, 2025
**Maintained By**: Code Index MCP Team
