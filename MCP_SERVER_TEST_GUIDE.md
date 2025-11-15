# MCP Server Test Guide for VS Code / Claude Desktop

## Quick Reference

**Service URL:** `https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app`
**SSE Endpoint:** `https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app/sse`
**API Key:** `${MCP_API_KEY_DEV}`

---

## 📝 Configuration for Claude Desktop

**File:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "code-index-semantic-search": {
      "url": "https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app/sse",
      "transport": "sse",
      "headers": {
        "X-API-Key": "${MCP_API_KEY_DEV}"
      }
    }
  }
}
```

**After saving:** Restart Claude Desktop

---

## 🧪 Test Prompts (In Order)

### Test 1: Server Discovery
**Prompt:**
```
List all available MCP tools from the code-index-semantic-search server.
```

**Expected Output:**
- Should show 19 tools
- Key tools: semantic_search_code, find_similar_code, ingest_code_from_git

---

### Test 2: Ingest a Sample Repository
**Prompt:**
```
Use the code-index-semantic-search server to ingest this public GitHub repository:
https://github.com/anthropics/anthropic-sdk-python

No authentication token needed since it's public.
```

**Expected Output:**
- Confirmation of repository cloning
- Number of files processed
- Number of code chunks created
- Ingestion completion message

---

### Test 3: Semantic Code Search
**Prompt:**
```
Using the code-index-semantic-search server, search for "API client initialization and authentication setup" in the ingested code.

Show me the top 5 results with their file paths and similarity scores.
```

**Expected Output:**
- 5 code chunks with semantic similarity scores
- File paths and line numbers
- Relevant code snippets showing API client setup

---

### Test 4: Find Similar Code Pattern
**Prompt:**
```
Using the code-index-semantic-search server, find code similar to this pattern:

```python
class Client:
    def __init__(self, api_key: str):
        self.api_key = api_key
```

Show me the top 3 most similar code chunks.
```

**Expected Output:**
- Similar initialization patterns
- Code chunks with class constructors
- Similarity scores

---

### Test 5: Multi-Language Search
**Prompt:**
```
Search for "error handling and exception management" but only in Python files.
Use the code-index-semantic-search server and limit to top 5 results.
```

**Expected Output:**
- Python-specific results
- Error handling code patterns
- Try/except blocks or error classes

---

## 🔧 Troubleshooting

### Issue: "Server not responding"
**Check:**
1. Restart Claude Desktop after config changes
2. Verify API key is correct (no extra spaces)
3. Check service is running:
   ```bash
   gcloud run services describe code-index-mcp-dev --region=us-east1
   ```

### Issue: "Authentication failed"
**Solution:**
- The API key in config must match exactly
- No quotes around the key in JSON (already in string)
- Restart Claude Desktop after changes

### Issue: "No tools available"
**Check:**
1. SSE endpoint URL ends with `/sse`
2. Transport is set to `"sse"` (not `"http"`)
3. Headers section includes X-API-Key

---

## 📊 Expected Tool List

When you run Test 1, you should see these tools:

**Semantic Search Tools:**
- `semantic_search_code` - Natural language code search
- `find_similar_code` - Find code similar to a snippet
- `ingest_code_from_git` - Ingest GitHub/GitLab repositories

**Project Management Tools:**
- `set_project_path` - Set the project directory
- `refresh_index` - Rebuild file index
- `build_deep_index` - Build symbol-level index

**Search Tools:**
- `search_code_advanced` - Regex/fuzzy search
- `find_files` - Find files by pattern

**File Analysis Tools:**
- `get_file_summary` - Get file structure
- `get_file_watcher_status` - Check file watcher
- `configure_file_watcher` - Configure auto-refresh

**Settings Tools:**
- `get_settings_info` - View configuration
- `clear_settings` - Reset settings
- `refresh_search_tools` - Re-detect search tools

---

## 💡 Pro Tips

1. **First ingestion takes time** - A typical repository with 100 files might take 2-3 minutes
2. **Semantic search is powerful** - Use natural language, not just keywords
3. **Language filtering** - Specify language to get more focused results
4. **Top-k parameter** - Default is 10, but you can request 5-20 results
5. **Private repos** - Provide GitHub personal access token for private repositories

---

## 🚀 Advanced Testing

### Test Private Repository Ingestion
```
Ingest this private repository using my personal access token:
https://github.com/my-org/my-private-repo

Token: ghp_xxxxxxxxxxxx
```

### Test Cross-File Search
```
Find all code related to "database connection pooling" across the entire repository.
Show results from different files to demonstrate the semantic understanding.
```

### Test Code Similarity Detection
```
Find duplicate or similar code patterns for refactoring opportunities.
Search for code similar to:
[paste a function from your codebase]
```

---

**Happy Testing! 🎉**

For issues, check Cloud Run logs:
```bash
gcloud run services logs read code-index-mcp-dev --region=us-east1
```
