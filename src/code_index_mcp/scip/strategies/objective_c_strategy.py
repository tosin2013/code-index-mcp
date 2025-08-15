"""Objective-C SCIP indexing strategy - SCIP standard compliant."""

import logging
import os
import re
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

import tree_sitter
from tree_sitter_c import language as c_language

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType


logger = logging.getLogger(__name__)


class ObjectiveCStrategy(SCIPIndexerStrategy):
    """SCIP-compliant Objective-C indexing strategy using Tree-sitter + regex patterns."""

    SUPPORTED_EXTENSIONS = {'.m', '.mm'}

    def __init__(self, priority: int = 95):
        """Initialize the Objective-C strategy."""
        super().__init__(priority)
        
        # Initialize C parser (handles Objective-C syntax reasonably well)
        c_lang = tree_sitter.Language(c_language())
        self.parser = tree_sitter.Parser(c_lang)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "objc"

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return True

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from Objective-C files."""
        logger.debug(f"ObjectiveCStrategy Phase 1: Processing {len(files)} files for symbol collection")
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
        logger.debug(f"ObjectiveCStrategy Phase 2: Generating documents for {len(files)} files")
        processed_count = 0
        error_count = 0
        total_occurrences = 0
        total_symbols = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                document = self._analyze_objc_file(file_path, project_path, relationships)
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
        """Collect symbol definitions from a single Objective-C file."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {os.path.relpath(file_path, project_path)}")
            return

        # Parse with Tree-sitter
        tree = self._parse_content(content)
        if not tree:
            logger.debug(f"Parse failed: {os.path.relpath(file_path, project_path)}")
            return

        # Collect symbols using both Tree-sitter and regex
        relative_path = self._get_relative_path(file_path, project_path)
        self._collect_symbols_from_tree_and_regex(tree, relative_path, content)
        logger.debug(f"Symbol collection - {relative_path}")

    def _analyze_objc_file(self, file_path: str, project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> Optional[scip_pb2.Document]:
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
        occurrences, symbols = self._analyze_tree_and_regex_for_document(tree, document.relative_path, content, relationships)

        # Add results to document
        document.occurrences.extend(occurrences)
        document.symbols.extend(symbols)

        logger.debug(f"Analyzed Objective-C file {document.relative_path}: "
                    f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _parse_content(self, content: str) -> Optional:
        """Parse Objective-C content with tree-sitter C parser."""
        try:
            content_bytes = content.encode('utf-8')
            return self.parser.parse(content_bytes)
        except Exception as e:
            logger.error(f"Failed to parse Objective-C content: {e}")
            return None

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """
        Build relationships between Objective-C symbols.
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        logger.debug(f"ObjectiveCStrategy: Building symbol relationships for {len(files)} files")
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"ObjectiveCStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships

    def _extract_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships from a single Objective-C file."""
        content = self._read_file_content(file_path)
        if not content:
            return {}
        
        relationships = {}
        relative_path = self._get_relative_path(file_path, project_path)
        
        # Class inheritance patterns
        interface_pattern = r"@interface\s+(\w+)\s*:\s*(\w+)"
        for match in re.finditer(interface_pattern, content):
            child_class = match.group(1)
            parent_class = match.group(2)
            
            child_symbol_id = self.symbol_manager.create_local_symbol(
                language="objc",
                file_path=relative_path,
                symbol_path=[child_class],
                descriptor="#"
            )
            parent_symbol_id = self.symbol_manager.create_local_symbol(
                language="objc",
                file_path=relative_path,
                symbol_path=[parent_class],
                descriptor="#"
            )
            
            if child_symbol_id not in relationships:
                relationships[child_symbol_id] = []
            relationships[child_symbol_id].append((parent_symbol_id, InternalRelationshipType.INHERITS))
        
        # Protocol adoption patterns
        protocol_pattern = r"@interface\s+(\w+).*?<(.+?)>"
        for match in re.finditer(protocol_pattern, content, re.DOTALL):
            class_name = match.group(1)
            protocols = [p.strip() for p in match.group(2).split(",")]
            
            class_symbol_id = self.symbol_manager.create_local_symbol(
                language="objc",
                file_path=relative_path,
                symbol_path=[class_name],
                descriptor="#"
            )
            
            for protocol in protocols:
                if protocol and protocol.replace(" ", "").isidentifier():
                    protocol_symbol_id = self.symbol_manager.create_local_symbol(
                        language="objc",
                        file_path=relative_path,
                        symbol_path=[protocol.strip()],
                        descriptor="#"
                    )
                    
                    if class_symbol_id not in relationships:
                        relationships[class_symbol_id] = []
                    relationships[class_symbol_id].append((protocol_symbol_id, InternalRelationshipType.IMPLEMENTS))
        
        logger.debug(f"Extracted {len(relationships)} relationships from {relative_path}")
        return relationships

    # Symbol collection methods
    def _collect_symbols_from_tree_and_regex(self, tree, file_path: str, content: str) -> None:
        """Collect symbols using both Tree-sitter and regex patterns."""
        scope_stack = []
        lines = content.split('\n')
        
        # First, use Tree-sitter for C-like constructs
        self._collect_symbols_from_tree_sitter(tree.root_node, file_path, scope_stack, content)
        
        # Then, use regex for Objective-C specific constructs
        self._collect_symbols_from_regex_patterns(file_path, lines, scope_stack)

    def _collect_symbols_from_tree_sitter(self, node, file_path: str, scope_stack: List[str], content: str):
        """Collect symbols from Tree-sitter AST for C-like constructs."""
        node_type = node.type

        if node_type == 'function_definition':
            self._register_c_function_symbol(node, file_path, scope_stack, content)
        elif node_type == 'struct_specifier':
            self._register_struct_symbol(node, file_path, scope_stack, content)
        elif node_type == 'enum_specifier':
            self._register_enum_symbol(node, file_path, scope_stack, content)
        elif node_type == 'typedef_declaration':
            self._register_typedef_symbol(node, file_path, scope_stack, content)

        # Recursively analyze child nodes
        for child in node.children:
            self._collect_symbols_from_tree_sitter(child, file_path, scope_stack, content)

    def _collect_symbols_from_regex_patterns(self, file_path: str, lines: List[str], scope_stack: List[str]):
        """Collect Objective-C specific symbols using regex patterns."""
        patterns = {
            'interface': re.compile(r'@interface\s+(\w+)(?:\s*:\s*(\w+))?', re.MULTILINE),
            'implementation': re.compile(r'@implementation\s+(\w+)', re.MULTILINE),
            'protocol': re.compile(r'@protocol\s+(\w+)', re.MULTILINE),
            'property': re.compile(r'@property[^;]*?\s+(\w+)\s*;', re.MULTILINE),
            'instance_method': re.compile(r'^[-]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
            'class_method': re.compile(r'^[+]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
            'category': re.compile(r'@interface\s+(\w+)\s*\(\s*(\w*)\s*\)', re.MULTILINE),
        }

        for line_num, line in enumerate(lines):
            line = line.strip()

            # @interface declarations
            match = patterns['interface'].match(line)
            if match:
                class_name = match.group(1)
                self._register_objc_class_symbol(class_name, file_path, scope_stack, "Objective-C interface")
                continue

            # @implementation
            match = patterns['implementation'].match(line)
            if match:
                class_name = match.group(1)
                self._register_objc_class_symbol(class_name, file_path, scope_stack, "Objective-C implementation")
                continue

            # @protocol
            match = patterns['protocol'].match(line)
            if match:
                protocol_name = match.group(1)
                self._register_objc_protocol_symbol(protocol_name, file_path, scope_stack)
                continue

            # @property
            match = patterns['property'].search(line)
            if match:
                property_name = match.group(1)
                self._register_objc_property_symbol(property_name, file_path, scope_stack)
                continue

            # Instance methods
            match = patterns['instance_method'].match(line)
            if match:
                method_name = match.group(1)
                self._register_objc_method_symbol(method_name, False, file_path, scope_stack)
                continue

            # Class methods
            match = patterns['class_method'].match(line)
            if match:
                method_name = match.group(1)
                self._register_objc_method_symbol(method_name, True, file_path, scope_stack)
                continue

    # Document analysis methods
    def _analyze_tree_and_regex_for_document(self, tree, file_path: str, content: str) -> tuple:
        """Analyze using both Tree-sitter and regex patterns to generate SCIP data."""
        occurrences = []
        symbols = []
        scope_stack = []
        lines = content.split('\n')
        
        # First, use Tree-sitter for C-like constructs
        tree_occs, tree_syms = self._analyze_tree_sitter_for_document(tree.root_node, file_path, scope_stack, content)
        occurrences.extend(tree_occs)
        symbols.extend(tree_syms)
        
        # Then, use regex for Objective-C specific constructs
        regex_occs, regex_syms = self._analyze_regex_patterns_for_document(file_path, lines, scope_stack)
        occurrences.extend(regex_occs)
        symbols.extend(regex_syms)
        
        return occurrences, symbols

    def _analyze_tree_sitter_for_document(self, node, file_path: str, scope_stack: List[str], content: str) -> tuple:
        """Analyze Tree-sitter nodes for C-like constructs and generate SCIP data."""
        occurrences = []
        symbols = []
        
        node_type = node.type

        if node_type == 'function_definition':
            occ, sym = self._process_c_function_for_document(node, file_path, scope_stack, content)
            if occ: occurrences.append(occ)
            if sym: symbols.append(sym)
        elif node_type == 'struct_specifier':
            occ, sym = self._process_struct_for_document(node, file_path, scope_stack, content)
            if occ: occurrences.append(occ)
            if sym: symbols.append(sym)
        elif node_type == 'enum_specifier':
            occ, sym = self._process_enum_for_document(node, file_path, scope_stack, content)
            if occ: occurrences.append(occ)
            if sym: symbols.append(sym)
        elif node_type == 'typedef_declaration':
            occ, sym = self._process_typedef_for_document(node, file_path, scope_stack, content)
            if occ: occurrences.append(occ)
            if sym: symbols.append(sym)
        elif node_type == 'identifier':
            occ = self._process_identifier_reference_for_document(node, file_path, scope_stack, content)
            if occ: occurrences.append(occ)

        # Recursively analyze child nodes
        for child in node.children:
            child_occs, child_syms = self._analyze_tree_sitter_for_document(child, file_path, scope_stack, content)
            occurrences.extend(child_occs)
            symbols.extend(child_syms)
        
        return occurrences, symbols

    def _analyze_regex_patterns_for_document(self, file_path: str, lines: List[str], scope_stack: List[str]) -> tuple:
        """Analyze Objective-C specific patterns using regex for SCIP document generation."""
        occurrences = []
        symbols = []
        
        patterns = {
            'interface': re.compile(r'@interface\s+(\w+)(?:\s*:\s*(\w+))?', re.MULTILINE),
            'implementation': re.compile(r'@implementation\s+(\w+)', re.MULTILINE),
            'protocol': re.compile(r'@protocol\s+(\w+)', re.MULTILINE),
            'property': re.compile(r'@property[^;]*?\s+(\w+)\s*;', re.MULTILINE),
            'instance_method': re.compile(r'^[-]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
            'class_method': re.compile(r'^[+]\s*\([^)]*\)\s*(\w+)', re.MULTILINE),
        }

        for line_num, line in enumerate(lines):
            line = line.strip()

            # @interface declarations
            match = patterns['interface'].match(line)
            if match:
                class_name = match.group(1)
                occ, sym = self._create_objc_class_symbol_for_document(line_num, class_name, file_path, scope_stack, "Objective-C interface")
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
                continue

            # @implementation
            match = patterns['implementation'].match(line)
            if match:
                class_name = match.group(1)
                occ, sym = self._create_objc_class_symbol_for_document(line_num, class_name, file_path, scope_stack, "Objective-C implementation")
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
                continue

            # @protocol
            match = patterns['protocol'].match(line)
            if match:
                protocol_name = match.group(1)
                occ, sym = self._create_objc_protocol_symbol_for_document(line_num, protocol_name, file_path, scope_stack)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
                continue

            # @property
            match = patterns['property'].search(line)
            if match:
                property_name = match.group(1)
                occ, sym = self._create_objc_property_symbol_for_document(line_num, property_name, file_path, scope_stack)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
                continue

            # Instance methods
            match = patterns['instance_method'].match(line)
            if match:
                method_name = match.group(1)
                occ, sym = self._create_objc_method_symbol_for_document(line_num, method_name, False, file_path, scope_stack)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
                continue

            # Class methods
            match = patterns['class_method'].match(line)
            if match:
                method_name = match.group(1)
                occ, sym = self._create_objc_method_symbol_for_document(line_num, method_name, True, file_path, scope_stack)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
                continue
        
        return occurrences, symbols

    # Symbol registration methods (Phase 1)
    def _register_c_function_symbol(self, node, file_path: str, scope_stack: List[str], content: str):
        """Register a C function symbol."""
        declarator = self._find_child_by_type(node, 'function_declarator')
        if declarator:
            name_node = self._find_child_by_type(declarator, 'identifier')
            if name_node:
                name = self._get_node_text(name_node, content)
                if name:
                    symbol_id = self.symbol_manager.create_local_symbol(
                        language="objc",
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
                        documentation=["C function"]
                    )

    def _register_struct_symbol(self, node, file_path: str, scope_stack: List[str], content: str):
        """Register a struct symbol."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node, content)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="objc",
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
                    documentation=["C struct"]
                )

    def _register_enum_symbol(self, node, file_path: str, scope_stack: List[str], content: str):
        """Register an enum symbol."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node, content)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="objc",
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
                    documentation=["C enum"]
                )

    def _register_typedef_symbol(self, node, file_path: str, scope_stack: List[str], content: str):
        """Register a typedef symbol."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node, content)
            if name:
                symbol_id = self.symbol_manager.create_local_symbol(
                    language="objc",
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
                    symbol_kind=scip_pb2.TypeParameter,
                    display_name=name,
                    documentation=["C typedef"]
                )

    def _register_objc_class_symbol(self, name: str, file_path: str, scope_stack: List[str], description: str):
        """Register an Objective-C class/interface symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
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
            symbol_kind=scip_pb2.Class,
            display_name=name,
            documentation=[description]
        )

    def _register_objc_protocol_symbol(self, name: str, file_path: str, scope_stack: List[str]):
        """Register an Objective-C protocol symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
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
            symbol_kind=scip_pb2.Interface,
            display_name=name,
            documentation=["Objective-C protocol"]
        )

    def _register_objc_property_symbol(self, name: str, file_path: str, scope_stack: List[str]):
        """Register an Objective-C property symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor=""
        )
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Property,
            display_name=name,
            documentation=["Objective-C property"]
        )

    def _register_objc_method_symbol(self, name: str, is_class_method: bool, file_path: str, scope_stack: List[str]):
        """Register an Objective-C method symbol."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
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
            symbol_kind=scip_pb2.Method,
            display_name=name,
            documentation=[f"Objective-C {'Class' if is_class_method else 'Instance'} method"]
        )

    # Document processing methods (Phase 2)
    def _process_c_function_for_document(self, node, file_path: str, scope_stack: List[str], content: str) -> tuple:
        """Process C function for SCIP document generation."""
        declarator = self._find_child_by_type(node, 'function_declarator')
        if declarator:
            name_node = self._find_child_by_type(declarator, 'identifier')
            if name_node:
                name = self._get_node_text(name_node, content)
                if name:
                    return self._create_function_symbol_for_document(node, name_node, name, file_path, scope_stack, "C function")
        return None, None

    def _process_struct_for_document(self, node, file_path: str, scope_stack: List[str], content: str) -> tuple:
        """Process struct for SCIP document generation."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node, content)
            if name:
                return self._create_type_symbol_for_document(node, name_node, name, scip_pb2.Struct, file_path, scope_stack, "C struct")
        return None, None

    def _process_enum_for_document(self, node, file_path: str, scope_stack: List[str], content: str) -> tuple:
        """Process enum for SCIP document generation."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node, content)
            if name:
                return self._create_type_symbol_for_document(node, name_node, name, scip_pb2.Enum, file_path, scope_stack, "C enum")
        return None, None

    def _process_typedef_for_document(self, node, file_path: str, scope_stack: List[str], content: str) -> tuple:
        """Process typedef for SCIP document generation."""
        name_node = self._find_child_by_type(node, 'type_identifier')
        if name_node:
            name = self._get_node_text(name_node, content)
            if name:
                return self._create_type_symbol_for_document(node, name_node, name, scip_pb2.TypeParameter, file_path, scope_stack, "C typedef")
        return None, None

    def _process_identifier_reference_for_document(self, node, file_path: str, scope_stack: List[str], content: str) -> Optional[scip_pb2.Occurrence]:
        """Process identifier reference for SCIP document generation."""
        # Only handle if it's not part of a declaration
        parent = node.parent
        if parent and parent.type not in [
            'function_definition', 'struct_specifier', 'enum_specifier', 'typedef_declaration'
        ]:
            name = self._get_node_text(node, content)
            if name and len(name) > 1:  # Avoid single letters
                # Try to resolve the reference
                symbol_id = self.reference_resolver.resolve_reference(name, file_path)
                if symbol_id:
                    range_obj = self.position_calculator.tree_sitter_node_to_range(node)
                    return self._create_occurrence(
                        symbol_id, range_obj, 0, scip_pb2.Identifier  # 0 = reference role
                    )
        return None

    # Symbol creation helpers for documents
    def _create_function_symbol_for_document(self, node, name_node, name: str, file_path: str, scope_stack: List[str], description: str) -> tuple:
        """Create a function symbol for SCIP document."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="()."
        )
        
        # Create definition occurrence
        range_obj = self.position_calculator.tree_sitter_node_to_range(name_node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierFunction
        )
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Function, [description]
        )
        
        return occurrence, symbol_info

    def _create_type_symbol_for_document(self, node, name_node, name: str, symbol_kind: int, file_path: str, scope_stack: List[str], description: str) -> tuple:
        """Create a type symbol for SCIP document."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="#"
        )
        
        # Create definition occurrence
        range_obj = self.position_calculator.tree_sitter_node_to_range(name_node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierType
        )
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, symbol_kind, [description]
        )
        
        return occurrence, symbol_info

    def _create_objc_class_symbol_for_document(self, line_num: int, name: str, file_path: str, scope_stack: List[str], description: str) -> tuple:
        """Create an Objective-C class/interface symbol for SCIP document."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=file_path,
            symbol_path=scope_stack + [name],
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
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Class, [description]
        )
        
        return occurrence, symbol_info

    def _create_objc_protocol_symbol_for_document(self, line_num: int, name: str, file_path: str, scope_stack: List[str]) -> tuple:
        """Create an Objective-C protocol symbol for SCIP document."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=file_path,
            symbol_path=scope_stack + [name],
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
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Interface, ["Objective-C protocol"]
        )
        
        return occurrence, symbol_info

    def _create_objc_property_symbol_for_document(self, line_num: int, name: str, file_path: str, scope_stack: List[str]) -> tuple:
        """Create an Objective-C property symbol for SCIP document."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=file_path,
            symbol_path=scope_stack + [name],
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
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Property, ["Objective-C property"]
        )
        
        return occurrence, symbol_info

    def _create_objc_method_symbol_for_document(self, line_num: int, name: str, is_class_method: bool, file_path: str, scope_stack: List[str]) -> tuple:
        """Create an Objective-C method symbol for SCIP document."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="objc",
            file_path=file_path,
            symbol_path=scope_stack + [name],
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
        
        # Create symbol information
        method_type = "Class method" if is_class_method else "Instance method"
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Method, [f"Objective-C {method_type.lower()}"]
        )
        
        return occurrence, symbol_info

    # Utility methods
    def _find_child_by_type(self, node, node_type: str) -> Optional:
        """Find first child node of the given type."""
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    def _get_node_text(self, node, content: str) -> str:
        """Get text content of a node."""
        return content[node.start_byte:node.end_byte]

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