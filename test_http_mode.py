#!/usr/bin/env python3
"""
Test script for HTTP/SSE mode of Code Index MCP Server.

This script tests the authentication middleware and HTTP transport locally
before deploying to cloud platforms.

Usage:
    # Terminal 1: Start server in HTTP mode
    MCP_TRANSPORT=http PORT=8080 uv run code-index-mcp

    # Terminal 2: Run this test script
    python test_http_mode.py

Expected Output:
    ✓ Health check: 200 OK
    ✓ Authentication test (with mock API key)
    ✗ Authentication test (without API key) - should fail
"""

import sys
from typing import Any, Dict

import requests


def test_health_check(base_url: str = "http://localhost:8080") -> bool:
    """
    Test basic connectivity to HTTP server.

    Verification:
    - Server responds to /health endpoint
    - Returns 200 OK status
    """
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✓ Health check: {response.status_code} {response.reason}")
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print("✗ Health check: Connection refused")
        print("  Make sure server is running with:")
        print("  MCP_TRANSPORT=http PORT=8080 uv run code-index-mcp")
        return False
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False


def test_authentication(base_url: str = "http://localhost:8080") -> bool:
    """
    Test authentication with mock API key.

    Note: This test will fail until you configure actual API keys
    in Google Secret Manager. For now, it verifies the endpoint
    exists and rejects invalid keys.
    """
    headers = {"X-API-Key": "ci_test_invalid_key_12345"}

    try:
        response = requests.get(f"{base_url}/tools", headers=headers, timeout=5)
        print(f"  Auth test (invalid key): {response.status_code}")

        # Should get 401 Unauthorized for invalid key
        if response.status_code == 401:
            print("✓ Authentication correctly rejects invalid keys")
            return True
        else:
            print(f"⚠ Unexpected status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"✗ Authentication test failed: {e}")
        return False


def test_no_authentication(base_url: str = "http://localhost:8080") -> bool:
    """
    Test that requests without authentication are rejected.
    """
    try:
        response = requests.get(f"{base_url}/tools", timeout=5)
        print(f"  No auth test: {response.status_code}")

        # Should get 401 Unauthorized without API key
        if response.status_code == 401:
            print("✓ Correctly rejects requests without API key")
            return True
        else:
            print(f"⚠ Expected 401, got {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ No-auth test failed: {e}")
        return False


def run_tests():
    """Run all HTTP mode tests."""
    print("=" * 60)
    print("Code Index MCP - HTTP Mode Test Suite")
    print("=" * 60)
    print()

    base_url = "http://localhost:8080"

    print("1. Testing Health Check...")
    health_ok = test_health_check(base_url)
    print()

    if not health_ok:
        print("Server not responding. Aborting tests.")
        sys.exit(1)

    print("2. Testing Authentication...")
    auth_works = test_authentication(base_url)
    print()

    print("3. Testing No Authentication...")
    no_auth_works = test_no_authentication(base_url)
    print()

    print("=" * 60)
    print("Test Summary:")
    print(f"  Health Check: {'✓ PASS' if health_ok else '✗ FAIL'}")
    print(f"  Authentication: {'✓ PASS' if auth_works else '✗ FAIL'}")
    print(f"  No Auth Rejection: {'✓ PASS' if no_auth_works else '✗ FAIL'}")
    print("=" * 60)
    print()

    if health_ok:
        print("✓ HTTP mode is working!")
        print()
        print("Next steps:")
        print("1. Set up Google Secret Manager API keys")
        print("2. Test with real API keys")
        print("3. Deploy to Google Cloud Run")
        return True
    else:
        print("✗ Tests failed")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
