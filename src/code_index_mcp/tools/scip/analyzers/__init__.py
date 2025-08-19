"""
Language-specific SCIP symbol analyzers.

This package provides the modular language analyzer system that replaces the
monolithic SCIPSymbolAnalyzer, following the refactoring plan for better
maintainability and extensibility.

Key Components:
- LanguageAnalyzer: Abstract base class for all language analyzers
- PythonAnalyzer: Python-specific import and symbol analysis
- ZigAnalyzer: Zig-specific import and symbol analysis
- ObjectiveCAnalyzer: Objective-C framework and symbol analysis
- JavaScriptAnalyzer: JavaScript/TypeScript analysis
- LanguageAnalyzerFactory: Factory for creating appropriate analyzers
- FallbackAnalyzer: Generic analyzer for unsupported languages

Usage:
    from .factory import get_analyzer

    # Get analyzer for Python file
    analyzer = get_analyzer(language='python')

    # Get analyzer based on file extension
    analyzer = get_analyzer(file_path='main.py')

    # Extract imports
    analyzer.extract_imports(document, imports, symbol_parser)
"""

from .base import LanguageAnalyzer, BaseLanguageAnalyzer, FallbackAnalyzer
from .python_analyzer import PythonAnalyzer
from .zig_analyzer import ZigAnalyzer
from .objc_analyzer import ObjectiveCAnalyzer
from .javascript_analyzer import JavaScriptAnalyzer
from .factory import (
    LanguageAnalyzerFactory,
    get_analyzer_factory,
    get_analyzer,
    register_custom_analyzer,
    get_supported_languages
)

__all__ = [
    # Base classes
    'LanguageAnalyzer',
    'BaseLanguageAnalyzer',
    'FallbackAnalyzer',

    # Language-specific analyzers
    'PythonAnalyzer',
    'ZigAnalyzer',
    'ObjectiveCAnalyzer',
    'JavaScriptAnalyzer',

    # Factory and utilities
    'LanguageAnalyzerFactory',
    'get_analyzer_factory',
    'get_analyzer',
    'register_custom_analyzer',
    'get_supported_languages'
]