# CI/CD Pipeline Setup Guide - Red Hat OpenShift

**Platform**: Red Hat OpenShift (Kubernetes)
**Status**: 📋 **Coming Soon** (Phase 2C)
**Reference**: [ADR 0007 - OpenShift HTTP Deployment](adrs/0007-openshift-http-deployment-with-auto-cleanup.md)

> **Note**: This guide will cover OpenShift-specific CI/CD setup. For other platforms, see:
> - [GCP Setup Guide](CI_CD_SETUP_GUIDE_GCP.md) ✅ **Available Now**
> - [AWS Setup Guide](CI_CD_SETUP_GUIDE_AWS.md) *(Coming Soon)*

## Status

This guide is **planned for Phase 2C** of the implementation roadmap. The OpenShift deployment automation will be added after GCP and AWS deployments are validated.

**Target Timeline**: After Phase 2A validation (estimated Q2 2026)

## Planned Features

When available, this guide will cover:

### CI/CD Pipeline for OpenShift

- **Automated Security Scanning**: Same as GCP (Gitleaks, Trivy, Bandit)
- **GitOps Deployment**: Tekton Pipelines (OpenShift-native CI/CD)
- **GitHub Actions Alternative**: For teams not using Tekton
- **Safe Deletion**: Manual approval-gated infrastructure deletion
- **Multi-Environment**: dev, staging, prod with namespace isolation

### OpenShift-Specific Components

1. **Deployment Options**:
   - **Tekton Pipelines** (recommended for OpenShift)
   - GitHub Actions (alternative for hybrid workflows)

2. **Container Platform**:
   - OpenShift Pods (not serverless like Lambda/Cloud Run)
   - Horizontal Pod Autoscaler (HPA) for scaling
   - Route with edge TLS termination

3. **Infrastructure**:
   - Helm charts for Kubernetes resources
   - Ansible for application configuration
   - OpenShift Data Foundation (ODF) for S3-compatible storage
   - Milvus vector database (Phase 3C)
   - vLLM for embeddings (Phase 3C)

4. **Storage**:
   - ObjectBucketClaim (ODF S3-compatible)
   - PersistentVolumeClaims for databases

5. **Secrets**:
   - Sealed Secrets for GitOps
   - OpenShift Secret resources
   - External Secrets Operator (optional)

## Pipeline Architecture (Planned)

### Option 1: Tekton Pipelines (OpenShift-Native)

```
┌─────────────────────────────────────────────────────────────┐
│  Git Push → Webhook → EventListener                         │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Pipeline Start (Tekton)                                     │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Task 1: Security Scanning                                   │
│  - Gitleaks (secrets detection)                             │
│  - Trivy (vulnerability scanning)                           │
│  - Bandit (Python security linting)                         │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Task 2: Testing                                             │
│  - pytest (unit tests)                                       │
│  - Integration tests                                         │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Task 3: Build & Push                                        │
│  - buildah/s2i build                                         │
│  - Push to OpenShift Internal Registry                      │
│  - Tag with commit SHA                                       │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Task 4: Deploy (Helm + Ansible)                            │
│  - helm upgrade --install                                    │
│  - Ansible configuration                                     │
│  - Apply NetworkPolicy and SCC                              │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Task 5: Verification (MCP Tests)                            │
│  - MCP tool validation (ADR 0010)                           │
│  - Health checks                                             │
└─────────────────────────────────────────────────────────────┘
```

### Option 2: GitHub Actions (Hybrid)

```
┌─────────────────────────────────────────────────────────────┐
│  Developer Push/PR                                           │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Security Scanning (security-scan.yml)             │
│  - Same as GCP (reusable workflow)                          │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: Testing                                            │
│  - Unit tests (pytest)                                       │
│  - Integration tests                                         │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: Build & Push                                       │
│  - Docker build                                              │
│  - Push to OpenShift Registry (or external)                 │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 4: Deploy (Helm + Ansible)                            │
│  - oc login (via service account token)                     │
│  - helm upgrade --install                                    │
│  - Ansible playbook                                          │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 5: Verification (MCP Tests)                           │
│  - MCP tool validation                                       │
│  - Route health check                                        │
└─────────────────────────────────────────────────────────────┘
```

## Planned Workflows

### Tekton Pipeline (pipeline.yaml) - Coming Soon

**Components**:
- `pipeline.yaml`: Main pipeline definition
- `tasks.yaml`: Custom tasks (build, test, deploy)
- `triggers.yaml`: EventListener and TriggerBinding
- `triggertemplate.yaml`: Pipeline instantiation

