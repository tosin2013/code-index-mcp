# Embedding Model Recommendation for Code Search

**Date:** 2025-01-27
**Current Model:** text-embedding-004 (768 dimensions)

## Quick Summary

**RECOMMENDATION:** Upgrade to `text-embedding-005` for better code search performance.

## Model Comparison

| Feature | text-embedding-004 | text-embedding-005 | gemini-embedding-001 |
|---------|-------------------|-------------------|---------------------|
| **Dimensions** | 768 | 768 | 768-3072 |
| **CODE_RETRIEVAL_QUERY** | ❌ No | ✅ **Yes** | ✅ Yes |
| **RETRIEVAL_DOCUMENT** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Performance (MTEB)** | Good | **Better** | Best |
| **API Compatibility** | TextEmbeddingModel | TextEmbeddingModel | google.genai.Client |
| **Code Migration** | N/A | ✅ **Drop-in replacement** | ⚠️ Requires API change |
| **Stability** | Stable | Stable | Stable |

## Why text-embedding-005 is Better for Code Search

1. **CODE_RETRIEVAL_QUERY Task Type**
   - Specifically optimized for code search queries
   - Better understanding of programming language syntax
   - Improved semantic matching for code patterns

2. **Top MTEB Multilingual Performance**
   - Achieved #1 rank on Massive Text Embedding Benchmark
   - Better cross-language code understanding
   - More accurate semantic similarity

3. **Drop-in Replacement**
   - Same API as text-embedding-004
   - No code changes needed (just update model name)
   - Same 768 dimensions (compatible with existing AlloyDB schema)

## Migration Path

### Option 1: Quick Upgrade to text-embedding-005 (RECOMMENDED)

**Effort:** 1 minute
**Risk:** Very low

**Changes:**
```python
# In src/code_index_mcp/embeddings/vertex_ai.py
@dataclass
class EmbeddingConfig:
    model_name: str = "text-embedding-005"  # Changed from 004
    task_type: str = "CODE_RETRIEVAL_QUERY"  # New task type for code
```

**Deployment:**
```bash
cd deployment/gcp
./deploy.sh dev --with-alloydb
```

### Option 2: Upgrade to gemini-embedding-001 (Future)

**Effort:** 2-4 hours
**Risk:** Medium (requires API changes)

**Benefits:**
- Latest and most powerful embedding model
- Supports up to 3072 dimensions (higher quality)
- State-of-the-art performance

**Trade-offs:**
- Requires switching from `vertexai.language_models` to `google.genai.Client`
- Different API signature
- Would need to update AlloyDB schema for higher dimensions
- More expensive ($0.000025 per 1k characters vs $0.00001)

## Recommendation

**For immediate deployment:**
1. ✅ Keep current fix with text-embedding-004
2. ✅ Test Git-sync ingestion works
3. ✅ Verify semantic search quality

**For optimization (within 1 week):**
1. Upgrade to text-embedding-005
2. Change task type to CODE_RETRIEVAL_QUERY
3. Re-ingest repositories for better embeddings
4. Compare search quality

**For future consideration (3-6 months):**
1. Evaluate gemini-embedding-001 performance
2. Benchmark cost vs quality trade-offs
3. Consider for production deployment

## Cost Comparison

| Model | Cost per 1k characters | Est. Monthly Cost* |
|-------|----------------------|-------------------|
| text-embedding-004 | $0.00001 | $5-10 |
| text-embedding-005 | $0.00001 | $5-10 |
| gemini-embedding-001 | $0.000025 | $12-25 |

*Based on ingesting 500k-1M lines of code per month

## Implementation Plan

### Phase 1: Deploy Current Fix (Now)
- ✅ API fix applied (TextEmbeddingInput)
- ⏳ Deploy to Cloud Run
- ⏳ Test with anthropic-sdk-python repo
- ⏳ Verify embeddings stored in AlloyDB

### Phase 2: Upgrade to text-embedding-005 (This Week)
- Update model_name in EmbeddingConfig
- Change default task_type to CODE_RETRIEVAL_QUERY
- Update documentation
- Re-deploy and test
- Compare search quality before/after

### Phase 3: Evaluate gemini-embedding-001 (Future)
- Create proof-of-concept branch
- Implement new API integration
- Benchmark performance and cost
- Make decision based on results

## References

- [Google Cloud Text Embeddings API](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-embeddings-api)
- [MTEB Multilingual Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [Gecko: Versatile Text Embeddings Research Paper](https://arxiv.org/abs/2403.20327)
- [Gemini Embedding Model Announcement](https://developers.googleblog.com/en/gemini-embedding-text-model-now-available-gemini-api/)
