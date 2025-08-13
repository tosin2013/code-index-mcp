"""
Project Management Service - Business logic for project lifecycle management.

This service handles the business logic for project initialization, configuration,
and lifecycle management. It composes technical tools to achieve business goals.
"""
import json
import logging
from typing import Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

from .base_service import BaseService
from ..tools.config import ProjectConfigTool
from ..utils.response_formatter import ResponseFormatter
from ..constants import SUPPORTED_EXTENSIONS
from ..indexing.unified_index_manager import UnifiedIndexManager

logger = logging.getLogger(__name__)

# Optional SCIP tools import
try:
    from ..tools.scip import SCIPIndexTool
    SCIP_AVAILABLE = True
except ImportError:
    SCIPIndexTool = None
    SCIP_AVAILABLE = False


@dataclass
class ProjectInitializationResult:
    """Business result for project initialization operations."""
    project_path: str
    file_count: int
    index_source: str  # 'loaded_existing' or 'built_new'
    search_capabilities: str
    monitoring_status: str
    message: str


class ProjectManagementService(BaseService):
    """
    Business service for project lifecycle management.

    This service orchestrates project initialization workflows by composing
    technical tools to achieve business goals like setting up projects,
    managing configurations, and coordinating system components.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self._config_tool = ProjectConfigTool()
        self._scip_tool = SCIPIndexTool() if SCIP_AVAILABLE else None
        # Import FileWatcherTool locally to avoid circular import
        from ..tools.monitoring import FileWatcherTool
        self._watcher_tool = FileWatcherTool(ctx)
        

    @contextmanager
    def _noop_operation(self, *_args, **_kwargs):
        yield

    def initialize_project(self, path: str) -> str:
        """
        Initialize a project with comprehensive business logic.

        This is the main business method that orchestrates the project
        initialization workflow, handling validation, cleanup, setup,
        and coordination of all project components.

        Args:
            path: Project directory path to initialize

        Returns:
            Success message with project information

        Raises:
            ValueError: If path is invalid or initialization fails
        """
        # Business validation
        self._validate_initialization_request(path)

        # Business workflow: Execute initialization
        result = self._execute_initialization_workflow(path)

        # Business result formatting
        return self._format_initialization_result(result)

    def _validate_initialization_request(self, path: str) -> None:
        """
        Validate the project initialization request according to business rules.

        Args:
            path: Project path to validate

        Raises:
            ValueError: If validation fails
        """
        # Business rule: Path must be valid
        error = self._config_tool.validate_project_path(path)
        if error:
            raise ValueError(error)

    def _execute_initialization_workflow(self, path: str) -> ProjectInitializationResult:
        """
        Execute the core project initialization business workflow.

        Args:
            path: Project path to initialize

        Returns:
            ProjectInitializationResult with initialization data
        """
        # Normalize path for consistent processing
        normalized_path = self._config_tool.normalize_project_path(path)

        # Business step 1: Cleanup existing project state
        self._cleanup_existing_project()

        # Business step 2: Initialize project configuration
        self._initialize_project_configuration(normalized_path)

        # Business step 3: Initialize unified index manager
        index_result = self._initialize_index_manager(normalized_path)

        # Business step 4: Setup file monitoring
        monitoring_result = self._setup_file_monitoring(normalized_path)

        # Business step 5: Update system state
        self._update_project_state(normalized_path, index_result['file_count'])

        # Business step 6: Get search capabilities info
        search_info = self._get_search_capabilities_info()

        return ProjectInitializationResult(
            project_path=normalized_path,
            file_count=index_result['file_count'],
            index_source=index_result['source'],
            search_capabilities=search_info,
            monitoring_status=monitoring_result,
            message=f"Project initialized: {normalized_path}"
        )

    def _cleanup_existing_project(self) -> None:
        """Business logic to cleanup existing project state."""
        with self._noop_operation():
            # Stop existing file monitoring
            self._watcher_tool.stop_existing_watcher()

            # Clear existing index cache
            self.helper.clear_index_cache()

            # Clear SCIP tool state
            self._scip_tool.clear_index()

    def _initialize_project_configuration(self, project_path: str) -> None:
        """Business logic to initialize project configuration."""
        with self._noop_operation():

            # Initialize settings using config tool
            settings = self._config_tool.initialize_settings(project_path)

            # Update context with new settings
            self.helper.update_settings(settings)
            self.helper.update_base_path(project_path)

            self._config_tool.get_settings_path()

    def _initialize_index_manager(self, project_path: str) -> Dict[str, Any]:
        """
        Business logic to initialize unified index manager.

        Args:
            project_path: Project path

        Returns:
            Dictionary with initialization results
        """
        with self._noop_operation():
            # Create unified index manager
            index_manager = UnifiedIndexManager(project_path, self.helper.settings)
            
            # Store in context
            self.helper.update_index_manager(index_manager)
            
            # Initialize the manager (this will load existing or build new)
            if index_manager.initialize():
                provider = index_manager.get_provider()
                if provider:
                    file_count = len(provider.get_file_list())
                    return {
                        'file_count': file_count,
                        'source': 'unified_manager'
                    }
            
            # Fallback if initialization fails
            return {
                'file_count': 0,
                'source': 'failed'
            }

    def _is_valid_existing_index(self, index_data: Dict[str, Any]) -> bool:
        """
        Business rule to determine if existing index is valid and usable.

        Args:
            index_data: Index data to validate

        Returns:
            True if index is valid and usable, False otherwise
        """
        if not index_data or not isinstance(index_data, dict):
            return False

        # Business rule: Must have new format metadata
        if 'index_metadata' not in index_data:
            return False

        # Business rule: Must be compatible version
        version = index_data.get('index_metadata', {}).get('version', '')
        return version >= '3.0'

    def _load_existing_index(self, index_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Business logic to load and use existing index.

        Args:
            index_data: Existing index data

        Returns:
            Dictionary with loading results
        """
        

        # Note: Legacy index loading is now handled by UnifiedIndexManager
        # This method is kept for backward compatibility but functionality moved

        # Extract file count from metadata
        file_count = index_data.get('project_metadata', {}).get('total_files', 0)

        

        return {
            'file_count': file_count,
            'source': 'loaded_existing'
        }

    def _build_new_index(self, project_path: str) -> Dict[str, Any]:
        """
        Business logic to build new project index.

        Args:
            project_path: Project path to index

        Returns:
            Dictionary with build results
        """
        

        try:
            # Use SCIP tool to build index
            file_count = self._scip_tool.build_index(project_path)

            # Save the new index using config tool
            # Note: This is a simplified approach - in a full implementation,
            # we would need to convert SCIP data to the expected format
            index_data = {
                'index_metadata': {
                    'version': '4.0-scip',
                    'source_format': 'scip',
                    'created_at': __import__('time').time()
                },
                'project_metadata': {
                    'project_root': project_path,
                    'total_files': file_count,
                    'tool_version': 'scip-builder'
                }
            }

            self._config_tool.save_index_data(index_data)

            # Save project configuration
            config = self._config_tool.create_default_config(project_path)
            self._config_tool.save_project_config(config)

            # No logging

            return {
                'file_count': file_count,
                'source': 'built_new'
            }

        except Exception as e:
            raise ValueError(f"Failed to build project index: {e}") from e

    def _setup_file_monitoring(self, project_path: str) -> str:
        """
        Business logic to setup file monitoring for the project.

        Args:
            project_path: Project path to monitor

        Returns:
            String describing monitoring setup result
        """
        

        try:
            # Create rebuild callback that uses our SCIP tool
            def rebuild_callback():
                logger.info("File watcher triggered rebuild callback")
                try:
                    logger.debug(f"Starting index rebuild for: {project_path}")
                    # Business logic: File changed, rebuild through unified manager
                    if self.helper.index_manager:
                        success = self.helper.index_manager.refresh_index(force=True)
                        if success:
                            provider = self.helper.index_manager.get_provider()
                            file_count = len(provider.get_file_list()) if provider else 0
                            logger.info(f"File watcher rebuild completed successfully - indexed {file_count} files")
                            return True
                    
                    logger.warning("File watcher rebuild failed - no index manager available")
                    return False
                except Exception as e:
                    import traceback
                    logger.error(f"File watcher rebuild failed: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return False

            # Start monitoring using watcher tool
            success = self._watcher_tool.start_monitoring(project_path, rebuild_callback)

            if success:
                # Store watcher in context for later access
                self._watcher_tool.store_in_context()
                # No logging
                return "monitoring_active"
            else:
                self._watcher_tool.record_error("Failed to start file monitoring")
                return "monitoring_failed"

        except Exception as e:
            error_msg = f"File monitoring setup failed: {e}"
            self._watcher_tool.record_error(error_msg)
            return "monitoring_error"

    def _update_project_state(self, project_path: str, file_count: int) -> None:
        """Business logic to update system state after project initialization."""
        

        # Update context with file count
        self.helper.update_file_count(file_count)

        # No logging

    def _get_search_capabilities_info(self) -> str:
        """Business logic to get search capabilities information."""
        search_info = self._config_tool.get_search_tool_info()

        if search_info['available']:
            return f"Advanced search enabled ({search_info['name']})"
        else:
            return "Basic search available"

    def _format_initialization_result(self, result: ProjectInitializationResult) -> str:
        """
        Format the initialization result according to business requirements.

        Args:
            result: Initialization result data

        Returns:
            Formatted result string for MCP response
        """
        if result.index_source == 'unified_manager':
            message = (f"Project path set to: {result.project_path}. "
                      f"Initialized unified index with {result.file_count} files. "
                      f"{result.search_capabilities}.")
        elif result.index_source == 'failed':
            message = (f"Project path set to: {result.project_path}. "
                      f"Index initialization failed. Some features may be limited. "
                      f"{result.search_capabilities}.")
        else:
            message = (f"Project path set to: {result.project_path}. "
                      f"Indexed {result.file_count} files. "
                      f"{result.search_capabilities}.")

        if result.monitoring_status != "monitoring_active":
            message += " (File monitoring unavailable - use manual refresh)"

        return message

    def get_project_config(self) -> str:
        """
        Get the current project configuration for MCP resource.

        Returns:
            JSON formatted configuration string
        """

        # Check if project is configured
        if not self.helper.base_path:
            config_data = {
                "status": "not_configured",
                "message": ("Project path not set. Please use set_project_path "
                           "to set a project directory first."),
                "supported_extensions": SUPPORTED_EXTENSIONS
            }
            return ResponseFormatter.config_response(config_data)

        # Get settings stats
        settings_stats = self.helper.settings.get_stats() if self.helper.settings else {}

        config_data = {
            "base_path": self.helper.base_path,
            "supported_extensions": SUPPORTED_EXTENSIONS,
            "file_count": self.helper.file_count,
            "settings_directory": self.helper.settings.settings_path if self.helper.settings else "",
            "settings_stats": settings_stats
        }

        return ResponseFormatter.config_response(config_data)

    def get_project_structure(self) -> str:
        """
        Get the project directory structure for MCP resource.

        Returns:
            JSON formatted project structure
        """

        # Check if project is configured
        if not self.helper.base_path:
            structure_data = {
                "status": "not_configured",
                "message": ("Project path not set. Please use set_project_path "
                           "to set a project directory first.")
            }
            return json.dumps(structure_data, indent=2)

        # Check if we have index cache with directory tree
        if (hasattr(self.ctx.request_context.lifespan_context, 'index_cache') and
            self.ctx.request_context.lifespan_context.index_cache and
            'directory_tree' in self.ctx.request_context.lifespan_context.index_cache):

            directory_tree = self.ctx.request_context.lifespan_context.index_cache['directory_tree']
            return json.dumps(directory_tree, indent=2)

        # If no directory tree available, try to build basic structure
        try:
            # Use config tool to get basic project structure
            basic_structure = self._config_tool.get_basic_project_structure(self.helper.base_path)
            return json.dumps(basic_structure, indent=2)
        except Exception as e:
            error_data = {
                "error": f"Unable to get project structure: {e}",
                "status": "error"
            }
            return json.dumps(error_data, indent=2)
