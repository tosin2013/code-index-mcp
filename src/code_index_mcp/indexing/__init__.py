"""
Code indexing utilities for the MCP server.

This module provides simple JSON-based indexing optimized for LLM consumption.
"""

# Import utility functions that are still used
from .qualified_names import (
    generate_qualified_name,
    normalize_file_path
)

# New JSON-based indexing system
from .json_index_builder import JSONIndexBuilder, SymbolInfo, FileInfo, IndexMetadata
from .json_index_manager import JSONIndexManager, get_index_manager

__all__ = [
    'generate_qualified_name',
    'normalize_file_path',
    'JSONIndexBuilder',
    'JSONIndexManager',
    'get_index_manager',
    'SymbolInfo',
    'FileInfo', 
    'IndexMetadata'
]