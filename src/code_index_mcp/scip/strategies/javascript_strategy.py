"""JavaScript/TypeScript SCIP indexing strategy - SCIP standard compliant."""

import logging
import os
from typing import List, Optional, Dict, Any, Set

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType

# Tree-sitter imports
import tree_sitter
from tree_sitter_javascript import language as js_language
from tree_sitter_typescript import language_typescript as ts_language


logger = logging.getLogger(__name__)


class JavaScriptStrategy(SCIPIndexerStrategy):
    """SCIP-compliant JavaScript/TypeScript indexing strategy using Tree-sitter."""

    SUPPORTED_EXTENSIONS = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}

    def __init__(self, priority: int = 95):
        """Initialize the JavaScript/TypeScript strategy."""
        super().__init__(priority)
        
        # Initialize parsers
        try:
            js_lang = tree_sitter.Language(js_language())
            ts_lang = tree_sitter.Language(ts_language())
            
            self.js_parser = tree_sitter.Parser(js_lang)
            self.ts_parser = tree_sitter.Parser(ts_lang)
            logger.info("JavaScript strategy initialized with Tree-sitter support")
        except Exception as e:
            logger.error(f"Failed to initialize JavaScript strategy: {e}")
            self.js_parser = None
            self.ts_parser = None
        
        # Initialize dependency tracking
        self.dependencies = {
            'imports': {
                'standard_library': [],
                'third_party': [],
                'local': []
            }
        }

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "javascript"

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return self.js_parser is not None and self.ts_parser is not None

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from JavaScript/TypeScript files."""
        logger.debug(f"JavaScriptStrategy Phase 1: Processing {len(files)} files for symbol collection")
        processed_count = 0
        error_count = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                self._collect_symbols_from_file(file_path, project_path)
                processed_count += 1
                
                if i % 10 == 0 or i == len(files):  # Progress every 10 files or at end
                    logger.debug(f"Phase 1 progress: {i}/{len(files)} files, last file: {relative_path}")
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"Phase 1 failed for {relative_path}: {e}")
                continue
        
        logger.info(f"Phase 1 summary: {processed_count} files processed, {error_count} errors")

    def _generate_documents_with_references(self, files: List[str], project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> List[scip_pb2.Document]:
        """Phase 2: Generate complete SCIP documents with resolved references."""
        documents = []
        logger.debug(f"JavaScriptStrategy Phase 2: Generating documents for {len(files)} files")
        processed_count = 0
        error_count = 0
        total_occurrences = 0
        total_symbols = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                document = self._analyze_javascript_file(file_path, project_path, relationships)
                if document:
                    documents.append(document)
                    total_occurrences += len(document.occurrences)
                    total_symbols += len(document.symbols)
                    processed_count += 1
                    
                if i % 10 == 0 or i == len(files):  # Progress every 10 files or at end
                    logger.debug(f"Phase 2 progress: {i}/{len(files)} files, "
                               f"last file: {relative_path}, "
                               f"{len(document.occurrences) if document else 0} occurrences")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Phase 2 failed for {relative_path}: {e}")
                continue
        
        logger.info(f"Phase 2 summary: {processed_count} documents generated, {error_count} errors, "
                   f"{total_occurrences} total occurrences, {total_symbols} total symbols")
        
        return documents

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """
        Build relationships between JavaScript/TypeScript symbols.
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        logger.debug(f"JavaScriptStrategy: Building symbol relationships for {len(files)} files")
        
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"JavaScriptStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single JavaScript/TypeScript file."""
        
        # Reset dependencies for this file
        self._reset_dependencies()
        
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {os.path.relpath(file_path, project_path)}")
            return

        # Parse with Tree-sitter
        try:
            tree = self._parse_js_content(content, file_path)
            if not tree or not tree.root_node:
                raise StrategyError(f"Failed to parse {os.path.relpath(file_path, project_path)}")
        except Exception as e:
            logger.warning(f"Parse error in {os.path.relpath(file_path, project_path)}: {e}")
            return

        # Collect symbols using integrated visitor
        relative_path = self._get_relative_path(file_path, project_path)
        self._collect_symbols_from_tree(tree, relative_path, content)
        logger.debug(f"Symbol collection - {relative_path}")

    def _analyze_javascript_file(self, file_path: str, project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> Optional[scip_pb2.Document]:
        """Analyze a single JavaScript/TypeScript file and generate complete SCIP document."""
        relative_path = self._get_relative_path(file_path, project_path)
        
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {relative_path}")
            return None

        # Parse with Tree-sitter
        try:
            tree = self._parse_js_content(content, file_path)
            if not tree or not tree.root_node:
                raise StrategyError(f"Failed to parse {relative_path}")
        except Exception as e:
            logger.warning(f"Parse error in {relative_path}: {e}")
            return None

        # Create SCIP document
        document = scip_pb2.Document()
        document.relative_path = relative_path
        document.language = self.get_language_name()

        # Analyze tree and generate occurrences
        self.position_calculator = PositionCalculator(content)
        
        occurrences, symbols = self._analyze_tree_for_document(tree, relative_path, content, relationships)
        
        # Add results to document
        document.occurrences.extend(occurrences)
        document.symbols.extend(symbols)
        
        logger.debug(f"Document analysis - {relative_path}: "
                    f"-> {len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _extract_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """
        Extract relationships from a single JavaScript/TypeScript file.
        
        Args:
            file_path: File to analyze
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        content = self._read_file_content(file_path)
        if not content:
            return {}
        
        try:
            tree = self._parse_js_content(content, file_path)
            if not tree or not tree.root_node:
                raise StrategyError(f"Failed to parse {file_path} for relationship extraction")
        except Exception as e:
            logger.warning(f"Parse error in {file_path}: {e}")
            return {}
        
        return self._extract_relationships_from_tree(tree, file_path, project_path)

    def _parse_js_content(self, content: str, file_path: str):
        """Parse JavaScript/TypeScript content using Tree-sitter parser."""
        # Determine parser based on file extension
        extension = os.path.splitext(file_path)[1].lower()
        
        if extension in {'.ts', '.tsx'}:
            parser = self.ts_parser
        else:
            parser = self.js_parser
        
        if not parser:
            raise StrategyError(f"No parser available for {extension}")
        
        content_bytes = content.encode('utf-8')
        return parser.parse(content_bytes)

    def _collect_symbols_from_tree(self, tree, file_path: str, content: str) -> None:
        """Collect symbols from Tree-sitter tree using integrated visitor."""
        # Use a set to track processed nodes and avoid duplicates
        self._processed_nodes = set()
        scope_stack = []
        
        def visit_node(node, current_scope_stack=None):
            if current_scope_stack is None:
                current_scope_stack = scope_stack[:]
            
            # Skip if already processed (by memory address)
            node_id = id(node)
            if node_id in self._processed_nodes:
                return
            self._processed_nodes.add(node_id)
            
            node_type = node.type
            
            # Traditional function and class declarations
            if node_type in ['function_declaration', 'method_definition', 'arrow_function']:
                name = self._get_js_function_name(node)
                if name:
                    self._register_function_symbol(node, name, file_path, current_scope_stack)
            elif node_type in ['class_declaration']:
                name = self._get_js_class_name(node)
                if name:
                    self._register_class_symbol(node, name, file_path, current_scope_stack)
            
            # Assignment expressions with function expressions (obj.method = function() {})
            elif node_type == 'assignment_expression':
                self._handle_assignment_expression(node, file_path, current_scope_stack)
            
            # Lexical declarations (const, let, var)
            elif node_type == 'lexical_declaration':
                self._handle_lexical_declaration(node, file_path, current_scope_stack)
            
            # Expression statements (might contain method chains)
            elif node_type == 'expression_statement':
                self._handle_expression_statement(node, file_path, current_scope_stack)
                    
            # Recursively visit children
            for child in node.children:
                visit_node(child, current_scope_stack)
        
        visit_node(tree.root_node)

    def _analyze_tree_for_document(self, tree, file_path: str, content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[List[scip_pb2.Occurrence], List[scip_pb2.SymbolInformation]]:
        """Analyze Tree-sitter tree to generate occurrences and symbols for SCIP document."""
        occurrences = []
        symbols = []
        scope_stack = []
        
        # Use the same processed nodes set to avoid duplicates
        if not hasattr(self, '_processed_nodes'):
            self._processed_nodes = set()
        
        def visit_node(node, current_scope_stack=None):
            if current_scope_stack is None:
                current_scope_stack = scope_stack[:]
            
            node_type = node.type
            
            # Traditional function and class declarations
            if node_type in ['function_declaration', 'method_definition', 'arrow_function']:
                name = self._get_js_function_name(node)
                if name:
                    symbol_id = self._create_function_symbol_id(name, file_path, current_scope_stack)
                    occurrence = self._create_function_occurrence(node, symbol_id)
                    symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                    scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                    symbol_info = self._create_function_symbol_info(node, symbol_id, name, scip_relationships)
                    
                    if occurrence:
                        occurrences.append(occurrence)
                    if symbol_info:
                        symbols.append(symbol_info)
                        
            elif node_type in ['class_declaration']:
                name = self._get_js_class_name(node)
                if name:
                    symbol_id = self._create_class_symbol_id(name, file_path, current_scope_stack)
                    occurrence = self._create_class_occurrence(node, symbol_id)
                    symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                    scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                    symbol_info = self._create_class_symbol_info(node, symbol_id, name, scip_relationships)
                    
                    if occurrence:
                        occurrences.append(occurrence)
                    if symbol_info:
                        symbols.append(symbol_info)
            
            # Assignment expressions with function expressions
            elif node_type == 'assignment_expression':
                occurrence, symbol_info = self._handle_assignment_for_document(node, file_path, current_scope_stack, relationships)
                if occurrence:
                    occurrences.append(occurrence)
                if symbol_info:
                    symbols.append(symbol_info)
            
            # Lexical declarations
            elif node_type == 'lexical_declaration':
                document_symbols = self._handle_lexical_for_document(node, file_path, current_scope_stack, relationships)
                for occ, sym in document_symbols:
                    if occ:
                        occurrences.append(occ)
                    if sym:
                        symbols.append(sym)
                        
            # Recursively visit children only if not in assignment or lexical that we handle above
            if node_type not in ['assignment_expression', 'lexical_declaration']:
                for child in node.children:
                    visit_node(child, current_scope_stack)
        
        visit_node(tree.root_node)
        return occurrences, symbols

    def _extract_relationships_from_tree(self, tree, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships from Tree-sitter tree."""
        relationships = {}
        scope_stack = []
        relative_path = self._get_relative_path(file_path, project_path)
        
        def visit_node(node, current_scope_stack=None):
            if current_scope_stack is None:
                current_scope_stack = scope_stack[:]
            
            node_type = node.type
            
            if node_type == 'class_declaration':
                # Extract inheritance relationships
                class_name = self._get_js_class_name(node)
                if class_name:
                    class_symbol_id = self._create_class_symbol_id(class_name, relative_path, current_scope_stack)
                    
                    # Look for extends clause
                    for child in node.children:
                        if child.type == 'class_heritage':
                            for heritage_child in child.children:
                                if heritage_child.type == 'identifier':
                                    parent_name = self._get_node_text(heritage_child)
                                    if parent_name:
                                        parent_symbol_id = self._create_class_symbol_id(parent_name, relative_path, current_scope_stack)
                                        if class_symbol_id not in relationships:
                                            relationships[class_symbol_id] = []
                                        relationships[class_symbol_id].append((parent_symbol_id, InternalRelationshipType.INHERITS))
                        
            elif node_type in ['function_declaration', 'method_definition', 'arrow_function']:
                # Extract function call relationships
                function_name = self._get_js_function_name(node)
                if function_name:
                    function_symbol_id = self._create_function_symbol_id(function_name, relative_path, current_scope_stack)
                    
                    # Find call expressions within this function
                    self._extract_calls_from_node(node, function_symbol_id, relationships, relative_path, current_scope_stack)
                        
            # Recursively visit children
            for child in node.children:
                visit_node(child, current_scope_stack)
        
        visit_node(tree.root_node)
        return relationships

    def _extract_calls_from_node(self, node, source_symbol_id: str, relationships: Dict, file_path: str, scope_stack: List):
        """Extract function calls from a node."""
        
        def visit_for_calls(n):
            if n.type == 'call_expression':
                # Get the function being called
                function_node = n.children[0] if n.children else None
                if function_node:
                    if function_node.type == 'identifier':
                        target_name = self._get_node_text(function_node)
                        if target_name:
                            target_symbol_id = self._create_function_symbol_id(target_name, file_path, scope_stack)
                            if source_symbol_id not in relationships:
                                relationships[source_symbol_id] = []
                            relationships[source_symbol_id].append((target_symbol_id, InternalRelationshipType.CALLS))
                            
            for child in n.children:
                visit_for_calls(child)
        
        visit_for_calls(node)

    # Helper methods for Tree-sitter node processing
    def _get_node_text(self, node) -> Optional[str]:
        """Get text content of a Tree-sitter node."""
        if hasattr(node, 'text'):
            try:
                return node.text.decode('utf-8')
            except:
                pass
        return None

    def _get_js_function_name(self, node) -> Optional[str]:
        """Extract function name from function node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._get_node_text(child)
        return None

    def _get_js_class_name(self, node) -> Optional[str]:
        """Extract class name from class node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._get_node_text(child)
        return None

    # Helper methods
    def _register_function_symbol(self, node, name: str, file_path: str, scope_stack: List[str]) -> None:
        """Register a function symbol definition."""
        symbol_id = self._create_function_symbol_id(name, file_path, scope_stack)
        
        # Create a dummy range for registration
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Function,
            display_name=name,
            documentation=["JavaScript function"]
        )

    def _register_class_symbol(self, node, name: str, file_path: str, scope_stack: List[str]) -> None:
        """Register a class symbol definition."""
        symbol_id = self._create_class_symbol_id(name, file_path, scope_stack)
        
        # Create a dummy range for registration
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Class,
            display_name=name,
            documentation=["JavaScript class"]
        )

    def _create_function_symbol_id(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for function."""
        # SCIP standard: local <local-id>
        local_id = ".".join(scope_stack + [name]) if scope_stack else name
        return f"local {local_id}()."

    def _create_class_symbol_id(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for class."""
        # SCIP standard: local <local-id>
        local_id = ".".join(scope_stack + [name]) if scope_stack else name
        return f"local {local_id}#"

    def _create_function_occurrence(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for function."""
        if not self.position_calculator:
            return None
            
        try:
            # Use Tree-sitter position calculation method
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierFunction
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_class_occurrence(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for class."""
        if not self.position_calculator:
            return None
            
        try:
            # Use Tree-sitter position calculation method
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierType
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_function_symbol_info(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for function."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        symbol_info.kind = scip_pb2.Function
        
        # Add documentation - check for JSDoc or comments
        symbol_info.documentation.append("JavaScript function")
        
        # Add relationships if provided
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_class_symbol_info(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for class."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        symbol_info.kind = scip_pb2.Class
        
        # Add documentation - check for JSDoc or comments
        symbol_info.documentation.append("JavaScript class")
        
        # Add relationships if provided
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    # JavaScript-specific syntax handlers
    def _handle_assignment_expression(self, node, file_path: str, scope_stack: List[str]) -> None:
        """Handle assignment expressions like obj.method = function() {}"""
        left_child = None
        right_child = None
        
        for child in node.children:
            if child.type == 'member_expression':
                left_child = child
            elif child.type in ['function_expression', 'arrow_function']:
                right_child = child
        
        if left_child and right_child:
            # Extract method name from member expression
            method_name = self._extract_member_expression_name(left_child)
            if method_name:
                # Use just the last part as function name for cleaner identification
                clean_name = method_name.split('.')[-1] if '.' in method_name else method_name
                # Register as function symbol
                self._register_function_symbol(right_child, clean_name, file_path, scope_stack + method_name.split('.')[:-1])
    
    def _handle_lexical_declaration(self, node, file_path: str, scope_stack: List[str]) -> None:
        """Handle lexical declarations like const VAR = value"""
        for child in node.children:
            if child.type == 'variable_declarator':
                # Get variable name and value
                var_name = None
                var_value = None
                
                for declarator_child in child.children:
                    if declarator_child.type == 'identifier':
                        var_name = self._get_node_text(declarator_child)
                    elif declarator_child.type in ['object_expression', 'new_expression', 'call_expression']:
                        var_value = declarator_child
                    elif declarator_child.type == 'object_pattern':
                        # Handle destructuring like const { v4: uuidv4 } = require('uuid')
                        self._handle_destructuring_pattern(declarator_child, file_path, scope_stack)
                
                if var_name:
                    # Check if this is an import/require statement
                    if var_value and var_value.type == 'call_expression':
                        # Check if it's a require() call
                        is_require = False
                        for cc in var_value.children:
                            if cc.type == 'identifier' and self._get_node_text(cc) == 'require':
                                is_require = True
                                break
                        
                        if is_require:
                            self._handle_import_statement(var_name, var_value, file_path, scope_stack)
                        else:
                            # Register as variable (like const limiter = rateLimit(...))
                            self._register_variable_symbol(child, var_name, file_path, scope_stack, var_value)
                        
                        # Extract functions from call_expression (like rateLimit config)
                        self._extract_functions_from_call_expression(var_value, var_name, file_path, scope_stack)
                    else:
                        # Register as constant/variable symbol
                        self._register_variable_symbol(child, var_name, file_path, scope_stack, var_value)
                        # Extract functions from object expressions
                        if var_value and var_value.type == 'object_expression':
                            self._extract_functions_from_object(var_value, var_name, file_path, scope_stack)
    
    def _handle_expression_statement(self, node, file_path: str, scope_stack: List[str]) -> None:
        """Handle expression statements that might contain method chains"""
        for child in node.children:
            if child.type == 'call_expression':
                # Look for method chain patterns like schema.virtual().get()
                self._handle_method_chain(child, file_path, scope_stack)
            elif child.type == 'assignment_expression':
                # Handle nested assignment expressions
                self._handle_assignment_expression(child, file_path, scope_stack)
    
    def _handle_method_chain(self, node, file_path: str, scope_stack: List[str]) -> None:
        """Handle method chains like schema.virtual('name').get(function() {})"""
        # Look for chained calls that end with function expressions
        for child in node.children:
            if child.type == 'member_expression':
                # This could be a chained method call
                member_name = self._extract_member_expression_name(child)
                if member_name:
                    # Look for function arguments
                    for sibling in node.children:
                        if sibling.type == 'arguments':
                            for arg in sibling.children:
                                if arg.type in ['function_expression', 'arrow_function']:
                                    # Register the function with a descriptive name
                                    func_name = f"{member_name}_callback"
                                    self._register_function_symbol(arg, func_name, file_path, scope_stack)
    
    def _extract_member_expression_name(self, node) -> Optional[str]:
        """Extract name from member expression like obj.prop.method"""
        parts = []
        
        def extract_parts(n):
            if n.type == 'member_expression':
                # Process children in order: object first, then property
                object_child = None
                property_child = None
                
                for child in n.children:
                    if child.type in ['identifier', 'member_expression']:
                        object_child = child
                    elif child.type == 'property_identifier':
                        property_child = child
                
                # Recursively extract object part first
                if object_child:
                    if object_child.type == 'member_expression':
                        extract_parts(object_child)
                    elif object_child.type == 'identifier':
                        parts.append(self._get_node_text(object_child))
                
                # Then add the property
                if property_child:
                    parts.append(self._get_node_text(property_child))
                    
            elif n.type == 'identifier':
                parts.append(self._get_node_text(n))
        
        extract_parts(node)
        return '.'.join(parts) if parts else None
    
    def _register_variable_symbol(self, node, name: str, file_path: str, scope_stack: List[str], value_node=None) -> None:
        """Register a variable/constant symbol definition."""
        symbol_id = self._create_variable_symbol_id(name, file_path, scope_stack, value_node)
        
        # Determine symbol type based on value
        symbol_kind = scip_pb2.Variable
        doc_type = "JavaScript variable"
        
        if value_node:
            if value_node.type == 'object_expression':
                symbol_kind = scip_pb2.Object
                doc_type = "JavaScript object"
            elif value_node.type == 'new_expression':
                symbol_kind = scip_pb2.Variable  # new expressions create variables, not classes
                doc_type = "JavaScript instance"
            elif value_node.type == 'call_expression':
                # Check if it's a require call vs regular function call
                is_require = False
                for child in value_node.children:
                    if child.type == 'identifier' and self._get_node_text(child) == 'require':
                        is_require = True
                        break
                if is_require:
                    symbol_kind = scip_pb2.Namespace
                    doc_type = "JavaScript import"
                else:
                    symbol_kind = scip_pb2.Variable
                    doc_type = "JavaScript constant"
        
        # Create a dummy range for registration
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=symbol_kind,
            display_name=name,
            documentation=[doc_type]
        )
    
    def _handle_destructuring_pattern(self, node, file_path: str, scope_stack: List[str]) -> None:
        """Handle destructuring patterns like { v4: uuidv4 }"""
        for child in node.children:
            if child.type == 'shorthand_property_identifier_pattern':
                # Simple destructuring like { prop }
                var_name = self._get_node_text(child)
                if var_name:
                    self._register_variable_symbol(child, var_name, file_path, scope_stack)
            elif child.type == 'pair_pattern':
                # Renamed destructuring like { v4: uuidv4 }
                for pair_child in child.children:
                    if pair_child.type == 'identifier':
                        var_name = self._get_node_text(pair_child)
                        if var_name:
                            self._register_variable_symbol(pair_child, var_name, file_path, scope_stack)
    
    def _handle_import_statement(self, var_name: str, call_node, file_path: str, scope_stack: List[str]) -> None:
        """Handle import statements like const lib = require('module')"""
        # Check if this is a require() call
        callee = None
        module_name = None
        
        for child in call_node.children:
            if child.type == 'identifier':
                callee = self._get_node_text(child)
            elif child.type == 'arguments':
                # Get the module name from arguments
                for arg in child.children:
                    if arg.type == 'string':
                        module_name = self._get_node_text(arg).strip('"\'')
                        break
        
        if callee == 'require' and module_name:
            # Classify dependency type
            self._classify_and_store_dependency(module_name)
            
            # Create SCIP standard symbol ID
            local_id = ".".join(scope_stack + [var_name]) if scope_stack else var_name
            symbol_id = f"local {local_id}(import)"
            
            dummy_range = scip_pb2.Range()
            dummy_range.start.extend([0, 0])
            dummy_range.end.extend([0, 1])
            
            self.reference_resolver.register_symbol_definition(
                symbol_id=symbol_id,
                file_path=file_path,
                definition_range=dummy_range,
                symbol_kind=scip_pb2.Namespace,
                display_name=var_name,
                documentation=[f"Import from {module_name}"]
            )
    
    def _handle_assignment_for_document(self, node, file_path: str, scope_stack: List[str], relationships: Optional[Dict[str, List[tuple]]]) -> tuple[Optional[scip_pb2.Occurrence], Optional[scip_pb2.SymbolInformation]]:
        """Handle assignment expressions for document generation"""
        left_child = None
        right_child = None
        
        for child in node.children:
            if child.type == 'member_expression':
                left_child = child
            elif child.type in ['function_expression', 'arrow_function']:
                right_child = child
        
        if left_child and right_child:
            method_name = self._extract_member_expression_name(left_child)
            if method_name:
                symbol_id = self._create_function_symbol_id(method_name, file_path, scope_stack)
                occurrence = self._create_function_occurrence(right_child, symbol_id)
                symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                symbol_info = self._create_function_symbol_info(right_child, symbol_id, method_name, scip_relationships)
                return occurrence, symbol_info
        
        return None, None
    
    def _handle_lexical_for_document(self, node, file_path: str, scope_stack: List[str], relationships: Optional[Dict[str, List[tuple]]]) -> List[tuple]:
        """Handle lexical declarations for document generation"""
        results = []
        
        for child in node.children:
            if child.type == 'variable_declarator':
                var_name = None
                var_value = None
                
                for declarator_child in child.children:
                    if declarator_child.type == 'identifier':
                        var_name = self._get_node_text(declarator_child)
                    elif declarator_child.type in ['object_expression', 'new_expression', 'call_expression']:
                        var_value = declarator_child
                
                if var_name:
                    # Create occurrence and symbol info for variable
                    symbol_id = self._create_variable_symbol_id(var_name, file_path, scope_stack, var_value)
                    occurrence = self._create_variable_occurrence(child, symbol_id)
                    symbol_info = self._create_variable_symbol_info(child, symbol_id, var_name, var_value)
                    results.append((occurrence, symbol_info))
        
        return results
    
    def _create_variable_symbol_id(self, name: str, file_path: str, scope_stack: List[str], value_node=None) -> str:
        """Create symbol ID for variable."""
        # SCIP standard: local <local-id>
        local_id = ".".join(scope_stack + [name]) if scope_stack else name
        
        # Determine descriptor based on value type
        descriptor = "."  # Default for variables
        if value_node:
            if value_node.type == 'object_expression':
                descriptor = "{}"
            elif value_node.type == 'new_expression':
                descriptor = "."  # new expressions are still variables, not classes
            elif value_node.type == 'call_expression':
                # Check if it's a require call vs regular function call
                is_require = False
                for child in value_node.children:
                    if child.type == 'identifier' and hasattr(self, '_get_node_text'):
                        if self._get_node_text(child) == 'require':
                            is_require = True
                            break
                descriptor = "(import)" if is_require else "."
        
        return f"local {local_id}{descriptor}"
    
    def _create_variable_occurrence(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for variable."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierConstant
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None
    
    def _create_variable_symbol_info(self, node, symbol_id: str, name: str, value_node=None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for variable."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        
        # Determine kind based on value - correct classification
        if value_node:
            if value_node.type == 'object_expression':
                symbol_info.kind = scip_pb2.Object
                symbol_info.documentation.append("JavaScript object literal")
            elif value_node.type == 'new_expression':
                symbol_info.kind = scip_pb2.Variable  # new expressions create variables, not classes
                symbol_info.documentation.append("JavaScript instance variable")
            elif value_node.type == 'call_expression':
                symbol_info.kind = scip_pb2.Namespace
                symbol_info.documentation.append("JavaScript import")
            elif value_node.type == 'function_expression':
                symbol_info.kind = scip_pb2.Function
                symbol_info.documentation.append("JavaScript function variable")
            else:
                symbol_info.kind = scip_pb2.Variable
                symbol_info.documentation.append("JavaScript variable")
        else:
            symbol_info.kind = scip_pb2.Variable
            symbol_info.documentation.append("JavaScript variable")
        
        return symbol_info
    
    def _extract_functions_from_object(self, object_node, parent_name: str, file_path: str, scope_stack: List[str]) -> None:
        """Extract functions from object expressions like { handler: function() {} }"""
        for child in object_node.children:
            if child.type == 'pair':
                prop_name = None
                prop_value = None
                
                for pair_child in child.children:
                    if pair_child.type in ['identifier', 'property_identifier']:
                        prop_name = self._get_node_text(pair_child)
                    elif pair_child.type in ['function_expression', 'arrow_function']:
                        prop_value = pair_child
                
                if prop_name and prop_value:
                    # Register function with context-aware name
                    func_scope = scope_stack + [parent_name]
                    self._register_function_symbol(prop_value, prop_name, file_path, func_scope)
    
    def _extract_functions_from_call_expression(self, call_node, parent_name: str, file_path: str, scope_stack: List[str]) -> None:
        """Extract functions from call expressions arguments like rateLimit({ handler: function() {} })"""
        for child in call_node.children:
            if child.type == 'arguments':
                for arg in child.children:
                    if arg.type == 'object_expression':
                        self._extract_functions_from_object(arg, parent_name, file_path, scope_stack)
                    elif arg.type in ['function_expression', 'arrow_function']:
                        # Anonymous function in call - give it a descriptive name
                        func_name = f"{parent_name}_callback"
                        self._register_function_symbol(arg, func_name, file_path, scope_stack)
    
    def _classify_and_store_dependency(self, module_name: str) -> None:
        """Classify and store dependency based on module name."""
        # Standard Node.js built-in modules
        node_builtins = {
            'fs', 'path', 'http', 'https', 'url', 'crypto', 'os', 'util', 'events', 
            'stream', 'buffer', 'child_process', 'cluster', 'dgram', 'dns', 'net', 
            'tls', 'zlib', 'readline', 'repl', 'vm', 'worker_threads', 'async_hooks'
        }
        
        if module_name in node_builtins:
            category = 'standard_library'
        elif module_name.startswith('./') or module_name.startswith('../') or module_name.startswith('/'):
            category = 'local'
        else:
            category = 'third_party'
        
        # Avoid duplicates
        if module_name not in self.dependencies['imports'][category]:
            self.dependencies['imports'][category].append(module_name)
    
    def get_dependencies(self) -> Dict[str, Any]:
        """Get collected dependencies for MCP response."""
        return self.dependencies
    
    def _reset_dependencies(self) -> None:
        """Reset dependency tracking for new file analysis."""
        self.dependencies = {
            'imports': {
                'standard_library': [],
                'third_party': [],
                'local': []
            }
        }