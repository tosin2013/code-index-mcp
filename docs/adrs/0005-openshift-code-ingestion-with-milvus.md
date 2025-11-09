# ADR 0005: OpenShift Code Ingestion with Milvus Vector Database

**Status**: Planning Document (Phase 3C - Future Enhancement)
**Date**: 2025-10-24
**Decision Maker**: Architecture Team
**Platform**: Red Hat OpenShift
**Related to**: ADR 0001, ADR 0003 (Google Cloud), ADR 0004 (AWS), ADR 0007 (OpenShift HTTP Deployment)
**Implementation Sequence**: Phase 3C (depends on ADR 0007 completion)

## Context

This ADR documents the **future implementation** of code ingestion for OpenShift (on-premise or cloud) deployments, using open-source vector database Milvus.

**Key Differences from Cloud Providers:**
- On-premise or self-managed infrastructure
- No vendor-specific embedding services
- Focus on open-source components
- Kubernetes-native architecture

**Note**: This is a **planning document** for Phase 3C (future implementation). It is not currently implemented.

**Prerequisites:**
- ✅ ADR 0001: MCP Transport Protocols (Complete)
- ⏳ ADR 0007: OpenShift HTTP Deployment with Auto-Cleanup (Planned - Phase 2C)
- This ADR builds upon ADR 0007 by adding semantic search capabilities using Milvus and vLLM

## Proposed Architecture

### OpenShift-Native Stack

```
┌──────────────────┐
│  OpenShift Pod   │
│   MCP Server     │
└────────┬─────────┘
         │
         ├─────────────────────────┐
         │                         │
         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐
│  OpenShift Data  │      │     Milvus       │
│  Foundation      │      │  Vector Database │
│  (Ceph/NooBaa)   │      │  - Embeddings    │
│  - S3 API        │      │  - Similarity    │
│  - Raw code      │      └────────┬─────────┘
│  - Archives      │               │
└──────────────────┘               │
         ┌─────────────────────────┘
         │
         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐
│   PostgreSQL     │      │      vLLM        │
│   (ODF Volumes)  │      │   Inference      │
│   - Metadata     │      │  - Embeddings    │
│   - User data    │      │  - GPU support   │
└──────────────────┘      └──────────────────┘
```

## Key Components

### 1. OpenShift Data Foundation (ODF)

**Why ODF:**
- Native OpenShift storage solution
- S3-compatible object storage via Ceph/NooBaa
- Multi-protocol support (S3, NFS, block storage)
- On-premise or cloud deployment
- Enterprise support from Red Hat

**Features:**
- Object storage (S3 API) for raw code and archives
- Block storage (RWO) for PostgreSQL
- File storage (RWX) for shared access if needed
- Built-in replication and high availability
- Seamless integration with OpenShift

**S3 Configuration:**
```yaml
# ObjectBucketClaim for S3 storage
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: code-storage-bucket
spec:
  generateBucketName: code-index-storage
  storageClassName: openshift-storage.noobaa.io
```

**Access Credentials:**
```bash
# ODF automatically creates secret with S3 credentials
oc get secret code-storage-bucket -o yaml

# Credentials:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - BUCKET_HOST (S3 endpoint)
# - BUCKET_NAME
```

### 2. Milvus Vector Database

**Why Milvus:**
- Open-source, cloud-agnostic
- Purpose-built for vector similarity search
- Kubernetes-native deployment
- High performance (GPU acceleration support)
- No vendor lock-in

**Features:**
- Multiple index types (IVF, HNSW, ANNOY, etc.)
- Horizontal scaling via sharding
- Query result caching
- Hybrid search (vector + scalar filtering)

**Deployment with ODF Storage:**
```yaml
# Helm chart installation using ODF for persistence
helm repo add milvus https://milvus-io.github.io/milvus-helm/
helm install milvus milvus/milvus \
  --set cluster.enabled=true \
  --set persistence.enabled=true \
  --set persistence.storageClass=ocs-storagecluster-ceph-rbd \
  --set persistence.size=100Gi
```

### 3. vLLM for Embedding Generation

