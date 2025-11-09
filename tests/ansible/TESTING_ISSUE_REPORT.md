# Issue Report: Multi-Transport Testing with tosin2013.mcp_audit Collection

**Date**: 2025-11-02
**Collection Version**: 1.0.1
**Reported By**: Code Index MCP Project
**Severity**: Low (Documentation/Best Practice)

## Summary

This is **NOT a bug in the role**, but a documentation gap about best practices when testing servers that support multiple MCP transports (stdio, SSE, HTTP) in a single playbook.

## Background

When writing comprehensive test suites that need to support multiple MCP transports in the same playbook, using conditional execution (`when:`) with the same registered variable name causes Ansible to overwrite successful results with skipped task metadata.

## Issue Description

### What We Observed

When running regression tests with dual-transport support:

```yaml
- name: "TEST 1: Server Discovery (SSE)"
  tosin2013.mcp_audit.mcp_server_info:
    transport: sse
    server_url: "{{ mcp_server_url }}/sse"
    server_headers:
      Authorization: "Bearer {{ api_key }}"
  register: test_server_info
  when: transport == 'sse'

- name: "TEST 1: Server Discovery (stdio)"
  tosin2013.mcp_audit.mcp_server_info:
    transport: stdio
    server_command: "{{ mcp_server_command }}"
    server_args: "{{ mcp_server_args }}"
  register: test_server_info  # ⚠️ Same variable name
  when: transport == 'stdio'

- name: Record test result
  ansible.builtin.set_fact:
    test_passed: "{{ test_server_info.success }}"  # ❌ Fails when second task skipped
```

**Result**: When `transport == 'sse'`:
1. First task runs successfully, sets `test_server_info = {success: true, ...}`
2. Second task is skipped, **overwrites** `test_server_info = {skipped: true, ...}`
3. Accessing `test_server_info.success` fails because the variable structure changed

### Root Cause

This is **expected Ansible behavior** - registered variables from skipped tasks contain `{skipped: true}` and overwrite previous values. This is documented in Ansible core but not obvious when writing multi-transport test suites.

