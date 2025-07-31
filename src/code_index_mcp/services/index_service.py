"""
Index management service for the Code Index MCP server.

This service handles index building, management, file discovery,
and index refresh operations.
"""

import asyncio
import fnmatch
import json
import time
from typing import Dict, Any, Optional, Callable
from mcp.server.fastmcp import Context

from .base_service import BaseService
from ..utils import ValidationHelper, ResponseFormatter


class IndexService(BaseService):
    """
    Service for managing project indexing and file discovery.

    This service handles:
    - Index building and rebuilding
    - File discovery and pattern matching
    - Index refresh operations
    - Index statistics and metadata
    """

    def __init__(self, ctx: Context):
        """
        Initialize the index service.

        Args:
            ctx: The MCP Context object
        """
        super().__init__(ctx)
        self.is_rebuilding = False
        self.rebuild_in_progress_lock = asyncio.Lock()

    def rebuild_index(self) -> str:
        """
        Rebuild the project index.

        Handles the logic for refresh_index MCP tool.

        Returns:
            Success message with file count information

        Raises:
            ValueError: If project is not set up or rebuild fails
        """
        self._require_project_setup()

        # Clear existing index
        self.helper.clear_index_cache()

        # Re-index the project
        file_count = self._index_project(self.base_path)

        # Update the last indexed timestamp in config
        if self.settings:
            config = self.settings.load_config()
            self.settings.save_config({
                **config,
                'last_indexed': time.time()
            })


        return f"Project re-indexed. Found {file_count} files."

    def find_files_by_pattern(self, pattern: str) -> Dict[str, Any]:
        """
        Find files matching a glob pattern.

        Simplified version - file watcher handles all index updates proactively.

        Args:
            pattern: Glob pattern to match files against

        Returns:
            Dictionary with files list and status information

        Raises:
            ValueError: If project is not set up or pattern is invalid
        """
        self._require_project_setup()

        # Validate glob pattern
        error = ValidationHelper.validate_glob_pattern(pattern)
        if error:
            raise ValueError(error)

        # Check if we need to index the project initially
        if not self.index_cache:
            self._index_project(self.base_path)

        # Search using current index
        matching_files = []
        if self.index_cache and 'files' in self.index_cache:
            for file_entry in self.index_cache['files']:
                file_path = file_entry.get('path', '')
                if fnmatch.fnmatch(file_path, pattern):
                    matching_files.append(file_path)

        # Return results - file watcher now handles all index updates proactively
        return ResponseFormatter.file_list_response(
            matching_files,
            f"✅ Found {len(matching_files)} files"
        )

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get index statistics and metadata.

        Returns:
            Dictionary with index statistics

        Raises:
            ValueError: If project is not set up
        """
        self._require_project_setup()

        stats = {
            "file_count": self.file_count,
            "base_path": self.base_path,
            "index_available": bool(self.index_cache),
            "has_directory_tree": ('directory_tree' in self.index_cache
                                   if self.index_cache else False),
            "has_files_list": 'files' in self.index_cache if self.index_cache else False
        }

        if self.index_cache and 'project_metadata' in self.index_cache:
            stats.update(self.index_cache['project_metadata'])

        return stats

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

    def start_background_rebuild(self) -> bool:
        """
        Start index rebuild in background without blocking searches.
        
        Returns:
            True if rebuild started, False if already in progress
        """
        if self.is_rebuilding:
            return False
        
        # Create background task
        task = asyncio.create_task(self._background_rebuild())
        task.add_done_callback(self._on_rebuild_complete)
        
        return True
    
    async def _background_rebuild(self) -> None:
        """
        Perform index rebuild asynchronously.
        """
        async with self.rebuild_in_progress_lock:
            try:
                self.is_rebuilding = True
                start_time = time.time()
                
                # Build new index using existing logic
                file_count = self._index_project(self.base_path)
                
                duration = time.time() - start_time
                print(f"Background rebuild completed in {duration:.2f}s with {file_count} files")
                
            except Exception as e:
                print(f"Background rebuild failed: {e}")
                raise
            finally:
                self.is_rebuilding = False
    
    def _on_rebuild_complete(self, task: asyncio.Task) -> None:
        """
        Handle rebuild completion or failure.
        
        Args:
            task: The completed asyncio task
        """
        try:
            task.result()  # Raise any exceptions that occurred
        except Exception as e:
            print(f"Background rebuild task failed: {e}")
    
    def get_rebuild_status(self) -> dict:
        """
        Get current rebuild status information.
        
        Returns:
            Dictionary with rebuild status
        """
        return {
            "is_rebuilding": self.is_rebuilding,
            "index_cache_size": len(self.index_cache.get('files', [])) if self.index_cache else 0
        }
