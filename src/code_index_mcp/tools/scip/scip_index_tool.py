"""
SCIP Index Tool - Pure technical component for SCIP index operations.

This tool handles low-level SCIP index operations without any business logic.
It provides technical capabilities that can be composed by business services.
"""

from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path
import logging
from ...scip.proto.scip_pb2 import Index as SCIPIndex
from ...indexing.scip_builder import SCIPIndexBuilder

logger = logging.getLogger(__name__)

# Import FileInfo from the central location to avoid duplication
from ...indexing.index_provider import FileInfo


class SCIPIndexTool:
    """
    Pure technical component for SCIP index operations.

    This tool provides low-level SCIP index capabilities without any
    business logic or decision making. It's designed to be composed
    by business services to achieve business goals.
    """

    def __init__(self):
        self._scip_index: Optional[SCIPIndex] = None
        self._builder = SCIPIndexBuilder()
        self._project_path: Optional[str] = None
        self._settings = None  # Will be set when needed

    def is_index_available(self) -> bool:
        """
        Check if SCIP index is available and ready for use.

        Returns:
            True if index is available, False otherwise
        """
        return self._scip_index is not None and len(self._scip_index.documents) > 0

    def build_index(self, project_path: str) -> int:
        """
        Build SCIP index for the specified project path.
        
        This is a pure technical operation that unconditionally rebuilds the index.
        Business logic for deciding when to rebuild should be handled by the caller.

        Args:
            project_path: Absolute path to the project directory

        Returns:
            Number of files indexed

        Raises:
            ValueError: If project path is invalid
            RuntimeError: If index building fails
        """
        if not Path(project_path).exists():
            logger.error(f"SCIP INDEX: Project path does not exist: {project_path}")
            raise ValueError(f"Project path does not exist: {project_path}")

        # Build new index (pure technical operation)
        try:
            logger.info(f"Building index for {project_path}")
            self._project_path = project_path
            
            # Initialize settings for this project
            from ...project_settings import ProjectSettings
            self._settings = ProjectSettings(project_path, skip_load=False)
            
            self._scip_index = self._builder.build_scip_index(project_path)
            logger.info(f"Built index with {len(self._scip_index.documents)} files")

            return len(self._scip_index.documents)
        except Exception as e:
            logger.error(f"Failed to build index: {e}")
            raise RuntimeError(f"Failed to build SCIP index: {e}") from e

    def save_index(self) -> bool:
        """
        Save the current SCIP index to disk.
        
        This is a pure technical operation that saves the current in-memory index.

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            if self._settings is None:
                logger.error("No settings available, cannot save index")
                return False
                
            if self._scip_index is None:
                logger.error("No index available to save")
                return False
                
            self.save_current_index()
            logger.info("Index saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            return False

    def get_file_list(self) -> List[FileInfo]:
        """
        Get list of all indexed files.

        Returns:
            List of FileInfo objects for all indexed files

        Raises:
            RuntimeError: If index is not available
        """
        if not self.is_index_available():
            raise RuntimeError("SCIP index is not available. Call build_index() first.")

        files = []
        for document in self._scip_index.documents:
            file_info = FileInfo(
                relative_path=document.relative_path,
                language=document.language,
                absolute_path=str(Path(self._project_path) / document.relative_path) if self._project_path else ""
            )
            files.append(file_info)

        return files

    def get_file_count(self) -> int:
        """
        Get the number of indexed files.

        Returns:
            Number of files in the index

        Raises:
            RuntimeError: If index is not available
        """
        if not self.is_index_available():
            raise RuntimeError("SCIP index is not available")

        return len(self._scip_index.documents)

    def get_project_metadata(self) -> dict:
        """
        Get project metadata from SCIP index.

        Returns:
            Dictionary containing project metadata

        Raises:
            RuntimeError: If index is not available
        """
        if not self.is_index_available():
            raise RuntimeError("SCIP index is not available")

        return {
            'project_root': self._scip_index.metadata.project_root,
            'total_files': len(self._scip_index.documents),
            'tool_version': self._scip_index.metadata.tool_info.version,
            'languages': list(set(doc.language for doc in self._scip_index.documents))
        }

    def load_existing_index(self, project_path: str) -> bool:
        """
        Try to load existing SCIP index from disk.

        Args:
            project_path: Absolute path to the project directory

        Returns:
            True if loaded successfully, False if no index exists or load failed
        """
        try:
            from ...project_settings import ProjectSettings

            self._project_path = project_path
            settings = ProjectSettings(project_path, skip_load=False)
            self._settings = settings

            # Try to load existing SCIP index
            scip_index = settings.load_scip_index()
            if scip_index is not None:
                self._scip_index = scip_index
                return True
            else:
                return False

        except Exception as e:
            return False

    def save_current_index(self) -> bool:
        """
        Save the current SCIP index to disk.

        Returns:
            True if saved successfully, False otherwise
        """
        if self._scip_index is None:
            return False

        if self._settings is None:
            return False

        try:
            self._settings.save_scip_index(self._scip_index)
            return True
        except Exception:
            return False

    def clear_index(self) -> None:
        """Clear the current SCIP index."""
        self._scip_index = None
        self._project_path = None
        # Keep settings for potential reload

    def get_raw_index(self) -> Optional[SCIPIndex]:
        """
        Get the raw SCIP index for advanced operations.

        Note: This should only be used by other technical tools,
        not by business services.

        Returns:
            Raw SCIP index or None if not available
        """
        return self._scip_index
