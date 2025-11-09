"""
Tests for the semantic search service.

These tests verify:
- Semantic search with vector similarity
- Similar code finding
- Hybrid search (semantic + keyword)
- Result formatting and ranking
- Mock mode for testing without GCP
"""

import sys
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from code_index_mcp.services.semantic_search_service import (
    SemanticSearchService,
    SemanticSearchResult,
    semantic_search,
    find_similar_code,
)


class MockDBConnection:
    """Mock database connection for testing."""
    
    def __init__(self):
        self.cursors = []
        self.committed = False
        self.closed = False
        
        # Mock data
        self.results = []
    
    def cursor(self):
        """Return a mock cursor."""
        cursor = MockCursor(self)
        self.cursors.append(cursor)
        return cursor
    
    def commit(self):
        """Mock commit."""
        self.committed = True
    
    def close(self):
        """Mock close."""
        self.closed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


class MockCursor:
    """Mock database cursor with RealDictCursor behavior."""
    
    def __init__(self, connection):
        self.connection = connection
        self.executed_queries = []
    
    def execute(self, query, params=None):
        """Mock execute."""
        self.executed_queries.append((query, params))
    
    def fetchall(self):
        """Mock fetchall returning dict-like rows."""
        return self.connection.results
    
    def fetchone(self):
        """Mock fetchone."""
        if self.connection.results:
            return self.connection.results[0]
        return None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


def create_mock_service(mock_conn):
    """Create a semantic search service with mocked embedder and database."""
    from code_index_mcp.embeddings.vertex_ai import MockVertexAIEmbedder
    mock_embedder = MockVertexAIEmbedder()
    
    return SemanticSearchService(
        db_connection_string="postgresql://test",
        embedder=mock_embedder,
        use_mock=False
    )


def create_mock_search_results():
    """Create mock search results for testing."""
    return [
        {
            'chunk_id': str(uuid4()),
            'file_path': 'auth/login.py',
            'chunk_name': 'authenticate_user',
            'chunk_type': 'function',
            'line_start': 10,
            'line_end': 25,
            'language': 'python',
            'content': 'def authenticate_user(username, password):\n    # Auth logic\n    pass',
            'symbols': {'function_name': 'authenticate_user', 'parameters': ['username', 'password']},
            'similarity_score': 0.95,
            'project_name': 'test-project'
        },
        {
            'chunk_id': str(uuid4()),
            'file_path': 'auth/session.py',
            'chunk_name': 'create_session',
            'chunk_type': 'function',
            'line_start': 5,
            'line_end': 15,
            'language': 'python',
            'content': 'def create_session(user_id):\n    # Session logic\n    pass',
            'symbols': {'function_name': 'create_session', 'parameters': ['user_id']},
            'similarity_score': 0.87,
            'project_name': 'test-project'
        },
        {
            'chunk_id': str(uuid4()),
            'file_path': 'utils/helpers.py',
            'chunk_name': 'hash_password',
            'chunk_type': 'function',
            'line_start': 20,
            'line_end': 30,
            'language': 'python',
            'content': 'def hash_password(password):\n    # Hashing logic\n    pass',
            'symbols': {'function_name': 'hash_password', 'parameters': ['password']},
            'similarity_score': 0.75,
            'project_name': 'test-project'
        }
    ]


def test_semantic_search_result():
    """Test SemanticSearchResult dataclass."""
    result = SemanticSearchResult(
        chunk_id="test-id",
        file_path="test.py",
        chunk_name="test_func",
        chunk_type="function",
        line_start=1,
        line_end=10,
        language="python",
        content="def test_func(): pass",
        symbols={"function_name": "test_func"},
        similarity_score=0.95,
        project_name="test-project"
    )
    
    assert result.chunk_id == "test-id"
    assert result.file_path == "test.py"
    assert result.similarity_score == 0.95
    
    # Test dict conversion
    result_dict = result.to_dict()
    assert "chunk_id" in result_dict
    assert "similarity_score" in result_dict
    assert result_dict["line_range"] == "1-10"
    assert result_dict["similarity_score"] == 0.95


