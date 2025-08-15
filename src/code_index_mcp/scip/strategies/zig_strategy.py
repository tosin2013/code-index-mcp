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
                logger.debug(f"Tree-sitter symbol collection - {relative_path}")
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

        if self.use_tree_sitter and self.parser:
            # Parse with Tree-sitter
            tree = self._parse_content(content)
            if tree:
                occurrences, symbols = self._analyze_tree_sitter_for_document(tree, document.relative_path, content, relationships)
                document.occurrences.extend(occurrences)
                document.symbols.extend(symbols)
                
                logger.debug(f"Analyzed Zig file {document.relative_path}: "
                            f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")
                return document

        raise StrategyError(f"Failed to parse {document.relative_path} with tree-sitter for document analysis")

        return document

    def _parse_content(self, content: str) -> Optional:
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
            # Const/var declarations
            elif node_type in ['const_declaration', 'var_declaration']:
                self._register_variable_symbol_ts(node, file_path, scope_stack, content)
            # Test declarations
            elif node_type == 'test_declaration':
                self._register_test_symbol_ts(node, file_path, scope_stack, content)
            
            # Recursively analyze child nodes
            for child in node.children:
                visit_node(child)
        
        visit_node(tree.root_node)

    def _analyze_tree_sitter_for_document(self, tree, file_path: str, content: str) -> tuple:
        """Analyze Tree-sitter AST to generate SCIP occurrences and symbols."""
        occurrences = []
        symbols = []
        scope_stack = []
        
        def visit_node(node):
            node_type = node.type
            
            # Process different node types
            if node_type == 'function_declaration':
                occ, sym = self._process_function_ts(node, file_path, scope_stack, content)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type == 'struct_declaration':
                occ, sym = self._process_struct_ts(node, file_path, scope_stack, content)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type == 'enum_declaration':
                occ, sym = self._process_enum_ts(node, file_path, scope_stack, content)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type in ['const_declaration', 'var_declaration']:
                occ, sym = self._process_variable_ts(node, file_path, scope_stack, content)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
            elif node_type == 'test_declaration':
                occ, sym = self._process_test_ts(node, file_path, scope_stack, content)
                if occ: occurrences.append(occ)
                if sym: symbols.append(sym)
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
