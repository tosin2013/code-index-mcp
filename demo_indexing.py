#!/usr/bin/env python3
"""
Demo script for the new code indexing system.

This script demonstrates the capabilities of the new structured indexing system,
showing how it analyzes code structure, relationships, and provides rich metadata.
"""

import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from code_index_mcp.indexing import IndexBuilder


def demo_indexing():
    """Demonstrate the indexing system on the current project."""
    print("🔍 Code Indexing System Demo")
    print("=" * 50)
    
    # Build index for current project
    project_path = "."
    print(f"📁 Analyzing project: {os.path.abspath(project_path)}")
    
    builder = IndexBuilder()
    index = builder.build_index(project_path)
    
    # Display project metadata
    print(f"\n📊 Project Metadata:")
    print(f"   Name: {index.project_metadata['name']}")
    print(f"   Total Files: {index.project_metadata['total_files']}")
    print(f"   Total Lines: {index.project_metadata['total_lines']}")
    print(f"   Indexed At: {index.project_metadata['indexed_at']}")
    
    # Display index metadata
    print(f"\n🔧 Index Metadata:")
    print(f"   Version: {index.index_metadata['version']}")
    print(f"   Analysis Time: {index.index_metadata['analysis_time_ms']}ms")
    print(f"   Languages: {', '.join(index.index_metadata['languages_analyzed'])}")
    # Removed supports field as it was not useful
    
    # Display file analysis
    print(f"\n📄 File Analysis:")
    python_files = [f for f in index.files if f['language'] == 'python']
    print(f"   Python files: {len(python_files)}")
    
    # Show some Python files with their functions and classes
    for file_info in python_files[:3]:  # Show first 3 Python files
        print(f"   📝 {file_info['path']}:")
        if file_info['functions']:
            func_names = [f['name'] for f in file_info['functions']]
            print(f"      Functions: {', '.join(func_names[:5])}")  # Show first 5
        if file_info['classes']:
            class_names = [c['name'] for c in file_info['classes']]
            print(f"      Classes: {', '.join(class_names)}")
    
    # Display special files
    print(f"\n📋 Special Files:")
    for category, files in index.special_files.items():
        if files:
            print(f"   {category.replace('_', ' ').title()}: {len(files)} files")
            for file_path in files[:3]:  # Show first 3 files in each category
                print(f"      - {file_path}")
    
    # Display directory structure (simplified)
    print(f"\n🌳 Directory Structure:")
    def print_tree(tree, indent=0):
        for name, subtree in tree.items():
            print("  " * indent + f"├── {name}")
            if isinstance(subtree, dict):
                print_tree(subtree, indent + 1)
    
    # Show only first level to avoid too much output
    for name, subtree in list(index.directory_tree.items())[:5]:
        print(f"├── {name}")
        if isinstance(subtree, dict) and subtree:
            for subname in list(subtree.keys())[:3]:
                print(f"│   ├── {subname}")
    
    # Display some lookup examples
    print(f"\n🔍 Lookup Examples:")
    print(f"   Total path mappings: {len(index.lookups['path_to_id'])}")
    print(f"   Total function mappings: {len(index.lookups['function_to_file_id'])}")
    print(f"   Total class mappings: {len(index.lookups['class_to_file_id'])}")
    
    # Show some function examples
    if index.lookups['function_to_file_id']:
        print(f"   Sample functions:")
        for func_name in list(index.lookups['function_to_file_id'].keys())[:5]:
            file_ids = index.lookups['function_to_file_id'][func_name]  # Now a List[int]
            file_paths = []
            for file_id in file_ids:
                file_path = next((f['path'] for f in index.files if f['id'] == file_id), f"unknown_file_{file_id}")
                file_paths.append(file_path)
            
            if len(file_paths) == 1:
                print(f"      {func_name} → {file_paths[0]}")
            else:
                print(f"      {func_name} → [{len(file_paths)} files] {', '.join(file_paths)}")
    
    # Display relationship examples
    print(f"\n🔗 Relationships:")
    reverse_lookups = index.reverse_lookups
    
    if reverse_lookups.get('function_callers'):
        print(f"   Function call relationships: {len(reverse_lookups['function_callers'])}")
        for func_name, callers in list(reverse_lookups['function_callers'].items())[:3]:
            caller_names = [c['caller'] for c in callers]
            print(f"      {func_name} ← called by: {', '.join(caller_names)}")
    
    if reverse_lookups.get('imports_module'):
        print(f"   Import relationships: {len(reverse_lookups['imports_module'])}")
        for module, file_ids in list(reverse_lookups['imports_module'].items())[:3]:
            print(f"      {module} ← imported by {len(file_ids)} files")
    
    # Show errors if any
    if index.index_metadata.get('files_with_errors'):
        print(f"\n⚠️  Files with errors: {len(index.index_metadata['files_with_errors'])}")
        for error_file in index.index_metadata['files_with_errors'][:3]:
            print(f"      - {error_file}")
    
    print(f"\n✅ Indexing complete! Index contains {len(index.files)} files.")
    
    # Optionally save the index to a file
    save_index = input("\n💾 Save index to file? (y/N): ").lower().strip()
    if save_index == 'y':
        output_file = "demo_index.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(index.to_json())
        print(f"📁 Index saved to {output_file}")
        print(f"   File size: {os.path.getsize(output_file)} bytes")


