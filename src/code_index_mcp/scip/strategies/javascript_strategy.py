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
