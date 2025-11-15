<!-- AUTO-UPDATED IMPLEMENTATION PLAN -->
<!-- This file is automatically updated based on ADRs and project conversations -->
<!-- Last Updated: 2025-11-14 -->
<!-- Update Frequency: As project progresses and new decisions are made -->

# Implementation Plan

## Overview

**Code Index MCP** is a Model Context Protocol (MCP) server that provides intelligent code indexing and analysis capabilities for Large Language Models. The project enables AI assistants to effectively search, navigate, and understand complex codebases through a combination of tree-sitter AST parsing, semantic search, and multi-cloud deployment options.

### Project Scope

The implementation follows a phased approach:
1. **Phase 1**: Core MCP server with local execution (stdio transport)
2. **Phase 2**: Cloud HTTP deployments (GCP, AWS, OpenShift)
3. **Phase 3**: Semantic search with vector embeddings (GCP, AWS, OpenShift)
4. **Phase 4**: CI/CD automation and security hardening
5. **Phase 5**: Production optimization and multi-cloud parity

### Technology Stack

- **Language**: Python 3.11+
- **Package Manager**: uv
- **MCP Framework**: FastMCP
- **Deployment**: Google Cloud Run (primary), AWS Lambda/ECS, OpenShift
- **Database**: AlloyDB (GCP), Aurora PostgreSQL (AWS), PostgreSQL + Milvus (OpenShift)
- **CI/CD**: GitHub Actions, Tekton Pipelines
- **IaC**: Terraform
- **Configuration Management**: Ansible

## Project Status

**Current Phase:** Phase 3A (GCP Semantic Search) + Phase 4 (CI/CD Automation)

**Overall Progress:** 85% complete

**Last Major Milestone:** ADR 0011 CI/CD Pipeline and Security Architecture - Completed 2025-11-10

**Next Milestone:** AlloyDB Provisioning and Semantic Search Production Deployment - Target: 2025-11-30

**Current Version:** 2.4.1

## Architecture Decisions Summary

All architectural decisions are documented in `docs/adrs/`. Key decisions impacting implementation:

- **ADR 0001: MCP Transport Protocols** - Dual transport support (stdio for local, HTTP/SSE for cloud)
- **ADR 0002: Cloud Run HTTP Deployment** - GCP serverless deployment with auto-cleanup (~$3/month)
- **ADR 0003: Google Cloud Code Ingestion** - AlloyDB + pgvector + Vertex AI for semantic search
- **ADR 0008: Git-Sync Ingestion Strategy** - Direct git clone/sync with webhooks (99% token savings)
- **ADR 0009: Ansible Deployment Automation** - Idempotent, declarative deployments replacing bash scripts
- **ADR 0010: MCP Server Testing** - Automated testing with tosin2013.mcp_audit Ansible collection
- **ADR 0011: CI/CD Pipeline and Security** - GitHub Actions + Tekton with multi-layer security scanning

## Implementation Phases

### Phase 1: Core MCP Server (Local Execution)

**Status:** ✅ Completed (100%)

**Objective:** Build foundational MCP server with stdio transport for local development

**Based on:** ADR 0001

**Tasks:**
- [x] Implement FastMCP server with stdio transport
- [x] Add tree-sitter parsing for 7 languages (Python, JS, TS, Java, Go, Objective-C, Zig)
- [x] Create fallback parsing strategy for 50+ file types
- [x] Build shallow index for file discovery (`find_files()`)
- [x] Build deep index for symbol extraction (`get_file_summary()`)
- [x] Implement search system with cascading tool detection (ugrep → ripgrep → ag → grep)
- [x] Add file watcher for real-time index updates
- [x] Create MCP tools for metadata search
- [x] Write comprehensive documentation (CLAUDE.md)

**Dependencies:** None

**Success Criteria:**
- ✅ MCP server runs locally with `uvx code-index-mcp`
- ✅ All metadata tools functional (set_project_path, find_files, search_code_advanced, etc.)
- ✅ Tree-sitter parsing works for supported languages
- ✅ File watcher automatically refreshes indexes

**Completed:** 2025-10-24

---

### Phase 2A: Google Cloud Platform HTTP Deployment

**Status:** ✅ Completed (100%)

**Objective:** Deploy MCP server to Cloud Run with HTTP/SSE transport, multi-user support, and automatic resource cleanup

