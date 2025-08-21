"""Python AST analyzer implementation."""

import ast
from typing import Iterator, Optional, Set, List, Dict, Any
from ..types import SCIPContext
from ..base.language_analyzer import BaseLanguageAnalyzer


class PythonASTAnalyzer(BaseLanguageAnalyzer):
    """Python AST analyzer for deep code analysis."""
    
    def __init__(self):
        """Initialize the AST analyzer."""
        self._processed_nodes: Set[int] = set()
        self._scope_stack: List[str] = []
        self._imports: Dict[str, str] = {}  # alias -> module mapping
    
    def parse(self, content: str, filename: str = "<unknown>") -> ast.AST:
        """Parse Python source code into AST."""
        try:
            return ast.parse(content, filename=filename)
        except SyntaxError as e:
            raise SyntaxError(f"Python syntax error in {filename}: {e}")
    
    def walk(self, tree: ast.AST) -> Iterator[ast.AST]:
        """Walk AST nodes, avoiding duplicates."""
        for node in ast.walk(tree):
            node_id = id(node)
            if node_id not in self._processed_nodes:
                self._processed_nodes.add(node_id)
                yield node
    
    def is_symbol_definition(self, node: ast.AST) -> bool:
        """Check if AST node represents a symbol definition."""
        return isinstance(node, (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.Assign,
            ast.AnnAssign,
            ast.AugAssign
        ))
    
    def is_symbol_reference(self, node: ast.AST) -> bool:
        """Check if AST node represents a symbol reference."""
        return isinstance(node, (
            ast.Name,
            ast.Attribute,
            ast.Call
        ))
    
    def get_symbol_name(self, node: ast.AST) -> Optional[str]:
        """Extract symbol name from AST node."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node.name
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Assign):
            # Handle simple assignments
            if len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    return target.id
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                return node.target.id
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                return node.target.id
        
        return None
    
    def get_node_position(self, node: ast.AST) -> tuple:
        """Get position information from AST node."""
        if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
            start_line = node.lineno - 1  # Convert to 0-based
            start_col = node.col_offset
            
            # Try to get end position
            if hasattr(node, 'end_lineno') and hasattr(node, 'end_col_offset'):
                end_line = node.end_lineno - 1
                end_col = node.end_col_offset
            else:
                # Estimate end position
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name_len = len(node.name)
                    end_line = start_line
                    end_col = start_col + name_len
                else:
                    end_line = start_line
                    end_col = start_col + 1
            
            return (start_line, start_col, end_line, end_col)
        
        return (0, 0, 0, 1)  # Default fallback
    
    def extract_decorators(self, node: ast.AST) -> List[str]:
        """Extract decorator names from function or class."""
        decorators = []
        if hasattr(node, 'decorator_list'):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorators.append(decorator.id)
                elif isinstance(decorator, ast.Attribute):
                    decorators.append(self._get_attribute_name(decorator))
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        decorators.append(decorator.func.id)
                    elif isinstance(decorator.func, ast.Attribute):
                        decorators.append(self._get_attribute_name(decorator.func))
        
        return decorators
    
    def extract_function_arguments(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """Extract function argument information."""
        arguments = []
        
        # Regular arguments
        for arg in node.args.args:
            arg_info = {
                'name': arg.arg,
                'type': 'regular',
                'annotation': self._get_annotation_string(arg.annotation) if arg.annotation else None
            }
            arguments.append(arg_info)
        
        # *args
        if node.args.vararg:
            arg_info = {
                'name': node.args.vararg.arg,
                'type': 'vararg',
                'annotation': self._get_annotation_string(node.args.vararg.annotation) if node.args.vararg.annotation else None
            }
            arguments.append(arg_info)
        
        # **kwargs  
        if node.args.kwarg:
            arg_info = {
                'name': node.args.kwarg.arg,
                'type': 'kwarg',
                'annotation': self._get_annotation_string(node.args.kwarg.annotation) if node.args.kwarg.annotation else None
            }
            arguments.append(arg_info)
        
        # Keyword-only arguments
        for arg in node.args.kwonlyargs:
            arg_info = {
                'name': arg.arg,
                'type': 'keyword_only',
                'annotation': self._get_annotation_string(arg.annotation) if arg.annotation else None
            }
            arguments.append(arg_info)
        
        return arguments
    
    def extract_class_bases(self, node: ast.ClassDef) -> List[str]:
        """Extract base class names."""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(self._get_attribute_name(base))
        
        return bases
    
    def extract_class_methods(self, node: ast.ClassDef) -> List[Dict[str, Any]]:
        """Extract class method information."""
        methods = []
        
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = {
                    'name': child.name,
                    'type': 'async_method' if isinstance(child, ast.AsyncFunctionDef) else 'method',
                    'decorators': self.extract_decorators(child),
                    'arguments': self.extract_function_arguments(child),
                    'is_property': 'property' in self.extract_decorators(child),
                    'is_static': 'staticmethod' in self.extract_decorators(child),
                    'is_class': 'classmethod' in self.extract_decorators(child),
                }
                methods.append(method_info)
        
        return methods
    
    def extract_imports(self, tree: ast.AST) -> Dict[str, str]:
        """Extract import statements and build alias mapping."""
        imports = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imports[name] = alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name
                        imports[name] = f"{node.module}.{alias.name}"
        
        return imports
    
    def analyze_scope_context(self, node: ast.AST, parent_scopes: List[str] = None) -> List[str]:
        """Analyze scope context for a node."""
        if parent_scopes is None:
            parent_scopes = []
        
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return parent_scopes + [node.name]
        
        return parent_scopes
    
    def find_variable_assignments(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Find all variable assignments in the AST."""
        assignments = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignment_info = {
                            'name': target.id,
                            'type': 'assignment',
                            'position': self.get_node_position(node),
                            'value_type': self._get_value_type(node.value)
                        }
                        assignments.append(assignment_info)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    assignment_info = {
                        'name': node.target.id,
                        'type': 'annotated_assignment',
                        'position': self.get_node_position(node),
                        'annotation': self._get_annotation_string(node.annotation),
                        'value_type': self._get_value_type(node.value) if node.value else None
                    }
                    assignments.append(assignment_info)
        
        return assignments
    
    def find_function_calls(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Find all function calls in the AST."""
        calls = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_info = {
                    'function': self._get_call_name(node),
                    'position': self.get_node_position(node),
                    'args_count': len(node.args),
                    'kwargs_count': len(node.keywords)
                }
                calls.append(call_info)
        
        return calls
    
    def _get_attribute_name(self, attr_node: ast.Attribute) -> str:
        """Get full attribute name (e.g., module.Class)."""
        parts = []
        current = attr_node
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.append(current.id)
        
        return ".".join(reversed(parts)) if parts else ""
    
    def _get_annotation_string(self, annotation: ast.AST) -> str:
        """Convert annotation AST to string."""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return self._get_attribute_name(annotation)
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        elif isinstance(annotation, ast.Str):  # Python < 3.8
            return annotation.s
        else:
            return str(type(annotation).__name__)
    
    def _get_value_type(self, value: ast.AST) -> str:
        """Get the type of a value expression."""
        if isinstance(value, ast.Constant):
            return type(value.value).__name__
        elif isinstance(value, (ast.Str, ast.Bytes)):  # Python < 3.8
            return type(value.s).__name__
        elif isinstance(value, ast.Num):  # Python < 3.8
            return type(value.n).__name__
        elif isinstance(value, ast.List):
            return "list"
        elif isinstance(value, ast.Dict):
            return "dict"
        elif isinstance(value, ast.Set):
            return "set"
        elif isinstance(value, ast.Tuple):
            return "tuple"
        elif isinstance(value, ast.Call):
            return self._get_call_name(value)
        else:
            return "unknown"
    
    def _get_call_name(self, call_node: ast.Call) -> str:
        """Get the name of a function call."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return self._get_attribute_name(call_node.func)
        else:
            return "unknown"