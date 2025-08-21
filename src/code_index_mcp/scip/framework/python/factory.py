"""Python SCIP Index Factory implementation."""

import ast
import os
import logging
from pathlib import Path
from typing import Set, List, Iterator, Optional, Dict
from ..base.index_factory import SCIPIndexFactory
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..base.enum_mapper import BaseEnumMapper
from ..symbol_generator import SCIPSymbolGenerator
from ..position_calculator import SCIPPositionCalculator
from ..types import SCIPSymbolContext as SCIPContext, SCIPSymbolDescriptor
from .relationship_extractor import PythonRelationshipExtractor
from .enum_mapper import PythonEnumMapper
from .ast_analyzer import PythonASTAnalyzer
from ...proto import scip_pb2

logger = logging.getLogger(__name__)


class PythonSCIPIndexFactory(SCIPIndexFactory):
    """Python-specific SCIP Index factory implementation with constructor injection."""
    
    def __init__(self, 
                 project_root: str,
                 symbol_generator: SCIPSymbolGenerator,
                 relationship_extractor: BaseRelationshipExtractor,
                 enum_mapper: BaseEnumMapper,
                 position_calculator: SCIPPositionCalculator):
        """Initialize Python factory with required components via constructor injection."""
        super().__init__(project_root, symbol_generator, relationship_extractor, 
                        enum_mapper, position_calculator)
        self.ast_analyzer = PythonASTAnalyzer()
        self._parsed_trees = {}  # Cache parsed AST trees
        self._current_file_symbols = set()  # Track symbols defined in current file
    
    def get_language(self) -> str:
        """Return language identifier."""
        return "python"
    
    def get_supported_extensions(self) -> Set[str]:
        """Return supported file extensions."""
        return {'.py', '.pyw', '.pyx'}
    
    def _get_or_parse_tree(self, context: SCIPContext):
        """Get cached AST tree or parse if not cached."""
        cache_key = context.file_path
        if cache_key not in self._parsed_trees:
            try:
                self._parsed_trees[cache_key] = self.ast_analyzer.parse(context.content)
            except SyntaxError:
                self._parsed_trees[cache_key] = None
        return self._parsed_trees[cache_key]
    
    def _extract_symbols(self, context: SCIPContext) -> Iterator[scip_pb2.SymbolInformation]:
        """Extract Python symbol definitions using AST analysis."""
        tree = self._get_or_parse_tree(context)
        if tree is None:
            return
            
        # First pass: collect all defined symbols in this file
        self._current_file_symbols.clear()
        for node in self.ast_analyzer.walk(tree):
            if self.ast_analyzer.is_symbol_definition(node):
                symbol_name = self.ast_analyzer.get_symbol_name(node)
                if symbol_name:
                    self._current_file_symbols.add(symbol_name)
        
        # Clear processed nodes cache for fresh traversal
        self.ast_analyzer._processed_nodes.clear()
        
        for node in self.ast_analyzer.walk(tree):
            if self.ast_analyzer.is_symbol_definition(node):
                symbol_info = self._create_symbol_from_ast_node(node, context)
                if symbol_info:
                    yield symbol_info
    
    def _extract_occurrences(self, context: SCIPContext) -> Iterator[scip_pb2.Occurrence]:
        """Extract Python symbol occurrences."""
        tree = self._get_or_parse_tree(context)
        if tree is None:
            return
            
        # First pass: collect all defined symbols in this file
        self._current_file_symbols.clear()
        for node in self.ast_analyzer.walk(tree):
            if self.ast_analyzer.is_symbol_definition(node):
                symbol_name = self.ast_analyzer.get_symbol_name(node)
                if symbol_name:
                    self._current_file_symbols.add(symbol_name)
        
        # Need to clear processed nodes for occurrence extraction
        # Since symbols were already extracted, the cache needs reset
        self.ast_analyzer._processed_nodes.clear()
        
        for node in self.ast_analyzer.walk(tree):
            if self.ast_analyzer.is_symbol_definition(node) or self.ast_analyzer.is_symbol_reference(node):
                occurrence = self._create_occurrence_from_ast_node(node, context)
                if occurrence:
                    yield occurrence
    
    def extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """Extract Python external symbols from imports."""
        external_symbols = []
        
        for doc in documents:
            # Use cached AST tree if available - need full path for cache key
            full_path = os.path.join(self.project_root, doc.relative_path)
            cache_key = full_path
            tree = self._parsed_trees.get(cache_key)
            
            if tree is None:
                # Only parse if not already cached
                try:
                    content = self._read_file(full_path)
                    tree = self.ast_analyzer.parse(content)
                    self._parsed_trees[cache_key] = tree
                except (FileNotFoundError, SyntaxError):
                    continue
            
            if tree is not None:
                for node in self.ast_analyzer.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        external_symbol = self._create_external_symbol_from_import(node)
                        if external_symbol:
                            external_symbols.append(external_symbol)
                continue
        
        return external_symbols
    
    def clear_cache(self):
        """Clear AST parsing cache."""
        self._parsed_trees.clear()
    
    def _create_symbol_from_ast_node(self, node: ast.AST, context: SCIPContext) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information from AST node."""
        symbol_info = scip_pb2.SymbolInformation()
        
        if isinstance(node, ast.FunctionDef):
            descriptor = SCIPSymbolDescriptor(

                name=node.name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = node.name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('function')
            
            # Add docstring if available
            docstring = ast.get_docstring(node)
            if docstring:
                symbol_info.documentation.append(docstring)
                
        elif isinstance(node, ast.AsyncFunctionDef):
            descriptor = SCIPSymbolDescriptor(

                name=node.name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = node.name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('async_function')
            
            # Add docstring if available
            docstring = ast.get_docstring(node)
            if docstring:
                symbol_info.documentation.append(docstring)
                
        elif isinstance(node, ast.ClassDef):
            descriptor = SCIPSymbolDescriptor(

                name=node.name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            symbol_info.symbol = self.symbol_generator.create_local_symbol(descriptor)
            symbol_info.display_name = node.name
            symbol_info.kind = self.enum_mapper.map_symbol_kind('class')
            
            # Add docstring if available
            docstring = ast.get_docstring(node)
            if docstring:
                symbol_info.documentation.append(docstring)
                
        else:
            return None
            
        return symbol_info
    
    def _create_occurrence_from_ast_node(self, node: ast.AST, context: SCIPContext) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence from AST node."""
        occurrence = scip_pb2.Occurrence()
        
        # Calculate position using position calculator
        try:
            position_info = self.position_calculator.calculate_positions(
                context.content, node
            )
            
            # Set range
            occurrence.range.start.extend([position_info.start_line, position_info.start_column])
            occurrence.range.end.extend([position_info.end_line, position_info.end_column])
            
        except Exception as e:
            # Skip if position calculation fails
            return None
        
        # Set symbol and roles based on node type
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            descriptor = SCIPSymbolDescriptor(

                name=node.name,

                kind="function",

                scope_path=context.scope_stack,

                descriptor_suffix="()."

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('function_definition')
            
        elif isinstance(node, ast.ClassDef):
            descriptor = SCIPSymbolDescriptor(

                name=node.name,

                kind="class",

                scope_path=context.scope_stack,

                descriptor_suffix="#"

            )

            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('definition')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('class_definition')
            
        elif isinstance(node, ast.Name):
            # Handle variable references
            # Check if this is an internal or external symbol
            is_internal = node.id in self._current_file_symbols
            
            if is_internal:
                descriptor = SCIPSymbolDescriptor(
                    name=node.id,
                    kind="variable",
                    scope_path=context.scope_stack,
                    descriptor_suffix=""
                )
                occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            else:
                # External symbol - use appropriate namespace
                # Common Python builtins
                if node.id in {'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 
                               'None', 'True', 'False', 'print', 'len', 'range', 'open'}:
                    occurrence.symbol = f"python-builtin {node.id}"
                else:
                    # Assume it's from an import or global scope
                    occurrence.symbol = f"python {node.id}"
            
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('reference')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('identifier')
            
        elif isinstance(node, ast.Call):
            # Handle function calls
            func_name = self._extract_call_name(node.func)
            if func_name:
                # Check if this is an internal or external function
                is_internal = func_name in self._current_file_symbols
                
                if is_internal:
                    # Internal function/method
                    if isinstance(node.func, ast.Attribute):
                        # Method call - use method descriptor
                        descriptor = SCIPSymbolDescriptor(
                            name=func_name,
                            kind="method",
                            scope_path=context.scope_stack,
                            descriptor_suffix="()."
                        )
                    else:
                        # Function call
                        descriptor = SCIPSymbolDescriptor(
                            name=func_name,
                            kind="function",
                            scope_path=context.scope_stack,
                            descriptor_suffix="()."
                        )
                    occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
                else:
                    # External function
                    if func_name in {'print', 'len', 'range', 'open', 'input', 'int', 'str', 'float'}:
                        occurrence.symbol = f"python-builtin {func_name}()."
                    else:
                        occurrence.symbol = f"python {func_name}()."
                
                occurrence.symbol_roles = self.enum_mapper.map_symbol_role('reference')
                occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('function')
            else:
                return None
                
        elif isinstance(node, ast.Attribute):
            # Handle attribute access (including method references)
            attr_name = node.attr
            descriptor = SCIPSymbolDescriptor(
                name=attr_name,
                kind="variable",  # Could be method, property, or field
                scope_path=context.scope_stack,
                descriptor_suffix=""
            )
            
            occurrence.symbol = self.symbol_generator.create_local_symbol(descriptor)
            occurrence.symbol_roles = self.enum_mapper.map_symbol_role('reference')
            occurrence.syntax_kind = self.enum_mapper.map_syntax_kind('identifier')
            
        else:
            return None
            
        return occurrence
    
    def _create_external_symbol_from_import(self, node: ast.AST) -> Optional[scip_pb2.SymbolInformation]:
        """Create external symbol from import statement."""
        symbol_info = scip_pb2.SymbolInformation()
        
        if isinstance(node, ast.Import):
            for alias in node.names:
                symbol_info.symbol = f"python-stdlib {alias.name}"
                symbol_info.display_name = alias.name
                symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
                symbol_info.documentation.append(f"Imported module: {alias.name}")
                return symbol_info
                
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                symbol_info.symbol = f"python-stdlib {node.module}"
                symbol_info.display_name = node.module
                symbol_info.kind = self.enum_mapper.map_symbol_kind('module')
                symbol_info.documentation.append(f"Imported from module: {node.module}")
                return symbol_info
        
        return None
    
    def build_cross_document_relationships(self, documents: List[scip_pb2.Document], full_index: scip_pb2.Index) -> int:
        """
        Build Python-specific cross-document relationships.
        
        This implementation analyzes Python import statements and creates proper
        cross-document relationships using package-qualified symbol names.
        """
        logger.info(f"Building Python cross-document relationships for {len(documents)} files")
        
        # Step 1: Analyze Python imports across all documents
        import_mapping = self._analyze_python_imports(documents)
        
        # Step 2: Build Python-specific symbol registry
        symbol_registry = self._build_python_symbol_registry(documents, import_mapping)
        
        # Step 3: Process cross-document references
        relationships_added = self._create_python_cross_document_relationships(
            documents, symbol_registry, import_mapping
        )
        
        logger.info(f"Added {relationships_added} Python cross-document relationships")
        return relationships_added
    
    def _analyze_python_imports(self, documents: List[scip_pb2.Document]) -> Dict[str, Dict[str, str]]:
        """
        Analyze Python import statements across all documents.
        
        Returns:
            Dict mapping file_path -> {symbol_name -> full_module_path}
        """
        import_mapping = {}
        
        for doc in documents:
            file_imports = {}
            
            # Get full file path for AST parsing
            full_path = os.path.join(self.project_root, doc.relative_path)
            cache_key = full_path
            
            # Use cached AST tree if available
            tree = self._parsed_trees.get(cache_key)
            if tree is None:
                try:
                    content = self._read_file(full_path)
                    if content:
                        tree = self.ast_analyzer.parse(content)
                        self._parsed_trees[cache_key] = tree
                except (FileNotFoundError, SyntaxError):
                    continue
            
            if tree is not None:
                # Extract import information
                for node in self.ast_analyzer.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imported_name = alias.asname if alias.asname else alias.name.split('.')[-1]
                            file_imports[imported_name] = alias.name
                    
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            for alias in node.names:
                                imported_name = alias.asname if alias.asname else alias.name
                                full_name = f"{node.module}.{alias.name}"
                                file_imports[imported_name] = full_name
            
            import_mapping[doc.relative_path] = file_imports
        
        logger.debug(f"Analyzed imports for {len(import_mapping)} Python files")
        return import_mapping
    
    def _build_python_symbol_registry(self, documents: List[scip_pb2.Document], 
                                    import_mapping: Dict[str, Dict[str, str]]) -> Dict[str, tuple]:
        """
        Build symbol registry with proper Python package-qualified names.
        
        Returns:
            Dict mapping full_symbol_id -> (document, symbol_info)
        """
        symbol_registry = {}
        
        for doc in documents:
            module_path = self._file_path_to_module_path(doc.relative_path)
            
            for symbol_info in doc.symbols:
                local_symbol = symbol_info.symbol
                
                # Convert local symbol to package-qualified symbol
                if local_symbol.startswith('local '):
                    symbol_name = local_symbol[6:]  # Remove 'local ' prefix
                    
                    # Create package-qualified symbol
                    package_symbol = f"python pypi {Path(self.project_root).name} HEAD {module_path}.{symbol_name}"
                    symbol_registry[package_symbol] = (doc, symbol_info)
                    
                    # Also register the local version for backward compatibility
                    symbol_registry[local_symbol] = (doc, symbol_info)
        
        logger.debug(f"Built Python symbol registry with {len(symbol_registry)} entries")
        return symbol_registry
    
    def _create_python_cross_document_relationships(self, documents: List[scip_pb2.Document],
                                                  symbol_registry: Dict[str, tuple],
                                                  import_mapping: Dict[str, Dict[str, str]]) -> int:
        """
        Create cross-document relationships based on Python import analysis.
        """
        relationships_added = 0
        
        for source_doc in documents:
            file_imports = import_mapping.get(source_doc.relative_path, {})
            
            for occurrence in source_doc.occurrences:
                # Skip if not a reference
                if not (occurrence.symbol_roles & 8):  # ReadAccess
                    continue
                
                # Skip if it's also a definition
                if occurrence.symbol_roles & 1:  # Definition
                    continue
                
                # Check if this is a cross-file reference based on imports
                symbol_name = self._extract_symbol_name_from_occurrence(occurrence)
                if symbol_name in file_imports:
                    # This is a reference to an imported symbol
                    target_module = file_imports[symbol_name]
                    target_symbol_id = f"python pypi {Path(self.project_root).name} HEAD {target_module}"
                    
                    target_entry = symbol_registry.get(target_symbol_id)
                    if target_entry:
                        target_doc, target_symbol_info = target_entry
                        
                        # Find the containing symbol in source document
                        source_symbol_id = self._find_containing_symbol_in_python(occurrence, source_doc)
                        
                        if source_symbol_id and source_symbol_id != target_symbol_id:
                            # Create relationship
                            relationship = scip_pb2.Relationship()
                            relationship.symbol = source_symbol_id
                            relationship.is_reference = True
                            
                            # Check for duplicates
                            if not any(rel.symbol == source_symbol_id for rel in target_symbol_info.relationships):
                                target_symbol_info.relationships.append(relationship)
                                relationships_added += 1
        
        return relationships_added
    
    def _extract_call_name(self, func_node: ast.AST) -> Optional[str]:
        """Extract the function name from a Call node's func attribute."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            return func_node.attr
        return None
    
    def _file_path_to_module_path(self, file_path: str) -> str:
        """Convert file path to Python module path."""
        # Remove .py extension and convert path separators to dots
        module_path = file_path.replace('\\', '/').replace('.py', '').replace('/', '.')
        
        # Remove common prefixes
        if module_path.startswith('src.'):
            module_path = module_path[4:]
        
        return module_path
    
    def _extract_symbol_name_from_occurrence(self, occurrence: scip_pb2.Occurrence) -> str:
        """Extract simple symbol name from SCIP occurrence."""
        symbol = occurrence.symbol
        if symbol.startswith('local '):
            return symbol[6:].split('.')[0]  # Get first part after 'local '
        return symbol.split('.')[-1]  # Get last part of qualified name
    
    def _find_containing_symbol_in_python(self, occurrence: scip_pb2.Occurrence, 
                                        document: scip_pb2.Document) -> Optional[str]:
        """Find which Python symbol contains this occurrence."""
        if not occurrence.range or not occurrence.range.start:
            return None
        
        occurrence_line = occurrence.range.start[0] if len(occurrence.range.start) > 0 else 0
        
        # Find the most specific containing symbol
        containing_symbol = None
        for symbol_info in document.symbols:
            # Simple heuristic: assume we're in the first function/class found
            if symbol_info.kind in [11, 3]:  # Function or Class
                containing_symbol = symbol_info.symbol
                break
        
        return containing_symbol


def create_python_scip_factory(project_root: str) -> PythonSCIPIndexFactory:
    """
    Factory creator for Python SCIP factory.
    Ensures all required components are properly assembled via constructor injection.
    """
    symbol_generator = SCIPSymbolGenerator(
        scheme="scip-python",
        package_manager="local",
        package_name=Path(project_root).name,
        version="HEAD"
    )
    
    relationship_extractor = PythonRelationshipExtractor()
    enum_mapper = PythonEnumMapper()
    position_calculator = SCIPPositionCalculator()
    
    return PythonSCIPIndexFactory(
        project_root=project_root,
        symbol_generator=symbol_generator,
        relationship_extractor=relationship_extractor,  # Guaranteed to be provided
        enum_mapper=enum_mapper,
        position_calculator=position_calculator
    )