**Based on:** ADR 0002, ADR 0009

**Tasks:**
- [x] Implement HTTP/SSE transport in FastMCP
- [x] Deploy to Google Cloud Run with auto-scale to zero
- [x] Set up Cloud Storage for multi-tenant user namespaces
- [x] Implement API key authentication with Secret Manager
- [x] Create automatic cleanup with Cloud Scheduler (30-day TTL)
- [x] Add storage lifecycle rules (archive 30 days, delete 90 days)
- [x] Replace bash deployment scripts with Ansible playbooks
- [x] Create multi-environment support (dev/staging/prod)
- [x] Build Ansible roles: prerequisites, storage, IAM, build, deploy, schema, cleanup
- [x] Create utility operations: generate_api_key, verify_schema, teardown

**Dependencies:** Phase 1 complete

**Success Criteria:**
- ✅ Cloud Run service deployed and accessible via HTTPS
- ✅ API key authentication working
- ✅ Multi-user namespace isolation functional
- ✅ Automatic cleanup preventing cost accumulation
- ✅ Ansible deployment idempotent and testable
- ✅ Cost under $5/month for typical usage

**Completed:** 2025-10-29

**Deployment:**
```bash
cd deployment/gcp/ansible
ansible-playbook deploy.yml -i inventory/dev.yml
```

---

### Phase 3A: Google Cloud Semantic Search with AlloyDB

**Status:** 🚧 In Progress (83% complete)

**Objective:** Enable semantic code search using AlloyDB + pgvector + Vertex AI embeddings

**Based on:** ADR 0003, ADR 0008

**Tasks:**
- [x] Design AlloyDB schema with vector support (pgvector extension)
- [x] Create Terraform infrastructure for AlloyDB cluster
- [x] Implement code chunking with AST-based parsing
- [x] Integrate Vertex AI text-embedding-004 (768 dimensions)
- [x] Build ingestion pipeline (chunk → embed → store)
- [x] Create semantic search service with vector similarity
- [x] Implement git-sync ingestion (`ingest_code_from_git` tool)
- [x] Add webhook support (GitHub, GitLab, Gitea, Bitbucket)
- [x] Create MCP tools: semantic_search_code, find_similar_code
- [x] Add authentication middleware for user context
- [x] Implement row-level security for multi-tenancy
- [x] Fix schema bugs (user_id column, git metadata columns)
- [x] Add health checks with schema validation
- [ ] **Provision AlloyDB cluster in GCP** ⏳ BLOCKED
- [ ] Apply schema to production AlloyDB instance
- [ ] Test with real-world large codebase (100k+ LOC)
- [ ] Performance benchmarking and optimization
- [ ] Documentation for semantic search workflows

**Dependencies:** Phase 2A complete, Terraform infrastructure ready

**Success Criteria:**
- [ ] AlloyDB cluster provisioned and accessible
- [ ] Schema applied with pgvector extension and HNSW index
- [x] Code ingestion pipeline functional (54/54 tests passing)
- [ ] Semantic search returns relevant results with >0.7 similarity
- [ ] Git-sync webhooks trigger automatic re-ingestion
- [ ] User namespace isolation enforced at database level
- [ ] Performance: <500ms for semantic search queries

**Current Blockers:**
- **AlloyDB Provisioning**: Pending GCP quota approval or budget allocation (~$220/month)
- Workaround: All code complete, tested with local PostgreSQL + pgvector

**Notes:**
- Infrastructure code 100% complete (Terraform, SQL schema, Python services)
- All MCP tools implemented and tested (21/21 tests passing)
- Git-sync ingestion provides 99% token savings vs file upload
- Ready for production deployment once AlloyDB cluster is provisioned

---

### Phase 4: CI/CD Pipeline and Security Architecture (GCP Focus)

**Status:** ✅ Completed (100%) - Documentation complete, Implementation in progress

**Objective:** Implement comprehensive CI/CD pipeline for automated, secure deployments to GCP with multi-layer security scanning

**Based on:** ADR 0011

**Tasks:**

#### 4.1 GitHub Actions Workflows
- [x] Document security scanning workflow (Gitleaks, Trivy, Bandit)
- [x] Document GCP deployment workflow (deploy-gcp.yml)
- [x] Document GCP deletion workflow with approval gates (delete-gcp.yml)
- [ ] **Implement .github/workflows/security-scan.yml**
  - [ ] Gitleaks secret detection on every PR
  - [ ] Trivy vulnerability scanning (CRITICAL/HIGH blocking)
  - [ ] Bandit Python security linting
