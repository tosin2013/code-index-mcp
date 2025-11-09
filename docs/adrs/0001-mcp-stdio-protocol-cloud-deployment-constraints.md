# ADR 0001: MCP Transport Protocols and Cloud Deployment Architecture

**Status**: Accepted (Updated)
**Date**: 2025-10-24 (Revised from stdio-only assumption)
**Decision Maker**: Architecture Team

## Context

The Model Context Protocol (MCP) supports **two transport mechanisms**:

### 1. Stdio Transport (Original)
**For local execution:**
1. **Client spawns MCP server** as a subprocess
2. **Communication via stdin/stdout** using JSON-RPC
3. **Server runs in client's execution context** (same machine, same network, same filesystem)

**Perfect for:**
- ✅ Desktop applications (Claude Desktop, VS Code, IDEs)
- ✅ Local development tools
- ✅ Command-line utilities

### 2. HTTP/SSE Transport (Cloud-Native)
**For remote execution:**
1. **Client connects to HTTP endpoint**
2. **Server-Sent Events (SSE)** for server-to-client streaming
3. **HTTP POST** for client-to-server requests
4. **Stateful connection** maintained via SSE stream

**Perfect for:**
- ✅ Cloud Run, AWS Lambda, Azure Functions
- ✅ Kubernetes/OpenShift deployments
- ✅ Multi-user shared servers
- ✅ Auto-scaling serverless platforms

## Discovery: HTTP Transport Enables True Cloud Deployment

