"""Objective-C SCIP Index Factory implementation."""

import os
from pathlib import Path
from typing import Set, List, Iterator, Optional
from ..base.index_factory import SCIPIndexFactory
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..base.enum_mapper import BaseEnumMapper
from ..symbol_generator import SCIPSymbolGenerator
from ..position_calculator import SCIPPositionCalculator
from ..types import SCIPContext, SCIPSymbolDescriptor
from .relationship_extractor import ObjectiveCRelationshipExtractor
from .enum_mapper import ObjectiveCEnumMapper
from .clang_analyzer import ObjectiveCClangAnalyzer
from ...proto import scip_pb2

try:
    import clang.cindex as clang
    from clang.cindex import CursorKind
    LIBCLANG_AVAILABLE = True
except ImportError:
    LIBCLANG_AVAILABLE = False
    clang = None
    CursorKind = None


class ObjectiveCSCIPIndexFactory(SCIPIndexFactory):
    """Objective-C-specific SCIP Index factory implementation with constructor injection."""
    
    def __init__(self, 
                 project_root: str,
                 symbol_generator: SCIPSymbolGenerator,
                 relationship_extractor: BaseRelationshipExtractor,
                 enum_mapper: BaseEnumMapper,
                 position_calculator: SCIPPositionCalculator):
        """Initialize Objective-C factory with required components via constructor injection."""
        if not LIBCLANG_AVAILABLE:
            raise ImportError("libclang library not available")
        
        super().__init__(project_root, symbol_generator, relationship_extractor, 
                        enum_mapper, position_calculator)
        self.clang_analyzer = ObjectiveCClangAnalyzer()
    
    def get_language(self) -> str:
        """Return language identifier."""
        return "objective-c"
    
    def get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {'.m', '.mm', '.h'}
    
    def _extract_symbols(self, context: SCIPContext) -> Iterator[scip_pb2.SymbolInformation]:
        """Extract Objective-C symbol definitions using libclang analysis."""
        try:
            translation_unit = self.clang_analyzer.parse(context.content, context.file_path)
            
            for cursor in self.clang_analyzer.walk(translation_unit):
                if self.clang_analyzer.is_symbol_definition(cursor):
                    symbol_info = self._create_symbol_from_clang_cursor(cursor, context)
                    if symbol_info:
                        yield symbol_info
                        
        except SyntaxError as e:
            # Handle syntax errors gracefully
            pass
    
    def _extract_occurrences(self, context: SCIPContext) -> Iterator[scip_pb2.Occurrence]:
        """Extract Objective-C symbol occurrences."""
        try:
            translation_unit = self.clang_analyzer.parse(context.content, context.file_path)
            
            for cursor in self.clang_analyzer.walk(translation_unit):
                if (self.clang_analyzer.is_symbol_definition(cursor) or 
                    self.clang_analyzer.is_symbol_reference(cursor)):
                    occurrence = self._create_occurrence_from_clang_cursor(cursor, context)
                    if occurrence:
                        yield occurrence
                        
        except SyntaxError as e:
            # Handle syntax errors gracefully
            pass
    
    def extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """Extract Objective-C external symbols from imports."""
        external_symbols = []
        
        for doc in documents:
            try:
                content = self._read_file(os.path.join(self.project_root, doc.relative_path))
                translation_unit = self.clang_analyzer.parse(content, doc.relative_path)
                
                # Extract include statements
                include_statements = self.clang_analyzer.extract_include_statements(translation_unit)
                for include_path in include_statements:
                    external_symbol = self._create_external_symbol_from_include(include_path)
                    if external_symbol:
                        external_symbols.append(external_symbol)
                        
            except Exception as e:
                # Skip problematic files
                continue
        
        return external_symbols
    
    def build_cross_document_relationships(self, documents: List[scip_pb2.Document], full_index: scip_pb2.Index) -> int:
        """
        Build Objective-C-specific cross-document relationships.
        
        This implementation provides basic cross-document relationship support
        for Objective-C. A more sophisticated implementation would analyze
        #import/#include statements and framework dependencies.
        """
        # For now, use a simplified approach
        # TODO: Implement proper Objective-C import analysis
        return 0  # Placeholder - no relationships added yet
    
    def _create_symbol_from_clang_cursor(self, cursor, context: SCIPContext) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information from libclang cursor."""
        symbol_info = scip_pb2.SymbolInformation()
        
        symbol_name = self.clang_analyzer.get_symbol_name(cursor)
        if not symbol_name:
            return None
        
        if cursor.kind == CursorKind.OBJC_INTERFACE_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('interface')
            
        elif cursor.kind == CursorKind.OBJC_IMPLEMENTATION_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('class')
            
        elif cursor.kind == CursorKind.OBJC_PROTOCOL_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('protocol')
            
        elif cursor.kind in [CursorKind.OBJC_CATEGORY_DECL, CursorKind.OBJC_CATEGORY_IMPL_DECL]:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('category')
            
        elif cursor.kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('method')
            
        elif cursor.kind == CursorKind.OBJC_PROPERTY_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="variable",

                scope_path=context.scope_stack,

                descriptor_suffix=""

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('property')
            
        elif cursor.kind == CursorKind.OBJC_IVAR_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="variable",

                scope_path=context.scope_stack,

                descriptor_suffix=""

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('ivar')
            
        elif cursor.kind == CursorKind.FUNCTION_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('function')
            
        elif cursor.kind == CursorKind.VAR_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="variable",

                scope_path=context.scope_stack,

                descriptor_suffix=""

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('variable')
            
        elif cursor.kind == CursorKind.ENUM_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('enum')
            
        elif cursor.kind == CursorKind.STRUCT_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('struct')
            
        elif cursor.kind == CursorKind.TYPEDEF_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="variable",

                scope_path=context.scope_stack,

                descriptor_suffix=""

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('typedef')
            
        elif cursor.kind == CursorKind.MACRO_DEFINITION:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="variable",

                scope_path=context.scope_stack,

                descriptor_suffix=""

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('macro')
            
        else:
            return None
            
        return symbol_info
    
    def _create_occurrence_from_clang_cursor(self, cursor, context: SCIPContext) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence from libclang cursor."""
        occurrence = scip_pb2.Occurrence()
        
        # Calculate position using position calculator
        try:
            position_info = self.position_calculator.calculate_positions_from_clang_cursor(
                context.content, cursor
            )
            
            # Set range
            occurrence.range.start.extend([position_info.start_line, position_info.start_column])
            occurrence.range.end.extend([position_info.end_line, position_info.end_column])
            
        except Exception as e:
            # Skip if position calculation fails
            return None
        
        symbol_name = self.clang_analyzer.get_symbol_name(cursor)
        if not symbol_name:
            return None
        
        # Set symbol and roles based on cursor type
        if cursor.kind == CursorKind.OBJC_INTERFACE_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('interface_declaration')
            
        elif cursor.kind == CursorKind.OBJC_IMPLEMENTATION_DECL:
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('class_declaration')
            
        elif cursor.kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('method_declaration')
            
        elif cursor.kind in [CursorKind.DECL_REF_EXPR, CursorKind.MEMBER_REF_EXPR]:
            # Handle variable references
            descriptor = SCIPSymbolDescriptor(

                name=symbol_name,

                kind="variable",

                scope_path=context.scope_stack,

                descriptor_suffix=""

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('reference')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('identifier')
            
        else:
            return None
            
        return occurrence
    
    def _create_external_symbol_from_include(self, include_path: str) -> Optional[scip_pb2.SymbolInformation]:
        """Create external symbol from include statement."""
        symbol_info = scip_pb2.SymbolInformation()
        
        # Determine if it's a system header or local header
        if include_path.startswith('/System/') or include_path.startswith('/usr/'):
            # System framework or library
            symbol_info.symbol = f"objc-system {include_path}"
            symbol_info.display_name = include_path
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"System header: {include_path}")
        elif 'Frameworks' in include_path:
            # Framework
            symbol_info.symbol = f"objc-framework {include_path}"
            symbol_info.display_name = include_path
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"Framework header: {include_path}")
        else:
            # Local or external header
            symbol_info.symbol = f"objc-external {include_path}"
            symbol_info.display_name = include_path
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"External header: {include_path}")
        
        return symbol_info


def create_objective_c_scip_factory(project_root: str) -> ObjectiveCSCIPIndexFactory:
    """
    Factory creator for Objective-C SCIP factory.
    Ensures all required components are properly assembled via constructor injection.
    """
    if not LIBCLANG_AVAILABLE:
        raise ImportError("libclang library not available")
    
    symbol_generator = SCIPSymbolGenerator(
        scheme="scip-objc",
        package_manager="xcode",
        package_name=Path(project_root).name,
        version="HEAD"
    )
    
    relationship_extractor = ObjectiveCRelationshipExtractor()
    enum_mapper = ObjectiveCEnumMapper()
    position_calculator = SCIPPositionCalculator()
    
    return ObjectiveCSCIPIndexFactory(
        project_root=project_root,
        symbol_generator=symbol_generator,
        relationship_extractor=relationship_extractor,  # Guaranteed to be provided
        enum_mapper=enum_mapper,
        position_calculator=position_calculator
    )