- [ ] **Implement .github/workflows/deploy-gcp.yml**
  - [ ] Multi-stage pipeline: security → test → build → deploy → verify
  - [ ] OIDC Workload Identity authentication (keyless)
  - [ ] Terraform infrastructure deployment
  - [ ] Ansible application deployment
  - [ ] Integration with ADR 0010 MCP testing for verification
- [ ] **Implement .github/workflows/delete-gcp.yml**
  - [ ] Manual trigger only
  - [ ] Confirmation input validation (must type "DELETE")
  - [ ] Environment restrictions (block prod deletion)
  - [ ] Manual approval requirement from 2+ reviewers
  - [ ] Audit logging of all deletions

#### 4.2 Security Configuration
- [x] Create .gitleaks.toml configuration
- [ ] **Implement Gitleaks configuration**
  - [ ] API key detection patterns
  - [ ] GCP/AWS/GitHub token patterns
  - [ ] Allowlist for docs/ and tests/
- [ ] **Implement Trivy configuration (trivy.yaml)**
  - [ ] Scan dependencies (requirements.txt, pyproject.toml)
  - [ ] Scan Docker images for OS vulnerabilities
  - [ ] Severity thresholds (CRITICAL/HIGH block deployment)
- [ ] **Configure Bandit in pyproject.toml**
  - [ ] Security checks for SQL injection, hardcoded passwords
  - [ ] Skip assert_used in tests
- [ ] **Set up OIDC Workload Identity**
  - [ ] Create Workload Identity Pool in GCP
  - [ ] Create Workload Identity Provider
  - [ ] Configure GitHub Actions service account
  - [ ] Test keyless authentication
- [ ] **Configure GitHub Secrets**
  - [ ] GCP_WORKLOAD_IDENTITY_PROVIDER
  - [ ] GCP_SERVICE_ACCOUNT
  - [ ] GCP_PROJECT_ID
  - [ ] GCP_REGION
  - [ ] CLOUDRUN_SERVICE_URL

#### 4.3 Deployment Automation
- [ ] **Create deployment script structure**
  - [ ] Environment-specific configurations (dev/staging/prod)
  - [ ] Automated Terraform plan/apply
  - [ ] Ansible playbook execution
  - [ ] Health check verification
- [ ] **Implement safe deletion workflow**
  - [ ] Interactive CLI script (deployment/gcp/scripts/delete-infrastructure.sh)
  - [ ] Multiple confirmation steps
  - [ ] Audit logging to file
  - [ ] Resource inventory display before deletion
  - [ ] Terraform destroy with approval

#### 4.4 Integration with Existing Tools
- [x] Integrate with Ansible deployment (ADR 0009)
- [x] Integrate with MCP testing (ADR 0010)
- [ ] **Configure CI/CD to use Ansible**
  - [ ] Call deploy.yml playbook in GitHub Actions
  - [ ] Pass environment variables and image tags
  - [ ] Capture deployment outputs
- [ ] **Configure CI/CD to use MCP tests**
  - [ ] Run test-cloud.yml after deployment
  - [ ] Validate all MCP tools functional
  - [ ] Fail pipeline if tests don't pass

#### 4.5 Testing and Validation
- [ ] **Test security scanning**
  - [ ] Commit test secret to verify Gitleaks detection
  - [ ] Test Trivy with vulnerable dependency
  - [ ] Test Bandit with insecure code pattern
- [ ] **Test deployment workflow**
  - [ ] Deploy to dev environment via GitHub Actions
  - [ ] Verify all pipeline stages complete
  - [ ] Validate deployed service health
- [ ] **Test deletion workflow**
  - [ ] Test interactive deletion script on dev
  - [ ] Test GitHub Actions deletion with approval
  - [ ] Verify audit logs captured

**Dependencies:**
- Phase 2A (Ansible deployment) complete
- ADR 0010 (MCP testing) Phase 1 complete

**Success Criteria:**
- [ ] Every `git push` triggers security scans
- [ ] CRITICAL/HIGH vulnerabilities block deployment
- [ ] No secrets ever committed to git (Gitleaks pre-commit hook)
- [ ] Deployments fully automated via GitHub Actions
- [ ] Manual approval required for infrastructure deletion
- [ ] Complete audit trail of all deployments and deletions
- [ ] OIDC authentication (no service account keys in GitHub)
- [ ] All pipeline stages complete in <15 minutes

