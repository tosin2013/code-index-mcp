#!/usr/bin/env python3
"""
MCP Server Validation Script

Validates an MCP server by calling its tools via HTTP/SSE transport.
"""
import json
import sys
import time
from typing import Any, Dict, Optional

import requests


class MCPValidator:
    def __init__(self, service_url: str):
        self.service_url = service_url.rstrip("/")
        self.session_id = None
        self.messages_url = None

    def establish_session(self) -> bool:
        """Establish SSE session and get messages endpoint."""
        try:
            response = requests.get(
                f"{self.service_url}/sse",
                headers={"Accept": "text/event-stream"},
                stream=True,
                timeout=10,
            )

            # Read first few lines to get session endpoint
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    endpoint = line[6:].strip()  # Remove 'data: ' prefix
                    self.messages_url = f"{self.service_url}{endpoint}"
                    # Extract session ID from URL
                    if "?" in endpoint:
                        params = endpoint.split("?")[1]
                        for param in params.split("&"):
                            if param.startswith("session_id="):
                                self.session_id = param.split("=")[1]
                    return True
            return False
        except Exception as e:
            print(f"❌ Failed to establish session: {e}", file=sys.stderr)
            return False

    def call_tool(self, method: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Make a JSON-RPC call to the MCP server."""
        if not self.messages_url:
            print("❌ No session established", file=sys.stderr)
            return None

        request_id = f"{method}-{int(time.time() * 1000)}"
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            payload["params"] = params

        try:
            # Post message (202 Accepted response)
            response = requests.post(
                self.messages_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code != 202:
                print(f"❌ Unexpected status: {response.status_code}", file=sys.stderr)
                return None

            # Read response from SSE stream
            sse_response = requests.get(
                f"{self.service_url}/sse?session_id={self.session_id}",
                headers={"Accept": "text/event-stream"},
                stream=True,
                timeout=30,
            )

            for line in sse_response.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("id") == request_id:
                            return data
                    except json.JSONDecodeError:
                        continue

            return None
        except Exception as e:
            print(f"❌ Tool call failed: {e}", file=sys.stderr)
            return None

    def list_tools(self) -> Optional[list]:
        """List available MCP tools."""
        result = self.call_tool("tools/list")
        if result and "result" in result:
            return [tool["name"] for tool in result["result"].get("tools", [])]
        return None

    def run_validation(
        self, run_ingestion: bool = False, run_search: bool = False
    ) -> Dict[str, Any]:
        """Run complete validation."""
        results = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "service_url": self.service_url,
            "tests": {},
        }

        # Test 1: Establish session
        print(f"Testing SSE endpoint: {self.service_url}/sse")
        if not self.establish_session():
            results["tests"]["sse_endpoint"] = "FAILED"
            return results
        results["tests"]["sse_endpoint"] = "PASSED"
        print(f"✅ Session established: {self.messages_url}")

        # Test 2: List tools
        print("\nListing available tools...")
        tools = self.list_tools()
        if not tools:
            results["tests"]["tools_list"] = "FAILED"
            return results
        results["tests"]["tools_list"] = "PASSED"
        results["available_tools"] = tools
        print(f"✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool}")

        # Test 3: Ingestion (optional)
        if run_ingestion:
            print("\nTesting git repository ingestion...")
            result = self.call_tool(
                "tools/call",
                {
                    "name": "ingest_git_repository",
                    "arguments": {
                        "repository_url": "https://github.com/octocat/Hello-World",
                        "project_name": f"validation-test-{int(time.time())}",
                    },
                },
            )
            if result and "result" in result:
                results["tests"]["ingestion"] = "PASSED"
                print("✅ Git ingestion successful")
            else:
                results["tests"]["ingestion"] = "FAILED"
                print("❌ Git ingestion failed")
        else:
            results["tests"]["ingestion"] = "SKIPPED"

        # Test 4: Search (optional)
        if run_search:
            print("\nTesting semantic search...")
            result = self.call_tool(
                "tools/call",
                {
                    "name": "semantic_search",
                    "arguments": {"query": "hello world function", "top_k": 5},
                },
            )
            if result and "result" in result:
                results["tests"]["semantic_search"] = "PASSED"
                print("✅ Semantic search successful")
            else:
                results["tests"]["semantic_search"] = "FAILED"
                print("❌ Semantic search failed")
        else:
            results["tests"]["semantic_search"] = "SKIPPED"

        return results


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_mcp.py <service_url> [--ingestion] [--search]", file=sys.stderr)
        sys.exit(1)

    service_url = sys.argv[1]
    run_ingestion = "--ingestion" in sys.argv
    run_search = "--search" in sys.argv

    print("=" * 50)
    print("MCP Server Validation")
    print("=" * 50)
    print(f"Service URL: {service_url}")
    print("=" * 50)
    print()

    validator = MCPValidator(service_url)
    results = validator.run_validation(run_ingestion, run_search)

    print("\n" + "=" * 50)
    print("Validation Summary")
    print("=" * 50)
    for test, status in results["tests"].items():
        icon = "✅" if status == "PASSED" else "⏭️" if status == "SKIPPED" else "❌"
        print(f"{icon} {test}: {status}")
    print("=" * 50)

    # Output JSON for Ansible
    print("\n" + json.dumps(results, indent=2))

    # Exit code: 0 if all run tests passed, 1 otherwise
    failed = any(status == "FAILED" for status in results["tests"].values())
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
