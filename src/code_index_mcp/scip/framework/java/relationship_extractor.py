"""Java relationship extractor implementation."""

from typing import Iterator, Optional, List
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..types import SCIPContext, Relationship
from ...core.relationship_types import InternalRelationshipType

try:
    import tree_sitter
    from tree_sitter_java import language as java_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class JavaRelationshipExtractor(BaseRelationshipExtractor):
    """Java-specific relationship extractor using tree-sitter analysis."""
    
    def __init__(self):
        """Initialize the Java relationship extractor."""
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("Tree-sitter Java library not available")
        
        java_lang = tree_sitter.Language(java_language())
        self.parser = tree_sitter.Parser(java_lang)
    
    def extract_inheritance_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract inheritance relationships from Java classes."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            for node in self._walk_tree(tree.root_node):
                if node.type == 'class_declaration':
                    class_name = self._get_class_name(node)
                    if not class_name:
                        continue
                    
                    class_symbol_id = self._create_class_symbol_id(class_name, context)
                    
                    # Look for extends clause
                    extends_node = self._find_child_by_type(node, 'superclass')
                    if extends_node:
                        parent_type = self._find_child_by_type(extends_node, 'type_identifier')
                        if parent_type:
                            parent_name = self._get_node_text(parent_type, context.content)
                            parent_symbol_id = self._create_class_symbol_id(parent_name, context)
                            yield Relationship(
                                source_symbol=class_symbol_id,
                                target_symbol=parent_symbol_id,
                                relationship_type=InternalRelationshipType.INHERITS
                            )
                            
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_call_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract method call relationships."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            for node in self._walk_tree(tree.root_node):
                if node.type == 'method_declaration':
                    method_name = self._get_method_name(node)
                    if not method_name:
                        continue
                    
                    method_symbol_id = self._create_method_symbol_id(method_name, context)
                    
                    # Find method invocations within this method
                    for call_node in self._walk_tree(node):
                        if call_node.type == 'method_invocation':
                            target_method = self._get_invocation_target(call_node, context.content)
                            if target_method and target_method != method_name:
                                target_symbol_id = self._create_method_symbol_id(target_method, context)
                                yield Relationship(
                                    source_symbol=method_symbol_id,
                                    target_symbol=target_symbol_id,
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
                if node.type == 'import_declaration':
                    import_path = self._get_import_path(node, context.content)
                    if import_path:
                        # Determine if it's a standard library or external dependency
                        if import_path.startswith('java.') or import_path.startswith('javax.'):
                            module_symbol_id = f"java-stdlib {import_path}"
                        else:
                            module_symbol_id = f"java-external {import_path}"
                        
                        yield Relationship(
                            source_symbol=file_symbol_id,
                            target_symbol=module_symbol_id,
                            relationship_type=InternalRelationshipType.IMPORTS
                        )
                        
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_composition_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract composition relationships (class fields)."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            for node in self._walk_tree(tree.root_node):
                if node.type == 'class_declaration':
                    class_name = self._get_class_name(node)
                    if not class_name:
                        continue
                    
                    class_symbol_id = self._create_class_symbol_id(class_name, context)
                    
                    # Find field declarations in this class
                    for field_node in self._walk_tree(node):
                        if field_node.type == 'field_declaration':
                            field_name = self._get_field_name(field_node, context.content)
                            if field_name:
                                field_symbol_id = self._create_field_symbol_id(field_name, class_symbol_id)
                                yield Relationship(
                                    source_symbol=class_symbol_id,
                                    target_symbol=field_symbol_id,
                                    relationship_type=InternalRelationshipType.CONTAINS
                                )
                                
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_interface_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract interface implementation relationships."""
        try:
            tree = self.parser.parse(bytes(context.content, 'utf8'))
            
            for node in self._walk_tree(tree.root_node):
                if node.type == 'class_declaration':
                    class_name = self._get_class_name(node)
                    if not class_name:
                        continue
                    
                    class_symbol_id = self._create_class_symbol_id(class_name, context)
                    
                    # Look for implements clause
                    implements_node = self._find_child_by_type(node, 'super_interfaces')
                    if implements_node:
                        for interface_node in self._find_children_by_type(implements_node, 'type_identifier'):
                            interface_name = self._get_node_text(interface_node, context.content)
                            interface_symbol_id = self._create_interface_symbol_id(interface_name, context)
                            yield Relationship(
                                source_symbol=class_symbol_id,
                                target_symbol=interface_symbol_id,
                                relationship_type=InternalRelationshipType.IMPLEMENTS
                            )
                            
                elif node.type == 'interface_declaration':
                    interface_name = self._get_interface_name(node, context.content)
                    if not interface_name:
                        continue
                    
                    interface_symbol_id = self._create_interface_symbol_id(interface_name, context)
                    
                    # Look for extends clause in interface
                    extends_node = self._find_child_by_type(node, 'extends_interfaces')
                    if extends_node:
                        for parent_interface_node in self._find_children_by_type(extends_node, 'type_identifier'):
                            parent_interface_name = self._get_node_text(parent_interface_node, context.content)
                            parent_symbol_id = self._create_interface_symbol_id(parent_interface_name, context)
                            yield Relationship(
                                source_symbol=interface_symbol_id,
                                target_symbol=parent_symbol_id,
                                relationship_type=InternalRelationshipType.INHERITS
                            )
                            
        except Exception:
            # Skip files with parsing errors
            return
    
    def _walk_tree(self, node) -> Iterator:
        """Walk tree-sitter tree nodes."""
        yield node
        for child in node.children:
            yield from self._walk_tree(child)
    
    def _find_child_by_type(self, node, node_type: str):
        """Find first child node of specified type."""
        for child in node.children:
            if child.type == node_type:
                return child
        return None
    
    def _find_children_by_type(self, node, node_type: str) -> List:
        """Find all child nodes of specified type."""
        children = []
        for child in node.children:
            if child.type == node_type:
                children.append(child)
        return children
    
    def _get_node_text(self, node, content: str) -> str:
        """Get text content of a tree-sitter node."""
        return content[node.start_byte:node.end_byte]
    
    def _get_class_name(self, class_node) -> Optional[str]:
        """Extract class name from class declaration node."""
        identifier_node = self._find_child_by_type(class_node, 'identifier')
        if identifier_node:
            return identifier_node.text.decode('utf8')
        return None
    
    def _get_method_name(self, method_node) -> Optional[str]:
        """Extract method name from method declaration node."""
        identifier_node = self._find_child_by_type(method_node, 'identifier')
        if identifier_node:
            return identifier_node.text.decode('utf8')
        return None
    
    def _get_interface_name(self, interface_node, content: str) -> Optional[str]:
        """Extract interface name from interface declaration node."""
        identifier_node = self._find_child_by_type(interface_node, 'identifier')
        if identifier_node:
            return self._get_node_text(identifier_node, content)
        return None
    
    def _get_field_name(self, field_node, content: str) -> Optional[str]:
        """Extract field name from field declaration node."""
        # Field declarations can have multiple declarators
        declarator = self._find_child_by_type(field_node, 'variable_declarator')
        if declarator:
            identifier = self._find_child_by_type(declarator, 'identifier')
            if identifier:
                return self._get_node_text(identifier, content)
        return None
    
    def _get_import_path(self, import_node, content: str) -> Optional[str]:
        """Extract import path from import declaration."""
        # Look for scoped_identifier or identifier in import
        for child in import_node.children:
            if child.type in ['scoped_identifier', 'identifier']:
                return self._get_node_text(child, content)
        return None
    
    def _get_invocation_target(self, invocation_node, content: str) -> Optional[str]:
        """Extract target method name from method invocation."""
        identifier_node = self._find_child_by_type(invocation_node, 'identifier')
        if identifier_node:
            return self._get_node_text(identifier_node, content)
        
        # Handle method calls like object.method()
        field_access = self._find_child_by_type(invocation_node, 'field_access')
        if field_access:
            identifier = self._find_child_by_type(field_access, 'identifier')
            if identifier:
                return self._get_node_text(identifier, content)
        
        return None
    
    def _create_class_symbol_id(self, class_name: str, context: SCIPContext) -> str:
        """Create symbol ID for class."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{class_name}" if scope_path else class_name
        return f"local {local_id}#"
    
    def _create_method_symbol_id(self, method_name: str, context: SCIPContext) -> str:
        """Create symbol ID for method."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{method_name}" if scope_path else method_name
        return f"local {local_id}()."
    
    def _create_interface_symbol_id(self, interface_name: str, context: SCIPContext) -> str:
        """Create symbol ID for interface."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{interface_name}" if scope_path else interface_name
        return f"local {local_id}#"
    
    def _create_field_symbol_id(self, field_name: str, class_symbol_id: str) -> str:
        """Create symbol ID for field."""
        # Extract class name from class symbol ID
        class_name = class_symbol_id.replace("local ", "").replace("#", "")
        return f"local {class_name}.{field_name}"
    
    def _create_file_symbol_id(self, file_path: str) -> str:
        """Create symbol ID for file."""
        return f"local {file_path}"