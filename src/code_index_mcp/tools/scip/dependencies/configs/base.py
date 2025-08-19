"""
Base dependency configuration class.

This module provides the abstract base class for language-specific dependency
configurations, defining the interface and common functionality.
"""

import logging
from abc import ABC, abstractmethod
from typing import Set, Dict, List, Optional, Pattern
import re

logger = logging.getLogger(__name__)


class BaseDependencyConfig(ABC):
    """
    Abstract base class for language-specific dependency configurations.

    Each language configuration defines how to classify imports and dependencies
    as standard_library, third_party, or local based on language-specific patterns.
    """

    def __init__(self):
        """Initialize the dependency configuration."""
        self._stdlib_modules: Optional[Set[str]] = None
        self._third_party_patterns: List[Pattern] = []
        self._local_patterns: List[Pattern] = []
        self._package_manager_indicators: Set[str] = set()

        # Initialize patterns
        self._compile_patterns()

    @abstractmethod
    def get_language_name(self) -> str:
        """Return the language name this configuration handles."""
        pass

    @abstractmethod
    def get_stdlib_modules(self) -> Set[str]:
        """Return set of standard library modules for this language."""
        pass

    def classify_import(self, import_path: str, context: Dict[str, any] = None) -> str:
        """
        Classify import path based on language-specific rules.

        Args:
            import_path: Import path to classify
            context: Optional context information (file path, project structure, etc.)

        Returns:
            Classification: 'standard_library', 'third_party', or 'local'
        """
        if not import_path:
            return 'local'  # Default for empty imports

        # Step 1: Check for obvious local patterns first
        if self._is_local_import(import_path, context):
            return 'local'

        # Step 2: Check standard library
        if self._is_stdlib_import(import_path):
            return 'standard_library'

        # Step 3: Check third-party patterns
        if self._is_third_party_import(import_path, context):
            return 'third_party'

        # Step 4: Language-specific classification
        return self._classify_import_impl(import_path, context)

    def normalize_import_path(self, raw_path: str) -> str:
        """
        Normalize import path for consistent processing.
        Default implementation just strips whitespace.

        Args:
            raw_path: Raw import path

        Returns:
            Normalized import path
        """
        return raw_path.strip()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        try:
            # Default patterns - subclasses should override
            self._third_party_patterns = [
                re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$'),  # Simple package names
            ]

            self._local_patterns = [
                re.compile(r'^\.'),  # Relative imports
                re.compile(r'^/'),   # Absolute local paths
            ]
        except Exception as e:
            logger.warning(f"Error compiling patterns for {self.get_language_name()}: {e}")

    def _is_local_import(self, import_path: str, context: Dict[str, any] = None) -> bool:
        """Check if import is local based on patterns."""
        # Relative imports are always local
        if import_path.startswith('.'):
            return True

        # Check compiled patterns
        for pattern in self._local_patterns:
            if pattern.match(import_path):
                return True

        # Context-based checks
        if context:
            # Check against project-specific patterns
            project_indicators = context.get('project_patterns', [])
            for indicator in project_indicators:
                if indicator in import_path:
                    return True

        return False

    def _is_stdlib_import(self, import_path: str) -> bool:
        """Check if import is from standard library."""
        if self._stdlib_modules is None:
            self._stdlib_modules = self.get_stdlib_modules()

        # Extract base module name
        base_module = import_path.split('.')[0].split('/')[0]
        return base_module in self._stdlib_modules

    def _is_third_party_import(self, import_path: str, context: Dict[str, any] = None) -> bool:
        """Check if import is third-party based on patterns."""
        # Check compiled patterns
        for pattern in self._third_party_patterns:
            if pattern.match(import_path):
                return True

        # Check package manager indicators
        if context:
            package_indicators = context.get('package_indicators', set())
            for indicator in package_indicators:
                if indicator in import_path:
                    return True

        return False

    def _classify_import_impl(self, import_path: str, context: Dict[str, any] = None) -> str:
        """
        Language-specific import classification implementation.
        Default implementation returns 'third_party' for unknown imports.

        Args:
            import_path: Import path to classify
            context: Optional context information

        Returns:
            Classification string
        """
        return 'third_party'

    def get_package_manager_files(self) -> Set[str]:
        """
        Return set of package manager files for this language.
        Used to detect project structure and third-party dependencies.

        Returns:
            Set of package manager file names
        """
        return set()

    def extract_dependencies_from_file(self, file_path: str, file_content: str) -> List[str]:
        """
        Extract dependency list from package manager files.

        Args:
            file_path: Path to the package manager file
            file_content: Content of the file

        Returns:
            List of dependency names
        """
        # Default implementation returns empty list
        # Subclasses should implement language-specific parsing
        return []

    def is_scoped_package(self, import_path: str) -> bool:
        """
        Check if import represents a scoped package.

        Args:
            import_path: Import path to check

        Returns:
            True if import is a scoped package
        """
        # Default implementation - no scoped packages
        return False

    def get_package_name_from_import(self, import_path: str) -> str:
        """
        Extract package name from import path.

        Args:
            import_path: Full import path

        Returns:
            Package name (first component typically)
        """
        # Default implementation: return first component
        if '/' in import_path:
            return import_path.split('/')[0]
        elif '.' in import_path:
            return import_path.split('.')[0]
        return import_path

    def supports_version_detection(self) -> bool:
        """
        Check if this configuration supports version detection.

        Returns:
            True if version detection is supported
        """
        return False

    def detect_package_version(self, package_name: str, context: Dict[str, any] = None) -> Optional[str]:
        """
        Detect version of a package if possible.

        Args:
            package_name: Name of the package
            context: Optional context (lock files, manifests, etc.)

        Returns:
            Package version or None if not detectable
        """
        return None
