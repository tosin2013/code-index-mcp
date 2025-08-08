"""
SCIP (Source Code Intelligence Protocol) indexing module.

This module provides SCIP-based code indexing capabilities using a multi-strategy
approach to support various programming languages and tools.
"""

from .factory import SCIPIndexerFactory, SCIPIndexingError

__all__ = ['SCIPIndexerFactory', 'SCIPIndexingError']