"""
C++ code analyzer using regex patterns.

This module provides analysis of C++ code, extracting classes, methods,
namespaces, and C++-specific features like templates and inheritance.
"""

import re
from typing import List, Dict, Any, Optional
from ..models import FileInfo, FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo
from .base import LanguageAnalyzer


class CppAnalyzer(LanguageAnalyzer):
    """C++ analyzer using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.cpp', '.cxx', '.cc', '.hpp', '.hxx', '.hh']
    
    @property
    def language_name(self) -> str:
        return 'cpp'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Analyze C++ code."""
        return self._safe_analyze(content, file_info)
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract function definitions from C++ content."""
        functions = []
        
        # Pattern for function definitions
        func_pattern = r'(?:^|\n)(?:(?:inline|static|virtual|explicit)\s+)*(?:template\s*<[^>]*>\s+)?(?:\w+(?:::\w+)*(?:<[^>]*>)?\s+)*(\w+)\s*\((.*?)\)\s*(?:const)?\s*(?:override)?\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            # Skip preprocessor directives and comments
            if line.strip().startswith('#') or line.strip().startswith('//'):
                continue
            
            match = re.search(func_pattern, line)
            if match:
                name = match.group(1)
                params_str = match.group(2)
                
                # Skip common non-function patterns
                if name in ['if', 'for', 'while', 'switch', 'class', 'struct', 'namespace']:
                    continue
                
                parameters = self._parse_cpp_parameters(params_str)
                
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
    
    def extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract class definitions from C++ content."""
        classes = []
        
        # Pattern for class declarations
        class_pattern = r'(?:template\s*<[^>]*>\s+)?class\s+(\w+)(?:\s*:\s*(?:public|private|protected)\s+(\w+(?:::\w+)*))?\s*\{'
        
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
        """Extract #include statements from C++ content."""
        imports = []
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            
            # #include statements
            include_match = re.match(r'#include\s+[<"](.+?)[>"]', line)
            if include_match:
                header = include_match.group(1)
                
                imports.append(ImportInfo(
                    module=header,
                    imported_names=[],
                    import_type='include',
                    line_number=i + 1
                ))
        
        return imports
    
    def get_language_specific_data(self, content: str) -> Dict[str, Any]:
        """Extract C++-specific features."""
        return {
            'namespaces': self._extract_namespaces(content),
            'templates': self._extract_templates(content),
            'inheritance': self._extract_inheritance_relationships(content),
            'operator_overloads': self._extract_operator_overloads(content)
        }
    
    def _parse_cpp_parameters(self, params_str: str) -> List[str]:
        """Parse C++ function parameters."""
        if not params_str.strip() or params_str.strip() == 'void':
            return []
        
        parameters = []
        
        # Split by comma, handling templates and function pointers
        param_parts = self._split_cpp_parameters(params_str)
        
        for param in param_parts:
            param = param.strip()
            if param:
                # Remove default values
                param = param.split('=')[0].strip()
                
                # Extract parameter name
                param = re.sub(r'\[.*?\]', '', param)  # Remove array brackets
                
                # Handle references and pointers
                words = param.split()
                if words:
                    param_name = words[-1]
                    # Remove pointer/reference symbols
                    param_name = param_name.lstrip('*&')
                    if param_name and param_name.isidentifier():
                        parameters.append(param_name)
        
        return parameters
    
    def _split_cpp_parameters(self, params_str: str) -> List[str]:
        """Split C++ parameters by comma, handling templates and function pointers."""
        params = []
        current_param = ""
        paren_count = 0
        angle_count = 0
        
        for char in params_str:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            elif char == '<':
                angle_count += 1
            elif char == '>':
                angle_count -= 1
            elif char == ',' and paren_count == 0 and angle_count == 0:
                params.append(current_param)
                current_param = ""
                continue
            
            current_param += char
        
        if current_param.strip():
            params.append(current_param)
        
        return params
    
    def _extract_class_methods(self, lines: List[str], class_start: int, class_end: int) -> List[str]:
        """Extract method names from a class definition."""
        methods = []
        
        # Pattern for method declarations
        method_pattern = r'(?:(?:public|private|protected):\s*)?(?:(?:virtual|static|inline)\s+)*(?:\w+(?:::\w+)*(?:<[^>]*>)?\s+)*(\w+)\s*\('
        
        for i in range(class_start + 1, min(class_end, len(lines))):
            line = lines[i].strip()
            
            # Skip comments and access specifiers
            if (line.startswith('//') or line.startswith('/*') or 
                line.endswith(':') or not line):
                continue
            
            match = re.search(method_pattern, line)
            if match:
                method_name = match.group(1)
                # Skip constructors and destructors (same name as class)
                if not method_name.startswith('~'):
                    methods.append(method_name)
        
        return methods
    
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
    
    def _extract_namespaces(self, content: str) -> List[str]:
        """Extract namespace declarations."""
        namespaces = []
        
        # Pattern for namespace declarations
        namespace_pattern = r'namespace\s+(\w+)\s*\{'
        
        for match in re.finditer(namespace_pattern, content):
            namespace_name = match.group(1)
            namespaces.append(namespace_name)
        
        return namespaces
    
    def _extract_templates(self, content: str) -> List[str]:
        """Extract template declarations."""
        templates = []
        
        # Pattern for template declarations
        template_pattern = r'template\s*<([^>]*)>\s*(?:class|struct)\s+(\w+)'
        
        for match in re.finditer(template_pattern, content):
            template_params = match.group(1)
            class_name = match.group(2)
            templates.append(f"{class_name}<{template_params}>")
        
        return templates
    
    def _extract_inheritance_relationships(self, content: str) -> Dict[str, List[str]]:
        """Extract class inheritance relationships."""
        inheritance = {}
        
        # Pattern for class inheritance
        inheritance_pattern = r'class\s+(\w+)\s*:\s*((?:(?:public|private|protected)\s+\w+(?:::\w+)*(?:\s*,\s*)?)+)'
        
        for match in re.finditer(inheritance_pattern, content):
            class_name = match.group(1)
            bases_str = match.group(2)
            
            # Parse base classes
            bases = []
            for base in bases_str.split(','):
                base = base.strip()
                # Remove access specifiers
                base = re.sub(r'^(?:public|private|protected)\s+', '', base)
                if base:
                    bases.append(base)
            
            inheritance[class_name] = bases
        
        return inheritance
    
    def _extract_operator_overloads(self, content: str) -> List[str]:
        """Extract operator overload declarations."""
        operators = []
        
        # Pattern for operator overloads
        operator_pattern = r'operator\s*([+\-*/%=<>!&|^~\[\]()]+)\s*\('
        
        for match in re.finditer(operator_pattern, content):
            operator = match.group(1)
            operators.append(operator)
        
        return operators