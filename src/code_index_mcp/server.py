"""
Code Index MCP Server

This MCP server allows LLMs to index, search, and analyze code from a project directory.
It provides tools for file discovery, content retrieval, and code analysis.
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional, Tuple, Any
import os
import pathlib
import json
import fnmatch
import sys
import tempfile
import subprocess
from mcp.server.fastmcp import FastMCP, Context, Image
from mcp import types

# Import the ProjectSettings class and constants - using relative import
from .project_settings import ProjectSettings
from .constants import SETTINGS_DIR

# Create the MCP server
mcp = FastMCP("CodeIndexer", dependencies=["pathlib"])

# In-memory references (will be loaded from persistent storage)
file_index = {}
code_content_cache = {}
supported_extensions = [
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala', '.sh',
    '.bash', '.html', '.css', '.scss', '.md', '.json', '.xml', '.yml', '.yaml', '.zig',
    # Frontend frameworks
    '.vue', '.svelte', '.mjs', '.cjs',
    # Style languages
    '.less', '.sass', '.stylus', '.styl',
    # Template engines
    '.hbs', '.handlebars', '.ejs', '.pug',
    # Modern frontend
    '.astro', '.mdx',
    # Database and SQL
    '.sql', '.ddl', '.dml', '.mysql', '.postgresql', '.psql', '.sqlite',
    '.mssql', '.oracle', '.ora', '.db2',
    # Database objects
    '.proc', '.procedure', '.func', '.function', '.view', '.trigger', '.index',
    # Database frameworks and tools
    '.migration', '.seed', '.fixture', '.schema',
    # NoSQL and modern databases
    '.cql', '.cypher', '.sparql', '.gql',
    # Database migration tools
    '.liquibase', '.flyway'
]

@dataclass
class CodeIndexerContext:
    """Context for the Code Indexer MCP server."""
    base_path: str
    settings: ProjectSettings
    file_count: int = 0

@asynccontextmanager
async def indexer_lifespan(server: FastMCP) -> AsyncIterator[CodeIndexerContext]:
    """Manage the lifecycle of the Code Indexer MCP server."""
    # Don't set a default path, user must explicitly set project path
    base_path = ""  # Empty string to indicate no path is set

    print("Initializing Code Indexer MCP server...")

    # Initialize settings manager with skip_load=True to skip loading files
    settings = ProjectSettings(base_path, skip_load=True)

    # Initialize context
    context = CodeIndexerContext(
        base_path=base_path,
        settings=settings
    )

    # Initialize global variables
    global file_index, code_content_cache

    try:
        print("Server ready. Waiting for user to set project path...")
        # Provide context to the server
        yield context
    finally:
        # Only save index and cache if project path has been set
        if context.base_path and file_index:
            print(f"Saving index for project: {context.base_path}")
            settings.save_index(file_index)

        if context.base_path and code_content_cache:
            print(f"Saving cache for project: {context.base_path}")
            settings.save_cache(code_content_cache)

# Initialize the server with our lifespan manager
mcp = FastMCP("CodeIndexer", lifespan=indexer_lifespan)

# ----- RESOURCES -----

@mcp.resource("config://code-indexer")
def get_config() -> str:
    """Get the current configuration of the Code Indexer."""
    ctx = mcp.get_context()

    # Get the base path from context
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return json.dumps({
            "status": "not_configured",
            "message": "Project path not set. Please use set_project_path to set a project directory first.",
            "supported_extensions": supported_extensions
        }, indent=2)

    # Get file count
    file_count = ctx.request_context.lifespan_context.file_count

    # Get settings stats
    settings = ctx.request_context.lifespan_context.settings
    settings_stats = settings.get_stats()

    config = {
        "base_path": base_path,
        "supported_extensions": supported_extensions,
        "file_count": file_count,
        "settings_directory": settings.settings_path,
        "settings_stats": settings_stats
    }

    return json.dumps(config, indent=2)

@mcp.resource("files://{file_path}")
def get_file_content(file_path: str) -> str:
    """Get the content of a specific file."""
    ctx = mcp.get_context()

    # Get the base path from context
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return "Error: Project path not set. Please use set_project_path to set a project directory first."

    # Handle absolute paths (especially Windows paths starting with drive letters)
    if os.path.isabs(file_path) or (len(file_path) > 1 and file_path[1] == ':'):
        # Absolute paths are not allowed via this endpoint
        return f"Error: Absolute file paths like '{file_path}' are not allowed. Please use paths relative to the project root."

    # Normalize the file path
    norm_path = os.path.normpath(file_path)

    # Check for path traversal attempts
    if "..\\" in norm_path or "../" in norm_path or norm_path.startswith(".."):
        return f"Error: Invalid file path: {file_path} (directory traversal not allowed)"

    # Construct the full path and verify it's within the project bounds
    full_path = os.path.join(base_path, norm_path)
    real_full_path = os.path.realpath(full_path)
    real_base_path = os.path.realpath(base_path)

    if not real_full_path.startswith(real_base_path):
        return f"Error: Access denied. File path must be within project directory."

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Cache the content for faster retrieval later
        code_content_cache[norm_path] = content

        return content
    except UnicodeDecodeError:
        return f"Error: File {file_path} appears to be a binary file or uses unsupported encoding."
    except Exception as e:
        return f"Error reading file: {e}"

@mcp.resource("structure://project")
def get_project_structure() -> str:
    """Get the structure of the project as a JSON tree."""
    ctx = mcp.get_context()

    # Get the base path from context
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return json.dumps({
            "status": "not_configured",
            "message": "Project path not set. Please use set_project_path to set a project directory first."
        }, indent=2)

    # Check if we need to refresh the index
    if not file_index:
        _index_project(base_path)
        # Update file count in context
        ctx.request_context.lifespan_context.file_count = _count_files(file_index)
        # Save updated index
        ctx.request_context.lifespan_context.settings.save_index(file_index)

    return json.dumps(file_index, indent=2)

@mcp.resource("settings://stats")
def get_settings_stats() -> str:
    """Get statistics about the settings directory and files."""
    ctx = mcp.get_context()

    # Get settings manager from context
    settings = ctx.request_context.lifespan_context.settings

    # Get settings stats
    stats = settings.get_stats()

    return json.dumps(stats, indent=2)

# ----- TOOLS -----

@mcp.tool()
def set_project_path(path: str, ctx: Context) -> str:
    """Set the base project path for indexing."""
    # Validate and normalize path
    try:
        norm_path = os.path.normpath(path)
        abs_path = os.path.abspath(norm_path)

        if not os.path.exists(abs_path):
            return f"Error: Path does not exist: {abs_path}"

        if not os.path.isdir(abs_path):
            return f"Error: Path is not a directory: {abs_path}"

        # Clear existing in-memory index and cache
        global file_index, code_content_cache
        file_index.clear()
        code_content_cache.clear()

        # Update the base path in context
        ctx.request_context.lifespan_context.base_path = abs_path

        # Create a new settings manager for the new path (don't skip loading files)
        ctx.request_context.lifespan_context.settings = ProjectSettings(abs_path, skip_load=False)

        # Print the settings path for debugging
        settings_path = ctx.request_context.lifespan_context.settings.settings_path
        print(f"Project settings path: {settings_path}")

        # Try to load existing index and cache
        print(f"Project path set to: {abs_path}")
        print(f"Attempting to load existing index and cache...")

        # Try to load index
        loaded_index = ctx.request_context.lifespan_context.settings.load_index()
        if loaded_index:
            print(f"Existing index found and loaded successfully")
            file_index = loaded_index
            file_count = _count_files(file_index)
            ctx.request_context.lifespan_context.file_count = file_count

            # Try to load cache
            loaded_cache = ctx.request_context.lifespan_context.settings.load_cache()
            if loaded_cache:
                print(f"Existing cache found and loaded successfully")
                code_content_cache.update(loaded_cache)

            # Get search capabilities info
            search_tool = ctx.request_context.lifespan_context.settings.get_preferred_search_tool()
            
            if search_tool == 'basic':
                search_info = " Basic search available."
            else:
                search_info = f" Advanced search enabled ({search_tool})."
            
            return f"Project path set to: {abs_path}. Loaded existing index with {file_count} files.{search_info}"
        else:
            print(f"No existing index found, creating new index...")

        # If no existing index, create a new one
        file_count = _index_project(abs_path)
        ctx.request_context.lifespan_context.file_count = file_count

        # Save the new index
        ctx.request_context.lifespan_context.settings.save_index(file_index)

        # Save project config
        config = {
            "base_path": abs_path,
            "supported_extensions": supported_extensions,
            "last_indexed": ctx.request_context.lifespan_context.settings.load_config().get('last_indexed', None)
        }
        ctx.request_context.lifespan_context.settings.save_config(config)

        # Get search capabilities info (this will trigger lazy detection)
        search_tool = ctx.request_context.lifespan_context.settings.get_preferred_search_tool()
        
        if search_tool == 'basic':
            search_info = " Basic search available."
        else:
            search_info = f" Advanced search enabled ({search_tool})."

        return f"Project path set to: {abs_path}. Indexed {file_count} files.{search_info}"
    except Exception as e:
        return f"Error setting project path: {e}"

@mcp.tool()
def search_code(query: str, ctx: Context, extensions: Optional[List[str]] = None, case_sensitive: bool = False) -> Dict[str, List[Tuple[int, str]]]:
    """
    Search for code matches within the indexed files.
    Returns a dictionary mapping filenames to lists of (line_number, line_content) tuples.
    """
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return {"error": "Project path not set. Please use set_project_path to set a project directory first."}

    # Check if we need to index the project
    if not file_index:
        _index_project(base_path)
        ctx.request_context.lifespan_context.file_count = _count_files(file_index)
        ctx.request_context.lifespan_context.settings.save_index(file_index)

    results = {}

    # Filter by extensions if provided
    if extensions:
        valid_extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
    else:
        valid_extensions = supported_extensions

    # Process the search
    for file_path, _info in _get_all_files(file_index):
        # Check if the file has a supported extension
        if not any(file_path.endswith(ext) for ext in valid_extensions):
            continue

        try:
            # Get file content (from cache if available)
            if file_path in code_content_cache:
                content = code_content_cache[file_path]
            else:
                full_path = os.path.join(base_path, file_path)
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                code_content_cache[file_path] = content

            # Search for matches
            matches = []
            for i, line in enumerate(content.splitlines(), 1):
                if (case_sensitive and query in line) or (not case_sensitive and query.lower() in line.lower()):
                    matches.append((i, line.strip()))

            if matches:
                results[file_path] = matches
        except Exception as e:
            ctx.info(f"Error searching file {file_path}: {e}")

    # Save the updated cache
    ctx.request_context.lifespan_context.settings.save_cache(code_content_cache)

    return results

@mcp.tool()
def search_code_advanced(
    pattern: str, 
    ctx: Context,
    case_sensitive: bool = True,
    context_lines: int = 0,
    file_pattern: Optional[str] = None,
    fuzzy: bool = False
) -> Dict[str, Any]:
    """
    Advanced search using external tools (ugrep, ripgrep, ag, grep) for better performance.
    
    - `pattern`: The search pattern (string or regex).
    - `case_sensitive`: Whether the search is case-sensitive.
    - `context_lines`: Number of context lines to show around each match.
    - `file_pattern`: Glob pattern to filter files (e.g., "*.py").
    - `fuzzy`: Enable fuzzy search. The behavior of this flag depends on the available tool:
               - With `ugrep`: Performs a true, edit-distance fuzzy search (handles typos).
               - With `ripgrep` or `ag`: Performs a word-boundary-based pattern search (handles word order and spacing).
    """
    base_path = ctx.request_context.lifespan_context.base_path

    if not base_path:
        return {"error": "Project path not set. Please use set_project_path to set a project directory first."}

    # Get search tool configuration
    settings = ctx.request_context.lifespan_context.settings
    preferred_tool = settings.get_preferred_search_tool()
    
    if preferred_tool == 'basic':
        # Fallback to existing search_code function
        ctx.info("Using basic search (no advanced tools available)")
        return {
            "tool_used": "basic",
            "results": search_code(pattern, ctx, case_sensitive=case_sensitive)
        }
    
    try:
        # Use advanced search tool
        results = _execute_advanced_search(
            pattern, base_path, preferred_tool, case_sensitive, context_lines, file_pattern, fuzzy
        )
        
        return {
            "tool_used": preferred_tool,
            "results": results,
            "total_matches": sum(len(matches) for matches in results.values())
        }
        
    except Exception as e:
        ctx.info(f"Advanced search failed: {e}, falling back to basic search")
        # Fallback to basic search
        return {
            "tool_used": "basic_fallback",
            "results": search_code(pattern, ctx, case_sensitive=case_sensitive),
            "fallback_reason": str(e)
        }

@mcp.tool()
def find_files(pattern: str, ctx: Context) -> List[str]:
    """
    Find files in the project that match the given pattern.
    Supports glob patterns like *.py or **/*.js.
    """
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return ["Error: Project path not set. Please use set_project_path to set a project directory first."]

    # Check if we need to index the project
    if not file_index:
        _index_project(base_path)
        ctx.request_context.lifespan_context.file_count = _count_files(file_index)
        ctx.request_context.lifespan_context.settings.save_index(file_index)

    matching_files = []
    for file_path, _info in _get_all_files(file_index):
        if fnmatch.fnmatch(file_path, pattern):
            matching_files.append(file_path)

    return matching_files

@mcp.tool()
def get_file_summary(file_path: str, ctx: Context) -> Dict[str, Any]:
    """
    Get a summary of a specific file, including:
    - Line count
    - Function/class definitions (for supported languages)
    - Import statements
    - Basic complexity metrics
    """
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return {"error": "Project path not set. Please use set_project_path to set a project directory first."}

    # Normalize the file path
    norm_path = os.path.normpath(file_path)
    if norm_path.startswith('..'):
        return {"error": f"Invalid file path: {file_path}"}

    full_path = os.path.join(base_path, norm_path)

    try:
        # Get file content
        if norm_path in code_content_cache:
            content = code_content_cache[norm_path]
        else:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            code_content_cache[norm_path] = content
            # Save the updated cache
            ctx.request_context.lifespan_context.settings.save_cache(code_content_cache)

        # Basic file info
        lines = content.splitlines()
        line_count = len(lines)

        # File extension for language-specific analysis
        _, ext = os.path.splitext(norm_path)

        summary = {
            "file_path": norm_path,
            "line_count": line_count,
            "size_bytes": os.path.getsize(full_path),
            "extension": ext,
        }

        # Language-specific analysis
        if ext == '.py':
            # Python analysis
            imports = []
            classes = []
            functions = []

            for i, line in enumerate(lines):
                line = line.strip()

                # Check for imports
                if line.startswith('import ') or line.startswith('from '):
                    imports.append(line)

                # Check for class definitions
                if line.startswith('class '):
                    classes.append({
                        "line": i + 1,
                        "name": line.replace('class ', '').split('(')[0].split(':')[0].strip()
                    })

                # Check for function definitions
                if line.startswith('def '):
                    functions.append({
                        "line": i + 1,
                        "name": line.replace('def ', '').split('(')[0].strip()
                    })

            summary.update({
                "imports": imports,
                "classes": classes,
                "functions": functions,
                "import_count": len(imports),
                "class_count": len(classes),
                "function_count": len(functions),
            })

        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            # JavaScript/TypeScript analysis
            imports = []
            classes = []
            functions = []

            for i, line in enumerate(lines):
                line = line.strip()

                # Check for imports
                if line.startswith('import ') or line.startswith('require('):
                    imports.append(line)

                # Check for class definitions
                if line.startswith('class ') or 'class ' in line:
                    class_name = ""
                    if 'class ' in line:
                        parts = line.split('class ')[1]
                        class_name = parts.split(' ')[0].split('{')[0].split('extends')[0].strip()
                    classes.append({
                        "line": i + 1,
                        "name": class_name
                    })

                # Check for function definitions
                if 'function ' in line or '=>' in line:
                    functions.append({
                        "line": i + 1,
                        "content": line
                    })

            summary.update({
                "imports": imports,
                "classes": classes,
                "functions": functions,
                "import_count": len(imports),
                "class_count": len(classes),
                "function_count": len(functions),
            })

        return summary
    except Exception as e:
        return {"error": f"Error analyzing file: {e}"}

@mcp.tool()
def refresh_index(ctx: Context) -> str:
    """Refresh the project index."""
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return "Error: Project path not set. Please use set_project_path to set a project directory first."

    # Clear existing index
    global file_index
    file_index.clear()

    # Re-index the project
    file_count = _index_project(base_path)
    ctx.request_context.lifespan_context.file_count = file_count

    # Save the updated index
    ctx.request_context.lifespan_context.settings.save_index(file_index)

    # Update the last indexed timestamp in config
    config = ctx.request_context.lifespan_context.settings.load_config()
    ctx.request_context.lifespan_context.settings.save_config({
        **config,
        'last_indexed': ctx.request_context.lifespan_context.settings._get_timestamp()
    })

    return f"Project re-indexed. Found {file_count} files."

@mcp.tool()
def get_settings_info(ctx: Context) -> Dict[str, Any]:
    """Get information about the project settings."""
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        # Even if base_path is not set, we can still show the temp directory
        temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)
        return {
            "status": "not_configured",
            "message": "Project path not set. Please use set_project_path to set a project directory first.",
            "temp_directory": temp_dir,
            "temp_directory_exists": os.path.exists(temp_dir)
        }

    settings = ctx.request_context.lifespan_context.settings

    # Get config
    config = settings.load_config()

    # Get stats
    stats = settings.get_stats()

    # Get temp directory
    temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)

    return {
        "settings_directory": settings.settings_path,
        "temp_directory": temp_dir,
        "temp_directory_exists": os.path.exists(temp_dir),
        "config": config,
        "stats": stats,
        "exists": os.path.exists(settings.settings_path)
    }

@mcp.tool()
def create_temp_directory() -> Dict[str, Any]:
    """Create the temporary directory used for storing index data."""
    temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)

    result = {
        "temp_directory": temp_dir,
        "existed_before": os.path.exists(temp_dir),
    }

    try:
        # Use ProjectSettings to handle directory creation consistently
        temp_settings = ProjectSettings("", skip_load=True)
        
        result["created"] = not result["existed_before"]
        result["exists_now"] = os.path.exists(temp_dir)
        result["is_directory"] = os.path.isdir(temp_dir)
    except Exception as e:
        result["error"] = str(e)

    return result

@mcp.tool()
def check_temp_directory() -> Dict[str, Any]:
    """Check the temporary directory used for storing index data."""
    temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)

    result = {
        "temp_directory": temp_dir,
        "exists": os.path.exists(temp_dir),
        "is_directory": os.path.isdir(temp_dir) if os.path.exists(temp_dir) else False,
        "temp_root": tempfile.gettempdir(),
    }

    # If the directory exists, list its contents
    if result["exists"] and result["is_directory"]:
        try:
            contents = os.listdir(temp_dir)
            result["contents"] = contents
            result["subdirectories"] = []

            # Check each subdirectory
            for item in contents:
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    subdir_info = {
                        "name": item,
                        "path": item_path,
                        "contents": os.listdir(item_path) if os.path.exists(item_path) else []
                    }
                    result["subdirectories"].append(subdir_info)
        except Exception as e:
            result["error"] = str(e)

    return result

@mcp.tool()
def clear_settings(ctx: Context) -> str:
    """Clear all settings and cached data."""
    base_path = ctx.request_context.lifespan_context.base_path

    # Check if base_path is set
    if not base_path:
        return "Error: Project path not set. Please use set_project_path to set a project directory first."

    settings = ctx.request_context.lifespan_context.settings

    # Clear all settings files
    settings.clear()

    # Clear in-memory cache and index
    global file_index, code_content_cache
    file_index.clear()
    code_content_cache.clear()

    return f"All settings and cache cleared from {settings.settings_path}"

@mcp.tool()
def refresh_search_tools(ctx: Context) -> str:
    """Refresh search tools detection and show available capabilities."""
    base_path = ctx.request_context.lifespan_context.base_path
    
    # Check if base_path is set
    if not base_path:
        return "Error: Project path not set. Please use set_project_path to set a project directory first."
    
    settings = ctx.request_context.lifespan_context.settings
    
    # Refresh search tools
    config = settings.refresh_search_tools()
    
    # Build response message
    preferred = config.get('preferred_tool', 'basic')
    available_tools = config.get('available_tools', {})
    
    message = f"Search tools refreshed. Preferred tool: {preferred}\n"
    message += "Available tools:\n"
    
    for tool_name, is_available in available_tools.items():
        status = "✓" if is_available else "✗"
        message += f"  {status} {tool_name}\n"
    
    if preferred != 'basic':
        message += f"\nAdvanced search capabilities enabled with {preferred}."
    else:
        message += "\nOnly basic search available. Consider installing ugrep (recommended for fuzzy search), ripgrep, or ag for better performance."
    
    return message

# ----- PROMPTS -----

@mcp.prompt()
def analyze_code(file_path: str = "", query: str = "") -> list[types.PromptMessage]:
    """Prompt for analyzing code in the project."""
    messages = [
        types.PromptMessage(role="user", content=types.TextContent(type="text", text=f"""I need you to analyze some code from my project.

{f'Please analyze the file: {file_path}' if file_path else ''}
{f'I want to understand: {query}' if query else ''}

First, let me give you some context about the project structure. Then, I'll provide the code to analyze.
""")),
        types.PromptMessage(role="assistant", content=types.TextContent(type="text", text="I'll help you analyze the code. Let me first examine the project structure to get a better understanding of the codebase."))
    ]
    return messages

@mcp.prompt()
def code_search(query: str = "") -> types.TextContent:
    """Prompt for searching code in the project."""
    search_text = f"\"query\"" if not query else f"\"{query}\""
    return types.TextContent(type="text", text=f"""I need to search through my codebase for {search_text}.

Please help me find all occurrences of this query and explain what each match means in its context.
Focus on the most relevant files and provide a brief explanation of how each match is used in the code.

If there are too many results, prioritize the most important ones and summarize the patterns you see.""")

@mcp.prompt()
def set_project() -> list[types.PromptMessage]:
    """Prompt for setting the project path."""
    messages = [
        types.PromptMessage(role="user", content=types.TextContent(type="text", text="""
        I need to analyze code from a project, but I haven't set the project path yet. Please help me set up the project path and index the code.

        First, I need to specify which project directory to analyze.
        """)),
        types.PromptMessage(role="assistant", content=types.TextContent(type="text", text="""
        Before I can help you analyze any code, we need to set up the project path. This is a required first step.

        Please provide the full path to your project folder. For example:
        - Windows: "C:/Users/username/projects/my-project"
        - macOS/Linux: "/home/username/projects/my-project"

        Once you provide the path, I'll use the `set_project_path` tool to configure the code analyzer to work with your project.
        """))
    ]
    return messages

# ----- HELPER FUNCTIONS -----

def _index_project(base_path: str) -> int:
    """
    Create an index of the project files.
    Returns the number of files indexed.
    """
    file_count = 0
    file_index.clear()

    for root, dirs, files in os.walk(base_path):
        # Skip hidden directories and common build/dependency directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and
                 d not in ['node_modules', 'venv', '__pycache__', 'build', 'dist']]

        # Create relative path from base_path
        rel_path = os.path.relpath(root, base_path)
        current_dir = file_index

        # Skip the '.' directory (base_path itself)
        if rel_path != '.':
            # Split the path and navigate/create the tree
            path_parts = rel_path.replace('\\', '/').split('/')
            for part in path_parts:
                if part not in current_dir:
                    current_dir[part] = {}
                current_dir = current_dir[part]

        # Add files to current directory
        for file in files:
            # Skip hidden files and files with unsupported extensions
            _, ext = os.path.splitext(file)
            if file.startswith('.') or ext not in supported_extensions:
                continue

            # Store file information
            file_path = os.path.join(rel_path, file).replace('\\', '/')
            if rel_path == '.':
                file_path = file

            current_dir[file] = {
                "type": "file",
                "path": file_path,
                "ext": ext
            }
            file_count += 1

    return file_count

def _count_files(directory: Dict) -> int:
    """
    Count the number of files in the index.
    """
    count = 0
    for name, value in directory.items():
        if isinstance(value, dict):
            if "type" in value and value["type"] == "file":
                count += 1
            else:
                count += _count_files(value)
    return count

def _get_all_files(directory: Dict, prefix: str = "") -> List[Tuple[str, Dict]]:
    """
    Recursively get all files from the directory structure.
    Returns a list of (file_path, file_info) tuples.
    """
    result = []

    for name, value in directory.items():
        if isinstance(value, dict):
            if "type" in value and value["type"] == "file":
                result.append((value["path"], value))
            else:
                new_prefix = f"{prefix}/{name}" if prefix else name
                result.extend(_get_all_files(value, new_prefix))

    return result

def _create_safe_fuzzy_pattern(pattern: str) -> str:
    """Create safe fuzzy search patterns that are more permissive than exact match
    but still safe from regex injection attacks.
    
    Args:
        pattern: Original search pattern
        
    Returns:
        Safe fuzzy pattern for grep -E (extended regex)
    """
    import re
    
    # Escape any regex special characters to make them literal
    escaped = re.escape(pattern)
    
    # Create fuzzy pattern that matches:
    # 1. Word at start of word boundary (e.g., "test" in "testing")
    # 2. Word at end of word boundary (e.g., "test" in "mytest") 
    # 3. Whole word (e.g., "test" as standalone word)
    if len(pattern) >= 3:  # Only for patterns of reasonable length
        # This pattern allows partial matches at word boundaries
        fuzzy_pattern = f"\\b{escaped}|{escaped}\\b"
    else:
        # For short patterns, require full word boundaries to avoid too many matches
        fuzzy_pattern = f"\\b{escaped}\\b"
    
    return fuzzy_pattern

def _execute_advanced_search(
    pattern: str, 
    base_path: str, 
    tool: str, 
    case_sensitive: bool, 
    context_lines: int, 
    file_pattern: Optional[str],
    fuzzy: bool = False
) -> Dict[str, List[Tuple[int, str]]]:
    """Execute advanced search using external tools.
    
    Returns:
        Dict mapping file paths to lists of (line_number, line_content) tuples
    """
    # Prepare search pattern
    search_pattern = pattern
    if fuzzy and tool != 'ugrep':  # ugrep has native fuzzy search
        search_pattern = _create_safe_fuzzy_pattern(pattern)
    
    # Build command based on tool
    if tool == 'ugrep':
        if fuzzy:
            cmd = ['ug', '--line-number', '--no-heading', '--fuzzy', '--ignore-files']  # Use native fuzzy search with gitignore
        else:
            cmd = ['ug', '--line-number', '--no-heading', '--fixed-strings', '--ignore-files']
        if not case_sensitive:
            cmd.append('--ignore-case')
        if context_lines > 0:
            cmd.extend(['-A', str(context_lines), '-B', str(context_lines)])
        if file_pattern:
            cmd.extend(['--include', file_pattern])

    elif tool == 'ripgrep':
        if fuzzy:
            cmd = ['rg', '--line-number', '--no-heading']  # Use regex mode for fuzzy
        else:
            cmd = ['rg', '--line-number', '--no-heading', '--fixed-strings']
        if not case_sensitive:
            cmd.append('--ignore-case')
        if context_lines > 0:
            cmd.extend(['-A', str(context_lines), '-B', str(context_lines)])
        if file_pattern:
            cmd.extend(['--glob', file_pattern])

    elif tool == 'ag':
        if fuzzy:
            cmd = ['ag', '--line-numbers', '--noheading']  # Use regex mode for fuzzy
        else:
            cmd = ['ag', '--line-numbers', '--noheading', '--literal']
        if not case_sensitive:
            cmd.append('--ignore-case')
        if context_lines > 0:
            cmd.extend(['-A', str(context_lines), '-B', str(context_lines)])
        if file_pattern:
            cmd.extend(['--', file_pattern])
            
    elif tool == 'grep':
        if fuzzy:
            cmd = ['grep', '-rn', '-E']  # -E for extended regex (safe fuzzy patterns)
        else:
            cmd = ['grep', '-rn', '-F']  # -F for fixed strings (exact match)
        if not case_sensitive:
            cmd.append('-i')
        if context_lines > 0:
            cmd.extend(['-A', str(context_lines), '-B', str(context_lines)])
        if file_pattern:
            cmd.extend(['--include=' + file_pattern])
    else:
        raise ValueError(f"Unknown search tool: {tool}")
    
    # Add pattern and base path
    cmd.extend([search_pattern, base_path])
    
    # Execute command
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=base_path
    )
    
    if result.returncode not in [0, 1]:  # 0 = found, 1 = not found, others = error
        raise Exception(f"Search command failed: {result.stderr}")
    
    # Parse output
    return _parse_search_output(result.stdout, base_path)

def _parse_search_output(output: str, base_path: str) -> Dict[str, List[Tuple[int, str]]]:
    """Parse search tool output into structured format.
    
    Returns:
        Dict mapping file paths to lists of (line_number, line_content) tuples
    """
    results = {}
    
    for line in output.splitlines():
        if not line.strip():
            continue
            
        # Parse format: filename:line_number:content
        parts = line.split(':', 2)
        if len(parts) >= 3:
            file_path = parts[0]
            try:
                line_number = int(parts[1])
                content = parts[2]
                
                # Make file path relative to base_path
                if file_path.startswith(base_path):
                    file_path = os.path.relpath(file_path, base_path)
                
                if file_path not in results:
                    results[file_path] = []
                
                results[file_path].append((line_number, content.strip()))
                
            except ValueError:
                # Skip lines that don't have valid line numbers
                continue
    
    return results

def main():
    """Entry point for the code indexer."""
    print("Starting Code Index MCP Server...", file=sys.stderr)

    # Ensure temporary directory exists using ProjectSettings
    temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)
    print(f"Temporary directory: {temp_dir}")

    try:
        # Use ProjectSettings to handle directory creation consistently
        temp_settings = ProjectSettings("", skip_load=True)
        print(f"Temporary directory setup completed")
    except Exception as e:
        print(f"Error setting up temporary directory: {e}", file=sys.stderr)

    mcp.run()

if __name__ == "__main__":
    main()