**Current Status:**
- Documentation: 100% complete (ADR 0011 created)
- Implementation: 20% complete
  - ✅ Ansible integration ready
  - ✅ MCP testing integration ready
  - ⏳ GitHub Actions workflows pending
  - ⏳ Security tool configuration pending
  - ⏳ OIDC Workload Identity pending

**Next Steps:**
1. Create `.github/workflows/security-scan.yml`
2. Create `.gitleaks.toml` configuration
3. Set up OIDC Workload Identity in GCP
4. Implement `deploy-gcp.yml` workflow
5. Test end-to-end deployment pipeline

**Notes:**
- Focus on GCP implementation first (AWS/OpenShift workflows documented but not implemented)
- Tekton pipeline documented for OpenShift but not yet created
- Interactive deletion script documented but not yet implemented
- All security tools selected and documented, ready for configuration

**Estimated Completion:** 2025-11-30

---

### Phase 2B: AWS HTTP Deployment

**Status:** 📋 Planned (0% complete)

**Objective:** Deploy MCP server to AWS Lambda or ECS with HTTP/SSE transport

**Based on:** ADR 0006

**Tasks:**
- [ ] Implement AWS Lambda deployment with API Gateway
- [ ] Implement AWS ECS Fargate deployment with ALB (alternative)
- [ ] Set up S3 for multi-tenant user namespaces
- [ ] Implement API key authentication with AWS Secrets Manager
- [ ] Create automatic cleanup with EventBridge rules
- [ ] Create Ansible playbooks for AWS deployment
- [ ] Terraform infrastructure for AWS

**Dependencies:** Phase 2A complete (can learn from GCP implementation)

**Success Criteria:**
- [ ] Lambda or ECS service deployed and accessible
- [ ] Cost under $3/month (Lambda option)
- [ ] Multi-user namespace isolation functional

**Target Start:** 2026-Q1

---

### Phase 2C: OpenShift HTTP Deployment

**Status:** 📋 Planned (0% complete)

**Objective:** Deploy MCP server to OpenShift with HTTP/SSE transport

**Based on:** ADR 0007

**Tasks:**
- [ ] Create Kubernetes manifests for OpenShift
- [ ] Set up ODF S3 or PVCs for user storage
- [ ] Implement authentication with Sealed Secrets
- [ ] Create CronJob for automatic cleanup
- [ ] Build Helm chart for deployment
- [ ] Create Ansible playbooks for OpenShift

**Dependencies:** Phase 2A complete

**Success Criteria:**
- [ ] OpenShift deployment functional
- [ ] HPA configured for auto-scaling
- [ ] NetworkPolicy and RBAC configured

**Target Start:** 2026-Q1

---

### Phase 3B: AWS Semantic Search with Aurora and Bedrock

**Status:** 📋 Planned (0% complete)

**Objective:** Enable semantic code search using Aurora PostgreSQL + pgvector + Amazon Bedrock

**Based on:** ADR 0004

**Tasks:**
- [ ] Create Terraform infrastructure for Aurora Serverless v2
- [ ] Implement Bedrock embedding generation (Titan Embeddings)
- [ ] Adapt ingestion pipeline for AWS
- [ ] Create semantic search service for Aurora
- [ ] Implement MCP tools for AWS deployment

**Dependencies:** Phase 3A complete, Phase 2B complete

**Success Criteria:**
- [ ] Semantic search functional on AWS
- [ ] Cost ~$65/month (3x cheaper than GCP)

**Target Start:** 2026-Q2

---

### Phase 3C: OpenShift Semantic Search with Milvus and vLLM

**Status:** 📋 Planned (0% complete)

**Objective:** Enable semantic code search using Milvus vector DB + vLLM + ODF storage

**Based on:** ADR 0005

**Tasks:**
- [ ] Deploy Milvus on OpenShift
- [ ] Deploy vLLM with GPU for embeddings (E5-Mistral-7B)
- [ ] Set up ODF for S3-compatible storage
- [ ] Adapt ingestion pipeline for OpenShift
- [ ] Create Helm charts for all components

