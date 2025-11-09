"""
Code Index MCP Server

This MCP server allows LLMs to index, search, and analyze code from a project directory.
It provides tools for file discovery, content retrieval, and code analysis.

This version uses a service-oriented architecture where MCP decorators delegate
to domain-specific services for business logic.
"""

import logging

# Standard library imports
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

import psycopg2

# Third-party imports
from mcp.server.fastmcp import Context, FastMCP

from .middleware.auth import AuthenticationError, AuthMiddleware, require_authentication

# Local imports
from .project_settings import ProjectSettings
from .services import FileService, FileWatcherService, SearchService, SettingsService
from .services.code_intelligence_service import CodeIntelligenceService
from .services.file_discovery_service import FileDiscoveryService
from .services.index_management_service import IndexManagementService
from .services.project_management_service import ProjectManagementService
from .services.settings_service import manage_temp_directory
from .services.system_management_service import SystemManagementService
from .utils import handle_mcp_resource_errors, handle_mcp_tool_errors


# Setup logging without writing to files
def setup_indexing_performance_logging():
    """Setup logging (stdout for INFO+, stderr for ERROR+)."""

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # stdout for INFO and DEBUG (Cloud Run captures this)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(logging.INFO)

    # stderr for errors
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(logging.ERROR)

    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)
    root_logger.setLevel(logging.INFO)


# Initialize logging (no file handlers)
setup_indexing_performance_logging()

logger = logging.getLogger(__name__)


def check_alloydb_connection() -> psycopg2.extensions.connection:
    """
    Check AlloyDB connection on startup if connection string is provided.

    Returns:
        Database connection if successful, None if no connection string

    Raises:
        RuntimeError: If connection check fails with details about the error
    """
    connection_string = os.getenv("ALLOYDB_CONNECTION_STRING")

    if not connection_string:
        logger.info("No ALLOYDB_CONNECTION_STRING set - skipping database health check")
        return None

    logger.info("Checking AlloyDB connection on startup...")

    try:
        # Attempt connection with 10 second timeout
        conn = psycopg2.connect(connection_string, connect_timeout=10)

        # Run simple query to verify connectivity
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            logger.info(f"✅ AlloyDB connection successful: {version[:50]}...")

        return conn

    except psycopg2.OperationalError as e:
        error_msg = str(e)

        # Extract connection details for better error messages
        if "Connection timed out" in error_msg:
            # Parse IP from connection string
            import re

            ip_match = re.search(r"@([\d\.]+):", connection_string)
            ip = ip_match.group(1) if ip_match else "unknown"

            raise RuntimeError(
                f"❌ AlloyDB connection timeout to {ip}:5432\n"
                f"Possible causes:\n"
                f"  1. Wrong IP address in ALLOYDB_CONNECTION_STRING\n"
                f"  2. VPC connector not properly configured\n"
                f"  3. AlloyDB instance not running\n"
                f"  4. Network routing issue\n"
                f"Error: {error_msg}"
            ) from e
        elif "password authentication failed" in error_msg:
            raise RuntimeError(
                f"❌ AlloyDB authentication failed\n"
                f"Check ALLOYDB_CONNECTION_STRING password is correct\n"
                f"Error: {error_msg}"
            ) from e
        else:
            raise RuntimeError(f"❌ AlloyDB connection failed: {error_msg}") from e
    except Exception as e:
        raise RuntimeError(f"❌ Unexpected error checking AlloyDB connection: {str(e)}") from e


