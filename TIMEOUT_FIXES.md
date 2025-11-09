# Cloud Run Timeout Fixes

## Problem
SSE connection closes during long-running operations (`ingest_code_for_search`, `build_deep_index`), causing `ClosedResourceError` in Cloud Run logs.

## Root Cause
1. **Insufficient timeout**: Original 300s (5 min) timeout too short for large codebases
2. **No progress visibility**: Long operations had minimal logging, making monitoring difficult
3. **SSE connection closed**: Client closes connection when no activity, server tries to respond after closure

## Solutions Implemented

### 1. Increased Cloud Run Timeout (15 minutes)
**File**: `deployment/gcp/deploy.sh:213`
```bash
# Changed from:
--timeout=300

# Changed to:
--timeout=900  # 15 minutes
```

### 2. Added Progress Logging for Ingestion
**File**: `src/code_index_mcp/server.py:694-707`
- Added `progress_callback` to `ingest_directory()` call
- Progress logs every file chunked
- Visible in Cloud Run logs with `[INGESTION PROGRESS]` prefix

### 3. Improved Indexing Progress Visibility
**File**: `src/code_index_mcp/indexing/json_index_builder.py:176`
- Changed progress logging from `DEBUG` → `INFO` level
- Logs every 100 files processed with percentage
- Format: `[INDEX PROGRESS] Processed 300/1000 files (30%)`

## Benefits
✅ **15-minute timeout** - Supports ingesting thousands of files
✅ **Real-time progress** - Monitor operations in Cloud Run logs
✅ **Better debugging** - Clear visibility into what's happening
✅ **No breaking changes** - Existing functionality unchanged

## How to Deploy

### Option 1: Redeploy from local machine
```bash
cd deployment/gcp
./deploy.sh dev  # or prod
```

### Option 2: Let CI/CD handle it
```bash
git add .
git commit -m "fix: increase Cloud Run timeout and add progress logging"
git push
```

## Monitoring Long Operations

After deployment, monitor progress in real-time:

```bash
# Watch logs (replace with your service name)
gcloud run services logs tail code-index-mcp-dev \
    --region=us-east1 \
    --format="value(textPayload)" \
    | grep -E "\[INGESTION|INDEX PROGRESS\]"
```

You'll see output like:
```
[INGESTION PROGRESS] Chunked src/main.py: 12 chunks | Data: {files: 50, chunks: 234}
[INDEX PROGRESS] Processed 200/500 files (40%)
[INGESTION] Completed successfully: {files_processed: 150, chunks_inserted: 3456}
```

## Expected Behavior After Fix

### Before (with errors):
- ❌ Operations timeout after 5 minutes
- ❌ `ClosedResourceError` in logs
- ❌ No visibility into progress

### After (with fixes):
- ✅ Operations complete successfully (up to 15 min)
- ✅ Progress visible in Cloud Run logs
- ✅ Clean completion with stats

## Testing the Fix

1. Deploy the updated code
2. Trigger a large ingestion:
   ```
   ingest_code_for_search(use_current_project=True, project_name="large-app")
   ```
3. Monitor Cloud Run logs for progress
4. Verify completion without errors

## Future Improvements (Optional)

If 15 minutes still isn't enough, consider:
1. **Background job processing** - Return immediately, poll for status
2. **Batch ingestion** - Split large projects into smaller batches
3. **Webhook callbacks** - Notify when long operations complete
4. **Progress API endpoint** - Real-time progress via HTTP endpoint

## Related Files
- `deployment/gcp/deploy.sh` - Deployment script with timeout config
- `src/code_index_mcp/server.py` - MCP tools with progress callbacks
- `src/code_index_mcp/ingestion/pipeline.py` - Ingestion with progress reporting
- `src/code_index_mcp/indexing/json_index_builder.py` - Index building with progress
