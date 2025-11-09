# ADR 0006: AWS HTTP Deployment with Automatic Resource Cleanup

**Status**: Planning Document (Phase 2B - Future Enhancement)
**Date**: 2025-10-24
**Decision Maker**: Architecture Team
**Related to**: ADR 0001 (HTTP/SSE Transport), ADR 0002 (Google Cloud equivalent), ADR 0004 (AWS Code Ingestion)
**Implementation Sequence**: Phase 2B (after Phase 2A completion, enables Phase 3B)

## Context

With MCP's HTTP/SSE transport support, we can deploy code-index-mcp to AWS as a standard cloud service. This ADR addresses AWS-specific HTTP deployment concerns parallel to ADR 0002 (Google Cloud Run).

**Note**: This is a **planning document** for Phase 2B (future implementation). It is not currently implemented.

**Prerequisites:**
- ✅ ADR 0001: MCP Transport Protocols (Complete)
- ✅ ADR 0002: Cloud Run HTTP Deployment (Complete - Phase 2A reference implementation)
- This ADR enables ADR 0004 (AWS semantic search with Aurora and Bedrock)

### User Requirements

1. **"How can users use this in AWS deployments?"**
   - Users connect to HTTPS endpoint (API Gateway or ALB)
   - Upload code via API or sync from git repositories

2. **"Will it be secure?"**
   - HTTPS encryption, API key authentication
   - IAM-based access control
   - See security section below

3. **"How does multi-project support work?"**
   - Per-user project namespaces in S3
   - Isolated storage and indexes
   - See multi-project section below

4. **"How to delete AWS services? Automation?"**
   - Automated cleanup via EventBridge
   - Resource TTLs and idle detection
   - See cleanup section below

5. **"How to protect AWS credentials in git?"**
   - Never commit credentials
   - Use AWS Secrets Manager + IAM roles
   - See security section below

## Decision: Lambda or ECS with HTTP Transport

Deploy code-index-mcp to AWS using either Lambda (serverless) or ECS Fargate (containerized) with HTTP/SSE transport and automatic resource management.

## Architecture

### Deployment Model Options

#### Option A: Lambda + API Gateway (Recommended for Light Usage)

```
┌─────────────┐                           ┌──────────────────┐
│   Claude    │   HTTPS (authenticated)   │  API Gateway     │
│   Desktop   │──────────────────────────►│  + Lambda        │
│             │                           │  (Auto-scaling)  │
│             │◄──────────────────────────│                  │
│             │   Response                └────────┬─────────┘
└─────────────┘                                    │
                                          ┌────────▼─────────┐
                                          │       S3         │
                                          │  - User code     │
                                          │  - Indexes       │
                                          │  - Cache         │
                                          └──────────────────┘
```

**Pros:**
- True serverless (pay per request)
- Zero idle costs
- Automatic scaling

**Cons:**
- 15-minute timeout limit
- Cold start latency (~1-3s)
- 10GB memory limit

#### Option B: ECS Fargate + ALB (Recommended for Heavy Usage)

```
┌─────────────┐                           ┌──────────────────┐
│   Claude    │   HTTPS (authenticated)   │  ALB + ECS       │
│   Desktop   │──────────────────────────►│  Fargate         │
│             │                           │  (Containers)    │
│             │◄──────────────────────────│                  │
│             │   Response                └────────┬─────────┘
└─────────────┘                                    │
                                          ┌────────▼─────────┐
                                          │       S3         │
                                          │  - User code     │
                                          │  - Indexes       │
                                          │  - Cache         │
                                          └──────────────────┘
```

**Pros:**
- Longer running tasks (no 15-min limit)
- Better for continuous services
- More control over resources

**Cons:**
- Minimum 0.25 vCPU always running (~$10/month)
- Slightly higher cost than Lambda for light usage

**Recommendation**: Start with Lambda, migrate to ECS if timeout issues occur.

### Components

1. **Lambda Function** (Option A)
   - Runtime: Python 3.11
   - Memory: 2GB (configurable up to 10GB)
   - Timeout: 900s (15 minutes max)
   - Environment: MCP_TRANSPORT=http
   - Concurrency: Provisioned or on-demand

