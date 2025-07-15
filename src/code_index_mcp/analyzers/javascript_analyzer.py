"""JavaScript/TypeScript language analyzer."""

import os
from typing import Dict, Any
from .base_analyzer import LanguageAnalyzer
from .analysis_result import AnalysisResult


class JavaScriptAnalyzer(LanguageAnalyzer):
    """Analyzer for JavaScript and TypeScript files."""

    def analyze(self, content: str, file_path: str, full_path: str = None) -> AnalysisResult:
        """Analyze JavaScript/TypeScript file content."""
        lines = content.splitlines()

        # Create result object
        _, ext = os.path.splitext(file_path)
        result = AnalysisResult(
            file_path=file_path,
            line_count=self._count_lines(content),
            size_bytes=self._get_file_size(content, full_path),
            extension=ext,
            analysis_type="javascript"
        )

        # JavaScript/TypeScript-specific analysis

        # Simplified patterns for better performance and safety
        # Using simpler string matching instead of complex regex

        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('//') or line.startswith('/*') or line.startswith('*'):
                continue

            # Check for imports (simplified)
            if (line.startswith('import ') or line.startswith('export import') or 
                'require(' in line or line.startswith('import(')):
                result.add_symbol("import", line, i + 1)

            # Check for exports (simplified)
            if (line.startswith('export ') or line.startswith('module.exports')):
                result.add_symbol("export", line, i + 1)

            # Check for class definitions (simplified)
            if 'class ' in line and ('export class' in line or line.startswith('class ')):
                # Extract class name
                parts = line.split('class ')[1] if 'class ' in line else ''
                if parts:
                    class_name = parts.split(' ')[0].split('{')[0].split('(')[0].strip()
                    if class_name:
                        result.add_symbol("class", class_name, i + 1)

            # Check for function definitions (simplified)
            if ('function ' in line or '=>' in line) and not line.endswith(';'):
                func_name = ""
                if 'function ' in line:
                    parts = line.split('function ')[1] if 'function ' in line else ''
                    if parts:
                        func_name = parts.split('(')[0].strip()
                elif '=>' in line and ('const ' in line or 'let ' in line or 'var ' in line):
                    # Arrow function
                    for keyword in ['const ', 'let ', 'var ']:
                        if keyword in line:
                            parts = line.split(keyword)[1]
                            func_name = parts.split('=')[0].strip()
                            break
                
                if func_name and func_name.isidentifier():
                    result.add_symbol("function", func_name, i + 1)

            # Check for constants (simplified)
            if line.startswith('const ') and '=' in line:
                parts = line.split('const ')[1]
                const_name = parts.split('=')[0].strip()
                if const_name and const_name.isidentifier():
                    result.add_symbol("constant", const_name, i + 1)

        return result