**Dependencies:** Phase 3A complete, Phase 2C complete

**Success Criteria:**
- [ ] Fully on-premise, air-gap capable semantic search
- [ ] GPU-accelerated embedding generation

**Target Start:** 2026-Q2

---

### Phase 5: Production Optimization and Monitoring

**Status:** 📋 Planned (0% complete)

**Objective:** Optimize performance, add monitoring, and prepare for production scale

**Tasks:**
- [ ] Add comprehensive logging and tracing
- [ ] Implement metrics collection (Prometheus/Datadog)
- [ ] Performance optimization (caching, query optimization)
- [ ] Cost optimization across all platforms
- [ ] Create operational runbooks
- [ ] Set up alerting and on-call procedures
- [ ] Load testing and capacity planning
- [ ] Security audit and penetration testing

**Dependencies:** Phase 3A, Phase 4 complete

**Success Criteria:**
- [ ] P99 latency <500ms for semantic search
- [ ] 99.9% uptime SLA
- [ ] Cost per user under $10/month
- [ ] All critical alerts routed to on-call

**Target Start:** 2026-Q3

---

## Current Sprint / Active Work

### Active as of 2025-11-14

**Sprint Goal:** Complete Phase 4 (CI/CD) GitHub Actions implementation and unblock Phase 3A (AlloyDB provisioning)

**In Progress:**
- **Phase 4.1: GitHub Actions Workflows** - Priority: HIGH
  - Status: Planning complete, implementation pending
  - Assigned to: Development team
  - Blockers: None
  - Next action: Create .github/workflows/security-scan.yml

- **Phase 3A: AlloyDB Provisioning** - Priority: HIGH
  - Status: Infrastructure code complete, awaiting cluster provisioning
  - Assigned to: DevOps/Platform team
  - Blockers: GCP quota approval or budget allocation
  - Next action: Submit GCP quota increase request or allocate $220/month budget

**Recently Completed:**
- [x] ADR 0011: CI/CD Pipeline and Security Architecture (2025-11-10)
- [x] Fix schema bugs: user_id column, git metadata columns (2025-11-12)
- [x] Add fail-fast behavior for critical initialization errors (2025-11-13)

**Up Next:**
- [ ] Implement security-scan.yml workflow
- [ ] Configure Gitleaks, Trivy, Bandit
- [ ] Set up OIDC Workload Identity
- [ ] Test security scanning pipeline

---

## Technical Requirements

### Infrastructure Requirements (GCP)
- [x] Google Cloud project with billing enabled
- [x] Cloud Run service quota
- [x] Artifact Registry for container images
- [x] Cloud Storage buckets
- [x] Secret Manager for API keys
- [x] Cloud Scheduler for cleanup
- [ ] AlloyDB cluster (waiting provisioning)
- [ ] VPC connector for AlloyDB
- [ ] Workload Identity Pool and Provider (for CI/CD)

### Development Environment
- [x] Python 3.11+ installed
- [x] uv package manager
- [x] Git repository
- [x] Docker for local testing
- [x] gcloud CLI authenticated
- [x] Ansible installed (>=2.14)
- [x] Terraform installed (>=1.5.0)

### Security Requirements
- [x] No credentials committed to git (.gitignore configured)
- [x] API keys stored in Secret Manager
- [ ] Gitleaks pre-commit hook configured
- [ ] OIDC Workload Identity (no service account keys)
- [ ] Secrets scanning in CI/CD
- [ ] Vulnerability scanning in CI/CD

### Testing Requirements
- [x] tosin2013.mcp_audit Ansible collection installed
- [x] Test playbooks for local (stdio) testing
- [x] Test playbooks for cloud (HTTP/SSE) testing
- [ ] Integration tests in CI/CD pipeline
- [ ] Automated regression testing

---

## Dependencies and Prerequisites

### External Dependencies

**GCP Services:**
- Cloud Run - Status: ✅ Available
- Cloud Storage - Status: ✅ Available
- Artifact Registry - Status: ✅ Available
- Secret Manager - Status: ✅ Available
- Cloud Scheduler - Status: ✅ Available
- Vertex AI (text-embedding-004) - Status: ✅ Available
- AlloyDB - Status: ⏳ Pending provisioning

**Third-Party Services:**
- GitHub (for Actions CI/CD) - Status: ✅ Available
- Git hosting (GitHub/GitLab/Gitea) - Status: ✅ Available