After reviewing the [Cloud Run MCP deployment guide](https://codelabs.developers.google.com/codelabs/cloud-run/how-to-deploy-a-secure-mcp-server-on-cloud-run), we now understand that:

## How HTTP/SSE Transport Works

```
┌─────────────┐                           ┌──────────────────┐
│   Claude    │   HTTP POST /message      │  Cloud Run       │
│   Desktop   │──────────────────────────►│  MCP Server      │
│             │                           │  (HTTP Endpoint) │
│             │◄──────────────────────────│                  │
│             │   SSE Stream (responses)  │                  │
└─────────────┘                           └──────────────────┘
```

**Key Features:**
- Standard HTTP endpoint (no stdin/stdout needed)
- SSE provides server-to-client streaming
- Compatible with load balancers, API gateways
- Supports auto-scaling and serverless platforms
- Can handle multiple concurrent clients

### Challenges Solved for code-index-mcp

✅ **Filesystem Access** (Solved - See ADR 0008)
   - **Solution**: Git-Sync ingestion - clone repos directly to cloud
   - **Benefits**: 99% token savings, 95% faster updates, auto-sync via webhooks
   - **Implementation**: `ingest_code_from_git` MCP tool

✅ **State Management** (Solved - See ADR 0002)
   - **Solution**: Store indexes in cloud storage (GCS, S3)
   - **Implementation**: `GCSAdapter` with user namespace isolation

✅ **Multi-tenancy** (Solved - See ADR 0002)
   - **Solution**: API key authentication + per-user namespaces
   - **Implementation**: Auth middleware with Secret Manager integration

✅ **Resource Management** (Solved - See ADR 0002)
   - **Solution**: TTL-based cleanup via Cloud Scheduler
   - **Implementation**: Automated cleanup jobs and lifecycle rules

## Decision

**We will support BOTH deployment modes**, each optimized for different use cases:

### Mode 1: Stdio Transport (Local Execution - Current Implementation)
**For individual developers working locally**

```python
# Current server.py already uses stdio via FastMCP
mcp = FastMCP("CodeIndexer", lifespan=indexer_lifespan)
# Runs via: uvx code-index-mcp
```

**Pros:**
- ✅ Zero deployment complexity
- ✅ Direct filesystem access
- ✅ No networking or authentication complexity
- ✅ Perfect for local development

**Cons:**
- ❌ Requires Python 3.10+ on user machine
- ❌ No sharing across teams

### Mode 2: HTTP/SSE Transport (Cloud Deployment - NEW)
**For teams, shared infrastructure, enterprise**

```python
# New: HTTP transport mode
if os.getenv("MCP_TRANSPORT") == "http":
    # Use FastMCP with HTTP transport
    mcp = FastMCP(
        "CodeIndexer",
        transport="sse",  # Server-Sent Events
        port=int(os.getenv("PORT", 8080))
    )
else:
    # Default: stdio transport
    mcp = FastMCP("CodeIndexer", lifespan=indexer_lifespan)
```

**Pros:**
- ✅ Deploy to Cloud Run, Lambda, Kubernetes
- ✅ Auto-scaling, load balancing
- ✅ Multi-user support with authentication
- ✅ No client-side dependencies

**Cons:**
- ❌ Requires code upload or git integration
- ❌ More complex deployment and security
- ❌ Cloud costs (though can auto-scale to zero)

## Consequences

### Positive
- ✅ Best of both worlds: local AND cloud deployment
- ✅ Users choose based on their needs (local dev vs team sharing)
- ✅ HTTP transport enables true serverless deployment
- ✅ Auto-scaling reduces costs when idle
- ✅ Existing stdio users unaffected (backward compatible)

### Negative
- ❌ More complex codebase (two transport modes)
- ❌ HTTP mode requires code upload/sync mechanism
- ❌ Authentication and multi-tenancy needed for HTTP
- ❌ Cloud deployments incur costs

### Neutral
- Deployment scripts handle infrastructure provisioning
- MCP server code remains transport-agnostic
- Can start with stdio, migrate to HTTP later

## Implementation Plan

### Phase 1: Add HTTP Transport Support (Week 1)
```python
# Update server.py
def create_mcp_server():
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        return FastMCP(
            "CodeIndexer",
            transport="sse",
            port=int(os.getenv("PORT", 8080)),
            lifespan=indexer_lifespan
        )
    else:
        return FastMCP("CodeIndexer", lifespan=indexer_lifespan)

mcp = create_mcp_server()
```

### Phase 2: Code Upload/Git Integration (Week 2)
- Add tool: `upload_code_archive()`
- Add tool: `sync_from_git()`
- Store in `/tmp/{user_id}/{project_id}/`

### Phase 3: Cloud Deployment Scripts (Week 3)
- Cloud Run deploy script with auto-cleanup
- AWS Lambda/ECS deploy script
- OpenShift Helm charts

### Phase 4: Authentication & Multi-tenancy (Week 4)
- API key authentication
- Per-user project isolation
- Resource quotas and limits

## Deployment Script Requirements

All deployment scripts must include:

1. **Automatic Resource Cleanup**
   - Cloud Scheduler job to delete idle instances
   - TTL-based project data deletion
   - Budget alerts and cost monitoring

2. **Security**
   - No hardcoded credentials in git
   - Environment variable injection
   - Secrets management (Secret Manager, AWS Secrets)

3. **Multi-Project Support**
   - Per-user namespaces: `/projects/{user_id}/{project_name}/`
   - Isolated indexes and caches
   - Configurable storage quotas

## Related Decisions
- ADR 0002: Cloud Run HTTP Deployment with Auto-Cleanup (100% Complete)
- ADR 0003: Google Cloud Semantic Search with AlloyDB (83% Complete)
- ADR 0008: Git-Sync Ingestion Strategy (100% Complete)
- ADR 0004: AWS Code Ingestion Strategy (Planned)
- ADR 0005: OpenShift Code Ingestion Strategy (Planned)
- ADR 0006: AWS HTTP Deployment (Planned)
- ADR 0007: OpenShift HTTP Deployment (Planned)

## References
- [MCP Specification](https://modelcontextprotocol.io)
- [Cloud Run MCP Deployment Guide](https://codelabs.developers.google.com/codelabs/cloud-run/how-to-deploy-a-secure-mcp-server-on-cloud-run)
- [FastMCP HTTP Transport](https://github.com/jlowin/fastmcp)
- code-index-mcp/src/code_index_mcp/server.py:89
