# Architectural Decision Records (ADRs)

This directory contains Architectural Decision Records (ADRs) documenting key design decisions for the Code Index MCP project.

## What are ADRs?

ADRs capture important architectural decisions along with their context and consequences. Each ADR describes:
- **Context**: The situation and forces at play
- **Decision**: The architecture/design decision made
- **Consequences**: The resulting context after applying the decision

## Quick Reference

| ADR | Title | Status | Key Decision |
|-----|-------|--------|--------------|
| [0001](0001-mcp-stdio-protocol-cloud-deployment-constraints.md) | MCP Transport Protocols | ✅ Implemented | Support both stdio (local) and HTTP/SSE (cloud) transports |
| [0002](0002-cloud-run-http-deployment-with-auto-cleanup.md) | Cloud Run HTTP Deployment | ✅ Implemented | Deploy to Cloud Run with automatic resource cleanup |
| [0003](0003-google-cloud-code-ingestion-with-alloydb.md) | Google Cloud Code Ingestion | 🚧 Future | Use AlloyDB + Vertex AI for semantic search (GCP) |
| [0004](0004-aws-code-ingestion-with-aurora-and-bedrock.md) | AWS Code Ingestion | 🚧 Future | Use Aurora PostgreSQL + Bedrock (AWS) |
| [0005](0005-openshift-code-ingestion-with-milvus.md) | OpenShift Code Ingestion | 🚧 Future | Use Milvus + vLLM + ODF (OpenShift) |
| [0006](0006-aws-http-deployment-with-auto-cleanup.md) | AWS HTTP Deployment | 🚧 Future | Deploy to Lambda/ECS with EventBridge cleanup |
| [0007](0007-openshift-http-deployment-with-auto-cleanup.md) | OpenShift HTTP Deployment | 🚧 Future | Deploy to OpenShift with CronJob cleanup |
| [0008](0008-git-sync-ingestion-strategy.md) | Git-Sync Ingestion Strategy | ✅ Implemented | Use git-sync for efficient code ingestion with webhooks |
| [0009](0009-ansible-deployment-automation.md) | Ansible Deployment Automation | ✅ Implemented | Use Ansible for deployment and operational tasks |
| [0010](0010-mcp-server-testing-with-ansible.md) | MCP Server Testing with Ansible | ✅ Accepted | Use tosin2013.mcp_audit for automated MCP testing |
| [0011](0011-cicd-pipeline-and-security-architecture.md) | CI/CD Pipeline and Security Architecture | ✅ Implemented | Comprehensive CI/CD with GitHub Actions, Tekton, and security scanning |

## Decision Timeline

```
2025-10-24 - 2025-11-02
├── Transport & Core
│   └── ADR 0001: MCP Transport Protocols ✅
│
├── HTTP Deployments
│   ├── ADR 0002: Google Cloud Run HTTP Deployment ✅
│   ├── ADR 0006: AWS HTTP Deployment (Lambda/ECS) 🚧
│   └── ADR 0007: OpenShift HTTP Deployment 🚧
│
├── Code Ingestion (Semantic Search)
│   ├── ADR 0003: Google Cloud Ingestion (AlloyDB) 🚧
│   ├── ADR 0004: AWS Ingestion (Aurora + Bedrock) 🚧
│   ├── ADR 0005: OpenShift Ingestion (Milvus + vLLM) 🚧
│   └── ADR 0008: Git-Sync Ingestion Strategy ✅
│
└── DevOps & Automation
    ├── ADR 0009: Ansible Deployment Automation ✅
    ├── ADR 0010: MCP Server Testing with Ansible ✅
    └── ADR 0011: CI/CD Pipeline and Security Architecture ✅
```

## ADR Summaries

### ADR 0001: MCP Transport Protocols and Cloud Deployment Architecture

**Status**: ✅ Implemented

**Problem**: How to support both local development and cloud deployment?

**Decision**: Implement dual transport support in FastMCP:
- **stdio transport** (default) - For local execution, spawned as subprocess
- **HTTP/SSE transport** - For cloud deployment, standard HTTP endpoint