**Why vLLM (Recommended for OpenShift):**
- Production-grade inference server
- Optimized for throughput and latency
- GPU acceleration with PagedAttention
- OpenAI-compatible API
- Better resource utilization than Ollama
- Continuous batching for high throughput

**Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-embeddings
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        args:
        - --model=intfloat/e5-mistral-7b-instruct  # High-quality embedding model
        - --served-model-name=embeddings
        - --dtype=half  # FP16 for efficiency
        - --max-model-len=4096
        env:
        - name: HUGGING_FACE_HUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: vllm-secrets
              key: hf-token
        ports:
        - containerPort: 8000
        resources:
          limits:
            nvidia.com/gpu: 1  # Requires GPU node
          requests:
            memory: 16Gi
            cpu: 4
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-embeddings
spec:
  selector:
    app: vllm-embeddings
  ports:
  - port: 8000
    targetPort: 8000
```

**Usage (OpenAI-compatible API):**
```python
import openai

# Point to vLLM service
openai.api_base = "http://vllm-embeddings:8000/v1"
openai.api_key = "not-needed"  # vLLM doesn't require key by default

# Generate embeddings
response = openai.Embedding.create(
    model="embeddings",
    input=code_text
)
embedding = response['data'][0]['embedding']
```

**Alternative Models for vLLM:**
```python
# Option 1: E5-Mistral (Best quality, requires GPU)
MODEL = "intfloat/e5-mistral-7b-instruct"  # 7B params, 4096 dimensions

# Option 2: BGE-Large (Good balance)
MODEL = "BAAI/bge-large-en-v1.5"  # 335M params, 1024 dimensions

# Option 3: E5-Base (Faster, smaller)
MODEL = "intfloat/e5-base-v2"  # 110M params, 768 dimensions
```

### Embedding Generation Options Comparison

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **vLLM** (Recommended) | ✅ Production-grade<br>✅ High throughput<br>✅ OpenAI API<br>✅ GPU optimized | ❌ Requires GPU<br>❌ More complex setup | **Best for production** |
| **Sentence Transformers** | ✅ Simple<br>✅ No service needed<br>✅ In-process | ❌ Slower<br>❌ Limited batching<br>❌ Model loaded per pod | Good for development |
| **Ollama** | ✅ Easy setup<br>✅ Multiple models | ❌ Less optimized<br>❌ Higher resource use | Not recommended (vLLM better) |
| **External API** | ✅ No GPU needed<br>✅ High quality | ❌ Costs money<br>❌ Data leaves cluster | Only if no GPU available |

**Recommendation:** Use **vLLM** for production OpenShift deployments with GPU nodes.

### 4. PostgreSQL for Metadata (Using ODF)

```yaml
# PostgreSQL StatefulSet with ODF storage
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgresql
spec:
  serviceName: postgresql
  replicas: 1
  template:
    spec:
      containers:
      - name: postgresql
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: codeindex
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: ocs-storagecluster-ceph-rbd  # ODF block storage
      resources:
        requests:
          storage: 20Gi
```

**Schema:**
```sql
-- Users and projects (same as cloud implementations)
CREATE TABLE users (...);
CREATE TABLE projects (...);

-- Code chunks (metadata only, vectors in Milvus)
CREATE TABLE code_chunks (
    chunk_id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(project_id),
    file_path TEXT NOT NULL,
    chunk_name VARCHAR(255),
    line_start INTEGER,
    line_end INTEGER,
    language VARCHAR(50),
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    milvus_id BIGINT UNIQUE,  -- Foreign key to Milvus
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5. MCP Server Pod

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: code-index-mcp
spec:
  replicas: 2  # For HA
  template:
    spec:
      containers:
      - name: mcp-server
        image: code-index-mcp:latest
        env:
        - name: MCP_TRANSPORT
          value: "http"
        - name: PORT
          value: "8080"
        - name: MILVUS_HOST
          value: "milvus-service"
        - name: POSTGRES_HOST
          value: "postgresql-service"
        - name: VLLM_HOST
          value: "vllm-embeddings"
        - name: VLLM_PORT
          value: "8000"
        - name: EMBEDDING_MODEL
          value: "vllm"  # or "local" or "openai"
        # ODF S3 credentials
        - name: S3_ENDPOINT
          valueFrom:
            secretKeyRef:
              name: code-storage-bucket
              key: BUCKET_HOST
        - name: S3_BUCKET
          valueFrom:
            secretKeyRef:
              name: code-storage-bucket
              key: BUCKET_NAME
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: code-storage-bucket
              key: AWS_ACCESS_KEY_ID
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: code-storage-bucket
              key: AWS_SECRET_ACCESS_KEY
        ports:
        - containerPort: 8080
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
```

## Milvus Integration

### Collection Schema

```python
from pymilvus import Collection, FieldSchema, CollectionSchema, DataType

# Define collection schema
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="project_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=50),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384)
]

