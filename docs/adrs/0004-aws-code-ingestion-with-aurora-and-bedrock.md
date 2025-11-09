# ADR 0004: AWS Code Ingestion with Aurora PostgreSQL and Amazon Bedrock

**Status**: Planning Document (Phase 3B - Future Enhancement)
**Date**: 2025-10-24
**Decision Maker**: Architecture Team
**Cloud Platform**: Amazon Web Services (AWS)
**Related to**: ADR 0001, ADR 0003 (Google Cloud equivalent), ADR 0006 (AWS HTTP Deployment)
**Implementation Sequence**: Phase 3B (depends on ADR 0006 completion)

## Context

This ADR documents the **future implementation** of code ingestion for AWS deployments, paralleling the Google Cloud implementation (ADR 0003) but using AWS-native services.

**Note**: This is a **planning document** for Phase 3B (future implementation). It is not currently implemented.

**Prerequisites:**
- ✅ ADR 0001: MCP Transport Protocols (Complete)
- ⏳ ADR 0006: AWS HTTP Deployment with Auto-Cleanup (Planned - Phase 2B)
- This ADR builds upon ADR 0006 by adding semantic search capabilities to the HTTP-deployed MCP server

## Proposed Architecture

### AWS-Native Stack

```
┌──────────────────┐
│   Lambda/ECS     │
│   MCP Server     │
└────────┬─────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────────┐  ┌──────────────────┐
│       S3        │  │  Aurora          │
│  - Raw code     │  │  PostgreSQL      │
│  - Archives     │  │  - Code chunks   │
└─────────────────┘  │  - pgvector      │
                     │  - Metadata      │
                     └────────┬─────────┘
                              │
                              │ AWS SDK
                              ▼
                     ┌──────────────────┐
                     │ Amazon Bedrock   │
                     │ Titan Embeddings │
                     └──────────────────┘
```

## Key AWS Services

### 1. Aurora PostgreSQL with pgvector

**Why Aurora:**
- Compatible with PostgreSQL (pgvector extension support)
- Serverless v2 option (scales to zero)
- Automatic backups and point-in-time recovery
- Read replicas for scaling
- Lower cost than AlloyDB for smaller workloads

**Configuration:**
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Similar schema to Google Cloud implementation
CREATE TABLE code_chunks (
    chunk_id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(project_id),
    file_path TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- Bedrock Titan dimensions
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create vector index
CREATE INDEX code_chunks_embedding_idx ON code_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### 2. Amazon Bedrock for Embeddings

**Why Bedrock:**
- Managed service for foundation models
- Titan Embeddings G1 - Text model
- Pay-per-use pricing
- No infrastructure management

**Models:**
```python
# Titan Embeddings G1 - Text
MODEL_ID = "amazon.titan-embed-text-v1"
EMBEDDING_DIMENSIONS = 1536

# Alternative: Cohere Embed
# MODEL_ID = "cohere.embed-english-v3"
# EMBEDDING_DIMENSIONS = 1024
```

**Python SDK:**
```python
import boto3
import json

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def generate_embedding(text: str) -> List[float]:
    """Generate embedding using Amazon Bedrock"""
    body = json.dumps({"inputText": text})

    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v1",
        body=body
    )

    response_body = json.loads(response['body'].read())
    return response_body['embedding']
```

### 3. S3 for Code Storage

**Bucket structure:**
```
s3://project-code-storage/
├── users/
│   ├── user_abc123/
│   │   ├── project_1/
│   │   └── project_2/
│   └── user_xyz789/
│       └── project_1/
```

**Lifecycle policies:**
```json
{
  "Rules": [
    {
      "Id": "Archive old code",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    }
  ]
}
```

### 4. Lambda or ECS for MCP Server

**Option A: Lambda (Serverless)**
- Pay per request
- Auto-scaling
- 15-minute timeout limit (may be too short for large indexing)

**Option B: ECS Fargate**
- Longer running tasks
- More control over resources
- Better for continuous services

**Recommendation:** Start with Lambda, migrate to ECS if needed.

## Schema Design

### Embedding Generation Function

```python
# AWS Lambda function for embedding generation
import boto3
import psycopg2
import json

def lambda_handler(event, context):
    """Generate embeddings for code chunks"""
    bedrock = boto3.client('bedrock-runtime')
    db = psycopg2.connect(os.environ['AURORA_ENDPOINT'])

    # Get chunks without embeddings
    cursor = db.cursor()
    cursor.execute("""
        SELECT chunk_id, content
        FROM code_chunks
        WHERE embedding IS NULL
        LIMIT 100
    """)

    for chunk_id, content in cursor:
        # Generate embedding
        embedding = generate_embedding_bedrock(content, bedrock)

        # Update chunk
        cursor.execute(
            "UPDATE code_chunks SET embedding = %s WHERE chunk_id = %s",
            (embedding, chunk_id)
        )

    db.commit()
    return {"statusCode": 200, "chunksProcessed": cursor.rowcount}
```

### MCP Tool Integration

```python
# Similar to Google Cloud implementation but using AWS SDK

@mcp.tool()
def ingest_project_code_aws(
    ctx: Context,
    project_name: str,
    s3_path: str = None,
    git_url: str = None
) -> Dict[str, Any]:
    """Ingest code using AWS services"""
    import boto3

    s3 = boto3.client('s3')
    rds_data = boto3.client('rds-data')

    # Download from S3
    # Chunk code
    # Generate embeddings via Bedrock
    # Store in Aurora

    pass

@mcp.tool()
def semantic_search_code_aws(
    ctx: Context,
    query: str,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """Semantic search using Aurora + Bedrock"""
    import boto3

    bedrock = boto3.client('bedrock-runtime')

    # Generate query embedding
    query_embedding = generate_embedding(query)

    # Search Aurora using pgvector
    # Return results

    pass
```

## Cost Estimation (AWS)

### Aurora Serverless v2

| Resource | Configuration | Monthly Cost |
|----------|--------------|--------------|
| Aurora Serverless v2 | 0.5-1 ACU (scales to zero) | ~$45-90/month |
| Storage | 100 GB | ~$10/month |
| **Total** | | **~$60/month** |

**Significantly cheaper than AlloyDB for small/medium workloads!**

### Bedrock Embeddings

| Model | Cost per 1M tokens |
|-------|-------------------|
| Titan Embeddings G1 | $0.10 |

**Example:** 100k LOC ≈ 5M characters ≈ $0.50 one-time

### S3 Storage

| Resource | Size | Monthly Cost |
|----------|------|--------------|
| S3 Standard | 10 GB | $0.23 |
| S3 Glacier (archived) | 90 GB | $0.36 |

### Total Monthly Cost (AWS)

- Aurora: $60
- S3: $1
- Bedrock (incremental): $1-5
- **Total: ~$65/month**

**3x cheaper than Google Cloud ($220/month)** for equivalent workload!

## Deployment Process

### Prerequisites

```bash
# AWS CLI
aws --version

# Configure credentials
aws configure

# Required permissions
aws iam get-user
```

### Infrastructure as Code (Terraform)

```hcl
# terraform/aws/main.tf

# Aurora PostgreSQL cluster
resource "aws_rds_cluster" "aurora" {
  cluster_identifier      = "code-index-aurora"
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned"
  engine_version          = "15.3"
  database_name           = "codeindex"
  master_username         = "admin"
  master_password         = var.db_password

  serverlessv2_scaling_configuration {
    max_capacity = 1.0
    min_capacity = 0.5
  }

  skip_final_snapshot = true
}

# S3 bucket for code storage
resource "aws_s3_bucket" "code_storage" {
  bucket = "${var.project_name}-code-storage"
}

# Lambda function for MCP server
resource "aws_lambda_function" "mcp_server" {
  function_name = "code-index-mcp"
  runtime       = "python3.11"
  handler       = "server.lambda_handler"
  role          = aws_iam_role.lambda_role.arn

  environment {
    variables = {
      MCP_TRANSPORT    = "http"
      AURORA_ENDPOINT  = aws_rds_cluster.aurora.endpoint
      S3_BUCKET        = aws_s3_bucket.code_storage.id
    }
  }
}
```

### Deployment Script

```bash
#!/bin/bash
# deployment/aws/deploy.sh

set -euo pipefail

# 1. Deploy infrastructure
cd terraform/aws
terraform init
terraform apply

# 2. Enable pgvector in Aurora
psql -h $AURORA_ENDPOINT -U admin -d codeindex \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. Create schema
psql -h $AURORA_ENDPOINT -U admin -d codeindex \
  -f schema/aurora-schema.sql

# 4. Deploy Lambda
aws lambda update-function-code \
  --function-name code-index-mcp \
  --zip-file fileb://lambda-package.zip

echo "✅ AWS deployment complete!"
```

## Security Considerations

### IAM Policies

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::project-code-storage/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement"
      ],
      "Resource": "arn:aws:rds:*:*:cluster:code-index-aurora"
    }
  ]
}
```

### Secrets Management

```bash
# Store secrets in AWS Secrets Manager
aws secretsmanager create-secret \
  --name code-index-mcp/api-keys \
  --secret-string '{"api_key_1": "sk-abc123..."}'