**Key Code**:
```python
def create_mcp_server():
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        return FastMCP("CodeIndexer", transport="sse", port=8080)
    else:
        return FastMCP("CodeIndexer")  # stdio default
```

**Impact**:
- ✅ Zero deployment complexity for individual developers
- ✅ Full cloud deployment capability for teams
- ✅ Same codebase for both modes
- ❌ HTTP mode requires cloud infrastructure setup

**Related**: Supersedes previous SSH-based deployment approach

---

### ADR 0002: Cloud Run HTTP Deployment with Automatic Resource Cleanup

**Status**: ✅ Implemented

**Problem**: How to deploy to Google Cloud Run securely with multi-project support and prevent cost accumulation?

**Decision**: Deploy using HTTP/SSE transport with multi-layer cleanup strategy:

1. **Architecture**:
   - Cloud Run with auto-scale to zero (no idle costs)
   - Cloud Storage for user code (multi-tenant namespaces)
   - API key authentication
   - Secret Manager for credentials (no keys in git)

2. **Multi-Project Isolation**:
   ```
   gs://project-code-storage/
   ├── users/
   │   ├── user_abc123/project_1/
   │   ├── user_abc123/project_2/
   │   └── user_xyz789/project_1/
   ```

3. **Automatic Cleanup**:
   - Cloud Scheduler jobs (daily cleanup of 30+ day idle projects)
   - Storage lifecycle rules (archive after 30 days, delete after 90)
   - Budget alerts to prevent cost overruns

**Key Security**:
- Never commit credentials (comprehensive .gitignore)
- Use Workload Identity (no service account keys)
- API keys stored in Secret Manager
- HTTPS only

**Impact**:
- ✅ True serverless (scales to zero)
- ✅ Multi-user with isolation
- ✅ Automatic cost control
- ✅ ~$3/month for typical team usage
- ❌ Cold start latency (5-10s after idle)

**Deployment**:
```bash
cd deployment/gcp
./deploy.sh
```

---

### ADR 0003: Google Cloud Code Ingestion with AlloyDB

**Status**: 🚧 Future Enhancement

**Problem**: How to enable semantic code search in Google Cloud deployments?

**Decision**: Use AlloyDB PostgreSQL with pgvector for vector similarity search and Vertex AI for embeddings.

**Architecture**:
```
Cloud Run (MCP Server)
    ↓
AlloyDB (pgvector + Vertex AI integration)
    ↓
Vertex AI (textembedding-gecko@003)
    ↓
Cloud Storage (Code + Indexes)
```

**Key Features**:
- AlloyDB's native Vertex AI integration (SQL function)
- HNSW index for fast vector similarity search
- 1536-dimensional embeddings
- Full-text search combined with semantic search

**Schema Example**:
```sql
CREATE TABLE code_chunks (
    chunk_id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536),  -- Vertex AI dimensions
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX code_chunks_embedding_idx ON code_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Cost**: ~$220/month for production workload

**Impact**:
- ✅ Native GCP integration
- ✅ Managed embedding generation
- ✅ High performance with HNSW
- ❌ Higher cost than alternatives
- ❌ Vendor lock-in to Google Cloud

**Related**: Complements ADR 0002 (Cloud Run deployment)

---

### ADR 0004: AWS Code Ingestion with Aurora PostgreSQL and Amazon Bedrock

**Status**: 🚧 Future Enhancement

**Problem**: How to enable semantic code search in AWS deployments?

**Decision**: Use Aurora PostgreSQL Serverless v2 with pgvector and Amazon Bedrock for embeddings.

**Architecture**:
```
Lambda/ECS (MCP Server)
    ↓
Aurora PostgreSQL Serverless v2 (pgvector)
    ↓
Amazon Bedrock (Titan Embeddings)
    ↓