schema = CollectionSchema(fields, description="Code embeddings")
collection = Collection(name="code_chunks", schema=schema)

# Create index for fast search
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 64}
}
collection.create_index(field_name="embedding", index_params=index_params)
```

### Insertion

```python
def insert_code_chunk(chunk: Dict) -> int:
    """Insert code chunk into Milvus and PostgreSQL"""
    # 1. Generate embedding
    embedding = generate_embedding(chunk['content'])

    # 2. Insert into Milvus
    entities = [
        [chunk['chunk_id']],
        [chunk['project_id']],
        [chunk['language']],
        [embedding]
    ]
    insert_result = collection.insert(entities)
    milvus_id = insert_result.primary_keys[0]

    # 3. Insert metadata into PostgreSQL
    db.execute(
        "INSERT INTO code_chunks (..., milvus_id) VALUES (..., %s)",
        (..., milvus_id)
    )

    return milvus_id
```

### Search

```python
def semantic_search(query: str, project_id: str, top_k: int = 10):
    """Semantic search using Milvus + PostgreSQL"""
    # 1. Generate query embedding
    query_embedding = generate_embedding(query)

    # 2. Vector search in Milvus
    search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
    results = collection.search(
        data=[query_embedding],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        expr=f'project_id == "{project_id}"'  # Filter by project
    )

    # 3. Get metadata from PostgreSQL
    milvus_ids = [hit.id for hit in results[0]]
    chunks = db.execute(
        "SELECT * FROM code_chunks WHERE milvus_id = ANY(%s)",
        (milvus_ids,)
    ).fetchall()

    return chunks
```

## Code Storage with ODF S3

### Python S3 Client (Boto3)

```python
import boto3
import os

# Initialize S3 client with ODF credentials
s3_client = boto3.client(
    's3',
    endpoint_url=f"https://{os.getenv('S3_ENDPOINT')}",
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    verify=True  # SSL verification
)

# Upload code archive
def upload_code_to_odf(user_id: str, project_name: str, local_path: str):
    """Upload code to ODF S3 bucket"""
    bucket = os.getenv('S3_BUCKET')
    s3_key = f"users/{user_id}/{project_name}/code.tar.gz"

    with open(local_path, 'rb') as f:
        s3_client.upload_fileobj(f, bucket, s3_key)

    return f"s3://{bucket}/{s3_key}"

# Download code from ODF
def download_code_from_odf(user_id: str, project_name: str, local_path: str):
    """Download code from ODF S3 bucket"""
    bucket = os.getenv('S3_BUCKET')
    s3_key = f"users/{user_id}/{project_name}/code.tar.gz"

    with open(local_path, 'wb') as f:
        s3_client.download_fileobj(bucket, s3_key, f)

    return local_path
```

## MCP Tool Implementation

```python
# In server.py

