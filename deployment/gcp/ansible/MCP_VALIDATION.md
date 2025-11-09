# MCP Server Validation

This Ansible role validates your deployed MCP server by calling its tools to test end-to-end functionality.

## What It Tests

1. **✅ SSE Endpoint** - Verifies the service is accessible via Server-Sent Events
2. **✅ MCP Tools** - Lists all available tools and verifies required tools exist
3. **✅ Git Ingestion** - Tests repository ingestion with AlloyDB storage
4. **✅ Semantic Search** - Tests vector embeddings and similarity search with Vertex AI

## Quick Start

### Option 1: Validate After Deployment

Run validation immediately after deploying:

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp/ansible

# Deploy with validation
ansible-playbook deploy.yml -i inventory/dev.yml -e "confirm_deployment=yes run_validation=true"
```

### Option 2: Standalone Validation

Validate an existing deployment:

```bash
cd /Users/tosinakinosho/workspaces/code-index-mcp/deployment/gcp/ansible

# Full validation
ansible-playbook validate.yml -i inventory/dev.yml

# Or specify service URL directly
ansible-playbook validate.yml -i inventory/dev.yml \
  -e "mcp_service_url=https://code-index-mcp-dev-920209401641.us-east1.run.app"
```

## Test Options

### Skip Ingestion Test

Ingestion takes ~2-5 minutes. Skip it for quick validation:

```bash
ansible-playbook validate.yml -i inventory/dev.yml \
  -e "run_ingestion_test=false"
```

### Skip All Long Tests

Test only basic connectivity:

```bash
ansible-playbook validate.yml -i inventory/dev.yml \
  -e "run_ingestion_test=false run_search_test=false"
```

### Custom Test Repository

Test with your own repository:

```bash
ansible-playbook validate.yml -i inventory/dev.yml \
  -e "test_repo_url=https://github.com/username/my-repo"
```

### Custom Search Query

Test search with specific query:

```bash
ansible-playbook validate.yml -i inventory/dev.yml \
  -e "test_search_query='authentication middleware'"
```

## Configuration

### Inventory Variables

Add to `inventory/dev.yml`:

```yaml
# MCP Server URL (set by deployment or manually)
cloudrun_service_url: "https://code-index-mcp-dev-920209401641.us-east1.run.app"

# Validation options
run_validation: false  # Enable post-deployment validation
run_ingestion_test: true
run_search_test: true
test_repo_url: "https://github.com/octocat/Hello-World"
test_search_query: "hello world function"
embedding_wait_time: 30  # seconds
write_validation_report: true
```

### Role Defaults

See `roles/mcp-validation/defaults/main.yml` for all options.

## Validation Output

### Console Output

```
===================================
MCP Server Validation
===================================
Service URL: https://code-index-mcp-dev-920209401641.us-east1.run.app
Test Repository: https://github.com/octocat/Hello-World
===================================

✅ MCP server is responding on SSE endpoint

Available MCP Tools:
- ingest_git_repository
- semantic_search
- list_projects
- search_code
- search_code_advanced
...

✅ All required tools are available
✅ Git repository ingestion successful
✅ Semantic search successful

===================================
✅ MCP Server Validation Complete
===================================
```

### Validation Report

A markdown report is generated:

```
./mcp-validation-report-1761831234.md
```

Contains:
- Test results table
- Available tools list
- Detailed JSON responses

## Expected Durations

| Test | Duration |
|------|----------|
| SSE Endpoint | 1-3 seconds |
| Tools List | 2-5 seconds |
| Git Ingestion | 2-5 minutes |
| Embedding Wait | 30 seconds |
| Semantic Search | 5-10 seconds |

**Total**: ~3-6 minutes for full validation

## Troubleshooting

### Service Not Responding

```
FAILED! => {"msg": "Status code was 404 and not [200]"}
```

**Fix**: Check service URL and ensure Cloud Run service is deployed.

### Tools Not Available

```
FAILED! => {"msg": "Required tools not available"}
```

**Fix**: Ensure Docker image was built with latest code and redeployed.

### Ingestion Failed

```
FAILED! => {"msg": "Ingestion test failed"}
```

**Possible causes**:
1. AlloyDB connection issue - check VPC connector
2. Vertex AI API not enabled
3. Service account missing permissions
4. Repository URL invalid or inaccessible

**Debug**:
```bash
# Check Cloud Run logs
gcloud run services logs read code-index-mcp-dev --region=us-east1 --limit=50

