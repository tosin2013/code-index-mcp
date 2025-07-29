"""
Python code analyzer using AST parsing.

This module provides comprehensive analysis of Python code, extracting functions,
classes, imports, and Python-specific features like decorators and async functions.
"""

import ast
import re
from typing import List, Dict, Any, Optional
from ..models import FileInfo, FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo
from .base import LanguageAnalyzer


class PythonAnalyzer(LanguageAnalyzer):
    """Python-specific code analyzer using AST parsing."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.py', '.pyw']
    
    @property
    def language_name(self) -> str:
        return 'python'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Analyze Python code using AST parsing."""
        try:
            tree = ast.parse(content)
            return self._extract_from_ast(tree, content, file_info)
        except SyntaxError as e:
            # Fall back to regex-based analysis for files with syntax errors
            return self._fallback_analysis(content, file_info, str(e))
        except Exception as e:
            # Use safe analysis for other errors
            return self._safe_analyze(content, file_info)
    
    def _extract_from_ast(self, tree: ast.AST, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Extract information from AST."""
        functions = []
        classes = []
        imports = []
        
        # Walk through all nodes in the AST
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = self._extract_function_from_node(node, content)
                if func_info:
                    functions.append(func_info)
            
            elif isinstance(node, ast.AsyncFunctionDef):
                func_info = self._extract_async_function_from_node(node, content)
                if func_info:
                    functions.append(func_info)
            
            elif isinstance(node, ast.ClassDef):
                class_info = self._extract_class_from_node(node, content)
                if class_info:
                    classes.append(class_info)
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_info = self._extract_import_from_node(node)
                if import_info:
                    imports.append(import_info)
        
        # Extract language-specific features
        language_specific = self._extract_python_specific_features(tree, content)
        
        return FileAnalysisResult(
            file_info=file_info,
            functions=functions,
            classes=classes,
            imports=imports,
            language_specific={'python': language_specific},
            analysis_errors=[]
        )
    
    def _extract_function_from_node(self, node: ast.FunctionDef, content: str) -> Optional[FunctionInfo]:
        """Extract function information from AST node."""
        try:
            # Get function parameters
            parameters = []
            for arg in node.args.args:
                parameters.append(arg.arg)
            
            # Add *args and **kwargs if present
            if node.args.vararg:
                parameters.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                parameters.append(f"**{node.args.kwarg.arg}")
            
            # Get line numbers
            line_start = node.lineno
            line_end = getattr(node, 'end_lineno', line_start)
            line_count = line_end - line_start + 1
            
            # Extract decorators
            decorators = []
            for decorator in node.decorator_list:
                decorators.append(self._get_decorator_name(decorator))
            
            return FunctionInfo(
                name=node.name,
                parameters=parameters,
                line_start=line_start,
                line_end=line_end,
                line_count=line_count,
                is_async=False,
                decorators=decorators
            )
        except Exception:
            return None
    
    def _extract_async_function_from_node(self, node: ast.AsyncFunctionDef, content: str) -> Optional[FunctionInfo]:
        """Extract async function information from AST node."""
        try:
            # Get function parameters
            parameters = []
            for arg in node.args.args:
                parameters.append(arg.arg)
            
            # Add *args and **kwargs if present
            if node.args.vararg:
                parameters.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                parameters.append(f"**{node.args.kwarg.arg}")
            
            # Get line numbers
            line_start = node.lineno
            line_end = getattr(node, 'end_lineno', line_start)
            line_count = line_end - line_start + 1
            
            # Extract decorators
            decorators = []
            for decorator in node.decorator_list:
                decorators.append(self._get_decorator_name(decorator))
            
            return FunctionInfo(
                name=node.name,
                parameters=parameters,
                line_start=line_start,
                line_end=line_end,
                line_count=line_count,
                is_async=True,
                decorators=decorators
            )
        except Exception:
            return None
    
    def _extract_class_from_node(self, node: ast.ClassDef, content: str) -> Optional[ClassInfo]:
        """Extract class information from AST node."""
        try:
            # Get line numbers
            line_start = node.lineno
            line_end = getattr(node, 'end_lineno', line_start)
            line_count = line_end - line_start + 1
            
            # Extract methods
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            
            # Extract base classes
            inherits_from = None
            if node.bases:
                # For simplicity, just take the first base class
                base = node.bases[0]
                if isinstance(base, ast.Name):
                    inherits_from = base.id
                elif isinstance(base, ast.Attribute):
                    inherits_from = self._get_attribute_name(base)
            
            return ClassInfo(
                name=node.name,
                line_start=line_start,
                line_end=line_end,
                line_count=line_count,
                methods=methods,
                inherits_from=inherits_from
            )
        except Exception:
            return None
    
    def _extract_import_from_node(self, node: ast.AST) -> Optional[ImportInfo]:
        """Extract import information from AST node."""
        try:
            if isinstance(node, ast.Import):
                # Handle: import module1, module2
                for alias in node.names:
                    return ImportInfo(
                        module=alias.name,
                        imported_names=[],
                        import_type='import',
                        line_number=node.lineno
                    )
            
            elif isinstance(node, ast.ImportFrom):
                # Handle: from module import name1, name2
                module = node.module or ''
                imported_names = []
                
                for alias in node.names:
                    imported_names.append(alias.name)
                
                return ImportInfo(
                    module=module,
                    imported_names=imported_names,
                    import_type='from',
                    line_number=node.lineno
                )
        except Exception:
            return None
    
    def _get_decorator_name(self, decorator: ast.AST) -> str:
        """Get decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return self._get_attribute_name(decorator)
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return f"{decorator.func.id}()"
            elif isinstance(decorator.func, ast.Attribute):
                return f"{self._get_attribute_name(decorator.func)}()"
        return str(decorator)
    
    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get full attribute name from AST node."""
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._get_attribute_name(node.value)}.{node.attr}"
        return node.attr
    
    def _extract_python_specific_features(self, tree: ast.AST, content: str) -> Dict[str, Any]:
        """Extract Python-specific features."""
        features = {
            'decorators': {},
            'async_functions': [],
            'class_inheritance': {}
        }
        
        for node in ast.walk(tree):
            # Collect decorators by function
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                decorators = [self._get_decorator_name(d) for d in node.decorator_list]
                features['decorators'][node.name] = decorators
            
            # Collect async functions
            if isinstance(node, ast.AsyncFunctionDef):
                features['async_functions'].append(node.name)
            
            # Collect class inheritance
            if isinstance(node, ast.ClassDef):
                inherits_from = None
                if node.bases:
                    base = node.bases[0]
                    if isinstance(base, ast.Name):
                        inherits_from = base.id
                    elif isinstance(base, ast.Attribute):
                        inherits_from = self._get_attribute_name(base)
                features['class_inheritance'][node.name] = inherits_from
        
        return features
    
    def _fallback_analysis(self, content: str, file_info: FileInfo, syntax_error: str) -> FileAnalysisResult:
        """Fallback to regex-based analysis when AST parsing fails."""
        functions = self._extract_functions_regex(content)
        classes = self._extract_classes_regex(content)
        imports = self._extract_imports_regex(content)
        
        return FileAnalysisResult(
            file_info=file_info,
            functions=functions,
            classes=classes,
            imports=imports,
            language_specific={'python': {}},
            analysis_errors=[f"AST parsing failed: {syntax_error}, used regex fallback"]
        )
    
    def _extract_functions_regex(self, content: str) -> List[FunctionInfo]:
        """Extract functions using regex patterns."""
        functions = []
        
        # Pattern for function definitions
        func_pattern = r'^(\s*)(async\s+)?def\s+(\w+)\s*\((.*?)\):'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.match(func_pattern, line)
            if match:
                indent, is_async, name, params = match.groups()
                
                # Parse parameters
                parameters = []
                if params.strip():
                    param_list = [p.strip() for p in params.split(',')]
                    parameters = [p.split('=')[0].strip() for p in param_list if p.strip()]
                
                # Estimate function end (simple heuristic)
                line_start = i + 1
                line_end = self._find_function_end(lines, i, len(indent))
                
                functions.append(FunctionInfo(
                    name=name,
                    parameters=parameters,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    is_async=bool(is_async)
                ))
        
        return functions
    
    def _extract_classes_regex(self, content: str) -> List[ClassInfo]:
        """Extract classes using regex patterns."""
        classes = []
        
        # Pattern for class definitions
        class_pattern = r'^(\s*)class\s+(\w+)(?:\((.*?)\))?:'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.match(class_pattern, line)
            if match:
                indent, name, bases = match.groups()
                
                # Parse base classes
                inherits_from = None
                if bases and bases.strip():
                    base_list = [b.strip() for b in bases.split(',')]
                    if base_list:
                        inherits_from = base_list[0]
                
                # Estimate class end
                line_start = i + 1
                line_end = self._find_class_end(lines, i, len(indent))
                
                # Find methods (simple heuristic)
                methods = []
                for j in range(i + 1, min(line_end, len(lines))):
                    method_match = re.match(r'\s+def\s+(\w+)', lines[j])
                    if method_match:
                        methods.append(method_match.group(1))
                
                classes.append(ClassInfo(
                    name=name,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    methods=methods,
                    inherits_from=inherits_from
                ))
        
        return classes
    
    def _extract_imports_regex(self, content: str) -> List[ImportInfo]:
        """Extract imports using regex patterns."""
        imports = []
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Handle "import module" statements
            import_match = re.match(r'^import\s+(.+)', line)
            if import_match:
                modules = [m.strip() for m in import_match.group(1).split(',')]
                for module in modules:
                    imports.append(ImportInfo(
                        module=module.split(' as ')[0],  # Handle "import module as alias"
                        imported_names=[],
                        import_type='import',
                        line_number=i + 1
                    ))
            
            # Handle "from module import ..." statements
            from_match = re.match(r'^from\s+(.+?)\s+import\s+(.+)', line)
            if from_match:
                module = from_match.group(1)
                imports_str = from_match.group(2)
                
                # Parse imported names
                imported_names = []
                if imports_str.strip() != '*':
                    names = [n.strip() for n in imports_str.split(',')]
                    imported_names = [n.split(' as ')[0] for n in names]  # Handle aliases
                
                imports.append(ImportInfo(
                    module=module,
                    imported_names=imported_names,
                    import_type='from',
                    line_number=i + 1
                ))
        
        return imports
    
    def _find_function_end(self, lines: List[str], start_idx: int, base_indent: int) -> int:
        """Find the end line of a function using indentation."""
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if line.strip() == '':
                continue
            
            # If we find a line with same or less indentation, function ends
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= base_indent and line.strip():
                return i
        
        return len(lines)
    
    def _find_class_end(self, lines: List[str], start_idx: int, base_indent: int) -> int:
        """Find the end line of a class using indentation."""
        return self._find_function_end(lines, start_idx, base_indent)