# ADR 0007: OpenShift HTTP Deployment with Automatic Resource Cleanup

**Status**: Planning Document (Phase 2C - Future Enhancement)
**Date**: 2025-10-24
**Decision Maker**: Architecture Team
**Related to**: ADR 0001 (HTTP/SSE Transport), ADR 0002 (Google Cloud equivalent), ADR 0005 (OpenShift Code Ingestion)
**Implementation Sequence**: Phase 2C (after Phase 2A completion, enables Phase 3C)

## Context

With MCP's HTTP/SSE transport support, we can deploy code-index-mcp to OpenShift as a standard Kubernetes service. This ADR addresses OpenShift-specific HTTP deployment concerns parallel to ADR 0002 (Google Cloud Run) and ADR 0006 (AWS Lambda/ECS).

**Note**: This is a **planning document** for Phase 2C (future implementation). It is not currently implemented.

**Prerequisites:**
- ✅ ADR 0001: MCP Transport Protocols (Complete)
- ✅ ADR 0002: Cloud Run HTTP Deployment (Complete - Phase 2A reference implementation)
- This ADR enables ADR 0005 (OpenShift semantic search with Milvus and vLLM)

### User Requirements

1. **"How can users use this in OpenShift deployments?"**
   - Users connect to HTTPS endpoint via OpenShift Route
   - Upload code via API or sync from git repositories

2. **"Will it be secure?"**
   - HTTPS encryption with edge TLS termination
   - OAuth/Token authentication
   - See security section below

3. **"How does multi-project support work?"**
   - Per-user namespaces or storage prefixes
   - Isolated PVCs or ODF buckets
   - See multi-project section below

4. **"How to delete OpenShift services? Automation?"**
   - Automated cleanup via CronJobs
   - Resource quotas and TTLs
   - See cleanup section below

5. **"How to protect credentials in git?"**
   - Never commit credentials
   - Use Sealed Secrets or External Secrets Operator
   - See security section below

## Decision: OpenShift Deployment with HTTP Transport

Deploy code-index-mcp to OpenShift using Kubernetes Deployments with HTTP/SSE transport and automatic resource management via CronJobs.

## Architecture

### Deployment Model

```
┌─────────────┐                           ┌──────────────────┐
│   Claude    │   HTTPS (authenticated)   │  OpenShift       │
│   Desktop   │──────────────────────────►│  Route (edge)    │
│             │                           │      ↓           │
│             │                           │  Service         │
│             │                           │      ↓           │
│             │◄──────────────────────────│  Pods (2)        │
│             │   Response                └────────┬─────────┘
└─────────────┘                                    │
                                          ┌────────▼─────────┐
                                          │  ODF S3 / PVCs   │
                                          │  - User code     │
                                          │  - Indexes       │
                                          │  - Cache         │
                                          └──────────────────┘
```

### Components

1. **Deployment**
   - Image: code-index-mcp:latest
   - Replicas: 2 (high availability)
   - Container port: 8080
   - Environment: MCP_TRANSPORT=http
   - Resources: 2 CPU, 4Gi memory

2. **Service**
   - Type: ClusterIP
   - Port: 80 → 8080
   - Protocol: HTTP
   - Session affinity: ClientIP (for stateful sessions)

3. **Route**
   - TLS termination: Edge
   - Custom hostname: code-index-mcp.apps.cluster.example.com
   - Automatic HTTPS redirect
   - Rate limiting annotations

4. **Storage**
   - **Option A**: OpenShift Data Foundation (ODF) S3
     - ObjectBucketClaim for S3-compatible storage
     - Per-user buckets or prefixes
   - **Option B**: Persistent Volume Claims (PVCs)
     - ReadWriteMany for shared access
     - Per-user PVCs with quotas

5. **CronJobs** (Cleanup Automation)
   - Daily schedule: Delete inactive projects
   - Weekly schedule: Cleanup old indexes
   - Monthly schedule: Storage usage reports

6. **Secrets**
   - Sealed Secrets for API keys
   - External Secrets Operator for vault integration
   - No secrets in ConfigMaps or environment variables

