"""
Import path normalization utilities.

This module provides utilities for normalizing import paths across different
languages and import styles for consistent dependency classification.
"""

import re
import logging
from typing import Dict, List, Optional, Set, Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ImportNormalizer:
    """
    Import path normalization system.

    Provides language-specific import path normalization to ensure
    consistent classification regardless of import style variations.
    """

    def __init__(self):
        """Initialize the import normalizer."""
        self._normalizers: Dict[str, Callable[[str], str]] = {}
        self._setup_default_normalizers()

    def _setup_default_normalizers(self) -> None:
        """Setup default normalizers for supported languages."""
        self._normalizers.update({
            'python': self._normalize_python_import,
            'javascript': self._normalize_javascript_import,
            'typescript': self._normalize_javascript_import,  # Same as JS
            'zig': self._normalize_zig_import,
            'objective-c': self._normalize_objc_import,
            'java': self._normalize_java_import,
            'swift': self._normalize_swift_import,
            'go': self._normalize_go_import,
            'rust': self._normalize_rust_import,
        })

    def normalize_import_path(self, import_path: str, language: str) -> str:
        """
        Normalize an import path based on language-specific rules.

        Args:
            import_path: Raw import path to normalize
            language: Programming language

        Returns:
            Normalized import path
        """
        if not import_path:
            return import_path

        # Apply basic normalization first
        normalized = self._basic_normalize(import_path)

        # Apply language-specific normalization
        language_lower = language.lower()
        if language_lower in self._normalizers:
            normalized = self._normalizers[language_lower](normalized)

        logger.debug(f"Normalized {import_path} -> {normalized} ({language})")
        return normalized

    def _basic_normalize(self, import_path: str) -> str:
        """Apply basic normalization common to all languages."""
        # Strip whitespace
        normalized = import_path.strip()

        # Remove quotes if present
        if (normalized.startswith('"') and normalized.endswith('"')) or \
           (normalized.startswith("'") and normalized.endswith("'")):
            normalized = normalized[1:-1]

        # Remove semicolons at the end
        normalized = normalized.rstrip(';')

        return normalized

    def _normalize_python_import(self, import_path: str) -> str:
        """Normalize Python import paths."""
        normalized = import_path

        # Handle namespace packages
        if normalized.endswith('.__init__'):
            normalized = normalized[:-9]

        # Convert file paths to module paths
        normalized = normalized.replace('/', '.')
        normalized = normalized.replace('\\', '.')

        # Remove .py extension if present
        if normalized.endswith('.py'):
            normalized = normalized[:-3]

        # Normalize multiple dots in relative imports
        if normalized.startswith('.'):
            # Count leading dots
            dot_count = 0
            for char in normalized:
                if char == '.':
                    dot_count += 1
                else:
                    break

            # Reconstruct with normalized dots
            remaining = normalized[dot_count:]
            if remaining:
                normalized = '.' * dot_count + remaining
            else:
                normalized = '.' * dot_count

        return normalized

    def _normalize_javascript_import(self, import_path: str) -> str:
        """Normalize JavaScript/TypeScript import paths."""
        normalized = import_path

        # Handle URL imports (for Deno or web)
        if normalized.startswith(('http://', 'https://')):
            parsed = urlparse(normalized)
            # Extract package name from URL
            path_parts = parsed.path.strip('/').split('/')
            if path_parts:
                normalized = path_parts[0]  # Use first path component as package name

        # Remove common file extensions
        extensions = ['.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs', '.json']
        for ext in extensions:
            if normalized.endswith(ext):
                normalized = normalized[:-len(ext)]
                break

        # Remove /index suffix (common in Node.js)
        if normalized.endswith('/index'):
            normalized = normalized[:-6]

        # Handle scoped packages - ensure proper format
        if normalized.startswith('@') and '/' in normalized:
            parts = normalized.split('/')
            if len(parts) >= 2:
                # Keep only @scope/package part
                normalized = f"{parts[0]}/{parts[1]}"

        # Convert Windows paths to forward slashes
        normalized = normalized.replace('\\', '/')

        return normalized

    def _normalize_zig_import(self, import_path: str) -> str:
        """Normalize Zig import paths."""
        normalized = import_path

        # Remove .zig extension
        if normalized.endswith('.zig'):
            normalized = normalized[:-4]

        # Convert Windows paths to forward slashes
        normalized = normalized.replace('\\', '/')

        # Handle relative paths
        if normalized.startswith('./'):
            normalized = normalized[2:]
        elif normalized.startswith('../'):
            # Keep relative indicator but normalize
            pass

        return normalized

    def _normalize_objc_import(self, import_path: str) -> str:
        """Normalize Objective-C import paths."""
        normalized = import_path

        # Remove framework suffix
        if normalized.endswith('.framework'):
            normalized = normalized[:-10]

        # Remove common file extensions
        extensions = ['.h', '.m', '.mm']
        for ext in extensions:
            if normalized.endswith(ext):
                normalized = normalized[:-len(ext)]
                break

        # Extract framework name from paths
        if '/' in normalized:
            parts = normalized.split('/')
            # For framework imports, usually want the framework name
            # e.g., "UIKit/UIKit.h" -> "UIKit"
            if len(parts) >= 2 and parts[0] == parts[-1]:
                normalized = parts[0]
            else:
                # Use the last component
                normalized = parts[-1]

        return normalized

    def _normalize_java_import(self, import_path: str) -> str:
        """Normalize Java import paths."""
        normalized = import_path

        # Java imports are typically already normalized
        # But handle any file extensions that might be present
        if normalized.endswith('.java'):
            normalized = normalized[:-5]

        # Convert file paths to package notation
        normalized = normalized.replace('/', '.')
        normalized = normalized.replace('\\', '.')

        return normalized

    def _normalize_swift_import(self, import_path: str) -> str:
        """Normalize Swift import paths."""
        normalized = import_path

        # Remove .swift extension if present
        if normalized.endswith('.swift'):
            normalized = normalized[:-6]

        # Swift imports are typically module names, so minimal normalization needed
        return normalized

    def _normalize_go_import(self, import_path: str) -> str:
        """Normalize Go import paths."""
        normalized = import_path

        # Go imports are typically already well-formatted
        # Remove any .go extension that might be present
        if normalized.endswith('.go'):
            normalized = normalized[:-3]

        # Convert Windows paths to forward slashes
        normalized = normalized.replace('\\', '/')

        return normalized

    def _normalize_rust_import(self, import_path: str) -> str:
        """Normalize Rust import paths."""
        normalized = import_path

        # Remove .rs extension if present
        if normalized.endswith('.rs'):
            normalized = normalized[:-3]

        # Convert :: to / for consistency (though :: is correct Rust syntax)
        # This is for classification purposes only
        normalized = normalized.replace('::', '/')

        return normalized

    def register_normalizer(self, language: str, normalizer: Callable[[str], str]) -> None:
        """
        Register a custom normalizer for a language.

        Args:
            language: Language name
            normalizer: Function that takes import_path and returns normalized path
        """
        self._normalizers[language.lower()] = normalizer
        logger.debug(f"Registered custom normalizer for {language}")

    def get_supported_languages(self) -> Set[str]:
        """
        Get set of languages with custom normalizers.

        Returns:
            Set of supported language names
        """
        return set(self._normalizers.keys())

    def normalize_package_name(self, package_name: str, language: str) -> str:
        """
        Normalize a package name for consistent lookup.

        Args:
            package_name: Package name to normalize
            language: Programming language

        Returns:
            Normalized package name
        """
        normalized = package_name.strip().lower()

        # Language-specific package name normalization
        if language.lower() == 'python':
            # Python package names use hyphens and underscores interchangeably
            normalized = normalized.replace('_', '-')
        elif language.lower() in ['javascript', 'typescript']:
            # JavaScript packages typically use hyphens
            # But handle scoped packages specially
            if normalized.startswith('@'):
                pass  # Keep scoped packages as-is
            else:
                normalized = normalized.replace('_', '-')
        elif language.lower() == 'zig':
            # Zig packages typically use hyphens
            normalized = normalized.replace('_', '-')
        elif language.lower() == 'objective-c':
            # Objective-C frameworks use CamelCase, preserve case
            normalized = package_name.strip()

        return normalized

    def extract_base_package_name(self, import_path: str, language: str) -> str:
        """
        Extract the base package name from an import path.

        Args:
            import_path: Full import path
            language: Programming language

        Returns:
            Base package name
        """
        normalized = self.normalize_import_path(import_path, language)

        if language.lower() in ['javascript', 'typescript']:
            # Handle scoped packages
            if normalized.startswith('@'):
                parts = normalized.split('/')
                if len(parts) >= 2:
                    return f"{parts[0]}/{parts[1]}"
                return parts[0]
            else:
                return normalized.split('/')[0]

        elif language.lower() == 'python':
            # Python: first component of dotted path
            if normalized.startswith('.'):
                # Relative import, return as-is
                return normalized
            return normalized.split('.')[0]

        elif language.lower() == 'zig':
            # Zig: handle different import patterns
            if '/' in normalized:
                parts = normalized.split('/')
                if len(parts) == 2:
                    # owner/repo pattern
                    return normalized
                return parts[0]
            return normalized

        elif language.lower() == 'objective-c':
            # Objective-C: framework name
            return normalized

        else:
            # Default: first component
            return normalized.split('/')[0].split('.')[0]