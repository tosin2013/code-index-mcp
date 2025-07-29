"""
C# code analyzer using regex patterns.

This module provides analysis of C# code, extracting classes, methods,
properties, and C#-specific features like attributes and LINQ.
"""

import re
from typing import List, Dict, Any, Optional
from ..models import FileInfo, FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo
from .base import LanguageAnalyzer


class CSharpAnalyzer(LanguageAnalyzer):
    """C# analyzer using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.cs']
    
    @property
    def language_name(self) -> str:
        return 'csharp'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Analyze C# code."""
        return self._safe_analyze(content, file_info)
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract method definitions from C# content."""
        functions = []
        
        # Pattern for method declarations
        method_pattern = r'(?:public|private|protected|internal)?\s*(?:static)?\s*(?:virtual|override|abstract)?\s*(?:async\s+)?(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*\((.*?)\)\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            # Skip comments and attributes
            if line.strip().startswith('//') or line.strip().startswith('['):
                continue
            
            match = re.search(method_pattern, line)
            if match:
                name = match.group(1)
                params_str = match.group(2)
                
                # Skip properties (get/set methods)
                if name in ['get', 'set']:
                    continue
                
                parameters = self._parse_csharp_parameters(params_str)
                is_async = 'async' in line
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                functions.append(FunctionInfo(
                    name=name,
                    parameters=parameters,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    is_async=is_async
                ))
        
        return functions
    
    def extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract class definitions from C# content."""
        classes = []
        
        # Pattern for class declarations
        class_pattern = r'(?:public|private|protected|internal)?\s*(?:abstract|sealed|static)?\s*(?:partial\s+)?class\s+(\w+)(?:\s*:\s*(\w+(?:\s*,\s*\w+)*))?\s*\{'
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            match = re.search(class_pattern, line)
            if match:
                name = match.group(1)
                inheritance_str = match.group(2)
                
                # Parse inheritance (first is base class, rest are interfaces)
                inherits_from = None
                if inheritance_str:
                    bases = [b.strip() for b in inheritance_str.split(',')]
                    if bases:
                        inherits_from = bases[0]
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '{', '}')
                
                # Extract methods and properties
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
        """Extract using statements from C# content."""
        imports = []
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Using statements
            using_match = re.match(r'using\s+(?:static\s+)?(.+?);', line)
            if using_match:
                namespace = using_match.group(1)
                
                # Handle aliases: using Alias = Namespace.Type;
                if '=' in namespace:
                    alias, actual_namespace = namespace.split('=', 1)
                    imported_names = [alias.strip()]
                    namespace = actual_namespace.strip()
                else:
                    imported_names = []
                
                imports.append(ImportInfo(
                    module=namespace,
                    imported_names=imported_names,
                    import_type='using',
                    line_number=i + 1
                ))
        
        return imports
    
    def get_language_specific_data(self, content: str) -> Dict[str, Any]:
        """Extract C#-specific features."""
        return {
            'attributes': self._extract_attributes(content),
            'properties': self._extract_properties(content),
            'events': self._extract_events(content),
            'linq_usage': self._extract_linq_usage(content),
            'async_await': self._extract_async_await_usage(content)
        }
    
    def _parse_csharp_parameters(self, params_str: str) -> List[str]:
        """Parse C# method parameters."""
        if not params_str.strip():
            return []
        
        parameters = []
        
        # Split by comma, handling generics
        param_parts = self._split_csharp_parameters(params_str)
        
        for param in param_parts:
            param = param.strip()
            if param:
                # Remove parameter modifiers and default values
                param = re.sub(r'^(?:ref|out|in|params)\s+', '', param)
                param = param.split('=')[0].strip()
                
                # Extract parameter name (last word)
                words = param.split()
                if len(words) >= 2:
                    param_name = words[-1]
                    if param_name.isidentifier():
                        parameters.append(param_name)
        
        return parameters
    
    def _split_csharp_parameters(self, params_str: str) -> List[str]:
        """Split C# parameters by comma, handling generics."""
        params = []
        current_param = ""
        angle_count = 0
        
        for char in params_str:
            if char == '<':
                angle_count += 1
            elif char == '>':
                angle_count -= 1
            elif char == ',' and angle_count == 0:
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
        
        # Pattern for methods and properties
        method_pattern = r'(?:public|private|protected|internal)?\s*(?:static)?\s*(?:virtual|override|abstract)?\s*(?:async\s+)?(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*(?:\(|{)'
        
        for i in range(class_start + 1, min(class_end, len(lines))):
            line = lines[i].strip()
            
            # Skip comments, attributes, and empty lines
            if (line.startswith('//') or line.startswith('[') or 
                line.startswith('/*') or not line):
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
    
    def _extract_attributes(self, content: str) -> Dict[str, List[str]]:
        """Extract C# attributes."""
        attributes = {}
        
        lines = content.splitlines()
        current_attributes = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check for attribute
            if line.startswith('[') and line.endswith(']'):
                attr_content = line[1:-1]
                # Handle multiple attributes in one line
                attrs = [attr.strip() for attr in attr_content.split(',')]
                current_attributes.extend(attrs)
            
            # Check for method/class/property after attributes
            elif current_attributes:
                # Look for method, class, or property declarations
                method_match = re.search(r'(?:public|private|protected|internal)?\s*(?:static)?\s*(?:virtual|override|abstract)?\s*(?:async\s+)?(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*(?:\(|{)', line)
                class_match = re.search(r'(?:public|private|protected|internal)?\s*(?:abstract|sealed|static)?\s*(?:partial\s+)?class\s+(\w+)', line)
                
                if method_match:
                    method_name = method_match.group(1)
                    attributes[method_name] = current_attributes.copy()
                    current_attributes = []
                elif class_match:
                    class_name = class_match.group(1)
                    attributes[class_name] = current_attributes.copy()
                    current_attributes = []
                elif not line or line.startswith('//'):
                    continue  # Skip empty lines and comments
                else:
                    current_attributes = []  # Reset if we hit something else
        
        return attributes
    
    def _extract_properties(self, content: str) -> List[str]:
        """Extract property declarations."""
        properties = []
        
        # Pattern for properties
        property_pattern = r'(?:public|private|protected|internal)?\s*(?:static)?\s*(?:virtual|override|abstract)?\s*\w+\s+(\w+)\s*\{\s*(?:get|set)'
        
        for match in re.finditer(property_pattern, content):
            property_name = match.group(1)
            properties.append(property_name)
        
        return properties
    
    def _extract_events(self, content: str) -> List[str]:
        """Extract event declarations."""
        events = []
        
        # Pattern for events
        event_pattern = r'(?:public|private|protected|internal)?\s*(?:static)?\s*event\s+\w+\s+(\w+)'
        
        for match in re.finditer(event_pattern, content):
            event_name = match.group(1)
            events.append(event_name)
        
        return events
    
    def _extract_linq_usage(self, content: str) -> List[str]:
        """Extract LINQ query usage."""
        linq_patterns = []
        
        # Common LINQ methods
        linq_methods = ['Where', 'Select', 'OrderBy', 'GroupBy', 'Join', 'First', 'Any', 'All', 'Count', 'Sum', 'Average']
        
        for method in linq_methods:
            pattern = rf'\.{method}\s*\('
            if re.search(pattern, content):
                linq_patterns.append(method)
        
        # LINQ query syntax
        if re.search(r'from\s+\w+\s+in\s+', content):
            linq_patterns.append('query_syntax')
        
        return linq_patterns
    
    def _extract_async_await_usage(self, content: str) -> Dict[str, List[str]]:
        """Extract async/await usage."""
        async_usage = {
            'async_methods': [],
            'await_calls': []
        }
        
        # Async methods
        async_pattern = r'async\s+(?:\w+\s+)*(\w+)\s*\('
        for match in re.finditer(async_pattern, content):
            method_name = match.group(1)
            async_usage['async_methods'].append(method_name)
        
        # Await calls
        await_pattern = r'await\s+(\w+(?:\.\w+)*)\s*\('
        for match in re.finditer(await_pattern, content):
            await_call = match.group(1)
            async_usage['await_calls'].append(await_call)
        
        return async_usage