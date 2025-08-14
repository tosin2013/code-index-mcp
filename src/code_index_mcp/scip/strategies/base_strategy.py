"""Base strategy interface for SCIP indexing - SCIP standard compliant."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import logging

from ..proto import scip_pb2
from ..core.symbol_manager import SCIPSymbolManager
from ..core.position_calculator import PositionCalculator
from ..core.local_reference_resolver import LocalReferenceResolver


logger = logging.getLogger(__name__)


class SCIPIndexerStrategy(ABC):
    """
    Base class for all SCIP indexing strategies.
    
    This version is fully compliant with SCIP standards and includes:
    - Standard SCIP symbol ID generation
    - Accurate position calculation
    - Local cross-file reference resolution
    - Two-phase analysis (symbol collection + reference resolution)
    """

    def __init__(self, priority: int = 50):
        """
        Initialize the strategy with a priority level.

        Args:
            priority: Strategy priority (higher = more preferred)
                     100 = Official tools (highest)
                     90 = Language-specific strategies
                     50 = Custom strategies (primary)
                     25 = Language-specialized defaults
                     10 = Generic defaults
                     1 = Fallback (lowest)
        """
        self.priority = priority
        
        # Core components (initialized per project)
        self.symbol_manager: Optional[SCIPSymbolManager] = None
        self.reference_resolver: Optional[LocalReferenceResolver] = None
        self.position_calculator: Optional[PositionCalculator] = None

    @abstractmethod
    def can_handle(self, extension: str, file_path: str) -> bool:
        """
        Check if this strategy can handle the given file type.

        Args:
            extension: File extension (e.g., '.py')
            file_path: Full path to the file

        Returns:
            True if this strategy can handle the file
        """

    @abstractmethod
    def get_language_name(self) -> str:
        """
        Get the language name for SCIP symbol generation.
        
        Returns:
            Language name (e.g., 'python', 'javascript', 'java')
        """

    def generate_scip_documents(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """
        Generate SCIP documents for the given files using two-phase analysis.

        Args:
            files: List of file paths to index
            project_path: Root path of the project

        Returns:
            List of SCIP Document objects

        Raises:
            StrategyError: If the strategy cannot process the files
        """
        import os
        from datetime import datetime
        strategy_name = self.__class__.__name__
        
        logger.info(f"🐍 {strategy_name}: Starting indexing of {len(files)} files")
        logger.debug(f"Files to process: {[os.path.basename(f) for f in files[:5]]}" + 
                    (f" ... and {len(files)-5} more" if len(files) > 5 else ""))
        
        try:
            # Initialize core components for this project
            logger.debug(f"🔧 {strategy_name}: Initializing components...")
            self._initialize_components(project_path)
            logger.debug(f"✅ {strategy_name}: Component initialization completed")
            
            # Phase 1: Collect all symbol definitions
            logger.info(f"📋 {strategy_name}: Phase 1 - Collecting symbol definitions from {len(files)} files")
            self._collect_symbol_definitions(files, project_path)
            logger.info(f"✅ {strategy_name}: Phase 1 completed")
            
            # Phase 2: Generate complete SCIP documents with resolved references
            logger.info(f"🔗 {strategy_name}: Phase 2 - Generating SCIP documents with resolved references")
            documents = self._generate_documents_with_references(files, project_path)
            logger.info(f"✅ {strategy_name}: Phase 2 completed, generated {len(documents)} documents")
            
            # Log statistics
            if self.reference_resolver:
                stats = self.reference_resolver.get_project_statistics()
                logger.info(f"📊 {strategy_name}: Statistics - {stats['total_definitions']} definitions, "
                           f"{stats['total_references']} references, {stats['files_with_symbols']} files")
            
            logger.info(f"🎉 {strategy_name}: Indexing completed")
            
            return documents
            
        except Exception as e:
            logger.error(f"❌ {strategy_name}: Failed: {e}")
            raise StrategyError(f"Failed to generate SCIP documents: {e}") from e

    def get_external_symbols(self):
        """Get external symbol information from symbol manager."""
        if self.symbol_manager:
            return self.symbol_manager.get_external_symbols()
        return []

    def get_dependencies(self):
        """Get dependency information from symbol manager.""" 
        if self.symbol_manager:
            return self.symbol_manager.get_dependencies()
        return {}

    def _initialize_components(self, project_path: str) -> None:
        """Initialize core components for the project."""
        import os
        project_name = os.path.basename(project_path)
        
        self.symbol_manager = SCIPSymbolManager(project_path, project_name)
        self.reference_resolver = LocalReferenceResolver(project_path)
        
        logger.debug(f"Initialized components for project: {project_name}")

    @abstractmethod
    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """
        Phase 1: Collect all symbol definitions from files.
        
        This phase should:
        1. Parse each file
        2. Extract symbol definitions
        3. Register them with the reference resolver
        
        Args:
            files: List of file paths to process
            project_path: Project root path
        """

    @abstractmethod
    def _generate_documents_with_references(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """
        Phase 2: Generate complete SCIP documents with resolved references.
        
        This phase should:
        1. Parse each file again
        2. Generate occurrences for definitions and references
        3. Resolve references using the reference resolver
        4. Create complete SCIP documents
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            List of complete SCIP documents
        """

    def get_priority(self) -> int:
        """Return the strategy priority."""
        return self.priority

    def get_strategy_name(self) -> str:
        """Return a human-readable name for this strategy."""
        class_name = self.__class__.__name__
        return class_name

    def is_available(self) -> bool:
        """
        Check if this strategy is available and ready to use.

        Returns:
            True if the strategy can be used
        """
        return True

    def _read_file_content(self, file_path: str) -> Optional[str]:
        """
        Read file content with encoding detection.
        
        Args:
            file_path: Path to file
            
        Returns:
            File content or None if reading fails
        """
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            
            logger.warning(f"Could not decode {file_path} with any encoding")
            return None
            
        except (OSError, PermissionError, FileNotFoundError) as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return None

    def _get_relative_path(self, file_path: str, project_path: str) -> str:
        """
        Get relative path from project root.
        
        Args:
            file_path: Absolute or relative file path
            project_path: Project root path
            
        Returns:
            Relative path from project root
        """
        try:
            from pathlib import Path
            path = Path(file_path)
            if path.is_absolute():
                return str(path.relative_to(Path(project_path)))
            return file_path
        except ValueError:
            # If path is not under project_path, return as-is
            return file_path

    def _create_scip_occurrence(self,
                               symbol_id: str,
                               range_obj: scip_pb2.Range,
                               symbol_roles: int,
                               syntax_kind: int) -> scip_pb2.Occurrence:
        """
        Create a SCIP occurrence.
        
        Args:
            symbol_id: SCIP symbol ID
            range_obj: SCIP Range object
            symbol_roles: SCIP symbol roles
            syntax_kind: SCIP syntax kind
            
        Returns:
            SCIP Occurrence object
        """
        occurrence = scip_pb2.Occurrence()
        occurrence.symbol = symbol_id
        occurrence.symbol_roles = symbol_roles
        occurrence.syntax_kind = syntax_kind
        occurrence.range.CopyFrom(range_obj)
        
        return occurrence

    def _create_scip_symbol_information(self,
                                       symbol_id: str,
                                       display_name: str,
                                       symbol_kind: int,
                                       documentation: List[str] = None) -> scip_pb2.SymbolInformation:
        """
        Create SCIP symbol information.
        
        Args:
            symbol_id: SCIP symbol ID
            display_name: Human-readable name
            symbol_kind: SCIP symbol kind
            documentation: Optional documentation
            
        Returns:
            SCIP SymbolInformation object
        """
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = display_name
        symbol_info.kind = symbol_kind
        
        if documentation:
            symbol_info.documentation.extend(documentation)
        
        return symbol_info


class StrategyError(Exception):
    """Base exception for strategy-related errors."""


class ToolUnavailableError(StrategyError):
    """Raised when a required tool is not available."""


class ConversionError(StrategyError):
    """Raised when conversion to SCIP format fails."""