## Security Architecture

### Authentication Flow

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ 1. Request with token
       ▼
┌──────────────┐
│  Route       │
│  (TLS edge)  │
└──────┬───────┘
       │ 2. Forward to Service
       ▼
┌──────────────┐
│  Pod         │
│  (Validate   │
│   token)     │
└──────────────┘
```

### Credential Management

**CRITICAL: Never commit credentials to git!**

```bash
# .gitignore (already configured)
*.key
*.pem
secrets/
deployment/**/*.key
openshift-token.txt
```

**Proper Approach:**

1. **API Keys**: Use Sealed Secrets
   ```bash
   # Create secret with kubeseal
   echo -n "sk-abc123..." | \
     kubectl create secret generic code-index-api-keys \
       --dry-run=client \
       --from-file=api-key=/dev/stdin \
       -o yaml | \
     kubeseal -o yaml > sealed-secret.yaml

   # Apply sealed secret
   oc apply -f sealed-secret.yaml
   ```

2. **Service Account Tokens**: Use RBAC
   ```bash
   # Create service account
   oc create serviceaccount code-index-mcp -n code-index-mcp

   # No need to download/commit tokens
   # Pods automatically mount SA token
   ```

3. **External Secrets**: Use External Secrets Operator
   ```yaml
   apiVersion: external-secrets.io/v1beta1
   kind: ExternalSecret
   metadata:
     name: code-index-api-keys
   spec:
     secretStoreRef:
       name: vault-backend
       kind: SecretStore
     target:
       name: api-keys
     data:
       - secretKey: api-key
         remoteRef:
           key: code-index-mcp/api-keys
           property: user1
   ```

### Network Security

#### NetworkPolicy
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: code-index-mcp
  namespace: code-index-mcp
spec:
  podSelector:
    matchLabels:
      app: code-index-mcp
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          network.openshift.io/policy-group: ingress
    ports:
    - protocol: TCP
      port: 8080
  egress:
  # Allow ODF S3 access
  - to:
    - namespaceSelector:
        matchLabels:
          name: openshift-storage
    ports:
    - protocol: TCP
      port: 443
  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: openshift-dns
    ports:
    - protocol: UDP
      port: 53
```

#### SecurityContextConstraints (SCC)
```yaml
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: code-index-mcp-scc
allowPrivilegedContainer: false
runAsUser:
  type: MustRunAsRange
  uidRangeMin: 1000
  uidRangeMax: 65535
seLinuxContext:
  type: MustRunAs
fsGroup:
  type: MustRunAs
supplementalGroups:
  type: RunAsAny
volumes:
- configMap
- downwardAPI
- emptyDir
- persistentVolumeClaim
- secret
```

## Multi-Project Isolation

### Option A: ODF S3 Storage Structure

```yaml
# ObjectBucketClaim for each user
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: code-storage-user-abc123
  namespace: code-index-mcp
spec:
  generateBucketName: code-index-user-abc123
  storageClassName: openshift-storage.noobaa.io
```

```
S3 Bucket: code-index-user-abc123
└── projects/
    ├── project_1/
    │   ├── src/
    │   └── .metadata
    └── project_2/
        ├── src/
        └── .metadata
```

### Option B: PVC Storage Structure

```yaml
# PVC for each user
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: code-storage-user-abc123
  namespace: code-index-mcp
spec:
  accessModes:
  - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
  storageClassName: ocs-storagecluster-cephfs
```

```
PVC: code-storage-user-abc123
└── projects/
    ├── project_1/
    └── project_2/
```

### Namespace Isolation

