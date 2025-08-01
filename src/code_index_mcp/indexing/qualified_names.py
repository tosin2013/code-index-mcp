"""
Qualified name utilities for handling duplicate function and class names.

This module provides utilities for generating and parsing qualified names
in the format 'file_path:element_name' to disambiguate between same-named
elements in different files.
"""

from typing import Tuple
import os


def generate_qualified_name(file_path: str, element_name: str) -> str:
    """
    Generate qualified name in format: file_path:element_name
    
    Args:
        file_path: Relative file path (e.g., 'src/utils/helpers.py')
        element_name: Function or class name (e.g., 'format_data')
    
    Returns:
        Qualified name string (e.g., 'src/utils/helpers.py:format_data')
    """
    if not file_path or not element_name:
        raise ValueError("Both file_path and element_name must be non-empty")
    
    # Normalize path separators to forward slashes for consistency
    normalized_path = file_path.replace(os.sep, '/')
    
    return f"{normalized_path}:{element_name}"


def parse_qualified_name(qualified_name: str) -> Tuple[str, str]:
    """
    Parse qualified name into file_path and element_name components.
    
    Args:
        qualified_name: Qualified name string (e.g., 'src/utils/helpers.py:format_data')
    
    Returns:
        Tuple of (file_path, element_name)
    
    Raises:
        ValueError: If qualified name format is invalid
    """
    if not qualified_name:
        raise ValueError("Qualified name cannot be empty")
    
    # Split on the last colon to handle Windows paths with drive letters
    if ':' not in qualified_name:
        raise ValueError(f"Invalid qualified name format (missing ':'): {qualified_name}")
    
    # Find the last colon that's not part of a Windows drive letter
    parts = qualified_name.split(':')
    if len(parts) < 2:
        raise ValueError(f"Invalid qualified name format: {qualified_name}")
    
    # Handle Windows drive letters (e.g., 'C:\path\file.py:function')
    if len(parts) > 2 and len(parts[0]) == 1 and parts[0].isalpha():
        # Windows drive letter case: rejoin first two parts
        file_path = ':'.join(parts[:-1])
        element_name = parts[-1]
    else:
        # Normal case: split on last colon
        file_path = ':'.join(parts[:-1])
        element_name = parts[-1]
    
    if not file_path or not element_name:
        raise ValueError(f"Invalid qualified name format: {qualified_name}")
    
    return file_path, element_name


def validate_qualified_name(qualified_name: str) -> bool:
    """
    Validate qualified name format.
    
    Args:
        qualified_name: Qualified name string to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        parse_qualified_name(qualified_name)
        return True
    except ValueError:
        return False


def normalize_file_path(file_path: str) -> str:
    """
    Normalize file path for consistent use throughout the codebase.
    
    This function provides a unified way to normalize file paths by:
    1. Converting all path separators to forward slashes
    2. Normalizing the path structure (removing redundant separators, etc.)
    
    Args:
        file_path: File path to normalize
    
    Returns:
        Normalized file path with forward slashes
    """
    if not file_path:
        return file_path
    
    # First normalize the path structure, then convert separators
    normalized = os.path.normpath(file_path)
    return normalized.replace(os.sep, '/')


def get_file_path_from_qualified_name(qualified_name: str) -> str:
    """
    Extract file path from qualified name.
    
    Args:
        qualified_name: Qualified name string
    
    Returns:
        File path component
    
    Raises:
        ValueError: If qualified name format is invalid
    """
    file_path, _ = parse_qualified_name(qualified_name)
    return file_path


def get_element_name_from_qualified_name(qualified_name: str) -> str:
    """
    Extract element name from qualified name.
    
    Args:
        qualified_name: Qualified name string
    
    Returns:
        Element name component
    
    Raises:
        ValueError: If qualified name format is invalid
    """
    _, element_name = parse_qualified_name(qualified_name)
    return element_name