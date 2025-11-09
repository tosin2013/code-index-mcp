"""
Middleware package for Code Index MCP Server.

This package contains middleware components for HTTP mode:
- Authentication: API key validation against Google Secret Manager
- Authorization: User context extraction and access control
"""

from .auth import AuthMiddleware, get_user_from_request

__all__ = ["AuthMiddleware", "get_user_from_request"]
