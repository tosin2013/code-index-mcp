"""JavaScript/TypeScript SCIP indexing strategy v2 - SCIP standard compliant."""

import logging
import os
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

try:
    import tree_sitter
    from tree_sitter_javascript import language as js_language
    from tree_sitter_typescript import language_typescript as ts_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType


logger = logging.getLogger(__name__)


class JavaScriptStrategy(SCIPIndexerStrategy):
    """SCIP-compliant JavaScript/TypeScript indexing strategy using Tree-sitter."""

    SUPPORTED_EXTENSIONS = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}

    def __init__(self, priority: int = 95):
        """Initialize the JavaScript/TypeScript strategy v2."""
        super().__init__(priority)
        
        if not TREE_SITTER_AVAILABLE:
            raise StrategyError("Tree-sitter not available for JavaScript/TypeScript strategy")
        
        # Initialize parsers
        js_lang = tree_sitter.Language(js_language())
        ts_lang = tree_sitter.Language(ts_language())
        
        self.js_parser = tree_sitter.Parser(js_lang)
        self.ts_parser = tree_sitter.Parser(ts_lang)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS and TREE_SITTER_AVAILABLE

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "javascript"  # Use 'javascript' for both JS and TS

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return TREE_SITTER_AVAILABLE

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from JavaScript/TypeScript files."""
        for file_path in files:
            try:
                self._collect_symbols_from_file(file_path, project_path)
            except Exception as e:
                logger.warning(f"Failed to collect symbols from {file_path}: {e}")
                continue

    def _generate_documents_with_references(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """Phase 2: Generate complete SCIP documents with resolved references."""
        documents = []
        
        for file_path in files:
            try:
                document = self._analyze_js_file(file_path, project_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"Failed to analyze JavaScript/TypeScript file {file_path}: {e}")
                continue
        
        return documents

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single JavaScript/TypeScript file."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return

        # Parse with Tree-sitter
        tree = self._parse_content(content, file_path)
        if not tree:
            return

        # Collect symbols
        relative_path = self._get_relative_path(file_path, project_path)
        collector = JavaScriptSymbolCollector(
            relative_path, content, tree, self.symbol_manager, self.reference_resolver
        )
        collector.analyze()

    def _analyze_js_file(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """Analyze a single JavaScript/TypeScript file and generate complete SCIP document."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return None

        # Parse with Tree-sitter
        tree = self._parse_content(content, file_path)
        if not tree:
            return None

        # Create SCIP document
        document = scip_pb2.Document()
        document.relative_path = self._get_relative_path(file_path, project_path)
        document.language = self._detect_specific_language(Path(file_path).suffix)

        # Analyze AST and generate occurrences
        self.position_calculator = PositionCalculator(content)
        analyzer = JavaScriptAnalyzer(
            document.relative_path,
            content,
            tree,
            document.language,
            self.symbol_manager,
            self.position_calculator,
            self.reference_resolver
        )
        analyzer.analyze()

        # Add results to document
        document.occurrences.extend(analyzer.occurrences)
        document.symbols.extend(analyzer.symbols)

        logger.debug(f"Analyzed JavaScript/TypeScript file {document.relative_path}: "
                    f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _parse_content(self, content: str, file_path: str) -> Optional[tree_sitter.Tree]:
        """Parse content with appropriate parser."""
        try:
            content_bytes = content.encode('utf-8')
            
            # Choose parser based on file extension
            extension = Path(file_path).suffix.lower()
            if extension in ['.ts', '.tsx']:
                return self.ts_parser.parse(content_bytes)
            else:
                return self.js_parser.parse(content_bytes)
                
        except Exception as e:
            logger.error(f"Failed to parse content: {e}")
            return None

    def _detect_specific_language(self, extension: str) -> str:
        """Detect specific language from extension."""
        ext_to_lang = {
            '.js': 'javascript',
            '.jsx': 'jsx',
            '.mjs': 'javascript',
            '.cjs': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'tsx'
        }
        return ext_to_lang.get(extension.lower(), 'javascript')


class JavaScriptSymbolCollector:
    """Tree-sitter based symbol collector for JavaScript/TypeScript (Phase 1)."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree, symbol_manager, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.symbol_manager = symbol_manager
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []

    def analyze(self):
        """Analyze the tree-sitter AST to collect symbols."""
        root = self.tree.root_node
        self._analyze_node(root)

    def _analyze_node(self, node: tree_sitter.Node):
        """Recursively analyze AST nodes."""
        node_type = node.type

        if node_type == 'function_declaration':
            self._register_function_symbol(node)
        elif node_type == 'method_definition':
            self._register_method_symbol(node)
        elif node_type == 'class_declaration':
            self._register_class_symbol(node)
        elif node_type == 'interface_declaration':
            self._register_interface_symbol(node)
        elif node_type == 'type_alias_declaration':
            self._register_type_alias_symbol(node)
        elif node_type == 'variable_declarator':
            self._register_variable_symbol(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)

    def _register_function_symbol(self, node: tree_sitter.Node):
        """Register a function symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="javascript",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="()."
                )
                
                self._register_symbol(symbol_id, name, scip_pb2.Function, ["JavaScript function"])

    def _register_method_symbol(self, node: tree_sitter.Node):
        """Register a method symbol definition."""
        name_node = (self._find_child_by_type(node, 'property_identifier') or 
                    self._find_child_by_type(node, 'identifier'))
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="javascript",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="()."
                )
                
                self._register_symbol(symbol_id, name, scip_pb2.Method, ["JavaScript method"])

    def _register_class_symbol(self, node: tree_sitter.Node):
        """Register a class symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="javascript",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="#"
                )
                
                self._register_symbol(symbol_id, name, scip_pb2.Class, ["JavaScript class"])

    def _register_interface_symbol(self, node: tree_sitter.Node):
        """Register a TypeScript interface symbol definition."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="javascript",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="#"
                )
                
                self._register_symbol(symbol_id, name, scip_pb2.Interface, ["TypeScript interface"])

    def _register_type_alias_symbol(self, node: tree_sitter.Node):
        """Register a TypeScript type alias symbol definition."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="javascript",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="#"
                )
                
                self._register_symbol(symbol_id, name, scip_pb2.TypeParameter, ["TypeScript type alias"])

    def _register_variable_symbol(self, node: tree_sitter.Node):
        """Register a variable symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="javascript",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor=""
                )
                
                self._register_symbol(symbol_id, name, scip_pb2.Variable, ["JavaScript variable"])

    def _register_symbol(self, symbol_id: str, name: str, symbol_kind: int, documentation: List[str]):
        """Register a symbol with the reference resolver."""
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=self.file_path,
            definition_range=dummy_range,
            symbol_kind=symbol_kind,
            display_name=name,
            documentation=documentation
        )

    def _find_child_by_type(self, node: tree_sitter.Node, node_type: str) -> Optional[tree_sitter.Node]:
        """Find first child node of the given type."""
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    def _get_node_text(self, node: tree_sitter.Node) -> str:
        """Get text content of a node."""
        return self.content[node.start_byte:node.end_byte]


