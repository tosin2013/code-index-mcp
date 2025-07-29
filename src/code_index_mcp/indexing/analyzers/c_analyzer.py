"""
C code analyzer using regex patterns.

This module provides analysis of C code, extracting functions, structs,
and C-specific features like preprocessor directives and includes.
"""

import re
from typing import List, Dict, Any, Optional
from ..models import FileInfo, FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo
from .base import LanguageAnalyzer


class CAnalyzer(LanguageAnalyzer):
    """C analyzer using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.c', '.h']
    
    @property
    def language_name(self) -> str:
        return 'c'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Analyze C code."""
        return self._safe_analyze(content, file_info)
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract function definitions from C content."""
        functions = []
        
        # Pattern for function definitions (simplified)
        func_pattern = r'(?:^|\n)(?:static\s+)?(?:inline\s+)?(?:\w+\s+)*(\w+)\s*\((.*?)\)\s*\{'
        
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
                if name in ['if', 'for', 'while', 'switch', 'struct', 'enum', 'union']:
                    continue
                
                parameters = self._parse_c_parameters(params_str)
                
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
        """Extract struct definitions from C content."""
        structs = []
        
        # Pattern for struct declarations
        struct_pattern = r'(?:typedef\s+)?struct\s+(?:(\w+)\s+)?\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.search(struct_pattern, line)
            if match:
                name = match.group(1) or f"anonymous_struct_{i}"
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                structs.append(ClassInfo(
                    name=name,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    methods=[],  # C structs don't have methods
                    inherits_from=None
                ))
        
        return structs
    
    def extract_imports(self, content: str) -> List[ImportInfo]:
        """Extract #include statements from C content."""
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
        """Extract C-specific features."""
        return {
            'preprocessor_directives': self._extract_preprocessor_directives(content),
            'global_variables': self._extract_global_variables(content),
            'typedefs': self._extract_typedefs(content)
        }
    
    def _parse_c_parameters(self, params_str: str) -> List[str]:
        """Parse C function parameters."""
        if not params_str.strip() or params_str.strip() == 'void':
            return []
        
        parameters = []
        
        # Split by comma, but be careful with function pointers
        param_parts = self._split_c_parameters(params_str)
        
        for param in param_parts:
            param = param.strip()
            if param:
                # Extract parameter name (last word before array brackets or end)
                param = re.sub(r'\[.*?\]', '', param)  # Remove array brackets
                words = param.split()
                if words:
                    param_name = words[-1]
                    # Remove pointer asterisks
                    param_name = param_name.lstrip('*')
                    if param_name and param_name.isidentifier():
                        parameters.append(param_name)
        
        return parameters
    
    def _split_c_parameters(self, params_str: str) -> List[str]:
        """Split C parameters by comma, handling function pointers."""
        params = []
        current_param = ""
        paren_count = 0
        
        for char in params_str:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            elif char == ',' and paren_count == 0:
                params.append(current_param)
                current_param = ""
                continue
            
            current_param += char
        
        if current_param.strip():
            params.append(current_param)
        
        return params
    
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
    
    def _extract_preprocessor_directives(self, content: str) -> List[str]:
        """Extract preprocessor directives."""
        directives = []
        
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                directives.append(line)
        
        return directives
    
    def _extract_global_variables(self, content: str) -> List[str]:
        """Extract global variable declarations."""
        variables = []
        
        # Simple pattern for global variables (this is quite complex in C)
        # This is a simplified version
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            
            # Skip preprocessor, comments, and function definitions
            if (line.startswith('#') or line.startswith('//') or 
                line.startswith('/*') or '{' in line or '}' in line):
                continue
            
            # Look for variable declarations ending with semicolon
            if line.endswith(';') and '=' in line:
                # Very basic extraction
                parts = line.split('=')[0].strip().split()
                if len(parts) >= 2:
                    var_name = parts[-1].rstrip(';')
                    if var_name.isidentifier():
                        variables.append(var_name)
        
        return variables
    
    def _extract_typedefs(self, content: str) -> List[str]:
        """Extract typedef declarations."""
        typedefs = []
        
        # Pattern for typedef
        typedef_pattern = r'typedef\s+.+?\s+(\w+)\s*;'
        
        for match in re.finditer(typedef_pattern, content):
            typedef_name = match.group(1)
            typedefs.append(typedef_name)
        
        return typedefs