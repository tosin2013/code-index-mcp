# Repository Guidelines

## Project Structure & Module Organization

### Source Code
Code Index MCP lives in `src/code_index_mcp/`, with `indexing/` managing builders, `services/` exposing MCP tool implementations, `search/` coordinating query utilities, and `utils/` housing cross-cutting helpers. The lightweight CLI bootstrapper is `run.py`, which adds `src/` to `PYTHONPATH` before invoking `code_index_mcp.server`. Sample corpora for language regression reside under `test/sample-projects/` (for example `python/user_management/`). Reserve `tests/` for runnable suites and avoid checking in generated `__pycache__` artifacts.

### Documentation Structure
```
docs/
├── DEPLOYMENT.md          # Cloud deployment guide (GCP, AWS, OpenShift)
└── adrs/                  # Architectural Decision Records
    ├── README.md          # ADR summary and quick reference
    ├── 0001-mcp-stdio-protocol-cloud-deployment-constraints.md
    ├── 0002-cloud-run-http-deployment-with-auto-cleanup.md
    ├── 0003-google-cloud-code-ingestion-with-alloydb.md
    ├── 0004-aws-code-ingestion-with-aurora-and-bedrock.md
    ├── 0005-openshift-code-ingestion-with-milvus.md
    ├── 0006-aws-http-deployment-with-auto-cleanup.md
    └── 0007-openshift-http-deployment-with-auto-cleanup.md
```

**Important Documentation Files**:
- `CLAUDE.md` - Comprehensive guide for Claude Code instances working on this repository
- `README.md` - User-facing documentation with quick start and features
- `AGENTS.md` - This file, repository guidelines for developers and agents

## Deployment Modes

Code Index MCP supports **two deployment modes**:

### Local Mode (Default - stdio transport)
```bash
uv run code-index-mcp
```
- For individual developers and local development
- Direct filesystem access, zero deployment complexity
- Spawned as subprocess by MCP clients

### Cloud Mode (HTTP/SSE transport)
```bash
MCP_TRANSPORT=http uv run code-index-mcp
```
- For teams and organizations
- Multi-user support with authentication
- Auto-scaling, automatic resource cleanup
- Platform options: Google Cloud Run, AWS Lambda/ECS, OpenShift

**See**: `docs/DEPLOYMENT.md` for platform-specific deployment instructions.

## Architectural Decision Records (ADRs)

All major architectural decisions are documented in `docs/adrs/`. The current structure:

**Transport & Core**:
- ADR 0001: MCP Transport Protocols (stdio vs HTTP/SSE)

**HTTP Deployments**:
- ADR 0002: Google Cloud Run HTTP Deployment (~$220/month)
- ADR 0006: AWS HTTP Deployment (~$2.50-65/month)
- ADR 0007: OpenShift HTTP Deployment (~$600-4,887/month)

**Code Ingestion (Semantic Search)**:
- ADR 0003: Google Cloud with AlloyDB + Vertex AI
- ADR 0004: AWS with Aurora PostgreSQL + Bedrock
- ADR 0005: OpenShift with Milvus + vLLM + ODF

### When to Create/Update ADRs

**Create a new ADR when**:
- Adding new deployment targets (e.g., Azure, Heroku)
- Changing transport protocols or server architecture
- Making major refactoring decisions
- Adding significant new features (e.g., RAG, embeddings)
- Changing security models or authentication

**Update existing ADRs when**:
- Implementation reveals better approaches
- Cost structures change significantly
- Technology choices are superseded
- Status changes (Proposed → Implemented → Deprecated)

**ADR Template**:
```markdown
# ADR NNNN: Title

**Status**: Proposed | Implemented | Deprecated | Superseded
**Date**: YYYY-MM-DD
**Decision Maker**: Team/Role
**Related to**: Other ADRs

## Context
The situation and problem motivating this decision

## Decision
The architectural choice being made

## Consequences
What becomes easier or harder, trade-offs, risks

## Related ADRs
Links to related decisions
```