# Lambda retrieves at runtime
import boto3
secrets = boto3.client('secretsmanager')
api_keys = secrets.get_secret_value(SecretId='code-index-mcp/api-keys')
```

## Comparison: AWS vs Google Cloud

| Feature | AWS | Google Cloud |
|---------|-----|--------------|
| **Compute** | Lambda/ECS | Cloud Run |
| **Database** | Aurora PostgreSQL | AlloyDB |
| **Embeddings** | Bedrock Titan | Vertex AI |
| **Storage** | S3 | Cloud Storage |
| **Monthly Cost** | ~$65 | ~$220 |
| **Scaling** | Serverless v2 | Auto-scale |
| **Integration** | AWS SDK | google_ml_integration |

**Winner for cost**: AWS (3x cheaper)
**Winner for integration**: Google Cloud (tighter integration)

## Implementation Priority

This is a **Phase 3B future enhancement**. Implement after:

1. ✅ Phase 1: ADR 0001: Transport protocols (Complete)
2. ✅ Phase 2A: ADR 0002: Cloud Run HTTP deployment (Complete)
3. 🚧 Phase 3A: ADR 0003: Google Cloud semantic search (83% complete - infrastructure ready)
4. ⏳ Phase 2B: ADR 0006: AWS HTTP deployment (Planned)
5. ⏳ **Phase 3B: ADR 0004: AWS semantic search** ← You are here
6. ⏳ Phase 2C: ADR 0007: OpenShift HTTP deployment (Planned)
7. ⏳ Phase 3C: ADR 0005: OpenShift semantic search (Planned)

## Related ADRs

- ADR 0001: MCP Transport Protocols and Cloud Deployment Architecture
- ADR 0003: Google Cloud Code Ingestion with AlloyDB (Phase 3A - parallel implementation)
- ADR 0005: OpenShift Code Ingestion with Milvus (Phase 3C - future)
- ADR 0006: AWS HTTP Deployment with Automatic Resource Cleanup (Phase 2B - prerequisite)
- ADR 0008: Git-Sync Ingestion Strategy (applies to all cloud deployments)

## References

- [Aurora PostgreSQL with pgvector](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.Extensions.html)
- [Amazon Bedrock Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [AWS Lambda with Python](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
