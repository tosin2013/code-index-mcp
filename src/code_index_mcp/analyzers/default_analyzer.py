"""Default analyzer for basic file information."""

import os
from typing import Dict, Any
from .base_analyzer import LanguageAnalyzer
from .analysis_result import AnalysisResult


class DefaultAnalyzer(LanguageAnalyzer):
    """Default analyzer that provides basic file information."""
    
    def analyze(self, content: str, file_path: str, full_path: str = None) -> AnalysisResult:
        """Provide basic file analysis."""
        _, ext = os.path.splitext(file_path)
        
        return AnalysisResult(
            file_path=file_path,
            line_count=self._count_lines(content),
            size_bytes=self._get_file_size(content, full_path),
            extension=ext,
            analysis_type="basic"
        )
    
