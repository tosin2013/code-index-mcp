"""
Project management service for the Code Index MCP server.

This service handles project initialization, configuration management,
and project structure operations.
"""

import asyncio
import os
import json
from mcp.server.fastmcp import Context

from .base_service import BaseService
from ..utils import ValidationHelper, ResponseFormatter
from ..project_settings import ProjectSettings
from ..constants import SUPPORTED_EXTENSIONS


class ProjectService(BaseService):
    """
    Service for managing project initialization and configuration.
    
    This service handles:
    - Project path initialization and validation
    - Project configuration management  
    - Project structure retrieval
    - Project metadata operations
    """
    
    def __init__(self, ctx: Context):
        """
        Initialize the project service.
        
        Args:
            ctx: The MCP Context object
        """
        super().__init__(ctx)
    
    def initialize_project(self, path: str) -> str:
        """
        Initialize a project with the given path.
        
        Handles the logic for set_project_path MCP tool.
        
        Args:
            path: The project directory path to initialize
            
        Returns:
            Success message with project information
            
        Raises:
            ValueError: If path is invalid or initialization fails
        """
        # Validate and normalize path
        norm_path = os.path.normpath(path)
        abs_path = os.path.abspath(norm_path)
        
        # Validate directory path
        error = ValidationHelper.validate_directory_path(abs_path)
        if error:
            raise ValueError(error)
        
        # Clear existing in-memory index and cache
        self.helper.clear_index_cache()
        
        # Update the base path in context
        self.helper.update_base_path(abs_path)
        
        # Create a new settings manager for the new path
        new_settings = ProjectSettings(abs_path, skip_load=False)
        self.helper.update_settings(new_settings)
        
        print(f"Project settings path: {new_settings.settings_path}")
        
        # Check for version migration
        print("Checking for index version and migration...")
        migration_result = new_settings.migrate_legacy_index()
        if not migration_result:
            print("Legacy index detected, will rebuild with new system")
        
        # Try to load existing index
        print(f"Project path set to: {abs_path}")
        print("Attempting to load existing index...")
        
        loaded_index_data = None
        try:
            loaded_index_data = new_settings.load_index()
        except Exception as e:
            print(f"Could not load existing index: {e}")
        
        if loaded_index_data and isinstance(loaded_index_data, dict):
            # Check if it's the new format
            if ('index_metadata' in loaded_index_data and 
                loaded_index_data.get('index_metadata', {}).get('version', '') >= '3.0'):
                print("Existing new-format index found and loaded successfully")
                
                # Update context with loaded index
                if hasattr(self.ctx.request_context.lifespan_context, 'index_cache'):
                    self.ctx.request_context.lifespan_context.index_cache.update(loaded_index_data)
                if hasattr(self.ctx.request_context.lifespan_context, 'file_index'):
                    self.ctx.request_context.lifespan_context.file_index.update(loaded_index_data)
                
                file_count = loaded_index_data.get('project_metadata', {}).get('total_files', 0)
                self.helper.update_file_count(file_count)
                
                # Get search capabilities info
                search_tool = new_settings.get_preferred_search_tool()
                search_info = (" Basic search available." if search_tool is None 
                             else f" Advanced search enabled ({search_tool.name}).")
                
                # Start file watcher service
                self._start_file_watcher(abs_path)
                
                return f"Project path set to: {abs_path}. Loaded existing index with {file_count} files.{search_info}"
            else:
                print("Old format index detected, will rebuild with new system")
        
        # Build new index
        try:
            file_count = self._index_project(abs_path)
        except Exception as e:
            print(f"Error building index: {e}")
            raise ValueError(f"Error building index: {e}")
        
        # Save project config
        config = {
            "base_path": abs_path,
            "supported_extensions": SUPPORTED_EXTENSIONS,
            "last_indexed": new_settings.load_config().get('last_indexed', None),
            "file_watcher": {
                "enabled": True,
                "debounce_seconds": 3.0,
                "additional_exclude_patterns": [],
                "monitored_extensions": [],  # Empty = use all supported extensions
                "exclude_patterns": [
                    ".git", ".svn", ".hg",
                    "node_modules", "__pycache__", ".venv", "venv",
                    ".DS_Store", "Thumbs.db",
                    "dist", "build", "target", ".idea", ".vscode",
                    ".pytest_cache", ".coverage", ".tox",
                    "bin", "obj"
                ]
            }
        }
        new_settings.save_config(config)
        
        # Get search capabilities info
        search_tool = new_settings.get_preferred_search_tool()
        search_info = (" Basic search available." if search_tool is None 
                     else f" Advanced search enabled ({search_tool.name}).")
        
        # Start file watcher service
        self._start_file_watcher(abs_path)
        
        return f"Project path set to: {abs_path}. Indexed {file_count} files.{search_info}"
    
    def get_project_config(self) -> str:
        """
        Get the current project configuration.
        
        Handles the logic for config://code-indexer MCP resource.
        
        Returns:
            JSON formatted configuration string
            
        Raises:
            ValueError: If project is not configured
        """
        # Check if base_path is set
        if not self.base_path:
            config_data = {
                "status": "not_configured",
                "message": "Project path not set. Please use set_project_path to set a project directory first.",
                "supported_extensions": SUPPORTED_EXTENSIONS
            }
            return ResponseFormatter.config_response(config_data)
        
        # Get settings stats
        settings_stats = self.settings.get_stats() if self.settings else {}
        
        config_data = {
            "base_path": self.base_path,
            "supported_extensions": SUPPORTED_EXTENSIONS,
            "file_count": self.file_count,
            "settings_directory": self.settings.settings_path if self.settings else "",
            "settings_stats": settings_stats
        }
        
        return ResponseFormatter.config_response(config_data)
    
    def get_project_structure(self) -> str:
        """
        Get the project directory structure.
        
        Handles the logic for structure://project MCP resource.
        
        Returns:
            JSON formatted project structure
            
        Raises:
            ValueError: If project is not configured or structure unavailable
        """
        # Check if base_path is set
        if not self.base_path:
            structure_data = {
                "status": "not_configured",
                "message": "Project path not set. Please use set_project_path to set a project directory first."
            }
            return json.dumps(structure_data, indent=2)
        
        # Check if we need to refresh the index
        if not self.index_cache:
            self._index_project(self.base_path)
        
        # Return the directory tree from the index
        if self.index_cache and 'directory_tree' in self.index_cache:
            return json.dumps(self.index_cache['directory_tree'], indent=2)
        else:
            error_data = {"error": "No directory tree available in index"}
            return json.dumps(error_data, indent=2)
    
    def _index_project(self, base_path: str) -> int:
        """
        Build the project index using the IndexBuilder system.
        
        Args:
            base_path: The project base path
            
        Returns:
            Number of files indexed
        """
        print(f"Building index for project: {base_path}")
        
        # Import here to avoid circular imports
        from ..indexing import IndexBuilder
        
        builder = IndexBuilder()
        code_index = builder.build_index(base_path)
        
        # Convert to dictionary for storage
        index_json = code_index.to_json()
        index_data = json.loads(index_json)
        
        # Store in cache
        if hasattr(self.ctx.request_context.lifespan_context, 'index_cache'):
            self.ctx.request_context.lifespan_context.index_cache.update(index_data)
        if hasattr(self.ctx.request_context.lifespan_context, 'file_index'):
            self.ctx.request_context.lifespan_context.file_index.update(index_data)
        
        file_count = code_index.project_metadata.get('total_files', 0)
        self.helper.update_file_count(file_count)
        
        # Save the index
        if self.settings:
            self.settings.save_index(code_index)
        
        print(f"Index built successfully with {file_count} files")
        return file_count
    
    def _start_file_watcher(self, base_path: str) -> None:
        """
        Initialize and start the file watcher service for the project.
        
        Args:
            base_path: The project base path to monitor
        """
        try:
            # Import FileWatcherService locally to avoid circular imports
            from .file_watcher_service import FileWatcherService
            from .index_service import IndexService
            
            # Initialize file watcher service
            file_watcher = FileWatcherService(self.ctx)
            
            # Create index service for rebuild callback
            index_service = IndexService(self.ctx)
            
            # Store file watcher service in context for cleanup
            if hasattr(self.ctx.request_context.lifespan_context, 'file_watcher_service'):
                self.ctx.request_context.lifespan_context.file_watcher_service = file_watcher
            
            # Start monitoring with background rebuild callback
            # We need to run this in an async context, so we'll create a task
            async def start_monitoring():
                success = await file_watcher.start_monitoring(
                    rebuild_callback=index_service.start_background_rebuild
                )
                if success:
                    print("File watcher service started successfully")
                else:
                    print("File watcher service failed to start - manual refresh required")
            
            # Schedule the async task
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If event loop is running, create task
                    asyncio.create_task(start_monitoring())
                else:
                    # If no event loop is running, run it
                    asyncio.run(start_monitoring())
            except RuntimeError:
                # If we can't get the loop, create a new one
                asyncio.run(start_monitoring())
                
        except Exception as e:
            print(f"Failed to initialize file watcher: {e}")
            print("Continuing without file watcher - manual refresh will be required")