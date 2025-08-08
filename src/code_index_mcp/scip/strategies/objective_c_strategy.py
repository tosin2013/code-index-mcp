# pylint: disable=no-member,too-many-instance-attributes,too-few-public-methods
"""Tree-sitter based Objective-C SCIP indexing strategy."""

import logging
import os
import re
from typing import List, Set, Dict, Any, Optional
from pathlib import Path

import tree_sitter
from tree_sitter_c import language as c_language

from .base_strategy import SCIPIndexerStrategy, ConversionError
from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class ObjectiveCStrategy(SCIPIndexerStrategy):
    """Tree-sitter based strategy for Objective-C files using C parser."""

    SUPPORTED_EXTENSIONS = {'.m', '.mm'}

    def __init__(self, priority: int = 90):
        """Initialize with tree-sitter C parser (works for Objective-C)."""
        super().__init__(priority)


        # Initialize C parser (handles Objective-C syntax well)
        c_lang = tree_sitter.Language(c_language())
        self.parser = tree_sitter.Parser(c_lang)

        logger.info("ObjectiveCStrategy initialized with tree-sitter")

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the given file extension."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def generate_scip_documents(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """
        Generate SCIP documents using tree-sitter AST parsing.

        Args:
            files: List of Objective-C file paths to index
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
            except (OSError, UnicodeDecodeError, ConversionError) as e:
                logger.error(f"Failed to create SCIP document for {file_path}: {str(e)}")
                # Continue with other files

        logger.info(f"ObjectiveCStrategy created {len(documents)} SCIP documents")
        return documents

    def _create_scip_document(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """
        Create a SCIP document for an Objective-C file using tree-sitter.

        Args:
            file_path: Path to the Objective-C file
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
            document.language = 'objc' if file_path.endswith('.m') else 'objcpp'

            # Parse with tree-sitter
            tree = self._parse_content(content)
            if not tree:
                return None

            # Analyze the AST
            analyzer = ObjectiveCTreeSitterAnalyzer(document.relative_path, content, tree, document.language)
            analyzer.analyze()

            # Add results to document
            document.occurrences.extend(analyzer.occurrences)
            document.symbols.extend(analyzer.symbols)

            logger.debug(f"Created SCIP document for {document.relative_path}: "
                        f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

            return document

        except (OSError, UnicodeDecodeError, ConversionError) as e:
            logger.error(f"Failed to create SCIP document for {file_path}: {str(e)}")
            return None

    def _parse_content(self, content: str) -> Optional[tree_sitter.Tree]:
        """Parse Objective-C content with tree-sitter C parser."""
        try:
            content_bytes = content.encode('utf-8')
            return self.parser.parse(content_bytes)
        except (UnicodeDecodeError, tree_sitter.TreeSitterError) as e:
            logger.error(f"Failed to parse Objective-C content: {str(e)}")
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
        return "Objective-C(TreeSitter)"


class ObjectiveCTreeSitterAnalyzer:
    """Tree-sitter based analyzer for Objective-C AST using C parser."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree, language: str):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.language = language
        self.lines = content.split('\n')
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

        # Track class/interface context
        self.scope_stack: List[str] = []

    def analyze(self):
        """Analyze the tree-sitter AST."""
        root = self.tree.root_node

        # Analyze all nodes
        self._analyze_node(root)

        # Also perform Objective-C specific pattern matching for constructs
        # that tree-sitter C parser might not handle perfectly
        self._analyze_objc_patterns()

        logger.debug(f"Analyzed {self.file_path}: "
                    f"{len(self.occurrences)} occurrences, {len(self.symbols)} symbols")

    def _analyze_node(self, node: tree_sitter.Node):
        """Recursively analyze AST nodes."""
        node_type = node.type

        # Handle C-like constructs that work for Objective-C
        if node_type == 'function_definition':
            self._handle_function_definition(node)
        elif node_type == 'declaration':
            self._handle_declaration(node)
        elif node_type == 'struct_specifier':
            self._handle_struct_specifier(node)
        elif node_type == 'enum_specifier':
            self._handle_enum_specifier(node)
        elif node_type == 'typedef_declaration':
            self._handle_typedef_declaration(node)
        elif node_type == 'preproc_def':
            self._handle_macro_definition(node)
        elif node_type == 'preproc_include':
            self._handle_include(node)
        elif node_type == 'identifier':
            self._handle_identifier_reference(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)

    def _analyze_objc_patterns(self):
        """Analyze Objective-C specific patterns using regex as fallback."""

        # Objective-C specific patterns that tree-sitter C might miss
        patterns = {
            'interface': re.compile(r'@interface\s+(\w+)(?:\s*:\s*(\w+))?', re.MULTILINE),
            'implementation': re.compile(r'@implementation\s+(\w+)', re.MULTILINE),
            'protocol': re.compile(r'@protocol\s+(\w+)', re.MULTILINE),
            'property': re.compile(r'@property[^;]*?\s+(\w+)\s*;', re.MULTILINE),
            'instance_method': re.compile(r'^[-]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
            'class_method': re.compile(r'^[+]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
            'synthesize': re.compile(r'@synthesize\s+(\w+)', re.MULTILINE),
            'category': re.compile(r'@interface\s+(\w+)\s*\(\s*(\w*)\s*\)', re.MULTILINE),
        }

        for line_num, line in enumerate(self.lines):
            line = line.strip()

            # @interface declarations
            match = patterns['interface'].match(line)
            if match:
                class_name = match.group(1)
                superclass = match.group(2) if match.group(2) else None
                self._add_objc_interface(line_num, class_name, superclass)
                continue

            # @implementation
            match = patterns['implementation'].match(line)
            if match:
                class_name = match.group(1)
                self._add_objc_implementation(line_num, class_name)
                continue

            # @protocol
            match = patterns['protocol'].match(line)
            if match:
                protocol_name = match.group(1)
                self._add_objc_protocol(line_num, protocol_name)
                continue

            # @property
            match = patterns['property'].search(line)
            if match:
                property_name = match.group(1)
                self._add_objc_property(line_num, property_name)
                continue

            # Instance methods
            match = patterns['instance_method'].match(line)
            if match:
                method_name = match.group(1)
                self._add_objc_method(line_num, method_name, is_class_method=False)
                continue

            # Class methods
            match = patterns['class_method'].match(line)
            if match:
                method_name = match.group(1)
                self._add_objc_method(line_num, method_name, is_class_method=True)
                continue

            # @synthesize
            match = patterns['synthesize'].search(line)
            if match:
                property_name = match.group(1)
                self._add_objc_synthesize(line_num, property_name)
                continue

            # Categories
            match = patterns['category'].match(line)
            if match:
                class_name = match.group(1)
                category_name = match.group(2) or "Anonymous"
                self._add_objc_category(line_num, class_name, category_name)
                continue

    def _handle_function_definition(self, node: tree_sitter.Node):
        """Handle C function definitions."""
        declarator = self._find_child_by_type(node, 'function_declarator')
        if declarator:
            name_node = self._find_child_by_type(declarator, 'identifier')
            if name_node:
                name = self._get_node_text(name_node)
                if name:
                    self._add_function_symbol(name_node, name)

    def _handle_declaration(self, node: tree_sitter.Node):
        """Handle variable declarations."""
        # Look for init_declarator
        for child in node.children:
            if child.type == 'init_declarator':
                name_node = self._find_child_by_type(child, 'identifier')
                if name_node:
                    name = self._get_node_text(name_node)
                    if name:
                        self._add_variable_symbol(name_node, name)

    def _handle_struct_specifier(self, node: tree_sitter.Node):
        """Handle struct definitions."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_struct_symbol(name_node, name)

    def _handle_enum_specifier(self, node: tree_sitter.Node):
        """Handle enum definitions."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_enum_symbol(name_node, name)

    def _handle_typedef_declaration(self, node: tree_sitter.Node):
        """Handle typedef declarations."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_typedef_symbol(name_node, name)

    def _handle_macro_definition(self, node: tree_sitter.Node):
        """Handle #define macros."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._add_macro_symbol(name_node, name)

    def _handle_include(self, node: tree_sitter.Node):
        """Handle #include statements."""
        # Includes are mostly for reference, don't create symbols
        # Could potentially track dependencies in the future
        logger.debug(f"Found include statement at line {node.start_point[0]}")

    def _handle_identifier_reference(self, node: tree_sitter.Node):
        """Handle identifier references (usage, not definition)."""
        # Only handle if it's not part of a declaration
        parent = node.parent
        if parent and parent.type not in [
            'function_definition', 'declaration', 'struct_specifier',
            'enum_specifier', 'typedef_declaration'
        ]:
            name = self._get_node_text(node)
            if name and len(name) > 1:  # Avoid single letters
                self._add_reference(node, name)

    # Objective-C specific symbol creators
    def _add_objc_interface(self, line_num: int, class_name: str, superclass: str = None):
        """Add an @interface declaration."""
        qualified_name = self._get_qualified_name(class_name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence_from_line(line_num, class_name, symbol_id,
                                                      roles=scip_pb2.Definition, syntax_kind=scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        docs = ["Objective-C interface"]
        if superclass:
            docs.append(f"Inherits from {superclass}")

        symbol_info = self._create_symbol_information(symbol_id, class_name, scip_pb2.Class, docs)
        self.symbols.append(symbol_info)

    def _add_objc_implementation(self, line_num: int, class_name: str):
        """Add an @implementation declaration."""
        qualified_name = self._get_qualified_name(class_name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence_from_line(line_num, class_name, symbol_id,
                                                      roles=scip_pb2.Definition, syntax_kind=scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, class_name, scip_pb2.Class,
                                                     ["Objective-C implementation"])
        self.symbols.append(symbol_info)

    def _add_objc_protocol(self, line_num: int, protocol_name: str):
        """Add an @protocol declaration."""
        qualified_name = self._get_qualified_name(protocol_name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence_from_line(line_num, protocol_name, symbol_id,
                                                      roles=scip_pb2.Definition, syntax_kind=scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, protocol_name, scip_pb2.Interface,
                                                     ["Objective-C protocol"])
        self.symbols.append(symbol_info)

    def _add_objc_property(self, line_num: int, property_name: str):
        """Add an @property declaration."""
        qualified_name = self._get_qualified_name(property_name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence_from_line(line_num, property_name, symbol_id,
                                                      roles=scip_pb2.Definition, syntax_kind=scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, property_name, scip_pb2.Property,
                                                     ["Objective-C property"])
        self.symbols.append(symbol_info)

    def _add_objc_method(self, line_num: int, method_name: str, is_class_method: bool = False):
        """Add an Objective-C method declaration."""
        qualified_name = self._get_qualified_name(method_name)
        symbol_id = self._create_symbol_id(qualified_name, '().')

        occurrence = self._create_occurrence_from_line(line_num, method_name, symbol_id,
                                                      roles=scip_pb2.Definition, syntax_kind=scip_pb2.IdentifierFunction)
        self.occurrences.append(occurrence)

        method_type = "Class method" if is_class_method else "Instance method"
        symbol_info = self._create_symbol_information(symbol_id, method_name, scip_pb2.Method,
                                                     [f"Objective-C {method_type.lower()}"])
        self.symbols.append(symbol_info)

    def _add_objc_synthesize(self, line_num: int, property_name: str):
        """Add an @synthesize declaration."""
        qualified_name = self._get_qualified_name(property_name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence_from_line(line_num, property_name, symbol_id,
                                                      roles=scip_pb2.Definition, syntax_kind=scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, property_name, scip_pb2.Property,
                                                     ["Objective-C synthesized property"])
        self.symbols.append(symbol_info)

    def _add_objc_category(self, line_num: int, class_name: str, category_name: str):
        """Add an Objective-C category declaration."""
        full_name = f"{class_name}({category_name})"
        qualified_name = self._get_qualified_name(full_name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence_from_line(line_num, class_name, symbol_id,
                                                      roles=scip_pb2.Definition, syntax_kind=scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, full_name, scip_pb2.Class,
                                                     [f"Objective-C category on {class_name}"])
        self.symbols.append(symbol_info)

    # C-style symbol creators
    def _add_function_symbol(self, node: tree_sitter.Node, name: str):
        """Add a C function symbol."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '().')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierFunction)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Function,
                                                     [f"C function in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_variable_symbol(self, node: tree_sitter.Node, name: str):
        """Add a variable symbol."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Variable,
                                                     [f"Variable in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_struct_symbol(self, node: tree_sitter.Node, name: str):
        """Add a struct symbol."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Struct,
                                                     [f"Struct in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_enum_symbol(self, node: tree_sitter.Node, name: str):
        """Add an enum symbol."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Enum,
                                                     [f"Enum in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_typedef_symbol(self, node: tree_sitter.Node, name: str):
        """Add a typedef symbol."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '#')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.TypeParameter,
                                                     [f"Typedef in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_macro_symbol(self, node: tree_sitter.Node, name: str):
        """Add a macro symbol."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, scip_pb2.Definition, scip_pb2.IdentifierMacro)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Constant,
                                                     [f"Macro in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_reference(self, node: tree_sitter.Node, name: str):
        """Add a reference (usage) occurrence."""
        qualified_name = self._get_qualified_name(name)
        symbol_id = self._create_symbol_id(qualified_name, '')

        occurrence = self._create_occurrence(node, symbol_id, 0, scip_pb2.IdentifierLocal)
        self.occurrences.append(occurrence)

    # Utility methods
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

    def _create_occurrence_from_line(self, line_num: int, name: str, symbol: str, *, roles: int, syntax_kind: int) -> scip_pb2.Occurrence:
        """Create a SCIP occurrence from line/column position."""
        occurrence = scip_pb2.Occurrence()

        # Find the position of the name in the line
        line_content = self.lines[line_num]
        col_start = line_content.find(name)
        if col_start == -1:
            col_start = 0
        col_end = col_start + len(name)

        occurrence.range.start.extend([line_num, col_start])
        occurrence.range.end.extend([line_num, col_end])
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