```python
# In server.py (OpenShift handler)
import boto3  # For ODF S3
# or
from kubernetes import client, config  # For PVCs

@mcp.tool()
def set_project_path(path: str, ctx: Context) -> str:
    user_id = ctx.request_context.user_id  # From auth middleware

    # Enforce namespace
    safe_path = f"/projects/{user_id}/{sanitize_path(path)}"

    # Mount storage
    if os.getenv("STORAGE_TYPE") == "s3":
        # Use ODF S3
        s3 = boto3.client('s3',
            endpoint_url=os.getenv('S3_ENDPOINT'),
            aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('S3_SECRET_KEY'))
        bucket = f"code-index-user-{user_id}"
        # ... download files to local storage ...
    else:
        # Use PVC (already mounted at /storage)
        pvc_path = f"/storage/users/{user_id}/"
        # ... read files from PVC ...

    return ProjectManagementService(ctx).initialize_project(safe_path)
```

### Resource Quotas

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: code-index-mcp-quota
  namespace: code-index-mcp
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    persistentvolumeclaims: "10"
    pods: "20"
```

## Automatic Resource Cleanup

### Challenge: Preventing Resource Accumulation

Without cleanup, projects can accumulate indefinitely:
- Idle projects consume storage
- Abandoned PVCs waste resources
- Old indexes never get deleted

### Solution: Multi-Layer Cleanup Strategy

#### Layer 1: Storage Lifecycle (Manual Configuration)

**For ODF S3:**
```yaml
# S3 lifecycle configuration (applied via NooBaa CLI)
# Delete objects older than 90 days
apiVersion: v1
kind: ConfigMap
metadata:
  name: s3-lifecycle-policy
data:
  lifecycle.json: |
    {
      "Rules": [
        {
          "ID": "Delete old projects",
          "Status": "Enabled",
          "Prefix": "projects/",
          "Expiration": {
            "Days": 90
          }
        }
      ]
    }
```

**For PVCs:**
```yaml
# Manual cleanup - no automatic lifecycle
# Use CronJob to identify and delete unused PVCs
```

#### Layer 2: CronJob Cleanup

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: code-index-cleanup-daily
  namespace: code-index-mcp
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: code-index-cleanup
          containers:
          - name: cleanup
            image: code-index-mcp:latest
            command:
            - python
            - -m
            - code_index_mcp.cleanup
            args:
            - --days=30
            - --dry-run=false
            env:
            - name: MCP_TRANSPORT
              value: "http"
            - name: STORAGE_TYPE
              value: "s3"  # or "pvc"
            - name: S3_ENDPOINT
              valueFrom:
                secretKeyRef:
                  name: code-storage-bucket
                  key: BUCKET_HOST
            - name: S3_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: code-storage-bucket
                  key: AWS_ACCESS_KEY_ID
            - name: S3_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: code-storage-bucket
                  key: AWS_SECRET_ACCESS_KEY
          restartPolicy: OnFailure
---
# RBAC for cleanup job
apiVersion: v1
kind: ServiceAccount
metadata:
  name: code-index-cleanup
  namespace: code-index-mcp
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: code-index-cleanup
  namespace: code-index-mcp
rules:
- apiGroups: [""]
  resources: ["persistentvolumeclaims"]
  verbs: ["list", "delete"]
- apiGroups: ["objectbucket.io"]
  resources: ["objectbucketclaims"]
  verbs: ["list", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: code-index-cleanup
  namespace: code-index-mcp
subjects:
- kind: ServiceAccount
  name: code-index-cleanup
roleRef:
  kind: Role
  name: code-index-cleanup
  apiGroup: rbac.authorization.k8s.io
```