After creating an ADR:
1. Update `docs/adrs/README.md` (add to table and timeline)
2. Update `CLAUDE.md` if it affects development workflow
3. Update `docs/DEPLOYMENT.md` if it's deployment-related

## Build, Test, and Development Commands

Install dependencies with `uv sync` after cloning. Use `uv run code-index-mcp` to launch the MCP server directly, or `uv run python run.py` when you need the local sys.path shim. During development, `uv run code-index-mcp --help` will list available CLI flags, and `uv run python -m code_index_mcp.server` mirrors the published entry point for debugging.

## Coding Style & Naming Conventions
Target Python 3.10+ and follow the `.pylintrc` configuration: 4-space indentation, 100-character line limit, and restrained function signatures (<= 7 parameters). Modules and functions stay `snake_case`, classes use `PascalCase`, and constants remain uppercase with underscores. Prefer explicit imports from sibling packages (`from .services import ...`) and keep logging to stderr as implemented in `server.py`.

## Testing Guidelines
Automated tests should live under `tests/`, mirroring the package hierarchy (`tests/indexing/test_shallow_index.py`, etc.). Use `uv run pytest` (with optional `-k` selectors) for unit and integration coverage, and stage representative fixtures inside `test/sample-projects/` when exercising new language strategies. Document expected behaviors in fixtures' README files or inline comments, and fail fast if tree-sitter support is not available for a language you add.

## Commit & Pull Request Guidelines
Follow the Conventional Commits style seen in history (`feat`, `fix`, `refactor(scope): summary`). Reference issue numbers when relevant and keep subjects under 72 characters. Pull requests should include: 1) a concise problem statement, 2) before/after behavior or performance notes, 3) instructions for reproducing test runs (`uv run pytest`, `uv run code-index-mcp`). Attach updated screenshots or logs when touching developer experience flows, and confirm the file watcher still transitions to "active" in manual smoke tests.

## Security & Credentials

**CRITICAL: Never commit credentials to git!**

The `.gitignore` is configured to exclude:
- `*.key`, `*.pem`, `*.p12`, `*.pfx`
- `gcloud-*.json`, `service-account-*.json`, `aws-credentials.json`
- `.env`, `.env.*` (except `.env.example`)
- `secrets/`, `.aws/`, `.gcloud/`, `.azure/`
- `terraform.tfstate`, `terraform.tfstate.backup`

**Proper credential management**:
1. Use cloud-native secret management:
   - Google Cloud: Secret Manager
   - AWS: AWS Secrets Manager
   - OpenShift: Sealed Secrets or External Secrets Operator
2. Use Workload Identity / IAM roles (no service account keys)
3. Store API keys in secret managers, inject as environment variables
4. Never hardcode credentials in source code or config files

**When deploying**:
- Always use deployment scripts in `deployment/{gcp,aws,openshift}/`
- Review security sections in relevant ADRs
- Test with least-privilege IAM policies first
- Enable cloud provider security scanning (Cloud Security Command Center, AWS Security Hub, etc.)

## Agent Workflow Tips

### Local Development
Always call `set_project_path` before invoking other tools, and prefer `search_code_advanced` with targeted `file_pattern` filters to minimize noise. When editing indexing strategies, run `refresh_index` in between changes to confirm cache rebuilds. Clean up temporary directories via `clear_settings` if you notice stale metadata, and document any new tooling you introduce in this guide.

### Cloud Deployment
When working on cloud deployment features:
1. Read the relevant ADR first (`docs/adrs/000X-*.md`)
2. Check `docs/DEPLOYMENT.md` for platform-specific instructions
3. Test locally with `MCP_TRANSPORT=http` before cloud deployment
4. Never skip security reviews for authentication/authorization code
5. Update cost estimates in ADRs if pricing changes significantly

### Documentation Updates
When making significant changes:
- Update `CLAUDE.md` if it affects development workflow
- Create/update ADRs for architectural decisions
- Update `docs/DEPLOYMENT.md` for deployment-related changes
- Update `README.md` if user-facing features change
- Update this file (`AGENTS.md`) for repository guidelines

