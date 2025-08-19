"""
Base interfaces and common utilities for language-specific SCIP analyzers.

This module provides the abstract base classes and shared functionality for the
modular language analyzer system, following the SCIP Symbol Analyzer refactoring plan.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Set
from ..symbol_definitions import ImportGroup, LocationInfo

logger = logging.getLogger(__name__)


class LanguageAnalyzer(ABC):
    """
    Abstract base class for language-specific SCIP symbol analyzers.

    Each language analyzer handles language-specific logic for:
    - Import extraction and classification
    - Symbol metadata enrichment
    - Dependency classification
    - Standard library module detection
    """

    def __init__(self):
        """Initialize the language analyzer."""
        self._cache: Dict[str, Any] = {}
        self.language_name = self._get_language_name()

    @abstractmethod
    def _get_language_name(self) -> str:
        """Return the name of the language this analyzer handles."""
        pass

    @abstractmethod
    def extract_imports(self, document, imports: ImportGroup, symbol_parser=None) -> None:
        """
        Extract import information from SCIP document.

        Args:
            document: SCIP document containing symbols and occurrences
            imports: ImportGroup to populate with extracted imports
            symbol_parser: Optional SCIPSymbolManager for enhanced parsing
        """
        pass

    @abstractmethod
    def classify_dependency(self, module_name: str) -> str:
        """
        Classify dependency as standard_library, third_party, or local.

        Args:
            module_name: Name of the module/dependency to classify

        Returns:
            Classification string: 'standard_library', 'third_party', or 'local'
        """
        pass

    @abstractmethod
    def extract_symbol_metadata(self, symbol_info, document) -> Dict[str, Any]:
        """
        Extract language-specific symbol metadata.

        Args:
            symbol_info: SCIP symbol information object
            document: SCIP document containing the symbol

        Returns:
            Dictionary with language-specific metadata
        """
        pass

    @abstractmethod
    def get_standard_library_modules(self) -> Set[str]:
        """
        Return set of standard library module names for this language.

        Returns:
            Set of standard library module names
        """
        pass

    def normalize_import_path(self, raw_path: str) -> str:
        """
        Normalize import path for consistent processing.
        Default implementation returns the path as-is.

        Args:
            raw_path: Raw import path from SCIP data

        Returns:
            Normalized import path
        """
        return raw_path.strip()

    def is_import_occurrence(self, occurrence) -> bool:
        """
        Check if occurrence represents an import statement.
        Default implementation checks for Import role (role = 2).

        Args:
            occurrence: SCIP occurrence object

        Returns:
            True if this occurrence is an import
        """
        return hasattr(occurrence, 'symbol_roles') and (occurrence.symbol_roles & 2)

    def extract_module_from_symbol(self, symbol: str, descriptors: str = "") -> Optional[str]:
        """
        Extract module name from SCIP symbol.
        Default implementation for common patterns.

        Args:
            symbol: SCIP symbol string
            descriptors: SCIP descriptors if available

        Returns:
            Module name or None if not extractable
        """
        try:
            if descriptors and '/' in descriptors:
                # Extract from descriptors: module.py/symbol -> module
                parts = descriptors.split('/')
                if len(parts) >= 2:
                    file_part = parts[0]
                    if file_part.endswith('.py'):
                        return file_part[:-3].replace('/', '.')
                    return file_part.replace('/', '.')

            # Fallback: parse from symbol string
            if symbol.startswith('external:'):
                symbol_path = symbol[9:]
                if '/' in symbol_path:
                    return symbol_path.split('/')[0]
                elif '#' in symbol_path:
                    return symbol_path.split('#')[0]
                return symbol_path.rstrip('.')

        except Exception as e:
            logger.debug(f"Error extracting module from symbol {symbol}: {e}")

        return None


class AnalyzerCache:
    """Shared caching system for analyzer results."""

    def __init__(self):
        self._symbol_cache: Dict[str, Dict[str, Any]] = {}
        self._dependency_cache: Dict[str, str] = {}
        self._module_cache: Dict[str, Set[str]] = {}

    def cache_symbol_metadata(self, symbol: str, metadata: Dict[str, Any]) -> None:
        """Cache symbol metadata."""
        self._symbol_cache[symbol] = metadata

    def get_cached_symbol_metadata(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached symbol metadata."""
        return self._symbol_cache.get(symbol)

    def cache_dependency_classification(self, module: str, classification: str) -> None:
        """Cache dependency classification result."""
        self._dependency_cache[module] = classification

    def get_cached_dependency_classification(self, module: str) -> Optional[str]:
        """Retrieve cached dependency classification."""
        return self._dependency_cache.get(module)

    def cache_standard_library_modules(self, language: str, modules: Set[str]) -> None:
        """Cache standard library modules for a language."""
        self._module_cache[language] = modules

    def get_cached_standard_library_modules(self, language: str) -> Optional[Set[str]]:
        """Retrieve cached standard library modules."""
        return self._module_cache.get(language)


