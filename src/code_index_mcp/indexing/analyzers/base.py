"""
Abstract base class for language-specific analyzers.

This module defines the interface that all language analyzers must implement,
providing common functionality and ensuring consistent behavior across analyzers.
"""

import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from ..models import FileAnalysisResult, FunctionInfo, ClassInfo, ImportInfo, FileInfo


class LanguageAnalyzer(ABC):
    """Abstract base class for language-specific analyzers."""
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        pass
    
    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the name of the language."""
        pass
    
    @abstractmethod
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """
        Analyze file content and extract code structures.
        
        Args:
            content: File content as string
            file_info: FileInfo object with file metadata
            
        Returns:
            FileAnalysisResult containing extracted information
        """
        pass
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract function definitions from content."""
        # Default implementation - should be overridden by subclasses
        return []
    
    def extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract class definitions from content."""
        # Default implementation - should be overridden by subclasses
        return []
    
    def extract_imports(self, content: str) -> List[ImportInfo]:
        """Extract import statements from content."""
        # Default implementation - should be overridden by subclasses
        return []
    
    def get_language_specific_data(self, content: str) -> Dict[str, Any]:
        """Extract language-specific features."""
        # Default implementation - should be overridden by subclasses
        return {}
    
    def _count_lines(self, content: str, start_pos: int, end_pos: int) -> int:
        """Count lines between two positions in content."""
        return content[:end_pos].count('\n') - content[:start_pos].count('\n') + 1
    
    def _get_line_number(self, content: str, pos: int) -> int:
        """Get line number for a position in content."""
        return content[:pos].count('\n') + 1
    
    def _safe_analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """
        Safely analyze content with error handling.
        
        This method wraps the analysis process with comprehensive error handling
        to ensure that analysis failures don't break the entire indexing process.
        """
        analysis_errors = []
        functions = []
        classes = []
        imports = []
        language_specific = {}
        
        try:
            # Try to extract functions
            functions = self.extract_functions(content)
        except Exception as e:
            analysis_errors.append(f"Function extraction failed: {str(e)}")
        
        try:
            # Try to extract classes
            classes = self.extract_classes(content)
        except Exception as e:
            analysis_errors.append(f"Class extraction failed: {str(e)}")
        
        try:
            # Try to extract imports
            imports = self.extract_imports(content)
        except Exception as e:
            analysis_errors.append(f"Import extraction failed: {str(e)}")
        
        try:
            # Try to extract language-specific data
            language_specific = self.get_language_specific_data(content)
        except Exception as e:
            analysis_errors.append(f"Language-specific extraction failed: {str(e)}")
        
        return FileAnalysisResult(
            file_info=file_info,
            functions=functions,
            classes=classes,
            imports=imports,
            language_specific={self.language_name: language_specific},
            analysis_errors=analysis_errors
        )


class GenericAnalyzer(LanguageAnalyzer):
    """Enhanced generic analyzer for file types without specific analyzers."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['*']  # Supports all extensions as fallback
    
    @property
    def language_name(self) -> str:
        return 'generic'
    
    def analyze(self, content: str, file_info: FileInfo) -> FileAnalysisResult:
        """
        Provide enhanced analysis for file types without specific analyzers.
        
        This analyzer attempts to extract basic code structures using
        common patterns that work across multiple languages.
        """
        return self._safe_analyze(content, file_info)
    
    def extract_functions(self, content: str) -> List[FunctionInfo]:
        """Extract functions using generic patterns."""
        functions = []
        
        # Common function patterns across languages
        patterns = [
            r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:async)?\s*(?:function|def|fn|func|sub|proc)\s+(\w+)\s*\(',  # function/def/fn/func
            r'^\s*(\w+)\s*:\s*function\s*\(',  # JavaScript object method
            r'^\s*(\w+)\s*=\s*function\s*\(',  # JavaScript function assignment
            r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',  # Arrow functions
            r'^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(',  # Java/C# methods
        ]
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    func_name = match.group(1)
                    
                    # Skip common keywords
                    if func_name not in ['if', 'for', 'while', 'switch', 'try', 'catch', 'class', 'struct']:
                        # Estimate function end (simple heuristic)
                        line_end = self._find_block_end(lines, i)
                        
                        functions.append(FunctionInfo(
                            name=func_name,
                            parameters=self._extract_parameters(line),
                            line_start=i + 1,
                            line_end=line_end,
                            line_count=line_end - i,
                            is_async='async' in line.lower()
                        ))
                        break
        
        return functions
    
    def extract_classes(self, content: str) -> List[ClassInfo]:
        """Extract classes using generic patterns."""
        classes = []
        
        # Common class patterns
        patterns = [
            r'^\s*(?:public|private|protected)?\s*(?:abstract)?\s*class\s+(\w+)(?:\s*:\s*(\w+))?',  # C#/Java
            r'^\s*class\s+(\w+)(?:\(([^)]+)\))?(?:\s*:\s*([^{]+))?',  # Python/general
            r'^\s*struct\s+(\w+)',  # C/Go struct
            r'^\s*interface\s+(\w+)',  # Interface
            r'^\s*type\s+(\w+)\s+struct',  # Go struct
        ]
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    class_name = match.group(1)
                    inherits_from = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                    
                    # Estimate class end
                    line_end = self._find_block_end(lines, i)
                    
                    # Extract methods (simplified)
                    methods = self._extract_class_methods(lines, i, line_end)
                    
                    classes.append(ClassInfo(
                        name=class_name,
                        line_start=i + 1,
                        line_end=line_end,
                        line_count=line_end - i,
                        methods=methods,
                        inherits_from=inherits_from
                    ))
                    break
        
        return classes
    
    def extract_imports(self, content: str) -> List[ImportInfo]:
        """Extract imports using generic patterns."""
        imports = []
        
        # Common import patterns
        patterns = [
            (r'^\s*import\s+(.+)', 'import'),
            (r'^\s*from\s+(.+?)\s+import\s+(.+)', 'from'),
            (r'^\s*#include\s*[<"](.+?)[>"]', 'include'),
            (r'^\s*require\s*\([\'"](.+?)[\'"]\)', 'require'),
            (r'^\s*use\s+(.+)', 'use'),
            (r'^\s*using\s+(.+)', 'using'),
        ]
        
        lines = content.splitlines()
        for i, line in enumerate(lines):
            for pattern, import_type in patterns:
                match = re.match(pattern, line)
                if match:
                    if import_type == 'from':
                        module = match.group(1)
                        imported_names = [name.strip() for name in match.group(2).split(',')]
                    else:
                        module = match.group(1)
                        imported_names = []
                    
                    imports.append(ImportInfo(
                        module=module.strip(),
                        imported_names=imported_names,
                        import_type=import_type,
                        line_number=i + 1
                    ))
                    break
        
        return imports
    
    def get_language_specific_data(self, content: str) -> Dict[str, Any]:
        """Extract generic language features."""
        return {
            'line_count': len(content.splitlines()),
            'char_count': len(content),
            'is_text_file': self._is_text_file(content),
            'detected_language': self._detect_language_hints(content),
            'has_comments': self._has_comments(content),
            'indentation_style': self._detect_indentation(content)
        }
    
    def _extract_parameters(self, line: str) -> List[str]:
        """Extract parameters from a function definition line."""
        # Find content between parentheses
        match = re.search(r'\(([^)]*)\)', line)
        if not match:
            return []
        
        params_str = match.group(1).strip()
        if not params_str:
            return []
        
        # Split by comma and clean up
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Remove type annotations and default values (simplified)
                param = param.split(':')[0].split('=')[0].strip()
                if param and param.isidentifier():
                    params.append(param)
        
        return params
    
    def _find_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of a code block using indentation or braces."""
        if start_idx >= len(lines):
            return start_idx + 1
        
        start_line = lines[start_idx]
        
        # If line has opening brace, find matching closing brace
        if '{' in start_line:
            brace_count = 0
            for i in range(start_idx, len(lines)):
                line = lines[i]
                brace_count += line.count('{') - line.count('}')
                if brace_count == 0 and i > start_idx:
                    return i + 1
        
        # Otherwise, use indentation-based detection
        base_indent = len(start_line) - len(start_line.lstrip())
        
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if line.strip() == '':
                continue
            
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= base_indent and line.strip():
                return i
        
        return len(lines)
    
    def _extract_class_methods(self, lines: List[str], start_idx: int, end_idx: int) -> List[str]:
        """Extract method names from a class block."""
        methods = []
        
        for i in range(start_idx + 1, min(end_idx, len(lines))):
            line = lines[i].strip()
            
            # Look for method-like patterns
            method_patterns = [
                r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:async)?\s*(?:function|def|fn)\s+(\w+)\s*\(',
                r'^\s*(\w+)\s*\(',  # Simple method call pattern
            ]
            
            for pattern in method_patterns:
                match = re.match(pattern, line)
                if match:
                    method_name = match.group(1)
                    if method_name not in ['if', 'for', 'while', 'switch', 'try', 'catch']:
                        methods.append(method_name)
                    break
        
        return methods
    
    def _is_text_file(self, content: str) -> bool:
        """Check if content appears to be text (not binary)."""
        try:
            content.encode('utf-8')
            return '\x00' not in content
        except UnicodeEncodeError:
            return False
    
    def _detect_language_hints(self, content: str) -> str:
        """Try to detect language from content patterns."""
        # Simple heuristics based on common patterns
        if 'def ' in content and 'import ' in content:
            return 'python'
        elif 'function ' in content and ('var ' in content or 'let ' in content or 'const ' in content):
            return 'javascript'
        elif 'public class ' in content or 'private class ' in content:
            return 'java'
        elif '#include' in content and ('int main' in content or 'void main' in content):
            return 'c'
        elif 'func ' in content and 'package ' in content:
            return 'go'
        elif 'fn ' in content and ('let ' in content or 'mut ' in content):
            return 'rust'
        else:
            return 'unknown'
    
    def _has_comments(self, content: str) -> bool:
        """Check if content has comments."""
        comment_patterns = ['//', '#', '/*', '--', ';', '%']
        return any(pattern in content for pattern in comment_patterns)
    
    def _detect_indentation(self, content: str) -> str:
        """Detect indentation style (tabs vs spaces)."""
        lines = content.splitlines()
        tab_count = 0
        space_count = 0
        
        for line in lines:
            if line.startswith('\t'):
                tab_count += 1
            elif line.startswith('    '):  # 4 spaces
                space_count += 1
            elif line.startswith('  '):   # 2 spaces
                space_count += 1
        
        if tab_count > space_count:
            return 'tabs'
        elif space_count > tab_count:
            return 'spaces'
        else:
            return 'mixed'