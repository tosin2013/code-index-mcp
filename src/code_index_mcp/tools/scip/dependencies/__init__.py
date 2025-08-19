"""
Unified dependency classification and management system.

This package provides the dependency management system that replaces scattered
dependency logic throughout the SCIPSymbolAnalyzer, following the refactoring
plan for centralized and configurable dependency classification.

Key Components:
- DependencyClassifier: Main dependency classification engine
- DependencyConfig: Abstract base for language-specific configurations
- DependencyRegistry: Centralized registry and caching system
- ImportNormalizer: Import path normalization utilities

The system supports:
- Configurable classification rules per language
- Caching for performance optimization
- Standard library detection
- Third-party package identification
- Local/project import detection
- Custom classification rules
"""

from .classifier import DependencyClassifier
from .registry import DependencyRegistry
from .normalizer import ImportNormalizer
from .configs import get_dependency_config

__all__ = [
    'DependencyClassifier',
    'DependencyRegistry',
    'ImportNormalizer',
    'get_dependency_config'
]