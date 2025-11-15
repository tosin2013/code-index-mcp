# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Code Index MCP is a Model Context Protocol (MCP) server that provides intelligent code indexing and analysis capabilities for Large Language Models. It enables AI assistants to effectively search, navigate, and understand complex codebases through a combination of tree-sitter AST parsing and fallback strategies.

**Architecture Notes:**

### Current Implementation

The system supports **two modes of operation**:

#### Mode A: Metadata-Only (Local Development)
- Builds **metadata indexes** (file paths, symbols, imports, function signatures)
- Stored in JSON/msgpack format in temp directories
- Code content read **on-demand from filesystem** via MCP resources
- Lightweight, fast, no duplication
- Perfect for local development

#### Mode B: Semantic Search (Cloud Deployment - Phase 3A 🚧)
- **Code ingestion** into vector database for semantic search
- **Google Cloud** (IN PROGRESS - 83% complete):
  - AlloyDB + pgvector for vector similarity search
  - Vertex AI text-embedding-004 for embeddings (768 dimensions)
  - Code chunking with AST-based parsing
  - Natural language code search via MCP tools
  - Infrastructure code ready, pending AlloyDB provisioning
- **AWS** (Planned): Aurora PostgreSQL + Amazon Bedrock (see ADR 0004)
- **OpenShift** (Planned): Milvus + PostgreSQL (see ADR 0005)

## Deployment Modes

This project supports **TWO deployment modes**:

### Mode 1: Local Execution (stdio transport)
```bash
# Run on your machine - current default
uvx code-index-mcp
```
- ✅ Zero deployment complexity
- ✅ Direct filesystem access
- ✅ No cloud costs

