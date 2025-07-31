"""
Relationship tracker for building cross-file code relationships.

This module analyzes relationships between code elements across files,
including function calls, class instantiations, and import dependencies.
"""

import os
import re
from typing import Dict, List, Any, Set
from .models import FileAnalysisResult, RelationshipGraph, LookupTables, ReverseLookups
from .qualified_names import generate_qualified_name, parse_qualified_name


class RelationshipTracker:
    """Tracks relationships between code elements across files."""
    
    def __init__(self):
        self.function_calls: Dict[str, List[str]] = {}
        self.class_instantiations: Dict[str, List[str]] = {}
        self.import_relationships: Dict[str, List[str]] = {}
        self.file_id_to_path: Dict[int, str] = {}
        self.path_to_file_id: Dict[str, int] = {}
        
        # Qualified name mappings for duplicate handling
        self.qualified_function_to_file: Dict[str, int] = {}
        self.qualified_class_to_file: Dict[str, int] = {}
        self.qualified_function_calls: Dict[str, List[str]] = {}
        self.qualified_class_instantiations: Dict[str, List[str]] = {}
    
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
        
        # Build qualified name mappings for duplicate handling
        self._build_qualified_mappings(analysis_results)
        
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
    
    def _build_qualified_mappings(self, analysis_results: List[FileAnalysisResult]):
        """Build qualified name mappings for duplicate handling."""
        for result in analysis_results:
            file_id = result.file_info.id
            file_path = result.file_info.path
            
            # Build qualified function mappings
            for func in result.functions:
                qualified_name = generate_qualified_name(file_path, func.name)
                self.qualified_function_to_file[qualified_name] = file_id
            
            # Build qualified class mappings
            for cls in result.classes:
                qualified_name = generate_qualified_name(file_path, cls.name)
                self.qualified_class_to_file[qualified_name] = file_id
    
    def _track_function_calls(self, analysis_results: List[FileAnalysisResult]):
        """Track function call relationships with qualified name support."""
        # Build both unqualified and qualified function registries
        function_to_file: Dict[str, int] = {}  # For backward compatibility
        function_name_to_files: Dict[str, List[int]] = {}  # For duplicate handling
        
        for result in analysis_results:
            for func in result.functions:
                # Unqualified mapping (last one wins - for backward compatibility)
                function_to_file[func.name] = result.file_info.id
                
                # Multi-file mapping for duplicates
                if func.name not in function_name_to_files:
                    function_name_to_files[func.name] = []
                if result.file_info.id not in function_name_to_files[func.name]:
                    function_name_to_files[func.name].append(result.file_info.id)
        
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
                    # Store both qualified and unqualified relationships
                    caller_qualified = generate_qualified_name(result.file_info.path, func.name)
                    
                    # Unqualified relationships (for backward compatibility)
                    self.function_calls[func.name] = valid_calls
                    
                    # Qualified relationships for duplicate handling
                    qualified_calls = []
                    for called_func in valid_calls:
                        # For each called function, determine which file it's actually in
                        # For now, use all possible files (handling duplicates)
                        target_files = function_name_to_files.get(called_func, [])
                        for target_file_id in target_files:
                            target_file_path = self.file_id_to_path[target_file_id]
                            qualified_call = generate_qualified_name(target_file_path, called_func)
                            qualified_calls.append(qualified_call)
                    
                    self.qualified_function_calls[caller_qualified] = qualified_calls
                    
                    # Update the function info with calls
                    func.calls = valid_calls
                    
                    # Update called_by relationships using qualified names
                    for called_func in valid_calls:
                        target_files = function_name_to_files.get(called_func, [])
                        for target_file_id in target_files:
                            # Find the function object and update its called_by list
                            for other_result in analysis_results:
                                if other_result.file_info.id == target_file_id:
                                    for other_func in other_result.functions:
                                        if other_func.name == called_func:
                                            if func.name not in other_func.called_by:
                                                other_func.called_by.append(func.name)
    
    def _track_class_usage(self, analysis_results: List[FileAnalysisResult]):
        """Track class instantiation relationships with qualified name support."""
        # Build both unqualified and qualified class registries
        class_to_file: Dict[str, int] = {}  # For backward compatibility
        class_name_to_files: Dict[str, List[int]] = {}  # For duplicate handling
        
        for result in analysis_results:
            for cls in result.classes:
                # Unqualified mapping (last one wins - for backward compatibility)
                class_to_file[cls.name] = result.file_info.id
                
                # Multi-file mapping for duplicates
                if cls.name not in class_name_to_files:
                    class_name_to_files[cls.name] = []
                if result.file_info.id not in class_name_to_files[cls.name]:
                    class_name_to_files[cls.name].append(result.file_info.id)
        
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
                    # Store both qualified and unqualified relationships
                    instantiator_qualified = generate_qualified_name(result.file_info.path, func.name)
                    
                    # Unqualified relationships (for backward compatibility)
                    self.class_instantiations[func.name] = valid_instantiations
                    
                    # Qualified relationships for duplicate handling
                    qualified_instantiations = []
                    for class_name in valid_instantiations:
                        # For each instantiated class, determine which file it's actually in
                        # For now, use all possible files (handling duplicates)
                        target_files = class_name_to_files.get(class_name, [])
                        for target_file_id in target_files:
                            target_file_path = self.file_id_to_path[target_file_id]
                            qualified_instantiation = generate_qualified_name(target_file_path, class_name)
                            qualified_instantiations.append(qualified_instantiation)
                    
                    self.qualified_class_instantiations[instantiator_qualified] = qualified_instantiations
                    
                    # Update instantiated_by relationships using qualified names
                    for class_name in valid_instantiations:
                        target_files = class_name_to_files.get(class_name, [])
                        for target_file_id in target_files:
                            # Find the class object and update its instantiated_by list
                            for other_result in analysis_results:
                                if other_result.file_info.id == target_file_id:
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
        """Build reverse lookup tables for efficient querying with qualified name support."""
        reverse_lookups = {
            'function_callers': {},
            'class_instantiators': {},
            'imports_module': {},
            'has_decorator': {}
        }
        
        # Build function_callers reverse lookup using qualified names
        for caller_qualified, callees_qualified in self.qualified_function_calls.items():
            try:
                caller_file_path, caller_name = parse_qualified_name(caller_qualified)
                caller_file_id = self.path_to_file_id.get(caller_file_path)
                
                if caller_file_id is None:
                    continue
                
                for callee_qualified in callees_qualified:
                    try:
                        callee_file_path, callee_name = parse_qualified_name(callee_qualified)
                        
                        # Use qualified names as keys for precise tracking
                        if callee_qualified not in reverse_lookups['function_callers']:
                            reverse_lookups['function_callers'][callee_qualified] = []
                        
                        reverse_lookups['function_callers'][callee_qualified].append({
                            'file_id': caller_file_id,
                            'caller': caller_name,
                            'caller_qualified': caller_qualified,
                            'caller_file_path': caller_file_path
                        })
                        
                        # Also maintain unqualified entries for backward compatibility
                        if callee_name not in reverse_lookups['function_callers']:
                            reverse_lookups['function_callers'][callee_name] = []
                        
                        # Avoid duplicates in unqualified lookup
                        unqualified_entry = {
                            'file_id': caller_file_id,
                            'caller': caller_name,
                            'caller_qualified': caller_qualified,
                            'caller_file_path': caller_file_path
                        }
                        
                        if unqualified_entry not in reverse_lookups['function_callers'][callee_name]:
                            reverse_lookups['function_callers'][callee_name].append(unqualified_entry)
                        
                    except ValueError:
                        # Skip malformed qualified names
                        continue
                        
            except ValueError:
                # Skip malformed qualified names
                continue
        
        # Build class_instantiators reverse lookup using qualified names
        for instantiator_qualified, classes_qualified in self.qualified_class_instantiations.items():
            try:
                instantiator_file_path, instantiator_name = parse_qualified_name(instantiator_qualified)
                instantiator_file_id = self.path_to_file_id.get(instantiator_file_path)
                
                if instantiator_file_id is None:
                    continue
                
                for class_qualified in classes_qualified:
                    try:
                        class_file_path, class_name = parse_qualified_name(class_qualified)
                        
                        # Use qualified names as keys for precise tracking
                        if class_qualified not in reverse_lookups['class_instantiators']:
                            reverse_lookups['class_instantiators'][class_qualified] = []
                        
                        reverse_lookups['class_instantiators'][class_qualified].append({
                            'file_id': instantiator_file_id,
                            'instantiator': instantiator_name,
                            'instantiator_qualified': instantiator_qualified,
                            'instantiator_file_path': instantiator_file_path
                        })
                        
                        # Also maintain unqualified entries for backward compatibility
                        if class_name not in reverse_lookups['class_instantiators']:
                            reverse_lookups['class_instantiators'][class_name] = []
                        
                        # Avoid duplicates in unqualified lookup
                        unqualified_entry = {
                            'file_id': instantiator_file_id,
                            'instantiator': instantiator_name,
                            'instantiator_qualified': instantiator_qualified,
                            'instantiator_file_path': instantiator_file_path
                        }
                        
                        if unqualified_entry not in reverse_lookups['class_instantiators'][class_name]:
                            reverse_lookups['class_instantiators'][class_name].append(unqualified_entry)
                        
                    except ValueError:
                        # Skip malformed qualified names
                        continue
                        
            except ValueError:
                # Skip malformed qualified names
                continue
        
        # Build imports_module reverse lookup (unchanged - doesn't need qualified names)
        for file_path, modules in self.import_relationships.items():
            file_id = self.path_to_file_id.get(file_path)
            if file_id is not None:
                for module in modules:
                    if module not in reverse_lookups['imports_module']:
                        reverse_lookups['imports_module'][module] = []
                    if file_id not in reverse_lookups['imports_module'][module]:
                        reverse_lookups['imports_module'][module].append(file_id)
        
        return reverse_lookups