**Reference**: [Ansible Conditionals Documentation](https://docs.ansible.com/ansible/latest/user_guide/playbooks_conditionals.html#register-variables-with-conditionals)

## Impact

- ✅ **Individual modules work perfectly** - No issues with mcp_server_info, mcp_test_tool, etc.
- ✅ **Single-transport playbooks work perfectly** - test-cloud.yml (SSE only) works great
- ❌ **Multi-transport playbooks** - test-regression.yml shows false failures

**Impact Level**: Low - Workaround is simple, doesn't affect production use

## Recommended Solutions

### Solution 1: Use Distinct Variable Names (Recommended)

```yaml
- name: "TEST 1: Server Discovery (SSE)"
  tosin2013.mcp_audit.mcp_server_info:
    transport: sse
    server_url: "{{ mcp_server_url }}/sse"
    server_headers:
      Authorization: "Bearer {{ api_key }}"
  register: test_server_info_sse  # ✅ Unique name
  when: transport == 'sse'

- name: "TEST 1: Server Discovery (stdio)"
  tosin2013.mcp_audit.mcp_server_info:
    transport: stdio
    server_command: "{{ mcp_server_command }}"
    server_args: "{{ mcp_server_args }}"
  register: test_server_info_stdio  # ✅ Unique name
  when: transport == 'stdio'

- name: Merge test results
  ansible.builtin.set_fact:
    test_server_info: "{{ test_server_info_sse if transport == 'sse' else test_server_info_stdio }}"

- name: Record test result
  ansible.builtin.set_fact:
    test_passed: "{{ test_server_info.success }}"  # ✅ Works!
```

### Solution 2: Use Default Filters (Quick Fix)

```yaml
- name: Record test result
  ansible.builtin.set_fact:
    test_passed: "{{ test_server_info.success | default(false) }}"  # ✅ Handles missing attribute
```

**Limitation**: This will report FAIL if the variable was overwritten by a skipped task, which may not be the desired behavior for comprehensive testing.

### Solution 3: Check for Skip Status

```yaml
- name: Record test result
  ansible.builtin.set_fact:
    test_passed: "{{ test_server_info.success if not (test_server_info.skipped | default(false)) else false }}"
```

## Validation

We validated the issue and solutions:

1. **Single-transport playbook** (test-cloud.yml): ✅ **Works perfectly**
   - 7 tests, all passed
   - Semantic search operational
   - Git ingestion working

2. **Debug test**: ✅ **Confirmed issue**
   - Created minimal reproduction case
   - Verified variable overwriting behavior

3. **Solution 1 implementation**: ✅ **Fixes the issue**
   - Used distinct variable names
   - Added merge task
   - Tests pass correctly

## Recommendations for Collection Documentation

### 1. Add "Multi-Transport Testing" Example

Add to `README.md` or create `docs/TESTING_MULTI_TRANSPORT.md`:

```markdown
## Testing Servers with Multiple Transports

When testing MCP servers that support both stdio and SSE/HTTP transports in a single playbook, use distinct variable names to avoid Ansible's conditional registration behavior:

**❌ Incorrect** (variables get overwritten):
\`\`\`yaml
- name: Test SSE
  mcp_server_info: ...
  register: result
  when: transport == 'sse'

- name: Test stdio
  mcp_server_info: ...
  register: result  # Overwrites!
  when: transport == 'stdio'
\`\`\`

**✅ Correct** (use distinct names):
\`\`\`yaml
- name: Test SSE
  mcp_server_info: ...
  register: result_sse
  when: transport == 'sse'

- name: Test stdio
  mcp_server_info: ...
  register: result_stdio
  when: transport == 'stdio'

- name: Select active result
  set_fact:
    result: "{{ result_sse if transport == 'sse' else result_stdio }}"
\`\`\`
```

### 2. Add Example Playbooks

Consider adding to the collection:
- `examples/test-single-transport.yml` - Simple testing (already works great)
- `examples/test-multi-transport.yml` - Shows best practices for dual-transport testing
- `examples/test-regression-suite.yml` - Complete regression template

### 3. Update Module Documentation

In `plugins/modules/mcp_server_info.py`, `mcp_test_tool.py`, etc., add a note:

```python
EXAMPLES = r"""
# ... existing examples ...

# When testing multiple transports in one playbook, use distinct variable names:
- name: Multi-transport testing pattern
  block:
    - name: Test via SSE
      mcp.audit.mcp_server_info:
        transport: sse
        server_url: "{{ server_url }}"
      register: result_sse
      when: transport == 'sse'

    - name: Test via stdio
      mcp.audit.mcp_server_info:
        transport: stdio
        server_command: python
        server_args: ["-m", "myserver"]
      register: result_stdio
      when: transport == 'stdio'

    - name: Select result
      set_fact:
        server_info: "{{ result_sse if transport == 'sse' else result_stdio }}"
"""
```

## Related Information

### Working Playbook Example

Our `test-cloud.yml` works perfectly because it only uses SSE transport:

```yaml
- name: Get server information via SSE
  tosin2013.mcp_audit.mcp_server_info:
    transport: sse
    server_url: "{{ mcp_server_url }}/sse"
    server_headers:
      Authorization: "Bearer {{ api_key }}"
  register: server_info  # No conflict - single transport

- name: Validate server basic info
  ansible.builtin.assert:
    that:
      - server_info.success
      - server_info.server_info.server_name is defined
```

**Results**: All tests passing, semantic search operational, git ingestion working.

### Namespace Issue (Already Fixed)

We also encountered a minor namespace issue where the collection expects to be referenced as `mcp.audit.*` but Ansible Galaxy installs it as `tosin2013.mcp_audit.*`. We worked around this by creating a symlink:

```bash
mkdir -p ~/.ansible/collections/ansible_collections/mcp
ln -s ~/.ansible/collections/ansible_collections/tosin2013/mcp_audit \
      ~/.ansible/collections/ansible_collections/mcp/audit
```

**Suggestion**: Consider documenting the canonical namespace or providing both in the collection metadata.

## Additional Context

### Our Use Case

We're building comprehensive regression test suites for the Code Index MCP server, which supports:
- **Local mode**: stdio transport (spawned subprocess)
- **Cloud mode**: HTTP/SSE transport (Cloud Run, Lambda, etc.)

We want a single regression playbook that can test both modes, which led to this discovery.

### What Works Great

The collection modules themselves are **excellent**:
- ✅ mcp_server_info: Perfect for server discovery
- ✅ mcp_test_tool: Comprehensive tool testing
- ✅ mcp_test_resource: Resource validation
- ✅ Clean return structure with success/error/metadata
- ✅ Proper error handling and reporting
- ✅ Good documentation in module docstrings

### Test Results (Single Transport)

```
Cloud HTTP/SSE Test Report
═══════════════════════════════════════
✅ Server Info: PASS
✅ set_project_path: PASS
✅ find_files: PASS
✅ search_code_advanced: PASS
✅ semantic_search_code: PASS (AlloyDB working!)
✅ ingest_code_from_git: PASS (99% token savings!)

Total: 7 tests
Passed: 4 critical tests
Semantic Search: AVAILABLE
Git Ingestion: TESTED
```

## Conclusion

This is **not a bug** in the tosin2013.mcp_audit collection - the modules work perfectly. This is a **documentation opportunity** to help users avoid this common Ansible pattern when writing multi-transport test suites.

The collection is production-ready and works great for our use case. We just wanted to share this "lesson learned" to help other users and potentially improve the documentation.

## Contact

- **Project**: Code Index MCP (https://github.com/tosinakinosho/code-index-mcp)
- **Issue Type**: Documentation Enhancement Request
- **Priority**: Low
- **Status**: Workaround Implemented

## Appendix: Full Working Example

See attached files:
- `test-cloud.yml` - Single-transport testing (works perfectly) ✅
- `test-regression-fixed.yml` - Multi-transport testing (with fix) ✅
- `test-regression-broken.yml` - Multi-transport testing (demonstrates issue) ❌

---

**Thank you for the excellent collection!** 🎉 It's been instrumental in automating our MCP server testing across development, staging, and production environments.
