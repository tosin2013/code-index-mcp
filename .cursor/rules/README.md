# Cursor AI Rules for Code Index MCP

This directory contains automated Cursor AI rules that enforce repository guidelines from `AGENTS.md`. These rules are automatically applied when working on the project in Cursor IDE.

## Rule Files

### 1. `coding-standards.mdc`
**Scope**: All Python files (`**/*.py`)

Enforces:
- Python 3.10+ requirement
- 4-space indentation, 100-character line limit
- Naming conventions (snake_case, PascalCase, UPPER_CASE)
- Function signature limits (≤7 parameters)
- Module organization patterns

### 2. `security-rules.mdc`
**Scope**: All files (`**/*`)

Enforces:
- Never commit credentials, API keys, or secrets
- Use cloud-native secret management (Secret Manager, AWS Secrets, Sealed Secrets)
- Proper `.gitignore` configuration for sensitive files
- Security review requirements for authentication/authorization code
- Least-privilege IAM policies

### 3. `documentation-workflow.mdc`
**Scope**: Documentation files (`docs/**/*.md`, `*.md`)

Enforces:
- ADR creation triggers (new deployments, architecture changes, new features)
- ADR update requirements (implementation changes, cost updates, status changes)
- Documentation cascade (update ADR → CLAUDE.md → DEPLOYMENT.md → README.md → AGENTS.md)
- ADR template structure compliance

### 4. `testing-requirements.mdc`
**Scope**: Test files (`tests/**/*.py`, `test/**/*`)

Enforces:
- Test organization (mirror package hierarchy)
- Test execution commands (`uv run pytest`)
- Fixture placement in `test/sample-projects/`
- Pre-release testing checklist (stdio mode, HTTP mode, MCP Inspector)

### 5. `commit-guidelines.mdc`
**Scope**: All files (`**/*`)

Enforces:
- Conventional Commits format (`feat:`, `fix:`, `refactor(scope):`)
- 72-character commit subject limit
- PR requirements (problem statement, before/after notes, reproduction steps)
- Pre-commit testing requirements

### 6. `deployment-workflow.mdc`
**Scope**: Deployment files (`deployment/**/*`, `src/code_index_mcp/server.py`)

Enforces:
- ADR review before deployment work
- Local HTTP testing before cloud deployment
- Platform-specific testing procedures (GCP, AWS, OpenShift)
- Test environment deployment before production
- Cleanup script execution requirements

### 7. `release-process.mdc`
**Scope**: Version files (`pyproject.toml`, `__init__.py`, `uv.lock`, release notes)

Enforces:
- Version synchronization across files
- Documentation review checklist
- Comprehensive testing (pytest, stdio, HTTP, MCP Inspector)
- Git tagging and GitHub release procedures

### 8. `agent-workflow.mdc`
**Scope**: Python files (`**/*.py`)

Enforces:
- MCP tool usage patterns (`set_project_path` first, `search_code_advanced` with filters)
- Index management workflow (`refresh_index` after strategy changes)
- Development commands (`uv sync`, `uv run code-index-mcp`)
- Common task procedures (add language support, add MCP tool, update dependencies)

### 9. `cost-conscious-development.mdc`
**Scope**: Deployment and ADR files (`deployment/**/*`, `docs/adrs/*.md`)

Enforces:
- Scale-to-zero considerations
- Auto-cleanup implementation requirements
- Cost estimation documentation in ADRs
- Budget alert recommendations
- Serverless-first architecture choices

## How Rules Work

Cursor AI automatically applies these rules when:
- Creating or editing files matching the glob patterns
- Making architectural decisions
- Preparing commits and PRs
- Deploying to cloud platforms
- Creating releases

## Maintenance

When updating `AGENTS.md`:
1. Review which rules need updates
2. Modify the corresponding `.mdc` files
3. Keep rule instructions clear and imperative
4. Test rule effectiveness with sample code changes
5. Update this README if rule purposes change

## Rule Format

Each `.mdc` file follows this structure:
```markdown
---
rule_type: auto
description: "[Brief summary of the rule's purpose]"
globs: ["**/*.py", "**/*.js"]
---

[Clear, imperative instruction 1]
[Clear, imperative instruction 2]
...
```

## References

- **Source**: `AGENTS.md` - Repository guidelines
- **Implementation Plan**: `docs/IMPLEMENTATION_PLAN.md` - Feature roadmap
- **Development Guide**: `CLAUDE.md` - Development workflow documentation
- **ADRs**: `docs/adrs/` - Architectural decisions