def analyze_specific_file():
    """Analyze a specific file in detail."""
    print("\n🔬 Detailed File Analysis")
    print("=" * 30)
    
    # Let's analyze the main server file
    server_file = "src/code_index_mcp/server.py"
    if not os.path.exists(server_file):
        print(f"❌ File not found: {server_file}")
        return
    
    # Build index and find the server file
    builder = IndexBuilder()
    index = builder.build_index(".")
    
    server_info = None
    for file_info in index.files:
        if file_info['path'] == server_file.replace('\\', '/'):
            server_info = file_info
            break
    
    if not server_info:
        print(f"❌ File not found in index: {server_file}")
        return
    
    print(f"📄 File: {server_info['path']}")
    print(f"   Language: {server_info['language']}")
    print(f"   Size: {server_info['size']} bytes")
    print(f"   Lines: {server_info['line_count']}")
    
    print(f"\n🔧 Functions ({len(server_info['functions'])}):")
    for func in server_info['functions'][:10]:  # Show first 10 functions
        params = ', '.join(func['parameters'][:3])  # Show first 3 params
        if len(func['parameters']) > 3:
            params += '...'
        async_marker = "async " if func['is_async'] else ""
        decorators = f"@{', @'.join(func['decorators'])} " if func['decorators'] else ""
        print(f"   {decorators}{async_marker}{func['name']}({params}) [lines {func['line_start']}-{func['line_end']}]")
        
        if func['calls']:
            print(f"      → calls: {', '.join(func['calls'][:3])}")
        if func['called_by']:
            print(f"      ← called by: {', '.join(func['called_by'][:3])}")
    
    print(f"\n🏗️  Classes ({len(server_info['classes'])}):")
    for cls in server_info['classes']:
        inheritance = f" extends {cls['inherits_from']}" if cls['inherits_from'] else ""
        print(f"   {cls['name']}{inheritance} [lines {cls['line_start']}-{cls['line_end']}]")
        if cls['methods']:
            print(f"      Methods: {', '.join(cls['methods'])}")
        if cls['instantiated_by']:
            print(f"      Instantiated by: {', '.join(cls['instantiated_by'])}")
    
    print(f"\n📦 Imports ({len(server_info['imports'])}):")
    for imp in server_info['imports'][:10]:  # Show first 10 imports
        if imp['imported_names']:
            names = ', '.join(imp['imported_names'][:3])
            if len(imp['imported_names']) > 3:
                names += '...'
            print(f"   from {imp['module']} import {names}")
        else:
            print(f"   import {imp['module']}")
    
    # Show language-specific features
    if server_info['language_specific']:
        print(f"\n🐍 Python-specific features:")
        python_features = server_info['language_specific'].get('python', {})
        
        if python_features.get('decorators'):
            print(f"   Decorators:")
            for func_name, decorators in python_features['decorators'].items():
                print(f"      {func_name}: {', '.join(decorators)}")
        
        if python_features.get('async_functions'):
            print(f"   Async functions: {', '.join(python_features['async_functions'])}")
        
        if python_features.get('class_inheritance'):
            print(f"   Class inheritance:")
            for cls_name, base in python_features['class_inheritance'].items():
                if base:
                    print(f"      {cls_name} → {base}")


if __name__ == "__main__":
    try:
        demo_indexing()
        
        # Ask if user wants detailed file analysis
        detail_analysis = input("\n🔬 Run detailed file analysis? (y/N): ").lower().strip()
        if detail_analysis == 'y':
            analyze_specific_file()
            
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()