2. **ECS Fargate Service** (Option B)
   - CPU: 2 vCPU
   - Memory: 4GB
   - Min tasks: 0 (with Application Auto Scaling)
   - Max tasks: 10
   - Health checks: /health endpoint

3. **API Gateway / Application Load Balancer**
   - REST API (Lambda) or HTTP API (ECS)
   - Custom domain with ACM certificate
   - API key authentication
   - Request/response logging

4. **S3 Buckets**
   - `{account-id}-code-index-code-storage`: User-uploaded code
   - `{account-id}-code-index-indexes`: Generated indexes and caches
   - Lifecycle rules: Delete after 30 days of inactivity

5. **EventBridge Rules** (Cleanup Automation)
   - Daily schedule: Delete inactive projects
   - Weekly schedule: Cleanup old indexes
   - Monthly schedule: Cost analysis and reporting

6. **AWS Secrets Manager**
   - API keys for user authentication
   - Git credentials (if syncing from private repos)
   - No secrets in environment variables

## Security Architecture

### Authentication Flow

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ 1. Request with API key
       ▼
┌──────────────┐
│  API Gateway │
│  (API Key    │
│   Validation)│
└──────┬───────┘
       │ 2. Validate API key
       │    (Secrets Manager)
       ▼
┌──────────────┐
│  Lambda/ECS  │
│  MCP Server  │
└──────────────┘
```

### Credential Management

**CRITICAL: Never commit credentials to git!**

```bash
# .gitignore (already configured)
*.key
*.pem
aws-credentials.json
.aws/credentials
secrets/
deployment/**/*.key
```

**Proper Approach:**

1. **API Keys**: Store in Secrets Manager
   ```bash
   # Create secret
   aws secretsmanager create-secret \
     --name code-index-mcp/api-keys \
     --secret-string '{"user1":"sk-abc123..."}'

   # Grant Lambda access
   aws lambda add-permission \
     --function-name code-index-mcp \
     --statement-id AllowSecretsAccess \
     --action lambda:InvokeFunction \
     --principal secretsmanager.amazonaws.com
   ```

2. **IAM Roles**: Use execution roles, not access keys
   ```bash
   # Lambda uses execution role
   # No need to download/commit access keys
   aws iam create-role \
     --role-name lambda-code-index-execution \
     --assume-role-policy-document file://trust-policy.json
   ```

3. **User Authentication**: Generate API keys via admin tool
   ```bash
   # Script to generate user API keys
   python scripts/generate_api_key.py --user=alice@company.com
   # Stores in Secrets Manager, returns key to admin only
   ```

### Network Security

#### Lambda Configuration
```yaml
# Lambda function configuration
VpcConfig:
  SubnetIds:
    - subnet-private-1a
    - subnet-private-1b
  SecurityGroupIds:
    - sg-lambda-egress
```

#### ECS Configuration
```yaml
# ECS task definition
NetworkMode: awsvpc
NetworkConfiguration:
  AwsvpcConfiguration:
    Subnets:
      - subnet-private-1a
      - subnet-private-1b
    SecurityGroups:
      - sg-ecs-service
    AssignPublicIp: DISABLED
```

## Multi-Project Isolation

### Storage Structure

```
s3://{account-id}-code-index-code-storage/
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

s3://{account-id}-code-index-indexes/
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
# In server.py (Lambda/ECS handler)
import boto3

@mcp.tool()
def set_project_path(path: str, ctx: Context) -> str:
    user_id = ctx.request_context.user_id  # From auth middleware

    # Enforce namespace
    safe_path = f"/projects/{user_id}/{sanitize_path(path)}"

    # Mount from S3 (using boto3)
    s3 = boto3.client('s3')
    bucket = f"{os.getenv('AWS_ACCOUNT_ID')}-code-index-code-storage"
    prefix = f"users/{user_id}/"

    # Download user's project files to /tmp (Lambda) or EFS (ECS)
    # ... implementation details ...

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
- Idle projects consume S3 storage costs
- Abandoned Lambda/ECS instances waste resources
- Old indexes never get deleted

### Solution: Multi-Layer Cleanup Strategy

#### Layer 1: S3 Lifecycle Rules