def test_service_initialization():
    """Test service initialization."""
    # Test with mock mode
    service = SemanticSearchService(use_mock=True)
    assert service.use_mock is True
    assert service.embedder is not None
    
    # Test with real mode
    service = SemanticSearchService(
        db_connection_string="postgresql://test",
        use_mock=False
    )
    assert service.use_mock is False


@patch('code_index_mcp.services.semantic_search_service.psycopg2.connect')
def test_semantic_search_basic(mock_connect):
    """Test basic semantic search."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_conn.results = create_mock_search_results()
    mock_connect.return_value = mock_conn
    
    # Create service with mock embedder
    service = create_mock_service(mock_conn)
    
    # Perform search
    user_id = uuid4()
    results = service.semantic_search(
        query="authentication logic",
        user_id=user_id,
        top_k=10
    )
    
    # Verify results
    assert len(results) == 3
    assert all(isinstance(r, SemanticSearchResult) for r in results)
    assert results[0].similarity_score == 0.95
    assert results[0].chunk_name == "authenticate_user"
    
    # Verify database was queried
    assert mock_conn.committed
    assert mock_conn.closed


@patch('code_index_mcp.services.semantic_search_service.psycopg2.connect')
def test_semantic_search_with_filters(mock_connect):
    """Test semantic search with project and language filters."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_conn.results = create_mock_search_results()
    mock_connect.return_value = mock_conn
    
    # Create service with mock embedder
    service = create_mock_service(mock_conn)
    
    # Search with filters
    user_id = uuid4()
    results = service.semantic_search(
        query="authentication",
        user_id=user_id,
        project_name="test-project",
        language="python",
        top_k=5
    )
    
    # Verify filters were applied
    assert len(results) > 0
    for result in results:
        assert result.project_name == "test-project"
        assert result.language == "python"


@patch('code_index_mcp.services.semantic_search_service.psycopg2.connect')
def test_semantic_search_min_similarity(mock_connect):
    """Test semantic search with minimum similarity threshold."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_conn.results = create_mock_search_results()
    mock_connect.return_value = mock_conn
    
    # Create service with mock embedder
    service = create_mock_service(mock_conn)
    
    # Search with high similarity threshold
    user_id = uuid4()
    results = service.semantic_search(
        query="authentication",
        user_id=user_id,
        min_similarity=0.90,
        top_k=10
    )
    
    # Only results with similarity >= 0.90 should be returned
    assert len(results) == 1
    assert results[0].similarity_score >= 0.90


@patch('code_index_mcp.services.semantic_search_service.psycopg2.connect')
def test_find_similar_code(mock_connect):
    """Test finding similar code."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_conn.results = create_mock_search_results()
    mock_connect.return_value = mock_conn
    
    # Create service with mock embedder
    service = create_mock_service(mock_conn)
    
    # Find similar code
    user_id = uuid4()
    code_snippet = "def login(user, pwd): return auth.verify(user, pwd)"
    
    results = service.find_similar_code(
        code_snippet=code_snippet,
        user_id=user_id,
        top_k=5
    )
    
    # Verify results
    assert len(results) > 0
    assert all(isinstance(r, SemanticSearchResult) for r in results)