```python
# cleanup.py
import boto3
from datetime import datetime, timedelta
from kubernetes import client, config
import argparse

def cleanup_s3_projects(days: int, dry_run: bool = True):
    """Delete S3 projects inactive for N days"""
    s3 = boto3.client('s3',
        endpoint_url=os.getenv('S3_ENDPOINT'),
        aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('S3_SECRET_KEY'))

    cutoff = datetime.now() - timedelta(days=days)
    deleted = []

    # List all user buckets
    buckets = s3.list_buckets()
    for bucket in buckets['Buckets']:
        if not bucket['Name'].startswith('code-index-user-'):
            continue

        # Check last modified
        objects = s3.list_objects_v2(Bucket=bucket['Name'])
        if 'Contents' not in objects:
            continue

        latest = max(obj['LastModified'] for obj in objects['Contents'])
        if latest.replace(tzinfo=None) < cutoff:
            if not dry_run:
                # Delete all objects
                for obj in objects['Contents']:
                    s3.delete_object(Bucket=bucket['Name'], Key=obj['Key'])
                s3.delete_bucket(Bucket=bucket['Name'])
            deleted.append(bucket['Name'])
            print(f"{'Would delete' if dry_run else 'Deleted'}: {bucket['Name']}")

    return deleted

def cleanup_pvcs(days: int, dry_run: bool = True):
    """Delete unused PVCs"""
    config.load_incluster_config()
    v1 = client.CoreV1Api()

    cutoff = datetime.now() - timedelta(days=days)
    deleted = []

    pvcs = v1.list_namespaced_persistent_volume_claim('code-index-mcp')
    for pvc in pvcs.items:
        if not pvc.metadata.name.startswith('code-storage-user-'):
            continue

        # Check last access time (custom annotation)
        last_access = pvc.metadata.annotations.get('last-access-time')
        if not last_access:
            continue

        last_access_dt = datetime.fromisoformat(last_access)
        if last_access_dt < cutoff:
            if not dry_run:
                v1.delete_namespaced_persistent_volume_claim(
                    name=pvc.metadata.name,
                    namespace='code-index-mcp')
            deleted.append(pvc.metadata.name)
            print(f"{'Would delete' if dry_run else 'Deleted'}: {pvc.metadata.name}")

    return deleted

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--dry-run', type=bool, default=True)
    args = parser.parse_args()

    storage_type = os.getenv('STORAGE_TYPE', 's3')
    if storage_type == 's3':
        cleanup_s3_projects(args.days, args.dry_run)
    else:
        cleanup_pvcs(args.days, args.dry_run)
```

#### Layer 3: Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: code-index-mcp
  namespace: code-index-mcp
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: code-index-mcp
  minReplicas: 1  # Cannot scale to 0 in K8s HPA
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Note**: OpenShift HPA cannot scale to zero. For true zero scaling, consider:
- KEDA (Kubernetes Event-driven Autoscaling)
- Knative Serving

#### Layer 4: Resource Monitoring

```yaml
# Prometheus ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: code-index-mcp
  namespace: code-index-mcp
spec:
  selector:
    matchLabels:
      app: code-index-mcp
  endpoints:
  - port: metrics
    interval: 30s
```

## Deployment Process

### Prerequisites

```bash
# Required tools
oc version  # OpenShift CLI 4.12+
helm version  # Helm 3+

# Required permissions
oc login --token=YOUR_TOKEN --server=https://api.cluster.example.com:6443
oc whoami

# Create namespace
oc new-project code-index-mcp
```

### Deployment Script

```bash
#!/bin/bash
# deployment/openshift/deploy.sh

set -euo pipefail

NAMESPACE="${NAMESPACE:-code-index-mcp}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-image-registry.openshift-image-registry.svc:5000}"

# 1. Create namespace
oc new-project "$NAMESPACE" || oc project "$NAMESPACE"

# 2. Create ImageStream
oc create imagestream code-index-mcp -n "$NAMESPACE" || true

# 3. Build image (using S2I or Dockerfile)
oc new-build python:3.11~https://github.com/johnhuang316/code-index-mcp.git \
  --name=code-index-mcp \
  --namespace="$NAMESPACE" || true

# Or build locally and push
docker build -t code-index-mcp:latest .
docker tag code-index-mcp:latest "${IMAGE_REGISTRY}/${NAMESPACE}/code-index-mcp:latest"
docker login -u $(oc whoami) -p $(oc whoami -t) "$IMAGE_REGISTRY"
docker push "${IMAGE_REGISTRY}/${NAMESPACE}/code-index-mcp:latest"

# 4. Create ODF S3 storage
cat <<EOF | oc apply -f -
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: code-storage-bucket
  namespace: $NAMESPACE
spec:
  generateBucketName: code-index-storage
  storageClassName: openshift-storage.noobaa.io
EOF

# 5. Wait for bucket creation
oc wait --for=condition=Ready objectbucketclaim/code-storage-bucket -n "$NAMESPACE" --timeout=300s

# 6. Deploy application using Helm
helm upgrade --install code-index-mcp ./helm-chart \
  --namespace "$NAMESPACE" \
  --set image.repository="${IMAGE_REGISTRY}/${NAMESPACE}/code-index-mcp" \
  --set image.tag=latest \
  --set storage.type=s3 \
  --set storage.s3.bucketName="code-index-storage"

# 7. Create Route
oc expose service code-index-mcp -n "$NAMESPACE" || true
oc patch route code-index-mcp -n "$NAMESPACE" --type=merge -p '{"spec":{"tls":{"termination":"edge"}}}'

# 8. Create cleanup CronJob
oc apply -f deployment/openshift/cronjob-cleanup.yaml -n "$NAMESPACE"

echo "✅ OpenShift deployment complete!"
echo "Route URL: https://$(oc get route code-index-mcp -n $NAMESPACE -o jsonpath='{.spec.host}')"
```