### Mode 2: Cloud Deployment (HTTP/SSE transport)
```bash
# Deploy to cloud with HTTP endpoint
MCP_TRANSPORT=http code-index-mcp
```
- ✅ Team sharing and collaboration
- ✅ Auto-scaling serverless deployment
- ✅ Multi-user with authentication
- See **docs/adrs/** for deployment guides

## Essential Commands

### Development Setup

**Important for Mac Development:**
This project requires Python 3.11+ and uses `uv` for dependency management. On Mac, ensure you're using Python 3.11 venv:

```bash
# Create Python 3.11 virtual environment (Mac)
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies using uv (recommended)
uv sync

# Alternative: pip installation
pip install -e .
```

### Running the Server
```bash
# Development mode (local testing)
uv run code-index-mcp

# Production mode (after pip install)
code-index-mcp
```

### Testing and Debugging
```bash
# Debug with MCP Inspector
npx @modelcontextprotocol/inspector uv run code-index-mcp

# Run tests (if pytest is configured)
uv run pytest tests/

# Check Python version
python --version  # Requires 3.10+
```

### Code Quality
```bash
# Lint with pylint
pylint src/code_index_mcp/

# Format code (if using black/ruff)
# Note: Check pyproject.toml for specific formatter configuration
```

## Testing with Ansible

**NEW**: We use the **tosin2013.mcp_audit** Ansible collection for automated MCP server testing across all deployment targets.

### Prerequisites for Testing

**IMPORTANT**: Before running Ansible tests, ensure the project's Python 3.11 venv is set up:

```bash
# 1. Create and activate Python 3.11 virtual environment
cd /Users/tosinakinosho/workspaces/code-index-mcp
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies (includes MCP SDK)
uv sync

# 3. Verify MCP SDK is available
.venv/bin/python -c "import mcp; print('MCP SDK available')"
```

**Why Python 3.11 venv is required**: The test inventory uses the project's `.venv/bin/python` to run the MCP server, ensuring all dependencies (MCP SDK, tree-sitter, etc.) are available. The Ansible modules also need MCP SDK installed in Ansible's Python environment (done automatically when you install `tosin2013.mcp_audit`).

### Quick Start - Test Local Server

```bash
# 1. Install testing dependencies
cd tests/ansible
ansible-galaxy collection install -r requirements.yml

# 2. Run quick tests (stdio mode) - 5 core tests
ansible-playbook test-quick.yml -i inventory/local.yml

# 3. Run full test suite (stdio mode) - comprehensive validation
ansible-playbook test-local.yml -i inventory/local.yml
```

**What it tests**:
- ✅ Server discovery and capabilities
- ✅ All metadata tools (set_project_path, find_files, search_code_advanced, etc.)
- ✅ File resource retrieval
- ✅ Comprehensive validation with pass/fail reporting

### Test Cloud Deployment

```bash
# Set environment variables
export CLOUDRUN_SERVICE_URL="https://code-index-mcp-dev-xxxxx.run.app"
export MCP_API_KEY_DEV="ci_your_api_key_here"

# Run cloud tests (HTTP/SSE mode)
cd tests/ansible
ansible-playbook test-cloud.yml -i inventory/gcp-dev.yml
```

**What it tests**:
- ✅ All metadata tools via HTTP/SSE
- ✅ Semantic search (if AlloyDB deployed)
- ✅ Git ingestion
- ✅ Multi-user isolation

### Test Local HTTP Mode (Matches Cloud Behavior)

**IMPORTANT**: For pre-production validation that ensures local tests match cloud behavior:

```bash
# Terminal 1: Start PostgreSQL
docker compose up -d postgres

# Terminal 2: Start MCP server in HTTP mode (matches cloud transport)
export MCP_TRANSPORT=http
export PORT=8080
export DATABASE_URL=postgresql://postgres:localdevpass@localhost:5432/code_index
uv run code-index-mcp

# Terminal 3: Run cloud test suite against local server
cd tests/ansible
ansible-playbook test-cloud.yml -i inventory/local-http.yml
```

**Why this matters**:
- ✅ **stdio mode** (test-local.yml) is stateless - each tool call = new process
- ✅ **HTTP/SSE mode** (test-cloud.yml) is stateful - persistent server with sessions
- ✅ Testing with local HTTP ensures 100% confidence in cloud deployment
- ✅ PostgreSQL + pgvector = AlloyDB + pgvector (100% database compatibility)

**See**: `docs/LOCAL_CLOUD_TESTING_ALIGNMENT.md` for complete details on transport and database layer compatibility.

### Full Regression Suite

```bash
# Before promoting to production, run full regression
ansible-playbook test-regression.yml -i inventory/gcp-staging.yml
```

**Generates**:
- Comprehensive test report (Markdown)
- Pass/fail statistics
- Recommendations for deployment readiness

### Available Test Playbooks

| Playbook | Purpose | When to Use |
|----------|---------|-------------|
| `test-local.yml` | Local stdio testing | During development, fast feedback |
| `test-cloud.yml` | Cloud HTTP/SSE testing | After deployment, validate cloud features |
| `test-regression.yml` | Full regression suite | Before production deployment |

### Integration with CI/CD

Tests automatically run in GitHub Actions on every deployment:

```yaml
# .github/workflows/test-and-deploy.yml
jobs:
  test-local:
    # Fast local tests first
  deploy-dev:
    # Deploy only if local tests pass
  test-cloud:
    # Validate cloud deployment
  deploy-production:
    # Production deployment only if all tests pass
```

### Testing Architecture

```
Deployment (ADR 0009)          Testing (ADR 0010)
──────────────────            ──────────────────
ansible-playbook deploy.yml   ansible-playbook test-cloud.yml
        ↓                              ↓
  Cloud Run Service            tosin2013.mcp_audit
        ↓                              ↓
   ✅ Deployed                 ✅ Validated
                                       ↓
                         Safe to promote to staging/prod
```

**Key Benefits**:
- ✅ **Automated**: No manual testing needed
- ✅ **Comprehensive**: Tests all MCP tools systematically
- ✅ **Multi-Transport**: stdio (local) and HTTP/SSE (cloud)
- ✅ **CI/CD Ready**: Integrates with GitHub Actions/GitLab CI
- ✅ **Regression Prevention**: Catches breaking changes before production

**Documentation**:
- **ADR 0010**: Testing strategy (docs/adrs/0010-mcp-server-testing-with-ansible.md)
- **Test README**: Testing guide (tests/ansible/README.md)
- **Integration Plan**: Complete setup (docs/MCP_TESTING_INTEGRATION_PLAN.md)

## Architecture Overview

### Transport Layer (Dual-Mode Support)

The server supports **two transport protocols**:

```python
# server.py configuration
def create_mcp_server():
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        # Cloud deployment mode (Cloud Run, Lambda, etc.)
        return FastMCP(
            "CodeIndexer",
            transport="sse",  # Server-Sent Events
            port=int(os.getenv("PORT", 8080)),
            lifespan=indexer_lifespan
        )
    else:
        # Local execution mode (default)
        return FastMCP("CodeIndexer", lifespan=indexer_lifespan)
```

**Key Decisions** (see ADR 0001):
- **stdio transport**: For local development, spawned as subprocess
- **HTTP/SSE transport**: For cloud deployment, standard HTTP endpoint
- Both modes share the same tool implementations

### Service-Oriented Design
The codebase follows a clean service-oriented architecture where MCP tool decorators in `server.py` delegate to domain-specific services:

- **server.py**: MCP server entry point with tool/resource decorators (src/code_index_mcp/server.py:1)
- **Services Layer**: Domain-specific business logic in `src/code_index_mcp/services/`
  - `ProjectManagementService`: Project initialization and configuration
  - `SearchService`: Code search using multiple backend tools
  - `FileDiscoveryService`: File finding and pattern matching
  - `IndexManagementService`: Index building and refreshing
  - `CodeIntelligenceService`: File analysis and symbol extraction
  - `SystemManagementService`: File watcher and system operations
  - `SettingsService`: Configuration management
  - `FileService`: File content retrieval
  - `SemanticSearchService`: Vector similarity search with AlloyDB (Phase 3A)

### Dual-Strategy Parsing Architecture

**Core Concept**: The indexing system uses specialized tree-sitter strategies for 7 languages and a fallback strategy for all others.

**Strategy Factory** (src/code_index_mcp/indexing/strategies/strategy_factory.py:18):
- **Specialized Strategies** (7 languages with tree-sitter AST parsing):
  - Python, JavaScript, TypeScript, Java, Go, Objective-C, Zig
  - Each has a dedicated strategy class (e.g., `PythonParsingStrategy`, `JavaScriptParsingStrategy`)
  - Direct tree-sitter integration with no regex fallbacks - fails fast with clear errors

- **Fallback Strategy** (50+ file types):
  - Used for C/C++, Rust, Ruby, PHP, Shell, and all other supported extensions
  - Provides basic file indexing and metadata extraction
  - Handled by `FallbackParsingStrategy` class

### Index Management Architecture

The system maintains two types of indexes:

1. **Shallow Index** (src/code_index_mcp/indexing/shallow_index_manager.py):
   - Fast file-level indexing
   - Powers `find_files()` tool
   - Automatically refreshed by file watcher
   - Stored in temporary directory with JSON format

2. **Deep Index** (src/code_index_mcp/indexing/deep_index_manager.py):
   - Full symbol extraction (classes, functions, methods)
   - Powers `get_file_summary()` tool
   - Requires explicit `build_deep_index()` call
   - Uses tree-sitter or fallback parsing strategies
   - Cached using msgpack for performance

### Search System Architecture

**Cascading Search Tool Detection** (src/code_index_mcp/project_settings.py:28):
The system auto-detects and prioritizes search tools in this order:
1. `ugrep` (UgrepStrategy) - Preferred, supports native fuzzy search
2. `ripgrep` (RipgrepStrategy) - Fast alternative
3. `ag` (AgStrategy) - Silver Searcher
4. `grep` (GrepStrategy) - System grep
5. `BasicSearchStrategy` - Pure Python fallback

**Important**: Only `ugrep` provides true fuzzy search. Other tools use word boundary matching for partial matches.

### File Watcher System

**Real-time Index Updates** (src/code_index_mcp/services/file_watcher_service.py):
- Automatic shallow index refresh when files change
- Configurable debounce (default: 6 seconds) to batch rapid changes
- Uses `watchdog` library for cross-platform file system monitoring
- Respects `.gitignore` patterns and standard exclusions (node_modules, __pycache__, etc.)
- Only monitors supported file extensions

### Semantic Search Architecture (Phase 3A - Cloud Mode)

**Core Components** for natural language code search:

#### 1. Code Chunking (src/code_index_mcp/ingestion/chunker.py)
- **Chunking Strategies**: FUNCTION, CLASS, FILE, SEMANTIC
- **AST-based Parsing**: Uses tree-sitter for Python, with fallback for other languages
- **Metadata Extraction**: Captures imports, docstrings, parameters, calls
- **Smart Boundaries**: Functions/classes with contextual overlap (3 lines)
- **Deduplication**: SHA256 content hashing to avoid redundant embeddings

Example chunk structure:
```python
CodeChunk(
    file_path="src/auth.py",
    chunk_type="function",
    chunk_name="authenticate_user",
    line_start=42,
    line_end=68,
    language="python",
    content="def authenticate_user(...)...",
    symbols={"imports": ["hashlib"], "calls": ["verify_password"], "docstring": "..."}
)
```

#### 2. Embeddings Generation (src/code_index_mcp/embeddings/vertex_ai.py)
- **Model**: Vertex AI `text-embedding-004` (768 dimensions)
- **Task Types**: RETRIEVAL_DOCUMENT (code), RETRIEVAL_QUERY (search)
- **Batch Processing**: 5 texts per batch with rate limiting (300 req/min)
- **Retry Logic**: 3 attempts with exponential backoff
- **Mock Mode**: `MockVertexAIEmbedder` for local testing without GCP costs
- **Enhanced Context**: Includes file path, language, docstrings in embedding text

#### 3. Ingestion Pipeline (src/code_index_mcp/ingestion/pipeline.py)
- **Workflow**: Chunk → Embed → Store in AlloyDB
- **Database Operations**: Create projects, insert chunks with deduplication
- **Progress Tracking**: Callback-based progress reporting
- **Batch Size**: 50 chunks per database transaction
- **Error Handling**: Continues on individual chunk failures

#### 4. Semantic Search Service (src/code_index_mcp/services/semantic_search_service.py)
- **Vector Similarity**: Cosine distance using pgvector `<=>` operator
- **Multi-tenancy**: User UUID-based row-level security
- **Hybrid Search**: Combines semantic similarity with keyword filtering
- **Result Ranking**: Similarity scores with configurable threshold
- **Search Methods**:
  - `semantic_search()`: Natural language queries
  - `find_similar_code()`: Code-to-code similarity
  - `hybrid_search()`: Semantic + keyword filtering
  - `search_by_function_name()`: Function name search with fuzzy matching

#### 5. Storage Abstraction (src/code_index_mcp/storage/)
- **BaseStorageAdapter**: Abstract interface for all storage backends
- **GCSAdapter**: Google Cloud Storage implementation
- **User Namespace Isolation**: `users/{user_id}/{project_name}/`
- **Async I/O**: Non-blocking operations for scalability
- **Stream Support**: Memory-efficient large file handling

#### 6. Authentication Middleware (src/code_index_mcp/middleware/auth.py)
- **API Key Validation**: Google Secret Manager integration
- **User Context Extraction**: UserContext with permissions and metadata
- **Multi-Provider Support**: GCP (implemented), AWS/OpenShift (planned)
- **Storage Prefix Generation**: Automatic namespace path creation

### Settings and Persistence

**Storage Strategy** (src/code_index_mcp/project_settings.py:54):
- Uses system temp directory by default: `tempfile.gettempdir() / code_indexer / {hash(project_path)}`
- Fallback to project `.code_indexer/` directory if temp is unavailable
- Final fallback to home directory `~/.code_indexer/`
- Each project gets isolated settings based on MD5 hash of project path

## Key Design Patterns

### Error Handling
- All MCP tools use decorators: `@handle_mcp_tool_errors` and `@handle_mcp_resource_errors`
- Located in `src/code_index_mcp/utils/error_handler.py`
- Provides consistent error responses across all tools

### Context Management
- FastMCP lifespan manager pattern (server.py:64)
- `CodeIndexerContext` dataclass holds server state
- File watcher initialized only after project path is set

### Validation and Filtering
- Centralized file filtering in `src/code_index_mcp/utils/file_filter.py`
- Uses `pathspec` library for `.gitignore` pattern matching
- Smart exclusions for build artifacts, dependencies, and temporary files

## Important Implementation Notes

### When Modifying Parsing Strategies
- Specialized strategies are in `src/code_index_mcp/indexing/strategies/`
- Each strategy must implement `ParsingStrategy` base class methods
- Tree-sitter strategies should fail fast (no regex fallbacks)
- Add new language support by creating a new strategy class and registering in `StrategyFactory._initialize_strategies()`

### When Adding MCP Tools
1. Add tool decorator in `server.py`
2. Implement business logic in appropriate service class
3. Use `@handle_mcp_tool_errors(return_type='str'|'dict'|'list')` decorator
4. Access context via `ctx: Context` parameter
5. Return appropriate type matching the decorator

### Available MCP Tools

**Metadata-Based Tools (Local Mode):**
- `set_project_path()`: Initialize project indexing
- `refresh_index()`: Rebuild shallow file index
- `build_deep_index()`: Generate full symbol index
- `search_code_advanced()`: Regex/fuzzy search with file filtering
- `find_files()`: Glob pattern file discovery
- `get_file_summary()`: File structure analysis (requires deep index)
- `get_file_watcher_status()`: Check file watcher status
- `configure_file_watcher()`: Enable/disable auto-refresh
- `get_settings_info()`: View project configuration
- `create_temp_directory()`: Set up index storage
- `check_temp_directory()`: Verify storage location
- `clear_settings()`: Reset cached data
- `refresh_search_tools()`: Re-detect search tools

**Semantic Search Tools (Cloud Mode - Phase 3A):**
- `semantic_search_code(query, language=None, top_k=10)`: Natural language code search
  - Example: `semantic_search_code("authentication logic", language="python")`
  - Returns ranked results with similarity scores
- `find_similar_code(code_snippet, language=None, top_k=5)`: Find similar implementations
  - Example: `find_similar_code("def hash_password(pwd): return bcrypt.hash(pwd)")`
  - Useful for finding code patterns and duplicates
- **`ingest_code_from_git(git_url, project_name=None, branch="main", auth_token=None)`**: **[RECOMMENDED]** Git-sync ingestion
  - **99% token savings** vs file upload
  - **95% faster** incremental updates (pull only changes)
  - **Auto-sync** via webhooks on git push
  - **Supports**: GitHub, GitLab, Bitbucket, Gitea
  - Examples:
    ```python
    # Public repository
    ingest_code_from_git(git_url="https://github.com/user/repo")

    # Private repository with token
    ingest_code_from_git(
        git_url="https://github.com/user/private-repo",
        auth_token="ghp_xxxxxxxxxxxx"
    )

    # Gitea custom domain
    ingest_code_from_git(
        git_url="https://gitea.example.com/user/app",
        auth_token="your_token"
    )
    ```
- `ingest_code_for_search(files=None, directory_path=None, project_name)`: **[DEPRECATED]** Legacy ingestion
  - **Local mode (still supported)**: Pass `directory_path` for direct filesystem access
  - **Cloud mode (deprecated)**: Use `ingest_code_from_git` instead
  - The `files` parameter will be removed in a future version

### Index Rebuilding Triggers
- **Shallow index**: File watcher or manual `refresh_index()` call
- **Deep index**: Only via explicit `build_deep_index()` call
- **After git operations**: Recommend calling `refresh_index()` for large changes

### Testing Considerations
- Sample projects available in `test/sample-projects/` for multiple languages
- Test directory structure: `tests/` for unit tests
- File watcher tests should account for debounce delays
- Use MCP Inspector for integration testing

## Common Workflows

### Adding Support for a New Language

If the language has tree-sitter bindings:
1. Add tree-sitter dependency to `pyproject.toml`
2. Create new strategy class in `src/code_index_mcp/indexing/strategies/`
3. Register in `StrategyFactory._initialize_strategies()` (strategy_factory.py:97)
4. Update documentation in README.md

If no tree-sitter bindings:
1. Add file extensions to `_file_type_mappings` in `StrategyFactory.__init__()` (strategy_factory.py:29)
2. FallbackParsingStrategy will automatically handle it

### Troubleshooting Index Issues
1. Check settings with `get_settings_info()` tool
2. Verify temp directory with `check_temp_directory()` tool
3. Force rebuild with `refresh_index()` or `build_deep_index()`
4. Clear stale data with `clear_settings()` tool
5. Check file watcher status with `get_file_watcher_status()` tool

### Performance Optimization
- Shallow index is fast and sufficient for file discovery
- Deep index is expensive - only build when symbol-level data needed
- File watcher debounce prevents excessive rebuilds during rapid changes
- Index files are cached in temp directory for reuse across sessions

### Cloud Code Ingestion Workflow (Phase 3A - Git-Sync)

**RECOMMENDED: Git-Sync Workflow** (99% token savings, auto-sync on push)

**For cloud-deployed servers - Use Git-Sync:**

1. **Initial Ingestion** (clone and ingest):
   ```python
   # Public repository
   ingest_code_from_git(
       git_url="https://github.com/user/my-project",
       project_name="my-project"
   )

   # Private repository
   ingest_code_from_git(
       git_url="https://github.com/user/private-project",
       auth_token="ghp_xxxxxxxxxxxx",
       project_name="private-project"
   )

   # Gitea custom domain
   ingest_code_from_git(
       git_url="https://gitea.example.com/user/app",
       auth_token="your_gitea_token"
   )
   ```

2. **Incremental Updates** (automatic via webhooks):
   - Set up webhook in Git platform (GitHub/GitLab/Gitea):
     - **Webhook URL**: `https://your-server.run.app/webhook/github` (or `/gitlab`, `/gitea`)
     - **Secret**: Set `GITHUB_WEBHOOK_SECRET` environment variable
     - **Events**: Select "Just the push event"
   - Every `git push` automatically syncs and re-ingests changed files
   - **95% faster** than full re-ingestion

3. **Manual Re-sync** (if needed):
   ```python
   # Just call again - it auto-detects existing repo and pulls changes
   ingest_code_from_git(git_url="https://github.com/user/my-project")
   ```

**Features:**
- ✅ **99% token savings** (no file upload needed)
- ✅ **95% faster** incremental updates (pull only changed files)
- ✅ **Auto-sync** via webhooks on every git push
- ✅ **4 platforms**: GitHub, GitLab, Bitbucket, Gitea
- ✅ **Persistent** repos in Cloud Storage for fast re-syncs
- ✅ **Private repos** supported with personal access tokens
- ✅ **Rate limiting** prevents abuse (30s minimum interval per repo)

**Webhook Configuration:**
- **GitHub**: X-Hub-Signature-256 (HMAC-SHA256)
- **GitLab**: X-Gitlab-Token (secret token)
- **Gitea**: X-Gitea-Signature (HMAC-SHA256)
- **Security**: All webhooks verified with signatures/tokens

---

**DEPRECATED: Legacy File Upload Workflow** (use Git-sync instead)

<details>
<summary>Click to expand legacy workflow (not recommended)</summary>

**For cloud-deployed servers that can't access local files (DEPRECATED):**

1. **Get the upload script**:
   ```bash
   curl -O https://raw.githubusercontent.com/YOUR-REPO/main/upload_code_for_ingestion.py
   ```

2. **Run the upload script**:
   ```bash
   python upload_code_for_ingestion.py /path/to/project \
       --project-name my-app \
       --batch-size 50
   ```

3. **For each batch**:
   - Script prints JSON payload
   - Copy and paste into AI assistant
   - Press Enter when done

**Problems with this approach:**
- 🔴 High token usage (~$5-20 per ingest)
- 🔴 Slow (LLM does all file I/O)
- 🔴 Not scalable (1000+ files problematic)
- 🔴 No incremental updates

**See**: `CLOUD_INGESTION_GUIDE.md` for legacy workflow details.
</details>

## Cloud Deployment Architecture

### Deployment Decision Tree

**For individual developers:**
→ Use **stdio mode** (local execution)
→ No deployment needed, run `uvx code-index-mcp`

**For teams/organizations:**
→ Use **HTTP mode** (cloud deployment)
→ Follow platform-specific guides in docs/adrs/

### Platform-Specific Implementations

#### Google Cloud (ADR 0002, ADR 0003)

**Phase 2A: HTTP Deployment** ✅ COMPLETE
```
Cloud Run (MCP Server, HTTP/SSE)
    ↓
Google Secret Manager (API Keys)
    ↓
Cloud Storage (Code + Indexes)
    ↓
Cloud Scheduler (Auto-cleanup)
```

**Phase 3A: Semantic Search** 🚧 IN PROGRESS (83% complete)
```
Cloud Run (MCP Server, HTTP/SSE)
    ↓
AlloyDB (Vector search with pgvector)
    ↓
Vertex AI (text-embedding-004, 768 dims)
    ↓
Cloud Storage (Code + Indexes)
```

**Key Features:**
- ✅ Auto-scaling to zero (no costs when idle)
- ✅ Automatic resource cleanup via Cloud Scheduler
- ✅ API key authentication with Secret Manager
- ✅ User namespace isolation
- ✅ Built-in Vertex AI integration for embeddings
- 🚧 Natural language code search (infrastructure ready)
- ~$220/month for production workload

**Deploy:**
```bash
# Deploy HTTP server (Phase 2A)
cd deployment/gcp
./deploy.sh

# Provision AlloyDB for semantic search (Phase 3A)
cd deployment/gcp/alloydb
./setup-alloydb.sh dev
```

**Status:**
- HTTP server: Live and tested ✅
- AlloyDB infrastructure: Code ready, pending provisioning ⏳
- Semantic search tools: Implemented and tested (21/21 tests passed) ✅

#### AWS (ADR 0004 - Future)
```
Lambda/ECS (MCP Server)
    ↓
Aurora PostgreSQL (pgvector)
    ↓
Amazon Bedrock (Embeddings)
    ↓
S3 (Code + Indexes)
```

#### OpenShift (ADR 0005 - Future)
```
OpenShift Pod (MCP Server)
    ↓
Milvus (Vector database)
    ↓
PostgreSQL (Metadata)
    ↓
Persistent Volumes (Code)
```

### Security Requirements for Cloud Deployments

**CRITICAL: Never commit credentials to git!**

The `.gitignore` is configured to exclude:
- `*.key`, `*.pem`, `gcloud-*.json`, `service-account-*.json`
- `.env`, `.aws/credentials`, `.azure/credentials`
- All deployment credential files

**Proper credential management:**
1. Use cloud-native secret management (Secret Manager, AWS Secrets, etc.)
2. Use Workload Identity / IAM roles (no service account keys)
3. API keys stored in Secret Manager, injected as environment variables

### Multi-Project Support in Cloud Mode

**Per-user isolation:**
```
Storage Structure:
/projects/{user_id}/{project_name}/
    ├── code/
    ├── indexes/
    └── embeddings/
```

**How it works:**
1. User authenticates with API key
2. MCP server enforces namespace isolation
3. Each user can have multiple projects
4. Automatic cleanup of inactive projects (configurable TTL)

### Resource Cleanup Automation

All cloud deployments include **automatic cleanup**:

1. **Cloud Scheduler jobs**: Daily cleanup of idle projects (>30 days)
2. **Storage lifecycle rules**: Archive cold data, delete old data
3. **Auto-scale to zero**: No compute costs when inactive
4. **Budget alerts**: Prevent cost overruns

**Manual cleanup:**
```bash
cd deployment/gcp
./destroy.sh  # Removes all cloud resources
```

## Architectural Decision Records (ADRs)

All major architectural decisions are documented in `docs/adrs/`:

- **ADR 0001**: MCP Transport Protocols and Cloud Deployment Architecture
  - Why we support both stdio and HTTP/SSE transports
  - Trade-offs between local and cloud deployment

- **ADR 0002**: Cloud Run HTTP Deployment with Automatic Resource Cleanup
  - How to deploy to Google Cloud Run
  - Multi-user support and authentication
  - Automatic resource cleanup strategies
  - Cost analysis and optimization

- **ADR 0003**: Google Cloud Code Ingestion with AlloyDB (Phase 3A - IN PROGRESS)
  - Semantic search using AlloyDB + pgvector
  - Vertex AI embedding generation (text-embedding-004, 768 dims)
  - Vector similarity search implementation
  - GCP-native architecture
  - Status: Infrastructure code complete (83%), pending AlloyDB provisioning

- **ADR 0004**: AWS Code Ingestion Strategy (Planned - Phase 3B)
  - Aurora PostgreSQL + Amazon Bedrock
  - Platform-specific optimizations

- **ADR 0005**: OpenShift Code Ingestion Strategy (Planned - Phase 3C)
  - Milvus vector database
  - On-premise deployment considerations

- **ADR 0006**: AWS HTTP Deployment with Automatic Resource Cleanup (Planned - Phase 2B)
  - Lambda/ECS deployment options
  - AWS Secrets Manager authentication
  - S3 storage adapter
  - EventBridge for automatic cleanup

- **ADR 0007**: OpenShift HTTP Deployment with Automatic Resource Cleanup (Planned - Phase 2C)
  - Kubernetes pod deployment
  - Sealed Secrets for authentication
  - Persistent Volumes for storage
  - CronJob for automatic cleanup

- **ADR 0008**: Git-Sync Ingestion Strategy for Cloud Deployments ✅ COMPLETE
  - Direct Git repository cloning and syncing (99% token savings vs file upload)
  - Automatic incremental updates via webhooks (GitHub, GitLab, Gitea, Bitbucket)
  - 95% faster updates (pull only changed files)
  - Cloud Storage (GCS) backend for repository persistence
  - `ingest_code_from_git` MCP tool for seamless code ingestion
  - Replaces legacy file upload approach
  - Status: 100% complete (2,700 lines, 54/54 tests passing)

- **ADR 0009**: Ansible Deployment Automation for Google Cloud ✅ COMPLETE
  - Idempotent, declarative deployment playbooks (replaces bash scripts)
  - Multi-environment support (dev/staging/prod) with single playbook
  - Comprehensive roles: prerequisites, storage, IAM, secrets, build, deploy, schema, cleanup
  - Utility operations: generate_api_key, query_database, verify_schema, test_connection, teardown
  - CI/CD ready (GitHub Actions, GitLab CI integration)
  - Testing and rollback capabilities
  - Status: 100% complete, production-ready (2,000+ lines)

- **ADR 0010**: MCP Server Testing and Validation with Ansible 🚧 IN PROGRESS
  - Automated testing using tosin2013.mcp_audit Ansible collection
  - Multi-transport testing (stdio for local, HTTP/SSE for cloud)
  - Comprehensive tool validation (all MCP tools systematically tested)
  - LLM integration testing (Ollama, OpenRouter, vLLM)
  - Regression prevention with full test suites
  - CI/CD integration for automated validation on every deployment
  - Test playbooks: test-local.yml, test-cloud.yml, test-llm-integration.yml, test-regression.yml
  - Status: Phase 1 complete, Phase 2-6 planned

- **ADR 0011**: CI/CD Pipeline and Security Architecture ✅ COMPLETE
  - Comprehensive CI/CD framework for multi-cloud deployments (GCP, AWS, OpenShift)
  - GitHub Actions workflows with multi-stage pipeline (security, test, build, deploy, verify)
  - Tekton pipelines for OpenShift-native GitOps
  - Multi-layer security scanning (Gitleaks, Trivy, Bandit)
  - OIDC Workload Identity for keyless authentication (no service account keys)
  - Controlled deletion with manual approval gates
  - Infrastructure as Code (Terraform) + Configuration as Code (Ansible)
  - Integration with ADR 0009 (Ansible deployment) and ADR 0010 (MCP testing)
  - Status: 100% complete, production-ready

**Implementation Tracking:**
- See `docs/IMPLEMENTATION_PLAN.md` for detailed task breakdowns and progress
- Phase 2A (GCP HTTP): 100% complete ✅
- Phase 3A (GCP Semantic Search): 83% complete 🚧
  - ✅ AlloyDB infrastructure code (Terraform + SQL schema)
  - ✅ Code chunking with AST parsing
  - ✅ Vertex AI embedding integration
  - ✅ Ingestion pipeline
  - ✅ Semantic search service + MCP tools
  - ⏳ AlloyDB cluster provisioning
  - ⏳ Real-world testing with large codebase
  - ⏳ Performance benchmarking

**When to create/update ADRs:**
- Adding new deployment targets
- Changing transport protocols
- Major architectural refactors
- Performance optimization strategies
- Security model changes
- Adding new cloud provider integrations
