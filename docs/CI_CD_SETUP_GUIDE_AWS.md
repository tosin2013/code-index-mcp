# CI/CD Pipeline Setup Guide - Amazon Web Services

**Platform**: Amazon Web Services (AWS)
**Status**: 📋 **Coming Soon** (Phase 2B)
**Reference**: [ADR 0006 - AWS HTTP Deployment](adrs/0006-aws-http-deployment-with-auto-cleanup.md)

> **Note**: This guide will cover AWS-specific CI/CD setup. For other platforms, see:
> - [GCP Setup Guide](CI_CD_SETUP_GUIDE_GCP.md) ✅ **Available Now**
> - [OpenShift Setup Guide](CI_CD_SETUP_GUIDE_OPENSHIFT.md) *(Coming Soon)*

## Status

This guide is **planned for Phase 2B** of the implementation roadmap. The AWS deployment workflows will be added after the GCP deployment is validated in production.

**Target Timeline**: After Phase 2A validation (estimated Q1 2026)

## Planned Features

When available, this guide will cover:

### CI/CD Pipeline for AWS

- **Automated Security Scanning**: Same as GCP (Gitleaks, Trivy, Bandit)
- **Automated Deployment**: Build → Test → Deploy to AWS Lambda/ECS
- **Safe Deletion**: Manual approval-gated infrastructure deletion
- **Keyless Authentication**: OIDC with GitHub Actions (no AWS access keys)
- **Multi-Environment**: dev, staging, prod with environment protection

### AWS-Specific Components

1. **Deployment Targets**:
   - AWS Lambda (serverless, lowest cost ~$2.50/month)
   - Amazon ECS Fargate (container-based, ~$27/month)

2. **Authentication**:
   - OIDC Workload Identity with GitHub Actions
   - AWS IAM roles (no long-lived credentials)

3. **Infrastructure**:
   - Terraform for AWS resources
   - Ansible for application configuration
   - Amazon Aurora PostgreSQL + pgvector (Phase 3B)
   - Amazon Bedrock for embeddings (Phase 3B)

4. **Storage**:
   - Amazon S3 for code and indexes
   - S3 lifecycle policies for automatic cleanup

5. **Secrets**:
   - AWS Secrets Manager for API keys
   - Parameter Store for configuration

## Pipeline Architecture (Planned)

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
│  - Docker build (multi-stage)                                │
│  - Push to Amazon ECR                                        │
│  - Tag with commit SHA                                       │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 4: Deploy Infrastructure (Terraform)                  │
│  - Lambda function or ECS cluster                            │
│  - API Gateway or ALB                                        │
│  - S3 buckets with lifecycle rules                          │
│  - Aurora PostgreSQL (Phase 3B)                             │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 5: Deploy Application (Ansible)                       │
│  - Lambda/ECS service configuration                          │
│  - Environment variables                                     │
│  - EventBridge cleanup job                                   │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Stage 6: Verification (MCP Tests)                           │
│  - MCP tool validation (ADR 0010)                           │
│  - Health checks                                             │
└─────────────────────────────────────────────────────────────┘
```

## Planned Workflows

### deploy-aws.yml (Coming Soon)

Will support:
- Automated deployment to Lambda or ECS
- OIDC authentication with AWS IAM
- Multi-environment support (dev/staging/prod)
- Terraform infrastructure management
- Ansible configuration management

### delete-aws.yml (Coming Soon)

Will include:
- Manual approval gates
- Audit logging to S3
- Resource inventory
- State file archival
- Production deletion protection

## Cost Comparison

| Component | Lambda (Serverless) | ECS Fargate |
|-----------|-------------------|-------------|
| **Compute** | $0.0000002/ms | $0.04048/hour |
| **API Gateway** | $3.50/million | N/A (ALB: $16/month) |
| **Storage (S3)** | $0.023/GB | $0.023/GB |
| **Estimated Monthly** | **~$2.50** | **~$27** |

**Recommendation**: Start with Lambda for lowest cost, migrate to ECS if you need:
- Longer execution times (>15 minutes)
- More memory (>10GB)
- More control over runtime environment

## Prerequisites (When Available)

1. AWS account with billing enabled
2. AWS CLI installed and configured
3. Terraform >= 1.5.0
4. Ansible >= 2.14
5. Docker for local testing
6. GitHub repository with Actions enabled

## Implementation Roadmap

**Phase 2B: AWS HTTP Deployment** (Planned)
- Week 1-2: Terraform infrastructure for Lambda/ECS
- Week 2-3: Ansible deployment playbooks
- Week 3: GitHub Actions workflows (deploy-aws.yml, delete-aws.yml)
- Week 4: Testing and documentation

**Phase 3B: AWS Semantic Search** (Future)
- Aurora PostgreSQL + pgvector setup
- Amazon Bedrock integration
- Ingestion pipeline adaptation
- MCP tools for semantic search

## How to Get Notified

Watch for updates:
1. **GitHub Releases**: Subscribe to repository releases
2. **Implementation Plan**: Check `docs/IMPLEMENTATION_PLAN.md` for progress
3. **ADR Updates**: Monitor `docs/adrs/` for AWS-related decisions

## Current Alternative

While AWS support is in development, you can:
1. Use the **GCP deployment** (fully operational)
2. Follow [CI_CD_SETUP_GUIDE_GCP.md](CI_CD_SETUP_GUIDE_GCP.md)
3. Deploy to GCP and migrate to AWS later (architecture is portable)

## Questions or Contributions

- **GitHub Issues**: Request AWS support or volunteer to help implement
- **Pull Requests**: Contributions welcome for AWS deployment automation
- **Discussions**: Share your AWS deployment requirements

---

**Last Updated**: November 14, 2025
**Status**: Planning Phase
**Expected Availability**: Q1 2026 (after Phase 2A validation)
