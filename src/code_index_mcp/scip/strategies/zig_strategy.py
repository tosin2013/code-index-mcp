"""Zig SCIP indexing strategy - SCIP standard compliant."""

import logging
import os
import re
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

try:
    import tree_sitter
    try:
        from tree_sitter_zig import language as zig_language
        TREE_SITTER_AVAILABLE = True
    except ImportError:
        # Try alternative import pattern
        try:
            import tree_sitter_zig
            zig_language = tree_sitter_zig.language
            TREE_SITTER_AVAILABLE = True
        except ImportError:
            TREE_SITTER_AVAILABLE = False
except ImportError:
    TREE_SITTER_AVAILABLE = False

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator


logger = logging.getLogger(__name__)


class ZigStrategy(SCIPIndexerStrategy):
    """SCIP-compliant Zig indexing strategy."""

    SUPPORTED_EXTENSIONS = {'.zig', '.zon'}

    def __init__(self, priority: int = 95):
        """Initialize the Zig strategy."""
        super().__init__(priority)
        
        if TREE_SITTER_AVAILABLE:
            try:
                # Initialize parser
                lang = tree_sitter.Language(zig_language())
                self.parser = tree_sitter.Parser(lang)
                self.use_tree_sitter = True
            except Exception as e:
                logger.warning(f"Failed to initialize tree-sitter-zig: {e}")
                self.use_tree_sitter = False
                self.parser = None
        else:
            self.use_tree_sitter = False
            self.parser = None
            logger.info("tree-sitter-zig not available, using regex-based parsing")

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "zig"

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return True  # Always available, fallback to regex if tree-sitter not available

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from Zig files."""
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
                document = self._analyze_zig_file(file_path, project_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"Failed to analyze Zig file {file_path}: {e}")
                continue
        
        return documents

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single Zig file."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return

        relative_path = self._get_relative_path(file_path, project_path)

        if self.use_tree_sitter and self.parser:
            # Parse with Tree-sitter
            tree = self._parse_content(content)
            if tree:
                collector = ZigTreeSitterSymbolCollector(
                    relative_path, content, tree, self.symbol_manager, self.reference_resolver
                )
                collector.analyze()
                return

        # Fallback to regex-based collection
        collector = ZigRegexSymbolCollector(
            relative_path, content, self.symbol_manager, self.reference_resolver
        )
        collector.analyze()

    def _analyze_zig_file(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """Analyze a single Zig file and generate complete SCIP document."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return None

        # Create SCIP document
        document = scip_pb2.Document()
        document.relative_path = self._get_relative_path(file_path, project_path)
        document.language = "zig"

        # Initialize position calculator
        self.position_calculator = PositionCalculator(content)

        if self.use_tree_sitter and self.parser:
            # Parse with Tree-sitter
            tree = self._parse_content(content)
            if tree:
                analyzer = ZigTreeSitterAnalyzer(
                    document.relative_path,
                    content,
                    tree,
                    document.language,
                    self.symbol_manager,
                    self.position_calculator,
                    self.reference_resolver
                )
                analyzer.analyze()
                document.occurrences.extend(analyzer.occurrences)
                document.symbols.extend(analyzer.symbols)
                
                logger.debug(f"Analyzed Zig file {document.relative_path}: "
                            f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")
                return document

        # Fallback to regex-based analysis
        analyzer = ZigRegexAnalyzer(
            document.relative_path,
            content,
            document.language,
            self.symbol_manager,
            self.position_calculator,
            self.reference_resolver
        )
        analyzer.analyze()
        
        document.occurrences.extend(analyzer.occurrences)
        document.symbols.extend(analyzer.symbols)

        logger.debug(f"Analyzed Zig file {document.relative_path} (regex): "
                    f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _parse_content(self, content: str) -> Optional[tree_sitter.Tree]:
        """Parse content with tree-sitter parser."""
        if not self.parser:
            return None
        
        try:
            content_bytes = content.encode('utf-8')
            return self.parser.parse(content_bytes)
        except Exception as e:
            logger.error(f"Failed to parse content with tree-sitter: {e}")
            return None


class ZigTreeSitterSymbolCollector:
    """Tree-sitter based symbol collector for Zig (Phase 1)."""

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

        # Function declarations
        if node_type == 'function_declaration':
            self._register_function_symbol(node)
        # Struct declarations
        elif node_type == 'struct_declaration':
            self._register_struct_symbol(node)
        # Enum declarations
        elif node_type == 'enum_declaration':
            self._register_enum_symbol(node)
        # Const/var declarations
        elif node_type in ['const_declaration', 'var_declaration']:
            self._register_variable_symbol(node)
        # Test declarations
        elif node_type == 'test_declaration':
            self._register_test_symbol(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)

    def _register_function_symbol(self, node: tree_sitter.Node):
        """Register a function symbol."""
        # Try to find the function name
        for child in node.children:
            if child.type == 'identifier':
                name = self.content[child.start_byte:child.end_byte]
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="()."
                )
                self.reference_resolver.register_definition(name, symbol_id, self.file_path)
                break

    def _register_struct_symbol(self, node: tree_sitter.Node):
        """Register a struct symbol."""
        # Look for the struct name (usually in a const declaration)
        parent = node.parent
        if parent and parent.type == 'const_declaration':
            for child in parent.children:
                if child.type == 'identifier':
                    name = self.content[child.start_byte:child.end_byte]
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    self.reference_resolver.register_definition(name, symbol_id, self.file_path)
                    break

    def _register_enum_symbol(self, node: tree_sitter.Node):
        """Register an enum symbol."""
        # Look for the enum name (usually in a const declaration)
        parent = node.parent
        if parent and parent.type == 'const_declaration':
            for child in parent.children:
                if child.type == 'identifier':
                    name = self.content[child.start_byte:child.end_byte]
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    self.reference_resolver.register_definition(name, symbol_id, self.file_path)
                    break

    def _register_variable_symbol(self, node: tree_sitter.Node):
        """Register a variable or constant symbol."""
        for child in node.children:
            if child.type == 'identifier':
                name = self.content[child.start_byte:child.end_byte]
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor=""
                )
                self.reference_resolver.register_definition(name, symbol_id, self.file_path)
                break

    def _register_test_symbol(self, node: tree_sitter.Node):
        """Register a test symbol."""
        # Test names are usually string literals
        for child in node.children:
            if child.type == 'string_literal':
                name = self.content[child.start_byte:child.end_byte].strip('"')
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=["test", name],
                    descriptor="()."
                )
                self.reference_resolver.register_definition(f"test_{name}", symbol_id, self.file_path)
                break


