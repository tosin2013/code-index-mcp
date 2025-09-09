"""
Java parsing strategy using tree-sitter.
"""

import logging
import re
from typing import Dict, List, Tuple, Optional
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)

import tree_sitter
from tree_sitter_java import language


class JavaParsingStrategy(ParsingStrategy):
    """Java-specific parsing strategy."""

    def __init__(self):
        self.java_language = tree_sitter.Language(language())

    def get_language_name(self) -> str:
        return "java"

    def get_supported_extensions(self) -> List[str]:
        return ['.java']

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Java file using tree-sitter."""
        return self._tree_sitter_parse(file_path, content)

    def _tree_sitter_parse(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse using tree-sitter."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        package = None

        parser = tree_sitter.Parser(self.java_language)

        try:
            tree = parser.parse(content.encode('utf8'))
            # Phase 1: Extract symbol definitions
            self._traverse_java_node(tree.root_node, content, file_path, symbols, functions, classes, imports)
            # Phase 2: Analyze method calls and build relationships
            self._analyze_java_calls(tree, content, symbols, file_path)

            # Extract package info
            for node in tree.root_node.children:
                if node.type == 'package_declaration':
                    package = self._extract_java_package(node, content)
                    break
        except Exception as e:
            logger.warning(f"Error parsing Java file {file_path}: {e}")

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            package=package
        )

        return symbols, file_info


    def _traverse_java_node(self, node, content: str, file_path: str, symbols: Dict[str, SymbolInfo],
                           functions: List[str], classes: List[str], imports: List[str]):
        """Traverse Java AST node."""
        if node.type == 'class_declaration':
            name = self._get_java_class_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                symbols[symbol_id] = SymbolInfo(
                    type="class",
                    file=file_path,
                    line=node.start_point[0] + 1
                )
                classes.append(name)

        elif node.type == 'method_declaration':
            name = self._get_java_method_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                symbols[symbol_id] = SymbolInfo(
                    type="method",
                    file=file_path,
                    line=node.start_point[0] + 1,
                    signature=self._get_java_method_signature(node, content)
                )
                functions.append(name)

        # Continue traversing children
        for child in node.children:
            self._traverse_java_node(child, content, file_path, symbols, functions, classes, imports)

    def _get_java_class_name(self, node, content: str) -> Optional[str]:
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_java_method_name(self, node, content: str) -> Optional[str]:
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_java_method_signature(self, node, content: str) -> str:
        return content[node.start_byte:node.end_byte].split('\n')[0].strip()

    def _extract_java_package(self, node, content: str) -> Optional[str]:
        for child in node.children:
            if child.type == 'scoped_identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _analyze_java_calls(self, tree, content: str, symbols: Dict[str, SymbolInfo], file_path: str):
        """Analyze Java method calls for relationships."""
        self._find_java_calls(tree.root_node, content, symbols, file_path)

    def _find_java_calls(self, node, content: str, symbols: Dict[str, SymbolInfo], file_path: str, current_method: str = None):
        """Recursively find Java method calls."""
        if node.type == 'method_declaration':
            method_name = self._get_java_method_name(node, content)
            if method_name:
                current_method = self._create_symbol_id(file_path, method_name)

        elif node.type == 'method_invocation':
            if current_method:
                called_method = self._get_called_method_name(node, content)
                if called_method:
                    # Find the called method in symbols and add relationship
                    for symbol_id, symbol_info in symbols.items():
                        symbol_name = symbol_id.split("::")[-1]
                        if symbol_name == called_method:  # Exact match instead of substring
                            if current_method not in symbol_info.called_by:
                                symbol_info.called_by.append(current_method)

        # Continue traversing children
        for child in node.children:
            self._find_java_calls(child, content, symbols, file_path, current_method)

    def _get_called_method_name(self, node, content: str) -> Optional[str]:
        """Extract called method name from method invocation node."""
        # Handle obj.method() pattern - look for the method name after the dot
        for child in node.children:
            if child.type == 'field_access':
                # For field_access nodes, get the field (method) name
                for subchild in child.children:
                    if subchild.type == 'identifier' and subchild.start_byte > child.start_byte:
                        # Get the rightmost identifier (the method name)
                        return content[subchild.start_byte:subchild.end_byte]
            elif child.type == 'identifier':
                # Direct method call without object reference
                return content[child.start_byte:child.end_byte]
        return None
