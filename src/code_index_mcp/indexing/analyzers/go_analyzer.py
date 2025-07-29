"""
Go code analyzer using regex patterns.

This module provides analysis of Go code, extracting functions, structs,
interfaces, and Go-specific features like goroutines and methods.
"""

import re
from typing import List, Dict, Any, Optional
from ..models import FileInfo, FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo
from .base import LanguageAnalyzer


class GoAnalyzer(LanguageAnalyzer):
    """Go analyzer using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.go']
    
    @property
    def language_name(self) -> str:
        return 'go'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Analyze Go code."""
        return self._safe_analyze(content, file_info)
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract function definitions from Go content."""
        functions = []
        
        # Pattern for function declarations
        func_pattern = r'func\s+(?:\([^)]*\)\s+)?(\w+)\s*\((.*?)\)(?:\s*\([^)]*\))?\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.search(func_pattern, line)
            if match:
                name = match.group(1)
                params_str = match.group(2)
                
                parameters = self._parse_go_parameters(params_str)
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                functions.append(FunctionInfo(
                    name=name,
                    parameters=parameters,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    is_async=False  # Go uses goroutines, not async/await
                ))
        
        return functions
    
    def extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract struct definitions from Go content (Go doesn't have classes)."""
        structs = []
        
        # Pattern for struct declarations
        struct_pattern = r'type\s+(\w+)\s+struct\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.search(struct_pattern, line)
            if match:
                name = match.group(1)
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                # Extract methods for this struct
                methods = self._extract_struct_methods(content, name)
                
                structs.append(ClassInfo(
                    name=name,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    methods=methods,
                    inherits_from=None  # Go uses composition, not inheritance
                ))
        
        return structs
    
    def extract_imports(self, content: str) -> List[ImportInfo]:
        """Extract import statements from Go content."""
        imports = []
        
        lines = content.splitlines()
        in_import_block = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Single import
            single_import_match = re.match(r'import\s+"(.+?)"', line)
            if single_import_match:
                module = single_import_match.group(1)
                imports.append(ImportInfo(
                    module=module,
                    imported_names=[],
                    import_type='import',
                    line_number=i + 1
                ))
                continue
            
            # Import block start
            if line == 'import (':
                in_import_block = True
                continue
            
            # Import block end
            if in_import_block and line == ')':
                in_import_block = False
                continue
            
            # Import within block
            if in_import_block:
                import_match = re.match(r'(?:(\w+)\s+)?"(.+?)"', line)
                if import_match:
                    alias = import_match.group(1)
                    module = import_match.group(2)
                    
                    imports.append(ImportInfo(
                        module=module,
                        imported_names=[alias] if alias else [],
                        import_type='import',
                        line_number=i + 1
                    ))
        
        return imports
    
    def get_language_specific_data(self, content: str) -> Dict[str, Any]:
        """Extract Go-specific features."""
        return {
            'struct_methods': self._extract_all_struct_methods(content),
            'interface_implementations': self._extract_interface_implementations(content),
            'goroutines': self._extract_goroutines(content)
        }
    
    def _parse_go_parameters(self, params_str: str) -> List[str]:
        """Parse Go function parameters."""
        if not params_str.strip():
            return []
        
        parameters = []
        
        # Go parameters can be: "name type" or "name1, name2 type"
        param_groups = params_str.split(',')
        
        for group in param_groups:
            group = group.strip()
            if group:
                # Split by whitespace to separate names from types
                parts = group.split()
                if len(parts) >= 2:
                    # Last part is type, everything before is parameter names
                    names = parts[:-1]
                    parameters.extend(names)
                elif len(parts) == 1:
                    # Could be just a type (anonymous parameter)
                    parameters.append(f"param_{len(parameters)}")
        
        return parameters
    
    def _extract_struct_methods(self, content: str, struct_name: str) -> List[str]:
        """Extract methods for a specific struct."""
        methods = []
        
        # Pattern for methods with receiver
        method_pattern = rf'func\s+\([^)]*{struct_name}[^)]*\)\s+(\w+)\s*\('
        
        for match in re.finditer(method_pattern, content):
            method_name = match.group(1)
            methods.append(method_name)
        
        return methods
    
    def _extract_all_struct_methods(self, content: str) -> Dict[str, List[str]]:
        """Extract all struct methods."""
        struct_methods = {}
        
        # Pattern for methods with receiver
        method_pattern = r'func\s+\([^)]*(\w+)[^)]*\)\s+(\w+)\s*\('
        
        for match in re.finditer(method_pattern, content):
            struct_name = match.group(1)
            method_name = match.group(2)
            
            if struct_name not in struct_methods:
                struct_methods[struct_name] = []
            struct_methods[struct_name].append(method_name)
        
        return struct_methods
    
    def _extract_interface_implementations(self, content: str) -> Dict[str, List[str]]:
        """Extract interface definitions."""
        interfaces = {}
        
        # Pattern for interface declarations
        interface_pattern = r'type\s+(\w+)\s+interface\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.search(interface_pattern, line)
            if match:
                interface_name = match.group(1)
                
                # Extract methods from interface
                methods = []
                j = i + 1
                brace_count = 1
                
                while j < len(lines) and brace_count > 0:
                    line = lines[j].strip()
                    
                    if '{' in line:
                        brace_count += line.count('{')
                    if '}' in line:
                        brace_count -= line.count('}')
                    
                    # Extract method signatures
                    method_match = re.match(r'(\w+)\s*\(', line)
                    if method_match and brace_count > 0:
                        methods.append(method_match.group(1))
                    
                    j += 1
                
                interfaces[interface_name] = methods
        
        return interfaces
    
    def _extract_goroutines(self, content: str) -> List[str]:
        """Extract goroutine calls."""
        goroutines = []
        
        # Pattern for goroutine calls
        pattern = r'go\s+(\w+)\s*\('
        
        for match in re.finditer(pattern, content):
            function_name = match.group(1)
            goroutines.append(function_name)
        
        return goroutines
    
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