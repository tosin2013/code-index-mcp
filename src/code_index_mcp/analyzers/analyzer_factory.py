"""Factory for creating language-specific analyzers."""

from typing import Dict, Type, Optional
from .base_analyzer import LanguageAnalyzer
from .default_analyzer import DefaultAnalyzer
from .python_analyzer import PythonAnalyzer
from .javascript_analyzer import JavaScriptAnalyzer
from .java_analyzer import JavaAnalyzer
from .objective_c_analyzer import ObjectiveCAnalyzer
from .zig_analyzer import ZigAnalyzer


class AnalyzerFactory:
    """Factory class for creating language-specific analyzers."""

    _analyzers: Dict[str, Type[LanguageAnalyzer]] = {}

    @classmethod
    def register(cls, extensions: list[str], analyzer_class: Type[LanguageAnalyzer]) -> None:
        """
        Register an analyzer for specific file extensions.

        Args:
            extensions: List of file extensions (e.g., ['.py', '.pyx'])
            analyzer_class: The analyzer class to register
        """
        for extension in extensions:
            cls._analyzers[extension.lower()] = analyzer_class

    @classmethod
    def get_analyzer(cls, extension: str) -> LanguageAnalyzer:
        """
        Get an analyzer instance for the given file extension.

        Args:
            extension: The file extension (e.g., '.py')

        Returns:
            Language analyzer instance, or DefaultAnalyzer if not found
        """
        extension = extension.lower()
        analyzer_class = cls._analyzers.get(extension, DefaultAnalyzer)
        # Create instance
        return analyzer_class()

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """
        Get all supported file extensions.

        Returns:
            List of all registered extensions
        """
        return list(cls._analyzers.keys())

    @classmethod
    def is_extension_supported(cls, extension: str) -> bool:
        """
        Check if an extension has a specific analyzer.

        Args:
            extension: The file extension to check

        Returns:
            True if a specific analyzer exists for the extension
        """
        return extension.lower() in cls._analyzers


# Initialize factory with built-in analyzers
def _initialize_factory():
    """Initialize the factory with built-in analyzers."""
    # Register analyzers
    AnalyzerFactory.register(['.py'], PythonAnalyzer)
    AnalyzerFactory.register(['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'], JavaScriptAnalyzer)
    AnalyzerFactory.register(['.java'], JavaAnalyzer)
    AnalyzerFactory.register(['.m', '.mm'], ObjectiveCAnalyzer)
    AnalyzerFactory.register(['.zig', '.zon'], ZigAnalyzer)


# Initialize on import
_initialize_factory()
