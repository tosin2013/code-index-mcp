# Cloud Ingestion Guide

## Problem
When using the **cloud-deployed MCP server**, it can't access files on your local machine.

## Solution: Upload Files in Requests

Use the `upload_code_for_ingestion.py` script to send files from your local machine to the cloud server.

### Quick Start

1. **Run the uploader script**:
```bash
python upload_code_for_ingestion.py /Users/tosinakinosho/workspaces/documcp \
    --project-name documcp \
    --batch-size 50
```

2. **For each batch**:
   - The script prints a JSON payload
   - Copy the JSON
   - Paste into Claude Desktop to call `ingest_code_for_search()`
   - Press Enter when done
   - Repeat for next batch

3. **Progress is tracked automatically**:
   - Progress saved to `.ingestion_progress.json` in your project
   - Resume interrupted uploads with `--resume`

### Example

```bash
# First time
python upload_code_for_ingestion.py ~/workspaces/documcp --project-name documcp

# Resume if interrupted
python upload_code_for_ingestion.py ~/workspaces/documcp --resume

# Custom batch size (smaller = more batches, but less data per request)
python upload_code_for_ingestion.py ~/workspaces/documcp --batch-size 25

# Reset progress and start over
python upload_code_for_ingestion.py ~/workspaces/documcp --reset
```

### Features

- ✅ **Auto-detects text files** (skips binaries)
- ✅ **Respects .gitignore patterns** (skips `node_modules`, etc.)
- ✅ **Batches files** (default: 50 files per batch)
- ✅ **Tracks progress locally** (`.ingestion_progress.json`)
- ✅ **Resume support** (interrupted uploads can be resumed)
- ✅ **Skips large files** (>1MB by default)

### What Gets Uploaded

- ✅ Source code files (`.py`, `.js`, `.java`, etc.)
- ✅ Configuration files (`.json`, `.yaml`, `.toml`, etc.)
- ✅ Documentation (`.md`, `.txt`, etc.)
- ❌ Binary files (images, videos, executables)
- ❌ Dependencies (`node_modules`, `__pycache__`, etc.)
- ❌ Build outputs (`dist`, `build`, `target`, etc.)

### Architecture

```
┌──────────────────┐                    ┌──────────────────┐
│  Your Local Mac  │                    │  Cloud Run (GCP) │
│                  │                    │                  │
│  uploader script │  ──JSON files──→   │  MCP Server      │
│  (collects files)│                    │  (writes to tmp) │
│                  │                    │  (ingests)       │
└──────────────────┘                    └────────┬─────────┘
                                                 │
                                                 ▼
                                        ┌─────────────────┐
                                        │    AlloyDB      │
                                        │  (stores data)  │
                                        └─────────────────┘
```

### Cloud Server Updates

The `ingest_code_for_search` tool now supports two modes:

**1. Cloud Mode** (when using cloud-deployed server):
```python
ingest_code_for_search(
    files=[
        {"path": "src/main.py", "content": "..."},
        {"path": "src/utils.py", "content": "..."}
    ],
    project_name="my-app"
)
```

**2. Stdio Mode** (when running server locally):
```python
ingest_code_for_search(
    directory_path="/path/to/project",
    project_name="my-app"
)
```

The server automatically detects which mode to use based on whether `files` are provided!

### Troubleshooting

**Q: "Too many files, batches are too large"**  
A: Use smaller batch size: `--batch-size 25`

**Q: "Want to skip certain files"**  
A: Add ignore patterns: `--ignore "*.test.js" "*.spec.ts"`

**Q: "Progress file corrupted"**  
A: Reset and start fresh: `--reset`

**Q: "Some files showing as 'already processed'"**  
A: That's the resume feature working! Use `--reset` to reprocess all files.

---

**Next**: Deploy the updated server and try it out!