### Helm Chart Structure

```
helm-chart/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── route.yaml
│   ├── cronjob-cleanup.yaml
│   ├── rbac.yaml
│   ├── networkpolicy.yaml
│   └── hpa.yaml
```

**values.yaml:**
```yaml
replicaCount: 2

image:
  repository: image-registry.openshift-image-registry.svc:5000/code-index-mcp/code-index-mcp
  tag: latest
  pullPolicy: Always

service:
  type: ClusterIP
  port: 80
  targetPort: 8080

route:
  enabled: true
  tls:
    termination: edge
  annotations:
    haproxy.router.openshift.io/rate-limit-connections: "true"
    haproxy.router.openshift.io/rate-limit-connections.concurrent-tcp: "100"

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 500m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

storage:
  type: s3  # or pvc
  s3:
    endpoint: ""  # Populated from secret
    bucketName: "code-index-storage"
  pvc:
    size: 50Gi
    storageClassName: ocs-storagecluster-cephfs

cleanup:
  enabled: true
  schedule: "0 2 * * *"
  retentionDays: 30
```

### Teardown Script

```bash
#!/bin/bash
# deployment/openshift/destroy.sh

set -euo pipefail

NAMESPACE="${NAMESPACE:-code-index-mcp}"

# 1. Delete Helm release
helm uninstall code-index-mcp -n "$NAMESPACE" || true

# 2. Delete Route
oc delete route code-index-mcp -n "$NAMESPACE" || true

# 3. Delete CronJobs
oc delete cronjob --all -n "$NAMESPACE" || true

# 4. Delete storage (optional, data will be lost!)
read -p "Delete all storage (OBC/PVCs)? (yes/no): " confirm
if [ "$confirm" = "yes" ]; then
  oc delete objectbucketclaim --all -n "$NAMESPACE"
  oc delete pvc --all -n "$NAMESPACE"
fi

# 5. Delete namespace
read -p "Delete namespace $NAMESPACE? (yes/no): " confirm_ns
if [ "$confirm_ns" = "yes" ]; then
  oc delete project "$NAMESPACE"
fi

echo "✅ Resources deleted"
```

## Cost Estimation

### On-Premise Hardware Costs

| Component | Specification | One-Time Cost |
|-----------|--------------|---------------|
| Compute Nodes (3) | 8 cores, 32GB RAM each | $9,000 |
| Storage (ODF) | 10TB SSD | $5,000 |
| GPU Node (optional) | NVIDIA A10 | $10,000 |
| Network | 10Gbps switches | $2,000 |
| **Total** | | **$26,000** |

**Amortized over 3 years**: ~$720/month

### OpenShift Licensing

| License Type | Annual Cost |
|-------------|-------------|
| OpenShift Platform Plus | $50,000/year (unlimited nodes) |
| **Monthly** | **$4,167/month** |

### Total Monthly Cost

**Option A: Managed OpenShift (ROSA, ARO)**
- ROSA/ARO cluster: ~$500/month (3 worker nodes)
- ODF storage: ~$100/month
- **Total: ~$600/month**