```bash
# Set lifecycle on buckets
aws s3api put-bucket-lifecycle-configuration \
  --bucket "${ACCOUNT_ID}-code-index-code-storage" \
  --lifecycle-configuration file://lifecycle.json

# lifecycle.json
{
  "Rules": [
    {
      "Id": "Delete old user projects",
      "Status": "Enabled",
      "Prefix": "users/",
      "Expiration": {
        "Days": 90
      },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

#### Layer 2: EventBridge Cleanup Jobs

```bash
# Create daily cleanup rule
aws events put-rule \
  --name code-index-mcp-cleanup-daily \
  --schedule-expression "cron(0 2 * * ? *)" \
  --state ENABLED

# Add Lambda target
aws events put-targets \
  --rule code-index-mcp-cleanup-daily \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT_ID:function:code-index-mcp-cleanup"
```

```python
# Lambda cleanup function
import boto3
from datetime import datetime, timedelta

def cleanup_handler(event, context):
    """
    Delete projects with no activity for N days.
    Called by EventBridge.
    """
    s3 = boto3.client('s3')
    bucket = f"{os.environ['AWS_ACCOUNT_ID']}-code-index-code-storage"

    cutoff = datetime.now() - timedelta(days=30)
    deleted = []

    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix='users/'):
        for obj in page.get('Contents', []):
            if obj['LastModified'].replace(tzinfo=None) < cutoff:
                s3.delete_object(Bucket=bucket, Key=obj['Key'])
                deleted.append(obj['Key'])

    return {
        'statusCode': 200,
        'body': {
            'deleted_count': len(deleted),
            'cutoff_date': cutoff.isoformat()
        }
    }
```

#### Layer 3: Lambda Concurrency / ECS Auto-Scaling

**Lambda:**
```bash
# Set reserved concurrency (prevents runaway costs)
aws lambda put-function-concurrency \
  --function-name code-index-mcp \
  --reserved-concurrent-executions 10
```

**ECS Fargate:**
```bash
# Application Auto Scaling to scale to zero
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/code-index-cluster/code-index-mcp \
  --min-capacity 0 \
  --max-capacity 10

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/code-index-cluster/code-index-mcp \
  --policy-name scale-down-to-zero \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

#### Layer 4: Cost Alerts and Budgets

```bash
# Create budget alert
aws budgets create-budget \
  --account-id ACCOUNT_ID \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json

# budget.json
{
  "BudgetName": "MCP Server Monthly Budget",
  "BudgetLimit": {
    "Amount": "100",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
```

## Deployment Process

### Prerequisites

```bash
# Required tools
aws --version  # AWS CLI v2
docker --version  # For container builds

# Required permissions
aws configure
aws sts get-caller-identity

# Required environment variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION="us-east-1"
```

### Option A: Lambda Deployment Script

```bash
#!/bin/bash
# deployment/aws/deploy-lambda.sh

set -euo pipefail

AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID required}"
AWS_REGION="${AWS_REGION:-us-east-1}"
FUNCTION_NAME="code-index-mcp"

# 1. Create S3 buckets
aws s3 mb "s3://${AWS_ACCOUNT_ID}-code-index-code-storage" --region "$AWS_REGION" || true
aws s3 mb "s3://${AWS_ACCOUNT_ID}-code-index-indexes" --region "$AWS_REGION" || true

# 2. Set lifecycle policies
aws s3api put-bucket-lifecycle-configuration \
  --bucket "${AWS_ACCOUNT_ID}-code-index-code-storage" \
  --lifecycle-configuration file://deployment/aws/lifecycle.json

# 3. Create IAM execution role
aws iam create-role \
  --role-name lambda-code-index-execution \
  --assume-role-policy-document file://deployment/aws/lambda-trust-policy.json || true

aws iam attach-role-policy \
  --role-name lambda-code-index-execution \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam put-role-policy \
  --role-name lambda-code-index-execution \
  --policy-name code-index-s3-access \
  --policy-document file://deployment/aws/lambda-s3-policy.json

# 4. Package Lambda function
pip install -t package -r requirements.txt
cd package
zip -r ../lambda-package.zip .
cd ..
zip -g lambda-package.zip -r src/

# 5. Create/Update Lambda function
ROLE_ARN=$(aws iam get-role --role-name lambda-code-index-execution --query 'Role.Arn' --output text)

aws lambda create-function \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.11 \
  --role "$ROLE_ARN" \
  --handler src.code_index_mcp.server.lambda_handler \
  --zip-file fileb://lambda-package.zip \
  --memory-size 2048 \
  --timeout 900 \
  --environment "Variables={MCP_TRANSPORT=http,AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID}" \
  || aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://lambda-package.zip

# 6. Create API Gateway
API_ID=$(aws apigatewayv2 create-api \
  --name code-index-mcp \
  --protocol-type HTTP \
  --target "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${FUNCTION_NAME}" \
  --query 'ApiId' --output text)

aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${API_ID}/*/*"

# 7. Create EventBridge cleanup rule
aws events put-rule \
  --name code-index-mcp-cleanup \
  --schedule-expression "cron(0 2 * * ? *)" \
  --state ENABLED

aws events put-targets \
  --rule code-index-mcp-cleanup \
  --targets "Id"="1","Arn"="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${FUNCTION_NAME}-cleanup"

echo "✅ Lambda deployment complete!"
echo "API Gateway URL: https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com"
```

