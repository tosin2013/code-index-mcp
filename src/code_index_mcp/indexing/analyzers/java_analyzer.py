"""
Java code analyzer using regex patterns.

This module provides analysis of Java code, extracting classes, methods,
imports, and Java-specific features like annotations and interfaces.
"""

import re
from typing import List, Dict, Any, Optional
from ..models import FileInfo, FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo
from .base import LanguageAnalyzer


class JavaAnalyzer(LanguageAnalyzer):
    """Java analyzer using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.java']
    
    @property
    def language_name(self) -> str:
        return 'java'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Analyze Java code."""
        return self._safe_analyze(content, file_info)
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract method definitions from Java content."""
        functions = []
        
        # Pattern for method declarations
        method_pattern = r'(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*\((.*?)\)\s*(?:throws\s+[\w\s,]+)?\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            # Skip comments and annotations
            if line.strip().startswith('//') or line.strip().startswith('@'):
                continue
                
            match = re.search(method_pattern, line)
            if match:
                name = match.group(1)
                params_str = match.group(2)
                
                # Skip constructors (same name as class)
                if self._is_constructor(name, content):
                    continue
                
                parameters = self._parse_java_parameters(params_str)
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                functions.append(FunctionInfo(
                    name=name,
                    parameters=parameters,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    is_async=False  # Java doesn't have async/await like JS/Python
                ))
        
        return functions
    
    def extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract class definitions from Java content."""
        classes = []
        
        # Pattern for class declarations
        class_pattern = r'(?:public|private|protected)?\s*(?:abstract)?\s*(?:final)?\s*class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+[\w\s,]+)?\s*\{'
        
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
        """Extract import statements from Java content."""
        imports = []
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Java import statements
            import_match = re.match(r'import\s+(?:static\s+)?(.+?);', line)
            if import_match:
                import_path = import_match.group(1)
                
                # Extract class name from import path
                if '.' in import_path:
                    parts = import_path.split('.')
                    module = '.'.join(parts[:-1])
                    imported_name = parts[-1]
                else:
                    module = import_path
                    imported_name = import_path
                
                imports.append(ImportInfo(
                    module=module,
                    imported_names=[imported_name] if imported_name != '*' else [],
                    import_type='import',
                    line_number=i + 1
                ))
        
        return imports
    
    def get_language_specific_data(self, content: str) -> Dict[str, Any]:
        """Extract Java-specific features."""
        return {
            'annotations': self._extract_annotations(content),
            'interface_implementations': self._extract_interface_implementations(content),
            'package_imports': self._extract_package_imports(content)
        }
    
    def _parse_java_parameters(self, params_str: str) -> List[str]:
        """Parse Java method parameters."""
        if not params_str.strip():
            return []
        
        parameters = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Java parameters have type and name: "String name"
                parts = param.split()
                if len(parts) >= 2:
                    param_name = parts[-1]  # Last part is the parameter name
                    parameters.append(param_name)
        
        return parameters
    
    def _is_constructor(self, method_name: str, content: str) -> bool:
        """Check if method is a constructor by comparing with class name."""
        class_pattern = r'class\s+(\w+)'
        match = re.search(class_pattern, content)
        if match:
            class_name = match.group(1)
            return method_name == class_name
        return False
    
    def _extract_class_methods(self, lines: List[str], class_start: int, class_end: int) -> List[str]:
        """Extract method names from a class definition."""
        methods = []
        
        method_pattern = r'(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*\('
        
        for i in range(class_start + 1, min(class_end, len(lines))):
            line = lines[i].strip()
            
            if line.startswith('//') or line.startswith('*') or line.startswith('@'):
                continue
            
            match = re.search(method_pattern, line)
            if match:
                method_name = match.group(1)
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
    
    def _extract_annotations(self, content: str) -> Dict[str, List[str]]:
        """Extract Java annotations."""
        annotations = {}
        
        lines = content.splitlines()
        current_annotations = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check for annotation
            if line.startswith('@'):
                annotation = line[1:].split('(')[0]  # Remove parameters
                current_annotations.append(annotation)
            
            # Check for method/class after annotations
            elif current_annotations:
                method_match = re.search(r'(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*\(', line)
                if method_match:
                    method_name = method_match.group(1)
                    annotations[method_name] = current_annotations.copy()
                    current_annotations = []
                elif not line or line.startswith('//'):
                    continue  # Skip empty lines and comments
                else:
                    current_annotations = []  # Reset if we hit something else
        
        return annotations
    
    def _extract_interface_implementations(self, content: str) -> Dict[str, List[str]]:
        """Extract interface implementations."""
        implementations = {}
        
        # Pattern for class implementing interfaces
        pattern = r'class\s+(\w+)(?:\s+extends\s+\w+)?\s+implements\s+([\w\s,]+)'
        
        for match in re.finditer(pattern, content):
            class_name = match.group(1)
            interfaces_str = match.group(2)
            
            interfaces = [iface.strip() for iface in interfaces_str.split(',')]
            implementations[class_name] = interfaces
        
        return implementations
    
    def _extract_package_imports(self, content: str) -> List[str]:
        """Extract package import statements."""
        imports = []
        
        pattern = r'import\s+(?:static\s+)?(.+?);'
        for match in re.finditer(pattern, content):
            imports.append(match.group(1))
        
        return imports