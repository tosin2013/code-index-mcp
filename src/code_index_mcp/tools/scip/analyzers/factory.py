"""
Language analyzer factory and registry.

This module provides the factory pattern for creating language-specific analyzers
based on document language or file extension, following the SCIP Symbol Analyzer
refactoring plan.
"""

import logging
from typing import Dict, Optional, Type, Set
from .base import LanguageAnalyzer, FallbackAnalyzer
from .python_analyzer import PythonAnalyzer
from .zig_analyzer import ZigAnalyzer
from .objc_analyzer import ObjectiveCAnalyzer
from .javascript_analyzer import JavaScriptAnalyzer

logger = logging.getLogger(__name__)


class LanguageAnalyzerFactory:
    """
    Factory for creating language-specific analyzers.

    This factory provides centralized management of language analyzers,
    supporting dynamic registration and language detection based on
    various criteria.
    """

    def __init__(self):
        """Initialize the factory with default analyzers."""
        self._analyzers: Dict[str, Type[LanguageAnalyzer]] = {}
        self._file_extension_map: Dict[str, str] = {}
        self._language_aliases: Dict[str, str] = {}
        self._analyzer_instances: Dict[str, LanguageAnalyzer] = {}

        # Register default analyzers
        self._register_default_analyzers()
        self._setup_file_extension_mapping()
        self._setup_language_aliases()

    def _register_default_analyzers(self) -> None:
        """Register all default language analyzers."""
        self.register_analyzer('python', PythonAnalyzer)
        self.register_analyzer('zig', ZigAnalyzer)
        self.register_analyzer('objective-c', ObjectiveCAnalyzer)
        self.register_analyzer('javascript', JavaScriptAnalyzer)
        self.register_analyzer('typescript', JavaScriptAnalyzer)  # TypeScript uses JS analyzer
        self.register_analyzer('fallback', FallbackAnalyzer)

    def _setup_file_extension_mapping(self) -> None:
        """Setup mapping from file extensions to language names."""
        self._file_extension_map = {
            # Python
            '.py': 'python',
            '.pyx': 'python',
            '.pyi': 'python',
            '.pyw': 'python',

            # Zig
            '.zig': 'zig',

            # Objective-C
            '.m': 'objective-c',
            '.mm': 'objective-c',
            '.h': 'objective-c',  # Could be C/C++ too, but often ObjC in iOS/macOS projects

            # JavaScript/TypeScript
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.mjs': 'javascript',
            '.cjs': 'javascript',

            # Other languages that might be added later
            '.java': 'java',
            '.kt': 'kotlin',
            '.swift': 'swift',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.php': 'php',
            '.scala': 'scala',
            '.clj': 'clojure',
            '.sh': 'shell',
            '.bash': 'shell',
            '.zsh': 'shell',
            '.fish': 'shell'
        }

    def _setup_language_aliases(self) -> None:
        """Setup aliases for language names."""
        self._language_aliases = {
            # Python aliases
            'py': 'python',
            'python3': 'python',

            # JavaScript/TypeScript aliases
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'ecmascript': 'javascript',
            'node': 'javascript',
            'nodejs': 'javascript',

            # Objective-C aliases
            'objc': 'objective-c',
            'obj-c': 'objective-c',
            'objective_c': 'objective-c',
            'objectivec': 'objective-c',

            # Other aliases
            'zigc': 'zig',
            'c++': 'cpp',
            'c#': 'csharp',
            'dotnet': 'csharp'
        }

    def register_analyzer(self, language: str, analyzer_class: Type[LanguageAnalyzer]) -> None:
        """
        Register a language analyzer.

        Args:
            language: Language name (canonical form)
            analyzer_class: Analyzer class to register
        """
        self._analyzers[language.lower()] = analyzer_class
        logger.debug(f"Registered analyzer for language: {language}")

    def get_analyzer(self, language: str = None, file_path: str = None) -> LanguageAnalyzer:
        """
        Get appropriate analyzer for the given language or file.

        Args:
            language: Language name (if known)
            file_path: File path (for extension-based detection)

        Returns:
            Language-specific analyzer or fallback analyzer
        """
        detected_language = self._detect_language(language, file_path)

        # Return cached instance if available
        if detected_language in self._analyzer_instances:
            return self._analyzer_instances[detected_language]

        # Create new instance
        analyzer_class = self._analyzers.get(detected_language)
        if analyzer_class:
            try:
                analyzer = analyzer_class()
                self._analyzer_instances[detected_language] = analyzer
                return analyzer
            except Exception as e:
                logger.warning(f"Failed to create analyzer for {detected_language}: {e}")

        # Fallback to default analyzer
        if 'fallback' not in self._analyzer_instances:
            self._analyzer_instances['fallback'] = FallbackAnalyzer()

        return self._analyzer_instances['fallback']

    def _detect_language(self, language: str = None, file_path: str = None) -> str:
        """
        Detect language from various hints.

        Args:
            language: Explicit language hint
            file_path: File path for extension-based detection

        Returns:
            Detected language name (normalized)
        """
        # Method 1: Use explicit language if provided
        if language:
            normalized = self._normalize_language(language)
            if normalized in self._analyzers:
                return normalized

        # Method 2: Detect from file extension
        if file_path:
            file_extension = self._get_file_extension(file_path)
            if file_extension in self._file_extension_map:
                detected = self._file_extension_map[file_extension]
                if detected in self._analyzers:
                    return detected

        # Method 3: Detect from file path patterns
        if file_path:
            path_based = self._detect_from_path_patterns(file_path)
            if path_based and path_based in self._analyzers:
                return path_based

        # Default to fallback
        return 'fallback'

    def _normalize_language(self, language: str) -> str:
        """
        Normalize language name using aliases.

        Args:
            language: Raw language name

        Returns:
            Normalized language name
        """
        language_lower = language.lower().strip()

        # Check aliases first
        if language_lower in self._language_aliases:
            return self._language_aliases[language_lower]

        # Return as-is if no alias found
        return language_lower

    def _get_file_extension(self, file_path: str) -> str:
        """
        Extract file extension from path.

        Args:
            file_path: File path

        Returns:
            File extension (including dot)
        """
        try:
            if '.' in file_path:
                return '.' + file_path.split('.')[-1].lower()
        except Exception:
            pass
        return ''

    def _detect_from_path_patterns(self, file_path: str) -> Optional[str]:
        """
        Detect language from file path patterns.

        Args:
            file_path: File path

        Returns:
            Detected language or None
        """
        path_lower = file_path.lower()

        # JavaScript/TypeScript project patterns
        if any(pattern in path_lower for pattern in ['node_modules', 'package.json', 'tsconfig']):
            if any(ext in path_lower for ext in ['.ts', '.tsx']):
                return 'typescript'
            return 'javascript'

        # Python project patterns
        if any(pattern in path_lower for pattern in ['__pycache__', 'requirements.txt', 'setup.py', '.py']):
            return 'python'

        # Zig project patterns
        if any(pattern in path_lower for pattern in ['build.zig', '.zig']):
            return 'zig'

        # Objective-C project patterns
        if any(pattern in path_lower for pattern in ['.xcodeproj', '.xcworkspace', 'podfile']):
            return 'objective-c'

        return None

    def get_supported_languages(self) -> Set[str]:
        """
        Get set of supported languages.

        Returns:
            Set of supported language names
        """
        return set(self._analyzers.keys())

    def get_supported_extensions(self) -> Set[str]:
        """
        Get set of supported file extensions.

        Returns:
            Set of supported file extensions
        """
        return set(self._file_extension_map.keys())

    def is_language_supported(self, language: str) -> bool:
        """
        Check if a language is supported.

        Args:
            language: Language name to check

        Returns:
            True if language is supported
        """
        normalized = self._normalize_language(language)
        return normalized in self._analyzers

    def clear_cache(self) -> None:
        """Clear cached analyzer instances."""
        self._analyzer_instances.clear()
        logger.debug("Cleared analyzer instance cache")

    def get_analyzer_info(self) -> Dict[str, Dict[str, any]]:
        """
        Get information about registered analyzers.

        Returns:
            Dictionary with analyzer information
        """
        info = {}
        for language, analyzer_class in self._analyzers.items():
            try:
                analyzer = analyzer_class()
                info[language] = {
                    'class': analyzer_class.__name__,
                    'supported_extensions': [
                        ext for ext, lang in self._file_extension_map.items()
                        if lang == language
                    ],
                    'aliases': [
                        alias for alias, canonical in self._language_aliases.items()
                        if canonical == language
                    ],
                    'standard_library_modules': len(analyzer.get_standard_library_modules())
                }
            except Exception as e:
                info[language] = {
                    'class': analyzer_class.__name__,
                    'error': str(e)
                }

        return info


# Global factory instance
_factory_instance: Optional[LanguageAnalyzerFactory] = None


def get_analyzer_factory() -> LanguageAnalyzerFactory:
    """
    Get the global analyzer factory instance.

    Returns:
        Global LanguageAnalyzerFactory instance
    """
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = LanguageAnalyzerFactory()
    return _factory_instance


def get_analyzer(language: str = None, file_path: str = None) -> LanguageAnalyzer:
    """
    Convenience function to get a language analyzer.

    Args:
        language: Language name (if known)
        file_path: File path (for extension-based detection)

    Returns:
        Appropriate language analyzer
    """
    return get_analyzer_factory().get_analyzer(language, file_path)


def register_custom_analyzer(language: str, analyzer_class: Type[LanguageAnalyzer]) -> None:
    """
    Register a custom language analyzer.

    Args:
        language: Language name
        analyzer_class: Custom analyzer class
    """
    get_analyzer_factory().register_analyzer(language, analyzer_class)


def get_supported_languages() -> Set[str]:
    """Get set of all supported languages."""
    return get_analyzer_factory().get_supported_languages()
