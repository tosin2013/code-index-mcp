"""JavaScript/TypeScript SCIP Index Factory implementation."""

import re
import os
from pathlib import Path
from typing import Set, List, Iterator, Optional, Dict, Any
from ..base.index_factory import SCIPIndexFactory
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..base.enum_mapper import BaseEnumMapper
from ..symbol_generator import SCIPSymbolGenerator
from ..position_calculator import SCIPPositionCalculator
from ..types import SCIPContext, SCIPSymbolDescriptor
from .relationship_extractor import JavaScriptRelationshipExtractor
from .enum_mapper import JavaScriptEnumMapper
from .syntax_analyzer import JavaScriptSyntaxAnalyzer
from ...proto import scip_pb2


class JavaScriptSCIPIndexFactory(SCIPIndexFactory):
    """JavaScript/TypeScript-specific SCIP Index factory implementation with constructor injection."""
    
    def __init__(self, 
                 project_root: str,
                 symbol_generator: SCIPSymbolGenerator,
                 relationship_extractor: BaseRelationshipExtractor,
                 enum_mapper: BaseEnumMapper,
                 position_calculator: SCIPPositionCalculator):
        """Initialize JavaScript factory with required components via constructor injection."""
        super().__init__(project_root, symbol_generator, relationship_extractor, 
                        enum_mapper, position_calculator)
        self.syntax_analyzer = JavaScriptSyntaxAnalyzer()
    
    def get_language(self) -> str:
        """Return language identifier."""
        return "javascript"
    
    def get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}
    
    def _extract_symbols(self, context: SCIPContext) -> Iterator[scip_pb2.SymbolInformation]:
        """Extract JavaScript symbol definitions using regex-based analysis."""
        try:
            patterns = self.syntax_analyzer.get_symbol_patterns()
            
            for pattern_type, pattern in patterns.items():
                for match in re.finditer(pattern, context.content, re.MULTILINE):
                    symbol_info = self._create_symbol_from_match(match, pattern_type, context)
                    if symbol_info:
                        yield symbol_info
                        
        except Exception as e:
            # Handle parsing errors gracefully
            pass
    
    def _extract_occurrences(self, context: SCIPContext) -> Iterator[scip_pb2.Occurrence]:
        """Extract JavaScript symbol occurrences."""
        try:
            patterns = self.syntax_analyzer.get_occurrence_patterns()
            
            for pattern_type, pattern in patterns.items():
                for match in re.finditer(pattern, context.content, re.MULTILINE):
                    occurrence = self._create_occurrence_from_match(match, pattern_type, context)
                    if occurrence:
                        yield occurrence
                        
        except Exception as e:
            # Handle parsing errors gracefully
            pass
    
    def extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """Extract JavaScript external symbols from imports."""
        external_symbols = []
        
        for doc in documents:
            try:
                content = self._read_file(os.path.join(self.project_root, doc.relative_path))
                import_patterns = self.syntax_analyzer.get_import_patterns()
                
                for pattern_type, pattern in import_patterns.items():
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        external_symbol = self._create_external_symbol_from_import_match(match, pattern_type)
                        if external_symbol:
                            external_symbols.append(external_symbol)
                            
            except Exception as e:
                # Skip problematic files
                continue
        
        return external_symbols
    
    def build_cross_document_relationships(self, documents: List[scip_pb2.Document], full_index: scip_pb2.Index) -> int:
        """
        Build JavaScript-specific cross-document relationships.
        
        This implementation provides basic cross-document relationship support
        for JavaScript/TypeScript. A more sophisticated implementation would
        analyze ES6 imports and require statements.
        """
        # For now, use a simplified approach
        # TODO: Implement proper JavaScript import/export analysis
        return 0  # Placeholder - no relationships added yet
    
    def _create_symbol_from_match(self, match: re.Match, pattern_type: str, context: SCIPContext) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information from regex match."""
        symbol_info = scip_pb2.SymbolInformation()
        
        if pattern_type == 'function':
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('function')
            
        elif pattern_type == 'arrow_function':
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('function')
            
        elif pattern_type == 'class':
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('class')
            
        elif pattern_type == 'const':
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="variable",

                scope_path=context.scope_stack,

                descriptor_suffix=""

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('constant')
            
        elif pattern_type == 'method':
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('method')
            
        elif pattern_type == 'object_method':
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('function')
            
        else:
            return None
            
        return symbol_info
    
    def _create_occurrence_from_match(self, match: re.Match, pattern_type: str, context: SCIPContext) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence from regex match."""
        occurrence = scip_pb2.Occurrence()
        
        # Calculate position using position calculator
        try:
            start_pos = match.start()
            end_pos = match.end()
            
            position_info = self.position_calculator.calculate_positions_from_offset(
                context.content, start_pos, end_pos
            )
            
            # Set range
            occurrence.range.start.extend([position_info.start_line, position_info.start_column])
            occurrence.range.end.extend([position_info.end_line, position_info.end_column])
            
        except Exception as e:
            # Skip if position calculation fails
            return None
        
        # Set symbol and roles based on pattern type
        if pattern_type in ['function', 'arrow_function', 'method', 'object_method']:
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('function_definition')
            
        elif pattern_type == 'class':
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('class_definition')
            
        elif pattern_type in ['const', 'let', 'var']:
            name = match.group(1)
            descriptor = SCIPSymbolDescriptor(

                name=name,

                kind="variable",

                scope_path=context.scope_stack,

                descriptor_suffix=""

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('variable_definition')
            
        elif pattern_type == 'identifier':
            name = match.group(0)
            descriptor = SCIPSymbolDescriptor(

                name=name,

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
    
    def _create_external_symbol_from_import_match(self, match: re.Match, pattern_type: str) -> Optional[scip_pb2.SymbolInformation]:
        """Create external symbol from import statement match."""
        symbol_info = scip_pb2.SymbolInformation()
        
        if pattern_type == 'es6_import':
            # import { name } from 'module'
            module_name = match.group(2) if match.lastindex >= 2 else match.group(1)
            symbol_info.symbol = f"npm {module_name}"
            symbol_info.display_name = module_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"ES6 imported module: {module_name}")
            return symbol_info
            
        elif pattern_type == 'require':
            # const name = require('module')
            module_name = match.group(2) if match.lastindex >= 2 else match.group(1)
            symbol_info.symbol = f"npm {module_name}"
            symbol_info.display_name = module_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"CommonJS required module: {module_name}")
            return symbol_info
            
        elif pattern_type == 'dynamic_import':
            # import('module')
            module_name = match.group(1)
            symbol_info.symbol = f"npm {module_name}"
            symbol_info.display_name = module_name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
            symbol_info.documentation.append(f"Dynamic imported module: {module_name}")
            return symbol_info
        
        return None


def create_javascript_scip_factory(project_root: str) -> JavaScriptSCIPIndexFactory:
    """
    Factory creator for JavaScript SCIP factory.
    Ensures all required components are properly assembled via constructor injection.
    """
    symbol_generator = SCIPSymbolGenerator(
        scheme="scip-javascript",
        package_manager="npm",
        package_name=Path(project_root).name,
        version="HEAD"
    )
    
    relationship_extractor = JavaScriptRelationshipExtractor()
    enum_mapper = JavaScriptEnumMapper()
    position_calculator = SCIPPositionCalculator()
    
    return JavaScriptSCIPIndexFactory(
        project_root=project_root,
        symbol_generator=symbol_generator,
        relationship_extractor=relationship_extractor,  # Guaranteed to be provided
        enum_mapper=enum_mapper,
        position_calculator=position_calculator
    )