**Development Tools:**
- FastMCP framework - Status: ✅ Available
- tree-sitter parsers - Status: ✅ Available
- Ansible Google Cloud collection - Status: ✅ Available

### Internal Prerequisites

**Phase Dependencies:**
- Phase 2A must complete before Phase 2B/2C
- Phase 3A must complete before Phase 3B/3C
- Phase 2A + Phase 3A must complete before Phase 5

**Code Dependencies:**
- [x] MCP server core (Phase 1)
- [x] HTTP/SSE transport (Phase 2A)
- [x] Git-sync ingestion (ADR 0008)
- [x] Ansible deployment automation (ADR 0009)
- [x] MCP testing framework (ADR 0010)

---

## Completed Milestones

- [x] **Phase 1: Core MCP Server** - Completed: 2025-10-24
  - Local stdio transport working
  - All metadata tools functional
  - Tree-sitter parsing for 7 languages
  - File watcher for real-time updates

- [x] **Phase 2A: GCP HTTP Deployment** - Completed: 2025-10-29
  - Cloud Run deployment successful
  - Multi-user namespace isolation
  - API key authentication
  - Automatic resource cleanup

- [x] **ADR 0008: Git-Sync Ingestion** - Completed: 2025-10-31
  - Direct git clone/sync working
  - Webhook support (GitHub, GitLab, Gitea, Bitbucket)
  - 99% token savings vs file upload
  - 54/54 tests passing

- [x] **ADR 0009: Ansible Deployment Automation** - Completed: 2025-10-29
  - Bash scripts replaced with Ansible
  - Idempotent, declarative deployments
  - Multi-environment support
  - Utility operations (generate_api_key, verify_schema, teardown)

- [x] **ADR 0011: CI/CD Documentation** - Completed: 2025-11-10
  - Complete CI/CD architecture documented
  - GitHub Actions workflows designed
  - Security scanning strategy defined
  - Integration points identified

- [x] **Version 2.4.1 Release** - Completed: 2025-11-12
  - Schema bug fixes (user_id, git metadata)
  - Enhanced health checks
  - Fail-fast initialization

---

## Upcoming Milestones

- [ ] **Phase 4.1: Security Scanning Pipeline** - Target: 2025-11-20
  - Gitleaks, Trivy, Bandit configured
  - Security scanning on every PR
  - Pre-commit hooks for secret detection

- [ ] **Phase 4.2: GCP Deployment Pipeline** - Target: 2025-11-25
  - GitHub Actions deploy-gcp.yml working
  - OIDC Workload Identity configured
  - Automated Terraform + Ansible deployment

- [ ] **Phase 3A: AlloyDB Production Deployment** - Target: 2025-11-30
  - AlloyDB cluster provisioned
  - Schema applied to production
  - Semantic search live in production

- [ ] **Phase 4.3: Deletion Safety Workflow** - Target: 2025-12-05
  - Interactive deletion script
  - GitHub Actions deletion workflow with approvals
  - Audit logging

- [ ] **Version 2.5.0 Release** - Target: 2025-12-10
  - Semantic search production-ready
  - CI/CD fully automated
  - Complete documentation

---

## Risk Mitigation

### Active Risks

**Risk: AlloyDB Provisioning Delay**
- **Status:** Active
- **Impact:** HIGH - Blocks Phase 3A completion
- **Probability:** MEDIUM
- **Mitigation:**
  - All infrastructure code complete and tested
  - Workaround with local PostgreSQL + pgvector for development
  - Alternative: Use Cloud SQL PostgreSQL with pgvector (cheaper but less performant)
  - Action: Submit GCP quota increase request or allocate budget

**Risk: OIDC Workload Identity Setup Complexity**
- **Status:** Active
- **Impact:** MEDIUM - Delays CI/CD automation
- **Probability:** MEDIUM
- **Mitigation:**
  - Comprehensive documentation in ADR 0011
  - Can start with service account key as temporary workaround
  - Google Cloud documentation and examples available
  - Action: Follow step-by-step setup guide

**Risk: Security Scanning False Positives**
- **Status:** Active
- **Impact:** LOW - May slow development
- **Probability:** HIGH
- **Mitigation:**
  - Allowlist mechanism in Gitleaks configuration
  - Trivy severity thresholds (only CRITICAL/HIGH block)
  - Clear process for approving false positives
  - Action: Document allowlist justification process