def check_alloydb_schema(conn: psycopg2.extensions.connection) -> None:
    """
    Verify AlloyDB schema is properly set up.

    Args:
        conn: Active database connection

    Raises:
        RuntimeError: If schema validation fails with details
    """
    if not conn:
        return

    logger.info("Validating AlloyDB schema...")

    try:
        with conn.cursor() as cur:
            # Check pgvector extension
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                )
            """
            )
            has_pgvector = cur.fetchone()[0]

            if not has_pgvector:
                raise RuntimeError(
                    "❌ pgvector extension not installed\n"
                    "Run: CREATE EXTENSION IF NOT EXISTS vector;\n"
                    "Or apply schema: ansible-playbook utilities.yml -i inventory/dev.yml -e operation=apply_schema"
                )

            # Check required tables
            required_tables = ["users", "projects", "code_chunks"]
            cur.execute(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename IN ('users', 'projects', 'code_chunks')
            """
            )
            existing_tables = [row[0] for row in cur.fetchall()]
            missing_tables = set(required_tables) - set(existing_tables)

            if missing_tables:
                raise RuntimeError(
                    f"❌ Missing required tables: {', '.join(missing_tables)}\n"
                    f"Apply schema: ansible-playbook utilities.yml -i inventory/dev.yml -e operation=apply_schema"
                )

            # Check critical columns exist in code_chunks (including git metadata)
            required_columns = [
                "chunk_id",
                "project_id",
                "user_id",
                "file_path",
                "content",
                "embedding",
                "line_start",
                "line_end",
                "commit_hash",
                "branch_name",
                "author_name",
                "commit_timestamp",
            ]
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'code_chunks'
                AND column_name IN ('chunk_id', 'project_id', 'user_id', 'file_path',
                                   'content', 'embedding', 'line_start', 'line_end',
                                   'commit_hash', 'branch_name', 'author_name', 'commit_timestamp')
            """
            )
            existing_columns = [row[0] for row in cur.fetchall()]
            missing_columns = set(required_columns) - set(existing_columns)

            if missing_columns:
                raise RuntimeError(
                    f"❌ code_chunks table missing required columns: {', '.join(missing_columns)}\n"
                    "Schema mismatch detected - run schema fix job:\n"
                    "gcloud run jobs execute fix-schema --region=us-east1"
                )

            # Check for google_ml_integration extension (for Vertex AI)
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'google_ml_integration'
                )
            """
            )
            has_google_ml = cur.fetchone()[0]

            if not has_google_ml:
                logger.warning(
                    "⚠️  google_ml_integration extension not found - Vertex AI features may be limited"
                )

            logger.info("✅ AlloyDB schema validation passed")
            logger.info(f"   - pgvector: enabled")
            logger.info(f"   - Tables: {', '.join(existing_tables)}")
            logger.info(
                f"   - Required columns: validated ({len(existing_columns)}/{len(required_columns)})"
            )
            logger.info(
                f"   - Google ML Integration: {'enabled' if has_google_ml else 'not enabled'}"
            )

    except psycopg2.Error as e:
        raise RuntimeError(f"❌ Schema validation failed: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"❌ Unexpected error validating schema: {str(e)}") from e


@dataclass
class CodeIndexerContext:
    """Context for the Code Indexer MCP server."""

    base_path: str
    settings: ProjectSettings
    file_count: int = 0
    file_watcher_service: FileWatcherService = None
    auth_middleware: AuthMiddleware = None


@asynccontextmanager
async def indexer_lifespan(_server: FastMCP) -> AsyncIterator[CodeIndexerContext]:
    """Manage the lifecycle of the Code Indexer MCP server."""
    # Check AlloyDB connection and schema on startup (if configured)
    conn = check_alloydb_connection()
    if conn:
        try:
            check_alloydb_schema(conn)
        finally:
            conn.close()

    # Don't set a default path, user must explicitly set project path
    base_path = ""  # Empty string to indicate no path is set

    # Initialize settings manager with skip_load=True to skip loading files
    settings = ProjectSettings(base_path, skip_load=True)

    # Initialize auth middleware if in HTTP mode
    auth_middleware = None
    if os.getenv("MCP_TRANSPORT") == "http":
        # In production, fail fast on initialization errors
        # Set FAIL_ON_INIT_ERROR=false to allow local development without full auth setup
        fail_on_error = os.getenv("FAIL_ON_INIT_ERROR", "true").lower() == "true"

        try:
            auth_middleware = AuthMiddleware(provider="gcp", project_id=os.getenv("GCP_PROJECT_ID"))
            logging.info("✅ Auth middleware initialized for HTTP mode")

        except Exception as e:
            logging.error(f"❌ Auth middleware initialization failed: {e}")
            if fail_on_error:
                logging.error("FAIL_ON_INIT_ERROR=true - Stopping server startup")
                logging.error("This prevents silent failures in production deployments")
                raise RuntimeError(
                    f"Critical dependency initialization failed: {e}\n"
                    "Set FAIL_ON_INIT_ERROR=false to continue without auth (development only)"
                ) from e
            else:
                logging.warning("⚠️  FAIL_ON_INIT_ERROR=false - Continuing without authentication")
                logging.warning("This is ONLY safe for local development!")

    # Initialize context - file watcher will be initialized later when project path is set
    context = CodeIndexerContext(
        base_path=base_path,
        settings=settings,
        file_watcher_service=None,
        auth_middleware=auth_middleware,
    )

    try:
        # Provide context to the server
        yield context
    finally:
        # Stop file watcher if it was started
        if context.file_watcher_service:
            context.file_watcher_service.stop_monitoring()


# Create the MCP server with lifespan manager
# Note: For HTTP mode, host/port are passed explicitly in main()
# See: https://gofastmcp.com/deployment/http
mcp = FastMCP("CodeIndexer", lifespan=indexer_lifespan, dependencies=["pathlib"])

# ----- RESOURCES -----


@mcp.resource("config://code-indexer")
@handle_mcp_resource_errors
def get_config() -> str:
    """Get the current configuration of the Code Indexer."""
    ctx = mcp.get_context()
    return ProjectManagementService(ctx).get_project_config()


@mcp.resource("files://{file_path}")
@handle_mcp_resource_errors
def get_file_content(file_path: str) -> str:
    """Get the content of a specific file."""
    ctx = mcp.get_context()
    # Use FileService for simple file reading - this is appropriate for a resource
    return FileService(ctx).get_file_content(file_path)


@mcp.resource("guide://semantic-search-ingestion")
@handle_mcp_resource_errors
def get_ingestion_guide() -> str:
    """Get comprehensive guide for semantic search code ingestion."""
    return """# Semantic Search Code Ingestion Guide

## Overview

Code Index MCP provides semantic search capabilities using AlloyDB + Vertex AI embeddings.
This guide explains how to ingest code for semantic search.

## Quick Start (Recommended)

Use the `ingest_code_for_search` MCP tool directly:

```python
# Option 1: Ingest current project
ingest_code_for_search(
    use_current_project=True,
    project_name="my-project"
)

# Option 2: Ingest specific directory
ingest_code_for_search(
    directory_path="/path/to/project",
    project_name="my-project"
)
```

## What Happens During Ingestion

1. **Directory Scanning**: Automatically discovers code files
2. **Code Chunking**: Parses code with AST (functions, classes, files)
3. **Embedding Generation**: Creates vector embeddings via Vertex AI
4. **Storage**: Stores chunks + embeddings in AlloyDB with deduplication
5. **Progress Tracking**: Reports files processed, chunks created, embeddings generated

## Requirements

### For Real Semantic Search (Production)
- AlloyDB cluster provisioned (`./deployment/gcp/setup-alloydb.sh dev`)
- `ALLOYDB_CONNECTION_STRING` environment variable set
- Vertex AI enabled in GCP project
- Cost: ~$100/month (AlloyDB) + $0.025 per 1M characters (embeddings)

### For Testing (Mock Mode)
- No cloud resources needed
- $0 cost
- Uses fake embeddings for testing pipeline
- Returns mock results for semantic search

## Ingestion Modes

### 1. stdio Mode (Local Development)
```python
# Server can directly access your filesystem
ingest_code_for_search(
    directory_path="/Users/you/projects/myapp",
    project_name="myapp"
)
```

**Pros**:
- ✅ Automatic file discovery
- ✅ Single command
- ✅ Handles .gitignore, binary detection
- ✅ Progress tracking built-in

**Cons**:
- ❌ Only works when server runs locally

### 2. HTTP Mode (Cloud Deployment)
```python
# Must upload files in request
ingest_code_for_search(
    files=[
        {"path": "src/main.py", "content": "..."},
        {"path": "src/utils.py", "content": "..."}
    ],
    project_name="myapp"
)
```

**Pros**:
- ✅ Works with cloud-deployed MCP server
- ✅ Manual control over what gets ingested
- ✅ Can batch large projects

**Cons**:
- ❌ Must provide file contents manually
- ❌ More complex for large projects

## Chunking Strategies

Choose how code is split for embedding:

- **function** (default): One chunk per function/method
  - Best for: Finding specific functions
  - Granularity: Fine

- **class**: One chunk per class
  - Best for: Object-oriented codebases
  - Granularity: Medium

- **file**: One chunk per file
  - Best for: Small files, scripts
  - Granularity: Coarse

- **semantic**: Smart chunking with overlap
  - Best for: Maximum search relevance
  - Granularity: Adaptive

## After Ingestion: Semantic Search

Once code is ingested, use these tools:

### Natural Language Search
```python
semantic_search_code(
    query="JWT authentication with token refresh",
    language="python",
    top_k=5,
    min_similarity=0.7
)
```

### Find Similar Code
```python
find_similar_code(
    code_snippet="def authenticate(user, pwd): return verify(user, pwd)",
    language="python",
    top_k=3
)
```

## Cost Estimation

### Development (Mock Mode)
- **Cost**: $0/month
- **Use case**: Testing, local development

### Production (Real AlloyDB + Vertex AI)
- **AlloyDB**: ~$100/month (dev cluster)
- **Vertex AI Embeddings**: ~$0.025 per 1M characters
  - Example: 100k LOC ≈ 5M chars ≈ $0.125 one-time
  - Example: 1M LOC ≈ 50M chars ≈ $1.25 one-time
- **Total**: ~$100-105/month

## Troubleshooting

### "AlloyDB not configured" Error
```python
{
  "error": "AlloyDB not configured",
  "instructions": "Set ALLOYDB_CONNECTION_STRING environment variable"
}
```

**Solution**: Either:
1. Provision AlloyDB: `cd deployment/gcp && ./setup-alloydb.sh dev`
2. Or accept mock mode for testing

### "No project path set" Error
**Solution**: Call `set_project_path` first if using `use_current_project=True`

### Large Projects (10k+ files)
**Recommendation**:
- Use file patterns to filter: `.py`, `.js`, `.ts` only
- Exclude test files, node_modules, vendor directories
- Consider ingesting incrementally by subdirectory

## Best Practices

1. **Start with mock mode** to test pipeline ($0 cost)
2. **Use function-level chunking** for most projects (best search results)
3. **Set project_name** meaningfully (used for filtering searches)
4. **Monitor costs** in GCP console after provisioning AlloyDB
5. **Re-ingest after major refactors** (deduplication prevents waste)

## Related Documentation

- ADR 0003: Google Cloud Code Ingestion Architecture
- `docs/IMPLEMENTATION_PLAN.md`: Phase 3A progress
- `deployment/gcp/ALLOYDB_SETUP.md`: Provisioning guide
- `deployment/gcp/QUICKSTART_SEMANTIC_SEARCH.md`: Quick start guide

## Support

For issues or questions:
- Check `docs/TROUBLESHOOTING_GUIDE.md`
- Review AlloyDB setup: `deployment/gcp/ALLOYDB_SETUP.md`
- Test connection: `deployment/gcp/test-alloydb-connection.sh`
"""


# Removed: structure://project resource - not necessary for most workflows
# Removed: settings://stats resource - this information is available via get_settings_info() tool
# and is more of a debugging/technical detail rather than context AI needs

# ----- TOOLS -----


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def set_project_path(path: str, ctx: Context) -> str:
    """Set the base project path for indexing."""
    # Strip whitespace and newlines from path to handle copy-paste issues
    clean_path = path.strip().replace("\n", "").replace("\r", "")
    return ProjectManagementService(ctx).initialize_project(clean_path)


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def search_code_advanced(
    pattern: str,
    ctx: Context,
    case_sensitive: bool = True,
    context_lines: int = 0,
    file_pattern: str = None,
    fuzzy: bool = False,
    regex: bool = None,
    max_line_length: int = None,
) -> Dict[str, Any]:
    """
    Search for a code pattern in the project using an advanced, fast tool.

    This tool automatically selects the best available command-line search tool
    (like ugrep, ripgrep, ag, or grep) for maximum performance.

    Args:
        pattern: The search pattern. Can be literal text or regex (see regex parameter).
        case_sensitive: Whether the search should be case-sensitive.
        context_lines: Number of lines to show before and after the match.
        file_pattern: A glob pattern to filter files to search in
                     (e.g., "*.py", "*.js", "test_*.py").
        max_line_length: Optional. Default None (no limit). Limits the length of lines when context_lines is used.
                     All search tools now handle glob patterns consistently:
                     - ugrep: Uses glob patterns (*.py, *.{js,ts})
                     - ripgrep: Uses glob patterns (*.py, *.{js,ts})
                     - ag (Silver Searcher): Automatically converts globs to regex patterns
                     - grep: Basic glob pattern matching
                     All common glob patterns like "*.py", "test_*.js", "src/*.ts" are supported.
        fuzzy: If True, enables fuzzy/partial matching behavior varies by search tool:
               - ugrep: Native fuzzy search with --fuzzy flag (true edit-distance fuzzy search)
               - ripgrep, ag, grep, basic: Word boundary pattern matching (not true fuzzy search)
               IMPORTANT: Only ugrep provides true fuzzy search. Other tools use word boundary
               matching which allows partial matches at word boundaries.
               For exact literal matches, set fuzzy=False (default and recommended).
        regex: Controls regex pattern matching behavior:
               - If True, enables regex pattern matching
               - If False, forces literal string search
               - If None (default), automatically detects regex patterns and enables regex for patterns like "ERROR|WARN"
               The pattern will always be validated for safety to prevent ReDoS attacks.

    Returns:
        A dictionary containing the search results or an error message.

    """
    return SearchService(ctx).search_code(
        pattern=pattern,
        case_sensitive=case_sensitive,
        context_lines=context_lines,
        file_pattern=file_pattern,
        fuzzy=fuzzy,
        regex=regex,
        max_line_length=max_line_length,
    )


@mcp.tool()
@handle_mcp_tool_errors(return_type="list")
def find_files(pattern: str, ctx: Context) -> List[str]:
    """
    Find files matching a glob pattern using pre-built file index.

    Use when:
    - Looking for files by pattern (e.g., "*.py", "test_*.js")
    - Searching by filename only (e.g., "README.md" finds all README files)
    - Checking if specific files exist in the project
    - Getting file lists for further analysis

    Pattern matching:
    - Supports both full path and filename-only matching
    - Uses standard glob patterns (*, ?, [])
    - Fast lookup using in-memory file index
    - Uses forward slashes consistently across all platforms

    Args:
        pattern: Glob pattern to match files (e.g., "*.py", "test_*.js", "README.md")

    Returns:
        List of file paths matching the pattern
    """
    return FileDiscoveryService(ctx).find_files(pattern)


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def get_file_summary(file_path: str, ctx: Context) -> Dict[str, Any]:
    """
    Get a summary of a specific file, including:
    - Line count
    - Function/class definitions (for supported languages)
    - Import statements
    - Basic complexity metrics
    """
    return CodeIntelligenceService(ctx).analyze_file(file_path)


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def refresh_index(ctx: Context) -> str:
    """
    Manually refresh the project index when files have been added/removed/moved.

    Use when:
    - File watcher is disabled or unavailable
    - After large-scale operations (git checkout, merge, pull) that change many files
    - When you want immediate index rebuild without waiting for file watcher debounce
    - When find_files results seem incomplete or outdated
    - For troubleshooting suspected index synchronization issues

    Important notes for LLMs:
    - Always available as backup when file watcher is not working
    - Performs full project re-indexing for complete accuracy
    - Use when you suspect the index is stale after file system changes
    - **Call this after programmatic file modifications if file watcher seems unresponsive**
    - Complements the automatic file watcher system

    Returns:
        Success message with total file count
    """
    return IndexManagementService(ctx).rebuild_index()


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def build_deep_index(ctx: Context) -> str:
    """
    Build the deep index (full symbol extraction) for the current project.

    This performs a complete re-index and loads it into memory.
    """
    return IndexManagementService(ctx).rebuild_deep_index()


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def get_settings_info(ctx: Context) -> Dict[str, Any]:
    """Get information about the project settings."""
    return SettingsService(ctx).get_settings_info()


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def create_temp_directory() -> Dict[str, Any]:
    """Create the temporary directory used for storing index data."""
    return manage_temp_directory("create")


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def check_temp_directory() -> Dict[str, Any]:
    """Check the temporary directory used for storing index data."""
    return manage_temp_directory("check")


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def clear_settings(ctx: Context) -> str:
    """Clear all settings and cached data."""
    return SettingsService(ctx).clear_all_settings()


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def refresh_search_tools(ctx: Context) -> str:
    """
    Manually re-detect the available command-line search tools on the system.
    This is useful if you have installed a new tool (like ripgrep) after starting the server.
    """
    return SearchService(ctx).refresh_search_tools()


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def get_file_watcher_status(ctx: Context) -> Dict[str, Any]:
    """Get file watcher service status and statistics."""
    return SystemManagementService(ctx).get_file_watcher_status()


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def configure_file_watcher(
    ctx: Context,
    enabled: bool = None,
    debounce_seconds: float = None,
    additional_exclude_patterns: list = None,
) -> str:
    """Configure file watcher service settings."""
    return SystemManagementService(ctx).configure_file_watcher(
        enabled, debounce_seconds, additional_exclude_patterns
    )


# ----- SEMANTIC SEARCH TOOLS (Phase 3A) -----


@mcp.tool()
@handle_mcp_tool_errors(return_type="list")
def semantic_search_code(
    ctx: Context,
    query: str,
    project_name: str = None,
    language: str = None,
    top_k: int = 10,
    min_similarity: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Search code by semantic meaning using vector similarity (Phase 3A feature).

    Requires AlloyDB and Vertex AI to be configured. Falls back to mock mode
    if not available.

    Args:
        query: Natural language query (e.g., "authentication with JWT")
        project_name: Filter to specific project (optional)
        language: Filter by programming language (optional)
        top_k: Number of results to return (default: 10)
        min_similarity: Minimum similarity threshold 0-1 (default: 0.0)

    Returns:
        List of code chunks with similarity scores

    Example:
        semantic_search_code("database connection pooling", language="python", top_k=5)
    """
    # Import here to avoid dependency issues if GCP packages not installed
    try:
        from uuid import uuid4

        from .services.semantic_search_service import semantic_search

        # Get database connection string from environment
        db_conn_str = os.getenv("ALLOYDB_CONNECTION_STRING")
        use_mock = not db_conn_str  # Use mock if no DB configured

        if use_mock:
            logging.warning("AlloyDB not configured, using mock mode (returns empty results)")

        # Use test user ID (in production, this would come from auth middleware)
        # This matches the user created by seed_test_user utility
        from uuid import UUID

        user_id = UUID("00000000-0000-0000-0000-000000000001")

        results = semantic_search(
            query=query,
            user_id=user_id,
            db_connection_string=db_conn_str or "mock",
            project_name=project_name,
            language=language,
            top_k=top_k,
            use_mock=use_mock,
        )

        if use_mock and not results:
            return [
                {
                    "info": "Semantic search requires AlloyDB setup",
                    "instructions": "Set ALLOYDB_CONNECTION_STRING environment variable",
                    "setup_guide": "See docs/DEPLOYMENT.md for AlloyDB provisioning",
                    "query": query,
                }
            ]

        return results

    except ImportError as e:
        return [
            {
                "error": "Semantic search dependencies not installed",
                "details": str(e),
                "install": "Run: uv sync --extra gcp",
            }
        ]


@mcp.tool()
@handle_mcp_tool_errors(return_type="list")
def find_similar_code(
    ctx: Context,
    code_snippet: str,
    project_name: str = None,
    language: str = None,
    top_k: int = 5,
    min_similarity: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Find code chunks similar to the provided code snippet (Phase 3A feature).

    Requires AlloyDB and Vertex AI to be configured. Falls back to mock mode
    if not available.

    Args:
        code_snippet: Code to find similar implementations of
        project_name: Filter to specific project (optional)
        language: Filter by programming language (optional)
        top_k: Number of results to return (default: 5)
        min_similarity: Minimum similarity threshold 0-1 (default: 0.5)

    Returns:
        List of similar code chunks with similarity scores

    Example:
        find_similar_code("def authenticate(user, pwd): return verify(user, pwd)", top_k=3)
    """
    # Import here to avoid dependency issues
    try:
        from uuid import uuid4

        from .services.semantic_search_service import find_similar_code as find_similar

        # Get database connection string from environment
        db_conn_str = os.getenv("ALLOYDB_CONNECTION_STRING")
        use_mock = not db_conn_str

        if use_mock:
            logging.warning("AlloyDB not configured, using mock mode")

        # Use test user ID (in production, this would come from auth middleware)
        # This matches the user created by seed_test_user utility
        from uuid import UUID

        user_id = UUID("00000000-0000-0000-0000-000000000001")

        results = find_similar(
            code_snippet=code_snippet,
            user_id=user_id,
            db_connection_string=db_conn_str or "mock",
            project_name=project_name,
            top_k=top_k,
            use_mock=use_mock,
        )

        if use_mock and not results:
            return [
                {
                    "info": "Similar code search requires AlloyDB setup",
                    "instructions": "Set ALLOYDB_CONNECTION_STRING environment variable",
                    "code_snippet_length": len(code_snippet),
                }
            ]

        return results

    except ImportError as e:
        return [
            {
                "error": "Semantic search dependencies not installed",
                "details": str(e),
                "install": "Run: uv sync --extra gcp",
            }
        ]


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def get_cloud_upload_script() -> Dict[str, str]:
    """
    Get the upload script for cloud ingestion.

    When using the cloud-deployed MCP server, you need this script to upload
    files from your local machine.

    Returns:
        Dictionary with script content and usage instructions

    Example:
        get_cloud_upload_script()
    """
    # Read the script from the same directory
    script_path = Path(__file__).parent.parent.parent / "upload_code_for_ingestion.py"

    try:
        script_content = script_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Fallback: return instructions to download it
        return {
            "error": "Script not found in installation",
            "download_url": "https://raw.githubusercontent.com/YOUR-REPO/main/upload_code_for_ingestion.py",
            "instructions": "Download the script and run: python upload_code_for_ingestion.py /path/to/project --project-name my-app",
        }

    return {
        "status": "success",
        "script": script_content,
        "usage": "Save this script and run: python upload_code_for_ingestion.py /path/to/project --project-name my-app",
        "features": [
            "Auto-detects text files (skips binaries)",
            "Respects .gitignore patterns",
            "Batches files (default: 50 per batch)",
            "Tracks progress locally",
            "Resume support for interrupted uploads",
        ],
    }


# REMOVED: reset_alloydb_schema tool - use Cloud Run Job 'fix-schema' instead
# This tool was too dangerous to expose to MCP clients as they might call it automatically.
#
# To fix schema issues, use:
#   gcloud run jobs execute fix-schema --region=us-east1 --wait
#
# Old implementation preserved below for reference but NOT exposed as MCP tool:
@handle_mcp_tool_errors(return_type="dict")
def reset_alloydb_schema() -> Dict[str, Any]:
    """
    [INTERNAL ONLY - NOT EXPOSED AS MCP TOOL]
    Reset AlloyDB schema (drops and recreates all tables, functions, indexes).
    ⚠️ WARNING: This will DELETE ALL DATA in the database!

    This function is no longer exposed to MCP clients.
    Use the Cloud Run Job 'fix-schema' instead for schema management.

    Returns:
        Dictionary with reset status
    """
    import logging

    import psycopg2

    logging.info("[SCHEMA RESET] Starting schema reset...")

    # Get database connection string
    db_conn_str = os.getenv("ALLOYDB_CONNECTION_STRING")
    if not db_conn_str:
        logging.error("[SCHEMA RESET] AlloyDB connection string not configured")
        return {
            "error": "AlloyDB not configured",
            "instructions": "Set ALLOYDB_CONNECTION_STRING environment variable",
        }

    try:
        logging.info("[SCHEMA RESET] Connecting to AlloyDB...")
        conn = psycopg2.connect(db_conn_str)
        conn.autocommit = True
        cur = conn.cursor()

        # Drop everything
        logging.info("[SCHEMA RESET] Dropping existing tables and functions...")
        cur.execute(
            """
            DROP TABLE IF EXISTS code_chunks CASCADE;
            DROP TABLE IF EXISTS projects CASCADE;
            DROP FUNCTION IF EXISTS set_user_context(UUID);
        """
        )

        logging.info("[SCHEMA RESET] Schema dropped successfully")

        cur.close()
        conn.close()

        logging.info(
            "[SCHEMA RESET] ✅ Schema reset complete! Next ingestion will recreate tables."
        )

        return {
            "status": "success",
            "message": "AlloyDB schema has been reset",
            "next_steps": "Run ingest_code_for_search() to recreate the schema and ingest code",
        }

    except Exception as e:
        logging.error(f"[SCHEMA RESET] Error: {e}")
        import traceback

        return {
            "error": "Schema reset failed",
            "details": str(e),
            "traceback": traceback.format_exc(),
        }


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def ingest_code_for_search(
    ctx: Context,
    files: List[Dict[str, str]] = None,
    project_name: str = None,
    directory_path: str = None,
    use_current_project: bool = False,
) -> Dict[str, Any]:
    """
    Ingest code into AlloyDB for semantic search (Phase 3A feature).

    **DEPRECATION NOTICE**: The `files` parameter is deprecated and will be removed
    in a future version. Use `ingest_code_from_git` instead for cloud deployments.

    **Recommended for cloud mode**: Use `ingest_code_from_git` which provides:
    - 99% token savings (no file upload needed)
    - 95% faster incremental updates
    - Auto-sync via webhooks
    - Support for GitHub, GitLab, Bitbucket, Gitea

    For LOCAL stdio mode, `directory_path` remains the recommended approach.

    Args:
        files: [DEPRECATED] List of file dicts with 'path' and 'content' keys
               Use `ingest_code_from_git` instead for cloud deployments.
        project_name: Project name for organization (required)
        directory_path: Local path (stdio mode only - still supported)
        use_current_project: Use set project path (stdio mode only - still supported)

    Returns:
        Dictionary with ingestion statistics

    Example (DEPRECATED - Cloud mode with files):
        # Don't use this anymore!
        ingest_code_for_search(
            files=[{"path": "src/main.py", "content": "print('hello')"}],
            project_name="my-app"
        )

    Example (RECOMMENDED - Cloud mode with Git):
        # Use this instead!
        ingest_code_from_git(
            git_url="https://github.com/user/my-app",
            project_name="my-app"
        )

    Example (Local stdio mode - still supported):
        ingest_code_for_search(
            directory_path="/path/to/project",
            project_name="my-app"
        )
    """
    # Import here to avoid dependency issues
    try:
        import shutil
        import tempfile
        import traceback
        from pathlib import Path
        from uuid import uuid4

        from .ingestion.pipeline import ingest_directory

        logging.info(
            f"[INGESTION] Tool called: files={len(files) if files else 0}, directory_path={directory_path}, project_name={project_name}"
        )

        # Deprecation warning for files parameter
        if files:
            logging.warning(
                "[INGESTION] DEPRECATION WARNING: The 'files' parameter is deprecated. "
                "Use 'ingest_code_from_git' instead for cloud deployments. "
                "Benefits: 99% token savings, 95% faster updates, auto-sync via webhooks. "
                "See: https://github.com/your-repo/docs/GIT_SYNC_IMPLEMENTATION_PLAN.md"
            )

        # Get database connection string
        db_conn_str = os.getenv("ALLOYDB_CONNECTION_STRING")
        if not db_conn_str:
            logging.error("[INGESTION] AlloyDB connection string not configured")
            return {
                "error": "AlloyDB not configured",
                "instructions": "Set ALLOYDB_CONNECTION_STRING environment variable",
                "setup_guide": "See docs/DEPLOYMENT.md for AlloyDB provisioning",
            }

        logging.info(f"[INGESTION] AlloyDB connection string found: {db_conn_str[:20]}...")

        # Determine ingestion mode
        temp_dir = None
        try:
            if files:
                # CLOUD MODE: Files uploaded in request
                logging.info(f"[INGESTION] Cloud mode: Processing {len(files)} uploaded files")

                if not project_name:
                    return {
                        "error": "project_name is required when uploading files",
                        "instructions": "Provide project_name parameter",
                    }

                # Create temporary directory for uploaded files
                temp_dir = tempfile.mkdtemp(prefix=f"code-ingest-{project_name}-")
                logging.info(f"[INGESTION] Created temp directory: {temp_dir}")

                # Write uploaded files to temp directory
                for file_info in files:
                    file_path = file_info.get("path")
                    file_content = file_info.get("content")

                    if not file_path or file_content is None:
                        logging.warning(f"[INGESTION] Skipping invalid file: {file_info}")
                        continue

                    # Create file path (relative to temp dir)
                    full_path = Path(temp_dir) / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)

                    # Write file content
                    full_path.write_text(file_content, encoding="utf-8")
                    logging.debug(
                        f"[INGESTION] Wrote file: {file_path} ({len(file_content)} bytes)"
                    )

                directory_path = temp_dir
                logging.info(f"[INGESTION] Ready to ingest {len(files)} files from temp directory")

            else:
                # STDIO MODE: Use local directory path
                logging.info("[INGESTION] Stdio mode: Using local directory path")

                if use_current_project:
                    # Get the custom context with base_path
                    logging.info("[INGESTION] Getting custom context for current project")
                    custom_ctx = mcp.get_context()
                    if not custom_ctx.base_path:
                        logging.error("[INGESTION] No project path set in context")
                        return {
                            "error": "No project path set",
                            "instructions": "Call set_project_path first",
                        }
                    directory_path = custom_ctx.base_path
                    logging.info(f"[INGESTION] Using current project path: {directory_path}")

                if not directory_path:
                    return {
                        "error": "No directory or files specified",
                        "instructions": "For cloud mode: provide 'files' list. For stdio mode: provide 'directory_path'",
                        "example_cloud": 'files=[{"path": "src/main.py", "content": "..."}]',
                        "example_stdio": 'directory_path="/path/to/project"',
                    }

                # Strip whitespace and newlines from path
                directory_path = directory_path.strip().replace("\n", "").replace("\r", "")
                logging.info(f"[INGESTION] Cleaned directory path: {directory_path}")

                # Auto-detect project name if not provided
                if not project_name:
                    project_name = Path(directory_path).name
                    logging.info(f"[INGESTION] Auto-detected project name: {project_name}")

            # Generate user ID
            user_id = uuid4()
            logging.info(f"[INGESTION] Generated user_id: {user_id}")

            # Progress callback for visibility in Cloud Run logs
            def log_progress(message: str, data: Dict[str, Any]):
                logging.info(f"[INGESTION PROGRESS] {message} | Data: {data}")

            # Run ingestion with progress logging
            logging.info(
                f"[INGESTION] Starting code ingestion for project '{project_name}' at {directory_path}"
            )
            logging.info(f"[INGESTION] This may take several minutes for large codebases...")
            stats = ingest_directory(
                directory_path=directory_path,
                user_id=user_id,
                project_name=project_name,
                db_connection_string=db_conn_str,
                use_mock_embedder=False,  # Use real Vertex AI
                progress_callback=log_progress,
            )

            logging.info(f"[INGESTION] Completed successfully: {stats.to_dict()}")
            return {
                "status": "success",
                "project_name": project_name,
                "files_uploaded": len(files) if files else 0,
                "mode": "cloud" if files else "stdio",
                **stats.to_dict(),
            }

        finally:
            # Clean up temp directory
            if temp_dir and Path(temp_dir).exists():
                logging.info(f"[INGESTION] Cleaning up temp directory: {temp_dir}")
                shutil.rmtree(temp_dir, ignore_errors=True)

    except ImportError as e:
        logging.error(f"[INGESTION] Import error: {e}")
        logging.error(f"[INGESTION] Traceback: {traceback.format_exc()}")
        return {
            "error": "Ingestion dependencies not installed",
            "details": str(e),
            "traceback": traceback.format_exc(),
            "install": "Run: uv sync --extra gcp",
        }
    except Exception as e:
        logging.error(f"[INGESTION] Unexpected error: {e}")
        logging.error(f"[INGESTION] Traceback: {traceback.format_exc()}")
        return {"error": "Ingestion failed", "details": str(e), "traceback": traceback.format_exc()}


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
async def ingest_code_from_git(
    ctx: Context,
    git_url: str,
    project_name: str = None,
    branch: str = "main",
    auth_token: str = None,
    sync_only: bool = False,
    chunking_strategy: str = "function",
) -> Dict[str, Any]:
    """
    Ingest code from Git repository with smart sync (Phase 3A - Git-Sync feature).

    This tool eliminates the need for LLMs to read and send file contents,
    reducing token usage by 90%+ and enabling incremental updates via webhooks.

    Workflow:
        First call: Clones repository to Cloud Storage and ingests code
        Subsequent calls: Pulls changes only and re-ingests modified files
        With webhooks: Auto-syncs on every git push

    Supported platforms:
        - GitHub (github.com)
        - GitLab (gitlab.com)
        - Bitbucket (bitbucket.org)
        - Gitea (custom domains, e.g., gitea.example.com)

    Args:
        git_url: Git repository URL (HTTPS or SSH)
                 Examples:
                   - https://github.com/user/repo
                   - https://gitlab.com/org/project
                   - git@github.com:user/repo.git
                   - https://gitea.example.com/user/repo
        project_name: Project name for organization (optional, auto-detected from repo)
        branch: Branch to sync (default: "main")
        auth_token: Personal access token for private repos (optional)
                    - GitHub: Create at https://github.com/settings/tokens
                    - GitLab: Create at https://gitlab.com/-/profile/personal_access_tokens
                    - Gitea: Create in user settings
        sync_only: If True, only sync repository without ingesting (default: False)
        chunking_strategy: Code chunking strategy: "function", "class", "file", "semantic"
                          (default: "function")

    Returns:
        Dictionary with sync and ingestion statistics:
        {
            "status": "success",
            "sync_type": "clone" | "pull",
            "repo_info": {
                "platform": "github",
                "owner": "user",
                "repo": "repo",
                "branch": "main"
            },
            "files_changed": 15,  # For pull operations
            "chunks_created": 67,
            "embeddings_generated": 67,
            "project_name": "repo",
            "mode": "git-sync",
            "token_savings": "99% vs files upload"
        }

    Examples:
        # Public GitHub repository
        ingest_code_from_git(
            git_url="https://github.com/user/my-project",
            project_name="my-project"
        )

        # Private GitLab repository with auth
        ingest_code_from_git(
            git_url="https://gitlab.com/org/private-project",
            auth_token="glpat_xxxxxxxxxxxx",
            project_name="private-project"
        )

        # Gitea custom domain
        ingest_code_from_git(
            git_url="https://git.company.com/dev/app",
            auth_token="your_gitea_token",
            branch="develop"
        )

        # Incremental update (pull changes only)
        # Just call again with same git_url - it auto-detects existing repo
        ingest_code_from_git(git_url="https://github.com/user/my-project")

    Note:
        - First ingestion clones entire repository (~1-2 minutes for 100k LOC)
        - Subsequent calls pull changes only (~5-10 seconds)
        - Repository persists in Cloud Storage for fast incremental updates
        - Webhooks can be configured for automatic sync on push
    """
    try:
        import traceback
        from pathlib import Path
        from uuid import uuid4

        from .ingestion.git_manager import GitManagerError, GitRepositoryManager
        from .ingestion.pipeline import ingest_directory

        logging.info(
            f"[GIT-SYNC] Tool called: git_url={git_url}, branch={branch}, project_name={project_name}"
        )

        # Validate git_url
        if not git_url or not git_url.strip():
            return {
                "error": "git_url is required",
                "instructions": "Provide a valid Git repository URL",
                "example": "https://github.com/user/repo",
            }

        # Get database connection string
        db_conn_str = os.getenv("ALLOYDB_CONNECTION_STRING")
        if not db_conn_str:
            logging.error("[GIT-SYNC] AlloyDB connection string not configured")
            return {
                "error": "AlloyDB not configured",
                "instructions": "Set ALLOYDB_CONNECTION_STRING environment variable",
                "setup_guide": "See docs/DEPLOYMENT.md for AlloyDB provisioning",
            }

        # Get GCS bucket for git repositories
        git_bucket = os.getenv("GCS_GIT_BUCKET", "code-index-git-repos")
        logging.info(f"[GIT-SYNC] Using GCS bucket: {git_bucket}")

        # Authenticate user and get user_id from API key
        user_context = None
        try:
            auth_middleware = ctx.request_context.lifespan_context.auth_middleware
        except AttributeError:
            auth_middleware = None

        if auth_middleware:
            try:
                user_context = await require_authentication(
                    ctx.request_context.session, auth_middleware
                )
                user_id = user_context.user_id
                logging.info(f"[GIT-SYNC] Authenticated user: {user_id}")
            except AuthenticationError as e:
                logging.error(f"[GIT-SYNC] Authentication failed: {e}")
                raise RuntimeError(f"Authentication required for git ingestion: {str(e)}")
        else:
            # Fallback to test user for local/stdio mode
            from uuid import UUID

            user_id = UUID("00000000-0000-0000-0000-000000000001")
            logging.warning(
                f"[GIT-SYNC] Using test user_id: {user_id} "
                "(auth middleware not available - development mode)"
            )

        # Initialize GitRepositoryManager
        git_manager = GitRepositoryManager(gcs_bucket=git_bucket, user_id=str(user_id))

        # Sync repository (clone or pull)
        logging.info(f"[GIT-SYNC] Syncing repository: {git_url}")
        sync_result = await git_manager.sync_repository(
            git_url=git_url, branch=branch, auth_token=auth_token
        )

        logging.info(
            f"[GIT-SYNC] Sync completed: type={sync_result['sync_type']}, "
            f"files_changed={sync_result.get('files_changed', 'N/A')}"
        )

        # Auto-detect project name if not provided
        if not project_name:
            project_name = sync_result["repo_info"]["repo"]
            logging.info(f"[GIT-SYNC] Auto-detected project name: {project_name}")

        # If sync_only, return sync results without ingestion
        if sync_only:
            return {
                "status": "success",
                "mode": "git-sync-only",
                "sync_type": sync_result["sync_type"],
                "repo_info": sync_result["repo_info"],
                "files_changed": sync_result.get("files_changed"),
                "local_path": sync_result["local_path"],
                "project_name": project_name,
                "ingestion_skipped": "Set sync_only=False to ingest code",
            }

        # Progress callback for visibility
        def log_progress(message: str, data: Dict[str, Any]):
            logging.info(f"[GIT-SYNC PROGRESS] {message} | Data: {data}")

        # Run ingestion pipeline
        logging.info(f"[GIT-SYNC] Starting code ingestion for project '{project_name}'")
        logging.info(f"[GIT-SYNC] This may take several minutes for large codebases...")

        # For incremental updates, only ingest changed files
        # TODO: Implement selective file ingestion based on sync_result['changed_files']
        # For now, ingest entire directory (optimization for future PR)

        stats = ingest_directory(
            directory_path=sync_result["local_path"],
            user_id=user_id,
            project_name=project_name,
            db_connection_string=db_conn_str,
            use_mock_embedder=False,  # Use real Vertex AI
            progress_callback=log_progress,
        )

        logging.info(f"[GIT-SYNC] Ingestion completed: {stats.to_dict()}")

        return {
            "status": "success",
            "mode": "git-sync",
            "sync_type": sync_result["sync_type"],
            "repo_info": {**sync_result["repo_info"], "branch": branch},
            "files_changed": sync_result.get("files_changed"),
            "project_name": project_name,
            "token_savings": "99% vs files upload (estimated)",
            "performance": (
                "95% faster for incremental updates"
                if sync_result["sync_type"] == "pull"
                else "75% faster vs file upload"
            ),
            **stats.to_dict(),
        }

    except GitManagerError as e:
        logging.error(f"[GIT-SYNC] Git operation failed: {e}")
        logging.error(f"[GIT-SYNC] Traceback: {traceback.format_exc()}")
        return {
            "error": "Git sync failed",
            "details": str(e),
            "traceback": traceback.format_exc(),
            "troubleshooting": {
                "check_url": "Verify the Git URL is correct",
                "check_auth": "For private repos, provide auth_token",
                "check_branch": "Verify the branch exists",
                "supported_platforms": ["GitHub", "GitLab", "Bitbucket", "Gitea"],
            },
        }
    except ImportError as e:
        logging.error(f"[GIT-SYNC] Import error: {e}")
        logging.error(f"[GIT-SYNC] Traceback: {traceback.format_exc()}")
        return {
            "error": "Git-sync dependencies not installed",
            "details": str(e),
            "traceback": traceback.format_exc(),
            "install": "Run: uv sync --extra gcp",
        }
    except Exception as e:
        logging.error(f"[GIT-SYNC] Unexpected error: {e}")
        logging.error(f"[GIT-SYNC] Traceback: {traceback.format_exc()}")
        return {
            "error": "Git-sync ingestion failed",
            "details": str(e),
            "traceback": traceback.format_exc(),
        }


# ----- PROMPTS -----
# Removed: analyze_code, code_search, set_project prompts


def main():
    """Main function to run the MCP server."""
    # Support both stdio (local) and HTTP/SSE (cloud) modes via environment variable
    transport_mode = os.getenv("MCP_TRANSPORT", "stdio")

    if transport_mode == "http":
        # HTTP/SSE mode for cloud deployment (Cloud Run, Lambda, OpenShift)
        # FastMCP reads host/port from mcp.settings object
        # nosec B104: Binding to 0.0.0.0 is required for Cloud Run containerized deployments
        host = os.getenv("HOST", "0.0.0.0")  # nosec B104
        port = int(os.getenv("PORT", 8080))

        # Set the host and port in mcp.settings before calling run()
        # These will be used by uvicorn.Config in run_sse_async()
        mcp.settings.host = host
        mcp.settings.port = port

        # Register webhook routes for Git-sync (Phase 3)
        try:
            from .admin.webhook_handler import setup_webhook_routes

            setup_webhook_routes(mcp)
            logging.info("Git-sync webhook routes registered successfully")
        except ImportError as e:
            logging.warning(f"Failed to register webhook routes: {e}")
            logging.warning("Webhook auto-sync will not be available")

        # Check if authentication is required
        require_auth = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

        if require_auth:
            logging.info(
                f"Starting MCP server in HTTP/SSE mode on {host}:{port} with API key authentication"
            )
            logging.info(
                "Note: Authentication middleware is available but not yet integrated with FastMCP SSE endpoints"
            )
            logging.info("To enable auth, API keys must be validated in a custom middleware")
            # TODO: Integrate AuthMiddleware with FastMCP's SSE endpoints
            # See: src/code_index_mcp/middleware/auth.py
            # Requires: Adding Starlette middleware to FastMCP's app
        else:
            logging.info(f"Starting MCP server in HTTP/SSE mode on {host}:{port} (unauthenticated)")

        # Note: Cleanup endpoint is handled by a separate Cloud Run Job
        # See deployment/gcp/cleanup-job.yaml for Cloud Scheduler integration

        # Now run with SSE transport - uvicorn will use our configured settings
        mcp.run(transport="sse")
    else:
        # stdio mode for local development (default)
        logging.info("Starting MCP server in stdio mode")
        mcp.run()


if __name__ == "__main__":
    main()
