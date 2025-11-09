#!/usr/bin/env python3
"""
Test script for embedding generation.

Tests Vertex AI embedding integration with code chunks.
Can run with mock embedder (no GCP) or real Vertex AI.
"""

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from code_index_mcp.embeddings import EmbeddingConfig, VertexAIEmbedder
from code_index_mcp.embeddings.vertex_ai import MockVertexAIEmbedder
from code_index_mcp.ingestion import ChunkStrategy, chunk_file


def test_single_embedding(use_mock=True):
    """Test generating a single embedding."""
    print("=" * 70)
    print("TEST 1: Single Embedding Generation")
    print("=" * 70)

    # Sample code text
    code_text = """
def fibonacci(n: int) -> int:
    \"\"\"Calculate the nth Fibonacci number.\"\"\"
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""

    # Initialize embedder
    config = EmbeddingConfig(dimensions=768)

    if use_mock:
        print("\n🔧 Using MockVertexAIEmbedder (no GCP required)")
        embedder = MockVertexAIEmbedder(config)
    else:
        print("\n☁️  Using VertexAIEmbedder (requires GCP)")
        embedder = VertexAIEmbedder(config)

    print(f"Model: {config.model_name}")
    print(f"Dimensions: {config.dimensions}")
    print("-" * 70)

    try:
        # Generate embedding
        print("\n📊 Generating embedding...")
        embedding = embedder.generate_embedding(code_text)

        print(f"✓ Embedding generated successfully")
        print(f"  Dimensions: {len(embedding)}")
        print(f"  First 5 values: {embedding[:5]}")
        print(f"  Last 5 values: {embedding[-5:]}")
        print(f"  Vector norm: {sum(x**2 for x in embedding)**0.5:.6f}")

        return True

    except Exception as e:
        print(f"❌ Failed to generate embedding: {e}")
        return False


def test_batch_embeddings(use_mock=True):
    """Test batch embedding generation."""
    print("\n" + "=" * 70)
    print("TEST 2: Batch Embedding Generation")
    print("=" * 70)

    # Sample code texts
    texts = [
        "def add(a, b): return a + b",
        "def subtract(a, b): return a - b",
        "def multiply(a, b): return a * b",
        "def divide(a, b): return a / b",
        "def power(a, b): return a ** b",
    ]

    config = EmbeddingConfig(dimensions=768, batch_size=2)  # Small batch for testing

    if use_mock:
        print("\n🔧 Using MockVertexAIEmbedder")
        embedder = MockVertexAIEmbedder(config)
    else:
        print("\n☁️  Using VertexAIEmbedder")
        embedder = VertexAIEmbedder(config)

    print(f"Batch size: {config.batch_size}")
    print(f"Number of texts: {len(texts)}")
    print("-" * 70)

    try:
        # Generate embeddings
        print("\n📊 Generating batch embeddings...")
        embeddings = embedder.generate_embeddings_batch(texts, show_progress=True)

        print(f"\n✓ Batch embeddings generated successfully")
        print(f"  Total embeddings: {len(embeddings)}")
        print(f"  Dimensions per embedding: {len(embeddings[0])}")

        # Show sample
        print(f"\n  Sample embedding (text 1):")
        print(f"    First 5 values: {embeddings[0][:5]}")

        return True

    except Exception as e:
        print(f"❌ Failed to generate batch embeddings: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_code_chunk_embeddings(use_mock=True):
    """Test embedding generation for code chunks."""
    print("\n" + "=" * 70)
    print("TEST 3: Code Chunk Embeddings")
    print("=" * 70)

    # Get chunks from sample file
    file_path = "test/sample-projects/python/user_management/models/user.py"

    if not Path(file_path).exists():
        print(f"❌ Sample file not found: {file_path}")
        return False

    content = Path(file_path).read_text()

    # Chunk the file
    print(f"\n📂 Chunking file: {file_path}")
    chunks = chunk_file(file_path, content, strategy=ChunkStrategy.FUNCTION)
    print(f"✓ Generated {len(chunks)} chunks")

    # Take first 5 chunks for testing
    test_chunks = chunks[:5]
    print(f"  Testing with first {len(test_chunks)} chunks")

    # Initialize embedder
    config = EmbeddingConfig(dimensions=768, batch_size=2)

    if use_mock:
        print("\n🔧 Using MockVertexAIEmbedder")
        embedder = MockVertexAIEmbedder(config)
    else:
        print("\n☁️  Using VertexAIEmbedder")
        embedder = VertexAIEmbedder(config)

    print("-" * 70)

    try:
        # Generate embeddings
        print("\n📊 Generating embeddings for chunks...")
        results = embedder.embed_code_chunks(test_chunks, use_metadata=True, show_progress=True)

        print(f"\n✓ Chunk embeddings generated successfully")
        print(f"  Total chunks embedded: {len(results)}")

        # Show details for first chunk
        chunk, embedding = results[0]
        print(f"\n  Sample chunk:")
        print(f"    Type: {chunk.chunk_type}")
        print(f"    Name: {chunk.chunk_name}")
        print(f"    Lines: {chunk.line_start}-{chunk.line_end}")
        print(f"    Embedding dimensions: {len(embedding)}")
        print(f"    First 5 values: {embedding[:5]}")

        return True

    except Exception as e:
        print(f"❌ Failed to generate chunk embeddings: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_embedding_statistics(use_mock=True):
    """Test embedding statistics and metadata."""
    print("\n" + "=" * 70)
    print("TEST 4: Embedding Statistics")
    print("=" * 70)

    config = EmbeddingConfig(dimensions=768)

    if use_mock:
        print("\n🔧 Using MockVertexAIEmbedder")
        embedder = MockVertexAIEmbedder(config)
    else:
        print("\n☁️  Using VertexAIEmbedder")
        embedder = VertexAIEmbedder(config)

    print("-" * 70)

    try:
        # Get stats
        stats = embedder.get_stats()

        print("\n📊 Embedder Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        print("\n✓ Statistics retrieved successfully")
        return True

    except Exception as e:
        print(f"❌ Failed to get statistics: {e}")
        return False


def test_embedding_persistence():
    """Test saving and loading embeddings."""
    print("\n" + "=" * 70)
    print("TEST 5: Embedding Persistence")
    print("=" * 70)

    # Generate sample embeddings
    config = EmbeddingConfig(dimensions=768)
    embedder = MockVertexAIEmbedder(config)

    texts = ["def test(): pass", "class Test: pass"]
    embeddings = embedder.generate_embeddings_batch(texts)

    # Save to JSON
    output_file = "test_embeddings_output.json"
    data = {
        "config": {
            "model": config.model_name,
            "dimensions": config.dimensions,
        },
        "embeddings": [
            {
                "text": text,
                "embedding": embedding[:10] + ["..."],  # Truncate for readability
                "dimensions": len(embedding),
            }
            for text, embedding in zip(texts, embeddings)
        ],
    }

    try:
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\n✓ Embeddings saved to {output_file}")
        print(f"  File size: {Path(output_file).stat().st_size} bytes")

        # Clean up
        Path(output_file).unlink()
        print(f"  Test file cleaned up")

        return True

    except Exception as e:
        print(f"❌ Failed to save embeddings: {e}")
        return False


def main():
    """Run all tests."""
    print("\n🧪 EMBEDDING GENERATION TESTS")
    print("=" * 70)

    # Check for GCP credentials
    has_gcp = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") is not None

    if has_gcp:
        print("\n✓ GCP credentials found")
        print("  Will test with real Vertex AI")
        use_mock = False
    else:
        print("\n⚠️  No GCP credentials found")
        print("  Will test with MockVertexAIEmbedder")
        print("  Set GOOGLE_APPLICATION_CREDENTIALS to test with real Vertex AI")
        use_mock = True

    print("\n")

    results = []

    try:
        # Run tests
        results.append(("Single Embedding", test_single_embedding(use_mock)))
        results.append(("Batch Embeddings", test_batch_embeddings(use_mock)))
        results.append(("Code Chunk Embeddings", test_code_chunk_embeddings(use_mock)))
        results.append(("Embedding Statistics", test_embedding_statistics(use_mock)))
        results.append(("Embedding Persistence", test_embedding_persistence()))

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        for test_name, passed in results:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"  {test_name}: {status}")

        # Final result
        all_passed = all(result for _, result in results)

        print("\n" + "=" * 70)
        if all_passed:
            print("✅ ALL TESTS PASSED!")
        else:
            print("❌ SOME TESTS FAILED")
        print("=" * 70)

        if use_mock:
            print("\nℹ️  Tests ran with MockVertexAIEmbedder")
            print("   To test with real Vertex AI:")
            print("   1. Set up GCP credentials")
            print("   2. Enable Vertex AI API")
            print("   3. Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
        else:
            print("\n✓ Tests ran with real Vertex AI")

        print("\nEmbedding generation is ready for integration!")
        print("Next: Build ingestion pipeline (chunk → embed → store)")
        print()

        sys.exit(0 if all_passed else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ TEST SUITE FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