class BaseLanguageAnalyzer(LanguageAnalyzer):
    """
    Base implementation providing common functionality for language analyzers.

    This class provides default implementations for common patterns while
    requiring subclasses to implement language-specific logic.
    """

    def __init__(self):
        super().__init__()
        self._cache = AnalyzerCache()
        self._standard_library_modules: Optional[Set[str]] = None

    def get_standard_library_modules(self) -> Set[str]:
        """
        Get standard library modules with caching.

        Returns:
            Set of standard library module names
        """
        if self._standard_library_modules is None:
            cached = self._cache.get_cached_standard_library_modules(self.language_name)
            if cached is not None:
                self._standard_library_modules = cached
            else:
                self._standard_library_modules = self._build_standard_library_modules()
                self._cache.cache_standard_library_modules(self.language_name, self._standard_library_modules)

        return self._standard_library_modules

    @abstractmethod
    def _build_standard_library_modules(self) -> Set[str]:
        """Build the set of standard library modules for this language."""
        pass

    def classify_dependency(self, module_name: str) -> str:
        """
        Classify dependency with caching support.

        Args:
            module_name: Name of the module to classify

        Returns:
            Classification string
        """
        # Check cache first
        cached = self._cache.get_cached_dependency_classification(module_name)
        if cached is not None:
            return cached

        # Perform classification
        classification = self._classify_dependency_impl(module_name)

        # Cache result
        self._cache.cache_dependency_classification(module_name, classification)

        return classification

    @abstractmethod
    def _classify_dependency_impl(self, module_name: str) -> str:
        """Implement the actual dependency classification logic."""
        pass

    def extract_symbol_metadata(self, symbol_info, document) -> Dict[str, Any]:
        """
        Extract symbol metadata with caching.

        Args:
            symbol_info: SCIP symbol information
            document: SCIP document

        Returns:
            Dictionary with symbol metadata
        """
        symbol = getattr(symbol_info, 'symbol', '')
        if not symbol:
            return {}

        # Check cache
        cached = self._cache.get_cached_symbol_metadata(symbol)
        if cached is not None:
            return cached

        # Extract metadata
        metadata = self._extract_symbol_metadata_impl(symbol_info, document)

        # Cache result
        self._cache.cache_symbol_metadata(symbol, metadata)

        return metadata

    @abstractmethod
    def _extract_symbol_metadata_impl(self, symbol_info, document) -> Dict[str, Any]:
        """Implement language-specific symbol metadata extraction."""
        pass


class FallbackAnalyzer(BaseLanguageAnalyzer):
    """
    Fallback analyzer for unsupported languages.

    Provides basic functionality when no language-specific analyzer is available.
    """

    def _get_language_name(self) -> str:
        return "fallback"

    def _build_standard_library_modules(self) -> Set[str]:
        """Fallback has no standard library modules."""
        return set()

    def _classify_dependency_impl(self, module_name: str) -> str:
        """Basic classification for unknown languages."""
        if module_name.startswith('.'):
            return 'local'
        # Default to third_party for unknown languages
        return 'third_party'

    def extract_imports(self, document, imports: ImportGroup, symbol_parser=None) -> None:
        """Basic import extraction using occurrence analysis."""
        try:
            seen_modules = set()

            for occurrence in document.occurrences:
                if not self.is_import_occurrence(occurrence):
                    continue

                symbol = occurrence.symbol
                module_name = self.extract_module_from_symbol(symbol)
                if module_name and module_name not in seen_modules:
                    classification = self.classify_dependency(module_name)
                    imports.add_import(module_name, classification)
                    seen_modules.add(module_name)

        except Exception as e:
            logger.debug(f"Error in fallback import extraction: {e}")

    def _extract_symbol_metadata_impl(self, symbol_info, document) -> Dict[str, Any]:
        """Basic metadata extraction for fallback."""
        return {
            'source': 'fallback',
            'confidence': 'low'
        }
