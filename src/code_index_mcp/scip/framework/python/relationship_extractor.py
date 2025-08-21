"""Python relationship extractor implementation."""

import ast
from typing import Iterator
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..types import SCIPContext, Relationship
from ...core.relationship_types import InternalRelationshipType


class PythonRelationshipExtractor(BaseRelationshipExtractor):
    """Python-specific relationship extractor using AST analysis."""
    
    def extract_inheritance_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract inheritance relationships from Python classes."""
        try:
            tree = ast.parse(context.content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_symbol_id = self._create_class_symbol_id(node.name, context)
                    
                    # Extract base classes
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            parent_symbol_id = self._create_class_symbol_id(base.id, context)
                            yield Relationship(
                                source_symbol=class_symbol_id,
                                target_symbol=parent_symbol_id,
                                relationship_type=InternalRelationshipType.INHERITS
                            )
                        elif isinstance(base, ast.Attribute):
                            # Handle module.ClassName inheritance
                            parent_name = self._get_attribute_name(base)
                            if parent_name:
                                parent_symbol_id = self._create_class_symbol_id(parent_name, context)
                                yield Relationship(
                                    source_symbol=class_symbol_id,
                                    target_symbol=parent_symbol_id,
                                    relationship_type=InternalRelationshipType.INHERITS
                                )
                                
        except SyntaxError:
            # Skip files with syntax errors
            return
    
    def extract_call_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract function/method call relationships."""
        try:
            tree = ast.parse(context.content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_symbol_id = self._create_function_symbol_id(node.name, context)
                    
                    # Find function calls within this function
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            target_function = self._extract_call_target(child)
                            if target_function:
                                target_symbol_id = self._create_function_symbol_id(target_function, context)
                                yield Relationship(
                                    source_symbol=function_symbol_id,
                                    target_symbol=target_symbol_id,
                                    relationship_type=InternalRelationshipType.CALLS
                                )
                                
        except SyntaxError:
            # Skip files with syntax errors
            return
    
    def extract_import_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract import/dependency relationships."""
        try:
            tree = ast.parse(context.content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_symbol_id = f"python-stdlib {alias.name}"
                        file_symbol_id = self._create_file_symbol_id(context.file_path)
                        
                        yield Relationship(
                            source_symbol=file_symbol_id,
                            target_symbol=module_symbol_id,
                            relationship_type=InternalRelationshipType.IMPORTS
                        )
                        
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_symbol_id = f"python-stdlib {node.module}"
                        file_symbol_id = self._create_file_symbol_id(context.file_path)
                        
                        yield Relationship(
                            source_symbol=file_symbol_id,
                            target_symbol=module_symbol_id,
                            relationship_type=InternalRelationshipType.IMPORTS
                        )
                        
        except SyntaxError:
            # Skip files with syntax errors
            return
    
    def extract_composition_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract composition relationships (class attributes)."""
        try:
            tree = ast.parse(context.content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_symbol_id = self._create_class_symbol_id(node.name, context)
                    
                    # Find attribute assignments in __init__ method
                    for child in ast.walk(node):
                        if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                            for assign_node in ast.walk(child):
                                if isinstance(assign_node, ast.Assign):
                                    for target in assign_node.targets:
                                        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                                            # This is a self.attribute assignment
                                            attribute_symbol_id = self._create_attribute_symbol_id(target.attr, class_symbol_id)
                                            yield Relationship(
                                                source_symbol=class_symbol_id,
                                                target_symbol=attribute_symbol_id,
                                                relationship_type=InternalRelationshipType.CONTAINS
                                            )
                                            
        except SyntaxError:
            # Skip files with syntax errors
            return
    
    def extract_interface_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract interface relationships (protocols, abstract base classes)."""
        try:
            tree = ast.parse(context.content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_symbol_id = self._create_class_symbol_id(node.name, context)
                    
                    # Check for abstract methods (indicating interface-like behavior)
                    has_abstract_methods = False
                    for child in ast.walk(node):
                        if isinstance(child, ast.FunctionDef):
                            # Check for @abstractmethod decorator
                            for decorator in child.decorator_list:
                                if isinstance(decorator, ast.Name) and decorator.id == "abstractmethod":
                                    has_abstract_methods = True
                                    break
                    
                    if has_abstract_methods:
                        # This class implements an interface pattern
                        interface_symbol_id = f"{class_symbol_id}_interface"
                        yield Relationship(
                            source_symbol=class_symbol_id,
                            target_symbol=interface_symbol_id,
                            relationship_type=InternalRelationshipType.IMPLEMENTS
                        )
                        
        except SyntaxError:
            # Skip files with syntax errors
            return
    
    def _create_class_symbol_id(self, class_name: str, context: SCIPContext) -> str:
        """Create symbol ID for class."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{class_name}" if scope_path else class_name
        return f"local {local_id}#"
    
    def _create_function_symbol_id(self, function_name: str, context: SCIPContext) -> str:
        """Create symbol ID for function."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{function_name}" if scope_path else function_name
        return f"local {local_id}()."
    
    def _create_attribute_symbol_id(self, attribute_name: str, class_symbol_id: str) -> str:
        """Create symbol ID for class attribute."""
        # Extract class name from class symbol ID
        class_name = class_symbol_id.replace("local ", "").replace("#", "")
        return f"local {class_name}.{attribute_name}"
    
    def _create_file_symbol_id(self, file_path: str) -> str:
        """Create symbol ID for file."""
        return f"local {file_path}"
    
    def _extract_call_target(self, call_node: ast.Call) -> str:
        """Extract the target function name from a call node."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        return None
    
    def _get_attribute_name(self, attr_node: ast.Attribute) -> str:
        """Get the full attribute name (e.g., module.Class)."""
        parts = []
        current = attr_node
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
            
        if isinstance(current, ast.Name):
            parts.append(current.id)
            
        return ".".join(reversed(parts)) if parts else None