@patch('code_index_mcp.services.semantic_search_service.psycopg2.connect')
def test_hybrid_search(mock_connect):
    """Test hybrid search with keyword filtering."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_conn.results = create_mock_search_results()
    mock_connect.return_value = mock_conn
    
    # Create service with mock embedder
    service = create_mock_service(mock_conn)
    
    # Perform hybrid search
    user_id = uuid4()
    results = service.hybrid_search(
        query="authentication",
        user_id=user_id,
        keyword_filter="authenticate",  # Should boost results with "authenticate" in name/content
        top_k=10
    )
    
    # Verify keyword filtering worked
    assert len(results) > 0
    # First result should contain the keyword
    first_result = results[0]
    assert ("authenticate" in first_result.content.lower() or
            (first_result.chunk_name and "authenticate" in first_result.chunk_name.lower()))


@patch('code_index_mcp.services.semantic_search_service.psycopg2.connect')
def test_search_by_function_name(mock_connect):
    """Test searching by function name."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_conn.results = create_mock_search_results()
    mock_connect.return_value = mock_conn
    
    # Create service with mock embedder
    service = create_mock_service(mock_conn)
    
    # Search by function name (fuzzy)
    user_id = uuid4()
    results = service.search_by_function_name(
        function_name="authenticate",
        user_id=user_id,
        fuzzy=True
    )
    
    # Should find functions with "authenticate" in name
    assert len(results) > 0
    for result in results:
        assert result.chunk_type == "function"
        assert "authenticate" in result.chunk_name.lower()


def test_mock_mode():
    """Test service in mock mode."""
    service = SemanticSearchService(use_mock=True)
    
    user_id = uuid4()
    results = service.semantic_search(
        query="test query",
        user_id=user_id,
        top_k=10
    )
    
    # Mock mode returns empty results
    assert results == []


@patch('code_index_mcp.services.semantic_search_service.psycopg2.connect')
def test_convenience_functions(mock_connect):
    """Test convenience functions."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_conn.results = create_mock_search_results()
    mock_connect.return_value = mock_conn
    
    user_id = uuid4()
    
    # Test semantic_search convenience function with mock mode
    results = semantic_search(
        query="authentication",
        user_id=user_id,
        db_connection_string="postgresql://test",
        top_k=5,
        use_mock=True  # Use mock mode to avoid embedder initialization
    )
    
    # Mock mode returns empty results
    assert isinstance(results, list)
    
    # Test find_similar_code convenience function with mock mode
    results = find_similar_code(
        code_snippet="def test(): pass",
        user_id=user_id,
        db_connection_string="postgresql://test",
        top_k=3,
        use_mock=True  # Use mock mode to avoid embedder initialization
    )
    
    assert isinstance(results, list)


def test_result_formatting():
    """Test result to_dict formatting."""
    result = SemanticSearchResult(
        chunk_id="test-id",
        file_path="test.py",
        chunk_name="test_func",
        chunk_type="function",
        line_start=1,
        line_end=10,
        language="python",
        content="def test(): pass",
        symbols={"test": "data"},
        similarity_score=0.123456789,
        project_name="test-project"
    )
    
    result_dict = result.to_dict()
    
    # Check all fields present
    assert "chunk_id" in result_dict
    assert "file_path" in result_dict
    assert "line_range" in result_dict
    assert "similarity_score" in result_dict
    
    # Check formatting
    assert result_dict["line_range"] == "1-10"
    assert result_dict["similarity_score"] == 0.1235  # Rounded to 4 decimals


if __name__ == "__main__":
    print("Running semantic search tests...")
    
    # Run tests
    test_semantic_search_result()
    print("✓ SemanticSearchResult tests passed")
    
    test_service_initialization()
    print("✓ Service initialization tests passed")
    
    test_semantic_search_basic()
    print("✓ Basic semantic search tests passed")
    
    test_semantic_search_with_filters()
    print("✓ Semantic search with filters tests passed")
    
    test_semantic_search_min_similarity()
    print("✓ Minimum similarity threshold tests passed")
    
    test_find_similar_code()
    print("✓ Find similar code tests passed")
    
    test_hybrid_search()
    print("✓ Hybrid search tests passed")
    
    test_search_by_function_name()
    print("✓ Search by function name tests passed")
    
    test_mock_mode()
    print("✓ Mock mode tests passed")
    
    test_convenience_functions()
    print("✓ Convenience function tests passed")
    
    test_result_formatting()
    print("✓ Result formatting tests passed")
    
    print("\n✅ All tests passed!")

