#!/bin/bash

# Test MCP API on Cloud Run
BASE_URL="https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app"

echo "=== Step 1: Connect to SSE endpoint ==="
SSE_RESPONSE=$(curl -s -N "$BASE_URL/sse" -H "Accept: text/event-stream" | head -3)
echo "$SSE_RESPONSE"

# Extract session ID from SSE response
SESSION_ID=$(echo "$SSE_RESPONSE" | grep "session_id=" | sed -E 's/.*session_id=([a-f0-9-]+).*/\1/')
echo ""
echo "Session ID: $SESSION_ID"

if [ -z "$SESSION_ID" ]; then
    echo "ERROR: Could not get session ID"
    exit 1
fi

echo ""
echo "=== Step 2: Send initialize request ==="
INIT_REQUEST='{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "test-client",
      "version": "1.0.0"
    }
  }
}'

curl -s -X POST "$BASE_URL/messages/?session_id=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d "$INIT_REQUEST" | jq '.'

echo ""
echo "=== Step 3: List available tools ==="
TOOLS_REQUEST='{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}'

curl -s -X POST "$BASE_URL/messages/?session_id=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d "$TOOLS_REQUEST" | jq '.result.tools[] | {name: .name, description: .description}' | head -30