S3 (Code + Indexes)
```

**Key Differences from Google Cloud**:
- Aurora Serverless v2 (scales to zero like Cloud Run)
- Amazon Bedrock Titan Embeddings ($0.10 per 1M tokens)
- Lambda or ECS for compute
- 3x cheaper than Google Cloud (~$65/month vs ~$220/month)

**Trade-offs**:
- ✅ **Cost-effective** (lowest cost option)
- ✅ Serverless database (scales to zero)
- ✅ Pay-per-use embeddings
- ❌ Less tight integration (separate API calls for embeddings)
- ❌ No native SQL embedding function

**Deployment**:
```bash
cd deployment/aws
./deploy.sh
```

**Related**: Parallel implementation to ADR 0003 (Google Cloud)

---

### ADR 0005: OpenShift Code Ingestion with Milvus, vLLM, and ODF

**Status**: 🚧 Future Enhancement

**Problem**: How to enable semantic code search in OpenShift (Kubernetes) deployments, especially for on-premise and air-gapped environments?

**Decision**: Use Milvus vector database, vLLM for embeddings, and OpenShift Data Foundation for S3-compatible storage.

**Architecture**:
```
OpenShift Pod (MCP Server)
    ↓
Milvus (Vector database with HNSW index)
    ↓
vLLM (E5-Mistral-7B embeddings with GPU)
    ↓
OpenShift Data Foundation (S3-compatible via Ceph/NooBaa)
```

**Key Components**:

1. **Milvus** - Open-source vector database
   - HNSW/IVF_FLAT indexes for fast similarity search
   - Horizontal scaling with query nodes
   - S3 backend for storage

2. **vLLM** - High-performance LLM inference
   - Production-grade (vs. Ollama for dev)
   - GPU acceleration (NVIDIA T4/A10/A100)
   - OpenAI-compatible API
   - Models: E5-Mistral-7B, BGE-Large, E5-Base

3. **OpenShift Data Foundation (ODF)**
   - S3-compatible API via Ceph/NooBaa
   - Multi-cloud object storage
   - Block storage for PostgreSQL/Milvus
   - Built-in data protection

**Storage Structure**:
```
ODF S3 (via NooBaa):
└── code-storage-bucket/
    ├── users/
    │   ├── user_abc123/project_1/
    │   └── user_xyz789/project_1/

ODF Block (PVCs):
├── postgresql-data (16Gi)
└── milvus-data (32Gi)
```

**Deployment**:
```bash
cd deployment/openshift
helm install code-index-mcp ./helm-chart
```

**Hardware Requirements**:
- CPU: 4+ cores per node
- Memory: 16+ GB per node
- GPU: NVIDIA T4/A10/A100 (for vLLM)
- Storage: 50+ GB ODF

**Impact**:
- ✅ **Open-source stack** (no vendor lock-in)
- ✅ **On-premise ready** (no external dependencies)
- ✅ **Air-gap capable** (all components self-hosted)
- ✅ **Production-grade inference** (vLLM)
- ✅ **Cost-effective for large scale** (one-time hardware)
- ❌ Requires GPU infrastructure
- ❌ More complex setup than cloud services
- ❌ Manual scaling and maintenance

**Related**: Alternative to ADR 0003 (Google Cloud) and ADR 0004 (AWS) for on-premise

---

### ADR 0006: AWS HTTP Deployment with Automatic Resource Cleanup

**Status**: 🚧 Future Enhancement

**Problem**: How to deploy code-index-mcp to AWS with HTTP/SSE transport, multi-user support, and automatic resource cleanup?

**Decision**: Deploy using Lambda (serverless) or ECS Fargate (containerized) with API Gateway, EventBridge cleanup, and S3 storage.

**Architecture Options**:

**Option A: Lambda + API Gateway** (Recommended for light usage)
```
API Gateway → Lambda → S3 Storage
- True serverless (pay per request)
- 15-minute timeout limit
- Cold start latency (~1-3s)
```

**Option B: ECS Fargate + ALB** (Recommended for heavy usage)
```
ALB → ECS Fargate → S3 Storage
- Longer running tasks (no timeout)
- Minimum $10/month (cannot scale to zero)
- Better for continuous services
```

**Key Features**:

1. **Multi-Project Isolation**:
   ```
   s3://account-code-storage/
   └── users/
       ├── user_abc123/project_1/
       └── user_xyz789/project_1/
   ```

2. **Automatic Cleanup**:
   - EventBridge rules (daily cleanup of 30+ day idle projects)
   - S3 lifecycle policies (archive after 30 days, delete after 90)
   - Budget alerts to prevent cost overruns

3. **Security**:
   - API Gateway authentication
   - AWS Secrets Manager for API keys
   - IAM execution roles (no access keys)

**Cost Comparison**:
- Lambda option: ~$2.50/month (12x cheaper than Google Cloud!)
- ECS option: ~$27/month (8x cheaper than Google Cloud!)
- Google Cloud Run: ~$220/month

**Deployment**:
```bash
cd deployment/aws
./deploy-lambda.sh  # or ./deploy-ecs.sh
```

**Impact**:
- ✅ **Lowest cost option** ($2.50/month with Lambda)
- ✅ True serverless with Lambda (scales to zero)
- ✅ Flexible (choose Lambda or ECS based on needs)
- ❌ Lambda 15-minute timeout (use ECS for longer operations)
- ❌ More services to manage than Cloud Run

**Related**: Parallel to ADR 0002 (Google Cloud Run), complements ADR 0004 (AWS Code Ingestion)

---

### ADR 0007: OpenShift HTTP Deployment with Automatic Resource Cleanup

**Status**: 🚧 Future Enhancement

**Problem**: How to deploy code-index-mcp to OpenShift/Kubernetes with HTTP/SSE transport, multi-user support, and automatic resource cleanup?

**Decision**: Deploy using Kubernetes Deployment with OpenShift Route, CronJob cleanup, and ODF/PVC storage.

**Architecture**:
```
OpenShift Route (HTTPS edge)
    ↓