### Option B: ECS Deployment Script

```bash
#!/bin/bash
# deployment/aws/deploy-ecs.sh

set -euo pipefail

AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID required}"
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="code-index-cluster"
SERVICE_NAME="code-index-mcp"

# 1. Create ECR repository
aws ecr create-repository \
  --repository-name code-index-mcp \
  --region "$AWS_REGION" || true

# 2. Build and push Docker image
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build -t code-index-mcp .
docker tag code-index-mcp:latest "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/code-index-mcp:latest"
docker push "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/code-index-mcp:latest"

# 3. Create ECS cluster
aws ecs create-cluster --cluster-name "$CLUSTER_NAME" || true

# 4. Register task definition
aws ecs register-task-definition --cli-input-json file://deployment/aws/ecs-task-definition.json

# 5. Create ALB
# (Requires VPC, subnets, security groups - see full script)

# 6. Create ECS service
aws ecs create-service \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --task-definition code-index-mcp \
  --desired-count 0 \
  --launch-type FARGATE \
  --network-configuration file://deployment/aws/ecs-network-config.json \
  --load-balancers file://deployment/aws/ecs-load-balancers.json

echo "✅ ECS deployment complete!"
```

### Teardown Script

```bash
#!/bin/bash
# deployment/aws/destroy.sh

set -euo pipefail

AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID required}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# 1. Delete Lambda function (if using Lambda)
aws lambda delete-function --function-name code-index-mcp || true

# 2. Delete API Gateway
API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='code-index-mcp'].ApiId" --output text)
[ -n "$API_ID" ] && aws apigatewayv2 delete-api --api-id "$API_ID"

# 3. Delete EventBridge rules
aws events remove-targets --rule code-index-mcp-cleanup --ids "1" || true
aws events delete-rule --name code-index-mcp-cleanup || true

# 4. Delete S3 buckets (optional, data will be lost!)
read -p "Delete all S3 buckets? (yes/no): " confirm
if [ "$confirm" = "yes" ]; then
  aws s3 rb "s3://${AWS_ACCOUNT_ID}-code-index-code-storage" --force
  aws s3 rb "s3://${AWS_ACCOUNT_ID}-code-index-indexes" --force
fi

# 5. Delete IAM role
aws iam detach-role-policy \
  --role-name lambda-code-index-execution \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole || true
aws iam delete-role-policy --role-name lambda-code-index-execution --policy-name code-index-s3-access || true
aws iam delete-role --role-name lambda-code-index-execution || true

echo "✅ Resources deleted"
```

## Cost Estimation

### Lambda Costs (Scale-to-Zero)

| Usage Pattern | Monthly Cost |
|---------------|--------------|
| Idle (0 requests) | $0 |
| Light (1k requests, avg 5s, 2GB) | ~$1.50 |
| Medium (100k requests, avg 5s, 2GB) | ~$30 |
| Heavy (1M requests, avg 5s, 2GB) | ~$250 |

**Lambda Pricing (us-east-1):**
- Requests: $0.20 per 1M requests
- Compute: $0.0000166667 per GB-second

### ECS Fargate Costs

| Configuration | Monthly Cost |
|---------------|--------------|
| 0.25 vCPU, 0.5 GB (min) | ~$10 |
| 2 vCPU, 4 GB (typical) | ~$60 |
| 4 vCPU, 8 GB (heavy) | ~$120 |

