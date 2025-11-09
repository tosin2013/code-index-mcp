"""Admin utilities for Code Index MCP server.

This module provides administrative functionality including:
- Automatic cleanup of idle projects
- Resource management and optimization
- Maintenance operations
"""

from .cleanup import CleanupResult, cleanup_idle_projects

__all__ = ["cleanup_idle_projects", "CleanupResult"]
