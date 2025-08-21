"""SCIP Index Factory - Abstract factory ensuring complete SCIP Index generation."""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

from .types import SCIPSymbolDescriptor, SCIPPositionInfo
from .compliance_validator import SCIPComplianceValidator
from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class SCIPIndexFactory(ABC):
    """
    Abstract factory ensuring complete SCIP Index generation.

    This factory ensures all generated SCIP indexes contain the 6 essential content categories:
    1. Index Metadata
    2. Document Collection
    3. Symbol Definitions
    4. Symbol Occurrences
    5. Symbol Relationships
    6. External Symbols
    """

    def __init__(self, project_root: str):
        """
        Initialize SCIP index factory.

        Args:
            project_root: Absolute path to project root
        """
        self.project_root = Path(project_root).resolve()
        self.project_name = self.project_root.name
        self._validator = SCIPComplianceValidator()

        logger.debug(f"Initialized SCIP Index Factory for project: {self.project_name}")

    @abstractmethod
    def create_metadata(self, project_root: str) -> scip_pb2.Metadata:
        """
        Create standard-compliant metadata (Category 1).

        Args:
            project_root: Project root directory

        Returns:
            SCIP Metadata object with all required fields
        """
        pass

    @abstractmethod
    def create_document(self, file_path: str, content: str) -> scip_pb2.Document:
        """
        Create complete document with all occurrences and symbols (Category 2).

        Args:
            file_path: Path to source file
            content: File content

        Returns:
            SCIP Document with complete symbol information
        """
        pass

    @abstractmethod
    def create_symbol_definition(self,
                                name: str,
                                kind: str,
                                scope: List[str],
                                file_path: str,
                                position: Optional[SCIPPositionInfo] = None,
                                documentation: Optional[List[str]] = None) -> scip_pb2.SymbolInformation:
        """
        Create SCIP-compliant symbol definition (Category 3).

        Args:
            name: Symbol name
            kind: Symbol kind (function, class, variable, etc.)
            scope: Scope path
            file_path: File where symbol is defined
            position: Optional position information
            documentation: Optional documentation

        Returns:
            SCIP SymbolInformation object
        """
        pass

    @abstractmethod
    def create_symbol_occurrence(self,
                                symbol_id: str,
                                position: SCIPPositionInfo,
                                role: str,
                                syntax: str) -> scip_pb2.Occurrence:
        """
        Create SCIP-compliant symbol occurrence (Category 4).

        Args:
            symbol_id: SCIP symbol identifier
            position: Position information
            role: Symbol role (definition, reference, etc.)
            syntax: Syntax kind

        Returns:
            SCIP Occurrence object
        """
        pass

    @abstractmethod
    def create_symbol_relationship(self,
                                  source: str,
                                  target: str,
                                  rel_type: str) -> scip_pb2.Relationship:
        """
        Create SCIP-compliant symbol relationship (Category 5).

        Args:
            source: Source symbol ID
            target: Target symbol ID
            rel_type: Relationship type (inheritance, call, import, etc.)

        Returns:
            SCIP Relationship object
        """
        pass

    @abstractmethod
    def extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """
        Extract external symbols from imports and dependencies (Category 6).

        Args:
            documents: List of processed documents

        Returns:
            List of external symbol information
        """
        pass

    def _extract_symbol_relationships(self, files: List[str], symbol_definitions: Dict[str, str],
                                    documents: List[scip_pb2.Document]) -> None:
        """
        Extract symbol relationships (Category 5).

        Default implementation does nothing. Subclasses can override to provide
        language-specific relationship extraction.

        Args:
            files: List of file paths
            symbol_definitions: Mapping of symbol names to symbol IDs
            documents: List of processed documents to update with relationships
        """
        # Default implementation - no relationship extraction
        pass

    def build_complete_index(self, files: List[str]) -> scip_pb2.Index:
        """
        Build complete SCIP Index with all 6 content categories.

        Args:
            files: List of file paths to index

        Returns:
            Complete SCIP Index

        Raises:
            RuntimeError: If index validation fails
        """
        logger.info(f"Building complete SCIP index for {len(files)} files")

        index = scip_pb2.Index()

        # 1. Create metadata (Category 1)
        logger.debug("Creating index metadata...")
        index.metadata.CopyFrom(self.create_metadata(str(self.project_root)))

        # 2. Process all documents (Category 2)
        logger.debug(f"Processing {len(files)} documents...")
        documents = []
        symbol_definitions = {}  # Track all symbol definitions for relationship extraction

        for file_path in files:
            try:
                content = self._read_file(file_path)
                if content is not None:
                    doc = self.create_document(file_path, content)
                    documents.append(doc)

                    # Collect symbol definitions for relationship extraction
                    for symbol_info in doc.symbols:
                        symbol_definitions[symbol_info.display_name] = symbol_info.symbol

                    logger.debug(f"Processed document: {doc.relative_path}")
                else:
                    logger.warning(f"Skipped unreadable file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                continue

        index.documents.extend(documents)
        logger.info(f"Successfully processed {len(documents)} documents")

        # 2.5. Extract relationships (Category 5) - if supported by factory
        logger.debug("Extracting symbol relationships...")
        try:
            self._extract_symbol_relationships(files, symbol_definitions, documents)
            logger.info("Completed relationship extraction")
        except Exception as e:
            logger.warning(f"Relationship extraction failed: {e}")

        # 3. Extract external symbols (Category 6)
        logger.debug("Extracting external symbols...")
        try:
            external_symbols = self.extract_external_symbols(documents)
            index.external_symbols.extend(external_symbols)
            logger.info(f"Extracted {len(external_symbols)} external symbols")
        except Exception as e:
            logger.warning(f"Failed to extract external symbols: {e}")

        # 4. Validate complete index
        logger.debug("Validating complete index...")
        if not self._validator.validate_index(index):
            validation_summary = self._validator.get_validation_summary()
            error_msg = f"Index validation failed: {validation_summary['error_messages']}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Log final statistics
        total_occurrences = sum(len(doc.occurrences) for doc in documents)
        total_symbols = sum(len(doc.symbols) for doc in documents)

        logger.info(f"Created complete SCIP index:")
        logger.info(f"  - Documents: {len(documents)}")
        logger.info(f"  - Occurrences: {total_occurrences}")
        logger.info(f"  - Symbol Definitions: {total_symbols}")
        logger.info(f"  - External Symbols: {len(external_symbols)}")

        return index

    def validate_generated_content(self, content: Any) -> bool:
        """
        Validate any generated SCIP content for compliance.

        Args:
            content: SCIP content to validate (Index, Document, etc.)

        Returns:
            True if content is compliant
        """
        try:
            if isinstance(content, scip_pb2.Index):
                return self._validator.validate_index(content)
            elif isinstance(content, scip_pb2.Document):
                return self._validator.validate_document(content)
            else:
                logger.warning(f"Unknown content type for validation: {type(content)}")
                return False
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False

    def get_validation_summary(self) -> dict:
        """Get detailed validation summary from last validation operation."""
        return self._validator.get_validation_summary()

    def _read_file(self, file_path: str) -> Optional[str]:
        """
        Read file content with encoding detection.

        Args:
            file_path: Path to file

        Returns:
            File content or None if reading fails
        """
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except (OSError, PermissionError, FileNotFoundError) as e:
                logger.warning(f"Could not read {file_path}: {e}")
                return None

        logger.warning(f"Could not decode {file_path} with any supported encoding")
        return None

    def _get_relative_path(self, file_path: str) -> str:
        """
        Get relative path from project root.

        Args:
            file_path: Absolute or relative file path

        Returns:
            Relative path from project root
        """
        try:
            path = Path(file_path)
            if path.is_absolute():
                return str(path.relative_to(self.project_root)).replace('\\', '/')
            return file_path.replace('\\', '/')
        except ValueError:
            # If path is not under project_root, return as-is
            return str(Path(file_path)).replace('\\', '/')

    def _validate_symbol_id(self, symbol_id: str) -> bool:
        """Validate symbol ID format."""
        return self._validator.validate_symbol_id(symbol_id)

    def _validate_position(self, position: SCIPPositionInfo, content: str) -> bool:
        """Validate position information."""
        return self._validator.validate_position(position, content)

    def get_factory_info(self) -> dict:
        """Get information about this factory instance."""
        return {
            'project_root': str(self.project_root),
            'project_name': self.project_name,
            'factory_type': self.__class__.__name__,
            'supported_categories': [
                'Index Metadata',
                'Document Collection',
                'Symbol Definitions',
                'Symbol Occurrences',
                'Symbol Relationships',
                'External Symbols'
            ]
        }