@mcp.tool()
def ingest_project_code_openshift(
    ctx: Context,
    project_name: str,
    s3_path: str = None,  # ODF S3 path
    git_url: str = None
) -> Dict[str, Any]:
    """Ingest code from ODF S3 or git into Milvus"""
    from pymilvus import Collection
    import boto3

    user_id = ctx.request_context.user_id

    # 1. Download code from ODF S3
    if s3_path:
        local_path = download_code_from_odf(user_id, project_name, "/tmp/code")
    elif git_url:
        local_path = clone_git_repo(git_url, "/tmp/code")
        # Upload to ODF for persistence
        upload_code_to_odf(user_id, project_name, local_path)

    # 2. Chunk code
    chunks = chunk_codebase(local_path)

    # 2. Connect to Milvus
    collection = Collection("code_chunks")

    # 3. Generate embeddings via vLLM and insert
    inserted = 0
    for chunk in chunks:
        embedding = generate_embedding_vllm(chunk['content'])

        # Insert into Milvus
        milvus_id = collection.insert([
            [str(chunk['chunk_id'])],
            [str(project_id)],
            [chunk['language']],
            [embedding]
        ]).primary_keys[0]

        # Insert metadata into PostgreSQL
        insert_chunk_metadata(chunk, milvus_id)
        inserted += 1

    collection.flush()

    return {
        "status": "success",
        "chunks_inserted": inserted
    }

def generate_embedding_vllm(text: str) -> List[float]:
    """Generate embedding using vLLM service"""
    import openai

    openai.api_base = f"http://{os.getenv('VLLM_HOST')}:{os.getenv('VLLM_PORT')}/v1"
    openai.api_key = "not-needed"

    response = openai.Embedding.create(
        model="embeddings",
        input=text
    )
    return response['data'][0]['embedding']

