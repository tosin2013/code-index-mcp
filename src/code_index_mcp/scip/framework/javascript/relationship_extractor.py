"""JavaScript relationship extractor implementation."""

import re
from typing import Iterator, Dict, List
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..types import SCIPContext, Relationship
from ...core.relationship_types import InternalRelationshipType


class JavaScriptRelationshipExtractor(BaseRelationshipExtractor):
    """JavaScript-specific relationship extractor using regex-based analysis."""
    
    def extract_inheritance_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract inheritance relationships from JavaScript classes."""
        try:
            # ES6 class inheritance: class Child extends Parent
            class_extends_pattern = r'class\s+(\w+)\s+extends\s+(\w+)'
            
            for match in re.finditer(class_extends_pattern, context.content, re.MULTILINE):
                child_class = match.group(1)
                parent_class = match.group(2)
                
                child_symbol_id = self._create_class_symbol_id(child_class, context)
                parent_symbol_id = self._create_class_symbol_id(parent_class, context)
                
                yield Relationship(
                    source_symbol=child_symbol_id,
                    target_symbol=parent_symbol_id,
                    relationship_type=InternalRelationshipType.INHERITS
                )
                
            # Prototype inheritance: Object.setPrototypeOf or Object.create
            prototype_pattern = r'Object\.setPrototypeOf\s*\(\s*(\w+)\.prototype\s*,\s*(\w+)\.prototype\s*\)'
            
            for match in re.finditer(prototype_pattern, context.content, re.MULTILINE):
                child_obj = match.group(1)
                parent_obj = match.group(2)
                
                child_symbol_id = self._create_function_symbol_id(child_obj, context)
                parent_symbol_id = self._create_function_symbol_id(parent_obj, context)
                
                yield Relationship(
                    source_symbol=child_symbol_id,
                    target_symbol=parent_symbol_id,
                    relationship_type=InternalRelationshipType.INHERITS
                )
                
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_call_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract function/method call relationships."""
        try:
            # Function calls: functionName() or object.method()
            function_call_patterns = [
                r'(\w+)\s*\(',  # Direct function calls
                r'(\w+)\.(\w+)\s*\(',  # Method calls
                r'this\.(\w+)\s*\(',  # Method calls on this
                r'super\.(\w+)\s*\(',  # Super method calls
            ]
            
            # Find all function definitions first
            function_defs = self._extract_function_definitions(context.content)
            
            for func_name in function_defs:
                func_symbol_id = self._create_function_symbol_id(func_name, context)
                
                # Look for calls within this function
                func_body = self._extract_function_body(context.content, func_name)
                if func_body:
                    for pattern in function_call_patterns:
                        for match in re.finditer(pattern, func_body, re.MULTILINE):
                            if pattern == r'(\w+)\.(\w+)\s*\(':
                                # Method call
                                target_function = match.group(2)
                            elif pattern == r'this\.(\w+)\s*\(' or pattern == r'super\.(\w+)\s*\(':
                                target_function = match.group(1)
                            else:
                                # Direct function call
                                target_function = match.group(1)
                                
                            if target_function and target_function != func_name:
                                target_symbol_id = self._create_function_symbol_id(target_function, context)
                                yield Relationship(
                                    source_symbol=func_symbol_id,
                                    target_symbol=target_symbol_id,
                                    relationship_type=InternalRelationshipType.CALLS
                                )
                                
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_import_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract import/dependency relationships."""
        try:
            import_patterns = {
                'es6_import': r'import\s+(?:\{[^}]+\}\s+from\s+)?[\'"]([^\'"]+)[\'"]',
                'require': r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                'dynamic_import': r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                'export_from': r'export\s+(?:\{[^}]+\}\s+)?from\s+[\'"]([^\'"]+)[\'"]'
            }
            
            file_symbol_id = self._create_file_symbol_id(context.file_path)
            
            for pattern_type, pattern in import_patterns.items():
                for match in re.finditer(pattern, context.content, re.MULTILINE):
                    module_name = match.group(1)
                    
                    # Determine if it's a local or external module
                    if module_name.startswith('.'):
                        # Local module
                        module_symbol_id = f"local {module_name}"
                    else:
                        # External module (npm package)
                        module_symbol_id = f"npm {module_name}"
                    
                    yield Relationship(
                        source_symbol=file_symbol_id,
                        target_symbol=module_symbol_id,
                        relationship_type=InternalRelationshipType.IMPORTS
                    )
                    
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_composition_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract composition relationships (object properties)."""
        try:
            # Class property definitions
            class_property_pattern = r'class\s+(\w+)\s*\{[^}]*?(\w+)\s*='
            
            for match in re.finditer(class_property_pattern, context.content, re.MULTILINE | re.DOTALL):
                class_name = match.group(1)
                property_name = match.group(2)
                
                class_symbol_id = self._create_class_symbol_id(class_name, context)
                property_symbol_id = self._create_property_symbol_id(property_name, class_symbol_id)
                
                yield Relationship(
                    source_symbol=class_symbol_id,
                    target_symbol=property_symbol_id,
                    relationship_type=InternalRelationshipType.CONTAINS
                )
                
            # Object literal properties
            object_literal_pattern = r'const\s+(\w+)\s*=\s*\{[^}]*?(\w+)\s*:'
            
            for match in re.finditer(object_literal_pattern, context.content, re.MULTILINE | re.DOTALL):
                object_name = match.group(1)
                property_name = match.group(2)
                
                object_symbol_id = self._create_variable_symbol_id(object_name, context)
                property_symbol_id = self._create_property_symbol_id(property_name, object_symbol_id)
                
                yield Relationship(
                    source_symbol=object_symbol_id,
                    target_symbol=property_symbol_id,
                    relationship_type=InternalRelationshipType.CONTAINS
                )
                
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_interface_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract interface relationships (TypeScript interfaces)."""
        try:
            # TypeScript interface implementation
            interface_impl_pattern = r'class\s+(\w+)\s+implements\s+([^{]+)'
            
            for match in re.finditer(interface_impl_pattern, context.content, re.MULTILINE):
                class_name = match.group(1)
                interfaces = match.group(2).strip()
                
                class_symbol_id = self._create_class_symbol_id(class_name, context)
                
                # Parse multiple interfaces
                for interface_name in re.findall(r'\w+', interfaces):
                    interface_symbol_id = self._create_interface_symbol_id(interface_name, context)
                    yield Relationship(
                        source_symbol=class_symbol_id,
                        target_symbol=interface_symbol_id,
                        relationship_type=InternalRelationshipType.IMPLEMENTS
                    )
                    
            # TypeScript interface extension
            interface_extends_pattern = r'interface\s+(\w+)\s+extends\s+([^{]+)'
            
            for match in re.finditer(interface_extends_pattern, context.content, re.MULTILINE):
                child_interface = match.group(1)
                parent_interfaces = match.group(2).strip()
                
                child_symbol_id = self._create_interface_symbol_id(child_interface, context)
                
                for parent_interface in re.findall(r'\w+', parent_interfaces):
                    parent_symbol_id = self._create_interface_symbol_id(parent_interface, context)
                    yield Relationship(
                        source_symbol=child_symbol_id,
                        target_symbol=parent_symbol_id,
                        relationship_type=InternalRelationshipType.INHERITS
                    )
                    
        except Exception:
            # Skip files with parsing errors
            return
    
    def _extract_function_definitions(self, content: str) -> List[str]:
        """Extract function definition names from content."""
        function_patterns = [
            r'function\s+(\w+)\s*\(',
            r'(?:const|let|var)\s+(\w+)\s*=\s*function',
            r'(?:const|let|var)\s+(\w+)\s*=\s*\([^)]*\)\s*=>',
            r'(\w+)\s*\([^)]*\)\s*\{',  # Method definitions
        ]
        
        functions = []
        for pattern in function_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                functions.append(match.group(1))
                
        return list(set(functions))  # Remove duplicates
    
    def _extract_function_body(self, content: str, func_name: str) -> str:
        """Extract the body of a specific function."""
        # Simple heuristic - find function and extract until matching brace
        func_pattern = rf'(?:function\s+{func_name}\s*\(|{func_name}\s*\([^)]*\)\s*=>|\b{func_name}\s*\([^)]*\)\s*{{)'
        
        match = re.search(func_pattern, content, re.MULTILINE)
        if match:
            start_pos = match.end()
            brace_count = 1
            i = start_pos
            
            while i < len(content) and brace_count > 0:
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                i += 1
                
            if brace_count == 0:
                return content[start_pos:i-1]
                
        return ""
    
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
    
    def _create_variable_symbol_id(self, variable_name: str, context: SCIPContext) -> str:
        """Create symbol ID for variable."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{variable_name}" if scope_path else variable_name
        return f"local {local_id}"
    
    def _create_property_symbol_id(self, property_name: str, parent_symbol_id: str) -> str:
        """Create symbol ID for property."""
        # Extract parent name from parent symbol ID
        parent_name = parent_symbol_id.replace("local ", "").rstrip("#().")
        return f"local {parent_name}.{property_name}"
    
    def _create_interface_symbol_id(self, interface_name: str, context: SCIPContext) -> str:
        """Create symbol ID for TypeScript interface."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{interface_name}" if scope_path else interface_name
        return f"local {local_id}#"
    
    def _create_file_symbol_id(self, file_path: str) -> str:
        """Create symbol ID for file."""
        return f"local {file_path}"