"""Java SCIP indexing strategy v2 - SCIP standard compliant."""

import logging
import os
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

try:
    import tree_sitter
    from tree_sitter_java import language as java_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator


logger = logging.getLogger(__name__)


class JavaStrategy(SCIPIndexerStrategy):
    """SCIP-compliant Java indexing strategy using Tree-sitter."""

    SUPPORTED_EXTENSIONS = {'.java'}

    def __init__(self, priority: int = 95):
        """Initialize the Java strategy v2."""
        super().__init__(priority)
        
        if not TREE_SITTER_AVAILABLE:
            raise StrategyError("Tree-sitter not available for Java strategy")
        
        # Initialize Java parser
        java_lang = tree_sitter.Language(java_language())
        self.parser = tree_sitter.Parser(java_lang)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS and TREE_SITTER_AVAILABLE

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "java"

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return TREE_SITTER_AVAILABLE

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from Java files."""
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
                document = self._analyze_java_file(file_path, project_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"Failed to analyze Java file {file_path}: {e}")
                continue
        
        return documents

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single Java file."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return

        # Parse with Tree-sitter
        tree = self._parse_content(content)
        if not tree:
            return

        # Collect symbols
        relative_path = self._get_relative_path(file_path, project_path)
        collector = JavaSymbolCollector(
            relative_path, content, tree, self.symbol_manager, self.reference_resolver
        )
        collector.analyze()

    def _analyze_java_file(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """Analyze a single Java file and generate complete SCIP document."""
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
        document.language = self.get_language_name()

        # Analyze AST and generate occurrences
        self.position_calculator = PositionCalculator(content)
        analyzer = JavaAnalyzer(
            document.relative_path,
            content,
            tree,
            self.symbol_manager,
            self.position_calculator,
            self.reference_resolver
        )
        analyzer.analyze()

        # Add results to document
        document.occurrences.extend(analyzer.occurrences)
        document.symbols.extend(analyzer.symbols)

        logger.debug(f"Analyzed Java file {document.relative_path}: "
                    f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _parse_content(self, content: str) -> Optional[tree_sitter.Tree]:
        """Parse Java content with tree-sitter."""
        try:
            content_bytes = content.encode('utf-8')
            return self.parser.parse(content_bytes)
        except Exception as e:
            logger.error(f"Failed to parse Java content: {e}")
            return None


class JavaSymbolCollector:
    """Tree-sitter based symbol collector for Java (Phase 1)."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree, symbol_manager, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.symbol_manager = symbol_manager
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []
        self.package_name = ""

    def analyze(self):
        """Analyze the tree-sitter AST to collect symbols."""
        root = self.tree.root_node
        
        # First pass: find package declaration
        self._find_package_declaration(root)
        
        # Second pass: collect symbols
        self._analyze_node(root)

    def _find_package_declaration(self, node: tree_sitter.Node):
        """Find and extract package declaration."""
        for child in node.children:
            if child.type == 'package_declaration':
                scoped_id = self._find_child_by_type(child, 'scoped_identifier')
                if scoped_id:
                    self.package_name = self._get_node_text(scoped_id)
                break

    def _analyze_node(self, node: tree_sitter.Node):
        """Recursively analyze AST nodes."""
        node_type = node.type

        if node_type == 'class_declaration':
            self._register_class_symbol(node)
        elif node_type == 'interface_declaration':
            self._register_interface_symbol(node)
        elif node_type == 'enum_declaration':
            self._register_enum_symbol(node)
        elif node_type == 'annotation_type_declaration':
            self._register_annotation_symbol(node)
        elif node_type == 'method_declaration':
            self._register_method_symbol(node)
        elif node_type == 'constructor_declaration':
            self._register_constructor_symbol(node)
        elif node_type == 'field_declaration':
            self._register_field_symbols(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)

    def _register_class_symbol(self, node: tree_sitter.Node):
        """Register a class symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.Class, "#", ["Java class"])

    def _register_interface_symbol(self, node: tree_sitter.Node):
        """Register an interface symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.Interface, "#", ["Java interface"])

    def _register_enum_symbol(self, node: tree_sitter.Node):
        """Register an enum symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.Enum, "#", ["Java enum"])

    def _register_annotation_symbol(self, node: tree_sitter.Node):
        """Register an annotation symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.Interface, "#", ["Java annotation"])

    def _register_method_symbol(self, node: tree_sitter.Node):
        """Register a method symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.Method, "().", ["Java method"])

    def _register_constructor_symbol(self, node: tree_sitter.Node):
        """Register a constructor symbol definition."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._register_symbol(name, scip_pb2.Method, "().", ["Java constructor"])

    def _register_field_symbols(self, node: tree_sitter.Node):
        """Register field symbol definitions."""
        # Find variable_declarator nodes
        for child in node.children:
            if child.type == 'variable_declarator':
                name_node = self._find_child_by_type(child, 'identifier')
                if name_node:
                    name = self._get_node_text(name_node)
                    if name:
                        self._register_symbol(name, scip_pb2.Field, "", ["Java field"])

    def _register_symbol(self, name: str, symbol_kind: int, descriptor: str, documentation: List[str]):
        """Register a symbol with the reference resolver."""
        # Build qualified path including package
        qualified_path = []
        if self.package_name:
            qualified_path.extend(self.package_name.replace('.', '/').split('/'))
        qualified_path.extend(self.scope_stack)
        qualified_path.append(name)

        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=self.file_path,
            symbol_path=qualified_path,
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