@mcp.tool()
def semantic_search_code_openshift(
    ctx: Context,
    query: str,
    project_name: str = None,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """Semantic search using Milvus + vLLM"""
    from pymilvus import Collection

    user_id = ctx.request_context.user_id

    # Generate query embedding via vLLM
    query_embedding = generate_embedding_vllm(query)

    # Search Milvus
    collection = Collection("code_chunks")
    collection.load()

    results = collection.search(
        data=[query_embedding],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": 64}},
        limit=top_k,
        expr=f'project_id == "{get_project_id(user_id, project_name)}"'
    )

    # Enrich with metadata from PostgreSQL
    return enrich_results_with_metadata(results)
```

## Deployment with Helm

### Helm Chart Structure

```
charts/code-index-mcp/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── deployment.yaml      # MCP server
    ├── service.yaml
    ├── route.yaml           # OpenShift Route
    ├── postgresql.yaml      # StatefulSet
    ├── milvus-standalone.yaml
    └── secrets.yaml
```

### values.yaml

```yaml
# Default values for code-index-mcp

replicaCount: 2

image:
  repository: quay.io/your-org/code-index-mcp
  tag: "latest"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8080

route:
  enabled: true
  host: code-index-mcp.apps.openshift.example.com
  tls:
    enabled: true
    termination: edge

# OpenShift Data Foundation storage
odf:
  enabled: true
  storageClass: ocs-storagecluster-ceph-rbd
  objectBucketClaim:
    enabled: true
    name: code-storage-bucket
    storageClass: openshift-storage.noobaa.io

# Milvus vector database
milvus:
  enabled: true
  standalone:
    resources:
      requests:
        memory: 4Gi
        cpu: 2
  persistence:
    enabled: true
    storageClass: ocs-storagecluster-ceph-rbd  # ODF block storage
    size: 100Gi

# PostgreSQL for metadata
postgresql:
  enabled: true
  persistence:
    enabled: true
    storageClass: ocs-storagecluster-ceph-rbd  # ODF block storage
    size: 20Gi
  auth:
    username: codeindex
    database: codeindex

# vLLM embedding service
vllm:
  enabled: true
  model: "intfloat/e5-mistral-7b-instruct"
  dtype: "half"  # FP16
  maxModelLen: 4096
  resources:
    requests:
      memory: 16Gi
      cpu: 4
      nvidia.com/gpu: 1
    limits:
      nvidia.com/gpu: 1
  nodeSelector:
    node.openshift.io/gpu: "true"  # Schedule on GPU nodes

# MCP server resources
resources:
  requests:
    memory: 2Gi
    cpu: 1
  limits:
    memory: 4Gi
    cpu: 2
```

### Installation

```bash
# Add Helm repo
helm repo add code-index-mcp https://charts.example.com/code-index-mcp

# Install
helm install code-index-mcp code-index-mcp/code-index-mcp \
  --namespace code-index \
  --create-namespace \
  --values custom-values.yaml

# Verify
oc get pods -n code-index
```

## Cost Estimation (On-Premise)

### Hardware Requirements

| Component | CPU | Memory | Storage | GPU | Quantity |
|-----------|-----|--------|---------|-----|----------|
| MCP Server Pods | 1-2 | 2-4 GB | - | - | 2 |
| vLLM Embeddings | 4 | 16 GB | - | 1 | 1 |
| Milvus Standalone | 2-4 | 4-8 GB | 100 GB (ODF) | - | 1 |
| PostgreSQL | 1-2 | 2-4 GB | 20 GB (ODF) | - | 1 |
| ODF Storage | - | - | 120 GB | - | - |
| **Total** | **10-14** | **26-34 GB** | **120 GB** | **1** | |

**Note:** Requires at least one GPU-enabled node for vLLM.

### Cloud Pricing (OpenShift Online)

| Resource | Monthly Cost |
|----------|--------------|
| OpenShift subscription (3 nodes) | ~$150/month |
| Persistent storage (120GB) | ~$12/month |
| **Total** | **~$162/month** |

**Cheaper than Google Cloud ($220), similar to AWS ($65-90).**

## Security Considerations

### OpenShift-Specific Security

```yaml
# SecurityContextConstraints
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: code-index-mcp-scc
allowPrivilegedContainer: false
runAsUser:
  type: MustRunAsRange
seLinuxContext:
  type: MustRunAs
fsGroup:
  type: MustRunAs
volumes:
- configMap
- secret
- persistentVolumeClaim
```

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: code-index-mcp-netpol
spec:
  podSelector:
    matchLabels:
      app: code-index-mcp
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: openshift-router
    ports:
    - port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: milvus
  - to:
    - podSelector:
        matchLabels:
          app: postgresql
```

## Comparison Matrix

| Feature | Google Cloud | AWS | OpenShift |
|---------|--------------|-----|-----------|
| **Vector DB** | AlloyDB pgvector | Aurora pgvector | Milvus |
| **Embeddings** | Vertex AI | Bedrock | vLLM |
| **Storage** | Cloud Storage | S3 | ODF S3 (Ceph) |
| **Cost/month** | ~$220 | ~$65 | ~$162 (cloud) / Variable (on-prem) |
| **Vendor Lock** | High | High | Low |
| **Privacy** | Medium | Medium | High |
| **Complexity** | Low | Medium | High |
| **GPU Required** | No | No | Yes (for vLLM) |

## Implementation Priority

This is a **Phase 3C future enhancement**. Implement after:

1. ✅ Phase 1: ADR 0001: Transport protocols (Complete)
2. ✅ Phase 2A: ADR 0002: Cloud Run HTTP deployment (Complete)
3. 🚧 Phase 3A: ADR 0003: Google Cloud semantic search (83% complete - infrastructure ready)
4. ⏳ Phase 2B: ADR 0006: AWS HTTP deployment (Planned)
5. ⏳ Phase 3B: ADR 0004: AWS semantic search (Planned)
6. ⏳ Phase 2C: ADR 0007: OpenShift HTTP deployment (Planned)
7. ⏳ **Phase 3C: ADR 0005: OpenShift semantic search** ← You are here

## Related ADRs

- ADR 0001: MCP Transport Protocols and Cloud Deployment Architecture
- ADR 0003: Google Cloud Code Ingestion with AlloyDB (Phase 3A - parallel implementation)
- ADR 0004: AWS Code Ingestion with Aurora and Bedrock (Phase 3B - future)
- ADR 0007: OpenShift HTTP Deployment with Automatic Resource Cleanup (Phase 2C - prerequisite)
- ADR 0008: Git-Sync Ingestion Strategy (applies to all cloud deployments)
- ADR 0009: Ansible Deployment Automation (deployment methodology)

## References

- [Milvus Documentation](https://milvus.io/docs)
- [OpenShift Helm Charts](https://docs.openshift.com/container-platform/latest/applications/working_with_helm_charts.html)
- [Sentence Transformers](https://www.sbert.net/)
- [Ollama](https://ollama.ai/)
- [PyMilvus SDK](https://milvus.io/api-reference/pymilvus/v2.3.x/About.md)