**Note**: Cannot scale to true zero like Lambda

### S3 Storage Costs

| Resource | Size | Monthly Cost |
|----------|------|--------------|
| Code storage (10 users, 1GB each) | 10 GB | $0.23 |
| Indexes (10 users, 500MB each) | 5 GB | $0.12 |
| Glacier (archived) | 100 GB | $0.40 |
| **Total** | **15 GB (active)** | **$0.35** |

### Total Monthly Cost (Typical Team)

**Lambda Option:**
- Lambda (light usage): $1.50
- S3 storage: $0.35
- Data transfer: $0.50
- **Total: ~$2.50/month** ✅ Cheapest option

**ECS Fargate Option:**
- ECS Fargate (0.25 vCPU): $10
- S3 storage: $0.35
- ALB: $16
- Data transfer: $0.50
- **Total: ~$27/month**

**Comparison to Google Cloud:**
- AWS Lambda: ~$2.50/month (12x cheaper!)
- AWS ECS: ~$27/month (8x cheaper!)
- Google Cloud Run: ~$220/month (baseline)

## Multi-Project Workflow

### User Perspective

1. **Connect to API Gateway endpoint**
   ```json
   // Claude Desktop config
   {
     "mcpServers": {
       "code-index": {
         "url": "https://abc123.execute-api.us-east-1.amazonaws.com",
         "headers": {
           "x-api-key": "YOUR_AWS_API_KEY"
         }
       }
     }
   }
   ```

2. **Upload or sync code**
   ```
   User: "Upload my project from /local/path/to/project"
   MCP: Uploads to s3://account-code-storage/users/{user_id}/project_1/
   ```

3. **Index and search**
   ```
   User: "Set project path to project_1"
   MCP: Downloads from S3, builds index
   User: "Search for authentication code"
   MCP: Returns results from indexed project
   ```

4. **Switch projects**
   ```
   User: "Set project path to project_2"
   MCP: Clears project_1 cache, loads project_2
   ```

## Consequences

### Positive
- ✅ True serverless with Lambda (scales to zero)
- ✅ Lowest cost option ($2.50/month for Lambda)
- ✅ Automatic resource cleanup (no manual intervention)
- ✅ Multi-user support with isolation
- ✅ No cold start with ECS Fargate option
- ✅ More flexible than Google Cloud Run

### Negative
- ❌ Lambda 15-minute timeout (use ECS for longer operations)
- ❌ Cold start latency with Lambda (1-3s)
- ❌ More complex than Google Cloud Run (more services to manage)
- ❌ ECS cannot scale to true zero (minimum $10/month)

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Cost runaway | Budget alerts, reserved concurrency, auto-cleanup |
| Data loss | S3 versioning, lifecycle warnings before deletion |
| Security breach | API key auth, IAM, Secrets Manager |
| Lambda timeouts | Migrate to ECS Fargate for long operations |
| Cold starts | Use provisioned concurrency or ECS |

## Implementation Checklist

- [ ] Add Lambda/ECS handler to server.py
- [ ] Create S3 integration for file storage
- [ ] Add API key authentication middleware
- [ ] Implement cleanup Lambda function
- [ ] Write deployment script (deploy-lambda.sh or deploy-ecs.sh)
- [ ] Write teardown script (destroy.sh)
- [ ] Set up EventBridge cleanup rules
- [ ] Configure S3 lifecycle rules
- [ ] Create IAM roles and policies
- [ ] Document user onboarding flow
- [ ] Update README with AWS instructions

## Related ADRs

- ADR 0001: MCP Transport Protocols and Cloud Deployment Architecture
- ADR 0002: Google Cloud Run HTTP Deployment (Phase 2A - reference implementation)
- ADR 0004: AWS Code Ingestion with Aurora and Bedrock (Phase 3B - dependent on this ADR)
- ADR 0007: OpenShift HTTP Deployment (Phase 2C - parallel future implementation)
- ADR 0008: Git-Sync Ingestion Strategy (applies to all cloud deployments)
- ADR 0009: Ansible Deployment Automation (deployment methodology)

## References

- [AWS Lambda for Python](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html)
- [API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [ECS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [S3 Lifecycle Management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [EventBridge Scheduler](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)
- [FastMCP HTTP Transport](https://github.com/jlowin/fastmcp)
