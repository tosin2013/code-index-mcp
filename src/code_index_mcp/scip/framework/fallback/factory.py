"""Fallback SCIP Index Factory implementation."""

import os
from pathlib import Path
from typing import Set, List, Iterator, Optional
from ..base.index_factory import SCIPIndexFactory
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..base.enum_mapper import BaseEnumMapper
from ..symbol_generator import SCIPSymbolGenerator
from ..position_calculator import SCIPPositionCalculator
from ..types import SCIPContext
from .relationship_extractor import FallbackRelationshipExtractor
from .enum_mapper import FallbackEnumMapper
from .basic_analyzer import FallbackBasicAnalyzer
from ...proto import scip_pb2
from ....constants import SUPPORTED_EXTENSIONS


class FallbackSCIPIndexFactory(SCIPIndexFactory):
    """Fallback SCIP Index factory for unsupported languages and files."""
    
    def __init__(self, 
                 project_root: str,
                 symbol_generator: SCIPSymbolGenerator,
                 relationship_extractor: BaseRelationshipExtractor,
                 enum_mapper: BaseEnumMapper,
                 position_calculator: SCIPPositionCalculator):
        """Initialize Fallback factory with required components via constructor injection."""
        super().__init__(project_root, symbol_generator, relationship_extractor, 
                        enum_mapper, position_calculator)
        self.basic_analyzer = FallbackBasicAnalyzer()
    
    def get_language(self) -> str:
        """Return language identifier."""
        return "text"
    
    def get_supported_extensions(self) -> Set[str]:
        """Return all supported file extensions as fallback handles everything."""
        return SUPPORTED_EXTENSIONS
    
    def _extract_symbols(self, context: SCIPContext) -> Iterator[scip_pb2.SymbolInformation]:
        """Extract minimal symbol information (file-level only)."""
        try:
            # Only create a file-level symbol for fallback
            file_name = Path(context.file_path).stem
            if file_name:
                symbol_info = self._create_file_symbol(context, file_name)
                if symbol_info:
                    yield symbol_info
                    
        except Exception as e:
            # Silently handle errors in fallback
            pass
    
    def _extract_occurrences(self, context: SCIPContext) -> Iterator[scip_pb2.Occurrence]:
        """Extract minimal occurrences (file-level only)."""
        try:
            # Create single occurrence for the entire file
            file_name = Path(context.file_path).stem
            if file_name:
                occurrence = self._create_file_occurrence(context, file_name)
                if occurrence:
                    yield occurrence
                    
        except Exception as e:
            # Silently handle errors in fallback
            pass
    
    def extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """Extract external symbols (none for fallback)."""
        return []  # Fallback doesn't analyze external dependencies
    
    def build_cross_document_relationships(self, documents: List[scip_pb2.Document], full_index: scip_pb2.Index) -> int:
        """
        Build cross-document relationships for fallback (no relationships).
        
        Fallback factory doesn't create cross-document relationships as it handles
        unsupported languages with minimal symbol information.
        """
        return 0  # No cross-document relationships for fallback
    
    def _create_file_symbol(self, context: SCIPContext, file_name: str) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information for the file itself."""
        symbol_info = scip_pb2.SymbolInformation()
        
        # Detect language from file extension
        language = self.basic_analyzer.detect_language_from_extension(
            Path(context.file_path).suffix
        )
        
        symbol_info.symbol = self.symbol_generator.create_local_symbol(
            language=language,
            file_path=context.file_path,
            symbol_path=[file_name],
            descriptor=""
        )
        symbol_info.display_name = file_name
        symbol_info.kind = self.enum_mapper.map_symbol_kind('file')
        symbol_info.documentation.append(
            f"File: {context.file_path} ({language})"
        )
        
        return symbol_info
    
    def _create_file_occurrence(self, context: SCIPContext, file_name: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for the file itself."""
        occurrence = scip_pb2.Occurrence()
        
        # Set range to cover entire file (0,0) to (lines, 0)
        lines = context.content.count('\n')
        occurrence.range.start.extend([0, 0])
        occurrence.range.end.extend([lines, 0])
        
        # Detect language from file extension
        language = self.basic_analyzer.detect_language_from_extension(
            Path(context.file_path).suffix
        )
        
        occurrence.symbol = self.symbol_generator.create_local_symbol(
            language=language,
            file_path=context.file_path,
            symbol_path=[file_name],
            descriptor=""
        )
        occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
        occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('file')
        
        return occurrence


def create_fallback_scip_factory(project_root: str) -> FallbackSCIPIndexFactory:
    """
    Factory creator for Fallback SCIP factory.
    Ensures all required components are properly assembled via constructor injection.
    """
    symbol_generator = SCIPSymbolGenerator(
        scheme="scip-fallback",
        package_manager="generic",
        package_name=Path(project_root).name,
        version="HEAD"
    )
    
    relationship_extractor = FallbackRelationshipExtractor()
    enum_mapper = FallbackEnumMapper()
    position_calculator = SCIPPositionCalculator()
    
    return FallbackSCIPIndexFactory(
        project_root=project_root,
        symbol_generator=symbol_generator,
        relationship_extractor=relationship_extractor,  # Guaranteed to be provided
        enum_mapper=enum_mapper,
        position_calculator=position_calculator
    )