Service (ClusterIP)
    ↓
Pods (2 replicas, HPA)
    ↓
ODF S3 / PVCs (user storage)
```

**Key Features**:

1. **Multi-Project Isolation**:
   - Option A: ODF S3 (ObjectBucketClaim per user)
   - Option B: PVCs (PersistentVolumeClaim per user)

2. **Automatic Cleanup**:
   - CronJob (daily cleanup of 30+ day idle projects)
   - Storage lifecycle policies via ODF
   - Resource quotas to prevent overuse

3. **Security**:
   - NetworkPolicy for ingress/egress control
   - SecurityContextConstraints (OpenShift-specific)
   - Sealed Secrets or External Secrets Operator
   - RBAC for service accounts

4. **Auto-Scaling**:
   - Horizontal Pod Autoscaler (min: 1, max: 10)
   - Note: Cannot scale to zero with standard HPA
   - Consider KEDA or Knative for true zero scaling

**Storage Options**:

**ODF S3** (Recommended):
```yaml
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: code-storage-user-abc123
spec:
  generateBucketName: code-index-user-abc123
  storageClassName: openshift-storage.noobaa.io
```

**PVCs** (Alternative):
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: code-storage-user-abc123
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: 50Gi
  storageClassName: ocs-storagecluster-cephfs
```

**Cost Comparison**:
- Managed OpenShift (ROSA/ARO): ~$600/month
- Self-hosted OpenShift: ~$4,887/month (hardware + license)
- Google Cloud Run: ~$220/month
- AWS Lambda: ~$2.50/month

**Note**: OpenShift is cost-effective only for:
- Large-scale deployments (100+ services)
- On-premise requirements
- Air-gapped environments
- Organizations with existing OpenShift infrastructure

**Deployment**:
```bash
cd deployment/openshift
./deploy.sh
# or
helm install code-index-mcp ./helm-chart
```

**Impact**:
- ✅ **On-premise deployment** (no cloud dependency)
- ✅ **Air-gap capable** (all components self-hosted)
- ✅ **Enterprise security** (RBAC, NetworkPolicy, SCC)
- ✅ **Kubernetes-native** (portable to other K8s)
- ❌ Cannot scale to zero (minimum 1 replica)
- ❌ Highest cost option (unless at large scale)
- ❌ More complex setup than cloud services

**Related**: Parallel to ADR 0002 (Google Cloud Run), complements ADR 0005 (OpenShift Code Ingestion)

---

### ADR 0008: Git-Sync Ingestion Strategy for Cloud Deployments

**Status**: ✅ Implemented