class JavaScriptAnalyzer:
    """Tree-sitter based analyzer for JavaScript/TypeScript AST (Phase 2)."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree, language: str,
                 symbol_manager, position_calculator, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.language = language
        self.symbol_manager = symbol_manager
        self.position_calculator = position_calculator
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []
        
        # Results
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

    def analyze(self):
        """Analyze the tree-sitter AST."""
        root = self.tree.root_node
        self._analyze_node(root)

    def _analyze_node(self, node: tree_sitter.Node):
        """Recursively analyze AST nodes."""
        node_type = node.type

        if node_type == 'function_declaration':
            self._handle_function_declaration(node)
        elif node_type == 'method_definition':
            self._handle_method_definition(node)
        elif node_type == 'class_declaration':
            self._handle_class_declaration(node)
        elif node_type == 'interface_declaration':
            self._handle_interface_declaration(node)
        elif node_type == 'type_alias_declaration':
            self._handle_type_alias_declaration(node)
        elif node_type == 'variable_declarator':
            self._handle_variable_declarator(node)
        elif node_type == 'identifier':
            self._handle_identifier_reference(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)

    def _handle_function_declaration(self, node: tree_sitter.Node):
        """Handle function declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_function_symbol(node, name_node, name, False)

    def _handle_method_definition(self, node: tree_sitter.Node):
        """Handle method definitions."""
        name_node = (self._find_child_by_type(node, 'property_identifier') or 
                    self._find_child_by_type(node, 'identifier'))
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_function_symbol(node, name_node, name, True)

    def _handle_class_declaration(self, node: tree_sitter.Node):
        """Handle class declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_class_symbol(node, name_node, name, scip_pb2.Class, "JavaScript class")
                
                # Enter class scope
                self.scope_stack.append(name)
                
                # Analyze class body
                class_body = self._find_child_by_type(node, 'class_body')
                if class_body:
                    self._analyze_node(class_body)
                
                # Exit class scope
                self.scope_stack.pop()

    def _handle_interface_declaration(self, node: tree_sitter.Node):
        """Handle TypeScript interface declarations."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_class_symbol(node, name_node, name, scip_pb2.Interface, "TypeScript interface")

    def _handle_type_alias_declaration(self, node: tree_sitter.Node):
        """Handle TypeScript type alias declarations."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_class_symbol(node, name_node, name, scip_pb2.TypeParameter, "TypeScript type alias")

    def _handle_variable_declarator(self, node: tree_sitter.Node):
        """Handle variable declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_variable_symbol(node, name_node, name)

    def _handle_identifier_reference(self, node: tree_sitter.Node):
        """Handle identifier references."""
        # Only handle if it's not part of a declaration
        parent = node.parent
        if parent and parent.type not in [
            'function_declaration', 'class_declaration', 'variable_declarator',
            'method_definition', 'interface_declaration', 'type_alias_declaration'
        ]:
            name = self._get_node_text(node)
            if name and len(name) > 1:  # Avoid single letters
                self._handle_name_reference(node, name)

    def _create_function_symbol(self, node: tree_sitter.Node, name_node: tree_sitter.Node, name: str, is_method: bool):
        """Create a function or method symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="javascript",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor="()."
        )
        
        # Create definition occurrence
        range_obj = self.position_calculator.tree_sitter_node_to_range(name_node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierFunction
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        kind = scip_pb2.Method if is_method else scip_pb2.Function
        doc_type = "method" if is_method else "function"
        documentation = [f"JavaScript {doc_type} in {self.language}"]
        
        symbol_info = self._create_symbol_information(
            symbol_id, name, kind, documentation
        )
        self.symbols.append(symbol_info)

    def _create_class_symbol(self, node: tree_sitter.Node, name_node: tree_sitter.Node, 
                            name: str, symbol_kind: int, description: str):
        """Create a class, interface, or type symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="javascript",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor="#"
        )
        
        # Create definition occurrence
        range_obj = self.position_calculator.tree_sitter_node_to_range(name_node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierType
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, symbol_kind, [description]
        )
        self.symbols.append(symbol_info)

    def _create_variable_symbol(self, node: tree_sitter.Node, name_node: tree_sitter.Node, name: str):
        """Create a variable symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="javascript",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor=""
        )
        
        # Create definition occurrence
        range_obj = self.position_calculator.tree_sitter_node_to_range(name_node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierLocal
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Variable, [f"JavaScript variable in {self.language}"]
        )
        self.symbols.append(symbol_info)

    def _handle_name_reference(self, node: tree_sitter.Node, name: str):
        """Handle name reference."""
        # Try to resolve the reference
        resolved_symbol_id = self.reference_resolver.resolve_reference_by_name(
            symbol_name=name,
            context_file=self.file_path,
            context_scope=self.scope_stack
        )
        
        if resolved_symbol_id:
            # Create reference occurrence
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = self._create_occurrence(
                resolved_symbol_id, range_obj, 0, scip_pb2.Identifier  # 0 = reference role
            )
            self.occurrences.append(occurrence)
            
            # Register the reference
            self.reference_resolver.register_symbol_reference(
                symbol_id=resolved_symbol_id,
                file_path=self.file_path,
                reference_range=range_obj,
                context_scope=self.scope_stack
            )

    def _find_child_by_type(self, node: tree_sitter.Node, node_type: str) -> Optional[tree_sitter.Node]:
        """Find first child node of the given type."""
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    def _get_node_text(self, node: tree_sitter.Node) -> str:
        """Get text content of a node."""
        return self.content[node.start_byte:node.end_byte]

    def _create_occurrence(self, symbol_id: str, range_obj: scip_pb2.Range, 
                          symbol_roles: int, syntax_kind: int) -> scip_pb2.Occurrence:
        """Create a SCIP occurrence."""
        occurrence = scip_pb2.Occurrence()
        occurrence.symbol = symbol_id
        occurrence.symbol_roles = symbol_roles
        occurrence.syntax_kind = syntax_kind
        occurrence.range.CopyFrom(range_obj)
        return occurrence

    def _create_symbol_information(self, symbol_id: str, display_name: str, 
                                  symbol_kind: int, documentation: List[str] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = display_name
        symbol_info.kind = symbol_kind
        
        if documentation:
            symbol_info.documentation.extend(documentation)
        
        return symbol_info

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """
        Build relationships between JavaScript/TypeScript symbols.
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        logger.debug(f"🔗 JavaScriptStrategy: Building symbol relationships for {len(files)} files")
        
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_js_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"✅ JavaScriptStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships

    def _extract_js_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
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
        
        # Determine language based on file extension
        file_ext = Path(file_path).suffix.lower()
        is_typescript = file_ext in {'.ts', '.tsx'}
        
        if TREE_SITTER_AVAILABLE:
            return self._extract_tree_sitter_relationships(content, file_path, is_typescript)
        else:
            return self._extract_regex_relationships(content, file_path)

    def _extract_tree_sitter_relationships(self, content: str, file_path: str, is_typescript: bool) -> Dict[str, List[tuple]]:
        """Extract relationships using tree-sitter parser."""
        try:
            # Choose appropriate language
            language = ts_language() if is_typescript else js_language()
            parser = tree_sitter.Parser()
            parser.set_language(tree_sitter.Language(language))
            
            tree = parser.parse(bytes(content, "utf8"))
            
            extractor = JSRelationshipExtractor(
                file_path=file_path,
                content=content,
                symbol_manager=self.symbol_manager,
                is_typescript=is_typescript
            )
            
            extractor.extract_from_tree(tree.root_node)
            return extractor.get_relationships()
            
        except Exception as e:
            logger.warning(f"Tree-sitter relationship extraction failed for {file_path}: {e}")
            return self._extract_regex_relationships(content, file_path)

    def _extract_regex_relationships(self, content: str, file_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships using regex patterns (fallback)."""
        import re
        
        relationships = {}
        
        # Simple regex patterns for basic relationship extraction
        # This is a fallback when tree-sitter is not available
        
        # Class inheritance patterns
        class_extends_pattern = r'class\s+(\w+)\s+extends\s+(\w+)'
        for match in re.finditer(class_extends_pattern, content):
            child_class = match.group(1)
            parent_class = match.group(2)
            
            child_symbol_id = self._generate_symbol_id(file_path, [child_class], "#")
            parent_symbol_id = self._generate_symbol_id(file_path, [parent_class], "#")
            
            if child_symbol_id not in relationships:
                relationships[child_symbol_id] = []
            relationships[child_symbol_id].append((parent_symbol_id, InternalRelationshipType.INHERITS))
        
        # Function calls patterns (basic)
        function_call_pattern = r'(\w+)\s*\('
        current_function = None
        
        # Simple function definition detection
        function_def_pattern = r'function\s+(\w+)\s*\('
        for match in re.finditer(function_def_pattern, content):
            current_function = match.group(1)
            # Extract calls within this function context (simplified)
        
        logger.debug(f"Regex extraction found {len(relationships)} relationships in {file_path}")
        return relationships

    def _generate_symbol_id(self, file_path: str, symbol_path: List[str], descriptor: str) -> str:
        """Generate SCIP symbol ID for a JavaScript symbol."""
        if self.symbol_manager:
            return self.symbol_manager.create_local_symbol(
                language="javascript",
                file_path=file_path,
                symbol_path=symbol_path,
                descriptor=descriptor
            )
        return f"local {'/'.join(symbol_path)}{descriptor}"


class JSRelationshipExtractor:
    """
    Tree-sitter based relationship extractor for JavaScript/TypeScript.
    """
    
    def __init__(self, file_path: str, content: str, symbol_manager, is_typescript: bool = False):
        self.file_path = file_path
        self.content = content
        self.symbol_manager = symbol_manager
        self.is_typescript = is_typescript
        self.relationships = {}
        self.current_scope = []
        
    def get_relationships(self) -> Dict[str, List[tuple]]:
        """Get extracted relationships."""
        return self.relationships
    
    def _add_relationship(self, source_symbol_id: str, target_symbol_id: str, relationship_type: InternalRelationshipType):
        """Add a relationship to the collection."""
        if source_symbol_id not in self.relationships:
            self.relationships[source_symbol_id] = []
        self.relationships[source_symbol_id].append((target_symbol_id, relationship_type))
    
    def extract_from_tree(self, node):
        """Extract relationships from tree-sitter AST."""
        self._visit_node(node)
    
    def _visit_node(self, node):
        """Visit a tree-sitter node recursively."""
        if node.type == "class_declaration":
            self._handle_class_declaration(node)
        elif node.type == "function_declaration":
            self._handle_function_declaration(node)
        elif node.type == "method_definition":
            self._handle_method_definition(node)
        elif node.type == "call_expression":
            self._handle_call_expression(node)
        elif node.type == "import_statement":
            self._handle_import_statement(node)
        
        # Visit child nodes
        for child in node.children:
            self._visit_node(child)
    
    def _handle_class_declaration(self, node):
        """Handle class declaration and inheritance."""
        class_name = None
        parent_class = None
        
        for child in node.children:
            if child.type == "identifier" and class_name is None:
                class_name = self._get_node_text(child)
            elif child.type == "class_heritage":
                # Find extends clause
                for heritage_child in child.children:
                    if heritage_child.type == "extends_clause":
                        for extends_child in heritage_child.children:
                            if extends_child.type == "identifier":
                                parent_class = self._get_node_text(extends_child)
                                break
        
        if class_name and parent_class:
            class_symbol_id = self._generate_symbol_id([class_name], "#")
            parent_symbol_id = self._generate_symbol_id([parent_class], "#")
            self._add_relationship(class_symbol_id, parent_symbol_id, InternalRelationshipType.INHERITS)
    
    def _handle_function_declaration(self, node):
        """Handle function declaration."""
        function_name = None
        
        for child in node.children:
            if child.type == "identifier":
                function_name = self._get_node_text(child)
                break
        
        if function_name:
            self.current_scope.append(function_name)
            # Extract calls within function body
            self._extract_function_calls(node, function_name)
            self.current_scope.pop()
    
    def _handle_method_definition(self, node):
        """Handle method definition within a class."""
        method_name = None
        
        for child in node.children:
            if child.type == "property_identifier":
                method_name = self._get_node_text(child)
                break
        
        if method_name:
            full_scope = self.current_scope + [method_name]
            self._extract_function_calls(node, method_name)
    
    def _handle_call_expression(self, node):
        """Handle function/method calls."""
        if self.current_scope:
            current_function = self.current_scope[-1]
            
            # Extract called function name
            called_function = None
            
            for child in node.children:
                if child.type == "identifier":
                    called_function = self._get_node_text(child)
                    break
                elif child.type == "member_expression":
                    # Handle method calls like obj.method()
                    called_function = self._extract_member_expression(child)
                    break
            
            if called_function and current_function:
                source_symbol_id = self._generate_symbol_id([current_function], "().")
                target_symbol_id = self._generate_symbol_id([called_function], "().")
                self._add_relationship(source_symbol_id, target_symbol_id, InternalRelationshipType.CALLS)
    
    def _handle_import_statement(self, node):
        """Handle import statements."""
        # Extract import relationships
        imported_module = None
        imported_symbols = []
        
        for child in node.children:
            if child.type == "import_clause":
                # Extract imported symbols
                pass
            elif child.type == "string":
                # Extract module path
                imported_module = self._get_node_text(child).strip('"\'')
        
        # Add import relationships if needed
        # This could be expanded to track module dependencies
    
    def _extract_function_calls(self, function_node, function_name: str):
        """Extract all function calls within a function."""
        old_scope = self.current_scope.copy()
        if function_name not in self.current_scope:
            self.current_scope.append(function_name)
        
        self._visit_calls_in_node(function_node)
        
        self.current_scope = old_scope
    
    def _visit_calls_in_node(self, node):
        """Visit all call expressions in a node."""
        if node.type == "call_expression":
            self._handle_call_expression(node)
        
        for child in node.children:
            self._visit_calls_in_node(child)
    
    def _extract_member_expression(self, node) -> str:
        """Extract full name from member expression (e.g., 'obj.method')."""
        parts = []
        
        for child in node.children:
            if child.type == "identifier":
                parts.append(self._get_node_text(child))
            elif child.type == "property_identifier":
                parts.append(self._get_node_text(child))
        
        return ".".join(parts) if parts else ""
    
    def _get_node_text(self, node) -> str:
        """Get text content of a tree-sitter node."""
        return self.content[node.start_byte:node.end_byte]
    
    def _generate_symbol_id(self, symbol_path: List[str], descriptor: str) -> str:
        """Generate SCIP symbol ID."""
        if self.symbol_manager:
            return self.symbol_manager.create_local_symbol(
                language="javascript",
                file_path=self.file_path,
                symbol_path=symbol_path,
                descriptor=descriptor
            )
        return f"local {'/'.join(symbol_path)}{descriptor}"
