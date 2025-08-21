"""SCIP Standard Framework - SCIP standard framework enforcing compliance."""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any

from .types import SCIPSymbolContext, SCIPSymbolExtractor
from .symbol_generator import SCIPSymbolGenerator
from .position_calculator import SCIPPositionCalculator
from .base.enum_mapper import BaseEnumMapper
from .compliance_validator import SCIPComplianceValidator
from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class SCIPStandardFramework(ABC):
    """SCIP standard framework - enforces compliance across all language strategies."""
    
    def __init__(self, language: str, project_root: str, version: str = "HEAD"):
        """
        Initialize SCIP standard framework.
        
        Args:
            language: Programming language (e.g., 'python', 'javascript')
            project_root: Absolute path to project root
            version: Project version for symbol generation
        """
        self.language = language.lower()
        self.project_root = Path(project_root).resolve()
        self.version = version
        
        # Core components - mandatory initialization
        self._symbol_generator = self._create_symbol_generator()
        self._position_calculator = SCIPPositionCalculator()
        self._enum_mapper = self._create_enum_mapper()
        self._validator = SCIPComplianceValidator()
        
        logger.debug(f"Initialized SCIP framework for {language} project: {self.project_root.name}")
    
    def _create_symbol_generator(self) -> SCIPSymbolGenerator:
        """Create SCIP standard symbol generator."""
        return SCIPSymbolGenerator(
            scheme=f"scip-{self.language}",
            package_manager="local",
            package_name=self.project_root.name,
            version=self.version
        )
    
    @abstractmethod
    def _create_enum_mapper(self) -> BaseEnumMapper:
        """Subclasses must implement language-specific enum mapping."""
        raise NotImplementedError("Subclasses must implement _create_enum_mapper")
    
    def process_file(self, file_path: str, extractor: SCIPSymbolExtractor) -> scip_pb2.Document:
        """
        Standardized file processing pipeline - enforces compliance.
        
        Args:
            file_path: Path to file to process
            extractor: Symbol extractor implementation
            
        Returns:
            SCIP Document with full compliance validation
            
        Raises:
            ValueError: If input validation fails
            RuntimeError: If processing fails or compliance validation fails
        """
        
        # 1. Validate input
        self._validate_file_input(file_path)
        
        # 2. Create document base structure
        document = self._create_document_base(file_path)
        
        # 3. Read content and create context
        content = self._read_file_safe(file_path)
        context = SCIPSymbolContext(
            file_path=file_path,
            content=content,
            scope_stack=[],
            imports={}
        )
        
        # 4. Extract symbols and generate SCIP elements
        occurrences, symbols = self._extract_scip_elements(context, extractor)
        
        # 5. Validate and add to document
        document.occurrences.extend(self._validate_occurrences(occurrences))
        document.symbols.extend(self._validate_symbols(symbols))
        
        # 6. Final compliance check
        if not self._validator.validate_document(document):
            validation_summary = self._validator.get_validation_summary()
            raise RuntimeError(f"Document failed SCIP compliance validation: {validation_summary['error_messages']}")
        
        logger.debug(f"Successfully processed {file_path} with {len(document.occurrences)} occurrences and {len(document.symbols)} symbols")
        return document
    
    def process_files(self, file_paths: List[str], extractors: Dict[str, SCIPSymbolExtractor]) -> List[scip_pb2.Document]:
        """
        Process multiple files with appropriate extractors.
        
        Args:
            file_paths: List of file paths to process
            extractors: Mapping of file extensions to extractors
            
        Returns:
            List of SCIP documents
        """
        documents = []
        
        for file_path in file_paths:
            try:
                # Determine appropriate extractor
                file_ext = Path(file_path).suffix.lower()
                extractor = extractors.get(file_ext)
                
                if not extractor:
                    logger.warning(f"No extractor available for {file_ext}, skipping {file_path}")
                    continue
                
                # Process file
                document = self.process_file(file_path, extractor)
                documents.append(document)
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                # Continue processing other files
                continue
        
        logger.info(f"Processed {len(documents)} files successfully out of {len(file_paths)} total")
        return documents
    
    def create_complete_index(self, file_paths: List[str], extractors: Dict[str, SCIPSymbolExtractor]) -> scip_pb2.Index:
        """
        Create complete SCIP index with all 6 essential content categories.
        
        Args:
            file_paths: List of file paths to index
            extractors: Mapping of file extensions to extractors
            
        Returns:
            Complete SCIP Index
        """
        index = scip_pb2.Index()
        
        # 1. Create metadata (Category 1)
        index.metadata.CopyFrom(self._create_metadata())
        
        # 2. Process all documents (Category 2)
        documents = self.process_files(file_paths, extractors)
        index.documents.extend(documents)
        
        # 3. Extract external symbols (Category 6)
        external_symbols = self._extract_external_symbols(documents)
        index.external_symbols.extend(external_symbols)
        
        # 4. Validate complete index
        if not self._validator.validate_index(index):
            validation_summary = self._validator.get_validation_summary()
            raise RuntimeError(f"Index failed SCIP compliance validation: {validation_summary['error_messages']}")
        
        logger.info(f"Created complete SCIP index with {len(documents)} documents and {len(external_symbols)} external symbols")
        return index
    
    def _validate_file_input(self, file_path: str) -> None:
        """Validate file input parameters."""
        if not file_path:
            raise ValueError("File path cannot be empty")
        
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"File does not exist: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
    
    def _create_document_base(self, file_path: str) -> scip_pb2.Document:
        """Create base document structure."""
        document = scip_pb2.Document()
        
        # Set relative path from project root
        try:
            relative_path = Path(file_path).relative_to(self.project_root)
            document.relative_path = str(relative_path).replace('\\', '/')
        except ValueError:
            # File is outside project root, use absolute path
            document.relative_path = str(Path(file_path)).replace('\\', '/')
        
        document.language = self.language
        
        return document
    
    def _create_metadata(self) -> scip_pb2.Metadata:
        """Create SCIP metadata with standard compliance."""
        metadata = scip_pb2.Metadata()
        metadata.version = scip_pb2.ProtocolVersion.UnspecifiedProtocolVersion
        
        # Tool information
        metadata.tool_info.name = "code-index-mcp"
        metadata.tool_info.version = "2.1.1"
        metadata.tool_info.arguments.extend(["scip-indexing", self.language])
        
        # Project information
        metadata.project_root = str(self.project_root)
        metadata.text_document_encoding = scip_pb2.UTF8
        
        return metadata
    
    def _read_file_safe(self, file_path: str) -> str:
        """Read file content with encoding detection."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        
        raise RuntimeError(f"Could not decode {file_path} with any supported encoding")
    
    def _extract_scip_elements(self, context: SCIPSymbolContext, extractor: SCIPSymbolExtractor) -> tuple:
        """Extract SCIP elements using provided extractor."""
        occurrences = []
        symbols = []
        
        try:
            # Extract symbol definitions
            for symbol_desc in extractor.extract_symbols(context):
                try:
                    # Create SCIP symbol
                    symbol_id = self._symbol_generator.create_local_symbol(symbol_desc)
                    
                    # Map to SCIP enums
                    symbol_kind = self._enum_mapper.validate_and_map_symbol_kind(symbol_desc.kind)
                    
                    # Create symbol information
                    symbol_info = scip_pb2.SymbolInformation()
                    symbol_info.symbol = symbol_id
                    symbol_info.display_name = symbol_desc.name
                    symbol_info.kind = symbol_kind
                    
                    symbols.append(symbol_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to create symbol for {symbol_desc.name}: {e}")
                    continue
            
            # Extract symbol references
            for symbol_desc, position_info in extractor.extract_references(context):
                try:
                    # Create SCIP symbol ID
                    symbol_id = self._symbol_generator.create_local_symbol(symbol_desc)
                    
                    # Create SCIP range
                    range_obj = scip_pb2.Range()
                    range_obj.start.extend([position_info.start_line, position_info.start_column])
                    range_obj.end.extend([position_info.end_line, position_info.end_column])
                    
                    # Map to SCIP enums
                    symbol_role = self._enum_mapper.validate_and_map_symbol_role("reference")
                    syntax_kind = self._enum_mapper.validate_and_map_syntax_kind("identifier")
                    
                    # Create occurrence
                    occurrence = scip_pb2.Occurrence()
                    occurrence.symbol = symbol_id
                    occurrence.symbol_roles = symbol_role
                    occurrence.syntax_kind = syntax_kind
                    occurrence.range.CopyFrom(range_obj)
                    
                    occurrences.append(occurrence)
                    
                except Exception as e:
                    logger.warning(f"Failed to create occurrence for {symbol_desc.name}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Symbol extraction failed: {e}")
            raise RuntimeError(f"Failed to extract symbols: {e}")
        
        return occurrences, symbols
    
    def _validate_occurrences(self, occurrences: List[scip_pb2.Occurrence]) -> List[scip_pb2.Occurrence]:
        """Validate occurrences for SCIP compliance."""
        validated = []
        
        for occurrence in occurrences:
            try:
                # Validate symbol ID
                if not self._validator.validate_symbol_id(occurrence.symbol):
                    logger.warning(f"Invalid symbol ID in occurrence: {occurrence.symbol}")
                    continue
                
                # Basic validation passed
                validated.append(occurrence)
                
            except Exception as e:
                logger.warning(f"Occurrence validation failed: {e}")
                continue
        
        logger.debug(f"Validated {len(validated)} out of {len(occurrences)} occurrences")
        return validated
    
    def _validate_symbols(self, symbols: List[scip_pb2.SymbolInformation]) -> List[scip_pb2.SymbolInformation]:
        """Validate symbols for SCIP compliance."""
        validated = []
        
        for symbol in symbols:
            try:
                # Validate symbol ID
                if not self._validator.validate_symbol_id(symbol.symbol):
                    logger.warning(f"Invalid symbol ID in symbol info: {symbol.symbol}")
                    continue
                
                # Basic validation passed
                validated.append(symbol)
                
            except Exception as e:
                logger.warning(f"Symbol validation failed: {e}")
                continue
        
        logger.debug(f"Validated {len(validated)} out of {len(symbols)} symbols")
        return validated
    
    def _extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """Extract external symbols from processed documents."""
        external_symbols = []
        
        # This is a placeholder implementation
        # Subclasses should implement language-specific external symbol extraction
        # based on import statements and dependencies
        
        return external_symbols
    
    def get_framework_info(self) -> dict:
        """Get information about this framework instance."""
        return {
            'language': self.language,
            'project_root': str(self.project_root),
            'project_name': self.project_root.name,
            'version': self.version,
            'components': {
                'symbol_generator': self._symbol_generator.get_generator_info(),
                'enum_mapper': self._enum_mapper.get_enum_info(),
                'position_calculator': True,
                'compliance_validator': True
            }
        }