# Check AlloyDB connection
gcloud alloydb instances list --region=us-east1

# Verify service account roles
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:code-index-mcp-dev@"
```

### Search Returned No Results

```
FAILED! => {"msg": "Search test failed"}
```

**Possible causes**:
1. Embeddings not yet generated (increase `embedding_wait_time`)
2. Ingestion didn't complete successfully
3. AlloyDB pgvector extension not installed

**Fix**:
```bash
# Wait longer for embeddings
ansible-playbook validate.yml -i inventory/dev.yml \
  -e "embedding_wait_time=60"
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Deploy to Cloud Run
  run: |
    cd deployment/gcp/ansible
    ansible-playbook deploy.yml -i inventory/prod.yml \
      -e "confirm_deployment=yes run_validation=true"

- name: Check validation report
  if: always()
  run: |
    cat deployment/gcp/ansible/mcp-validation-report-*.md
```

### Post-Deployment Hook

Add to `deploy.yml` post_tasks:

```yaml
- name: Always run validation
  ansible.builtin.include_role:
    name: mcp-validation
  vars:
    mcp_service_url: "{{ cloudrun_service_url }}"
    run_ingestion_test: true
    run_search_test: true
```

## API Details

The validation role makes JSON-RPC 2.0 calls to the MCP server:

### List Tools

```json
{
  "jsonrpc": "2.0",
  "id": "list-tools-123",
  "method": "tools/list"
}
```

### Call Tool (Ingestion)

```json
{
  "jsonrpc": "2.0",
  "id": "ingest-test-123",
  "method": "tools/call",
  "params": {
    "name": "ingest_git_repository",
    "arguments": {
      "repository_url": "https://github.com/octocat/Hello-World",
      "project_name": "validation-test-123"
    }
  }
}
```

### Call Tool (Search)

```json
{
  "jsonrpc": "2.0",
  "id": "search-test-123",
  "method": "tools/call",
  "params": {
    "name": "semantic_search",
    "arguments": {
      "query": "hello world function",
      "project_name": "validation-test-123",
      "top_k": 5
    }
  }
}
```

## Cost Considerations

Each validation run:
- **Git Ingestion**: ~$0.01 (AlloyDB storage, Vertex AI embeddings)
- **Semantic Search**: ~$0.001 (Vertex AI query)
- **Total**: ~$0.01-0.02 per full validation

**Recommendation**: Run full validation only on deployment or significant changes.

## Security

### Authentication

If your MCP server requires authentication:

```yaml
# Add to inventory
mcp_auth_token: "{{ lookup('env', 'MCP_AUTH_TOKEN') }}"
```

Update validation role to include:

```yaml
- name: Call authenticated endpoint
  ansible.builtin.uri:
    headers:
      Authorization: "Bearer {{ mcp_auth_token }}"
```

## Next Steps

After validation passes:

1. **Add to Claude Desktop** - Use the service URL in your Claude config
2. **Test manually** - Try semantic search in Claude
3. **Monitor costs** - Check GCP billing dashboard
4. **Set up alerts** - Configure Cloud Monitoring for errors

## Related Documentation

- [Ansible Deployment Guide](./README.md)
- [Cloud Run Deployment](../../DEPLOYMENT.md)
- [MCP Protocol Spec](https://modelcontextprotocol.io/)
- [Troubleshooting Guide](../../../docs/TROUBLESHOOTING_GUIDE.md)