class JavaAnalyzer:
    """Tree-sitter based analyzer for Java AST (Phase 2)."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree,
                 symbol_manager, position_calculator, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.symbol_manager = symbol_manager
        self.position_calculator = position_calculator
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []
        self.package_name = ""
        
        # Results
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

    def analyze(self):
        """Analyze the tree-sitter AST."""
        root = self.tree.root_node
        
        # First pass: find package declaration
        self._find_package_declaration(root)
        
        # Second pass: analyze all nodes
        self._analyze_node(root)

    def _find_package_declaration(self, node: tree_sitter.Node):
        """Find and extract package declaration."""
        for child in node.children:
            if child.type == 'package_declaration':
                scoped_id = self._find_child_by_type(child, 'scoped_identifier')
                if scoped_id:
                    self.package_name = self._get_node_text(scoped_id)
                break

    def _analyze_node(self, node: tree_sitter.Node):
        """Recursively analyze AST nodes."""
        node_type = node.type

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
                self._create_type_symbol(node, name_node, name, scip_pb2.Class, "Java class")
                
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
                self._create_type_symbol(node, name_node, name, scip_pb2.Interface, "Java interface")
                
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
                self._create_type_symbol(node, name_node, name, scip_pb2.Enum, "Java enum")
                
                # Enter enum scope
                self.scope_stack.append(name)
                
                # Analyze enum body
                enum_body = self._find_child_by_type(node, 'enum_body')
                if enum_body:
                    self._analyze_node(enum_body)
                
                # Exit enum scope
                self.scope_stack.pop()

    def _handle_annotation_declaration(self, node: tree_sitter.Node):
        """Handle annotation declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_type_symbol(node, name_node, name, scip_pb2.Interface, "Java annotation")

    def _handle_method_declaration(self, node: tree_sitter.Node):
        """Handle method declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_method_symbol(node, name_node, name, "Java method")

    def _handle_constructor_declaration(self, node: tree_sitter.Node):
        """Handle constructor declarations."""
        name_node = self._find_child_by_type(node, 'identifier')
        if name_node:
            name = self._get_node_text(name_node)
            if name:
                self._create_method_symbol(node, name_node, name, "Java constructor")

    def _handle_field_declaration(self, node: tree_sitter.Node):
        """Handle field declarations."""
        # Find variable_declarator nodes
        for child in node.children:
            if child.type == 'variable_declarator':
                name_node = self._find_child_by_type(child, 'identifier')
                if name_node:
                    name = self._get_node_text(name_node)
                    if name:
                        self._create_field_symbol(node, name_node, name)

    def _handle_import_declaration(self, node: tree_sitter.Node):
        """Handle import declarations."""
        # Find the imported name (could be scoped_identifier or asterisk)
        scoped_id = self._find_child_by_type(node, 'scoped_identifier')
        if scoped_id:
            import_name = self._get_node_text(scoped_id)
            if import_name:
                # Get the last part as the imported name
                if '.' in import_name:
                    module_name = import_name.rsplit('.', 1)[0]
                    symbol_name = import_name.rsplit('.', 1)[-1]
                else:
                    module_name = import_name
                    symbol_name = import_name

                # Create import symbol
                symbol_id = self.symbol_manager.create_stdlib_symbol(
                    language="java",
                    module_name=module_name,
                    symbol_name=symbol_name,
                    descriptor=""
                )
                
                range_obj = self.position_calculator.tree_sitter_node_to_range(scoped_id)
                occurrence = self._create_occurrence(
                    symbol_id, range_obj, scip_pb2.Import, scip_pb2.IdentifierNamespace
                )
                self.occurrences.append(occurrence)

    def _handle_identifier_reference(self, node: tree_sitter.Node):
        """Handle identifier references."""
        # Only handle if it's not part of a declaration
        parent = node.parent
        if parent and parent.type not in [
            'class_declaration', 'interface_declaration', 'enum_declaration',
            'method_declaration', 'constructor_declaration', 'field_declaration',
            'variable_declarator'
        ]:
            name = self._get_node_text(node)
            if name and len(name) > 1:  # Avoid single letters
                self._handle_name_reference(node, name)

    def _create_type_symbol(self, node: tree_sitter.Node, name_node: tree_sitter.Node, 
                           name: str, symbol_kind: int, description: str):
        """Create a type symbol (class, interface, enum, annotation)."""
        # Build qualified path including package
        qualified_path = []
        if self.package_name:
            qualified_path.extend(self.package_name.replace('.', '/').split('/'))
        qualified_path.extend(self.scope_stack)
        qualified_path.append(name)

        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=self.file_path,
            symbol_path=qualified_path,
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

    def _create_method_symbol(self, node: tree_sitter.Node, name_node: tree_sitter.Node, 
                             name: str, description: str):
        """Create a method or constructor symbol."""
        # Build qualified path including package
        qualified_path = []
        if self.package_name:
            qualified_path.extend(self.package_name.replace('.', '/').split('/'))
        qualified_path.extend(self.scope_stack)
        qualified_path.append(name)

        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=self.file_path,
            symbol_path=qualified_path,
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
            symbol_id, name, scip_pb2.Method, [description]
        )
        self.symbols.append(symbol_info)

    def _create_field_symbol(self, node: tree_sitter.Node, name_node: tree_sitter.Node, name: str):
        """Create a field symbol."""
        # Build qualified path including package
        qualified_path = []
        if self.package_name:
            qualified_path.extend(self.package_name.replace('.', '/').split('/'))
        qualified_path.extend(self.scope_stack)
        qualified_path.append(name)

        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=self.file_path,
            symbol_path=qualified_path,
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
            symbol_id, name, scip_pb2.Field, ["Java field"]
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
