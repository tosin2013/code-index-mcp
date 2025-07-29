"""
JavaScript/TypeScript code analyzer using regex patterns.

This module provides analysis of JavaScript and TypeScript code, extracting functions,
classes, imports/exports, and JavaScript-specific features like arrow functions.
"""

import re
from typing import List, Dict, Any, Optional
from ..models import FileInfo, FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo
from .base import LanguageAnalyzer


class JavaScriptAnalyzer(LanguageAnalyzer):
    """JavaScript/TypeScript analyzer using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
    
    @property
    def language_name(self) -> str:
        return 'javascript'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Analyze JavaScript/TypeScript code."""
        return self._safe_analyze(content, file_info)
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract function definitions from JavaScript/TypeScript content."""
        functions = []
        
        # Extract regular functions
        functions.extend(self._extract_regular_functions(content))
        
        # Extract arrow functions
        functions.extend(self._extract_arrow_functions(content))
        
        # Extract async functions
        functions.extend(self._extract_async_functions(content))
        
        return functions
    
    def extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract class definitions from JavaScript/TypeScript content."""
        classes = []
        
        # Pattern for class definitions (supports dotted inheritance like React.Component)
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+([\w.]+))?\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.search(class_pattern, line)
            if match:
                name = match.group(1)
                inherits_from = match.group(2)
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                # Extract methods
                methods = self._extract_class_methods(lines, i, line_end)
                
                classes.append(ClassInfo(
                    name=name,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    methods=methods,
                    inherits_from=inherits_from
                ))
        
        return classes
    
    def extract_imports(self, content: str) -> List[ImportInfo]:
        """Extract import/export statements from JavaScript/TypeScript content."""
        imports = []
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            
            # ES6 import statements
            import_match = re.match(r'import\s+(.+?)\s+from\s+[\'"](.+?)[\'"]', line)
            if import_match:
                imports_str = import_match.group(1)
                module = import_match.group(2)
                
                imported_names = self._parse_import_names(imports_str)
                
                imports.append(ImportInfo(
                    module=module,
                    imported_names=imported_names,
                    import_type='es6',
                    line_number=i + 1
                ))
            
            # CommonJS require statements
            require_match = re.match(r'(?:const|let|var)\s+(.+?)\s*=\s*require\([\'"](.+?)[\'"]\)', line)
            if require_match:
                imports_str = require_match.group(1)
                module = require_match.group(2)
                
                imported_names = self._parse_require_names(imports_str)
                
                imports.append(ImportInfo(
                    module=module,
                    imported_names=imported_names,
                    import_type='commonjs',
                    line_number=i + 1
                ))
        
        return imports
    
    def get_language_specific_data(self, content: str) -> Dict[str, Any]:
        """Extract JavaScript-specific features."""
        return {
            'arrow_functions': self._extract_arrow_function_names(content),
            'async_functions': self._extract_async_function_names(content),
            'es6_exports': self._extract_es6_exports(content),
            'es6_imports': self._extract_es6_import_modules(content)
        }
    
    def _extract_regular_functions(self, content: str) -> List[FunctionInfo]:
        """Extract regular function declarations (excluding async functions)."""
        functions = []
        
        # Pattern for function declarations
        func_pattern = r'function\s+(\w+)\s*\((.*?)\)\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            # Skip lines that contain 'async function' (more robust check)
            if re.search(r'async\s+function', line):
                continue
                
            match = re.search(func_pattern, line)
            if match:
                name = match.group(1)
                params_str = match.group(2)
                
                parameters = self._parse_parameters(params_str)
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                functions.append(FunctionInfo(
                    name=name,
                    parameters=parameters,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    is_async=False
                ))
        
        return functions
    
    def _extract_arrow_functions(self, content: str) -> List[FunctionInfo]:
        """Extract arrow function definitions."""
        functions = []
        
        # Pattern for arrow functions assigned to variables
        arrow_pattern = r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\((.*?)\)\s*=>'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.search(arrow_pattern, line)
            if match:
                name = match.group(1)
                params_str = match.group(2)
                
                parameters = self._parse_parameters(params_str)
                is_async = 'async' in line
                
                # For arrow functions, estimate end based on semicolon or next statement
                line_start = i + 1
                line_end = self._find_arrow_function_end(lines, i)
                
                functions.append(FunctionInfo(
                    name=name,
                    parameters=parameters,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    is_async=is_async
                ))
        
        return functions
    
    def _extract_async_functions(self, content: str) -> List[FunctionInfo]:
        """Extract async function declarations."""
        functions = []
        
        # Pattern for async function declarations (more flexible whitespace handling)
        async_pattern = r'async\s+function\s+(\w+)\s*\((.*?)\)\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.search(async_pattern, line)
            if match:
                name = match.group(1)
                params_str = match.group(2)
                
                parameters = self._parse_parameters(params_str)
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                functions.append(FunctionInfo(
                    name=name,
                    parameters=parameters,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    is_async=True
                ))
        
        return functions
    
    def _extract_class_methods(self, lines: List[str], class_start: int, class_end: int) -> List[str]:
        """Extract method names from a class definition."""
        methods = []
        
        for i in range(class_start + 1, min(class_end, len(lines))):
            line = lines[i].strip()
            
            # Method pattern (including async methods)
            method_match = re.match(r'(?:async\s+)?(\w+)\s*\(', line)
            if method_match and not line.startswith('//'):
                method_name = method_match.group(1)
                # Skip common non-method patterns
                if method_name not in ['if', 'for', 'while', 'switch', 'catch']:
                    methods.append(method_name)
        
        return methods
    
    def _parse_parameters(self, params_str: str) -> List[str]:
        """Parse function parameters from parameter string."""
        if not params_str.strip():
            return []
        
        parameters = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Handle default parameters and destructuring (simplified)
                param_name = param.split('=')[0].strip()
                param_name = param_name.split(':')[0].strip()  # Remove TypeScript types
                if param_name and not param_name.startswith('...'):
                    parameters.append(param_name)
                elif param_name.startswith('...'):
                    parameters.append(param_name)
        
        return parameters
    
    def _parse_import_names(self, imports_str: str) -> List[str]:
        """Parse imported names from import statement."""
        imports_str = imports_str.strip()
        
        # Handle default import
        if not imports_str.startswith('{'):
            return [imports_str.split(' as ')[0].strip()]
        
        # Handle named imports
        if imports_str.startswith('{') and imports_str.endswith('}'):
            names_str = imports_str[1:-1]
            names = []
            for name in names_str.split(','):
                name = name.strip().split(' as ')[0].strip()
                if name:
                    names.append(name)
            return names
        
        return []
    
    def _parse_require_names(self, imports_str: str) -> List[str]:
        """Parse imported names from require statement."""
        imports_str = imports_str.strip()
        
        # Handle destructuring
        if imports_str.startswith('{') and imports_str.endswith('}'):
            names_str = imports_str[1:-1]
            names = []
            for name in names_str.split(','):
                name = name.strip()
                if name:
                    names.append(name)
            return names
        
        # Handle simple assignment
        return [imports_str]
    
    def _find_block_end(self, lines: List[str], start_idx: int, open_char: str, close_char: str) -> int:
        """Find the end of a block using brace matching."""
        brace_count = 0
        found_open = False
        
        for i in range(start_idx, len(lines)):
            line = lines[i]
            for char in line:
                if char == open_char:
                    brace_count += 1
                    found_open = True
                elif char == close_char:
                    brace_count -= 1
                    if found_open and brace_count == 0:
                        return i + 1
        
        return len(lines)
    
    def _find_arrow_function_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of an arrow function."""
        line = lines[start_idx]
        
        # If it's a single-line arrow function
        if ';' in line:
            return start_idx + 1
        
        # If it starts with a brace, find matching brace
        if '{' in line:
            return self._find_block_end(lines, start_idx, '{', '}')
        
        # Otherwise, assume it's a single expression
        return start_idx + 1
    
    def _extract_arrow_function_names(self, content: str) -> List[str]:
        """Extract names of arrow functions."""
        names = []
        pattern = r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(.*?\)\s*=>'
        for match in re.finditer(pattern, content):
            names.append(match.group(1))
        return names
    
    def _extract_async_function_names(self, content: str) -> List[str]:
        """Extract names of async functions."""
        names = []
        # Async function declarations
        pattern1 = r'async\s+function\s+(\w+)'
        for match in re.finditer(pattern1, content):
            names.append(match.group(1))
        
        # Async arrow functions
        pattern2 = r'(?:const|let|var)\s+(\w+)\s*=\s*async\s*\('
        for match in re.finditer(pattern2, content):
            names.append(match.group(1))
        
        return names
    
    def _extract_es6_exports(self, content: str) -> List[str]:
        """Extract ES6 export statements."""
        exports = []
        
        # Named exports
        pattern1 = r'export\s+(?:const|let|var|function|class)\s+(\w+)'
        for match in re.finditer(pattern1, content):
            exports.append(match.group(1))
        
        # Export lists
        pattern2 = r'export\s+\{([^}]+)\}'
        for match in re.finditer(pattern2, content):
            names = [name.strip() for name in match.group(1).split(',')]
            exports.extend(names)
        
        # Default exports
        if re.search(r'export\s+default', content):
            exports.append('default')
        
        return exports
    
    def _extract_es6_import_modules(self, content: str) -> List[str]:
        """Extract modules imported via ES6 imports."""
        modules = []
        pattern = r'import\s+.+?\s+from\s+[\'"](.+?)[\'"]'
        for match in re.finditer(pattern, content):
            modules.append(match.group(1))
        return modules