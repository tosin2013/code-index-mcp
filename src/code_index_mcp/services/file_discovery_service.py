"""
File Discovery Service - Business logic for intelligent file discovery.

This service handles the business logic for finding files in a project,
including pattern matching, relevance scoring, and result optimization.
It composes technical tools to achieve business goals.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base_service import BaseService
from ..tools.filesystem import FileMatchingTool
from ..utils import ValidationHelper


@dataclass
class FileDiscoveryResult:
    """Business result for file discovery operations."""
    files: List[str]
    total_count: int
    pattern_used: str
    search_strategy: str
    metadata: Dict[str, Any]


class FileDiscoveryService(BaseService):
    """
    Business service for intelligent file discovery.

    This service orchestrates file discovery workflows by composing
    technical tools to achieve business goals like finding relevant
    files, optimizing search results, and providing meaningful metadata.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self._matcher_tool = FileMatchingTool()

    def find_files(self, pattern: str, max_results: Optional[int] = None) -> Dict[str, Any]:
        """
        Find files matching the given pattern using intelligent discovery.

        This is the main business method that orchestrates the file discovery
        workflow, ensuring the index is available, applying business rules,
        and optimizing results for the user.

        Args:
            pattern: Glob pattern to search for (e.g., "*.py", "test_*.js")
            max_results: Maximum number of results to return (None for no limit)

        Returns:
            Dictionary with discovery results and metadata

        Raises:
            ValueError: If pattern is invalid or project not set up
        """
        # Business validation
        self._validate_discovery_request(pattern)

        # Business logic: Ensure index is ready
        self._ensure_index_available()

        # Business workflow: Execute discovery
        discovery_result = self._execute_discovery_workflow(pattern, max_results)

        # Business result formatting
        return self._format_discovery_result(discovery_result)

    def _validate_discovery_request(self, pattern: str) -> None:
        """
        Validate the file discovery request according to business rules.

        Args:
            pattern: Pattern to validate

        Raises:
            ValueError: If validation fails
        """
        # Ensure project is set up
        self._require_project_setup()

        # Validate pattern
        if not pattern or not pattern.strip():
            raise ValueError("Search pattern cannot be empty")

        # Business rule: Validate glob pattern
        error = ValidationHelper.validate_glob_pattern(pattern)
        if error:
            raise ValueError(f"Invalid search pattern: {error}")

    def _ensure_index_available(self) -> None:
        """
        Business logic to ensure index is available for discovery.

        Now uses unified index manager instead of direct SCIP tool access.

        Raises:
            RuntimeError: If index cannot be made available
        """
        # Business rule: Check if unified index manager is available
        if not self.index_manager:
            raise RuntimeError("Index manager not available. Please initialize project first.")
        
        # Business rule: Check if index provider is available
        provider = self.index_provider
        if provider and provider.is_available():
            return
        
        # Business logic: Initialize or refresh index
        try:
            if not self.index_manager.initialize():
                raise RuntimeError("Failed to initialize index manager")
            
            # Update context with file count
            provider = self.index_provider
            if provider:
                file_count = len(provider.get_file_list())
                self.helper.update_file_count(file_count)

        except Exception as e:
            raise RuntimeError(f"Failed to ensure index availability: {e}") from e

    def _execute_discovery_workflow(self, pattern: str, max_results: Optional[int]) -> FileDiscoveryResult:
        """
        Execute the core file discovery business workflow.

        Args:
            pattern: Search pattern
            max_results: Maximum results limit

        Returns:
            FileDiscoveryResult with discovery data
        """
        # Get all indexed files through unified interface
        provider = self.index_provider
        if not provider:
            raise RuntimeError("Index provider not available. Please initialize project first.")
        
        all_files = provider.get_file_list()

        # Apply pattern matching using technical tool
        matched_files = self._matcher_tool.match_glob_pattern(all_files, pattern)

        # Business logic: Apply relevance sorting
        sorted_files = self._matcher_tool.sort_by_relevance(matched_files, pattern)

        # Business logic: Apply result limits if specified
        if max_results:
            limited_files = self._matcher_tool.limit_results(sorted_files, max_results)
        else:
            limited_files = sorted_files

        # Business logic: Determine search strategy used
        search_strategy = self._determine_search_strategy(pattern, len(all_files), len(matched_files))

        # Extract file paths for result
        file_paths = [file_info.relative_path for file_info in limited_files]

        # Gather business metadata
        metadata = self._gather_discovery_metadata(all_files, matched_files, limited_files, pattern)

        return FileDiscoveryResult(
            files=file_paths,
            total_count=len(matched_files),
            pattern_used=pattern,
            search_strategy=search_strategy,
            metadata=metadata
        )

    def _determine_search_strategy(self, pattern: str, total_files: int, matched_files: int) -> str:
        """
        Business logic to determine what search strategy was most effective.

        Args:
            pattern: Search pattern used
            total_files: Total files in index
            matched_files: Number of files matched

        Returns:
            String describing the search strategy
        """
        is_glob_pattern = '*' in pattern or '?' in pattern

        if is_glob_pattern:
            # Glob pattern strategy determination
            if matched_files == 0:
                strategy = "glob_pattern_no_matches"
            elif matched_files < 10:
                strategy = "glob_pattern_focused"
            elif matched_files > total_files * 0.5:  # More than 50% of files matched
                strategy = "glob_pattern_very_broad"
            else:
                strategy = "glob_pattern_broad"
        else:
            # Exact filename strategy determination
            if matched_files == 0:
                strategy = "exact_filename_not_found"
            elif matched_files == 1:
                strategy = "exact_filename_found"
            else:
                strategy = "exact_filename_multiple_matches"

        return strategy

    def _get_project_metadata_from_index_manager(self) -> Dict[str, Any]:
        """
        Get project metadata from unified index manager.

        Returns:
            Dictionary with project metadata, or default values if not available
        """
        if self.index_manager:
            try:
                status = self.index_manager.get_index_status()
                if status and status.get('metadata'):
                    metadata = status['metadata']
                    return {
                        'project_root': metadata.get('project_root', self.base_path),
                        'total_files': status.get('file_count', 0),
                        'tool_version': metadata.get('tool_version', 'unified-manager'),
                        'languages': []  # Languages info not available in current IndexMetadata
                    }
                elif status:
                    # Fallback to status info
                    return {
                        'project_root': self.base_path,
                        'total_files': status.get('file_count', 0),
                        'tool_version': 'unified-manager',
                        'languages': []
                    }
            except (AttributeError, KeyError, TypeError):
                pass  # Fall through to default if metadata access fails
        
        # Fallback to default metadata if index manager not available
        return {
            'project_root': self.base_path,
            'total_files': 0,
            'tool_version': 'unknown',
            'languages': []
        }

    def _gather_discovery_metadata(self, all_files, matched_files, limited_files, pattern: str) -> Dict[str, Any]:
        """
        Gather business metadata about the discovery operation.

        Args:
            all_files: All files in index
            matched_files: Files that matched the pattern
            limited_files: Final limited result set
            pattern: Search pattern used

        Returns:
            Dictionary with business metadata
        """
        # Get project metadata from unified index manager
        project_metadata = self._get_project_metadata_from_index_manager()

        # Calculate business metrics
        match_ratio = len(matched_files) / len(all_files) if all_files else 0

        # Analyze file types in results
        file_languages = {}
        for file_info in matched_files:
            lang = file_info.language
            file_languages[lang] = file_languages.get(lang, 0) + 1

        # Analyze pattern characteristics
        pattern_type = 'glob' if ('*' in pattern or '?' in pattern) else 'exact'
        pattern_complexity = 'simple' if pattern.count('*') <= 1 else 'complex'

        return {
            'total_indexed_files': len(all_files),
            'total_matches': len(matched_files),
            'returned_results': len(limited_files),
            'match_ratio': round(match_ratio, 3),
            'languages_found': file_languages,
            'project_languages': project_metadata.get('languages', []),
            'search_efficiency': 'high' if match_ratio < 0.1 else 'medium' if match_ratio < 0.5 else 'low',
            'pattern_type': pattern_type,
            'pattern_complexity': pattern_complexity,
            'original_pattern': pattern
        }

    def _format_discovery_result(self, discovery_result: FileDiscoveryResult) -> Dict[str, Any]:
        """
        Format the discovery result according to business requirements.

        Args:
            discovery_result: Raw discovery result

        Returns:
            Formatted result dictionary for MCP response
        """
        return {
            'files': discovery_result.files,
            'total': discovery_result.total_count,
            'pattern': discovery_result.pattern_used,
            'strategy': discovery_result.search_strategy,
            'metadata': discovery_result.metadata,
            'status': 'success'
        }
