"""
SCIP (Source Code Intelligence Protocol) indexing module.

This module provides SCIP-based code indexing capabilities using a modern
language manager approach to support various programming languages and tools.
"""

from .language_manager import SCIPLanguageManager, LanguageNotSupportedException, create_language_manager

__all__ = ['SCIPLanguageManager', 'LanguageNotSupportedException', 'create_language_manager']