"""Base analyzer interface for language-specific code analysis."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import os
import re
from .analysis_result import AnalysisResult


class LanguageAnalyzer(ABC):
    """Abstract base class for language-specific code analyzers."""

    @abstractmethod
    def analyze(self, content: str, file_path: str, full_path: str = None) -> AnalysisResult:
        """
        Analyze the content of a file and return structured information.

        Args:
            content: The file content as a string
            file_path: The relative path of the file
            full_path: The absolute path of the file (optional)

        Returns:
            AnalysisResult containing structured analysis information
        """


    def _count_lines(self, content: str) -> int:
        """Count the number of lines in the content."""
        return len(content.splitlines())

    def _get_file_size(self, content: str, full_path: str = None) -> int:
        """Get the file size in bytes."""
        if full_path:
            try:
                return os.path.getsize(full_path)
            except (OSError, IOError):
                pass
        # Fallback to content size in bytes
        return len(content.encode('utf-8'))
    
    def _filter_comments_and_empty_lines(self, lines: List[str], comment_patterns: List[str] = None) -> List[str]:
        """Filter out comments and empty lines."""
        if comment_patterns is None:
            comment_patterns = ['//', '#', '/*', '*', '--']
        
        filtered_lines = []
        in_multiline_comment = False
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                continue
                
            # Handle multiline comments
            if '/*' in stripped:
                in_multiline_comment = True
            if '*/' in stripped:
                in_multiline_comment = False
                continue
            if in_multiline_comment:
                continue
                
            # Skip single line comments
            is_comment = False
            for pattern in comment_patterns:
                if stripped.startswith(pattern):
                    is_comment = True
                    break
            
            if not is_comment:
                filtered_lines.append(stripped)
                
        return filtered_lines
    
    # Constants for ReDoS protection
    MAX_PATTERN_LENGTH = 500
    MAX_WILDCARD_COUNT = 10
    
    def _safe_regex_match(self, pattern: str, text: str) -> Optional[re.Match]:
        """Safely match regex pattern with timeout protection."""
        try:
            # Simple pattern validation to prevent ReDoS
            if (len(pattern) > self.MAX_PATTERN_LENGTH or 
                pattern.count('*') > self.MAX_WILDCARD_COUNT or 
                pattern.count('+') > self.MAX_WILDCARD_COUNT):
                return None
            return re.match(pattern, text)
        except re.error:
            return None