### Mitigated Risks

**Risk: Bash Script Deployment Fragility**
- **Status:** ✅ Mitigated (ADR 0009)
- **Mitigation:** Replaced with Ansible idempotent playbooks

**Risk: Manual Testing Overhead**
- **Status:** ✅ Mitigated (ADR 0010)
- **Mitigation:** Automated MCP testing with Ansible collection

**Risk: Token Costs for Code Ingestion**
- **Status:** ✅ Mitigated (ADR 0008)
- **Mitigation:** Git-sync ingestion provides 99% token savings

---

## Testing Strategy

### Unit Testing
- [x] Python unit tests with pytest (tests/unit/)
- [x] Code coverage tracking
- [ ] Unit tests in CI/CD pipeline

### Integration Testing
- [x] MCP tool integration tests (tests/integration/)
- [x] Ansible test playbooks (test-local.yml, test-cloud.yml)
- [ ] Integration tests in CI/CD pipeline

### Security Testing
- [ ] Gitleaks secret scanning on every PR
- [ ] Trivy vulnerability scanning (dependencies + container images)
- [ ] Bandit Python security linting
- [ ] Manual security audit before production

### Performance Testing
- [ ] Load testing semantic search (target: <500ms P99)
- [ ] Ingestion pipeline performance (target: 1000 files/min)
- [ ] Concurrent user testing
- [ ] Cost analysis under load

### End-to-End Testing
- [x] Local MCP server validation (stdio transport)
- [x] Cloud MCP server validation (HTTP/SSE transport)
- [x] Git-sync ingestion with webhooks
- [ ] Full deployment pipeline (CI/CD → production)

### Regression Testing
- [x] Comprehensive test suite (test-regression.yml)
- [ ] Automated regression testing on every deployment
- [ ] Performance regression detection

---

## Technical Debt & Future Improvements

### Technical Debt

**High Priority:**
- [ ] Refactor server.py tool decorators to reduce code duplication (Priority: HIGH)
  - Multiple tools share similar patterns
  - Extract common logic to shared decorators
  - Estimated effort: 2 days

- [ ] Improve error messages for tree-sitter parsing failures (Priority: MEDIUM)
  - Current errors not user-friendly
  - Add suggestions for fixing common issues
  - Estimated effort: 1 day

**Medium Priority:**
- [ ] Add caching layer for frequently accessed indexes (Priority: MEDIUM)
  - Reduce filesystem I/O
  - Speed up repeated searches
  - Estimated effort: 3 days

- [ ] Optimize Docker image size (Priority: MEDIUM)
  - Current image ~800MB, can reduce to ~400MB
  - Use multi-stage builds
  - Estimated effort: 1 day

**Low Priority:**
- [ ] Migrate from msgpack to more efficient serialization (Priority: LOW)
  - Marginal performance improvement
  - Estimated effort: 2 days

### Future Improvements

**Phase 5+ Features:**
- [ ] Real-time collaborative code indexing (Priority: MEDIUM)
  - Multiple users working on same codebase
  - Live index updates
  - Estimated effort: 2 weeks

- [ ] Advanced code intelligence features (Priority: MEDIUM)
  - Call graph analysis
  - Dependency tracking
  - Code quality metrics
  - Estimated effort: 4 weeks

- [ ] IDE integrations (Priority: MEDIUM)
  - VS Code extension
  - JetBrains plugin
  - Estimated effort: 6 weeks

- [ ] Natural language query improvements (Priority: LOW)
  - Better query understanding
  - Query suggestion
  - Estimated effort: 2 weeks

---

## Timeline

**Project Start:** 2025-10-24

**Current Date:** 2025-11-14

**Estimated Completion:** 2026-Q3 (for full multi-cloud parity)

### Phase Timeline

