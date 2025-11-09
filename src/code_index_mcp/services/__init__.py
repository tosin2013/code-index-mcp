"""
Service layer for the Code Index MCP server.

This package contains domain-specific services that handle the business logic
for different areas of functionality:


- SearchService: Code search operations and search tool management
- FileService: File operations, content retrieval, and analysis
- SettingsService: Settings management and directory operations

Each service follows a consistent pattern:
- Constructor accepts MCP Context parameter
- Methods correspond to MCP entry points
- Clear domain boundaries with no cross-service dependencies
- Shared utilities accessed through utils module
- Meaningful exceptions raised for error conditions
"""

# New Three-Layer Architecture Services
from .base_service import BaseService
from .code_intelligence_service import CodeIntelligenceService
from .file_discovery_service import FileDiscoveryService

# Simple Services
from .file_service import FileService  # Simple file reading for resources
from .file_watcher_service import FileWatcherService  # Low-level service, still needed
from .index_management_service import IndexManagementService
from .project_management_service import ProjectManagementService
from .search_service import SearchService  # Already follows clean architecture

# Semantic Search (Phase 3A)
from .semantic_search_service import SemanticSearchResult, SemanticSearchService
from .settings_service import SettingsService
from .system_management_service import SystemManagementService

__all__ = [
    # New Architecture
    "BaseService",
    "ProjectManagementService",
    "IndexManagementService",
    "FileDiscoveryService",
    "CodeIntelligenceService",
    "SystemManagementService",
    "SearchService",
    "SettingsService",
    # Simple Services
    "FileService",  # Simple file reading for resources
    "FileWatcherService",  # Keep as low-level service
    # Semantic Search
    "SemanticSearchService",
    "SemanticSearchResult",
]
