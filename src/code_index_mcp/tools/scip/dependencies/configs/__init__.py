"""
Language-specific dependency configuration system.

This package provides language-specific dependency configurations that define
how imports and dependencies should be classified for each supported language.

Key Components:
- BaseDependencyConfig: Abstract base class for all configurations
- PythonConfig: Python-specific dependency rules
- ZigConfig: Zig-specific dependency rules
- JavaScriptConfig: JavaScript/TypeScript dependency rules
- ObjectiveCConfig: Objective-C framework classification rules

Each configuration defines:
- Standard library module sets
- Third-party package detection rules
- Local import patterns
- Package manager integration
- Custom classification logic
"""

from .base import BaseDependencyConfig
from .python import PythonDependencyConfig
from .zig import ZigDependencyConfig
from .javascript import JavaScriptDependencyConfig
from .objc import ObjectiveCDependencyConfig

# Configuration registry
_CONFIGS = {
    'python': PythonDependencyConfig,
    'zig': ZigDependencyConfig,
    'javascript': JavaScriptDependencyConfig,
    'typescript': JavaScriptDependencyConfig,  # TypeScript uses JS config
    'objective-c': ObjectiveCDependencyConfig,
}

def get_dependency_config(language: str) -> BaseDependencyConfig:
    """
    Get dependency configuration for the specified language.

    Args:
        language: Language name

    Returns:
        Language-specific dependency configuration
    """
    language_lower = language.lower()
    config_class = _CONFIGS.get(language_lower)

    if config_class:
        return config_class()

    # Return base config for unsupported languages
    return BaseDependencyConfig()

def register_dependency_config(language: str, config_class) -> None:
    """
    Register a custom dependency configuration.

    Args:
        language: Language name
        config_class: Configuration class
    """
    _CONFIGS[language.lower()] = config_class

__all__ = [
    'BaseDependencyConfig',
    'PythonDependencyConfig',
    'ZigDependencyConfig',
    'JavaScriptDependencyConfig',
    'ObjectiveCDependencyConfig',
    'get_dependency_config',
    'register_dependency_config'
]