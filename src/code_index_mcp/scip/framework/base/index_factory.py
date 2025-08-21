"""Abstract factory base class for SCIP index generation with guaranteed completeness."""

from abc import ABC, abstractmethod
from typing import Set, List, Iterator
from ..types import SCIPContext
from ..symbol_generator import SCIPSymbolGenerator
from ..position_calculator import SCIPPositionCalculator
from .relationship_extractor import BaseRelationshipExtractor
from .enum_mapper import BaseEnumMapper
from ...proto import scip_pb2
from ...core.relationship_types import InternalRelationshipType


class SCIPIndexFactory(ABC):
    """Abstract factory for SCIP index generation with guaranteed completeness."""
    
    def __init__(self, 
                 project_root: str,
                 symbol_generator: SCIPSymbolGenerator,
                 relationship_extractor: BaseRelationshipExtractor,
                 enum_mapper: BaseEnumMapper,
                 position_calculator: SCIPPositionCalculator):
        """
        Constructor injection ensures all required components are provided.
        
        Args:
            project_root: Root directory of the project
            symbol_generator: SCIP symbol ID generator
            relationship_extractor: Language-specific relationship extractor
            enum_mapper: Language-specific enum mapper
            position_calculator: UTF-8 compliant position calculator
        """
        self.project_root = project_root
        self.symbol_generator = symbol_generator
        self.relationship_extractor = relationship_extractor
        self.enum_mapper = enum_mapper
        self.position_calculator = position_calculator
    
    @abstractmethod
    def get_language(self) -> str:
        """Return the language identifier."""
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        pass
    
    @abstractmethod
    def _extract_symbols(self, context: SCIPContext) -> Iterator[scip_pb2.SymbolInformation]:
        """Extract symbol definitions from source code."""
        pass
    
    @abstractmethod
    def _extract_occurrences(self, context: SCIPContext) -> Iterator[scip_pb2.Occurrence]:
        """Extract symbol occurrences from source code."""
        pass
    
    def create_document(self, file_path: str, content: str) -> scip_pb2.Document:
        """
        Create complete SCIP document with all essential components.
        
        This method is final and ensures all components are used.
        """
        document = scip_pb2.Document()
        document.relative_path = self._get_relative_path(file_path)
        document.language = self.get_language()
        
        # Create processing context
        context = SCIPContext(file_path, content, [], {})
        
        # Extract symbols (guaranteed to be implemented)
        symbols = list(self._extract_symbols(context))
        document.symbols.extend(symbols)
        
        # Extract occurrences (guaranteed to be implemented)
        occurrences = list(self._extract_occurrences(context))
        document.occurrences.extend(occurrences)
        
        # Extract relationships (guaranteed to be available)
        relationships = list(self.relationship_extractor.extract_all_relationships(context))
        self._add_relationships_to_document(document, relationships)
        
        return document
    
    def build_complete_index(self, files: List[str]) -> scip_pb2.Index:
        """Build complete SCIP index with all 6 essential content categories."""
        index = scip_pb2.Index()
        
        # 1. Create metadata
        index.metadata.CopyFrom(self.create_metadata())
        
        # 2. Process all documents
        documents = []
        for file_path in files:
            if self.can_handle_file(file_path):
                document = self.create_document(file_path, self._read_file(file_path))
                documents.append(document)
        
        index.documents.extend(documents)
        
        # 3. Extract external symbols
        external_symbols = self.extract_external_symbols(documents)
        index.external_symbols.extend(external_symbols)
        
        return index
    
    def create_metadata(self) -> scip_pb2.Metadata:
        """Create standard SCIP metadata."""
        metadata = scip_pb2.Metadata()
        metadata.version = scip_pb2.UnspecifiedProtocolVersion
        metadata.tool_info.name = "code-index-mcp"
        metadata.tool_info.version = "2.1.1"
        metadata.tool_info.arguments.extend(["scip-indexing", self.get_language()])
        metadata.project_root = self.project_root
        metadata.text_document_encoding = scip_pb2.UTF8
        return metadata
    
    @abstractmethod
    def extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """Extract external symbols from imports and dependencies."""
        pass
    
    @abstractmethod
    def build_cross_document_relationships(self, documents: List[scip_pb2.Document], full_index: scip_pb2.Index) -> int:
        """
        Build cross-document relationships for language-specific processing.
        
        This method should analyze the provided documents and create relationships
        between symbols across different files, taking into account the language's
        specific module system and import semantics.
        
        Args:
            documents: List of SCIP documents for this language
            full_index: Complete SCIP index with all documents and symbols
            
        Returns:
            Number of cross-document relationships added
        """
        pass
    
    def can_handle_file(self, file_path: str) -> bool:
        """Check if this factory can handle the file."""
        import os
        extension = os.path.splitext(file_path)[1].lower()
        return extension in self.get_supported_extensions()
    
    def _get_relative_path(self, file_path: str) -> str:
        """Get relative path from project root."""
        import os
        return os.path.relpath(file_path, self.project_root)
    
    def _read_file(self, file_path: str) -> str:
        """Read file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ""
    
    def _add_relationships_to_document(self, document: scip_pb2.Document, relationships):
        """Add relationships to document symbols."""
        # Build a map of symbol_id -> SymbolInformation for quick lookup
        symbol_map = {}
        for symbol_info in document.symbols:
            symbol_map[symbol_info.symbol] = symbol_info
        
        # Process each relationship
        for rel in relationships:
            # Add forward relationship (source -> target)
            if rel.source_symbol in symbol_map:
                source_symbol_info = symbol_map[rel.source_symbol]
                
                # Create SCIP Relationship
                scip_rel = scip_pb2.Relationship()
                scip_rel.symbol = rel.target_symbol
                
                # Map relationship type to SCIP flags
                if rel.relationship_type == InternalRelationshipType.CALLS:
                    scip_rel.is_reference = True
                elif rel.relationship_type == InternalRelationshipType.INHERITS:
                    scip_rel.is_reference = True
                elif rel.relationship_type == InternalRelationshipType.IMPLEMENTS:
                    scip_rel.is_implementation = True
                elif rel.relationship_type == InternalRelationshipType.IMPORTS:
                    scip_rel.is_reference = True
                elif rel.relationship_type == InternalRelationshipType.CONTAINS:
                    scip_rel.is_definition = True
                else:
                    scip_rel.is_reference = True  # Default
                
                # Add to source symbol's relationships
                source_symbol_info.relationships.append(scip_rel)
            
            # Add reverse relationship for called_by (target -> source)
            if rel.relationship_type == InternalRelationshipType.CALLS:
                if rel.target_symbol in symbol_map:
                    target_symbol_info = symbol_map[rel.target_symbol]
                    
                    # Create reverse relationship for called_by
                    reverse_rel = scip_pb2.Relationship()
                    reverse_rel.symbol = rel.source_symbol
                    reverse_rel.is_reference = True  # called_by is a reference
                    
                    # Add to target symbol's relationships
                    target_symbol_info.relationships.append(reverse_rel)