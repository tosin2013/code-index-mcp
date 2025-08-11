"""
Code indexing utilities for the MCP server.

This module provides utility functions for duplicate detection and 
qualified name generation used by the SCIP indexing system.
"""

# Import utility functions that are still used
from .qualified_names import (
    generate_qualified_name,
    normalize_file_path
)

# SCIP builder is still used by the new architecture
from .scip_builder import SCIPIndexBuilder

__all__ = [
    'generate_qualified_name',
    'normalize_file_path',
    'SCIPIndexBuilder'
]