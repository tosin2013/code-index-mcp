"""Zig relationship extractor implementation."""

from typing import Iterator, Optional, List
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..types import SCIPContext, Relationship
from ...core.relationship_types import InternalRelationshipType

import tree_sitter
from tree_sitter_zig import language as zig_language


class ZigRelationshipExtractor(BaseRelationshipExtractor):
    """Zig-specific relationship extractor using tree-sitter analysis."""
    
    def __init__(self):
        """Initialize the Zig relationship extractor."""
        lang = tree_sitter.Language(zig_language())
        self.parser = tree_sitter.Parser(lang)
    
    def extract_inheritance_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract inheritance relationships from Zig (limited, as Zig doesn't have traditional inheritance)."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            # Zig doesn't have traditional inheritance, but we can extract composition relationships
            # where structs contain other struct types
            for node in self._walk_tree(tree.root_node):
                if node.type == 'struct_declaration':
                    struct_name = self._get_struct_name(node)
                    if not struct_name:
                        continue
                    
                    struct_symbol_id = self._create_struct_symbol_id(struct_name, context)
                    
                    # Look for embedded structs or type fields that reference other types
                    for field_node in self._walk_tree(node):
                        if field_node.type == 'container_field':
                            field_type = self._get_field_type(field_node, context.content)
                            if field_type and self._is_custom_type(field_type):
                                type_symbol_id = self._create_type_symbol_id(field_type, context)
                                yield Relationship(
                                    source_symbol=struct_symbol_id,
                                    target_symbol=type_symbol_id,
                                    relationship_type=InternalRelationshipType.CONTAINS
                                )
                            
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_call_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract function call relationships."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            for node in self._walk_tree(tree.root_node):
                if node.type == 'function_declaration':
                    function_name = self._get_function_name(node)
                    if not function_name:
                        continue
                    
                    function_symbol_id = self._create_function_symbol_id(function_name, context)
                    
                    # Find function calls within this function
                    for call_node in self._walk_tree(node):
                        if call_node.type == 'call_expression':
                            target_function = self._get_call_target(call_node, context.content)
                            if target_function and target_function != function_name:
                                target_symbol_id = self._create_function_symbol_id(target_function, context)
                                yield Relationship(
                                    source_symbol=function_symbol_id,
                                    target_symbol=target_symbol_id,
                                    relationship_type=InternalRelationshipType.CALLS
                                )
                        elif call_node.type == 'builtin_call_expr':
                            # Handle builtin functions like @import, @cInclude, etc.
                            builtin_name = self._get_builtin_name(call_node, context.content)
                            if builtin_name:
                                builtin_symbol_id = f"zig-builtin {builtin_name}"
                                yield Relationship(
                                    source_symbol=function_symbol_id,
                                    target_symbol=builtin_symbol_id,
                                    relationship_type=InternalRelationshipType.CALLS
                                )
                                
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_import_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract import/dependency relationships."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            file_symbol_id = self._create_file_symbol_id(context.file_path)
            
            for node in self._walk_tree(tree.root_node):
                if node.type == 'builtin_call_expr':
                    builtin_name = self._get_builtin_name(node, context.content)
                    if builtin_name in ['@import', '@cImport', '@cInclude']:
                        import_path = self._get_import_path(node, context.content)
                        if import_path:
                            # Determine if it's a standard library, C library, or local import
                            if import_path.startswith('std'):
                                module_symbol_id = f"zig-std {import_path}"
                            elif builtin_name in ['@cImport', '@cInclude']:
                                module_symbol_id = f"c-lib {import_path}"
                            elif import_path.startswith('./') or import_path.startswith('../'):
                                module_symbol_id = f"local {import_path}"
                            else:
                                module_symbol_id = f"zig-external {import_path}"
                            
                            yield Relationship(
                                source_symbol=file_symbol_id,
                                target_symbol=module_symbol_id,
                                relationship_type=InternalRelationshipType.IMPORTS
                            )
                            
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_composition_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract composition relationships (struct fields, union fields)."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            for node in self._walk_tree(tree.root_node):
                if node.type in ['struct_declaration', 'union_declaration']:
                    container_name = self._get_container_name(node)
                    if not container_name:
                        continue
                    
                    container_symbol_id = self._create_container_symbol_id(container_name, node.type, context)
                    
                    # Find fields in this container
                    for field_node in self._walk_tree(node):
                        if field_node.type == 'container_field':
                            field_name = self._get_field_name(field_node, context.content)
                            if field_name:
                                field_symbol_id = self._create_field_symbol_id(field_name, container_symbol_id)
                                yield Relationship(
                                    source_symbol=container_symbol_id,
                                    target_symbol=field_symbol_id,
                                    relationship_type=InternalRelationshipType.CONTAINS
                                )
                                
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_interface_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract interface relationships (Zig doesn't have interfaces, but has error sets and protocols)."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            for node in self._walk_tree(tree.root_node):
                if node.type == 'error_set_declaration':
                    error_set_name = self._get_error_set_name(node, context.content)
                    if not error_set_name:
                        continue
                    
                    error_set_symbol_id = self._create_error_set_symbol_id(error_set_name, context)
                    
                    # Find error values in this error set
                    for error_node in self._walk_tree(node):
                        if error_node.type == 'identifier':
                            error_name = self._get_node_text(error_node, context.content)
                            if error_name and error_name != error_set_name:
                                error_symbol_id = self._create_error_symbol_id(error_name, error_set_symbol_id)
                                yield Relationship(
                                    source_symbol=error_set_symbol_id,
                                    target_symbol=error_symbol_id,
                                    relationship_type=InternalRelationshipType.CONTAINS
                                )
                                
        except Exception:
            # Skip files with parsing errors
            return
    
    def _walk_tree(self, node) -> Iterator:
        """Walk tree-sitter tree nodes."""
        yield node
        for child in node.children:
            yield from self._walk_tree(child)
    
    def _get_node_text(self, node, content: str) -> str:
        """Get text content of a tree-sitter node."""
        return content[node.start_byte:node.end_byte]
    
    def _get_struct_name(self, struct_node) -> Optional[str]:
        """Extract struct name from struct declaration node."""
        for child in struct_node.children:
            if child.type == 'identifier':
                return child.text.decode('utf8')
        return None
    
    def _get_function_name(self, function_node) -> Optional[str]:
        """Extract function name from function declaration node."""
        for child in function_node.children:
            if child.type == 'identifier':
                return child.text.decode('utf8')
        return None
    
    def _get_container_name(self, container_node) -> Optional[str]:
        """Extract container name from struct/union declaration node."""
        for child in container_node.children:
            if child.type == 'identifier':
                return child.text.decode('utf8')
        return None
    
    def _get_field_name(self, field_node, content: str) -> Optional[str]:
        """Extract field name from container field node."""
        for child in field_node.children:
            if child.type == 'identifier':
                return self._get_node_text(child, content)
        return None
    
    def _get_field_type(self, field_node, content: str) -> Optional[str]:
        """Extract field type from container field node."""
        # Look for type information in the field
        for child in field_node.children:
            if child.type in ['type_expression', 'identifier']:
                return self._get_node_text(child, content)
        return None
    
    def _get_call_target(self, call_node, content: str) -> Optional[str]:
        """Extract target function name from call expression."""
        for child in call_node.children:
            if child.type == 'identifier':
                return self._get_node_text(child, content)
            elif child.type == 'field_expression':
                # Handle method calls like obj.method()
                for grandchild in child.children:
                    if grandchild.type == 'identifier':
                        return self._get_node_text(grandchild, content)
        return None
    
    def _get_builtin_name(self, builtin_node, content: str) -> Optional[str]:
        """Extract builtin function name from builtin call expression."""
        builtin_text = self._get_node_text(builtin_node, content)
        if builtin_text.startswith('@'):
            # Extract just the builtin name (e.g., "@import" from "@import(...)")
            paren_index = builtin_text.find('(')
            if paren_index > 0:
                return builtin_text[:paren_index]
            return builtin_text
        return None
    
    def _get_import_path(self, import_node, content: str) -> Optional[str]:
        """Extract import path from import expression."""
        # Look for string literal in the import call
        for child in self._walk_tree(import_node):
            if child.type == 'string_literal':
                path_text = self._get_node_text(child, content)
                # Remove quotes
                return path_text.strip('"\'')
        return None
    
    def _get_error_set_name(self, error_set_node, content: str) -> Optional[str]:
        """Extract error set name from error set declaration."""
        for child in error_set_node.children:
            if child.type == 'identifier':
                return self._get_node_text(child, content)
        return None
    
    def _is_custom_type(self, type_name: str) -> bool:
        """Check if a type name represents a custom type (not a builtin)."""
        builtin_types = {
            'i8', 'i16', 'i32', 'i64', 'i128',
            'u8', 'u16', 'u32', 'u64', 'u128',
            'f16', 'f32', 'f64', 'f128',
            'bool', 'void', 'noreturn', 'type',
            'anyerror', 'anyframe', 'anyopaque'
        }
        return type_name not in builtin_types and not type_name.startswith('*')
    
    def _create_struct_symbol_id(self, struct_name: str, context: SCIPContext) -> str:
        """Create symbol ID for struct."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{struct_name}" if scope_path else struct_name
        return f"local {local_id}#"
    
    def _create_function_symbol_id(self, function_name: str, context: SCIPContext) -> str:
        """Create symbol ID for function."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{function_name}" if scope_path else function_name
        return f"local {local_id}()."
    
    def _create_container_symbol_id(self, container_name: str, container_type: str, context: SCIPContext) -> str:
        """Create symbol ID for struct/union container."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{container_name}" if scope_path else container_name
        return f"local {local_id}#"
    
    def _create_type_symbol_id(self, type_name: str, context: SCIPContext) -> str:
        """Create symbol ID for type."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{type_name}" if scope_path else type_name
        return f"local {local_id}#"
    
    def _create_field_symbol_id(self, field_name: str, container_symbol_id: str) -> str:
        """Create symbol ID for field."""
        # Extract container name from container symbol ID
        container_name = container_symbol_id.replace("local ", "").replace("#", "")
        return f"local {container_name}.{field_name}"
    
    def _create_error_set_symbol_id(self, error_set_name: str, context: SCIPContext) -> str:
        """Create symbol ID for error set."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{error_set_name}" if scope_path else error_set_name
        return f"local {local_id}#"
    
    def _create_error_symbol_id(self, error_name: str, error_set_symbol_id: str) -> str:
        """Create symbol ID for error value."""
        # Extract error set name from error set symbol ID
        error_set_name = error_set_symbol_id.replace("local ", "").replace("#", "")
        return f"local {error_set_name}.{error_name}"
    
    def _create_file_symbol_id(self, file_path: str) -> str:
        """Create symbol ID for file."""
        return f"local {file_path}"