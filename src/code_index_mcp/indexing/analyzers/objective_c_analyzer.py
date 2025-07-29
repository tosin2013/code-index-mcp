"""
Objective-C code analyzer using regex patterns.

This module provides analysis of Objective-C code, extracting interfaces,
implementations, methods, properties, and Objective-C-specific features.
"""

import re
from typing import List, Dict, Any, Optional
from ..models import FileInfo, FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo
from .base import LanguageAnalyzer


class ObjectiveCAnalyzer(LanguageAnalyzer):
    """Objective-C analyzer using regex patterns."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.m', '.mm', '.h']
    
    @property
    def language_name(self) -> str:
        return 'objective-c'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """Analyze Objective-C code."""
        return self._safe_analyze(content, file_info)
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract method definitions from Objective-C content."""
        functions = []
        
        # Pattern for method definitions: - (returnType)methodName: or + (returnType)methodName:
        method_pattern = r'^([-+])\s*\([^)]+\)\s*(\w+)(?::\s*\([^)]*\)\s*(\w+))*'
        
        lines = content.splitlines()
        in_interface = False
        in_implementation = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Track context
            if line.startswith('@interface'):
                in_interface = True
                in_implementation = False
                continue
            elif line.startswith('@implementation'):
                in_interface = False
                in_implementation = True
                continue
            elif line == '@end':
                in_interface = False
                in_implementation = False
                continue
            
            # Only extract methods from interface or implementation blocks
            if not (in_interface or in_implementation):
                continue
            
            match = re.match(method_pattern, line)
            if match:
                method_type = match.group(1)  # - or +
                method_name = match.group(2)
                
                # Parse parameters (simplified)
                parameters = self._parse_objc_parameters(line)
                
                # Estimate method end (simple heuristic)
                line_start = i + 1
                line_end = self._find_method_end(lines, i, in_implementation)
                
                # Determine if it's async (Objective-C doesn't have native async/await)
                is_async = 'completion' in line.lower() or 'callback' in line.lower()
                
                functions.append(FunctionInfo(
                    name=method_name,
                    parameters=parameters,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    is_async=is_async
                ))
        
        return functions
    
    def extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract interface and implementation definitions from Objective-C content."""
        classes = []
        
        # Pattern for @interface declarations
        interface_pattern = r'^@interface\s+(\w+)(?:\s*:\s*(\w+))?'
        # Pattern for @implementation declarations
        implementation_pattern = r'^@implementation\s+(\w+)'
        
        lines = content.splitlines()
        interfaces = {}  # Store interface info
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check for interface definitions
            interface_match = re.match(interface_pattern, line)
            if interface_match:
                name = interface_match.group(1)
                superclass = interface_match.group(2)
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '@interface', '@end')
                
                # Extract methods from interface
                methods = self._extract_interface_methods(lines, i, line_end)
                
                interfaces[name] = {
                    'name': name,
                    'superclass': superclass,
                    'line_start': line_start,
                    'line_end': line_end,
                    'methods': methods
                }
            
            # Check for implementation definitions
            implementation_match = re.match(implementation_pattern, line)
            if implementation_match:
                name = implementation_match.group(1)
                
                line_start = i + 1
                line_end = self._find_block_end(lines, i, '@implementation', '@end')
                
                # Extract methods from implementation
                methods = self._extract_implementation_methods(lines, i, line_end)
                
                # Combine with interface info if available
                interface_info = interfaces.get(name, {})
                all_methods = list(set(interface_info.get('methods', []) + methods))
                
                classes.append(ClassInfo(
                    name=name,
                    line_start=line_start,
                    line_end=line_end,
                    line_count=line_end - line_start + 1,
                    methods=all_methods,
                    inherits_from=interface_info.get('superclass')
                ))
        
        # Add interfaces that don't have implementations (like protocols)
        for name, info in interfaces.items():
            if not any(cls.name == name for cls in classes):
                classes.append(ClassInfo(
                    name=name,
                    line_start=info['line_start'],
                    line_end=info['line_end'],
                    line_count=info['line_end'] - info['line_start'] + 1,
                    methods=info['methods'],
                    inherits_from=info['superclass']
                ))
        
        return classes
    
    def extract_imports(self, content: str) -> List[ImportInfo]:
        """Extract #import statements from Objective-C content."""
        imports = []
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            
            # #import statements
            import_match = re.match(r'#import\s+[<"](.+?)[>"]', line)
            if import_match:
                header = import_match.group(1)
                
                imports.append(ImportInfo(
                    module=header,
                    imported_names=[],
                    import_type='import',
                    line_number=i + 1
                ))
        
        return imports
    
    def get_language_specific_data(self, content: str) -> Dict[str, Any]:
        """Extract Objective-C-specific features."""
        return {
            'properties': self._extract_properties(content),
            'protocols': self._extract_protocols(content),
            'categories': self._extract_categories(content),
            'synthesized_properties': self._extract_synthesized_properties(content)
        }
    
    def _parse_objc_parameters(self, method_line: str) -> List[str]:
        """Parse Objective-C method parameters."""
        parameters = []
        
        # Objective-C method syntax: - (returnType)methodName:(paramType)paramName
        # This is a simplified parser
        parts = method_line.split(':')
        
        for i, part in enumerate(parts[1:], 1):  # Skip the method name part
            # Look for parameter name after the type
            param_match = re.search(r'\)\s*(\w+)', part)
            if param_match:
                parameters.append(param_match.group(1))
            else:
                # Fallback: use generic parameter name
                parameters.append(f'param{i}')
        
        return parameters
    
    def _find_method_end(self, lines: List[str], start_idx: int, in_implementation: bool) -> int:
        """Find the end of a method definition."""
        if not in_implementation:
            # In interface, methods are just declarations (single line)
            return start_idx + 1
        
        # In implementation, find the closing brace
        brace_count = 0
        found_open_brace = False
        
        for i in range(start_idx, len(lines)):
            line = lines[i]
            
            for char in line:
                if char == '{':
                    brace_count += 1
                    found_open_brace = True
                elif char == '}':
                    brace_count -= 1
                    if found_open_brace and brace_count == 0:
                        return i + 1
        
        return len(lines)
    
    def _find_block_end(self, lines: List[str], start_idx: int, start_marker: str, end_marker: str) -> int:
        """Find the end of an Objective-C block."""
        for i in range(start_idx + 1, len(lines)):
            line = lines[i].strip()
            if line == end_marker:
                return i + 1
        return len(lines)
    
    def _extract_interface_methods(self, lines: List[str], start_idx: int, end_idx: int) -> List[str]:
        """Extract method names from an interface block."""
        methods = []
        method_pattern = r'^[-+]\s*\([^)]+\)\s*(\w+)'
        
        for i in range(start_idx + 1, min(end_idx, len(lines))):
            line = lines[i].strip()
            match = re.match(method_pattern, line)
            if match:
                methods.append(match.group(1))
        
        return methods
    
    def _extract_implementation_methods(self, lines: List[str], start_idx: int, end_idx: int) -> List[str]:
        """Extract method names from an implementation block."""
        methods = []
        method_pattern = r'^[-+]\s*\([^)]+\)\s*(\w+)'
        
        for i in range(start_idx + 1, min(end_idx, len(lines))):
            line = lines[i].strip()
            match = re.match(method_pattern, line)
            if match:
                methods.append(match.group(1))
        
        return methods
    
    def _extract_properties(self, content: str) -> List[str]:
        """Extract @property declarations."""
        properties = []
        
        # Pattern for @property declarations
        property_pattern = r'@property\s*\([^)]*\)\s*[\w\s*]+\s*(\w+)'
        
        for match in re.finditer(property_pattern, content):
            property_name = match.group(1)
            properties.append(property_name)
        
        return properties
    
    def _extract_protocols(self, content: str) -> List[str]:
        """Extract @protocol declarations."""
        protocols = []
        
        # Pattern for @protocol declarations
        protocol_pattern = r'@protocol\s+(\w+)'
        
        for match in re.finditer(protocol_pattern, content):
            protocol_name = match.group(1)
            protocols.append(protocol_name)
        
        return protocols
    
    def _extract_categories(self, content: str) -> List[str]:
        """Extract category declarations."""
        categories = []
        
        # Pattern for category declarations: @interface ClassName (CategoryName)
        category_pattern = r'@interface\s+(\w+)\s+\((\w+)\)'
        
        for match in re.finditer(category_pattern, content):
            class_name = match.group(1)
            category_name = match.group(2)
            categories.append(f"{class_name}+{category_name}")
        
        return categories
    
    def _extract_synthesized_properties(self, content: str) -> List[str]:
        """Extract @synthesize declarations."""
        synthesized = []
        
        # Pattern for @synthesize declarations
        synthesize_pattern = r'@synthesize\s+(\w+)'
        
        for match in re.finditer(synthesize_pattern, content):
            property_name = match.group(1)
            synthesized.append(property_name)
        
        return synthesized