**Features**:
- Runs entirely within OpenShift cluster
- No external dependencies (except Git webhooks)
- Full GitOps workflow
- Integrated with OpenShift UI

### GitHub Actions Alternative

**deploy-openshift.yml** (Coming Soon):
- Deploy from GitHub Actions to OpenShift
- Uses `oc` CLI with service account token
- Helm for resource management
- Ansible for configuration

**delete-openshift.yml** (Coming Soon):
- Manual approval gates
- Resource cleanup via Helm
- Audit logging
- Production protection

## Cost Comparison

| Deployment Type | Monthly Cost | Notes |
|----------------|-------------|-------|
| **Managed ROSA** | ~$600 | AWS-managed OpenShift |
| **Managed ARO** | ~$600 | Azure-managed OpenShift |
| **Self-Hosted OCP** | ~$4,887 | On-premise hardware + subscriptions |
| **OKD (Free)** | Hardware cost only | Community distribution |

**Recommendation**:
- **ROSA/ARO** for production (managed, easier)
- **Self-hosted** for large scale or air-gapped
- **OKD** for development/testing only

## Prerequisites (When Available)

1. OpenShift 4.12+ cluster access
2. `oc` CLI installed and configured
3. Helm 3+ installed
4. Ansible >= 2.14
5. Docker for local testing
6. For GPU workloads (Phase 3C): NVIDIA GPU nodes

## Tekton vs GitHub Actions

| Feature | Tekton | GitHub Actions |
|---------|--------|---------------|
| **Runs in cluster** | ✅ Yes | ❌ No |
| **GitOps-friendly** | ✅ Yes | ⚠️ Hybrid |
| **Air-gap support** | ✅ Yes | ❌ No |
| **Setup complexity** | ⚠️ Medium | ✅ Easy |
| **OpenShift UI integration** | ✅ Yes | ❌ No |
| **Reuse GCP workflows** | ❌ No | ✅ Yes |

**Recommendation**:
- Use **Tekton** for OpenShift-native GitOps
- Use **GitHub Actions** if you're already using it for GCP/AWS

## Implementation Roadmap

**Phase 2C: OpenShift HTTP Deployment** (Planned)
- Week 1-2: Helm chart development
- Week 2-3: Ansible playbooks adaptation
- Week 3-4: Tekton pipeline OR GitHub Actions workflow
- Week 4-5: Testing and documentation
- Week 5-6: Security configuration (NetworkPolicy, SCC)

**Phase 3C: OpenShift Semantic Search** (Future)
- Milvus vector database deployment
- vLLM for embeddings (requires GPU)
- Ingestion pipeline adaptation
- MCP tools for semantic search

## OpenShift-Specific Considerations

### 1. SecurityContextConstraints (SCC)

OpenShift requires explicit security policies:
```yaml
# Custom SCC for code-index-mcp
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: code-index-mcp-scc
allowHostDirVolumePlugin: false
allowHostIPC: false
allowHostNetwork: false
allowHostPID: false
allowHostPorts: false
allowPrivilegedContainer: false
runAsUser:
  type: MustRunAsRange
```

### 2. Routes (not Ingress)

OpenShift uses Routes for external access:
```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: code-index-mcp
spec:
  tls:
    termination: edge
  to:
    kind: Service
    name: code-index-mcp
```

### 3. NetworkPolicy

Namespace isolation with NetworkPolicy:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: code-index-mcp-policy
spec:
  podSelector:
    matchLabels:
      app: code-index-mcp
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: openshift-ingress
```

## How to Get Notified

Watch for updates:
1. **GitHub Releases**: Subscribe to repository releases
2. **Implementation Plan**: Check `docs/IMPLEMENTATION_PLAN.md` for progress
3. **ADR Updates**: Monitor `docs/adrs/` for OpenShift-related decisions

## Current Alternative

While OpenShift support is in development, you can:
1. Use the **GCP deployment** (fully operational)
2. Follow [CI_CD_SETUP_GUIDE_GCP.md](CI_CD_SETUP_GUIDE_GCP.md)
3. Deploy to GCP and migrate to OpenShift later

## Questions or Contributions

- **GitHub Issues**: Request OpenShift support or volunteer to help implement
- **Pull Requests**: Contributions welcome for:
  - Helm charts
  - Tekton pipelines
  - Ansible playbooks
  - Documentation
- **Discussions**: Share your OpenShift deployment requirements

---

**Last Updated**: November 14, 2025
**Status**: Planning Phase
**Expected Availability**: Q2 2026 (after Phase 2B)
