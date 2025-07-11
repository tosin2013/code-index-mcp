"""
Basic, pure-Python search strategy.
"""
import os
import re
import fnmatch
from typing import Dict, List, Optional, Tuple

from .base import SearchStrategy, create_safe_fuzzy_pattern

class BasicSearchStrategy(SearchStrategy):
    """
    A basic, pure-Python search strategy.

    This strategy iterates through files and lines manually. It's a fallback
    for when no advanced command-line search tools are available.
    It does not support context lines.
    """

    @property
    def name(self) -> str:
        """The name of the search tool."""
        return 'basic'

    def is_available(self) -> bool:
        """This basic strategy is always available."""
        return True

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches the glob pattern."""
        if not pattern:
            return True
        
        # Handle simple cases efficiently
        if pattern.startswith('*') and not any(c in pattern[1:] for c in '*?[]{}'):
            return filename.endswith(pattern[1:])
        
        # Use fnmatch for more complex patterns
        return fnmatch.fnmatch(filename, pattern)

    def search(
        self,
        pattern: str,
        base_path: str,
        case_sensitive: bool = True,
        context_lines: int = 0,
        file_pattern: Optional[str] = None,
        fuzzy: bool = False
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Execute a basic, line-by-line search.

        Note: This implementation does not support context_lines.
        Fuzzy searching uses the shared create_safe_fuzzy_pattern function.
        """
        results: Dict[str, List[Tuple[int, str]]] = {}
        
        flags = 0 if case_sensitive else re.IGNORECASE
        
        if fuzzy:
            # Use the shared safe fuzzy pattern function
            search_pattern = create_safe_fuzzy_pattern(pattern)
            search_regex = re.compile(search_pattern, flags)
        else:
            search_regex = re.compile(pattern, flags)

        for root, _, files in os.walk(base_path):
            for file in files:
                # Improved file pattern matching with glob support
                if file_pattern and not self._matches_pattern(file, file_pattern):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_path)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if search_regex.search(line):
                                if rel_path not in results:
                                    results[rel_path] = []
                                # Strip newline for consistent output
                                results[rel_path].append((line_num, line.rstrip('\n')))
                except (UnicodeDecodeError, PermissionError, OSError):
                    # Ignore files that can't be opened or read due to encoding/permission issues
                    continue
                except Exception:
                    # Ignore any other unexpected exceptions to maintain robustness
                    continue
        
        return results 