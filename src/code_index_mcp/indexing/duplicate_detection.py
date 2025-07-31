"""
Duplicate detection utilities for code indexing.

This module provides utilities for detecting and reporting duplicate
function and class names across the indexed codebase.
"""

from typing import Dict, List, Set, Tuple, Any
from .models import CodeIndex
from .qualified_names import parse_qualified_name


def detect_duplicate_functions(index: CodeIndex) -> Dict[str, List[int]]:
    """
    Detect functions with duplicate names across files.
    
    Args:
        index: Complete code index
        
    Returns:
        Dictionary mapping function names to lists of file IDs where duplicates exist
    """
    duplicates = {}
    
    if 'function_to_file_id' in index.lookups:
        for func_name, file_ids in index.lookups['function_to_file_id'].items():
            if isinstance(file_ids, list) and len(file_ids) > 1:
                duplicates[func_name] = file_ids
    
    return duplicates


def detect_duplicate_classes(index: CodeIndex) -> Dict[str, List[int]]:
    """
    Detect classes with duplicate names across files.
    
    Args:
        index: Complete code index
        
    Returns:
        Dictionary mapping class names to lists of file IDs where duplicates exist
    """
    duplicates = {}
    
    if 'class_to_file_id' in index.lookups:
        for class_name, file_ids in index.lookups['class_to_file_id'].items():
            if isinstance(file_ids, list) and len(file_ids) > 1:
                duplicates[class_name] = file_ids
    
    return duplicates


def get_duplicate_statistics(index: CodeIndex) -> Dict[str, Any]:
    """
    Get comprehensive statistics about duplicate names in the index.
    
    Args:
        index: Complete code index
        
    Returns:
        Dictionary containing duplicate statistics
    """
    duplicate_functions = detect_duplicate_functions(index)
    duplicate_classes = detect_duplicate_classes(index)
    
    # Calculate total occurrences
    total_function_duplicates = sum(len(file_ids) for file_ids in duplicate_functions.values())
    total_class_duplicates = sum(len(file_ids) for file_ids in duplicate_classes.values())
    
    # Find most duplicated names
    most_duplicated_function = None
    max_function_count = 0
    for func_name, file_ids in duplicate_functions.items():
        if len(file_ids) > max_function_count:
            max_function_count = len(file_ids)
            most_duplicated_function = func_name
    
    most_duplicated_class = None
    max_class_count = 0
    for class_name, file_ids in duplicate_classes.items():
        if len(file_ids) > max_class_count:
            max_class_count = len(file_ids)
            most_duplicated_class = class_name
    
    return {
        'function_duplicates': {
            'count': len(duplicate_functions),
            'total_occurrences': total_function_duplicates,
            'most_duplicated': {
                'name': most_duplicated_function,
                'count': max_function_count
            },
            'names': list(duplicate_functions.keys())
        },
        'class_duplicates': {
            'count': len(duplicate_classes),
            'total_occurrences': total_class_duplicates,
            'most_duplicated': {
                'name': most_duplicated_class,
                'count': max_class_count
            },
            'names': list(duplicate_classes.keys())
        },
        'total_unique_functions': len(index.lookups.get('function_to_file_id', {})),
        'total_unique_classes': len(index.lookups.get('class_to_file_id', {})),
        'duplicate_percentage': {
            'functions': (len(duplicate_functions) / max(1, len(index.lookups.get('function_to_file_id', {})))) * 100,
            'classes': (len(duplicate_classes) / max(1, len(index.lookups.get('class_to_file_id', {})))) * 100
        }
    }


def get_file_paths_for_duplicates(index: CodeIndex, element_name: str, element_type: str = 'function') -> List[str]:
    """
    Get file paths for all instances of a duplicate element.
    
    Args:
        index: Complete code index
        element_name: Name of the function or class
        element_type: 'function' or 'class'
        
    Returns:
        List of file paths where the element appears
    """
    lookup_key = f"{element_type}_to_file_id"
    
    if lookup_key not in index.lookups:
        return []
    
    file_ids = index.lookups[lookup_key].get(element_name, [])
    if not isinstance(file_ids, list):
        file_ids = [file_ids]  # Handle old format
    
    file_paths = []
    for file_id in file_ids:
        # Find the file with this ID
        for file_entry in index.files:
            if file_entry.get('id') == file_id:
                file_paths.append(file_entry.get('path', f'unknown_file_{file_id}'))
                break
    
    return file_paths


