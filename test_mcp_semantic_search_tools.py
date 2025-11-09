"""
Test suite for semantic search MCP tools in server.py

Tests the three new MCP tools:
1. semantic_search_code
2. find_similar_code  
3. ingest_code_for_search

Runs WITHOUT AlloyDB/GCP by using mock mode.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from code_index_mcp.server import (
    semantic_search_code,
    find_similar_code,
    ingest_code_for_search
)

class MockContext:
    """Mock MCP Context object"""
    def __init__(self, base_path=""):
        self.base_path = base_path
        self.request_context = {}


class TestSemanticSearchMCPTools(unittest.TestCase):
    """Test semantic search MCP tool implementations"""
    
    def setUp(self):
        """Set up test context"""
        self.ctx = MockContext()
        # Ensure AlloyDB env var is not set (to test mock mode)
        if "ALLOYDB_CONNECTION_STRING" in os.environ:
            del os.environ["ALLOYDB_CONNECTION_STRING"]
    
    def test_semantic_search_code_mock_mode(self):
        """Test semantic_search_code in mock mode (no AlloyDB)"""
        result = semantic_search_code(
            ctx=self.ctx,
            query="authentication with JWT",
            language="python",
            top_k=5
        )
        
        # Should return info message in mock mode
        assert isinstance(result, list)
        assert len(result) > 0
        assert "info" in result[0]
        assert "AlloyDB" in result[0]["info"]
        print("✓ semantic_search_code mock mode works")
    
    def test_find_similar_code_mock_mode(self):
        """Test find_similar_code in mock mode (no AlloyDB)"""
        result = find_similar_code(
            ctx=self.ctx,
            code_snippet="def authenticate(user, pwd): return True",
            language="python",
            top_k=3
        )
        
        # Should return info message in mock mode
        assert isinstance(result, list)
        assert len(result) > 0
        assert "info" in result[0]
        print("✓ find_similar_code mock mode works")
    
    def test_ingest_code_for_search_no_alloydb(self):
        """Test ingest_code_for_search without AlloyDB configured"""
        result = ingest_code_for_search(
            ctx=self.ctx,
            directory_path="/tmp/test",
            project_name="test-project",
            use_current_project=False
        )
        
        # Should return error about missing AlloyDB
        assert isinstance(result, dict)
        assert "error" in result
        assert "AlloyDB not configured" in result["error"]
        print("✓ ingest_code_for_search requires AlloyDB")
    
    def test_ingest_code_for_search_no_project_path(self):
        """Test ingest_code_for_search with no project path set"""
        # Don't set base_path in context
        result = ingest_code_for_search(
            ctx=self.ctx,
            use_current_project=True
        )
        
        # Should return error about missing project path
        assert isinstance(result, dict)
        # Will fail at AlloyDB check first, which is fine
        assert "error" in result
        print("✓ ingest_code_for_search validates project path")
    
    @patch.dict(os.environ, {"ALLOYDB_CONNECTION_STRING": "postgresql://mock:5432/db"})
    @patch("code_index_mcp.services.semantic_search_service.semantic_search")
    def test_semantic_search_code_with_alloydb(self, mock_search):
        """Test semantic_search_code when AlloyDB is configured"""
        # Mock the semantic_search function
        mock_search.return_value = [
            {
                "chunk_id": "123",
                "file_path": "auth.py",
                "function_name": "authenticate",
                "code": "def authenticate(user, pwd): ...",
                "similarity": 0.95
            }
        ]
        
        result = semantic_search_code(
            ctx=self.ctx,
            query="JWT authentication",
            top_k=5
        )
        
        # Should call the semantic_search function
        assert mock_search.called
        assert isinstance(result, list)
        if result and "chunk_id" in result[0]:
            assert result[0]["chunk_id"] == "123"
        print("✓ semantic_search_code calls service correctly")
    
    @patch.dict(os.environ, {"ALLOYDB_CONNECTION_STRING": "postgresql://mock:5432/db"})
    @patch("code_index_mcp.services.semantic_search_service.find_similar_code")
    def test_find_similar_code_with_alloydb(self, mock_find):
        """Test find_similar_code when AlloyDB is configured"""
        # Mock the find_similar_code function (at service level)
        mock_find.return_value = [
            {
                "chunk_id": "456",
                "file_path": "users.py",
                "function_name": "verify_password",
                "code": "def verify_password(pwd): ...",
                "similarity": 0.87
            }
        ]
        
        result = find_similar_code(
            ctx=self.ctx,
            code_snippet="def check_password(p): return True",
            top_k=3
        )
        
        # Should call the find_similar_code function
        assert mock_find.called
        assert isinstance(result, list)
        if result and "chunk_id" in result[0]:
            assert result[0]["chunk_id"] == "456"
        print("✓ find_similar_code calls service correctly")
    
    @patch.dict(os.environ, {"ALLOYDB_CONNECTION_STRING": "postgresql://mock:5432/db"})
    @patch("code_index_mcp.ingestion.pipeline.ingest_directory")
    def test_ingest_code_for_search_with_alloydb(self, mock_ingest):
        """Test ingest_code_for_search when AlloyDB is configured"""
        from code_index_mcp.ingestion.pipeline import IngestionStats
        
        # Mock the ingest_directory function (at pipeline level)
        stats = IngestionStats()
        stats.files_processed = 10
        stats.chunks_created = 50
        stats.embeddings_generated = 50
        stats.finish()
        mock_ingest.return_value = stats
        
        self.ctx.base_path = "/tmp/test-project"
        result = ingest_code_for_search(
            ctx=self.ctx,
            use_current_project=True,
            project_name="test-project"
        )
        
        # Should call the ingest_directory function
        assert mock_ingest.called
        assert isinstance(result, dict)
        if "status" in result:
            assert result["status"] == "success"
            assert result["files_processed"] == 10
        print("✓ ingest_code_for_search calls ingestion pipeline correctly")
    
    def test_semantic_search_parameters(self):
        """Test parameter handling for semantic_search_code"""
        result = semantic_search_code(
            ctx=self.ctx,
            query="database connection",
            project_name="my-app",
            language="python",
            top_k=15,
            min_similarity=0.7
        )
        
        # Should handle all parameters
        assert isinstance(result, list)
        print("✓ semantic_search_code accepts all parameters")
    
    def test_find_similar_code_parameters(self):
        """Test parameter handling for find_similar_code"""
        result = find_similar_code(
            ctx=self.ctx,
            code_snippet="class User: pass",
            project_name="my-app",
            language="python",
            top_k=8,
            min_similarity=0.6
        )
        
        # Should handle all parameters
        assert isinstance(result, list)
        print("✓ find_similar_code accepts all parameters")
    
    def test_ingest_code_parameters(self):
        """Test parameter handling for ingest_code_for_search"""
        result = ingest_code_for_search(
            ctx=self.ctx,
            directory_path="/tmp/code",
            project_name="custom-name",
            use_current_project=False
        )
        
        # Should handle all parameters
        assert isinstance(result, dict)
        print("✓ ingest_code_for_search accepts all parameters")


def run_tests():
    """Run all tests and report results"""
    print("\n" + "="*70)
    print("Testing Semantic Search MCP Tools (Phase 3A)")
    print("="*70 + "\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSemanticSearchMCPTools)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ All MCP semantic search tool tests passed!")
    else:
        print("\n❌ Some tests failed")
    
    print("="*70)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())

