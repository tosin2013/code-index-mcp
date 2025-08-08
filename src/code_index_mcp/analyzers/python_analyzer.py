"""Python language analyzer."""

import os
from typing import Dict, Any
from .base_analyzer import LanguageAnalyzer
from .analysis_result import AnalysisResult


class PythonAnalyzer(LanguageAnalyzer):
    """Analyzer for Python files."""

    def analyze(self, content: str, file_path: str, full_path: str = None) -> AnalysisResult:
        """Analyze Python file content."""
        lines = content.splitlines()

        # Create result object
        _, ext = os.path.splitext(file_path)
        result = AnalysisResult(
            file_path=file_path,
            line_count=self._count_lines(content),
            size_bytes=self._get_file_size(content, full_path),
            extension=ext,
            analysis_type="python"
        )

        # Python-specific analysis
        for i, line in enumerate(lines):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Check for imports
            if line.startswith('import ') or line.startswith('from '):
                result.add_symbol("import", line, i + 1)

            # Check for class definitions
            if line.startswith('class '):
                class_name = line.replace('class ', '').split('(')[0].split(':')[0].strip()
                result.add_symbol("class", class_name, i + 1)

            # Check for function definitions
            if line.startswith('def '):
                func_name = line.replace('def ', '').split('(')[0].strip()
                result.add_symbol("function", func_name, i + 1)

        return result