def analyze_duplicate_relationships(index: CodeIndex) -> Dict[str, Any]:
    """
    Analyze relationships between duplicate elements.
    
    Args:
        index: Complete code index
        
    Returns:
        Dictionary containing relationship analysis for duplicates
    """
    analysis = {
        'cross_file_calls': [],
        'duplicate_call_patterns': [],
        'ambiguous_references': []
    }
    
    # Analyze reverse lookups for qualified names
    if hasattr(index, 'reverse_lookups') and index.reverse_lookups:
        function_callers = index.reverse_lookups.get('function_callers', {})
        
        # Look for qualified names in the callers
        for callee, callers in function_callers.items():
            try:
                # Check if this is a qualified name
                if ':' in callee:
                    file_path, func_name = parse_qualified_name(callee)
                    
                    # Check if the unqualified name also has entries
                    if func_name in function_callers:
                        analysis['cross_file_calls'].append({
                            'qualified_name': callee,
                            'unqualified_name': func_name,
                            'qualified_callers': len(callers),
                            'total_callers': len(function_callers[func_name])
                        })
                        
            except (ValueError, KeyError):
                continue
    
    return analysis


def format_duplicate_report(index: CodeIndex) -> str:
    """
    Generate a formatted report of duplicate names in the codebase.
    
    Args:
        index: Complete code index
        
    Returns:
        Formatted string report
    """
    stats = get_duplicate_statistics(index)
    duplicate_functions = detect_duplicate_functions(index)
    duplicate_classes = detect_duplicate_classes(index)
    
    report = []
    report.append("=" * 60)
    report.append("DUPLICATE NAMES DETECTION REPORT")
    report.append("=" * 60)
    report.append("")
    
    # Summary
    report.append("SUMMARY:")
    report.append(f"  Total unique functions: {stats['total_unique_functions']}")
    report.append(f"  Functions with duplicates: {stats['function_duplicates']['count']} ({stats['duplicate_percentage']['functions']:.1f}%)")
    report.append(f"  Total unique classes: {stats['total_unique_classes']}")
    report.append(f"  Classes with duplicates: {stats['class_duplicates']['count']} ({stats['duplicate_percentage']['classes']:.1f}%)")
    report.append("")
    
    # Function duplicates
    if duplicate_functions:
        report.append("DUPLICATE FUNCTIONS:")
        for func_name, file_ids in sorted(duplicate_functions.items()):
            file_paths = get_file_paths_for_duplicates(index, func_name, 'function')
            report.append(f"  {func_name} ({len(file_ids)} occurrences):")
            for path in file_paths:
                report.append(f"    - {path}")
        report.append("")
    
    # Class duplicates
    if duplicate_classes:
        report.append("DUPLICATE CLASSES:")
        for class_name, file_ids in sorted(duplicate_classes.items()):
            file_paths = get_file_paths_for_duplicates(index, class_name, 'class')
            report.append(f"  {class_name} ({len(file_ids)} occurrences):")
            for path in file_paths:
                report.append(f"    - {path}")
        report.append("")
    
    # Most duplicated
    if stats['function_duplicates']['most_duplicated']['name']:
        report.append("MOST DUPLICATED:")
        report.append(f"  Function: {stats['function_duplicates']['most_duplicated']['name']} ({stats['function_duplicates']['most_duplicated']['count']} occurrences)")
    
    if stats['class_duplicates']['most_duplicated']['name']:
        report.append(f"  Class: {stats['class_duplicates']['most_duplicated']['name']} ({stats['class_duplicates']['most_duplicated']['count']} occurrences)")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)