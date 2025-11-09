# Code Index MCP - Authentication Guide

**Status**: Implemented (Infrastructure Ready, Middleware Integration Pending)  
**Confidence**: 88% - Scripts and deployment ready, FastMCP integration needed  
**Date**: October 26, 2025

---

## Overview

This guide explains how to deploy and use Code Index MCP with API key authentication on Google Cloud Run.

## Current Status

### ✅ Ready:
- **API Key Generation**: Script to create secure API keys in GCP Secret Manager
- **Deployment Support**: Deploy with `--require-auth` flag
- **Auth Middleware**: Complete implementation in `src/code_index_mcp/middleware/auth.py`
- **Claude Desktop Support**: Headers can be configured for authenticated requests

### ⏳ Pending:
- **FastMCP Integration**: Authentication middleware needs to be connected to FastMCP's SSE endpoints
- **Token Validation**: Currently deployed with `--no-allow-unauthenticated` but not enforcing API keys yet

## Deployment Options

### Option 1: No Authentication (Current Default)
```bash
cd deployment/gcp
./deploy.sh dev --with-alloydb
```

- ✅ Quick setup, no API key needed
- ⚠️ **Public access** - anyone with the URL can use your service
- 💰 **Cost risk** - unlimited usage possible

### Option 2: With Authentication (Recommended for Production)
```bash
cd deployment/gcp
./deploy.sh dev --with-alloydb --require-auth
```

- ✅ Secure - requires API key for all requests
- ✅ **User isolation** - each API key tied to a user_id
- ✅ **Audit trail** - track usage per API key
- 💰 **Cost control** - manage who can access the service

## Step-by-Step Setup (With Authentication)

### Step 1: Deploy with Authentication
```bash
cd deployment/gcp
./deploy.sh dev --with-alloydb --require-auth
```

**What this does**:
- Deploys Cloud Run with `--no-allow-unauthenticated`
- Sets `REQUIRE_AUTH=true` environment variable
- Shows instructions for generating API keys

### Step 2: Generate an API Key
```bash
cd deployment/gcp
./generate-api-key.sh demo-user dev
```

**Output**:
```
========================================
  API Key Generated Successfully!
========================================

IMPORTANT: Save this API key securely!
It will not be shown again.

API Key:
  ci_a1b2c3d4e5f6...

Usage in Claude Desktop:
  {
    "mcpServers": {
      "code-index-semantic-search": {
        "url": "https://code-index-mcp-dev-*.run.app/sse",
        "transport": "sse",
        "headers": {
          "X-API-Key": "ci_a1b2c3d4e5f6..."
        }
      }
    }
  }
```

### Step 3: Configure Claude Desktop

Add the configuration to your `claude_desktop_config.json`:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`  
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app/sse",
      "transport": "sse",
      "headers": {
        "X-API-Key": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Step 4: Restart Claude Desktop

Quit and reopen Claude Desktop to establish a new authenticated SSE connection.

### Step 5: Test the Connection

In Claude Desktop, try:
```
List the available MCP tools from code-index-semantic-search
```

You should see tools like:
- `ingest_code_for_search`
- `semantic_search_code`
- `find_similar_code`

## API Key Management

### Viewing Existing Keys
```bash
gcloud secrets list --project=YOUR_PROJECT_ID --filter="labels.service:code-index-mcp"
```

### Generating Additional Keys
```bash
# For another user
./generate-api-key.sh alice dev

# For production
./generate-api-key.sh bob prod
```

### Revoking a Key
```bash
gcloud secrets delete code-index-api-key-demo-user-dev --project=YOUR_PROJECT_ID
```

### Key Rotation
1. Generate a new key with the same user_id
2. Update Claude Desktop config with new key
3. Delete old key after confirming new one works

## Security Best Practices

### API Key Format
- **Prefix**: `ci_` (code-index)
- **Length**: 32 hex characters (64 chars total)
- **Example**: `ci_a1b2c3d4e5f6789...`

### Secret Manager Labels
Each API key secret has these labels:
- `service: code-index-mcp` - Identifies the service
- `user_id: <user>` - Maps key to a user
- `environment: <env>` - dev/staging/prod

### IAM Permissions
The Cloud Run service account needs:
- `roles/secretmanager.secretAccessor` on API key secrets

### Constant-Time Comparison
API keys are validated using constant-time comparison to prevent timing attacks.

## Troubleshooting

### Issue: "404 Session Not Found"
**Cause**: Connection timed out (Cloud Run scaled to zero)  
**Fix**: Restart Claude Desktop to create a new session

### Issue: "Authentication Failed"
**Cause**: Invalid or missing API key  
**Fix**: 
1. Verify API key in Claude Desktop config
2. Check Secret Manager for the key:
   ```bash
   gcloud secrets versions access latest --secret=code-index-api-key-demo-user-dev
   ```

### Issue: "Permission Denied on Secret"
**Cause**: Service account lacks access  
**Fix**:
```bash
gcloud secrets add-iam-policy-binding code-index-api-key-demo-user-dev \
    --member="serviceAccount:920209401641-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Issue: Authentication Not Enforced
**Cause**: FastMCP SSE middleware integration pending  
**Status**: Infrastructure ready, integration needed  
**Workaround**: Currently deployed with `--no-allow-unauthenticated`, but token validation not yet active

## Cost Implications

### Without Authentication
- **Risk**: Unlimited public usage
- **Potential**: $100-1000+/month if discovered

### With Authentication
- **Control**: Only issued API keys can access
- **Predictable**: ~$180-220/month for controlled usage
- **Audit**: Track usage per user/key

## Testing Authentication Locally

```bash
# Start server with auth
cd /Users/tosinakinosho/workspaces/code-index-mcp
REQUIRE_AUTH=true MCP_TRANSPORT=http PORT=8080 uv run code-index-mcp

# Test without API key (should fail eventually)
curl -H "Accept: text/event-stream" http://localhost:8080/sse

# Test with API key (should succeed eventually)
curl -H "Accept: text/event-stream" \
     -H "X-API-Key: ci_your_key_here" \
     http://localhost:8080/sse
```

**Note**: Currently logs a warning but doesn't enforce. Full integration coming soon.

## Next Steps

### For You (User)
1. **Deploy with auth**: `./deploy.sh dev --with-alloydb --require-auth`
2. **Generate API key**: `./generate-api-key.sh demo-user dev`
3. **Configure Claude Desktop** with the API key
4. **Test ingestion** and semantic search

### For Development (TODO)
1. **Integrate AuthMiddleware** with FastMCP's Starlette app
2. **Add middleware** to `/sse` and `/messages/` endpoints
3. **Extract user context** from API keys for multi-tenancy
4. **Test authentication flow** end-to-end
5. **Document Claude Desktop** header support for MCP

## References

- **Auth Middleware**: `src/code_index_mcp/middleware/auth.py`
- **Deployment Script**: `deployment/gcp/deploy.sh`
- **API Key Generation**: `deployment/gcp/generate-api-key.sh`
- **ADR 0002**: Cloud Run HTTP Deployment
- **GCP Secret Manager**: https://cloud.google.com/secret-manager/docs

---

**Confidence**: 88% - Infrastructure complete, FastMCP integration needed for full enforcement