**Option B: Self-hosted OpenShift**
- Hardware amortization: $720/month
- OpenShift license: $4,167/month
- **Total: ~$4,887/month**

**Comparison to Cloud:**
- OpenShift (managed): ~$600/month (3x more expensive than Google Cloud)
- OpenShift (self-hosted): ~$4,887/month (22x more expensive!)
- Google Cloud Run: ~$220/month
- AWS Lambda: ~$2.50/month

**Note**: OpenShift is cost-effective only for:
- Large-scale deployments (100+ services)
- On-premise requirements
- Air-gapped environments
- Organizations with existing OpenShift infrastructure

## Multi-Project Workflow

### User Perspective

1. **Connect to OpenShift Route**
   ```json
   // Claude Desktop config
   {
     "mcpServers": {
       "code-index": {
         "url": "https://code-index-mcp-code-index-mcp.apps.cluster.example.com",
         "headers": {
           "Authorization": "Bearer YOUR_OPENSHIFT_TOKEN"
         }
       }
     }
   }
   ```

2. **Upload or sync code**
   ```
   User: "Upload my project from /local/path/to/project"
   MCP: Uploads to ODF S3 bucket or PVC
   ```

3. **Index and search**
   ```
   User: "Set project path to project_1"
   MCP: Loads from ODF/PVC, builds index
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
- ✅ On-premise deployment (no cloud dependency)
- ✅ Air-gap capable (all components self-hosted)
- ✅ Enterprise-grade security (RBAC, NetworkPolicy, SCC)
- ✅ Multi-tenancy with namespaces
- ✅ Kubernetes-native (portable to other K8s platforms)
- ✅ Built-in monitoring (Prometheus, Grafana)

### Negative
- ❌ Cannot scale to zero (minimum 1 replica with HPA)
- ❌ Higher cost than cloud (unless at scale)
- ❌ More complex setup than cloud services
- ❌ Requires OpenShift expertise
- ❌ Manual scaling configuration

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Cost overrun (self-hosted) | Use managed ROSA/ARO instead |
| Resource exhaustion | Resource quotas, LimitRanges |
| Security vulnerabilities | NetworkPolicy, SCC, regular scanning |
| Storage costs | CronJob cleanup, lifecycle policies |
| No auto-scale to zero | Consider KEDA or Knative |

## Implementation Checklist

- [ ] Add OpenShift-specific configuration to server.py
- [ ] Create Helm chart with all components
- [ ] Implement ODF S3 integration
- [ ] Add token-based authentication middleware
- [ ] Implement cleanup CronJob
- [ ] Write deployment script (deploy.sh)
- [ ] Write teardown script (destroy.sh)
- [ ] Configure RBAC and SecurityContextConstraints
- [ ] Set up NetworkPolicy
- [ ] Create monitoring dashboards
- [ ] Document user onboarding flow
- [ ] Update README with OpenShift instructions

## Related ADRs

- ADR 0001: MCP Transport Protocols and Cloud Deployment Architecture
- ADR 0002: Google Cloud Run HTTP Deployment (Phase 2A - reference implementation)
- ADR 0005: OpenShift Code Ingestion with Milvus (Phase 3C - dependent on this ADR)
- ADR 0006: AWS HTTP Deployment (Phase 2B - parallel future implementation)
- ADR 0008: Git-Sync Ingestion Strategy (applies to all cloud deployments)
- ADR 0009: Ansible Deployment Automation (deployment methodology)

## References

- [OpenShift Routes](https://docs.openshift.com/container-platform/latest/networking/routes/route-configuration.html)
- [OpenShift Data Foundation](https://docs.openshift.com/container-platform/latest/storage/persistent_storage/persistent-storage-ocs.html)
- [Kubernetes CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [OpenShift SecurityContextConstraints](https://docs.openshift.com/container-platform/latest/authentication/managing-security-context-constraints.html)
- [FastMCP HTTP Transport](https://github.com/jlowin/fastmcp)