## Cloud Deployment Testing

### Local HTTP Mode Testing
Before deploying to cloud, test HTTP transport locally:
```bash
# Terminal 1: Start server in HTTP mode
MCP_TRANSPORT=http PORT=8080 uv run code-index-mcp

# Terminal 2: Test with curl
curl http://localhost:8080/health
```

### Platform-Specific Testing

**Google Cloud Run**:
```bash
# Build and test locally with Cloud Run emulator
docker build -t code-index-mcp .
docker run -p 8080:8080 -e MCP_TRANSPORT=http code-index-mcp

# Deploy to test project first
gcloud config set project YOUR-TEST-PROJECT-ID
cd deployment/gcp && ./deploy.sh
```

**AWS Lambda**:
```bash
# Test Lambda handler locally
uv run python -c "
from code_index_mcp.server import lambda_handler
event = {'httpMethod': 'GET', 'path': '/health'}
print(lambda_handler(event, None))
"

# Deploy to test account first
export AWS_ACCOUNT_ID=YOUR-TEST-ACCOUNT-ID
cd deployment/aws && ./deploy-lambda.sh
```

**OpenShift**:
```bash
# Test with local Kubernetes (minikube/kind)
minikube start
cd deployment/openshift && ./deploy.sh

# Or use OpenShift Local (CRC)
crc start
oc login -u developer https://api.crc.testing:6443
```

### Cleanup After Testing
Always tear down test deployments:
```bash
# Google Cloud
cd deployment/gcp && ./destroy.sh

# AWS
cd deployment/aws && ./destroy.sh

# OpenShift
cd deployment/openshift && ./destroy.sh
```

## Release Preparation Checklist

### Version Updates
- Update the project version everywhere it lives: `pyproject.toml`, `src/code_index_mcp/__init__.py`, and `uv.lock`.
- Add a release note entry to `RELEASE_NOTE.txt` for the new version.
- Update `CHANGELOG.md` if it exists.

### Documentation Review
- Ensure `README.md` reflects current features and deployment options
- Verify all ADRs are up-to-date with implementation status
- Check `docs/DEPLOYMENT.md` has current cost estimates
- Confirm `CLAUDE.md` has accurate development commands

### Testing
- Run full test suite: `uv run pytest`
- Test local stdio mode: `uv run code-index-mcp`
- Test local HTTP mode: `MCP_TRANSPORT=http uv run code-index-mcp`
- Smoke test with MCP Inspector: `npx @modelcontextprotocol/inspector uv run code-index-mcp`

### Git Operations
- Commit the version bump (plus any release artifacts) and push the branch to `origin`.
- Create a git tag for the new version: `git tag v2.X.Y`
- Push the tag to `origin`: `git push origin v2.X.Y`
- Create GitHub release with release notes

## Quick Reference

### Key Files to Check Before Changes
- `CLAUDE.md` - Repository guide for AI assistants
- `docs/adrs/README.md` - ADR summary and quick reference
- Relevant ADR file in `docs/adrs/` - For architectural context
- `.gitignore` - Ensure credentials are excluded

### Common Tasks
- **Add new language support**: Update `src/code_index_mcp/indexing/strategies/`, run `refresh_index`
- **Add new MCP tool**: Update `src/code_index_mcp/server.py` and relevant service
- **Add cloud deployment**: Create new ADR, update `docs/DEPLOYMENT.md`, add deployment scripts
- **Fix security issue**: Review security section in relevant ADR, update `.gitignore` if needed
- **Update dependencies**: `uv sync`, test thoroughly, update `uv.lock`

### Cost-Conscious Development
When adding cloud features, always consider:
- **Scale-to-zero**: Can this run on-demand only?
- **Auto-cleanup**: Will unused resources be cleaned up automatically?
- **Cost estimation**: Document monthly cost impact in ADR
- **Budget alerts**: Recommend setting up cost monitoring
