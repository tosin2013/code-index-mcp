# pylint: disable=no-member
"""Tree-sitter based Java SCIP indexing strategy."""

import logging
import os
from typing import List, Set, Dict, Any, Optional
from pathlib import Path

import tree_sitter
from tree_sitter_java import language as java_language

from .base_strategy import SCIPIndexerStrategy, ConversionError
from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class JavaStrategy(SCIPIndexerStrategy):
    """Tree-sitter based strategy for Java files."""

    SUPPORTED_EXTENSIONS = {'.java'}

    def __init__(self, priority: int = 90):
        """Initialize with tree-sitter Java parser."""
        super().__init__(priority)


        # Initialize Java parser
        java_lang = tree_sitter.Language(java_language())
        self.parser = tree_sitter.Parser(java_lang)

        logger.info("JavaStrategy initialized with tree-sitter")

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the given file extension."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def generate_scip_documents(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """
        Generate SCIP documents using tree-sitter AST parsing.

        Args:
            files: List of Java file paths to index
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

        logger.info(f"JavaStrategy created {len(documents)} SCIP documents")
        return documents

    def _create_scip_document(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """
        Create a SCIP document for a Java file using tree-sitter.

        Args:
            file_path: Path to the Java file
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
            document.language = 'java'

            # Parse with tree-sitter
            tree = self._parse_content(content)
            if not tree:
                return None

            # Analyze the AST
            analyzer = JavaTreeSitterAnalyzer(document.relative_path, content, tree)
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

    def _parse_content(self, content: str) -> Optional[tree_sitter.Tree]:
        """Parse Java content with tree-sitter."""
        try:
            content_bytes = content.encode('utf-8')
            return self.parser.parse(content_bytes)
        except Exception as e:
            logger.error(f"Failed to parse Java content: {str(e)}")
            return None

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
        return "Java(TreeSitter)"


class JavaTreeSitterAnalyzer:
    """Tree-sitter based analyzer for Java AST."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.lines = content.split('\n')
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

        # Track package and class context
        self.package_name = ""
        self.scope_stack: List[str] = []

    def analyze(self):
        """Analyze the tree-sitter AST."""
        root = self.tree.root_node

        # First pass: find package declaration
        self._find_package_declaration(root)

        # Second pass: analyze all nodes
        self._analyze_node(root)

        logger.debug(f"Analyzed {self.file_path}: "
                    f"{len(self.occurrences)} occurrences, {len(self.symbols)} symbols")

    def _find_package_declaration(self, node: tree_sitter.Node):
        """Find and extract package declaration."""
        for child in node.children:
            if child.type == 'package_declaration':
                # Find the scoped_identifier
                scoped_id = self._find_child_by_type(child, 'scoped_identifier')
                if scoped_id:
                    self.package_name = self._get_node_text(scoped_id)
                break

    def _analyze_node(self, node: tree_sitter.Node):
        """Recursively analyze AST nodes."""
        node_type = node.type

        # Handle different Java constructs
        if node_type == 'class_declaration':
            self._handle_class_declaration(node)
        elif node_type == 'interface_declaration':
            self._handle_interface_declaration(node)
        elif node_type == 'enum_declaration':
            self._handle_enum_declaration(node)
        elif node_type == 'annotation_type_declaration':
            self._handle_annotation_declaration(node)
        elif node_type == 'method_declaration':
            self._handle_method_declaration(node)
        elif node_type == 'constructor_declaration':
            self._handle_constructor_declaration(node)
        elif node_type == 'field_declaration':
            self._handle_field_declaration(node)
        elif node_type == 'local_variable_declaration':
            self._handle_local_variable_declaration(node)
        elif node_type == 'import_declaration':
            self._handle_import_declaration(node)
        elif node_type == 'identifier':
            self._handle_identifier_reference(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)

    def _handle_class_declaration(self, node: tree_sitter.Node):
        """Handle class declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_class_symbol(name_node, name, scip_pb2.Class)

                # Enter class scope
                self.scope_stack.append(name)

                # Analyze class body
                class_body = self._find_child_by_type(node, 'class_body')
                if class_body:
                    self._analyze_node(class_body)

                # Exit class scope
                self.scope_stack.pop()

    def _handle_interface_declaration(self, node: tree_sitter.Node):
        """Handle interface declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_class_symbol(name_node, name, scip_pb2.Interface)

                # Enter interface scope
                self.scope_stack.append(name)

                # Analyze interface body
                interface_body = self._find_child_by_type(node, 'interface_body')
                if interface_body:
                    self._analyze_node(interface_body)

                # Exit interface scope
                self.scope_stack.pop()

    def _handle_enum_declaration(self, node: tree_sitter.Node):
        """Handle enum declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_class_symbol(name_node, name, scip_pb2.Enum)

                # Enter enum scope
                self.scope_stack.append(name)

                # Analyze enum body
                enum_body = self._find_child_by_type(node, 'enum_body')
                if enum_body:
                    self._analyze_node(enum_body)

                # Exit enum scope
                self.scope_stack.pop()

    def _handle_annotation_declaration(self, node: tree_sitter.Node):
        """Handle annotation type declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_class_symbol(name_node, name, scip_pb2.Interface)  # Annotations are like interfaces

    def _handle_method_declaration(self, node: tree_sitter.Node):
        """Handle method declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_method_symbol(name_node, name)

    def _handle_constructor_declaration(self, node: tree_sitter.Node):
        """Handle constructor declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_method_symbol(name_node, name, is_constructor=True)

    def _handle_field_declaration(self, node: tree_sitter.Node):
        """Handle field declarations."""
        # Find variable_declarator nodes
        for child in node.children:
            if child.type == 'variable_declarator':
                name_node = self._find_child_by_type(child, 'identifier')
                if name_node:
                    name = self._get_node_text(name_node)
                    if name:
                        self._add_field_symbol(name_node, name)

    def _handle_local_variable_declaration(self, node: tree_sitter.Node):
        """Handle local variable declarations."""
        # Find variable_declarator nodes
        for child in node.children:
            if child.type == 'variable_declarator':
                name_node = self._find_child_by_type(child, 'identifier')
                if name_node:
                    name = self._get_node_text(name_node)
                    if name:
                        self._add_local_variable_symbol(name_node, name)

    def _handle_import_declaration(self, node: tree_sitter.Node):
        """Handle import declarations."""
        # Find the imported name (could be scoped_identifier or asterisk)
        scoped_id = self._find_child_by_type(node, 'scoped_identifier')
        if scoped_id:
            import_name = self._get_node_text(scoped_id)
            if import_name:
                # Get the last part as the imported name
                parts = import_name.split('.')
                name = parts[-1] if parts else import_name
                self._add_import_symbol(scoped_id, name, import_name)

    def _handle_identifier_reference(self, node: tree_sitter.Node):
        """Handle identifier references (usage, not definition)."""
        # Only handle if it's not part of a declaration
        parent = node.parent
        if parent and parent.type not in [
            'class_declaration', 'interface_declaration', 'enum_declaration',
            'method_declaration', 'constructor_declaration', 'field_declaration',
            'local_variable_declaration', 'variable_declarator'
        ]:
            name = self._get_node_text(node)
            if name and len(name) > 1:  # Avoid single letters
                self._add_reference(node, name)

    def _add_class_symbol(self, node: tree_sitter.Node, name: str, kind: int):
        """Add a class/interface/enum symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        kind_name = {
            scip_pb2.Class: "Class",
            scip_pb2.Interface: "Interface",
            scip_pb2.Enum: "Enum"
        }.get(kind, "Type")

        symbol_info = self._create_symbol_information(symbol_id, name, kind,
                                                     [f"{kind_name} in Java"])
        self.symbols.append(symbol_info)

    def _add_method_symbol(self, node: tree_sitter.Node, name: str, is_constructor: bool = False):
        """Add a method/constructor symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '().')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierFunction)
        self.occurrences.append(occurrence)

        kind_name = "Constructor" if is_constructor else "Method"
        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Method,
                                                     [f"{kind_name} in Java"])
        self.symbols.append(symbol_info)

    def _add_field_symbol(self, node: tree_sitter.Node, name: str):
        """Add a field symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Field,
                                                     ["Field in Java"])
        self.symbols.append(symbol_info)

    def _add_local_variable_symbol(self, node: tree_sitter.Node, name: str):
        """Add a local variable symbol to the index."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Variable,
                                                     ["Local variable in Java"])
        self.symbols.append(symbol_info)

    def _add_import_symbol(self, node: tree_sitter.Node, name: str, full_name: str):
        """Add an import symbol to the index."""
        symbol_id = self._create_symbol_id(full_name, '')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierNamespace)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Namespace,
                                                     [f"Import in Java: {full_name}"])
        self.symbols.append(symbol_info)

    def _add_reference(self, node: tree_sitter.Node, name: str):
        """Add a reference (usage) occurrence."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, 0, scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

    def _get_qualified_name(self, name: str) -> str:
        """Get qualified name including package and scope."""
        parts = []

        if self.package_name:
            parts.append(self.package_name)

        parts.extend(self.scope_stack)
        parts.append(name)

        return '.'.join(parts)

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
