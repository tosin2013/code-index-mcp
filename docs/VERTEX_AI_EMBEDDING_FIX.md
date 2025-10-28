# Vertex AI Embedding API Fix

**Date:** 2025-01-27
**Issue:** TypeError with `task_type` parameter in `get_embeddings()`
**Status:** ✅ Fixed

## Problem

The embedding generation was failing with:
```
TypeError: _TextEmbeddingModel.get_embeddings() got an unexpected keyword argument 'task_type'
```

## Root Cause

The Vertex AI `TextEmbeddingModel` API changed. The `get_embeddings()` method no longer accepts `task_type` as a direct keyword argument. Instead, texts must be wrapped in `TextEmbeddingInput` objects.

## Solution

### Before (Incorrect):
```python
embeddings = self._model.get_embeddings(
    texts=[text],
    task_type=task_type,
    output_dimensionality=self.config.dimensions
)
```

### After (Correct):
```python
from vertexai.language_models import TextEmbeddingInput

text_input = TextEmbeddingInput(
    text=text,
    task_type=task_type
)
embeddings = self._model.get_embeddings(
    [text_input],
    output_dimensionality=self.config.dimensions
)
```

## Changes Made

**File:** `src/code_index_mcp/embeddings/vertex_ai.py`

1. **Import `TextEmbeddingInput`** at initialization (line 84)
2. **Updated `generate_embedding()`** method (lines 161-176)
   - Wrap text in `TextEmbeddingInput` object
   - Pass wrapped input to `get_embeddings()`
3. **Updated `generate_embeddings_batch()`** method (lines 227-243)
   - Wrap all texts in `TextEmbeddingInput` objects
   - Pass list of wrapped inputs to `get_embeddings()`

## Supported Task Types

According to Google Cloud documentation, these task types are supported:

- `RETRIEVAL_QUERY` - For search queries
- `RETRIEVAL_DOCUMENT` - For documents being searched (our use case)
- `SEMANTIC_SIMILARITY` - For similarity comparisons
- `CLASSIFICATION` - For classification tasks
- `CLUSTERING` - For clustering tasks
- `QUESTION_ANSWERING` - For Q&A tasks
- `FACT_VERIFICATION` - For fact checking
- `CODE_RETRIEVAL_QUERY` - For code search queries

## Model Recommendations

### Current Model: text-embedding-004
- ✅ Works with TextEmbeddingInput API
- ✅ Supports 768 or 1536 dimensions
- ⚠️ May be superseded by newer models

### Consider Upgrading To:
1. **text-embedding-005** (if available)
   - Newer model with potential improvements
   - Check availability in your region

2. **gemini-embedding-001**
   - Latest embedding model from Google
   - Requires different API (`google.genai.Client`)
   - Would require more significant code changes

## Testing

After this fix, the embedding generation should work correctly:

```python
# Test with code chunks
chunks_with_embeddings = embedder.embed_code_chunks(
    chunks=code_chunks,
    use_metadata=True
)

# Verify embeddings generated
assert len(chunks_with_embeddings) == len(code_chunks)
assert all(len(emb) == 768 for _, emb in chunks_with_embeddings)
```

## References

- [Vertex AI Text Embeddings API](https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings)
- [TextEmbeddingInput Documentation](https://cloud.google.com/python/docs/reference/aiplatform/latest/vertexai.language_models.TextEmbeddingInput)
- [Vertex AI Samples - Text Embedding](https://github.com/GoogleCloudPlatform/vertex-ai-samples/blob/main/notebooks/official/generative_ai/text_embedding_new_api.ipynb)
