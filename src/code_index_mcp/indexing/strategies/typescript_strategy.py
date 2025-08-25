"""
TypeScript parsing strategy using tree-sitter.
"""

import logging
from typing import Dict, List, Tuple, Optional
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)

import tree_sitter
from tree_sitter_typescript import language_typescript


class TypeScriptParsingStrategy(ParsingStrategy):
    """TypeScript-specific parsing strategy using tree-sitter."""

    def __init__(self):
        self.ts_language = tree_sitter.Language(language_typescript())

    def get_language_name(self) -> str:
        return "typescript"

    def get_supported_extensions(self) -> List[str]:
        return ['.ts', '.tsx']

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse TypeScript file using tree-sitter."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        exports = []

        parser = tree_sitter.Parser(self.ts_language)
        tree = parser.parse(content.encode('utf8'))
        # Phase 1: Extract symbols
        self._traverse_ts_node(tree.root_node, content, file_path, symbols, functions, classes, imports, exports)
        # Phase 2: Analyze function calls using tree-sitter
        self._analyze_ts_calls_with_tree_sitter(tree.root_node, content, file_path, symbols)

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            exports=exports
        )

        return symbols, file_info

    def _traverse_ts_node(self, node, content: str, file_path: str, symbols: Dict[str, SymbolInfo],
                         functions: List[str], classes: List[str], imports: List[str], exports: List[str]):
        """Traverse TypeScript AST node."""
        if node.type == 'function_declaration':
            name = self._get_function_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                signature = self._get_ts_function_signature(node, content)
                symbols[symbol_id] = SymbolInfo(
                    type="function",
                    file=file_path,
                    line=node.start_point[0] + 1,
                    signature=signature
                )
                functions.append(name)

        elif node.type == 'class_declaration':
            name = self._get_class_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                symbols[symbol_id] = SymbolInfo(
                    type="class",
                    file=file_path,
                    line=node.start_point[0] + 1
                )
                classes.append(name)

        elif node.type == 'interface_declaration':
            name = self._get_interface_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                symbols[symbol_id] = SymbolInfo(
                    type="interface",
                    file=file_path,
                    line=node.start_point[0] + 1
                )
                classes.append(name)  # Group interfaces with classes for simplicity

        elif node.type == 'method_definition':
            method_name = self._get_method_name(node, content)
            class_name = self._find_parent_class(node, content)
            if method_name and class_name:
                full_name = f"{class_name}.{method_name}"
                symbol_id = self._create_symbol_id(file_path, full_name)
                signature = self._get_ts_function_signature(node, content)
                symbols[symbol_id] = SymbolInfo(
                    type="method",
                    file=file_path,
                    line=node.start_point[0] + 1,
                    signature=signature
                )
                # Add method to functions list for consistency
                functions.append(full_name)

        # Continue traversing children
        for child in node.children:
            self._traverse_ts_node(child, content, file_path, symbols, functions, classes, imports, exports)

    def _get_function_name(self, node, content: str) -> Optional[str]:
        """Extract function name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_class_name(self, node, content: str) -> Optional[str]:
        """Extract class name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_interface_name(self, node, content: str) -> Optional[str]:
        """Extract interface name from tree-sitter node."""
        for child in node.children:
            if child.type == 'type_identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_method_name(self, node, content: str) -> Optional[str]:
        """Extract method name from tree-sitter node."""
        for child in node.children:
            if child.type == 'property_identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _find_parent_class(self, node, content: str) -> Optional[str]:
        """Find the parent class of a method."""
        parent = node.parent
        while parent:
            if parent.type in ['class_declaration', 'interface_declaration']:
                return self._get_class_name(parent, content) or self._get_interface_name(parent, content)
            parent = parent.parent
        return None

    def _get_ts_function_signature(self, node, content: str) -> str:
        """Extract TypeScript function signature."""
        return content[node.start_byte:node.end_byte].split('\n')[0].strip()


    def _analyze_ts_calls_with_tree_sitter(self, node, content: str, file_path: str, symbols: Dict[str, SymbolInfo],
                                           current_function: Optional[str] = None, current_class: Optional[str] = None):
        """Analyze TypeScript function calls using tree-sitter AST."""
        # Track function/method context
        if node.type == 'function_declaration':
            func_name = self._get_function_name(node, content)
            if func_name:
                current_function = f"{file_path}::{func_name}"
        elif node.type == 'method_definition':
            method_name = self._get_method_name(node, content)
            parent_class = self._find_parent_class(node, content)
            if method_name and parent_class:
                current_function = f"{file_path}::{parent_class}.{method_name}"
        elif node.type == 'class_declaration':
            current_class = self._get_class_name(node, content)

        # Detect function calls
        if node.type == 'call_expression' and current_function:
            # Extract the function being called
            called_function = None
            if node.children:
                func_node = node.children[0]
                if func_node.type == 'identifier':
                    # Direct function call
                    called_function = content[func_node.start_byte:func_node.end_byte]
                elif func_node.type == 'member_expression':
                    # Method call (obj.method or this.method)
                    for child in func_node.children:
                        if child.type == 'property_identifier':
                            called_function = content[child.start_byte:child.end_byte]
                            break

            # Add relationship if we found the called function
            if called_function:
                for symbol_id, symbol_info in symbols.items():
                    if symbol_info.type in ["function", "method"]:
                        symbol_name = symbol_id.split("::")[-1]
                        # Check for exact match or method name match
                        if (symbol_name == called_function or
                            symbol_name.endswith(f".{called_function}")):
                            if current_function not in symbol_info.called_by:
                                symbol_info.called_by.append(current_function)
                            break

        # Recursively process children
        for child in node.children:
            self._analyze_ts_calls_with_tree_sitter(child, content, file_path, symbols, current_function, current_class)

