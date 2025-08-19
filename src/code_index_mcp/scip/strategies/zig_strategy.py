"""Zig SCIP indexing strategy - SCIP standard compliant."""

import logging
import os
import re
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

import tree_sitter
from tree_sitter_zig import language as zig_language

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType


logger = logging.getLogger(__name__)


class ZigStrategy(SCIPIndexerStrategy):
    """SCIP-compliant Zig indexing strategy."""

    SUPPORTED_EXTENSIONS = {'.zig', '.zon'}

    def __init__(self, priority: int = 95):
        """Initialize the Zig strategy."""
        super().__init__(priority)
        
        # Initialize parser
        lang = tree_sitter.Language(zig_language())
        self.parser = tree_sitter.Parser(lang)
        self.use_tree_sitter = True
        
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
        return "zig"

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return self.use_tree_sitter and self.parser is not None

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from Zig files."""
        logger.debug(f"ZigStrategy Phase 1: Processing {len(files)} files for symbol collection")
        processed_count = 0
        error_count = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                self._collect_symbols_from_file(file_path, project_path)
                processed_count += 1
                
                if i % 10 == 0 or i == len(files):
                    logger.debug(f"Phase 1 progress: {i}/{len(files)} files, last file: {relative_path}")
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"Phase 1 failed for {relative_path}: {e}")
                continue
        
        logger.info(f"Phase 1 summary: {processed_count} files processed, {error_count} errors")

    def _generate_documents_with_references(self, files: List[str], project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> List[scip_pb2.Document]:
        """Phase 2: Generate complete SCIP documents with resolved references."""
        documents = []
        logger.debug(f"ZigStrategy Phase 2: Generating documents for {len(files)} files")
        processed_count = 0
        error_count = 0
        total_occurrences = 0
        total_symbols = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                document = self._analyze_zig_file(file_path, project_path, relationships)
                if document:
                    documents.append(document)
                    total_occurrences += len(document.occurrences)
                    total_symbols += len(document.symbols)
                    processed_count += 1
                    
                if i % 10 == 0 or i == len(files):
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

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single Zig file."""
        # Reset dependencies for this file
        self._reset_dependencies()
        
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {os.path.relpath(file_path, project_path)}")
            return

        relative_path = self._get_relative_path(file_path, project_path)

        if self.use_tree_sitter and self.parser:
            # Parse with Tree-sitter
            tree = self._parse_content(content)
            if tree:
                self._collect_symbols_from_tree_sitter(tree, relative_path, content)
                # Register dependencies with symbol manager
                self._register_dependencies_with_symbol_manager()
                logger.debug(f"Tree-sitter symbol collection - {relative_path}, deps: {self._count_dependencies()}")
                return

        raise StrategyError(f"Failed to parse {relative_path} with tree-sitter for symbol collection")

    def _analyze_zig_file(self, file_path: str, project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> Optional[scip_pb2.Document]:
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

        # Reset dependencies for this file
        self._reset_dependencies()
        
        if self.use_tree_sitter and self.parser:
            # Parse with Tree-sitter
            tree = self._parse_content(content)
            if tree:
                occurrences, symbols = self._analyze_tree_sitter_for_document(tree, document.relative_path, content, relationships)
                document.occurrences.extend(occurrences)
                document.symbols.extend(symbols)
                
                # Add dependency information to symbols
                self._add_dependency_info_to_symbols(document, content)
                
                logger.debug(f"Analyzed Zig file {document.relative_path}: "
                            f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols, "
                            f"dependencies: {self._count_dependencies()}")
                return document

        raise StrategyError(f"Failed to parse {document.relative_path} with tree-sitter for document analysis")

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

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """
        Build relationships between Zig symbols.
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        logger.debug(f"ZigStrategy: Building symbol relationships for {len(files)} files")
        
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"ZigStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships

    def _extract_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships from a single Zig file."""
        content = self._read_file_content(file_path)
        if not content:
            return {}
        
        relative_path = self._get_relative_path(file_path, project_path)
        
        if self.use_tree_sitter and self.parser:
            tree = self._parse_content(content)
            if tree:
                return self._extract_relationships_from_tree_sitter(tree, relative_path, content)
        
        raise StrategyError(f"Failed to parse {relative_path} with tree-sitter for relationship extraction")

    # Tree-sitter based methods
    def _collect_symbols_from_tree_sitter(self, tree, file_path: str, content: str) -> None:
        """Collect symbols using Tree-sitter AST."""
        scope_stack = []
        
        def visit_node(node):
            node_type = node.type
            
            # Function declarations
            if node_type == 'function_declaration':
                self._register_function_symbol_ts(node, file_path, scope_stack, content)
            # Struct declarations
            elif node_type == 'struct_declaration':
                self._register_struct_symbol_ts(node, file_path, scope_stack, content)
            # Enum declarations
            elif node_type == 'enum_declaration':
                self._register_enum_symbol_ts(node, file_path, scope_stack, content)
            # Variable declarations (const/var)
            elif node_type == 'variable_declaration':
                self._register_variable_symbol_ts(node, file_path, scope_stack, content)
                # Check if it contains an @import call
                self._check_for_import_in_variable(node, file_path, scope_stack, content)
            # Test declarations
            elif node_type == 'test_declaration':
                self._register_test_symbol_ts(node, file_path, scope_stack, content)
            
            # Recursively analyze child nodes
            for child in node.children:
                visit_node(child)
        
        visit_node(tree.root_node)

    def _analyze_tree_sitter_for_document(self, tree, file_path: str, content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[List[scip_pb2.Occurrence], List[scip_pb2.SymbolInformation]]:
        """Analyze Tree-sitter AST to generate SCIP occurrences and symbols."""
        occurrences = []
        symbols = []
        scope_stack = []
        
        def visit_node(node):
            node_type = node.type
            
            # Process different node types
            if node_type == 'function_declaration':
                occ, sym = self._process_function_ts(node, file_path, scope_stack, content, relationships)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type == 'struct_declaration':
                occ, sym = self._process_struct_ts(node, file_path, scope_stack, content, relationships)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type == 'enum_declaration':
                occ, sym = self._process_enum_ts(node, file_path, scope_stack, content, relationships)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type == 'variable_declaration':
                occ, sym = self._process_variable_ts(node, file_path, scope_stack, content, relationships)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type == 'test_declaration':
                occ, sym = self._process_test_ts(node, file_path, scope_stack, content, relationships)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type == 'builtin_function_call' and self._is_import_call(node):
                # Handle @import() calls
                self._handle_import_declaration(node, file_path, scope_stack, content)
            elif node_type == 'identifier':
                occ = self._process_identifier_ts(node, file_path, scope_stack, content)
                if occ: occurrences.append(occ)
            
            # Recursively analyze child nodes
            for child in node.children:
                visit_node(child)
        
        visit_node(tree.root_node)
        return occurrences, symbols

    def _extract_relationships_from_tree_sitter(self, tree, file_path: str, content: str) -> Dict[str, List[tuple]]:
        """Extract relationships from Tree-sitter AST."""
        relationships = {}
        scope_stack = []
        
        def visit_node(node):
            node_type = node.type
            
            if node_type in ['function_declaration', 'test_declaration']:
                # Extract function call relationships within this function
                function_name = self._get_function_name_ts(node, content)
                if function_name:
                    function_symbol_id = self.symbol_manager.create_local_symbol(
                        language="zig",
                        file_path=file_path,
                        symbol_path=scope_stack + [function_name],
                        descriptor="()."
                    )
                    
                    # Find call expressions within this function
                    self._extract_calls_from_node_ts(node, function_symbol_id, relationships, file_path, scope_stack, content)
            
            # Recursively visit children
            for child in node.children:
                visit_node(child)
        
        visit_node(tree.root_node)
        return relationships

    # Tree-sitter node processing methods (missing implementations)
    def _register_function_symbol_ts(self, node, file_path: str, scope_stack: List[str], content: str) -> None:
        """Register a function symbol definition."""
        name = self._get_function_name_ts(node, content)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="()."
        )
        
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
            documentation=["Zig function"]
        )

    def _register_struct_symbol_ts(self, node, file_path: str, scope_stack: List[str], content: str) -> None:
        """Register a struct symbol definition."""
        name = self._get_struct_name_ts(node, content)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="#"
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Struct,
            display_name=name,
            documentation=["Zig struct"]
        )

    def _register_enum_symbol_ts(self, node, file_path: str, scope_stack: List[str], content: str) -> None:
        """Register an enum symbol definition."""
        name = self._get_enum_name_ts(node, content)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="#"
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Enum,
            display_name=name,
            documentation=["Zig enum"]
        )

    def _register_variable_symbol_ts(self, node, file_path: str, scope_stack: List[str], content: str) -> None:
        """Register a variable/constant symbol definition."""
        name = self._get_variable_name_ts(node, content)
        if not name:
            return
            
        # Determine if it's const or var
        is_const = self._is_const_declaration(node)
        symbol_kind = scip_pb2.Constant if is_const else scip_pb2.Variable
        descriptor = "." 
        
        symbol_id = self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor=descriptor
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=symbol_kind,
            display_name=name,
            documentation=["Zig constant" if is_const else "Zig variable"]
        )

    def _register_test_symbol_ts(self, node, file_path: str, scope_stack: List[str], content: str) -> None:
        """Register a test symbol definition."""
        name = self._get_test_name_ts(node, content)
        if not name:
            name = "test"  # Default name for unnamed tests
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="()."
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Function,
            display_name=name,
            documentation=["Zig test"]
        )

    # Process methods for document generation
    def _process_function_ts(self, node, file_path: str, scope_stack: List[str], content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[Optional[scip_pb2.Occurrence], Optional[scip_pb2.SymbolInformation]]:
        """Process function for document generation."""
        name = self._get_function_name_ts(node, content)
        if not name:
            return None, None
            
        symbol_id = self._create_function_symbol_id_ts(name, file_path, scope_stack)
        occurrence = self._create_function_occurrence_ts(node, symbol_id)
        
        symbol_relationships = relationships.get(symbol_id, []) if relationships else []
        scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
        
        symbol_info = self._create_function_symbol_info_ts(node, symbol_id, name, scip_relationships)
        
        return occurrence, symbol_info

    def _process_struct_ts(self, node, file_path: str, scope_stack: List[str], content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[Optional[scip_pb2.Occurrence], Optional[scip_pb2.SymbolInformation]]:
        """Process struct for document generation."""
        name = self._get_struct_name_ts(node, content)
        if not name:
            return None, None
            
        symbol_id = self._create_struct_symbol_id_ts(name, file_path, scope_stack)
        occurrence = self._create_struct_occurrence_ts(node, symbol_id)
        
        symbol_relationships = relationships.get(symbol_id, []) if relationships else []
        scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
        
        symbol_info = self._create_struct_symbol_info_ts(node, symbol_id, name, scip_relationships)
        
        return occurrence, symbol_info

    def _process_enum_ts(self, node, file_path: str, scope_stack: List[str], content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[Optional[scip_pb2.Occurrence], Optional[scip_pb2.SymbolInformation]]:
        """Process enum for document generation."""
        name = self._get_enum_name_ts(node, content)
        if not name:
            return None, None
            
        symbol_id = self._create_enum_symbol_id_ts(name, file_path, scope_stack)
        occurrence = self._create_enum_occurrence_ts(node, symbol_id)
        
        symbol_relationships = relationships.get(symbol_id, []) if relationships else []
        scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
        
        symbol_info = self._create_enum_symbol_info_ts(node, symbol_id, name, scip_relationships)
        
        return occurrence, symbol_info

    def _process_variable_ts(self, node, file_path: str, scope_stack: List[str], content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[Optional[scip_pb2.Occurrence], Optional[scip_pb2.SymbolInformation]]:
        """Process variable/constant for document generation."""
        name = self._get_variable_name_ts(node, content)
        if not name:
            return None, None
            
        symbol_id = self._create_variable_symbol_id_ts(name, file_path, scope_stack, node)
        occurrence = self._create_variable_occurrence_ts(node, symbol_id)
        
        symbol_relationships = relationships.get(symbol_id, []) if relationships else []
        scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
        
        symbol_info = self._create_variable_symbol_info_ts(node, symbol_id, name, scip_relationships)
        
        return occurrence, symbol_info

    def _process_test_ts(self, node, file_path: str, scope_stack: List[str], content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[Optional[scip_pb2.Occurrence], Optional[scip_pb2.SymbolInformation]]:
        """Process test for document generation."""
        name = self._get_test_name_ts(node, content) or "test"
            
        symbol_id = self._create_test_symbol_id_ts(name, file_path, scope_stack)
        occurrence = self._create_test_occurrence_ts(node, symbol_id)
        
        symbol_relationships = relationships.get(symbol_id, []) if relationships else []
        scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
        
        symbol_info = self._create_test_symbol_info_ts(node, symbol_id, name, scip_relationships)
        
        return occurrence, symbol_info

    def _process_identifier_ts(self, node, file_path: str, scope_stack: List[str], content: str) -> Optional[scip_pb2.Occurrence]:
        """Process identifier for references."""
        name = self._get_node_text_ts(node)
        if not name:
            return None
            
        # Create a reference occurrence
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = f"local {name}"  # Simple reference
            occurrence.symbol_roles = scip_pb2.ReadAccess
            occurrence.syntax_kind = scip_pb2.IdentifierLocal
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    # Helper methods for extracting names from Tree-sitter nodes
    def _get_function_name_ts(self, node, content: str) -> Optional[str]:
        """Extract function name from function node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text_ts(child)
        return None

    def _get_struct_name_ts(self, node, content: str) -> Optional[str]:
        """Extract struct name from struct node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text_ts(child)
        return None

    def _get_enum_name_ts(self, node, content: str) -> Optional[str]:
        """Extract enum name from enum node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text_ts(child)
        return None

    def _get_variable_name_ts(self, node, content: str) -> Optional[str]:
        """Extract variable name from variable declaration node."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text_ts(child)
        return None

    def _get_test_name_ts(self, node, content: str) -> Optional[str]:
        """Extract test name from test node."""
        for child in node.children:
            if child.type == "string_literal":
                # Test with string name: test "my test" {}
                text = self._get_node_text_ts(child)
                if text:
                    return text.strip('"')
            elif child.type == "identifier":
                # Test with identifier: test my_test {}
                return self._get_node_text_ts(child)
        return None

    def _get_node_text_ts(self, node) -> Optional[str]:
        """Get text content of a Tree-sitter node."""
        if hasattr(node, 'text'):
            try:
                return node.text.decode('utf-8')
            except:
                pass
        return None

    def _is_const_declaration(self, node) -> bool:
        """Check if a declaration is const."""
        return node.type == "const_declaration"

    # Symbol ID creation methods
    def _create_function_symbol_id_ts(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for function."""
        return self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="()."
        )

    def _create_struct_symbol_id_ts(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for struct."""
        return self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="#"
        )

    def _create_enum_symbol_id_ts(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for enum."""
        return self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="#"
        )

    def _create_variable_symbol_id_ts(self, name: str, file_path: str, scope_stack: List[str], node) -> str:
        """Create symbol ID for variable/constant."""
        descriptor = "."
        return self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor=descriptor
        )

    def _create_test_symbol_id_ts(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for test."""
        return self.symbol_manager.create_local_symbol(
            language="zig",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="()."
        )

    # Occurrence creation methods
    def _create_function_occurrence_ts(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for function."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierFunctionDefinition
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_struct_occurrence_ts(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for struct."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierType
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_enum_occurrence_ts(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for enum."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierType
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_variable_occurrence_ts(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for variable/constant."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            
            # Check if this variable is an import by examining the node for @import
            is_import = self._is_variable_import(node)
            
            if is_import:
                occurrence.symbol_roles = scip_pb2.Import  # Mark as Import role
                occurrence.syntax_kind = scip_pb2.IdentifierNamespace
            else:
                occurrence.symbol_roles = scip_pb2.Definition
                occurrence.syntax_kind = scip_pb2.IdentifierConstant
                
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_test_occurrence_ts(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for test."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierFunctionDefinition
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    # Symbol information creation methods
    def _create_function_symbol_info_ts(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for function."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        symbol_info.kind = scip_pb2.Function
        
        symbol_info.documentation.append("Zig function")
        
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_struct_symbol_info_ts(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for struct."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        symbol_info.kind = scip_pb2.Struct
        
        symbol_info.documentation.append("Zig struct")
        
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_enum_symbol_info_ts(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for enum."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        symbol_info.kind = scip_pb2.Enum
        
        symbol_info.documentation.append("Zig enum")
        
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_variable_symbol_info_ts(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for variable/constant."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        
        # Determine if it's const or var
        is_const = self._is_const_declaration(node)
        symbol_info.kind = scip_pb2.Constant if is_const else scip_pb2.Variable
        symbol_info.documentation.append("Zig constant" if is_const else "Zig variable")
        
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_test_symbol_info_ts(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for test."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        symbol_info.kind = scip_pb2.Function
        
        symbol_info.documentation.append("Zig test")
        
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_scip_relationships(self, symbol_relationships: List[tuple]) -> List[scip_pb2.Relationship]:
        """Convert internal relationships to SCIP relationships."""
        scip_relationships = []
        for target_symbol_id, relationship_type in symbol_relationships:
            relationship = scip_pb2.Relationship()
            relationship.symbol = target_symbol_id
            relationship.is_reference = True
            scip_relationships.append(relationship)
        return scip_relationships

    # Dependency handling methods (Zig-specific)
    def _is_import_call(self, node) -> bool:
        """Check if a builtin function call is an @import call."""
        if node.type != "builtin_function_call":
            return False
        
        for child in node.children:
            if child.type == "builtin_identifier":
                name = self._get_node_text_ts(child)
                return name == "@import"
        return False

    def _handle_import_declaration(self, node, file_path: str, scope_stack: List[str], content: str) -> None:
        """Handle @import() declarations."""
        import_path = self._extract_import_path_from_node(node)
        if not import_path:
            return
        
        # Classify dependency type
        dependency_type = self._classify_zig_dependency(import_path)
        
        # Store dependency
        if import_path not in self.dependencies['imports'][dependency_type]:
            self.dependencies['imports'][dependency_type].append(import_path)
        
        # Create SCIP symbol for import
        var_name = f"import_{import_path.replace('.', '_').replace('/', '_')}"
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
            documentation=[f"Zig import from {import_path}"]
        )

    def _extract_import_path_from_node(self, node) -> Optional[str]:
        """Extract import path from @import() call."""
        # Look for string in arguments based on actual AST structure
        for child in node.children:
            if child.type == "arguments":
                for arg in child.children:
                    if arg.type == "string":
                        # Extract from string_content child
                        for string_child in arg.children:
                            if string_child.type == "string_content":
                                path = self._get_node_text_ts(string_child)
                                if path:
                                    return path
        return None

    def _classify_zig_dependency(self, import_path: str) -> str:
        """Classify Zig dependency based on import path."""
        # Zig standard library modules
        zig_std_modules = {
            'std', 'builtin', 'root', 'testing', 'math', 'mem', 'fs', 'net', 
            'json', 'fmt', 'log', 'crypto', 'hash', 'sort', 'thread', 'atomic',
            'os', 'process', 'time', 'random', 'debug', 'meta', 'ascii', 'unicode'
        }
        
        if import_path in zig_std_modules:
            return 'standard_library'
        elif import_path.startswith('./') or import_path.startswith('../') or import_path.endswith('.zig'):
            return 'local'
        else:
            return 'third_party'

    def _extract_calls_from_node_ts(self, node, source_symbol_id: str, relationships: Dict, file_path: str, scope_stack: List[str], content: str) -> None:
        """Extract function calls from a Tree-sitter node."""
        def visit_for_calls(n):
            if n.type == 'call_expression':
                # Get the function being called
                function_node = n.children[0] if n.children else None
                if function_node and function_node.type == 'identifier':
                    target_name = self._get_node_text_ts(function_node)
                    if target_name:
                        target_symbol_id = self._create_function_symbol_id_ts(target_name, file_path, scope_stack)
                        if source_symbol_id not in relationships:
                            relationships[source_symbol_id] = []
                        relationships[source_symbol_id].append((target_symbol_id, InternalRelationshipType.CALLS))
                        
            for child in n.children:
                visit_for_calls(child)
        
        visit_for_calls(node)

    def _check_for_import_in_variable(self, node, file_path: str, scope_stack: List[str], content: str) -> None:
        """Check if a variable declaration contains an @import call."""
        for child in node.children:
            if child.type == 'builtin_function':
                # Check if it's @import
                builtin_id = None
                for grandchild in child.children:
                    if grandchild.type == 'builtin_identifier':
                        builtin_id = self._get_node_text_ts(grandchild)
                        break
                
                if builtin_id == '@import':
                    # Extract import path
                    import_path = self._extract_import_path_from_node(child)
                    if import_path:
                        # Classify and store dependency
                        dependency_type = self._classify_zig_dependency(import_path)
                        if import_path not in self.dependencies['imports'][dependency_type]:
                            self.dependencies['imports'][dependency_type].append(import_path)
                        
                        # Create SCIP symbol for import
                        var_name = self._get_variable_name_ts(node, content)
                        if var_name:
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
                                documentation=[f"Zig import from {import_path}"]
                            )

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

    def _add_dependency_info_to_symbols(self, document: scip_pb2.Document, content: str) -> None:
        """Add dependency classification information to SCIP symbols."""
        if not self.dependencies['imports']:
            return
            
        # Update existing import symbols with dependency classification
        for symbol_info in document.symbols:
            symbol_name = self._extract_symbol_name_from_id(symbol_info.symbol)
            
            # Check if this symbol is an import
            if self._is_import_symbol(symbol_name, symbol_info):
                # Find which dependency category this import belongs to
                dependency_type = self._find_dependency_type(symbol_name)
                if dependency_type:
                    # Update symbol documentation with dependency type
                    symbol_info.documentation.append(f"Dependency type: {dependency_type}")
                    # Mark as import role
                    if hasattr(symbol_info, 'symbol_roles'):
                        symbol_info.symbol_roles |= 2  # SymbolRole.Import = 2
                        
    def _count_dependencies(self) -> str:
        """Get dependency count summary for logging."""
        total = (len(self.dependencies['imports']['standard_library']) + 
                len(self.dependencies['imports']['third_party']) + 
                len(self.dependencies['imports']['local']))
        return f"{total} total ({len(self.dependencies['imports']['standard_library'])} std, " \
               f"{len(self.dependencies['imports']['third_party'])} 3rd, " \
               f"{len(self.dependencies['imports']['local'])} local)"
               
    def _extract_symbol_name_from_id(self, symbol_id: str) -> str:
        """Extract symbol name from SCIP symbol ID."""
        # Symbol ID format: "scip-zig local code-index-mcp .../filename/symbol_name."
        parts = symbol_id.split('/')
        if parts:
            last_part = parts[-1]
            # Remove trailing descriptor (., (), #)
            if last_part.endswith('.'):
                return last_part[:-1]
            elif last_part.endswith('().'):
                return last_part[:-3]
            elif last_part.endswith('#'):
                return last_part[:-1]
        return ""
        
    def _is_import_symbol(self, symbol_name: str, symbol_info: scip_pb2.SymbolInformation) -> bool:
        """Check if a symbol represents an import."""
        # Check if symbol documentation mentions import
        for doc in symbol_info.documentation:
            if "import" in doc.lower():
                return True
        return False
        
    def _find_dependency_type(self, symbol_name: str) -> str:
        """Find which dependency type category a symbol belongs to."""
        for dep_type, imports in self.dependencies['imports'].items():
            if symbol_name in imports:
                return dep_type
        return ""
        
    def _register_dependencies_with_symbol_manager(self) -> None:
        """Register collected dependencies with the symbol manager."""
        if not self.symbol_manager or not self.dependencies['imports']:
            return
            
        for dep_type, imports in self.dependencies['imports'].items():
            for import_path in imports:
                try:
                    # Register with symbol manager for global dependency tracking
                    symbol_id = self.symbol_manager.moniker_manager.register_import(
                        package_name=import_path,
                        symbol_name=import_path,  # Use import path as symbol name
                        module_path="",
                        alias=None,
                        import_kind="namespace",  # Zig imports are namespace-like
                        version=""  # Zig doesn't use version in @import()
                    )
                    logger.debug(f"Registered dependency: {import_path} ({dep_type}) -> {symbol_id}")
                except Exception as e:
                    logger.warning(f"Failed to register dependency {import_path}: {e}")
                    
    def _is_variable_import(self, node) -> bool:
        """Check if a variable declaration contains an @import call."""
        for child in node.children:
            if child.type == 'builtin_function':
                # Check if it's @import
                builtin_id = None
                for grandchild in child.children:
                    if grandchild.type == 'builtin_identifier':
                        builtin_id = self._get_node_text_ts(grandchild)
                        break
                
                if builtin_id == '@import':
                    return True
        return False
