# ADR 0002: Cloud Run HTTP Deployment with Automatic Resource Cleanup

**Status**: Accepted (100% Complete - Phase 2A)
**Date**: 2025-10-24 (Original), Updated 2025-10-29
**Decision Maker**: Architecture Team
**Supersedes**: Previous SSH-based deployment approach
**Related to**: ADR 0001 (HTTP/SSE Transport), ADR 0003 (Semantic Search), ADR 0008 (Git-Sync)

## Context

With MCP's HTTP/SSE transport support, we can deploy code-index-mcp as a standard cloud service. This ADR addresses the specific questions raised:

### User Requirements

1. **"How can users use this in their project if deployed in Cloud Run?"**
   - Users connect to HTTPS endpoint from Claude Desktop
   - Upload code via API or sync from git repositories

2. **"Will it be secure?"**
   - HTTPS encryption, API key authentication
   - IAM-based access control
   - See security section below

3. **"How does multi-project support work?"**
   - Per-user project namespaces
   - Isolated storage and indexes
   - See multi-project section below

4. **"How to delete Cloud Run services? Automation?"**
   - Automated cleanup via Cloud Scheduler
   - Resource TTLs and idle detection
   - See cleanup section below

5. **"How to protect gcloud credentials in git?"**
   - Never commit credentials
   - Use Secret Manager + IAM
   - See security section below

## Decision: Cloud Run with HTTP Transport

Deploy code-index-mcp to Cloud Run using HTTP/SSE transport with automatic resource management.

## Architecture

### Deployment Model

```
┌─────────────┐                           ┌──────────────────┐
│   Claude    │   HTTPS (authenticated)   │  Cloud Run       │
│   Desktop   │──────────────────────────►│  Service         │
│             │                           │  (Auto-scaling)  │
│             │◄──────────────────────────│                  │
│             │   SSE Stream              └────────┬─────────┘
└─────────────┘                                    │
                                                   │
                                          ┌────────▼─────────┐
                                          │  Cloud Storage   │
                                          │  - User code     │
                                          │  - Indexes       │
                                          │  - Cache         │
                                          └──────────────────┘
```

### Components

1. **Cloud Run Service**
   - HTTP endpoint on port 8080
   - MCP_TRANSPORT=http environment variable
   - Min instances: 0 (scale to zero when idle)
   - Max instances: 10 (configurable)
   - Memory: 2GB, CPU: 2
   - Timeout: 3600s (for long-running operations)

2. **Cloud Storage Buckets**
   - `{project}-code-storage`: User-uploaded code
   - `{project}-indexes`: Generated indexes and caches
   - Lifecycle rules: Delete after 30 days of inactivity

3. **Cloud Scheduler** (Cleanup Automation)
   - Daily job: Delete inactive projects
   - Weekly job: Cleanup old indexes
   - Monthly job: Cost analysis and reporting

4. **Secret Manager**
   - API keys for user authentication
   - Git credentials (if syncing from private repos)
   - No secrets in code or environment variables

## Security Architecture

### Authentication Flow

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ 1. Request with API key
       ▼
┌──────────────┐
│  Cloud Run   │
│  (IAP +      │
│   API Auth)  │
└──────┬───────┘
       │ 2. Validate API key
       │    (Secret Manager)
       ▼