| Phase | Start | End | Status | Progress |
|-------|-------|-----|--------|----------|
| Phase 1: Core MCP Server | 2025-10-24 | 2025-10-24 | ✅ Complete | 100% |
| Phase 2A: GCP HTTP Deployment | 2025-10-25 | 2025-10-29 | ✅ Complete | 100% |
| Phase 3A: GCP Semantic Search | 2025-10-30 | 2025-11-30 | 🚧 In Progress | 83% |
| Phase 4: CI/CD (GCP) | 2025-11-10 | 2025-11-30 | 🚧 In Progress | 20% |
| Phase 2B: AWS HTTP Deployment | 2026-Q1 | 2026-Q1 | 📋 Planned | 0% |
| Phase 2C: OpenShift HTTP Deployment | 2026-Q1 | 2026-Q1 | 📋 Planned | 0% |
| Phase 3B: AWS Semantic Search | 2026-Q2 | 2026-Q2 | 📋 Planned | 0% |
| Phase 3C: OpenShift Semantic Search | 2026-Q2 | 2026-Q2 | 📋 Planned | 0% |
| Phase 5: Production Optimization | 2026-Q3 | 2026-Q3 | 📋 Planned | 0% |

### Key Dates

- **2025-10-24**: Project kickoff, Phase 1 complete
- **2025-10-29**: Phase 2A (GCP HTTP) complete, Ansible automation (ADR 0009) complete
- **2025-10-31**: Git-sync ingestion (ADR 0008) complete
- **2025-11-10**: CI/CD architecture (ADR 0011) documented
- **2025-11-12**: Version 2.4.1 released (schema bug fixes)
- **2025-11-14**: Implementation plan created (this document)
- **2025-11-20** (target): Security scanning pipeline live
- **2025-11-25** (target): GCP deployment pipeline automated
- **2025-11-30** (target): AlloyDB provisioned, semantic search in production
- **2025-12-10** (target): Version 2.5.0 release (semantic search + CI/CD)
- **2026-Q1**: AWS and OpenShift HTTP deployments
- **2026-Q2**: Multi-cloud semantic search parity
- **2026-Q3**: Production optimization and monitoring

---

## References

### Architecture Decision Records

- [ADR 0001: MCP Transport Protocols](adrs/0001-mcp-stdio-protocol-cloud-deployment-constraints.md)
- [ADR 0002: Cloud Run HTTP Deployment](adrs/0002-cloud-run-http-deployment-with-auto-cleanup.md)
- [ADR 0003: Google Cloud Code Ingestion](adrs/0003-google-cloud-code-ingestion-with-alloydb.md)
- [ADR 0004: AWS Code Ingestion](adrs/0004-aws-code-ingestion-with-aurora-and-bedrock.md)
- [ADR 0005: OpenShift Code Ingestion](adrs/0005-openshift-code-ingestion-with-milvus.md)
- [ADR 0006: AWS HTTP Deployment](adrs/0006-aws-http-deployment-with-auto-cleanup.md)
- [ADR 0007: OpenShift HTTP Deployment](adrs/0007-openshift-http-deployment-with-auto-cleanup.md)
- [ADR 0008: Git-Sync Ingestion Strategy](adrs/0008-git-sync-ingestion-strategy.md)
- [ADR 0009: Ansible Deployment Automation](adrs/0009-ansible-deployment-automation.md)
- [ADR 0010: MCP Server Testing with Ansible](adrs/0010-mcp-server-testing-with-ansible.md)
- [ADR 0011: CI/CD Pipeline and Security Architecture](adrs/0011-cicd-pipeline-and-security-architecture.md)

### Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Developer guide and project overview
- [PLAN.md](../PLAN.md) - CI/CD and security strategy (source for ADR 0011)
- [README.md](../README.md) - Project README
- [deployment/gcp/ansible/README.md](../deployment/gcp/ansible/README.md) - Ansible deployment guide
- [tests/ansible/README.md](../tests/ansible/README.md) - MCP testing guide

### External Resources

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [AlloyDB Documentation](https://cloud.google.com/alloydb/docs)
- [Vertex AI Embeddings](https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings)
- [Ansible Google Cloud Collection](https://galaxy.ansible.com/google/cloud)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

---

## Change Log

### 2025-11-14 - Initial Creation
- Created comprehensive implementation plan based on all ADRs
- Documented current status (85% complete)
- Focused Phase 4 (CI/CD) on GCP implementation per ADR 0011
- Identified key blockers: AlloyDB provisioning, GitHub Actions implementation
- Established timeline through 2026-Q3 for full multi-cloud parity
- Created sprint tracking for active work
- Added risk mitigation strategies

---

*This document is automatically maintained and updated as the project progresses.*

*Manual edits are preserved during updates. Add notes in the relevant sections.*

*For questions or updates, refer to ADRs in `docs/adrs/` or contact the development team.*
