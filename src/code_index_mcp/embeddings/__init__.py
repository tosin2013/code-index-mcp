"""
Embeddings module for semantic code search.

This module handles generating vector embeddings for code chunks using
various embedding models (Vertex AI, OpenAI, local models, etc.).
"""

from .vertex_ai import (
    VertexAIEmbedder,
    generate_embedding,
    generate_embeddings_batch,
    EmbeddingConfig,
)

__all__ = [
    "VertexAIEmbedder",
    "generate_embedding",
    "generate_embeddings_batch",
    "EmbeddingConfig",
]



