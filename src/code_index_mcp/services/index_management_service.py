"""
Index Management Service - Business logic for index lifecycle management.

This service handles the business logic for index rebuilding, status monitoring,
and index-related operations. It composes technical tools to achieve business goals.
"""
import time
import logging

from typing import Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from .base_service import BaseService
from ..tools.scip import SCIPIndexTool
from ..tools.config import ProjectConfigTool


@dataclass
class IndexRebuildResult:
    """Business result for index rebuild operations."""
    file_count: int
    rebuild_time: float
    status: str
    message: str


class IndexManagementService(BaseService):
    """
    Business service for index lifecycle management.

    This service orchestrates index management workflows by composing
    technical tools to achieve business goals like rebuilding indexes,
    monitoring index status, and managing index lifecycle.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self._scip_tool = SCIPIndexTool()
        self._config_tool = ProjectConfigTool()

    def rebuild_index(self) -> str:
        """
        Rebuild the project index using business logic.

        This is the main business method that orchestrates the index
        rebuild workflow, ensuring proper validation, cleanup, and
        state management.

        Returns:
            Success message with rebuild information

        Raises:
            ValueError: If project not set up or rebuild fails
        """
        # Business validation
        self._validate_rebuild_request()

        # Business workflow: Execute rebuild
        result = self._execute_rebuild_workflow()

        # Business result formatting
        return self._format_rebuild_result(result)

    def get_rebuild_status(self) -> Dict[str, Any]:
        """
        Get current index rebuild status information.

        Returns:
            Dictionary with rebuild status and metadata
        """
        # Check if project is set up
        if not self.base_path:
            return {
                'status': 'not_initialized',
                'message': 'Project not initialized',
                'is_rebuilding': False
            }

        # Get index availability status - try to load existing index first
        if not self._scip_tool.is_index_available():
            self._scip_tool.load_existing_index(self.base_path)
        is_available = self._scip_tool.is_index_available()

        # Get basic status information
        status = {
            'status': 'ready' if is_available else 'needs_rebuild',
            'index_available': is_available,
            'is_rebuilding': False,  # We don't track background rebuilds in this simplified version
            'project_path': self.base_path
        }

        # Add file count if index is available
        if is_available:
            try:
                status['file_count'] = self._scip_tool.get_file_count()
                status['metadata'] = self._scip_tool.get_project_metadata()
            except Exception as e:
                status['error'] = f"Failed to get index metadata: {e}"

        return status

    def _validate_rebuild_request(self) -> None:
        """
        Validate the index rebuild request according to business rules.

        Raises:
            ValueError: If validation fails
        """
        # Business rule: Project must be set up
        self._require_project_setup()

    def _execute_rebuild_workflow(self) -> IndexRebuildResult:
        """
        Execute the core index rebuild business workflow.

        Returns:
            IndexRebuildResult with rebuild data
        """

        start_time = time.time()

        # Business step 1: Clear existing index state
        self._clear_existing_index()

        # Business step 2: Rebuild index using technical tool
        file_count = self._rebuild_index_data()

        # Business step 3: Update system state
        self._update_index_state(file_count)

        # Business step 4: Save updated configuration
        self._save_rebuild_metadata()

        rebuild_time = time.time() - start_time

        return IndexRebuildResult(
            file_count=file_count,
            rebuild_time=rebuild_time,
            status='success',
            message=f"Index rebuilt successfully with {file_count} files"
        )

    def _clear_existing_index(self) -> None:
        """Business logic to clear existing index state."""

        # Clear unified index manager
        self.helper.clear_index_cache()

        # No logging

    def _rebuild_index_data(self) -> int:
        """
        Business logic to rebuild index data using technical tools.

        Returns:
            Number of files indexed

        Raises:
            RuntimeError: If rebuild fails
        """
        try:
            # Business logic: Manual rebuild through unified manager
            if not self.index_manager:
                raise RuntimeError("Index manager not available")
            
            # Force rebuild
            success = self.index_manager.refresh_index(force=True)
            if not success:
                raise RuntimeError("Index rebuild failed")
            
            # Get file count from provider
            provider = self.index_provider
            if provider:
                file_count = len(provider.get_file_list())
                
                # Save the rebuilt index
                if not self.index_manager.save_index():
                    logger.warning("Manual rebuild: Index built but save failed")
                
                return file_count
            else:
                raise RuntimeError("No index provider available after rebuild")

        except Exception as e:
            raise RuntimeError(f"Failed to rebuild index: {e}") from e

    def _update_index_state(self, file_count: int) -> None:
        """Business logic to update system state after rebuild."""
        # No logging

        # Update context with new file count
        self.helper.update_file_count(file_count)

        # No logging

    def _save_rebuild_metadata(self) -> None:
        """Business logic to save SCIP index and metadata."""

        try:
            # Initialize config tool if needed
            if not self._config_tool.get_project_path():
                self._config_tool.initialize_settings(self.base_path)

            # Get the SCIP index from the tool
            scip_index = self._scip_tool.get_raw_index()
            if scip_index is None:
                raise RuntimeError("No SCIP index available to save")

            # Save the actual SCIP protobuf index
            settings = self._config_tool._settings
            settings.save_scip_index(scip_index)
            # Also save legacy JSON metadata for compatibility
            index_data = {
                'index_metadata': {
                    'version': '4.0-scip',
                    'source_format': 'scip',
                    'last_rebuilt': time.time(),
                    'rebuild_trigger': 'manual'
                },
                'project_metadata': self._scip_tool.get_project_metadata()
            }

            # Save metadata (legacy format)
            self._config_tool.save_index_data(index_data)

            # Update project configuration
            config = self._config_tool.create_default_config(self.base_path)
            config['last_indexed'] = time.time()
            self._config_tool.save_project_config(config)

        except Exception:
            pass

    def _format_rebuild_result(self, result: IndexRebuildResult) -> str:
        """
        Format the rebuild result according to business requirements.

        Args:
            result: Rebuild result data

        Returns:
            Formatted result string for MCP response
        """
        return f"Project re-indexed. Found {result.file_count} files."
