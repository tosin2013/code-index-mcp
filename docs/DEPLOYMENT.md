# Code Index MCP - Cloud Deployment Guide

This guide provides practical deployment instructions for running code-index-mcp in production cloud environments.

## Table of Contents

- [Deployment Overview](#deployment-overview)
- [Prerequisites](#prerequisites)
- [Google Cloud Deployment](#google-cloud-deployment)
- [AWS Deployment](#aws-deployment)
- [OpenShift Deployment](#openshift-deployment)
- [Security Configuration](#security-configuration)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Troubleshooting](#troubleshooting)

## Deployment Overview

Code Index MCP supports **two deployment modes**:

### Local Mode (stdio transport)
```bash
# Run locally on your machine
uvx code-index-mcp
```
✅ **Best for**: Individual developers, local development
✅ **No cloud costs**, direct filesystem access, zero deployment complexity

### Cloud Mode (HTTP/SSE transport)
```bash
# Deploy to cloud with HTTP endpoint
MCP_TRANSPORT=http code-index-mcp
```
✅ **Best for**: Teams, organizations, multi-user environments
✅ **Features**: Auto-scaling, multi-user support, automatic resource cleanup

## Prerequisites

### All Platforms

1. **Python 3.11+**
   ```bash
   python --version  # Should be 3.11 or higher
   ```

2. **Git**
   ```bash
   git --version
   ```

3. **Docker** (for container builds)
   ```bash
   docker --version
   ```

### Platform-Specific CLIs

#### Google Cloud
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

#### AWS
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Configure credentials
aws configure
```

#### OpenShift
```bash
# Install oc CLI
# Download from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/

# Login to cluster
oc login --token=YOUR_TOKEN --server=https://api.cluster.example.com:6443
```

## Google Cloud Deployment

**Architecture**: Cloud Run + AlloyDB + Vertex AI + Cloud Storage

**Estimated Cost**: ~$220/month for production workload, scales to $0 when idle

### Quick Start

1. **Set environment variables**
   ```bash
   export GCP_PROJECT_ID="your-project-id"
   export GCP_REGION="us-central1"
   ```

2. **Enable required APIs**
   ```bash
   gcloud services enable \
     run.googleapis.com \
     storage.googleapis.com \
     secretmanager.googleapis.com \
     scheduler.googleapis.com \
     alloydb.googleapis.com \
     aiplatform.googleapis.com
   ```

3. **Create storage buckets**
   ```bash
   gsutil mb -p "$GCP_PROJECT_ID" -l "$GCP_REGION" "gs://${GCP_PROJECT_ID}-code-storage"
   gsutil mb -p "$GCP_PROJECT_ID" -l "$GCP_REGION" "gs://${GCP_PROJECT_ID}-indexes"
   ```

4. **Set lifecycle policies**
   ```bash
   cat > lifecycle.json <<EOF
   {
     "lifecycle": {
       "rule": [
         {
           "action": {"type": "Delete"},
           "condition": {
             "age": 90,
             "matchesPrefix": ["users/"]
           }
         },
         {
           "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
           "condition": {
             "age": 30,
             "matchesStorageClass": ["STANDARD"]
           }
         }
       ]
     }
   }
   EOF

   gsutil lifecycle set lifecycle.json "gs://${GCP_PROJECT_ID}-code-storage"
   ```

5. **Deploy to Cloud Run**
   ```bash
   gcloud run deploy code-index-mcp \
     --source . \
     --region "$GCP_REGION" \
     --platform managed \
     --allow-unauthenticated \
     --set-env-vars "MCP_TRANSPORT=http,GCP_PROJECT=$GCP_PROJECT_ID" \
     --min-instances 0 \
     --max-instances 10 \
     --memory 2Gi \
     --cpu 2 \
     --timeout 3600
   ```

6. **Create API keys for users**
   ```bash
   # Generate API key
   API_KEY=$(openssl rand -base64 32)

   # Store in Secret Manager
   echo -n "$API_KEY" | gcloud secrets create mcp-api-key-user1 --data-file=-

   # Grant Cloud Run access
   gcloud secrets add-iam-policy-binding mcp-api-key-user1 \
     --member="serviceAccount:${GCP_PROJECT_ID}@appspot.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"

   # Share API key with user securely
   echo "User API Key: $API_KEY"
   ```

7. **Set up automatic cleanup**
   ```bash
   # Create Cloud Scheduler job for daily cleanup
   SERVICE_URL=$(gcloud run services describe code-index-mcp \
     --region="$GCP_REGION" \
     --format='value(status.url)')

   gcloud scheduler jobs create http code-index-mcp-cleanup \
     --schedule="0 2 * * *" \
     --uri="${SERVICE_URL}/admin/cleanup" \
     --http-method=POST \
     --oidc-service-account-email="${GCP_PROJECT_ID}@appspot.gserviceaccount.com"
   ```

### User Configuration (Claude Desktop)

Users connect to your deployed service:

```json
{
  "mcpServers": {
    "code-index": {
      "url": "https://code-index-mcp-xyz123.run.app",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

### Teardown

```bash
# Delete Cloud Run service
gcloud run services delete code-index-mcp --region="$GCP_REGION" --quiet

# Delete scheduler job
gcloud scheduler jobs delete code-index-mcp-cleanup --quiet

# Delete storage buckets (WARNING: data will be lost!)
gsutil -m rm -r "gs://${GCP_PROJECT_ID}-code-storage"
gsutil -m rm -r "gs://${GCP_PROJECT_ID}-indexes"

# Delete secrets
gcloud secrets delete mcp-api-key-user1 --quiet
```

## AWS Deployment

**Architecture**: Lambda/ECS + Aurora PostgreSQL + Amazon Bedrock + S3

**Estimated Cost**: ~$65/month for production workload (3x cheaper than Google Cloud)

**Status**: 🚧 Future enhancement - see [ADR 0004](adrs/0004-aws-code-ingestion-with-aurora-and-bedrock.md)

### Quick Start

1. **Set environment variables**
   ```bash
   export AWS_REGION="us-east-1"
   export PROJECT_NAME="code-index-mcp"
   ```

2. **Create S3 buckets**
   ```bash
   aws s3 mb "s3://${PROJECT_NAME}-code-storage" --region "$AWS_REGION"
   aws s3 mb "s3://${PROJECT_NAME}-indexes" --region "$AWS_REGION"
   ```

3. **Deploy Aurora PostgreSQL cluster**
   ```bash
   aws rds create-db-cluster \
     --db-cluster-identifier code-index-aurora \
     --engine aurora-postgresql \
     --engine-mode provisioned \
     --engine-version 15.3 \
     --database-name codeindex \
     --master-username admin \
     --master-user-password "YOUR_SECURE_PASSWORD" \
     --serverless-v2-scaling-configuration MinCapacity=0.5,MaxCapacity=1.0
   ```

4. **Enable pgvector extension**
   ```bash
   psql -h YOUR_AURORA_ENDPOINT -U admin -d codeindex \
     -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

5. **Deploy Lambda or ECS**
   ```bash
   # Option A: Lambda (for lightweight usage)
   aws lambda create-function \
     --function-name code-index-mcp \
     --runtime python3.11 \
     --handler server.lambda_handler \
     --environment Variables="{MCP_TRANSPORT=http,AURORA_ENDPOINT=YOUR_ENDPOINT}" \
     --memory-size 2048 \
     --timeout 900

   # Option B: ECS Fargate (for continuous service)
   # TODO: Add ECS deployment commands
   ```

6. **Configure API Gateway** (for Lambda)
   ```bash
   aws apigatewayv2 create-api \
     --name code-index-mcp \
     --protocol-type HTTP \
     --target "arn:aws:lambda:${AWS_REGION}:ACCOUNT_ID:function:code-index-mcp"
   ```

### User Configuration

```json
{
  "mcpServers": {
    "code-index": {
      "url": "https://api-id.execute-api.us-east-1.amazonaws.com",
      "headers": {
        "x-api-key": "YOUR_AWS_API_KEY"
      }
    }
  }
}
```

## OpenShift Deployment

**Architecture**: OpenShift Pod + Milvus + vLLM + OpenShift Data Foundation (ODF)

**Best for**: On-premise deployments, air-gapped environments, organizations with existing OpenShift

**Status**: 🚧 Future enhancement - see [ADR 0005](adrs/0005-openshift-code-ingestion-with-milvus.md)

### Prerequisites

- OpenShift 4.12+
- OpenShift Data Foundation operator installed
- GPU node pool (for vLLM embeddings)

### Quick Start

1. **Create namespace**
   ```bash
   oc new-project code-index-mcp
   ```

2. **Install Milvus operator**
   ```bash
   oc apply -f https://github.com/milvus-io/milvus-operator/releases/download/v1.0.0/milvus-operator.yaml
   ```

3. **Deploy Milvus cluster**
   ```yaml
   cat <<EOF | oc apply -f -
   apiVersion: milvus.io/v1beta1
   kind: Milvus
   metadata:
     name: code-index-milvus
     namespace: code-index-mcp
   spec:
     mode: cluster
     dependencies:
       storage:
         type: S3
         endpoint: s3.openshift-storage.svc:443
         useSSL: true
         inClusterConfig:
           enabled: true
   EOF
   ```

4. **Create S3 storage using ODF**
   ```yaml
   cat <<EOF | oc apply -f -
   apiVersion: objectbucket.io/v1alpha1
   kind: ObjectBucketClaim
   metadata:
     name: code-storage-bucket
     namespace: code-index-mcp
   spec:
     generateBucketName: code-index-storage
     storageClassName: openshift-storage.noobaa.io
   EOF
   ```

5. **Deploy vLLM inference service**
   ```yaml
   cat <<EOF | oc apply -f -
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: vllm-embeddings
     namespace: code-index-mcp
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: vllm-embeddings
     template:
       metadata:
         labels:
           app: vllm-embeddings
       spec:
         nodeSelector:
           nvidia.com/gpu.present: "true"
         containers:
         - name: vllm
           image: vllm/vllm-openai:latest
           args:
           - --model=intfloat/e5-mistral-7b-instruct
           - --dtype=half
           - --max-model-len=4096
           resources:
             limits:
               nvidia.com/gpu: 1
               memory: 16Gi
             requests:
               memory: 16Gi
           ports:
           - containerPort: 8000
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: vllm-embeddings
     namespace: code-index-mcp
   spec:
     selector:
       app: vllm-embeddings
     ports:
     - port: 8000
       targetPort: 8000
   EOF
   ```

6. **Deploy MCP server**
   ```yaml
   cat <<EOF | oc apply -f -
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: code-index-mcp
     namespace: code-index-mcp
   spec:
     replicas: 2
     selector:
       matchLabels:
         app: code-index-mcp
     template:
       metadata:
         labels:
           app: code-index-mcp
       spec:
         containers:
         - name: mcp-server
           image: code-index-mcp:latest
           env:
           - name: MCP_TRANSPORT
             value: "http"
           - name: MILVUS_HOST
             value: "code-index-milvus"
           - name: MILVUS_PORT
             value: "19530"
           - name: VLLM_HOST
             value: "vllm-embeddings"
           - name: VLLM_PORT
             value: "8000"
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
           ports:
           - containerPort: 8080
   ---
   apiVersion: v1
   kind: Service
   metadata:
     name: code-index-mcp
     namespace: code-index-mcp
   spec:
     selector:
       app: code-index-mcp
     ports:
     - port: 80
       targetPort: 8080
   ---
   apiVersion: route.openshift.io/v1
   kind: Route
   metadata:
     name: code-index-mcp
     namespace: code-index-mcp
   spec:
     to:
       kind: Service
       name: code-index-mcp
     tls:
       termination: edge
   EOF
   ```

7. **Get the route URL**
   ```bash
   oc get route code-index-mcp -o jsonpath='{.spec.host}'
   ```

### User Configuration

```json
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

## Security Configuration

### API Key Management

**Never commit API keys to git!** The `.gitignore` is configured to exclude:
- `*.key`, `*.pem`, `*.p12`
- `gcloud-*.json`, `service-account-*.json`
- `.env`, `.env.*`
- `secrets/`

### Best Practices

1. **Use Secret Management**
   - Google Cloud: Secret Manager
   - AWS: AWS Secrets Manager
   - OpenShift: Sealed Secrets or External Secrets Operator

2. **Enable Authentication**
   ```python
   # In server.py
   from fastapi import HTTPException, Header

   async def verify_api_key(authorization: str = Header(...)):
       if not authorization.startswith("Bearer "):
           raise HTTPException(status_code=401)

       api_key = authorization.replace("Bearer ", "")
       # Validate against Secret Manager
       if not is_valid_api_key(api_key):
           raise HTTPException(status_code=403)
   ```

3. **Use Workload Identity** (Google Cloud)
   ```bash
   # No need for service account keys
   gcloud iam service-accounts add-iam-policy-binding \
     YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com \
     --role roles/iam.workloadIdentityUser \
     --member "serviceAccount:YOUR_PROJECT.svc.id.goog[NAMESPACE/KSA_NAME]"
   ```

4. **Enable HTTPS Only**
   - Cloud Run: Automatic HTTPS
   - API Gateway: Enforce HTTPS
   - OpenShift: TLS edge termination

### Network Security

```yaml
# OpenShift NetworkPolicy example
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: code-index-mcp
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
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: vllm-embeddings
  - to:
    - podSelector:
        matchLabels:
          app: code-index-milvus
```

## Monitoring and Maintenance

### Health Checks

All deployments should implement health check endpoints:

```python
@mcp.tool()
def health_check() -> Dict[str, Any]:
    """Health check endpoint for load balancers"""
    return {
        "status": "healthy",
        "version": "2.4.1",
        "transport": os.getenv("MCP_TRANSPORT", "stdio"),
        "timestamp": datetime.now().isoformat()
    }
```

### Logging

**Google Cloud:**
```bash
# View logs
gcloud run services logs read code-index-mcp --region="$GCP_REGION" --limit=50
```

**AWS:**
```bash
# View Lambda logs
aws logs tail /aws/lambda/code-index-mcp --follow
```

**OpenShift:**
```bash
# View pod logs
oc logs -f deployment/code-index-mcp -n code-index-mcp
```

### Cost Monitoring

**Google Cloud:**
```bash
# Create budget alert
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="MCP Server Monthly Budget" \
  --budget-amount=100USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90
```

**AWS:**
```bash
# Create budget
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

## Troubleshooting

### Common Issues

#### 1. Cold Start Latency

**Symptom**: First request takes 10-30 seconds

**Solution**:
```bash
# Google Cloud: Set min instances
gcloud run services update code-index-mcp \
  --min-instances 1 \
  --region "$GCP_REGION"
```

#### 2. Out of Memory Errors

**Symptom**: Container crashes with OOM

**Solution**:
```bash
# Increase memory allocation
gcloud run services update code-index-mcp \
  --memory 4Gi \
  --region "$GCP_REGION"
```

#### 3. Timeout Errors

**Symptom**: Large indexing operations fail

**Solution**:
```bash
# Increase timeout
gcloud run services update code-index-mcp \
  --timeout 3600 \
  --region "$GCP_REGION"
```

#### 4. Authentication Failures

**Symptom**: 401/403 errors

**Check**:
```bash
# Verify API key in Secret Manager
gcloud secrets versions access latest --secret="mcp-api-key-user1"

# Check IAM permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID
```

#### 5. Storage Access Issues

**Symptom**: Cannot read/write to storage

**Check**:
```bash
# Google Cloud: Verify service account permissions
gsutil iam get "gs://${GCP_PROJECT_ID}-code-storage"

# AWS: Check IAM role
aws iam get-role --role-name lambda-execution-role
```

### Debug Mode

Enable verbose logging:

```bash
# Set environment variable
gcloud run services update code-index-mcp \
  --update-env-vars "LOG_LEVEL=DEBUG" \
  --region "$GCP_REGION"
```

### Performance Tuning

1. **Index Optimization**
   - Use shallow index for file discovery
   - Build deep index only when needed
   - Enable file watcher for auto-refresh

2. **Database Tuning**
   - AlloyDB: Adjust HNSW index parameters (m=16, ef_construction=64)
   - Aurora: Use read replicas for search queries
   - Milvus: Tune nlist and nprobe parameters

3. **Caching**
   - Enable Redis for frequent queries
   - Cache embeddings to reduce API calls
   - Use CDN for static resources

## Additional Resources

- [ADR 0001: MCP Transport Protocols](adrs/0001-mcp-stdio-protocol-cloud-deployment-constraints.md)
- [ADR 0002: Cloud Run Deployment](adrs/0002-cloud-run-http-deployment-with-auto-cleanup.md)
- [ADR 0003: Google Cloud Ingestion](adrs/0003-google-cloud-code-ingestion-with-alloydb.md)
- [ADR 0004: AWS Deployment Strategy](adrs/0004-aws-code-ingestion-with-aurora-and-bedrock.md)
- [ADR 0005: OpenShift Deployment](adrs/0005-openshift-code-ingestion-with-milvus.md)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)

## Support

For issues and questions:
- GitHub Issues: https://github.com/YOUR_ORG/code-index-mcp/issues
- Documentation: https://github.com/YOUR_ORG/code-index-mcp/tree/master/docs
