"""
Code indexing utilities for the MCP server.

This module provides utility functions for duplicate detection and 
qualified name generation used by the SCIP indexing system.
"""

# Import utility functions that are still used
from .duplicate_detection import (
    detect_duplicate_functions,
    detect_duplicate_classes,
    get_duplicate_statistics,
    format_duplicate_report
)

from .qualified_names import (
    generate_qualified_name,
    normalize_file_path
)

# Simple models for backward compatibility
from .simple_models import CodeIndex

# SCIP builder is still used by the new architecture
from .scip_builder import SCIPIndexBuilder

__all__ = [
    'detect_duplicate_functions',
    'detect_duplicate_classes', 
    'get_duplicate_statistics',
    'format_duplicate_report',
    'generate_qualified_name',
    'normalize_file_path',
    'SCIPIndexBuilder',
    'CodeIndex'
]