"""Objective-C SCIP indexing strategy v2 - SCIP standard compliant."""

import logging
import os
import re
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

try:
    import tree_sitter
    from tree_sitter_c import language as c_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator


logger = logging.getLogger(__name__)


class ObjectiveCStrategy(SCIPIndexerStrategy):
    """SCIP-compliant Objective-C indexing strategy using Tree-sitter + regex patterns."""

    SUPPORTED_EXTENSIONS = {'.m', '.mm'}

    def __init__(self, priority: int = 95):
        """Initialize the Objective-C strategy v2."""
        super().__init__(priority)
        
        if not TREE_SITTER_AVAILABLE:
            raise StrategyError("Tree-sitter not available for Objective-C strategy")
        
        # Initialize C parser (handles Objective-C syntax reasonably well)
        c_lang = tree_sitter.Language(c_language())
        self.parser = tree_sitter.Parser(c_lang)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS and TREE_SITTER_AVAILABLE

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "objc"

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return TREE_SITTER_AVAILABLE

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from Objective-C files."""
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
                document = self._analyze_objc_file(file_path, project_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"Failed to analyze Objective-C file {file_path}: {e}")
                continue
        
        return documents

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single Objective-C file."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return

        # Parse with Tree-sitter
        tree = self._parse_content(content)
        if not tree:
            return

        # Collect symbols using both Tree-sitter and regex
        relative_path = self._get_relative_path(file_path, project_path)
        collector = ObjectiveCSymbolCollector(
            relative_path, content, tree, self.symbol_manager, self.reference_resolver
        )
        collector.analyze()

    def _analyze_objc_file(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """Analyze a single Objective-C file and generate complete SCIP document."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return None

        # Parse with Tree-sitter
        tree = self._parse_content(content)
        if not tree:
            return None

        # Create SCIP document
        document = scip_pb2.Document()
        document.relative_path = self._get_relative_path(file_path, project_path)
        document.language = 'objc' if file_path.endswith('.m') else 'objcpp'

        # Analyze AST and generate occurrences
        self.position_calculator = PositionCalculator(content)
        analyzer = ObjectiveCAnalyzer(
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

        logger.debug(f"Analyzed Objective-C file {document.relative_path}: "
                    f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _parse_content(self, content: str) -> Optional[tree_sitter.Tree]:
        """Parse Objective-C content with tree-sitter C parser."""
        try:
            content_bytes = content.encode('utf-8')
            return self.parser.parse(content_bytes)
        except Exception as e:
            logger.error(f"Failed to parse Objective-C content: {e}")
            return None


class ObjectiveCSymbolCollector:
    """Symbol collector for Objective-C using Tree-sitter + regex patterns (Phase 1)."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree, symbol_manager, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.lines = content.split('\n')
        self.symbol_manager = symbol_manager
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []

    def analyze(self):
        """Analyze using both Tree-sitter and regex patterns."""
        # First, use Tree-sitter for C-like constructs
        root = self.tree.root_node
        self._analyze_tree_sitter_node(root)
        
        # Then, use regex for Objective-C specific constructs
        self._analyze_objc_patterns()

    def _analyze_tree_sitter_node(self, node: tree_sitter.Node):
        """Analyze Tree-sitter nodes for C-like constructs."""
        node_type = node.type

        if node_type == 'function_definition':
            self._register_c_function(node)
        elif node_type == 'struct_specifier':
            self._register_struct(node)
        elif node_type == 'enum_specifier':
            self._register_enum(node)
        elif node_type == 'typedef_declaration':
            self._register_typedef(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_tree_sitter_node(child)

    def _analyze_objc_patterns(self):
        """Analyze Objective-C specific patterns using regex."""
        patterns = {
            'interface': re.compile(r'@interface\s+(\w+)(?:\s*:\s*(\w+))?', re.MULTILINE),
            'implementation': re.compile(r'@implementation\s+(\w+)', re.MULTILINE),
            'protocol': re.compile(r'@protocol\s+(\w+)', re.MULTILINE),
            'property': re.compile(r'@property[^;]*?\s+(\w+)\s*;', re.MULTILINE),
            'instance_method': re.compile(r'^[-]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
            'class_method': re.compile(r'^[+]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
            'category': re.compile(r'@interface\s+(\w+)\s*\(\s*(\w*)\s*\)', re.MULTILINE),
        }

        for line_num, line in enumerate(self.lines):
            line = line.strip()

            # @interface declarations
            match = patterns['interface'].match(line)
            if match:
                class_name = match.group(1)
                self._register_objc_class(class_name, scip_pb2.Class, "Objective-C interface")
                continue

            # @implementation
            match = patterns['implementation'].match(line)
            if match:
                class_name = match.group(1)
                self._register_objc_class(class_name, scip_pb2.Class, "Objective-C implementation")
                continue

            # @protocol
            match = patterns['protocol'].match(line)
            if match:
                protocol_name = match.group(1)
                self._register_objc_class(protocol_name, scip_pb2.Interface, "Objective-C protocol")
                continue

            # @property
            match = patterns['property'].search(line)
            if match:
                property_name = match.group(1)
                self._register_objc_property(property_name)
                continue

            # Instance methods
            match = patterns['instance_method'].match(line)
            if match:
                method_name = match.group(1)
                self._register_objc_method(method_name, False)
                continue

            # Class methods
            match = patterns['class_method'].match(line)
            if match:
                method_name = match.group(1)
                self._register_objc_method(method_name, True)
                continue

    def _register_c_function(self, node: tree_sitter.Node):
        """Register a C function symbol."""
        declarator = self._find_child_by_type(node, 'function_declarator')
        if declarator:
            name_node = self._find_child_by_type(declarator, 'identifier')
            if name_node:
                name = self._get_node_text(name_node)
                if name:
                    self._register_symbol(name, scip_pb2.Function, "().", ["C function"])

    def _register_struct(self, node: tree_sitter.Node):
        """Register a struct symbol."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.Struct, "#", ["C struct"])

    def _register_enum(self, node: tree_sitter.Node):
        """Register an enum symbol."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.Enum, "#", ["C enum"])

    def _register_typedef(self, node: tree_sitter.Node):
        """Register a typedef symbol."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.TypeParameter, "#", ["C typedef"])

    def _register_objc_class(self, name: str, symbol_kind: int, description: str):
        """Register an Objective-C class/interface/protocol symbol."""
        self._register_symbol(name, symbol_kind, "#", [description])

    def _register_objc_property(self, name: str):
        """Register an Objective-C property symbol."""
        self._register_symbol(name, scip_pb2.Property, "", ["Objective-C property"])

    def _register_objc_method(self, name: str, is_class_method: bool):
        """Register an Objective-C method symbol."""
        method_type = "Class method" if is_class_method else "Instance method"
        self._register_symbol(name, scip_pb2.Method, "().", [f"Objective-C {method_type.lower()}"])

    def _register_symbol(self, name: str, symbol_kind: int, descriptor: str, documentation: List[str]):
        """Register a symbol with the reference resolver."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor=descriptor
        )
        
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


class ObjectiveCAnalyzer:
    """Objective-C analyzer for generating complete SCIP data (Phase 2)."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree, language: str,
                 symbol_manager, position_calculator, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.language = language
        self.lines = content.split('\n')
        self.symbol_manager = symbol_manager
        self.position_calculator = position_calculator
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []
        
        # Results
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

    def analyze(self):
        """Analyze using both Tree-sitter and regex patterns."""
        # First, use Tree-sitter for C-like constructs
        root = self.tree.root_node
        self._analyze_tree_sitter_node(root)
        
        # Then, use regex for Objective-C specific constructs
        self._analyze_objc_patterns()

    def _analyze_tree_sitter_node(self, node: tree_sitter.Node):
        """Analyze Tree-sitter nodes for C-like constructs."""
        node_type = node.type

        if node_type == 'function_definition':
            self._handle_c_function(node)
        elif node_type == 'struct_specifier':
            self._handle_struct(node)
        elif node_type == 'enum_specifier':
            self._handle_enum(node)
        elif node_type == 'typedef_declaration':
            self._handle_typedef(node)
        elif node_type == 'identifier':
            self._handle_identifier_reference(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_tree_sitter_node(child)

    def _analyze_objc_patterns(self):
        """Analyze Objective-C specific patterns using regex."""
        patterns = {
            'interface': re.compile(r'@interface\s+(\w+)(?:\s*:\s*(\w+))?', re.MULTILINE),
            'implementation': re.compile(r'@implementation\s+(\w+)', re.MULTILINE),
            'protocol': re.compile(r'@protocol\s+(\w+)', re.MULTILINE),
            'property': re.compile(r'@property[^;]*?\s+(\w+)\s*;', re.MULTILINE),
            'instance_method': re.compile(r'^[-]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
            'class_method': re.compile(r'^[+]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
        }

        for line_num, line in enumerate(self.lines):
            line = line.strip()

            # @interface declarations
            match = patterns['interface'].match(line)
            if match:
                class_name = match.group(1)
                self._create_objc_class_symbol(line_num, class_name, scip_pb2.Class, "Objective-C interface")
                continue

            # @implementation
            match = patterns['implementation'].match(line)
            if match:
                class_name = match.group(1)
                self._create_objc_class_symbol(line_num, class_name, scip_pb2.Class, "Objective-C implementation")
                continue

            # @protocol
            match = patterns['protocol'].match(line)
            if match:
                protocol_name = match.group(1)
                self._create_objc_class_symbol(line_num, protocol_name, scip_pb2.Interface, "Objective-C protocol")
                continue

            # @property
            match = patterns['property'].search(line)
            if match:
                property_name = match.group(1)
                self._create_objc_property_symbol(line_num, property_name)
                continue

            # Instance methods
            match = patterns['instance_method'].match(line)
            if match:
                method_name = match.group(1)
                self._create_objc_method_symbol(line_num, method_name, False)
                continue

            # Class methods
            match = patterns['class_method'].match(line)
            if match:
                method_name = match.group(1)
                self._create_objc_method_symbol(line_num, method_name, True)
                continue

    def _handle_c_function(self, node: tree_sitter.Node):
        """Handle C function definitions."""
        declarator = self._find_child_by_type(node, 'function_declarator')
        if declarator:
            name_node = self._find_child_by_type(declarator, 'identifier')
            if name_node:
                name = self._get_node_text(name_node)
                if name:
                    self._create_function_symbol(node, name_node, name, "C function")

    def _handle_struct(self, node: tree_sitter.Node):
        """Handle struct definitions."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_type_symbol(node, name_node, name, scip_pb2.Struct, "C struct")

    def _handle_enum(self, node: tree_sitter.Node):
        """Handle enum definitions."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_type_symbol(node, name_node, name, scip_pb2.Enum, "C enum")

    def _handle_typedef(self, node: tree_sitter.Node):
        """Handle typedef declarations."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_type_symbol(node, name_node, name, scip_pb2.TypeParameter, "C typedef")

    def _handle_identifier_reference(self, node: tree_sitter.Node):
        """Handle identifier references."""
        # Only handle if it's not part of a declaration
        parent = node.parent
        if parent and parent.type not in [
            'function_definition', 'struct_specifier', 'enum_specifier', 'typedef_declaration'
        ]:
            name = self._get_node_text(node)
            if name and len(name) > 1:  # Avoid single letters
                self._handle_name_reference(node, name)

    def _create_function_symbol(self, node: tree_sitter.Node, name_node: tree_sitter.Node, name: str, description: str):
        """Create a function symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
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
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Function, [description]
        )
        self.symbols.append(symbol_info)

    def _create_type_symbol(self, node: tree_sitter.Node, name_node: tree_sitter.Node, 
                           name: str, symbol_kind: int, description: str):
        """Create a type symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
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

    def _create_objc_class_symbol(self, line_num: int, name: str, symbol_kind: int, description: str):
        """Create an Objective-C class/interface/protocol symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor="#"
        )
        
        # Create definition occurrence from line position
        start_col, end_col = self.position_calculator.find_name_in_line(line_num, name)
        range_obj = self.position_calculator.line_col_to_range(
            line_num, start_col, line_num, end_col
        )
        
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierType
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, symbol_kind, [description]
        )
        self.symbols.append(symbol_info)

    def _create_objc_property_symbol(self, line_num: int, name: str):
        """Create an Objective-C property symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor=""
        )
        
        # Create definition occurrence from line position
        start_col, end_col = self.position_calculator.find_name_in_line(line_num, name)
        range_obj = self.position_calculator.line_col_to_range(
            line_num, start_col, line_num, end_col
        )
        
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierLocal
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Property, ["Objective-C property"]
        )
        self.symbols.append(symbol_info)

    def _create_objc_method_symbol(self, line_num: int, name: str, is_class_method: bool):
        """Create an Objective-C method symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor="()."
        )
        
        # Create definition occurrence from line position
        start_col, end_col = self.position_calculator.find_name_in_line(line_num, name)
        range_obj = self.position_calculator.line_col_to_range(
            line_num, start_col, line_num, end_col
        )
        
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierFunction
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        method_type = "Class method" if is_class_method else "Instance method"
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Method, [f"Objective-C {method_type.lower()}"]
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
