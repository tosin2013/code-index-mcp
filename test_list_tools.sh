#!/bin/bash

# Get SSE session
echo "=== Connecting to SSE endpoint ==="
SESSION_RESPONSE=$(curl -s -N "https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app/sse" \
    -H "Accept: text/event-stream" \
    -H "X-API-Key: ci_35ee58d690a4b6127a03b712330c5ba562285ca9d5516d3d9ba3e42582d97b9b" | head -3)
echo "$SESSION_RESPONSE"

# Extract session ID
SESSION_ID=$(echo "$SESSION_RESPONSE" | grep "session_id=" | sed -E 's/.*session_id=([a-f0-9-]+).*/\1/')
echo ""
echo "Session ID: $SESSION_ID"

if [ -z "$SESSION_ID" ]; then
    echo "ERROR: Could not get session ID"
    exit 1
fi

# Initialize the MCP protocol
echo ""
echo "=== Initializing MCP protocol ==="
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

curl -s -X POST "https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app/messages/?session_id=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ci_35ee58d690a4b6127a03b712330c5ba562285ca9d5516d3d9ba3e42582d97b9b" \
  -d "$INIT_REQUEST"

echo ""
echo ""

# List tools
echo "=== Listing MCP tools ==="
TOOLS_REQUEST='{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}'

TOOLS_RESPONSE=$(curl -s -X POST "https://code-index-mcp-dev-cjshzpy4wq-ue.a.run.app/messages/?session_id=$SESSION_ID" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ci_35ee58d690a4b6127a03b712330c5ba562285ca9d5516d3d9ba3e42582d97b9b" \
  -d "$TOOLS_REQUEST")

echo "$TOOLS_RESPONSE" | jq -r '.result.tools[] | "- \(.name): \(.description)"' | head -15
