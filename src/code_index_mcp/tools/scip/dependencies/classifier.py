"""
Main dependency classifier engine.

This module provides the centralized DependencyClassifier that replaces scattered
dependency logic throughout the SCIPSymbolAnalyzer, supporting configurable
classification rules per language.
"""

import logging
from typing import Dict, Set, List, Optional, Any
from .configs import get_dependency_config, BaseDependencyConfig
from .registry import DependencyRegistry
from .normalizer import ImportNormalizer

logger = logging.getLogger(__name__)


class DependencyClassifier:
    """
    Main dependency classification engine.

    This class provides centralized dependency classification with support for:
    - Language-specific classification rules
    - Caching for performance optimization
    - Context-aware classification
    - Custom rule registration
    - Batch processing capabilities
    """

    def __init__(self):
        """Initialize the dependency classifier."""
        self._configs: Dict[str, BaseDependencyConfig] = {}
        self._registry = DependencyRegistry()
        self._normalizer = ImportNormalizer()
        self._context_cache: Dict[str, Dict[str, Any]] = {}

    def classify_import(
        self,
        import_path: str,
        language: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Classify an import path based on language-specific rules.

        Args:
            import_path: Import path to classify
            language: Programming language
            context: Optional context information (project structure, etc.)

        Returns:
            Classification: 'standard_library', 'third_party', or 'local'
        """
        if not import_path:
            return 'local'

        # Normalize the import path
        normalized_path = self._normalizer.normalize_import_path(import_path, language)

        # Check cache first
        cache_key = f"{language}:{normalized_path}"
        cached_result = self._registry.get_cached_classification(cache_key)
        if cached_result is not None:
            return cached_result

        # Get language-specific configuration
        config = self._get_config(language)

        # Perform classification
        classification = config.classify_import(normalized_path, context)

        # Cache the result
        self._registry.cache_classification(cache_key, classification)

        logger.debug(f"Classified {import_path} ({language}) as {classification}")
        return classification

    def classify_batch(
        self,
        imports: List[str],
        language: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Classify multiple imports efficiently.

        Args:
            imports: List of import paths to classify
            language: Programming language
            context: Optional context information

        Returns:
            Dictionary mapping import_path -> classification
        """
        results = {}
        config = self._get_config(language)

        for import_path in imports:
            if not import_path:
                results[import_path] = 'local'
                continue

            # Normalize the import path
            normalized_path = self._normalizer.normalize_import_path(import_path, language)

            # Check cache first
            cache_key = f"{language}:{normalized_path}"
            cached_result = self._registry.get_cached_classification(cache_key)

            if cached_result is not None:
                results[import_path] = cached_result
            else:
                # Perform classification
                classification = config.classify_import(normalized_path, context)
                results[import_path] = classification

                # Cache the result
                self._registry.cache_classification(cache_key, classification)

        logger.debug(f"Classified {len(imports)} imports for {language}")
        return results

    def get_standard_library_modules(self, language: str) -> Set[str]:
        """
        Get standard library modules for a language.

        Args:
            language: Programming language

        Returns:
            Set of standard library module names
        """
        config = self._get_config(language)
        return config.get_stdlib_modules()

    def is_standard_library(self, import_path: str, language: str) -> bool:
        """
        Check if an import is from the standard library.

        Args:
            import_path: Import path to check
            language: Programming language

        Returns:
            True if import is from standard library
        """
        return self.classify_import(import_path, language) == 'standard_library'

    def is_third_party(self, import_path: str, language: str) -> bool:
        """
        Check if an import is third-party.

        Args:
            import_path: Import path to check
            language: Programming language

        Returns:
            True if import is third-party
        """
        return self.classify_import(import_path, language) == 'third_party'

    def is_local(self, import_path: str, language: str) -> bool:
        """
        Check if an import is local.

        Args:
            import_path: Import path to check
            language: Programming language

        Returns:
            True if import is local
        """
        return self.classify_import(import_path, language) == 'local'

    def register_custom_config(self, language: str, config: BaseDependencyConfig) -> None:
        """
        Register a custom dependency configuration for a language.

        Args:
            language: Language name
            config: Custom configuration instance
        """
        self._configs[language.lower()] = config
        logger.debug(f"Registered custom dependency config for {language}")

    def update_context(self, project_path: str, context: Dict[str, Any]) -> None:
        """
        Update context information for a project.

        Args:
            project_path: Path to the project
            context: Context information to cache
        """
        self._context_cache[project_path] = context
        logger.debug(f"Updated context for project: {project_path}")

    def get_context(self, project_path: str) -> Optional[Dict[str, Any]]:
        """
        Get cached context information for a project.

        Args:
            project_path: Path to the project

        Returns:
            Cached context or None
        """
        return self._context_cache.get(project_path)

    def extract_dependencies_from_file(
        self,
        file_path: str,
        file_content: str,
        language: str
    ) -> List[str]:
        """
        Extract dependencies from package manager files.

        Args:
            file_path: Path to the package manager file
            file_content: Content of the file
            language: Programming language

        Returns:
            List of dependency names
        """
        config = self._get_config(language)
        return config.extract_dependencies_from_file(file_path, file_content)

    def get_package_manager_files(self, language: str) -> Set[str]:
        """
        Get package manager files for a language.

        Args:
            language: Programming language

        Returns:
            Set of package manager file names
        """
        config = self._get_config(language)
        return config.get_package_manager_files()

    def detect_package_version(
        self,
        package_name: str,
        language: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Detect version of a package if possible.

        Args:
            package_name: Name of the package
            language: Programming language
            context: Optional context information

        Returns:
            Package version or None if not detectable
        """
        config = self._get_config(language)
        if config.supports_version_detection():
            return config.detect_package_version(package_name, context)
        return None

    def get_supported_languages(self) -> Set[str]:
        """
        Get set of supported languages.

        Returns:
            Set of supported language names
        """
        # Languages supported by default configs
        supported = {'python', 'zig', 'javascript', 'typescript', 'objective-c'}
        # Add custom registered languages
        supported.update(self._configs.keys())
        return supported

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._registry.clear_cache()
        self._context_cache.clear()
        logger.debug("Cleared dependency classifier cache")

    def get_classification_stats(self) -> Dict[str, Any]:
        """
        Get statistics about classification operations.

        Returns:
            Dictionary with classification statistics
        """
        return self._registry.get_stats()

    def _get_config(self, language: str) -> BaseDependencyConfig:
        """
        Get or create configuration for a language.

        Args:
            language: Programming language

        Returns:
            Language-specific dependency configuration
        """
        language_lower = language.lower()

        # Check if we have a custom config
        if language_lower in self._configs:
            return self._configs[language_lower]

        # Get default config
        config = get_dependency_config(language_lower)
        self._configs[language_lower] = config

        return config


# Global classifier instance
_classifier_instance: Optional[DependencyClassifier] = None


def get_dependency_classifier() -> DependencyClassifier:
    """
    Get the global dependency classifier instance.

    Returns:
        Global DependencyClassifier instance
    """
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = DependencyClassifier()
    return _classifier_instance


def classify_import(
    import_path: str,
    language: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience function to classify an import.

    Args:
        import_path: Import path to classify
        language: Programming language
        context: Optional context information

    Returns:
        Classification string
    """
    return get_dependency_classifier().classify_import(import_path, language, context)


def get_standard_library_modules(language: str) -> Set[str]:
    """
    Convenience function to get standard library modules.

    Args:
        language: Programming language

    Returns:
        Set of standard library module names
    """
    return get_dependency_classifier().get_standard_library_modules(language)
