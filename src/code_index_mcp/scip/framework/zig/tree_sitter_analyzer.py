"""Zig tree-sitter analyzer implementation."""

from typing import Iterator, Optional, Set, List, Dict, Any
from ..types import SCIPContext
from ..base.language_analyzer import BaseLanguageAnalyzer

import tree_sitter
from tree_sitter_zig import language as zig_language


class ZigTreeSitterAnalyzer(BaseLanguageAnalyzer):
    """Zig analyzer using tree-sitter for AST parsing."""
    
    def __init__(self):
        """Initialize the Zig tree-sitter analyzer."""
        lang = tree_sitter.Language(zig_language())
        self.parser = tree_sitter.Parser(lang)
        self._processed_nodes: Set[int] = set()
    
    def parse(self, content: str, filename: str = "<unknown>"):
        """Parse Zig source code into tree-sitter AST."""
        try:
            return self.parser.parse(bytes(content, 'utf8'))
        except Exception as e:
            raise SyntaxError(f"Zig syntax error in {filename}: {e}")
    
    def walk(self, tree) -> Iterator:
        """Walk tree-sitter tree nodes, avoiding duplicates."""
        for node in self._walk_node(tree.root_node):
            node_id = id(node)
            if node_id not in self._processed_nodes:
                self._processed_nodes.add(node_id)
                yield node
    
    def _walk_node(self, node) -> Iterator:
        """Recursively walk tree nodes."""
        yield node
        for child in node.children:
            yield from self._walk_node(child)
    
    def is_symbol_definition(self, node) -> bool:
        """Check if tree-sitter node represents a symbol definition."""
        return node.type in {
            'function_declaration',
            'struct_declaration',
            'union_declaration',
            'enum_declaration',
            'variable_declaration',
            'constant_declaration',
            'type_declaration',
            'container_field',
            'parameter_declaration',
            'test_declaration',
            'comptime_declaration',
            'error_set_declaration',
        }
    
    def is_symbol_reference(self, node) -> bool:
        """Check if tree-sitter node represents a symbol reference."""
        return node.type in {
            'identifier',
            'call_expression',
            'field_expression',
            'builtin_call_expr',
        }
    
    def get_symbol_name(self, node) -> Optional[str]:
        """Extract symbol name from tree-sitter node."""
        if node.type in ['function_declaration', 'struct_declaration', 'union_declaration',
                        'enum_declaration', 'variable_declaration', 'constant_declaration',
                        'type_declaration', 'test_declaration', 'comptime_declaration']:
            # Look for identifier child
            for child in node.children:
                if child.type == 'identifier':
                    return child.text.decode('utf8')
        
        elif node.type == 'container_field':
            # Field in struct/union/enum
            for child in node.children:
                if child.type == 'identifier':
                    return child.text.decode('utf8')
        
        elif node.type == 'parameter_declaration':
            # Function parameter
            for child in node.children:
                if child.type == 'identifier':
                    return child.text.decode('utf8')
        
        elif node.type == 'identifier':
            return node.text.decode('utf8')
        
        return None
    
    def get_node_position(self, node) -> tuple:
        """Get position information from tree-sitter node."""
        start_line = node.start_point[0]
        start_col = node.start_point[1]
        end_line = node.end_point[0]
        end_col = node.end_point[1]
        
        return (start_line, start_col, end_line, end_col)
    
    def extract_function_info(self, tree) -> List[Dict[str, Any]]:
        """Extract function information from the AST."""
        functions = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'function_declaration':
                function_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'function',
                    'position': self.get_node_position(node),
                    'is_public': self._is_public_function(node),
                    'is_extern': self._is_extern_function(node),
                    'return_type': self._extract_return_type(node),
                    'parameters': self._extract_function_parameters(node),
                }
                functions.append(function_info)
        
        return functions
    
    def extract_struct_info(self, tree) -> List[Dict[str, Any]]:
        """Extract struct information from the AST."""
        structs = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'struct_declaration':
                struct_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'struct',
                    'position': self.get_node_position(node),
                    'is_public': self._is_public_declaration(node),
                    'fields': self._extract_struct_fields(node),
                }
                structs.append(struct_info)
        
        return structs
    
    def extract_union_info(self, tree) -> List[Dict[str, Any]]:
        """Extract union information from the AST."""
        unions = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'union_declaration':
                union_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'union',
                    'position': self.get_node_position(node),
                    'is_public': self._is_public_declaration(node),
                    'fields': self._extract_union_fields(node),
                }
                unions.append(union_info)
        
        return unions
    
    def extract_enum_info(self, tree) -> List[Dict[str, Any]]:
        """Extract enum information from the AST."""
        enums = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'enum_declaration':
                enum_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'enum',
                    'position': self.get_node_position(node),
                    'is_public': self._is_public_declaration(node),
                    'values': self._extract_enum_values(node),
                }
                enums.append(enum_info)
        
        return enums
    
    def extract_variable_info(self, tree) -> List[Dict[str, Any]]:
        """Extract variable information from the AST."""
        variables = []
        
        for node in self._walk_node(tree.root_node):
            if node.type in ['variable_declaration', 'constant_declaration']:
                variable_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'constant' if node.type == 'constant_declaration' else 'variable',
                    'position': self.get_node_position(node),
                    'is_public': self._is_public_declaration(node),
                    'variable_type': self._extract_variable_type(node),
                    'is_mutable': node.type == 'variable_declaration',
                }
                variables.append(variable_info)
        
        return variables
    
    def extract_test_info(self, tree) -> List[Dict[str, Any]]:
        """Extract test declaration information from the AST."""
        tests = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'test_declaration':
                test_info = {
                    'name': self.get_symbol_name(node) or self._extract_test_name(node),
                    'type': 'test',
                    'position': self.get_node_position(node),
                }
                tests.append(test_info)
        
        return tests
    
    def extract_import_statements(self, tree) -> List[str]:
        """Extract import statements from the AST."""
        imports = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'builtin_call_expr':
                builtin_text = node.text.decode('utf8')
                if builtin_text.startswith('@import'):
                    import_path = self._extract_import_path(node)
                    if import_path:
                        imports.append(import_path)
        
        return imports
    
    def extract_error_set_info(self, tree) -> List[Dict[str, Any]]:
        """Extract error set information from the AST."""
        error_sets = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'error_set_declaration':
                error_set_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'error_set',
                    'position': self.get_node_position(node),
                    'errors': self._extract_error_values(node),
                }
                error_sets.append(error_set_info)
        
        return error_sets
    
    def _is_public_declaration(self, node) -> bool:
        """Check if a declaration is public."""
        # Look for 'pub' keyword in parent or siblings
        parent = node.parent
        if parent:
            for child in parent.children:
                if child.type == 'keyword' and child.text.decode('utf8') == 'pub':
                    return True
        return False
    
    def _is_public_function(self, node) -> bool:
        """Check if a function is public."""
        return self._is_public_declaration(node)
    
    def _is_extern_function(self, node) -> bool:
        """Check if a function is extern."""
        # Look for 'extern' keyword
        parent = node.parent
        if parent:
            for child in parent.children:
                if child.type == 'keyword' and child.text.decode('utf8') == 'extern':
                    return True
        return False
    
    def _extract_return_type(self, function_node) -> Optional[str]:
        """Extract return type from function declaration."""
        # Look for return type after the parameter list
        for child in function_node.children:
            if child.type in ['type_expression', 'identifier']:
                return child.text.decode('utf8')
        return None
    
    def _extract_function_parameters(self, function_node) -> List[Dict[str, str]]:
        """Extract parameter information from function declaration."""
        parameters = []
        
        for child in function_node.children:
            if child.type == 'parameter_list':
                for param_child in child.children:
                    if param_child.type == 'parameter_declaration':
                        param_name = self.get_symbol_name(param_child)
                        param_type = self._extract_parameter_type(param_child)
                        if param_name:
                            parameters.append({
                                'name': param_name,
                                'type': param_type or 'unknown'
                            })
        
        return parameters
    
    def _extract_parameter_type(self, param_node) -> Optional[str]:
        """Extract parameter type from parameter declaration."""
        for child in param_node.children:
            if child.type in ['type_expression', 'identifier']:
                return child.text.decode('utf8')
        return None
    
    def _extract_struct_fields(self, struct_node) -> List[str]:
        """Extract field names from struct declaration."""
        fields = []
        
        for child in struct_node.children:
            if child.type == 'container_declaration':
                for field_child in child.children:
                    if field_child.type == 'container_field':
                        field_name = self.get_symbol_name(field_child)
                        if field_name:
                            fields.append(field_name)
        
        return fields
    
    def _extract_union_fields(self, union_node) -> List[str]:
        """Extract field names from union declaration."""
        return self._extract_struct_fields(union_node)  # Same logic
    
    def _extract_enum_values(self, enum_node) -> List[str]:
        """Extract enum value names from enum declaration."""
        values = []
        
        for child in enum_node.children:
            if child.type == 'container_declaration':
                for value_child in child.children:
                    if value_child.type == 'container_field':
                        value_name = self.get_symbol_name(value_child)
                        if value_name:
                            values.append(value_name)
        
        return values
    
    def _extract_variable_type(self, var_node) -> Optional[str]:
        """Extract variable type from variable declaration."""
        for child in var_node.children:
            if child.type in ['type_expression', 'identifier']:
                return child.text.decode('utf8')
        return None
    
    def _extract_test_name(self, test_node) -> Optional[str]:
        """Extract test name from test declaration."""
        # Test name is usually in a string literal
        for child in test_node.children:
            if child.type == 'string_literal':
                return child.text.decode('utf8').strip('"\'')
        return None
    
    def _extract_import_path(self, import_node) -> Optional[str]:
        """Extract import path from @import call."""
        for child in self._walk_node(import_node):
            if child.type == 'string_literal':
                return child.text.decode('utf8').strip('"\'')
        return None
    
    def _extract_error_values(self, error_set_node) -> List[str]:
        """Extract error values from error set declaration."""
        errors = []
        
        for child in error_set_node.children:
            if child.type == 'error_set':
                for error_child in child.children:
                    if error_child.type == 'identifier':
                        errors.append(error_child.text.decode('utf8'))
        
        return errors