**Problem**: How to efficiently ingest code into cloud deployments for semantic search? Legacy file upload approach is slow (high token usage) and doesn't support incremental updates.

**Decision**: Use direct Git repository cloning and syncing with webhook-based automatic updates.

**Key Features**:
- **99% token savings** vs file upload (no files sent to LLM)
- **95% faster** incremental updates (pull only changed files)
- **Auto-sync** via webhooks on every `git push`
- **Multi-platform**: GitHub, GitLab, Bitbucket, Gitea
- **Private repo support** with personal access tokens
- **Persistent repos** in Cloud Storage for fast re-syncs

**Architecture**:
```
git push → Webhook → Cloud Run → git pull → Re-ingest changed files
```

**Impact**:
- ✅ **Massive cost savings** (no file upload to LLM)
- ✅ **Fast incremental updates** (seconds vs minutes)
- ✅ **Automated sync** (no manual intervention)
- ✅ **Production-ready** (54/54 tests passing)
- ❌ Requires git hosting (GitHub, GitLab, etc.)

**Related**: Replaces legacy file upload approach, works with ADR 0002/0003/0004/0005

---

### ADR 0009: Ansible Deployment Automation for Google Cloud

**Status**: ✅ Implemented

**Problem**: Bash scripts for deployment lacked idempotency, testing, rollback, and were hard to maintain.

**Decision**: Replace bash scripts with Ansible playbooks and reusable roles for declarative, idempotent deployments.

**Key Features**:
- **Idempotent**: Safe to re-run without side effects
- **Declarative**: Define desired state, Ansible ensures it
- **Multi-Environment**: Single playbook for dev/staging/prod
- **Testable**: Dry-run mode (`--check`)
- **Rollback**: Automatic rollback on failure
- **Utilities**: API key generation, schema verification, teardown

**Architecture**:
```
deploy.yml → code-index-mcp role →
  ├── prerequisites.yml
  ├── storage.yml
  ├── build_image.yml
  ├── deploy_cloudrun.yml
  └── apply_schema.yml
```

**Impact**:
- ✅ **Production-ready** (100% complete)
- ✅ **Maintainable** (YAML vs bash)
- ✅ **Reusable** (roles for AWS/OpenShift planned)
- ✅ **CI/CD ready** (GitHub Actions/GitLab CI)
- ❌ Learning curve (Ansible YAML syntax)

**Related**: Complements ADR 0002 (Cloud Run), used by ADR 0011 (CI/CD)

---

### ADR 0010: MCP Server Testing and Validation with Ansible

**Status**: ✅ Accepted

**Problem**: How to systematically test MCP server deployments across different transports (stdio, HTTP/SSE) and ensure all tools work correctly?

**Decision**: Use `tosin2013.mcp_audit` Ansible collection for automated, comprehensive MCP testing.

**Key Features**:
- **Multi-transport testing**: stdio (local) and HTTP/SSE (cloud)
- **Comprehensive validation**: All MCP tools systematically tested
- **Regression prevention**: Full test suites catch breaking changes
- **CI/CD integration**: GitHub Actions/GitLab CI compatible
- **Test playbooks**: test-local.yml, test-cloud.yml, test-regression.yml

**Test Coverage**:
- ✅ Server discovery and capabilities
- ✅ All metadata tools (set_project_path, find_files, search_code_advanced)
- ✅ File resource retrieval
- ✅ Semantic search (if AlloyDB deployed)
- ✅ Git ingestion

**Impact**:
- ✅ **Automated testing** (no manual validation needed)
- ✅ **Multi-transport** (ensures local and cloud parity)
- ✅ **Regression prevention** (catches breaking changes)
- ✅ **CI/CD ready** (integrates with pipelines)

**Related**: Used by ADR 0011 (CI/CD verification stage)

---

### ADR 0011: CI/CD Pipeline and Security Architecture

**Status**: ✅ Implemented

**Problem**: Need automated, secure CI/CD pipelines for multi-cloud deployments (GCP, AWS, OpenShift) with comprehensive security scanning.

**Decision**: Implement comprehensive CI/CD framework using GitHub Actions (cloud) and Tekton (OpenShift) with multi-layer security scanning.

