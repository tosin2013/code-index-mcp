# pylint: disable=no-member
"""Tree-sitter based JavaScript/TypeScript SCIP indexing strategy."""

import logging
import os
from typing import List, Set, Dict, Any, Optional
from pathlib import Path

import tree_sitter
from tree_sitter_javascript import language as js_language
from tree_sitter_typescript import language_typescript as ts_language

from .base_strategy import SCIPIndexerStrategy, ConversionError
from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class JavaScriptStrategy(SCIPIndexerStrategy):
    """Tree-sitter based strategy for JavaScript/TypeScript files."""

    SUPPORTED_EXTENSIONS = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}

    def __init__(self, priority: int = 90):
        """Initialize with tree-sitter parsers."""
        super().__init__(priority)


        # Initialize parsers
        js_lang = tree_sitter.Language(js_language())
        ts_lang = tree_sitter.Language(ts_language())

        self.js_parser = tree_sitter.Parser(js_lang)
        self.ts_parser = tree_sitter.Parser(ts_lang)

        logger.info("JavaScriptStrategy initialized with tree-sitter")

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the given file extension."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def generate_scip_documents(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """
        Generate SCIP documents using tree-sitter AST parsing.

        Args:
            files: List of JavaScript/TypeScript file paths to index
            project_path: Root path of the project

        Returns:
            List of SCIP Document objects
        """

        documents = []

        for file_path in files:
            try:
                document = self._create_scip_document(file_path, project_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"Failed to create SCIP document for {file_path}: {str(e)}")
                # Continue with other files

        logger.info(f"JavaScriptStrategy created {len(documents)} SCIP documents")
        return documents

    def _create_scip_document(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """
        Create a SCIP document for a JavaScript/TypeScript file using tree-sitter.

        Args:
            file_path: Path to the JavaScript/TypeScript file
            project_path: Root path of the project

        Returns:
            SCIP Document object or None if failed
        """
        try:
            # Resolve full file path
            if not os.path.isabs(file_path):
                full_path = os.path.join(project_path, file_path)
            else:
                full_path = file_path

            # Read file content
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Create SCIP document
            document = scip_pb2.Document()
            document.relative_path = self._get_relative_path(file_path, project_path)
            document.language = self._detect_language(Path(file_path).suffix)

            # Parse with appropriate parser
            tree = self._parse_content(content, document.language)
            if not tree:
                return None

            # Analyze the AST
            analyzer = JSTreeSitterAnalyzer(document.relative_path, content, tree, document.language)
            analyzer.analyze()

            # Add results to document
            document.occurrences.extend(analyzer.occurrences)
            document.symbols.extend(analyzer.symbols)

            logger.debug(f"Created SCIP document for {document.relative_path}: "
                        f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

            return document

        except Exception as e:
            logger.error(f"Failed to create SCIP document for {file_path}: {str(e)}")
            return None

    def _parse_content(self, content: str, language: str) -> Optional[tree_sitter.Tree]:
        """Parse content with appropriate parser."""
        try:
            content_bytes = content.encode('utf-8')

            if language in ['typescript', 'tsx']:
                return self.ts_parser.parse(content_bytes)
            else:
                return self.js_parser.parse(content_bytes)
        except Exception as e:
            logger.error(f"Failed to parse content: {str(e)}")
            return None

    def _detect_language(self, extension: str) -> str:
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

    def _get_relative_path(self, file_path: str, project_path: str) -> str:
        """Get relative path from project root."""
        try:
            path = Path(file_path)
            if path.is_absolute():
                return str(path.relative_to(Path(project_path)))
            return file_path
        except ValueError:
            return file_path

    def get_strategy_name(self) -> str:
        """Return a human-readable name for this strategy."""
        return "JavaScript/TypeScript(TreeSitter)"


class JSTreeSitterAnalyzer:
    """Tree-sitter based analyzer for JavaScript/TypeScript AST."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree, language: str):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.language = language
        self.lines = content.split('\n')
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

        # Track scope for qualified names
        self.scope_stack: List[str] = []

    def analyze(self):
        """Analyze the tree-sitter AST."""
        root = self.tree.root_node
        self._analyze_node(root)

        logger.debug(f"Analyzed {self.file_path}: "
                    f"{len(self.occurrences)} occurrences, {len(self.symbols)} symbols")

    def _analyze_node(self, node: tree_sitter.Node):
        """Recursively analyze AST nodes."""
        # Handle different node types
        node_type = node.type

        if node_type == 'function_declaration':
            self._handle_function_declaration(node)
        elif node_type == 'method_definition':
            self._handle_method_definition(node)
        elif node_type == 'arrow_function':
            self._handle_arrow_function(node)
        elif node_type == 'class_declaration':
            self._handle_class_declaration(node)
        elif node_type == 'interface_declaration':
            self._handle_interface_declaration(node)
        elif node_type == 'type_alias_declaration':
            self._handle_type_alias(node)
        elif node_type == 'variable_declarator':
            self._handle_variable_declarator(node)
        elif node_type == 'import_statement' or node_type == 'import_declaration':
            self._handle_import(node)
        elif node_type == 'export_statement' or node_type == 'export_declaration':
            self._handle_export(node)
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
                self._add_function_symbol(name_node, name, is_method=False)

    def _handle_method_definition(self, node: tree_sitter.Node):
        """Handle class method definitions."""
        # Find the method name (property_identifier or identifier)
        name_node = self._find_child_by_type(node, 'property_identifier') or self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_function_symbol(name_node, name, is_method=True)

    def _handle_arrow_function(self, node: tree_sitter.Node):
        """Handle arrow functions assigned to variables."""
        # Arrow functions are often handled as part of variable_declarator

    def _handle_class_declaration(self, node: tree_sitter.Node):
        """Handle class declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_class_symbol(name_node, name)

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
        if self.language not in ['typescript', 'tsx']:
            return

        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_interface_symbol(name_node, name)

    def _handle_type_alias(self, node: tree_sitter.Node):
        """Handle TypeScript type aliases."""
        if self.language not in ['typescript', 'tsx']:
            return

        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_type_symbol(name_node, name)

    def _handle_variable_declarator(self, node: tree_sitter.Node):
        """Handle variable declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                # Check if it's assigned to a function
                value_node = node.children[-1] if len(node.children) > 2 else None
                if value_node and value_node.type in ['function_expression', 'arrow_function']:
                    self._add_function_symbol(name_node, name, is_method=False)
                else:
                    self._add_variable_symbol(name_node, name)

    def _handle_import(self, node: tree_sitter.Node):
        """Handle import statements."""
        # Find imported identifiers
        for child in node.children:
            if child.type == 'import_specifier':
                name_node = self._find_child_by_type(child, 'identifier')
                if name_node:
                    name = self._get_node_text(name_node)
                    if name:
                        self._add_import_symbol(name_node, name)

    def _handle_export(self, node: tree_sitter.Node):
        """Handle export statements."""
        # Exports are usually handled as part of their declarations

    def _handle_identifier_reference(self, node: tree_sitter.Node):
        """Handle identifier references (usage, not definition)."""
        # Only handle if it's not part of a declaration
        parent = node.parent
        if parent and parent.type not in [
            'function_declaration', 'class_declaration', 'variable_declarator',
            'method_definition', 'interface_declaration', 'type_alias_declaration'
        ]:
            name = self._get_node_text(node)
            if name and len(name) > 1:  # Avoid single letters
                self._add_reference(node, name)

    def _add_function_symbol(self, node: tree_sitter.Node, name: str, is_method: bool = False):
        """Add a function symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '().')

        # Create occurrence
        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierFunction)
        self.occurrences.append(occurrence)

        # Create symbol info
        kind = scip_pb2.Method if is_method else scip_pb2.Function
        docs = [f"{'Method' if is_method else 'Function'} in {self.language}"]
        symbol_info = self._create_symbol_information(symbol_id, name, kind, docs)
        self.symbols.append(symbol_info)

    def _add_class_symbol(self, node: tree_sitter.Node, name: str):
        """Add a class symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Class,
                                                     [f"Class in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_interface_symbol(self, node: tree_sitter.Node, name: str):
        """Add an interface symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Interface,
                                                     [f"Interface in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_type_symbol(self, node: tree_sitter.Node, name: str):
        """Add a type alias symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.TypeParameter,
                                                     [f"Type alias in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_variable_symbol(self, node: tree_sitter.Node, name: str):
        """Add a variable symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Variable,
                                                     [f"Variable in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_import_symbol(self, node: tree_sitter.Node, name: str):
        """Add an import symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierNamespace)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Namespace,
                                                     [f"Import in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_reference(self, node: tree_sitter.Node, name: str):
        """Add a reference (usage) occurrence."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, 0, scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

    def _get_qualified_name(self, name: str) -> str:
        """Get qualified name based on current scope."""
        if self.scope_stack:
            return '.'.join(self.scope_stack + [name])
        return name

    def _find_child_by_type(self, node: tree_sitter.Node, node_type: str) -> Optional[tree_sitter.Node]:
        """Find first child node of the given type."""
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    def _get_node_text(self, node: tree_sitter.Node) -> str:
        """Get text content of a node."""
        return self.content[node.start_byte:node.end_byte]

    def _create_symbol_id(self, name: str, kind: str) -> str:
        """Create a SCIP symbol identifier."""
        clean_path = (self.file_path.replace('/', '.').replace('\\', '.')
                     .replace('.', '_'))
        return f"local {clean_path} {name}{kind}"

    def _create_occurrence(self, node: tree_sitter.Node, symbol: str, roles: int, syntax_kind: int) -> scip_pb2.Occurrence:
        """Create a SCIP occurrence from a tree-sitter node."""
        occurrence = scip_pb2.Occurrence()

        # Convert byte positions to line/column
        start_line, start_col = self._byte_to_line_col(node.start_byte)
        end_line, end_col = self._byte_to_line_col(node.end_byte)

        occurrence.range.start.extend([start_line, start_col])
        occurrence.range.end.extend([end_line, end_col])
        occurrence.symbol = symbol
        occurrence.symbol_roles = roles
        occurrence.syntax_kind = syntax_kind

        return occurrence

    def _byte_to_line_col(self, byte_offset: int) -> tuple[int, int]:
        """Convert byte offset to line/column position."""
        content_before = self.content[:byte_offset]
        lines_before = content_before.split('\n')
        line = len(lines_before) - 1
        col = len(lines_before[-1])
        return line, col

    def _create_symbol_information(self, symbol: str, name: str, kind: int,
                                  documentation: List[str] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol
        symbol_info.kind = kind
        symbol_info.display_name = name

        if documentation:
            symbol_info.documentation.extend(documentation)

        return symbol_info
