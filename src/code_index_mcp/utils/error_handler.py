"""
Decorator-based error handling for MCP entry points.

This module provides consistent error handling across all MCP tools, resources, and prompts.
Supports both synchronous and asynchronous functions.
"""

import asyncio
import functools
import inspect
import json
from typing import Any, Callable, Dict, Union


def handle_mcp_errors(return_type: str = "str") -> Callable:
    """
    Decorator to handle exceptions in MCP entry points consistently.

    This decorator catches all exceptions and formats them according to the expected
    return type, providing consistent error responses across all MCP entry points.

    Supports both sync and async functions automatically.

    Args:
        return_type: The expected return type format
            - 'str': Returns error as string format "Error: {message}"
            - 'dict': Returns error as dict format {"error": "Operation failed: {message}"}
            - 'json': Returns error as JSON string with dict format
            - 'list': Returns error as list format [{"error": "Operation failed: {message}"}]

    Returns:
        Decorator function that wraps MCP entry points with error handling

    Example:
        @mcp.tool()
        @handle_mcp_errors(return_type='str')
        def set_project_path(path: str, ctx: Context) -> str:
            from ..services.project_management_service import ProjectManagementService
            return ProjectManagementService(ctx).initialize_project(path)

        @mcp.tool()
        @handle_mcp_errors(return_type='dict')
        async def ingest_code_from_git(git_url: str, ctx: Context) -> Dict[str, Any]:
            # Async function example
            result = await some_async_operation()
            return result
    """

    def decorator(func: Callable) -> Callable:
        # Check if function is async
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Union[str, Dict[str, Any]]:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_message = str(e)

                    if return_type == "dict":
                        return {"error": f"Operation failed: {error_message}"}
                    elif return_type == "json":
                        return json.dumps({"error": f"Operation failed: {error_message}"})
                    elif return_type == "list":
                        return [{"error": f"Operation failed: {error_message}"}]
                    else:  # return_type == 'str' (default)
                        return f"Error: {error_message}"

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Union[str, Dict[str, Any]]:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_message = str(e)

                    if return_type == "dict":
                        return {"error": f"Operation failed: {error_message}"}
                    elif return_type == "json":
                        return json.dumps({"error": f"Operation failed: {error_message}"})
                    elif return_type == "list":
                        return [{"error": f"Operation failed: {error_message}"}]
                    else:  # return_type == 'str' (default)
                        return f"Error: {error_message}"

            return sync_wrapper

    return decorator


def handle_mcp_resource_errors(func: Callable) -> Callable:
    """
    Specialized error handler for MCP resources that always return strings.

    This is a convenience decorator specifically for @mcp.resource decorated functions
    which always return string responses.

    Args:
        func: The MCP resource function to wrap

    Returns:
        Wrapped function with error handling

    Example:
        @mcp.resource("config://code-indexer")
        @handle_mcp_resource_errors
        def get_config() -> str:
            ctx = mcp.get_context()
            from ..services.project_management_service import ProjectManagementService
            return ProjectManagementService(ctx).get_project_config()
    """
    return handle_mcp_errors(return_type="str")(func)


def handle_mcp_tool_errors(return_type: str = "str") -> Callable:
    """
    Specialized error handler for MCP tools with flexible return types.

    This is a convenience decorator specifically for @mcp.tool decorated functions
    which may return either strings or dictionaries.

    Args:
        return_type: The expected return type ('str' or 'dict')

    Returns:
        Decorator function for MCP tools

    Example:
        @mcp.tool()
        @handle_mcp_tool_errors(return_type='dict')
        def find_files(pattern: str, ctx: Context) -> Dict[str, Any]:
            from ..services.file_discovery_service import FileDiscoveryService
            return FileDiscoveryService(ctx).find_files(pattern)
    """
    return handle_mcp_errors(return_type=return_type)