class ZigTreeSitterAnalyzer:
    """Tree-sitter based analyzer for Zig (Phase 2)."""

    def __init__(self, file_path: str, content: str, tree: tree_sitter.Tree,
                 language: str, symbol_manager, position_calculator, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.tree = tree
        self.language = language
        self.symbol_manager = symbol_manager
        self.position_calculator = position_calculator
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

    def analyze(self):
        """Analyze the tree-sitter AST to generate SCIP occurrences."""
        root = self.tree.root_node
        self._analyze_node(root)

    def _analyze_node(self, node: tree_sitter.Node):
        """Recursively analyze AST nodes and generate occurrences."""
        node_type = node.type

        # Process different node types
        if node_type == 'function_declaration':
            self._process_function(node)
        elif node_type == 'struct_declaration':
            self._process_struct(node)
        elif node_type == 'enum_declaration':
            self._process_enum(node)
        elif node_type in ['const_declaration', 'var_declaration']:
            self._process_variable(node)
        elif node_type == 'test_declaration':
            self._process_test(node)
        elif node_type == 'identifier':
            self._process_identifier(node)

        # Recursively analyze child nodes
        for child in node.children:
            self._analyze_node(child)

    def _process_function(self, node: tree_sitter.Node):
        """Process a function declaration."""
        for child in node.children:
            if child.type == 'identifier':
                name = self.content[child.start_byte:child.end_byte]
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="()."
                )
                
                # Create occurrence
                occurrence = self._create_occurrence(child, symbol_id, is_definition=True)
                if occurrence:
                    self.occurrences.append(occurrence)
                
                # Create symbol information
                symbol_info = self._create_symbol_info(symbol_id, name, "function")
                if symbol_info:
                    self.symbols.append(symbol_info)
                break

    def _process_struct(self, node: tree_sitter.Node):
        """Process a struct declaration."""
        parent = node.parent
        if parent and parent.type == 'const_declaration':
            for child in parent.children:
                if child.type == 'identifier':
                    name = self.content[child.start_byte:child.end_byte]
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    
                    occurrence = self._create_occurrence(child, symbol_id, is_definition=True)
                    if occurrence:
                        self.occurrences.append(occurrence)
                    
                    symbol_info = self._create_symbol_info(symbol_id, name, "struct")
                    if symbol_info:
                        self.symbols.append(symbol_info)
                    break

    def _process_enum(self, node: tree_sitter.Node):
        """Process an enum declaration."""
        parent = node.parent
        if parent and parent.type == 'const_declaration':
            for child in parent.children:
                if child.type == 'identifier':
                    name = self.content[child.start_byte:child.end_byte]
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    
                    occurrence = self._create_occurrence(child, symbol_id, is_definition=True)
                    if occurrence:
                        self.occurrences.append(occurrence)
                    
                    symbol_info = self._create_symbol_info(symbol_id, name, "enum")
                    if symbol_info:
                        self.symbols.append(symbol_info)
                    break

    def _process_variable(self, node: tree_sitter.Node):
        """Process a variable or constant declaration."""
        for child in node.children:
            if child.type == 'identifier':
                name = self.content[child.start_byte:child.end_byte]
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor=""
                )
                
                occurrence = self._create_occurrence(child, symbol_id, is_definition=True)
                if occurrence:
                    self.occurrences.append(occurrence)
                
                var_type = "constant" if node.type == 'const_declaration' else "variable"
                symbol_info = self._create_symbol_info(symbol_id, name, var_type)
                if symbol_info:
                    self.symbols.append(symbol_info)
                break

    def _process_test(self, node: tree_sitter.Node):
        """Process a test declaration."""
        for child in node.children:
            if child.type == 'string_literal':
                name = self.content[child.start_byte:child.end_byte].strip('"')
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=["test", name],
                    descriptor="()."
                )
                
                occurrence = self._create_occurrence(child, symbol_id, is_definition=True)
                if occurrence:
                    self.occurrences.append(occurrence)
                
                symbol_info = self._create_symbol_info(symbol_id, f"test_{name}", "test")
                if symbol_info:
                    self.symbols.append(symbol_info)
                break

    def _process_identifier(self, node: tree_sitter.Node):
        """Process an identifier that might be a reference."""
        # Skip if this is part of a definition
        parent = node.parent
        if parent and parent.type in ['function_declaration', 'const_declaration', 
                                       'var_declaration', 'struct_declaration', 
                                       'enum_declaration']:
            return
        
        name = self.content[node.start_byte:node.end_byte]
        # Try to resolve the reference
        symbol_id = self.reference_resolver.resolve_reference(name, self.file_path)
        if symbol_id:
            occurrence = self._create_occurrence(node, symbol_id, is_definition=False)
            if occurrence:
                self.occurrences.append(occurrence)

    def _create_occurrence(self, node: tree_sitter.Node, symbol_id: str, is_definition: bool) -> Optional[scip_pb2.Occurrence]:
        """Create a SCIP occurrence from a tree-sitter node."""
        try:
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.SymbolRole.Definition if is_definition else 0
            
            # Calculate range
            start_line = node.start_point[0]
            start_col = node.start_point[1]
            end_line = node.end_point[0]
            end_col = node.end_point[1]
            
            occurrence.range.extend([start_line, start_col, end_col])
            if end_line > start_line:
                occurrence.range.extend([end_line, end_col])
            
            return occurrence
        except Exception as e:
            logger.error(f"Failed to create occurrence: {e}")
            return None

    def _create_symbol_info(self, symbol_id: str, name: str, kind: str) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information."""
        try:
            symbol_info = scip_pb2.SymbolInformation()
            symbol_info.symbol = symbol_id
            symbol_info.display_name = name
            
            # Map kind to SCIP kind
            kind_mapping = {
                'function': scip_pb2.SymbolInformation.Kind.Function,
                'struct': scip_pb2.SymbolInformation.Kind.Struct,
                'enum': scip_pb2.SymbolInformation.Kind.Enum,
                'constant': scip_pb2.SymbolInformation.Kind.Constant,
                'variable': scip_pb2.SymbolInformation.Kind.Variable,
                'test': scip_pb2.SymbolInformation.Kind.Function,
            }
            
            symbol_info.kind = kind_mapping.get(kind, scip_pb2.SymbolInformation.Kind.UnspecifiedKind)
            
            return symbol_info
        except Exception as e:
            logger.error(f"Failed to create symbol info: {e}")
            return None


class ZigRegexSymbolCollector:
    """Regex-based symbol collector for Zig (Phase 1 fallback)."""

    def __init__(self, file_path: str, content: str, symbol_manager, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.symbol_manager = symbol_manager
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []

    def analyze(self):
        """Analyze content using regex patterns to collect symbols."""
        lines = self.content.splitlines()
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip comments and empty lines
            if not line_stripped or line_stripped.startswith('//'):
                continue
            
            # Function definitions
            if match := re.search(r'(?:pub\s+)?fn\s+(\w+)\s*\(', line):
                name = match.group(1)
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="()."
                )
                self.reference_resolver.register_definition(name, symbol_id, self.file_path)
            
            # Struct definitions
            if 'struct' in line and 'const' in line:
                if match := re.search(r'const\s+(\w+)\s*=\s*struct', line):
                    name = match.group(1)
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    self.reference_resolver.register_definition(name, symbol_id, self.file_path)
            
            # Enum definitions
            if 'enum' in line and 'const' in line:
                if match := re.search(r'const\s+(\w+)\s*=\s*enum', line):
                    name = match.group(1)
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    self.reference_resolver.register_definition(name, symbol_id, self.file_path)
            
            # Error sets
            if 'error{' in line and 'const' in line:
                if match := re.search(r'const\s+(\w+)\s*=\s*error\{', line):
                    name = match.group(1)
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    self.reference_resolver.register_definition(name, symbol_id, self.file_path)
            
            # Test blocks
            if match := re.search(r'test\s+"([^"]+)"', line):
                name = match.group(1)
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=["test", name],
                    descriptor="()."
                )
                self.reference_resolver.register_definition(f"test_{name}", symbol_id, self.file_path)


class ZigRegexAnalyzer:
    """Regex-based analyzer for Zig (Phase 2 fallback)."""

    def __init__(self, file_path: str, content: str, language: str,
                 symbol_manager, position_calculator, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.language = language
        self.symbol_manager = symbol_manager
        self.position_calculator = position_calculator
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

    def analyze(self):
        """Analyze content using regex patterns to generate SCIP occurrences."""
        lines = self.content.splitlines()
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip comments and empty lines
            if not line_stripped or line_stripped.startswith('//'):
                continue
            
            # Function definitions
            if match := re.search(r'(?:pub\s+)?fn\s+(\w+)\s*\(', line):
                name = match.group(1)
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="zig",
                    file_path=self.file_path,
                    symbol_path=self.scope_stack + [name],
                    descriptor="()."
                )
                
                # Create occurrence
                start_col = match.start(1)
                end_col = match.end(1)
                occurrence = self._create_occurrence_from_position(
                    line_num, start_col, end_col, symbol_id, is_definition=True
                )
                if occurrence:
                    self.occurrences.append(occurrence)
                
                # Create symbol info
                symbol_info = self._create_symbol_info(symbol_id, name, "function")
                if symbol_info:
                    self.symbols.append(symbol_info)
            
            # Struct definitions
            if 'struct' in line and 'const' in line:
                if match := re.search(r'const\s+(\w+)\s*=\s*struct', line):
                    name = match.group(1)
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    
                    start_col = match.start(1)
                    end_col = match.end(1)
                    occurrence = self._create_occurrence_from_position(
                        line_num, start_col, end_col, symbol_id, is_definition=True
                    )
                    if occurrence:
                        self.occurrences.append(occurrence)
                    
                    symbol_info = self._create_symbol_info(symbol_id, name, "struct")
                    if symbol_info:
                        self.symbols.append(symbol_info)
            
            # Enum definitions
            if 'enum' in line and 'const' in line:
                if match := re.search(r'const\s+(\w+)\s*=\s*enum', line):
                    name = match.group(1)
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=self.file_path,
                        symbol_path=self.scope_stack + [name],
                        descriptor="#"
                    )
                    
                    start_col = match.start(1)
                    end_col = match.end(1)
                    occurrence = self._create_occurrence_from_position(
                        line_num, start_col, end_col, symbol_id, is_definition=True
                    )
                    if occurrence:
                        self.occurrences.append(occurrence)
                    
                    symbol_info = self._create_symbol_info(symbol_id, name, "enum")
                    if symbol_info:
                        self.symbols.append(symbol_info)

    def _create_occurrence_from_position(self, line: int, start_col: int, end_col: int,
                                          symbol_id: str, is_definition: bool) -> Optional[scip_pb2.Occurrence]:
        """Create a SCIP occurrence from line and column positions."""
        try:
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.SymbolRole.Definition if is_definition else 0
            
            # SCIP uses 0-indexed lines and columns
            occurrence.range.extend([line, start_col, end_col])
            
            return occurrence
        except Exception as e:
            logger.error(f"Failed to create occurrence: {e}")
            return None

    def _create_symbol_info(self, symbol_id: str, name: str, kind: str) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information."""
        try:
            symbol_info = scip_pb2.SymbolInformation()
            symbol_info.symbol = symbol_id
            symbol_info.display_name = name
            
            # Map kind to SCIP kind
            kind_mapping = {
                'function': scip_pb2.SymbolInformation.Kind.Function,
                'struct': scip_pb2.SymbolInformation.Kind.Struct,
                'enum': scip_pb2.SymbolInformation.Kind.Enum,
                'constant': scip_pb2.SymbolInformation.Kind.Constant,
                'variable': scip_pb2.SymbolInformation.Kind.Variable,
                'test': scip_pb2.SymbolInformation.Kind.Function,
            }
            
            symbol_info.kind = kind_mapping.get(kind, scip_pb2.SymbolInformation.Kind.UnspecifiedKind)
            
            return symbol_info
        except Exception as e:
            logger.error(f"Failed to create symbol info: {e}")
            return None