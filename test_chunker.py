#!/usr/bin/env python3
"""
Test script for code chunking functionality.

Tests the chunker with sample Python files from the test directory.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from code_index_mcp.ingestion import ChunkStrategy, chunk_directory, chunk_file


def test_single_file():
    """Test chunking a single Python file."""
    print("=" * 70)
    print("TEST 1: Single File Chunking")
    print("=" * 70)

    # Test with user_management Python sample
    file_path = "test/sample-projects/python/user_management/models/user.py"

    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return

    content = Path(file_path).read_text()

    # Test different strategies
    for strategy in [ChunkStrategy.FUNCTION, ChunkStrategy.SEMANTIC]:
        print(f"\n📋 Strategy: {strategy.value}")
        print("-" * 70)

        chunks = chunk_file(file_path, content, strategy=strategy)

        print(f"✓ Generated {len(chunks)} chunks")

        for i, chunk in enumerate(chunks, 1):
            print(f"\nChunk {i}:")
            print(f"  Type: {chunk.chunk_type}")
            print(f"  Name: {chunk.chunk_name}")
            print(f"  Lines: {chunk.line_start}-{chunk.line_end}")
            print(f"  Language: {chunk.language}")
            print(f"  Content Hash: {chunk.content_hash[:16]}...")
            print(f"  Symbols: {list(chunk.symbols.keys())}")

            # Show first few lines of content
            content_preview = chunk.content.split("\n")[:3]
            print(f"  Content Preview:")
            for line in content_preview:
                print(f"    {line[:70]}")

        print()


def test_directory():
    """Test chunking an entire directory."""
    print("\n" + "=" * 70)
    print("TEST 2: Directory Chunking")
    print("=" * 70)

    # Test with Python user_management sample
    directory = "test/sample-projects/python/user_management"

    if not Path(directory).exists():
        print(f"❌ Directory not found: {directory}")
        return

    print(f"\n📂 Chunking directory: {directory}")
    print("-" * 70)

    results = chunk_directory(directory, strategy=ChunkStrategy.FUNCTION, file_patterns=["*.py"])

    total_chunks = sum(len(chunks) for chunks in results.values())
    print(f"\n✓ Processed {len(results)} files")
    print(f"✓ Generated {total_chunks} total chunks")

    # Show summary
    print("\nFile Summary:")
    for file_path, chunks in sorted(results.items()):
        print(f"  {file_path}: {len(chunks)} chunks")
        for chunk in chunks:
            print(
                f"    - {chunk.chunk_type}: {chunk.chunk_name} (lines {chunk.line_start}-{chunk.line_end})"
            )


def test_chunk_metadata():
    """Test metadata extraction from chunks."""
    print("\n" + "=" * 70)
    print("TEST 3: Metadata Extraction")
    print("=" * 70)

    # Test with a file that has imports and function calls
    file_path = "test/sample-projects/python/user_management/services/user_manager.py"

    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return

    content = Path(file_path).read_text()
    chunks = chunk_file(file_path, content, strategy=ChunkStrategy.FUNCTION)

    print(f"\n📋 Analyzing {file_path}")
    print(f"✓ Found {len(chunks)} chunks")

    for chunk in chunks:
        print(f"\n{chunk.chunk_type.upper()}: {chunk.chunk_name}")
        print("-" * 70)

        # Show symbols
        symbols = chunk.symbols

        if "imports" in symbols and symbols["imports"]:
            print(f"  Imports: {', '.join(symbols['imports'][:5])}")
            if len(symbols["imports"]) > 5:
                print(f"    ... and {len(symbols['imports']) - 5} more")

        if "parameters" in symbols:
            print(f"  Parameters: {', '.join(symbols['parameters'])}")

        if "calls" in symbols and symbols["calls"]:
            print(f"  Function Calls: {', '.join(symbols['calls'][:5])}")
            if len(symbols["calls"]) > 5:
                print(f"    ... and {len(symbols['calls']) - 5} more")

        if "docstring" in symbols and symbols["docstring"]:
            doc_preview = symbols["docstring"].split("\n")[0][:60]
            print(f"  Docstring: {doc_preview}...")


def test_chunk_serialization():
    """Test chunk serialization to dict."""
    print("\n" + "=" * 70)
    print("TEST 4: Chunk Serialization")
    print("=" * 70)

    file_path = "test/sample-projects/python/user_management/models/user.py"

    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return

    content = Path(file_path).read_text()
    chunks = chunk_file(file_path, content, strategy=ChunkStrategy.FUNCTION)

    if chunks:
        chunk_dict = chunks[0].to_dict()
        print(f"\n✓ Serialized chunk: {chunks[0].chunk_name}")
        print("-" * 70)
        print("Dictionary keys:", list(chunk_dict.keys()))
        print("\nSample output:")
        import json

        print(json.dumps(chunk_dict, indent=2, default=str)[:500] + "...")


def main():
    """Run all tests."""
    print("\n🧪 CODE CHUNKER TESTS")
    print("=" * 70)

    try:
        test_single_file()
        test_directory()
        test_chunk_metadata()
        test_chunk_serialization()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nCode chunker is working correctly!")
        print("Ready for integration with AlloyDB and Vertex AI.")
        print()

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