┌──────────────┐
│  MCP Server  │
│  Process     │
└──────────────┘
```

### Credential Management

**CRITICAL: Never commit credentials to git!**

```bash
# .gitignore (already exists, update if needed)
*.key
*.pem
*.p12
.env
.env.*
gcloud-*.json
service-account-*.json
secrets/
deployment/*.key
```

**Proper Approach:**

1. **API Keys**: Store in Secret Manager
   ```bash
   # Create secret
   echo -n "sk-abc123..." | gcloud secrets create mcp-api-key \
     --data-file=-

   # Grant Cloud Run access
   gcloud secrets add-iam-policy-binding mcp-api-key \
     --member="serviceAccount:PROJECT_ID@appspot.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

2. **Service Account**: Use Workload Identity, not keys
   ```bash
   # Cloud Run uses default compute service account
   # No need to download/commit JSON keys
   ```

3. **User Authentication**: Generate API keys via admin tool
   ```bash
   # Script to generate user API keys
   python scripts/generate_api_key.py --user=alice@company.com
   # Stores in Secret Manager, returns key to admin only
   ```

### Network Security

```yaml
# Cloud Run service configuration
ingress: all  # or internal-and-cloud-load-balancing
authentication: required  # Requires valid API key
encryption: TLS-only
```

## Multi-Project Isolation

### Storage Structure

```
gs://{project}-code-storage/
├── users/
│   ├── user_abc123/
│   │   ├── project_1/
│   │   │   ├── src/
│   │   │   └── .metadata
│   │   └── project_2/
│   │       ├── src/
│   │       └── .metadata
│   └── user_xyz789/
│       └── project_1/
│           └── ...

gs://{project}-indexes/
├── user_abc123/
│   ├── project_1/
│   │   ├── shallow_index.json
│   │   ├── deep_index.msgpack
│   │   └── embeddings/
│   └── project_2/
│       └── ...
```

### Namespace Isolation

```python
# In server.py
@mcp.tool()
def set_project_path(path: str, ctx: Context) -> str:
    user_id = ctx.request_context.user_id  # From auth middleware

    # Enforce namespace
    safe_path = f"/projects/{user_id}/{sanitize_path(path)}"

    # Mount from GCS
    mount_gcs_bucket(
        bucket=f"{GCP_PROJECT}-code-storage",
        prefix=f"users/{user_id}/",
        mount_point=f"/projects/{user_id}/"
    )

    return ProjectManagementService(ctx).initialize_project(safe_path)
```

### Resource Quotas

```python
# Per-user limits
USER_QUOTAS = {
    "max_projects": 10,
    "max_storage_gb": 50,
    "max_index_size_gb": 10,
    "max_concurrent_requests": 5
}
```

## Automatic Resource Cleanup

### Challenge: Preventing Resource Accumulation

Without cleanup, projects can accumulate indefinitely:
- Idle projects consume storage costs
- Abandoned Cloud Run instances waste resources
- Old indexes never get deleted

### Solution: Multi-Layer Cleanup Strategy

#### Layer 1: Cloud Storage Lifecycle Rules

```bash
# Set lifecycle on buckets
gsutil lifecycle set lifecycle.json gs://${PROJECT}-code-storage

# lifecycle.json
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 90,  # 90 days
          "matchesPrefix": ["users/"]
        }
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {
          "age": 30,  # Move to cold storage after 30 days
          "matchesStorageClass": ["STANDARD"]
        }
      }
    ]
  }
}
```

#### Layer 2: Cloud Scheduler Cleanup Jobs

```bash
# Create daily cleanup job
gcloud scheduler jobs create http cleanup-idle-projects \
  --schedule="0 2 * * *" \
  --uri="https://code-index-mcp-HASH.run.app/admin/cleanup" \
  --http-method=POST \
  --headers="Authorization=Bearer $(gcloud auth print-identity-token)" \
  --message-body='{"action":"cleanup_idle","days":30}'
```

```python
# In server.py - Admin endpoint
@mcp.tool()
def cleanup_idle_projects(days: int = 30) -> Dict[str, Any]:
    """
    Delete projects with no activity for N days.
    Called by Cloud Scheduler.
    """
    from google.cloud import storage
    from datetime import datetime, timedelta

    client = storage.Client()
    bucket = client.bucket(f"{GCP_PROJECT}-code-storage")

    cutoff = datetime.now() - timedelta(days=days)
    deleted = []

    for blob in bucket.list_blobs(prefix="users/"):
        if blob.updated < cutoff:
            blob.delete()
            deleted.append(blob.name)

    return {
        "deleted_count": len(deleted),
        "cutoff_date": cutoff.isoformat()
    }
```

#### Layer 3: Cloud Run Auto-Scale to Zero

```yaml
# In Cloud Run service spec
apiVersion: serving.knoxville.dev/v1
kind: Service
metadata:
  name: code-index-mcp
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"  # Scale to zero when idle
        autoscaling.knative.dev/maxScale: "10"
    spec:
      containerConcurrency: 10
      timeoutSeconds: 3600
```

**How it works:**
- No traffic → Cloud Run scales to 0 instances → No compute costs
- First request → Cold start (~5-10s) → Instance spun up
- Ongoing traffic → Keeps instances warm
- 15 minutes idle → Scales back to 0

#### Layer 4: Cost Alerts and Budgets

```bash
# Create budget alert
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="MCP Server Monthly Budget" \
  --budget-amount=100USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --threshold-rule=percent=100
```

### Cleanup Dashboard (Admin Tool)

```python
# scripts/cleanup_dashboard.py
import streamlit as st
from google.cloud import storage, monitoring_v3

# Show:
# - Active projects and last access time
# - Storage usage per user
# - Idle projects (candidates for deletion)
# - Cost breakdown
# - Manual cleanup controls
```

## Deployment Process

### Prerequisites

```bash
# Required tools
gcloud --version  # Google Cloud SDK
docker --version  # For local testing

# Required permissions
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable run.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  scheduler.googleapis.com
```

### Deployment Script

```bash
#!/bin/bash
# deployment/gcp/deploy.sh

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?GCP_PROJECT_ID environment variable required}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="code-index-mcp"

# 1. Create storage buckets
gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${PROJECT_ID}-code-storage" || true
gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${PROJECT_ID}-indexes" || true

# 2. Set lifecycle policies
gsutil lifecycle set deployment/gcp/lifecycle.json "gs://${PROJECT_ID}-code-storage"

# 3. Build and deploy
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "MCP_TRANSPORT=http,GCP_PROJECT=$PROJECT_ID" \
  --min-instances 0 \
  --max-instances 10 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600

# 4. Create cleanup scheduler job
gcloud scheduler jobs create http "${SERVICE_NAME}-cleanup" \
  --schedule="0 2 * * *" \
  --uri="https://$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')/admin/cleanup" \
  --http-method=POST \
  --oidc-service-account-email="$PROJECT_ID@appspot.gserviceaccount.com"

echo "✅ Deployment complete!"
echo "Service URL: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')"
```

### Teardown Script

```bash
#!/bin/bash
# deployment/gcp/destroy.sh

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?GCP_PROJECT_ID required}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="code-index-mcp"

# 1. Delete Cloud Run service
gcloud run services delete "$SERVICE_NAME" --region="$REGION" --quiet

# 2. Delete scheduler jobs
gcloud scheduler jobs delete "${SERVICE_NAME}-cleanup" --quiet || true

# 3. Delete storage buckets (optional, data will be lost!)
read -p "Delete all storage buckets? (yes/no): " confirm
if [ "$confirm" = "yes" ]; then
  gsutil -m rm -r "gs://${PROJECT_ID}-code-storage"
  gsutil -m rm -r "gs://${PROJECT_ID}-indexes"
fi

echo "✅ Resources deleted"
```

## Cost Estimation

### Cloud Run Costs (Scale-to-Zero)

| Usage Pattern | Monthly Cost |
|---------------|--------------|
| Idle (0 requests) | $0 |
| Light (1k requests, avg 5s) | ~$2 |
| Medium (100k requests, avg 5s) | ~$50 |
| Heavy (1M requests, avg 5s) | ~$400 |

### Storage Costs

| Resource | Size | Monthly Cost |
|----------|------|--------------|
| Code storage (10 users, 1GB each) | 10 GB | $0.20 |
| Indexes (10 users, 500MB each) | 5 GB | $0.10 |
| **Total** | **15 GB** | **$0.30** |

### Total Monthly Cost (Typical Team)

- Cloud Run (light usage): $2
- Storage: $0.30
- Egress: $0.50
- **Total: ~$3/month**

With aggressive scale-to-zero and cleanup, costs can be near-zero for inactive periods.

## Multi-Project Workflow

### User Perspective

1. **Connect to Cloud Run endpoint**
   ```json
   // Claude Desktop config
   {
     "mcpServers": {
       "code-index": {
         "url": "https://code-index-mcp-xyz.run.app",
         "headers": {
           "Authorization": "Bearer YOUR_API_KEY"
         }
       }
     }
   }
   ```

2. **Upload or sync code**
   ```
   User: "Upload my project from /local/path/to/project"
   MCP: Uploads to gs://project-code-storage/users/{user_id}/project_1/
   ```

3. **Index and search**
   ```
   User: "Set project path to project_1"
   MCP: Mounts GCS, builds index
   User: "Search for authentication code"
   MCP: Returns results from indexed project
   ```

4. **Switch projects**
   ```
   User: "Set project path to project_2"
   MCP: Unmounts project_1, mounts project_2
   ```

## Consequences

### Positive
- ✅ True serverless deployment (scales to zero)
- ✅ Automatic resource cleanup (no manual intervention)
- ✅ Multi-user support with isolation
- ✅ No SSH complexity
- ✅ Pay-per-use pricing model
- ✅ Integrated with GCP IAM and security

### Negative
- ❌ Cold start latency (5-10s after idle)
- ❌ Requires code upload (can't access local filesystem)
- ❌ More complex than local stdio execution
- ❌ Monthly costs (though minimal with auto-cleanup)

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Cost runaway | Budget alerts, auto-cleanup, scale-to-zero |
| Data loss | Lifecycle rules warn before deletion, backups |
| Security breach | API key auth, IAM, Secret Manager |
| Cold starts | Keep 1 min instance warm for paid plans |

## Implementation Status

### ✅ Phase 2A: Complete (100%)

**HTTP Transport Support**
- ✅ Implemented in `src/code_index_mcp/server.py`
- ✅ Environment variable: `MCP_TRANSPORT=http`
- ✅ FastMCP SSE transport integration
- ✅ Port configuration via `PORT` environment variable

**GCS Storage Integration**
- ✅ Implemented in `src/code_index_mcp/storage/gcs_adapter.py`
- ✅ Storage abstraction layer (`BaseStorageAdapter`)
- ✅ User namespace isolation: `users/{user_id}/{project_name}/`
- ✅ Async I/O for scalability

**API Key Authentication**
- ✅ Implemented in `src/code_index_mcp/middleware/auth.py`
- ✅ Google Secret Manager integration
- ✅ User context extraction
- ✅ Storage prefix generation

**Deployment Infrastructure**
- ✅ Deployment script: `deployment/gcp/deploy.sh`
- ✅ Teardown script: `deployment/gcp/destroy.sh`
- ✅ Dockerfile with all dependencies
- ✅ Cloud Scheduler jobs for cleanup
- ✅ Lifecycle rules configuration

**Documentation**
- ✅ User onboarding guide: `docs/USER_ONBOARDING_GUIDE.md`
- ✅ Deployment guide: `docs/DEPLOYMENT.md`
- ✅ Cloud Run deployment success: `docs/CLOUD_RUN_DEPLOYMENT_SUCCESS.md`
- ✅ Updated README with Cloud Run instructions

**Testing and Validation**
- ✅ Successfully deployed to Cloud Run
- ✅ HTTP/SSE transport verified working
- ✅ Multi-user isolation tested
- ✅ API key authentication tested
- ✅ Automatic cleanup verified

### 🚀 Enhanced Features (Bonus)

**Git-Sync Integration** (See ADR 0008)
- ✅ `ingest_code_from_git` MCP tool
- ✅ Webhook handlers for GitHub, GitLab, Gitea
- ✅ Auto-sync on git push
- ✅ 99% token savings vs file upload
- ✅ 54/54 tests passing

**Semantic Search** (See ADR 0003)
- ✅ Code chunking pipeline
- ✅ Vertex AI embedding integration
- ✅ Semantic search MCP tools
- ⏳ Awaiting AlloyDB provisioning (83% complete)

## Related ADRs
- ADR 0001: MCP Transport Protocols
- ADR 0003: Code Ingestion Strategy
- ADR 0004: Multi-Project Isolation
- ADR 0005: AWS Deployment Plan (Future)
- ADR 0006: OpenShift Deployment Plan (Future)

## References
- [Cloud Run MCP Guide](https://codelabs.developers.google.com/codelabs/cloud-run/how-to-deploy-a-secure-mcp-server-on-cloud-run)
- [FastMCP HTTP Transport](https://github.com/jlowin/fastmcp)
- [Cloud Storage Lifecycle Management](https://cloud.google.com/storage/docs/lifecycle)
- [Cloud Scheduler](https://cloud.google.com/scheduler/docs)
