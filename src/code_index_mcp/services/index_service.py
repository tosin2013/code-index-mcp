"""
Index management service for the Code Index MCP server.

This service handles index building, management, file discovery,
and index refresh operations.
"""

import fnmatch
import json
import time
from typing import Dict, Any, Optional
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

    REFRESH_RATE_LIMIT_SECONDS = 5

    def __init__(self, ctx: Context):
        """
        Initialize the index service.

        Args:
            ctx: The MCP Context object
        """
        super().__init__(ctx)
        self._cached_last_refresh_time: Optional[float] = None

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

            # Update auto-refresh timer
            self._update_last_refresh_time()

        return f"Project re-indexed. Found {file_count} files."

    def find_files_by_pattern(self, pattern: str) -> Dict[str, Any]:
        """
        Find files matching a glob pattern.

        Handles the logic for find_files MCP tool with auto-refresh capability.

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

        # First search attempt using index
        matching_files = []
        if self.index_cache and 'files' in self.index_cache:
            for file_entry in self.index_cache['files']:
                file_path = file_entry.get('path', '')
                if fnmatch.fnmatch(file_path, pattern):
                    matching_files.append(file_path)

        # If no results found, try auto-refresh once (with rate limiting)
        if not matching_files:
            if self._should_auto_refresh():
                # Perform full re-index
                self._index_project(self.base_path)

                # Update last refresh time
                self._update_last_refresh_time()

                # Search again after refresh
                if self.index_cache and 'files' in self.index_cache:
                    for file_entry in self.index_cache['files']:
                        file_path = file_entry.get('path', '')
                        if fnmatch.fnmatch(file_path, pattern):
                            matching_files.append(file_path)

                if matching_files:
                    return ResponseFormatter.file_list_response(
                        matching_files,
                        f"✅ Found {len(matching_files)} files after refresh"
                    )
                else:
                    return ResponseFormatter.file_list_response(
                        [],
                        "⚠️ No files found even after refresh"
                    )
            else:
                # Rate limited
                remaining_time = self._get_remaining_refresh_time()
                return ResponseFormatter.file_list_response(
                    [],
                    f"⚠️ No files found - Rate limited. Try again in {remaining_time} seconds"
                )

        # Return successful results
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

    def _get_last_refresh_time(self) -> float:
        """Get last refresh time from config."""
        if not self.settings:
            return 0.0

        # Use cached value if available
        if hasattr(self, '_cached_last_refresh_time'):
            return self._cached_last_refresh_time

        config = self.settings.load_config()
        self._cached_last_refresh_time = config.get('last_auto_refresh_time', 0.0)
        return self._cached_last_refresh_time

    def _should_auto_refresh(self) -> bool:
        """Check if auto-refresh is allowed based on rate limit."""
        last_refresh_time = self._get_last_refresh_time()
        current_time = time.time()
        return (current_time - last_refresh_time) >= self.REFRESH_RATE_LIMIT_SECONDS

    def _update_last_refresh_time(self) -> None:
        """Update refresh time in both memory cache and persistent config."""
        current_time = time.time()

        # Update memory cache
        self._cached_last_refresh_time = current_time

        # Persist to config
        if self.settings:
            config = self.settings.load_config()
            config['last_auto_refresh_time'] = current_time
            self.settings.save_config(config)

    def _get_remaining_refresh_time(self) -> int:
        """Get remaining seconds until next refresh is allowed."""
        last_refresh_time = self._get_last_refresh_time()
        current_time = time.time()
        elapsed = current_time - last_refresh_time
        remaining = max(0, self.REFRESH_RATE_LIMIT_SECONDS - elapsed)
        return int(remaining)
