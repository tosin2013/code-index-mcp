"""Zig SCIP Index Factory implementation."""

import os
from pathlib import Path
from typing import Set, List, Iterator, Optional
from ..base.index_factory import SCIPIndexFactory
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..base.enum_mapper import BaseEnumMapper
from ..symbol_generator import SCIPSymbolGenerator
from ..position_calculator import SCIPPositionCalculator
from ..types import SCIPContext, SCIPSymbolDescriptor
from .relationship_extractor import ZigRelationshipExtractor
from .enum_mapper import ZigEnumMapper
from .tree_sitter_analyzer import ZigTreeSitterAnalyzer
from ...proto import scip_pb2

import tree_sitter
from tree_sitter_zig import language as zig_language


class ZigSCIPIndexFactory(SCIPIndexFactory):
    """Zig-specific SCIP Index factory implementation with constructor injection."""
    
    def __init__(self, 
                 project_root: str,
                 symbol_generator: SCIPSymbolGenerator,
                 relationship_extractor: BaseRelationshipExtractor,
                 enum_mapper: BaseEnumMapper,
                 position_calculator: SCIPPositionCalculator):
        """Initialize Zig factory with required components via constructor injection."""
        super().__init__(project_root, symbol_generator, relationship_extractor, 
                        enum_mapper, position_calculator)
        self.tree_analyzer = ZigTreeSitterAnalyzer()
    
    def get_language(self) -> str:
        """Return language identifier."""
        return "zig"
    
    def get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {'.zig', '.zon'}
    
    def _extract_symbols(self, context: SCIPContext) -> Iterator[scip_pb2.SymbolInformation]:
        """Extract Zig symbol definitions using tree-sitter analysis."""
        try:
            tree = self.tree_analyzer.parse(context.content, context.file_path)
            
            for node in self.tree_analyzer.walk(tree):
                if self.tree_analyzer.is_symbol_definition(node):
                    symbol_info = self._create_symbol_from_tree_node(node, context)
                    if symbol_info:
                        yield symbol_info
                        
        except SyntaxError as e:
            # Handle syntax errors gracefully
            pass
    
    def _extract_occurrences(self, context: SCIPContext) -> Iterator[scip_pb2.Occurrence]:
        """Extract Zig symbol occurrences."""
        try:
            tree = self.tree_analyzer.parse(context.content, context.file_path)
            
            for node in self.tree_analyzer.walk(tree):
                if (self.tree_analyzer.is_symbol_definition(node) or 
                    self.tree_analyzer.is_symbol_reference(node)):
                    occurrence = self._create_occurrence_from_tree_node(node, context)
                    if occurrence:
                        yield occurrence
                        
        except SyntaxError as e:
            # Handle syntax errors gracefully
            pass
    
    def extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """Extract Zig external symbols from imports."""
        external_symbols = []
        
        for doc in documents:
            try:
                content = self._read_file(os.path.join(self.project_root, doc.relative_path))
                tree = self.tree_analyzer.parse(content, doc.relative_path)
                
                # Extract import statements
                import_statements = self.tree_analyzer.extract_import_statements(tree)
                for import_path in import_statements:
                    external_symbol = self._create_external_symbol_from_import(import_path)
                    if external_symbol:
                        external_symbols.append(external_symbol)
                        
            except Exception as e:
                # Skip problematic files
                continue
        
        return external_symbols
    
    def build_cross_document_relationships(self, documents: List[scip_pb2.Document], full_index: scip_pb2.Index) -> int:
        """
        Build Zig-specific cross-document relationships.
        
        This implementation provides basic cross-document relationship support
        for Zig. A more sophisticated implementation would analyze @import statements
        and module dependencies.
        """
        # For now, use a simplified approach
        # TODO: Implement proper Zig import analysis
        return 0  # Placeholder - no relationships added yet
    
    def _create_symbol_from_tree_node(self, node, context: SCIPContext) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information from tree-sitter node."""
        symbol_info = scip_pb2.SymbolInformation()
        
        symbol_name = self.tree_analyzer.get_symbol_name(node)
        if not symbol_name:
            return None
        
        if node.type == 'function_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="function",
                scope_path=context.scope_stack,
                descriptor_suffix="()."
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('function')
            
        elif node.type == 'struct_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="struct",
                scope_path=context.scope_stack,
                descriptor_suffix="#"
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('struct')
            
        elif node.type == 'union_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="union",
                scope_path=context.scope_stack,
                descriptor_suffix="#"
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('union')
            
        elif node.type == 'enum_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="enum",
                scope_path=context.scope_stack,
                descriptor_suffix="#"
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('enum')
            
        elif node.type == 'variable_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="variable",
                scope_path=context.scope_stack,
                descriptor_suffix=""
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('variable')
            
        elif node.type == 'constant_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="constant",
                scope_path=context.scope_stack,
                descriptor_suffix=""
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('constant')
            
        elif node.type == 'type_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="type",
                scope_path=context.scope_stack,
                descriptor_suffix=""
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('type')
            
        elif node.type == 'container_field':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="field",
                scope_path=context.scope_stack,
                descriptor_suffix=""
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('field')
            
        elif node.type == 'parameter_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="parameter",
                scope_path=context.scope_stack,
                descriptor_suffix=""
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('parameter')
            
        elif node.type == 'test_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="test_declaration",
                scope_path=context.scope_stack,
                descriptor_suffix="()."
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('test_declaration')
            
        elif node.type == 'comptime_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="comptime_declaration",
                scope_path=context.scope_stack,
                descriptor_suffix="()."
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('comptime_declaration')
            
        elif node.type == 'error_set_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="error_set",
                scope_path=context.scope_stack,
                descriptor_suffix="#"
            )
            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = symbol_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('error_set')
            
        else:
            return None
            
        return symbol_info
    
    def _create_occurrence_from_tree_node(self, node, context: SCIPContext) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence from tree-sitter node."""
        occurrence = scip_pb2.Occurrence()
        
        # Calculate position using position calculator
        try:
            position_info = self.position_calculator.calculate_positions_from_tree_node(
                context.content, node
            )
            
            # Set range
            occurrence.range.start.extend([position_info.start_line, position_info.start_column])
            occurrence.range.end.extend([position_info.end_line, position_info.end_column])
            
        except Exception as e:
            # Skip if position calculation fails
            return None
        
        symbol_name = self.tree_analyzer.get_symbol_name(node)
        if not symbol_name:
            return None
        
        # Set symbol and roles based on node type
        if node.type == 'function_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="function",
                scope_path=context.scope_stack,
                descriptor_suffix="()."
            )
            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('function_declaration')
            
        elif node.type in ['struct_declaration', 'union_declaration', 'enum_declaration']:
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind=node.type.replace('_declaration', ''),
                scope_path=context.scope_stack,
                descriptor_suffix="#"
            )
            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind(f'{node.type}')
            
        elif node.type in ['variable_declaration', 'constant_declaration']:
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind=node.type.replace('_declaration', ''),
                scope_path=context.scope_stack,
                descriptor_suffix=""
            )
            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind(f'{node.type}')
            
        elif node.type == 'test_declaration':
            descriptor = SCIPSymbolDescriptor(
                name=symbol_name,
                kind="test_declaration",
                scope_path=context.scope_stack,
                descriptor_suffix="()."
            )
            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('test')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('test_declaration')
            
        elif node.type == 'identifier':
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
    
    def _create_external_symbol_from_import(self, import_path: str) -> Optional[scip_pb2.SymbolInformation]:
        """Create external symbol from import statement."""
        symbol_info = scip_pb2.SymbolInformation()
        
        # Determine if it's a standard library, C library, or external import
        if import_path.startswith('std'):
            symbol_info.symbol = f"zig-std {import_path}"
            symbol_info.display_name = import_path
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"Zig standard library: {import_path}")
        elif import_path.startswith('c'):
            symbol_info.symbol = f"c-lib {import_path}"
            symbol_info.display_name = import_path
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"C library: {import_path}")
        elif import_path.startswith('./') or import_path.startswith('../'):
            symbol_info.symbol = f"local {import_path}"
            symbol_info.display_name = import_path
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"Local module: {import_path}")
        else:
            symbol_info.symbol = f"zig-external {import_path}"
            symbol_info.display_name = import_path
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"External Zig module: {import_path}")
        
        return symbol_info


def create_zig_scip_factory(project_root: str) -> ZigSCIPIndexFactory:
    """
    Factory creator for Zig SCIP factory.
    Ensures all required components are properly assembled via constructor injection.
    """
    symbol_generator = SCIPSymbolGenerator(
        scheme="scip-zig",
        package_manager="zig",
        package_name=Path(project_root).name,
        version="HEAD"
    )
    
    relationship_extractor = ZigRelationshipExtractor()
    enum_mapper = ZigEnumMapper()
    position_calculator = SCIPPositionCalculator()
    
    return ZigSCIPIndexFactory(
        project_root=project_root,
        symbol_generator=symbol_generator,
        relationship_extractor=relationship_extractor,  # Guaranteed to be provided
        enum_mapper=enum_mapper,
        position_calculator=position_calculator
    )