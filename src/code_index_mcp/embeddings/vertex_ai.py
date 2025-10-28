"""
Vertex AI embedding generation for code chunks.

This module provides integration with Google Cloud Vertex AI's text embedding models
for generating vector representations of code chunks for semantic search.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingConfig:
    """
    Configuration for Vertex AI embedding generation.
    
    Attributes:
        model_name: Vertex AI model to use (e.g., 'text-embedding-004')
        dimensions: Embedding vector dimensions (768 or 1536 for text-embedding-004)
        task_type: Task type for embeddings ('SEMANTIC_SIMILARITY', 'RETRIEVAL_QUERY', 'RETRIEVAL_DOCUMENT')
        batch_size: Number of texts to process in one batch
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries (exponential backoff)
        rate_limit_rpm: Requests per minute limit (0 = no limit)
        project_id: GCP project ID (optional, uses default if not set)
        location: GCP location (default: us-central1)
    """
    model_name: str = "text-embedding-004"
    dimensions: int = 768  # or 1536 for higher quality
    task_type: str = "RETRIEVAL_DOCUMENT"  # or SEMANTIC_SIMILARITY, RETRIEVAL_QUERY
    batch_size: int = 5
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_rpm: int = 300  # Vertex AI default limit
    project_id: Optional[str] = None
    location: str = "us-central1"
    
    # Rate limiting state
    _request_times: List[float] = field(default_factory=list, repr=False, compare=False)


class VertexAIEmbedder:
    """
    Vertex AI embedding generator for code chunks.
    
    Handles:
    - Single and batch embedding generation
    - Rate limiting
    - Retry logic with exponential backoff
    - Error handling
    - Caching (optional)
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """
        Initialize Vertex AI embedder.
        
        Args:
            config: Embedding configuration (uses defaults if not provided)
        """
        self.config = config or EmbeddingConfig()
        self._model = None
        self._vertexai_initialized = False
        
        # Try to initialize Vertex AI
        try:
            self._initialize_vertexai()
        except Exception as e:
            logger.warning(f"Vertex AI initialization deferred: {e}")
            logger.info("Vertex AI will be initialized on first use")
    
    def _initialize_vertexai(self):
        """Initialize Vertex AI SDK (lazy loading)."""
        if self._vertexai_initialized:
            return
        
        try:
            import vertexai
            from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput

            # Store TextEmbeddingInput class for use in embedding generation
            self._TextEmbeddingInput = TextEmbeddingInput

            # Initialize Vertex AI
            vertexai.init(
                project=self.config.project_id,
                location=self.config.location
            )

            # Load model
            self._model = TextEmbeddingModel.from_pretrained(self.config.model_name)
            self._vertexai_initialized = True

            logger.info(f"Vertex AI initialized with model: {self.config.model_name}")
        
        except ImportError:
            raise ImportError(
                "Vertex AI SDK not installed. Install with: pip install google-cloud-aiplatform"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Vertex AI: {e}")
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting based on requests per minute."""
        if self.config.rate_limit_rpm <= 0:
            return  # No rate limiting
        
        now = time.time()
        window = 60.0  # 1 minute window
        
        # Remove old requests outside window
        self.config._request_times = [
            t for t in self.config._request_times 
            if now - t < window
        ]
        
        # Check if we've hit the limit
        if len(self.config._request_times) >= self.config.rate_limit_rpm:
            # Calculate sleep time
            oldest = self.config._request_times[0]
            sleep_time = window - (now - oldest) + 0.1  # Small buffer
            
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        # Record this request
        self.config._request_times.append(time.time())
    
    def generate_embedding(
        self,
        text: str,
        task_type: Optional[str] = None
    ) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            task_type: Override config task_type (optional)
        
        Returns:
            Embedding vector as list of floats
        
        Raises:
            RuntimeError: If embedding generation fails after retries
        """
        self._initialize_vertexai()
        
        task_type = task_type or self.config.task_type
        
        for attempt in range(self.config.max_retries):
            try:
                self._enforce_rate_limit()

                # Wrap text in TextEmbeddingInput (required for text-embedding-004)
                text_input = self._TextEmbeddingInput(
                    text=text,
                    task_type=task_type
                )

                # Generate embedding
                embeddings = self._model.get_embeddings(
                    [text_input],
                    output_dimensionality=self.config.dimensions
                )

                # Extract values
                embedding_vector = embeddings[0].values

                return list(embedding_vector)
            
            except Exception as e:
                logger.warning(f"Embedding attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    raise RuntimeError(f"Failed to generate embedding after {self.config.max_retries} attempts: {e}")
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        task_type: Optional[str] = None,
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            task_type: Override config task_type (optional)
            show_progress: Show progress messages
        
        Returns:
            List of embedding vectors
        
        Raises:
            RuntimeError: If batch embedding fails
        """
        self._initialize_vertexai()
        
        task_type = task_type or self.config.task_type
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i:i + self.config.batch_size]
            batch_num = i // self.config.batch_size + 1
            total_batches = (len(texts) + self.config.batch_size - 1) // self.config.batch_size
            
            if show_progress:
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} texts)")
            
            for attempt in range(self.config.max_retries):
                try:
                    self._enforce_rate_limit()

                    # Wrap texts in TextEmbeddingInput (required for text-embedding-004)
                    text_inputs = [
                        self._TextEmbeddingInput(text=text, task_type=task_type)
                        for text in batch
                    ]

                    # Generate embeddings for batch
                    embeddings = self._model.get_embeddings(
                        text_inputs,
                        output_dimensionality=self.config.dimensions
                    )

                    # Extract values
                    batch_embeddings = [list(emb.values) for emb in embeddings]
                    all_embeddings.extend(batch_embeddings)

                    break  # Success
                
                except Exception as e:
                    logger.warning(f"Batch {batch_num} attempt {attempt + 1} failed: {e}")
                    
                    if attempt < self.config.max_retries - 1:
                        delay = self.config.retry_delay * (2 ** attempt)
                        logger.info(f"Retrying batch {batch_num} in {delay:.2f}s...")
                        time.sleep(delay)
                    else:
                        raise RuntimeError(f"Failed to generate batch embeddings after {self.config.max_retries} attempts: {e}")
        
        return all_embeddings
    
    def embed_code_chunks(
        self,
        chunks: List[Any],  # List[CodeChunk]
        use_metadata: bool = True,
        show_progress: bool = True
    ) -> List[Tuple[Any, List[float]]]:  # List[Tuple[CodeChunk, embedding]]
        """
        Generate embeddings for code chunks.
        
        Args:
            chunks: List of CodeChunk objects
            use_metadata: Include metadata in embedding text
            show_progress: Show progress messages
        
        Returns:
            List of (chunk, embedding) tuples
        """
        # Prepare texts for embedding
        texts = []
        for chunk in chunks:
            if use_metadata:
                # Include metadata for better embeddings
                text = self._prepare_chunk_text(chunk)
            else:
                # Just use code content
                text = chunk.content
            
            texts.append(text)
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        embeddings = self.generate_embeddings_batch(
            texts,
            task_type="RETRIEVAL_DOCUMENT",
            show_progress=show_progress
        )
        
        # Pair chunks with embeddings
        return list(zip(chunks, embeddings))
    
    def _prepare_chunk_text(self, chunk: Any) -> str:
        """
        Prepare chunk text for embedding, including relevant metadata.
        
        Args:
            chunk: CodeChunk object
        
        Returns:
            Formatted text for embedding
        """
        parts = []
        
        # Add file path and language context
        parts.append(f"File: {chunk.file_path}")
        parts.append(f"Language: {chunk.language}")
        
        # Add chunk type and name
        if chunk.chunk_name:
            parts.append(f"{chunk.chunk_type.capitalize()}: {chunk.chunk_name}")
        
        # Add docstring if available
        if chunk.symbols.get('docstring'):
            parts.append(f"Description: {chunk.symbols['docstring']}")
        
        # Add imports context
        if chunk.symbols.get('imports'):
            imports = chunk.symbols['imports'][:5]  # First 5 imports
            parts.append(f"Imports: {', '.join(imports)}")
        
        # Add the actual code
        parts.append("\nCode:")
        parts.append(chunk.content)
        
        return "\n".join(parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get embedding generation statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "model": self.config.model_name,
            "dimensions": self.config.dimensions,
            "batch_size": self.config.batch_size,
            "rate_limit_rpm": self.config.rate_limit_rpm,
            "initialized": self._vertexai_initialized,
            "recent_requests": len(self.config._request_times),
        }


# Convenience functions

def generate_embedding(
    text: str,
    config: Optional[EmbeddingConfig] = None
) -> List[float]:
    """
    Convenience function to generate a single embedding.
    
    Args:
        text: Text to embed
        config: Configuration (uses defaults if not provided)
    
    Returns:
        Embedding vector
    """
    embedder = VertexAIEmbedder(config=config)
    return embedder.generate_embedding(text)


def generate_embeddings_batch(
    texts: List[str],
    config: Optional[EmbeddingConfig] = None,
    show_progress: bool = False
) -> List[List[float]]:
    """
    Convenience function to generate embeddings in batch.
    
    Args:
        texts: List of texts to embed
        config: Configuration (uses defaults if not provided)
        show_progress: Show progress messages
    
    Returns:
        List of embedding vectors
    """
    embedder = VertexAIEmbedder(config=config)
    return embedder.generate_embeddings_batch(texts, show_progress=show_progress)


# Mock embedder for local testing (no GCP required)

class MockVertexAIEmbedder:
    """
    Mock embedder for local testing without Vertex AI.
    
    Generates random embeddings with the correct dimensions.
    Useful for testing the ingestion pipeline without GCP costs.
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """Initialize mock embedder."""
        self.config = config or EmbeddingConfig()
        logger.info("MockVertexAIEmbedder initialized (no GCP connection)")
    
    def generate_embedding(self, text: str, **kwargs) -> List[float]:
        """Generate a mock embedding."""
        # Generate random but consistent embedding based on text hash
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(self.config.dimensions).tolist()
        
        # Normalize to unit length (like real embeddings)
        norm = np.linalg.norm(embedding)
        embedding = [x / norm for x in embedding]
        
        return embedding
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = False,
        **kwargs
    ) -> List[List[float]]:
        """Generate mock embeddings for batch."""
        return [self.generate_embedding(text) for text in texts]
    
    def embed_code_chunks(
        self,
        chunks: List[Any],
        **kwargs
    ) -> List[Tuple[Any, List[float]]]:
        """Generate mock embeddings for chunks."""
        embeddings = [self.generate_embedding(chunk.content) for chunk in chunks]
        return list(zip(chunks, embeddings))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get mock stats."""
        return {
            "model": f"{self.config.model_name} (MOCK)",
            "dimensions": self.config.dimensions,
            "initialized": True,
            "mock": True,
        }



