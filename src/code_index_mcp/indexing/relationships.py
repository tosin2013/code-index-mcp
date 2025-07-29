"""
Relationship tracker for building cross-file code relationships.

This module analyzes relationships between code elements across files,
including function calls, class instantiations, and import dependencies.
"""

import os
import re
from typing import Dict, List, Any, Set
from .models import FileAnalysisResult, RelationshipGraph, LookupTables, ReverseLookups


class RelationshipTracker:
    """Tracks relationships between code elements across files."""
    
    def __init__(self):
        self.function_calls: Dict[str, List[str]] = {}
        self.class_instantiations: Dict[str, List[str]] = {}
        self.import_relationships: Dict[str, List[str]] = {}
        self.file_id_to_path: Dict[int, str] = {}
        self.path_to_file_id: Dict[str, int] = {}
    
    def build_relationships(self, analysis_results: List[FileAnalysisResult]) -> RelationshipGraph:
        """
        Build relationship graph from analysis results.
        
        Args:
            analysis_results: List of file analysis results
            
        Returns:
            RelationshipGraph containing all relationships
        """
        # Build file mappings
        self._build_file_mappings(analysis_results)
        
        # Track different types of relationships
        self._track_function_calls(analysis_results)
        self._track_class_usage(analysis_results)
        self._track_imports(analysis_results)
        
        # Build reverse lookups
        reverse_lookups = self._build_reverse_lookups()
        
        return RelationshipGraph(
            function_calls=self.function_calls,
            class_instantiations=self.class_instantiations,
            import_relationships=self.import_relationships,
            reverse_lookups=reverse_lookups
        )
    
    def _build_file_mappings(self, analysis_results: List[FileAnalysisResult]):
        """Build mappings between file IDs and paths."""
        for result in analysis_results:
            file_id = result.file_info.id
            file_path = result.file_info.path
            self.file_id_to_path[file_id] = file_path
            self.path_to_file_id[file_path] = file_id
    
    def _track_function_calls(self, analysis_results: List[FileAnalysisResult]):
        """Track function call relationships."""
        # First, build a global function registry
        function_to_file: Dict[str, int] = {}
        
        for result in analysis_results:
            for func in result.functions:
                function_to_file[func.name] = result.file_info.id
        
        # Then analyze function calls in each file
        for result in analysis_results:
            file_content = self._get_file_content(result.file_info.path)
            if not file_content:
                continue
            
            for func in result.functions:
                calls = self._extract_function_calls_from_content(
                    file_content, func, result.file_info.language
                )
                
                # Filter to only include calls to functions we know about
                valid_calls = [call for call in calls if call in function_to_file]
                
                if valid_calls:
                    self.function_calls[func.name] = valid_calls
                    
                    # Update the function info with calls
                    func.calls = valid_calls
                    
                    # Update called_by relationships
                    for called_func in valid_calls:
                        # Find the function object and update its called_by list
                        for other_result in analysis_results:
                            for other_func in other_result.functions:
                                if other_func.name == called_func:
                                    if func.name not in other_func.called_by:
                                        other_func.called_by.append(func.name)
    
    def _track_class_usage(self, analysis_results: List[FileAnalysisResult]):
        """Track class instantiation relationships."""
        # Build a global class registry
        class_to_file: Dict[str, int] = {}
        
        for result in analysis_results:
            for cls in result.classes:
                class_to_file[cls.name] = result.file_info.id
        
        # Analyze class instantiations
        for result in analysis_results:
            file_content = self._get_file_content(result.file_info.path)
            if not file_content:
                continue
            
            for func in result.functions:
                instantiations = self._extract_class_instantiations_from_content(
                    file_content, func, result.file_info.language
                )
                
                # Filter to only include classes we know about
                valid_instantiations = [inst for inst in instantiations if inst in class_to_file]
                
                if valid_instantiations:
                    self.class_instantiations[func.name] = valid_instantiations
                    
                    # Update instantiated_by relationships
                    for class_name in valid_instantiations:
                        for other_result in analysis_results:
                            for cls in other_result.classes:
                                if cls.name == class_name:
                                    if func.name not in cls.instantiated_by:
                                        cls.instantiated_by.append(func.name)
    
    def _track_imports(self, analysis_results: List[FileAnalysisResult]):
        """Track import relationships between modules."""
        for result in analysis_results:
            file_path = result.file_info.path
            imported_modules = []
            
            for import_info in result.imports:
                imported_modules.append(import_info.module)
            
            if imported_modules:
                self.import_relationships[file_path] = imported_modules
    
    def _extract_function_calls_from_content(
        self, content: str, func: Any, language: str
    ) -> List[str]:
        """Extract function calls from file content."""
        calls = []
        
        # Get the function's content (approximate)
        lines = content.splitlines()
        if func.line_start <= len(lines) and func.line_end <= len(lines):
            func_content = '\n'.join(lines[func.line_start-1:func.line_end])
            
            # Language-specific function call patterns
            if language == 'python':
                calls.extend(self._extract_python_function_calls(func_content))
            elif language in ['javascript', 'typescript']:
                calls.extend(self._extract_javascript_function_calls(func_content))
            elif language == 'java':
                calls.extend(self._extract_java_function_calls(func_content))
            elif language == 'go':
                calls.extend(self._extract_go_function_calls(func_content))
            elif language in ['c', 'cpp']:
                calls.extend(self._extract_c_function_calls(func_content))
            elif language == 'csharp':
                calls.extend(self._extract_csharp_function_calls(func_content))
        
        return list(set(calls))  # Remove duplicates
    
    def _extract_class_instantiations_from_content(
        self, content: str, func: Any, language: str
    ) -> List[str]:
        """Extract class instantiations from file content."""
        instantiations = []
        
        # Get the function's content
        lines = content.splitlines()
        if func.line_start <= len(lines) and func.line_end <= len(lines):
            func_content = '\n'.join(lines[func.line_start-1:func.line_end])
            
            # Language-specific instantiation patterns
            if language == 'python':
                instantiations.extend(self._extract_python_instantiations(func_content))
            elif language in ['javascript', 'typescript']:
                instantiations.extend(self._extract_javascript_instantiations(func_content))
            elif language == 'java':
                instantiations.extend(self._extract_java_instantiations(func_content))
            elif language == 'go':
                instantiations.extend(self._extract_go_instantiations(func_content))
            elif language in ['c', 'cpp']:
                instantiations.extend(self._extract_cpp_instantiations(func_content))
            elif language == 'csharp':
                instantiations.extend(self._extract_csharp_instantiations(func_content))
        
        return list(set(instantiations))  # Remove duplicates
    
    def _extract_python_function_calls(self, content: str) -> List[str]:
        """Extract Python function calls."""
        calls = []
        
        # Pattern for function calls: function_name(
        pattern = r'(\w+)\s*\('
        
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            # Skip common keywords and built-ins
            if func_name not in ['if', 'for', 'while', 'with', 'try', 'except', 'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple']:
                calls.append(func_name)
        
        return calls
    
    def _extract_python_instantiations(self, content: str) -> List[str]:
        """Extract Python class instantiations."""
        instantiations = []
        
        # Pattern for class instantiation: ClassName(
        pattern = r'([A-Z]\w*)\s*\('
        
        for match in re.finditer(pattern, content):
            class_name = match.group(1)
            instantiations.append(class_name)
        
        return instantiations
    
    def _extract_javascript_function_calls(self, content: str) -> List[str]:
        """Extract JavaScript function calls."""
        calls = []
        
        # Pattern for function calls
        pattern = r'(\w+)\s*\('
        
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            # Skip common keywords
            if func_name not in ['if', 'for', 'while', 'switch', 'try', 'catch', 'console', 'setTimeout', 'setInterval']:
                calls.append(func_name)
        
        return calls
    
    def _extract_javascript_instantiations(self, content: str) -> List[str]:
        """Extract JavaScript class instantiations."""
        instantiations = []
        
        # Pattern for new ClassName(
        pattern = r'new\s+([A-Z]\w*)\s*\('
        
        for match in re.finditer(pattern, content):
            class_name = match.group(1)
            instantiations.append(class_name)
        
        return instantiations
    
    def _extract_java_function_calls(self, content: str) -> List[str]:
        """Extract Java method calls."""
        calls = []
        
        # Pattern for method calls
        pattern = r'(\w+)\s*\('
        
        for match in re.finditer(pattern, content):
            method_name = match.group(1)
            # Skip common keywords
            if method_name not in ['if', 'for', 'while', 'switch', 'try', 'catch', 'System', 'String']:
                calls.append(method_name)
        
        return calls
    
    def _extract_java_instantiations(self, content: str) -> List[str]:
        """Extract Java class instantiations."""
        instantiations = []
        
        # Pattern for new ClassName(
        pattern = r'new\s+([A-Z]\w*)\s*\('
        
        for match in re.finditer(pattern, content):
            class_name = match.group(1)
            instantiations.append(class_name)
        
        return instantiations
    
    def _extract_go_function_calls(self, content: str) -> List[str]:
        """Extract Go function calls."""
        calls = []
        
        # Pattern for function calls
        pattern = r'(\w+)\s*\('
        
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            # Skip common keywords
            if func_name not in ['if', 'for', 'switch', 'select', 'go', 'defer', 'make', 'new', 'len', 'cap']:
                calls.append(func_name)
        
        return calls
    
    def _extract_go_instantiations(self, content: str) -> List[str]:
        """Extract Go struct instantiations."""
        instantiations = []
        
        # Pattern for struct literals: StructName{
        pattern = r'([A-Z]\w*)\s*\{'
        
        for match in re.finditer(pattern, content):
            struct_name = match.group(1)
            instantiations.append(struct_name)
        
        return instantiations
    
    def _extract_c_function_calls(self, content: str) -> List[str]:
        """Extract C function calls."""
        calls = []
        
        # Pattern for function calls
        pattern = r'(\w+)\s*\('
        
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            # Skip common keywords and standard library functions
            if func_name not in ['if', 'for', 'while', 'switch', 'printf', 'scanf', 'malloc', 'free', 'sizeof']:
                calls.append(func_name)
        
        return calls
    
    def _extract_cpp_instantiations(self, content: str) -> List[str]:
        """Extract C++ class instantiations."""
        instantiations = []
        
        # Pattern for new ClassName or ClassName variable
        patterns = [
            r'new\s+([A-Z]\w*)\s*\(',  # new ClassName(
            r'([A-Z]\w*)\s+\w+\s*\(',  # ClassName variable(
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                class_name = match.group(1)
                instantiations.append(class_name)
        
        return instantiations
    
    def _extract_csharp_function_calls(self, content: str) -> List[str]:
        """Extract C# method calls."""
        calls = []
        
        # Pattern for method calls
        pattern = r'(\w+)\s*\('
        
        for match in re.finditer(pattern, content):
            method_name = match.group(1)
            # Skip common keywords
            if method_name not in ['if', 'for', 'while', 'switch', 'try', 'catch', 'Console', 'String']:
                calls.append(method_name)
        
        return calls
    
    def _extract_csharp_instantiations(self, content: str) -> List[str]:
        """Extract C# class instantiations."""
        instantiations = []
        
        # Pattern for new ClassName(
        pattern = r'new\s+([A-Z]\w*)\s*\('
        
        for match in re.finditer(pattern, content):
            class_name = match.group(1)
            instantiations.append(class_name)
        
        return instantiations
    
    def _get_file_content(self, file_path: str) -> str:
        """Get file content for analysis."""
        try:
            # Convert relative path to absolute if needed
            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)
            
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            
            return ""
            
        except (OSError, PermissionError, FileNotFoundError):
            return ""
    
    def _build_reverse_lookups(self) -> Dict[str, Any]:
        """Build reverse lookup tables for efficient querying."""
        reverse_lookups = {
            'function_callers': {},
            'class_instantiators': {},
            'imports_module': {},
            'has_decorator': {}
        }
        
        # Build function_callers reverse lookup
        for caller, callees in self.function_calls.items():
            for callee in callees:
                if callee not in reverse_lookups['function_callers']:
                    reverse_lookups['function_callers'][callee] = []
                
                # Find the file ID for the caller
                caller_file_id = None
                for file_id, path in self.file_id_to_path.items():
                    # This is simplified - would need better lookup
                    caller_file_id = file_id
                    break
                
                reverse_lookups['function_callers'][callee].append({
                    'file_id': caller_file_id,
                    'caller': caller
                })
        
        # Build class_instantiators reverse lookup
        for instantiator, classes in self.class_instantiations.items():
            for class_name in classes:
                if class_name not in reverse_lookups['class_instantiators']:
                    reverse_lookups['class_instantiators'][class_name] = []
                
                # Find the file ID for the instantiator
                instantiator_file_id = None
                for file_id, path in self.file_id_to_path.items():
                    # This is simplified - would need better lookup
                    instantiator_file_id = file_id
                    break
                
                reverse_lookups['class_instantiators'][class_name].append({
                    'file_id': instantiator_file_id,
                    'instantiator': instantiator
                })
        
        # Build imports_module reverse lookup
        for file_path, modules in self.import_relationships.items():
            file_id = self.path_to_file_id.get(file_path)
            if file_id is not None:
                for module in modules:
                    if module not in reverse_lookups['imports_module']:
                        reverse_lookups['imports_module'][module] = []
                    reverse_lookups['imports_module'][module].append(file_id)
        
        return reverse_lookups