**Pipeline Stages**:
1. **Security Scans**: Gitleaks (secrets), Trivy (vulnerabilities), Bandit (Python security)
2. **Testing**: Unit and integration tests
3. **Build**: Docker image with commit SHA tag
4. **Infrastructure**: Terraform for IaC
5. **Application**: Ansible for deployment
6. **Verification**: Health checks + MCP tool validation (ADR 0010)

**Security Features**:
- **OIDC Workload Identity**: Keyless authentication (no service account keys)
- **Secret Detection**: Gitleaks prevents credential commits
- **Vulnerability Scanning**: Trivy blocks CRITICAL/HIGH findings
- **Controlled Deletion**: Manual approval gates for infrastructure teardown
- **Audit Logging**: Complete record of all deployments

**Architecture**:
```
GitHub Actions (GCP/AWS) + Tekton (OpenShift)
  ├── Security Scans (Gitleaks, Trivy, Bandit)
  ├── Tests (pytest)
  ├── Build (Docker)
  ├── Deploy Infrastructure (Terraform)
  ├── Deploy Application (Ansible - ADR 0009)
  └── Verify (MCP Tests - ADR 0010)
```

**Impact**:
- ✅ **Security-first**: Multiple layers of security validation
- ✅ **Automated**: `git push` triggers everything
- ✅ **Multi-cloud**: GCP, AWS, OpenShift support
- ✅ **Safe deletions**: Manual approval prevents accidents
- ✅ **Auditable**: Complete deployment history
- ❌ Complexity (more complex than manual deployments)

**Related**: Uses ADR 0009 (Ansible) for deployment, ADR 0010 (Testing) for verification

---

## Decision Principles

All architectural decisions in this project follow these principles:

1. **Local-First**: Prioritize local development experience
2. **Optional Cloud**: Cloud features are enhancements, not requirements
3. **Platform-Native**: Use cloud-native services for each platform
4. **Cost-Conscious**: Implement auto-cleanup and scale-to-zero
5. **Open Standards**: Prefer open protocols and formats
6. **Security by Default**: Never commit credentials, use managed secrets

## Creating New ADRs

When making a significant architectural decision:

1. **Create a new ADR file**: `docs/adrs/NNNN-title-with-dashes.md`
2. **Use the template**:
   ```markdown
   # ADR NNNN: Title

   **Status**: Proposed | Accepted | Implemented | Deprecated | Superseded
   **Date**: YYYY-MM-DD
   **Decision Maker**: Team/Role

   ## Context
   What is the issue that we're seeing that is motivating this decision?

   ## Decision
   What is the change that we're proposing and/or doing?

   ## Consequences
   What becomes easier or more difficult to do because of this change?

   ## Related ADRs
   Links to related decisions
   ```
3. **Update this README**: Add entry to the table and timeline
4. **Update CLAUDE.md**: If the decision affects development workflows

## Implementation Roadmap

For a comprehensive implementation plan with detailed steps, timelines, and dependencies, see:

**📋 [Implementation Plan](../IMPLEMENTATION_PLAN.md)**

This document provides:
- Complete implementation sequences for all platforms
- Week-by-week task breakdowns
- Success criteria and testing checklists
- Risk management strategies
- Platform selection decision tree

**Quick Links**:
- [Phase 2: HTTP Deployments](../IMPLEMENTATION_PLAN.md#phase-2-http-deployments) - Basic cloud deployment
- [Phase 3: Semantic Search](../IMPLEMENTATION_PLAN.md#phase-3-semantic-search) - Vector embeddings
- [Platform Selection Guide](../IMPLEMENTATION_PLAN.md#platform-selection-guide) - Choose your platform

## References

- [Implementation Plan](../IMPLEMENTATION_PLAN.md) - Detailed roadmap and task breakdown
- [Cloud Deployment Guide](../DEPLOYMENT.md) - Platform-specific deployment instructions
- [ADR Documentation](https://adr.github.io/) - ADR methodology
- [MCP Specification](https://spec.modelcontextprotocol.io/) - Model Context Protocol
- [FastMCP Documentation](https://github.com/jlowin/fastmcp) - Python MCP framework
