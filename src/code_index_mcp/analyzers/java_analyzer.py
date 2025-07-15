"""Java language analyzer."""

import os
import re
from typing import Dict, Any
from .base_analyzer import LanguageAnalyzer
from .analysis_result import AnalysisResult


class JavaAnalyzer(LanguageAnalyzer):
    """Analyzer for Java files."""
    
    def __init__(self):
        """Initialize with compiled regex patterns for performance."""
        self.import_pattern = re.compile(r'^import\s+([\w.]+);')
        self.class_pattern = re.compile(r'^(public\s+|protected\s+|private\s+)?(static\s+)?(abstract\s+)?(final\s+)?class\s+(\w+)')
        self.method_pattern = re.compile(r'^(public|protected|private|static|final|abstract|synchronized|native|strictfp|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)')
        self.field_pattern = re.compile(r'^(public|protected|private|static|final|transient|volatile|\s)+[\w<>\[\]]+\s+(\w+)\s*(=|;)')

    def analyze(self, content: str, file_path: str, full_path: str = None) -> AnalysisResult:
        """Analyze Java file content."""
        lines = content.splitlines()

        # Create result object
        _, ext = os.path.splitext(file_path)
        result = AnalysisResult(
            file_path=file_path,
            line_count=self._count_lines(content),
            size_bytes=self._get_file_size(content, full_path),
            extension=ext,
            analysis_type="java"
        )

        # Java-specific analysis using pre-compiled patterns

        in_multiline_comment = False

        for i, line in enumerate(lines):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('//'):
                continue

            # Handle multiline comments
            if '/*' in line:
                in_multiline_comment = True
            if '*/' in line:
                in_multiline_comment = False
                continue
            if in_multiline_comment:
                continue

            # Check for imports
            import_match = self.import_pattern.match(line)
            if import_match:
                result.add_symbol("import", import_match.group(1), i + 1)

            # Check for class definitions
            class_match = self.class_pattern.match(line)
            if class_match:
                modifiers = [m for m in class_match.groups()[:4] if m and m.strip()]
                result.add_symbol("class", class_match.group(5), i + 1, 
                                {"modifiers": modifiers})

            # Check for method definitions
            method_match = self.method_pattern.match(line)
            if method_match and not line.strip().endswith(';'):
                result.add_symbol("function", method_match.group(2), i + 1)

            # Check for field definitions
            field_match = self.field_pattern.match(line)
            if field_match and not line.strip().startswith('//'):
                result.add_symbol("field", field_match.group(2), i + 1)

        return result

