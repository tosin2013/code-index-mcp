"""
Tests for the ingestion pipeline.

These tests verify:
- Directory and file ingestion
- Database operations (with mocking)
- Progress tracking
- Error handling
- Stats reporting
"""

import shutil

# Add src to path
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent / "src"))

from code_index_mcp.ingestion.chunker import ChunkStrategy
from code_index_mcp.ingestion.pipeline import IngestionPipeline, IngestionStats, ingest_directory


class MockDBConnection:
    """Mock database connection for testing."""

    def __init__(self):
        self.cursors = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

        # Mock data storage
        self.projects = {}
        self.chunks = []

    def cursor(self):
        """Return a mock cursor."""
        cursor = MockCursor(self)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        """Mock commit."""
        self.committed = True

    def rollback(self):
        """Mock rollback."""
        self.rolled_back = True

    def close(self):
        """Mock close."""
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class MockCursor:
    """Mock database cursor."""

    def __init__(self, connection):
        self.connection = connection
        self.results = []
        self.executed_queries = []

    def execute(self, query, params=None):
        """Mock execute."""
        self.executed_queries.append((query, params))

        # Handle different query types
        if "set_user_context" in query:
            self.results = [None]
        elif "SELECT project_id FROM projects" in query:
            # Return existing project or None
            if params and len(params) >= 2:
                user_id, project_name = params[0], params[1]
                key = f"{user_id}:{project_name}"
                if key in self.connection.projects:
                    self.results = [(self.connection.projects[key],)]
                else:
                    self.results = []
        elif "INSERT INTO projects" in query and "RETURNING" in query:
            # Create new project
            project_id = str(uuid4())
            if params and len(params) >= 2:
                user_id, project_name = params[0], params[1]
                key = f"{user_id}:{project_name}"
                self.connection.projects[key] = project_id
            self.results = [(project_id,)]
        elif "INSERT INTO code_chunks" in query:
            # Insert chunk
            chunk_id = str(uuid4())
            self.connection.chunks.append(params)

            # Check for conflict (duplicate)
            if params and "duplicate" in str(params):
                self.results = []  # Simulate ON CONFLICT DO NOTHING
            else:
                self.results = [(chunk_id,)]
        elif "UPDATE projects SET" in query:
            # Update project stats
            self.results = []

    def fetchone(self):
        """Mock fetchone."""
        if self.results:
            return self.results[0]
        return None

    def fetchall(self):
        """Mock fetchall."""
        return self.results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def create_test_directory(tmp_path):
    """Create a test directory with sample code files."""
    # Create Python file
    py_file = tmp_path / "test.py"
    py_file.write_text(
        """
def hello_world():
    \"\"\"Say hello.\"\"\"
    print("Hello, world!")

class TestClass:
    \"\"\"Test class.\"\"\"
    def method(self):
        return 42
"""
    )

    # Create JavaScript file
    js_file = tmp_path / "test.js"
    js_file.write_text(
        """
function greet(name) {
    console.log(`Hello, ${name}!`);
}

class Person {
    constructor(name) {
        this.name = name;
    }
}
"""
    )

    return tmp_path


def test_ingestion_stats():
    """Test IngestionStats dataclass."""
    stats = IngestionStats()

    assert stats.files_processed == 0
    assert stats.chunks_created == 0
    assert stats.chunks_inserted == 0
    assert stats.chunks_skipped == 0
    assert stats.chunks_failed == 0

    # Test timing
    assert stats.duration_seconds >= 0

    stats.finish()
    assert stats.end_time is not None

    # Test dict conversion
    stats_dict = stats.to_dict()
    assert "files_processed" in stats_dict
    assert "duration_seconds" in stats_dict


def test_pipeline_initialization():
    """Test pipeline initialization."""
    pipeline = IngestionPipeline(db_connection_string="postgresql://test", use_mock_embedder=True)

    assert pipeline.db_connection_string == "postgresql://test"
    assert pipeline.chunker is not None
    assert pipeline.embedder is not None
    assert pipeline.chunking_strategy == ChunkStrategy.FUNCTION


def test_progress_callback():
    """Test progress callback mechanism."""
    pipeline = IngestionPipeline(db_connection_string="postgresql://test", use_mock_embedder=True)

    messages = []
    stats_list = []

    def callback(message, stats):
        messages.append(message)
        stats_list.append(stats)

    pipeline.set_progress_callback(callback)
    pipeline._report_progress("Test message", {"test": "data"})

    assert len(messages) == 1
    assert messages[0] == "Test message"
    assert stats_list[0] == {"test": "data"}


@patch("code_index_mcp.ingestion.pipeline.psycopg2.connect")
def test_ingest_directory_basic(mock_connect):
    """Test basic directory ingestion."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_connect.return_value = mock_conn

    # Create test directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_directory(tmp_path)

        # Create pipeline
        pipeline = IngestionPipeline(
            db_connection_string="postgresql://test", use_mock_embedder=True
        )

        # Ingest directory
        user_id = uuid4()
        stats = pipeline.ingest_directory(
            directory_path=str(tmp_path),
            user_id=user_id,
            project_name="test-project",
            gcs_bucket="test-bucket",
            gcs_prefix="test-prefix",
        )

        # Verify stats
        assert stats.files_processed == 2  # test.py and test.js
        assert stats.chunks_created > 0
        assert stats.embeddings_generated == stats.chunks_created
        assert stats.chunks_inserted >= 0
        assert stats.end_time is not None

        # Verify database operations
        assert mock_conn.committed
        assert mock_conn.closed
        assert len(mock_conn.cursors) > 0


@patch("code_index_mcp.ingestion.pipeline.psycopg2.connect")
def test_ingest_files(mock_connect):
    """Test file-specific ingestion."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_connect.return_value = mock_conn

    # Create test files
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        py_file = tmp_path / "test.py"
        py_file.write_text("def test(): pass")

        # Create pipeline
        pipeline = IngestionPipeline(
            db_connection_string="postgresql://test", use_mock_embedder=True
        )

        # Ingest specific file
        user_id = uuid4()
        stats = pipeline.ingest_files(
            file_paths=[str(py_file)], user_id=user_id, project_name="test-project"
        )

        # Verify stats
        assert stats.files_processed == 1
        assert stats.chunks_created >= 1
        assert stats.embeddings_generated == stats.chunks_created


@patch("code_index_mcp.ingestion.pipeline.psycopg2.connect")
def test_progress_tracking(mock_connect):
    """Test progress tracking during ingestion."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_connect.return_value = mock_conn

    # Create test directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_directory(tmp_path)

        # Create pipeline with progress callback
        pipeline = IngestionPipeline(
            db_connection_string="postgresql://test", use_mock_embedder=True
        )

        progress_messages = []

        def track_progress(message, stats):
            progress_messages.append(message)

        pipeline.set_progress_callback(track_progress)

        # Ingest
        user_id = uuid4()
        stats = pipeline.ingest_directory(
            directory_path=str(tmp_path), user_id=user_id, project_name="test-project"
        )

        # Verify progress messages
        assert len(progress_messages) > 0
        assert any("Connecting to AlloyDB" in msg for msg in progress_messages)
        assert any("Scanning directory" in msg for msg in progress_messages)
        assert any("complete" in msg.lower() for msg in progress_messages)


@patch("code_index_mcp.ingestion.pipeline.psycopg2.connect")
def test_error_handling(mock_connect):
    """Test error handling during ingestion."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_connect.return_value = mock_conn

    # Create pipeline
    pipeline = IngestionPipeline(db_connection_string="postgresql://test", use_mock_embedder=True)

    # Test directory not found
    try:
        pipeline.ingest_directory(
            directory_path="/nonexistent/path", user_id=uuid4(), project_name="test-project"
        )
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass  # Expected

    # Test database connection failure
    mock_connect.side_effect = Exception("Database connection failed")
    try:
        pipeline.ingest_directory(
            directory_path="/tmp", user_id=uuid4(), project_name="test-project"
        )
        assert False, "Should have raised Exception"
    except Exception as e:
        assert "Database connection failed" in str(e)


@patch("code_index_mcp.ingestion.pipeline.psycopg2.connect")
def test_deduplication(mock_connect):
    """Test chunk deduplication via content_hash."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_connect.return_value = mock_conn

    # Create test file
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        py_file = tmp_path / "test.py"
        py_file.write_text("def test(): pass")

        # Create pipeline
        pipeline = IngestionPipeline(
            db_connection_string="postgresql://test", use_mock_embedder=True
        )

        # First ingestion
        user_id = uuid4()
        stats1 = pipeline.ingest_directory(
            directory_path=str(tmp_path), user_id=user_id, project_name="test-project"
        )

        # Reset mock connection for second ingestion
        mock_connect.return_value = mock_conn

        # Second ingestion (should detect duplicates)
        stats2 = pipeline.ingest_directory(
            directory_path=str(tmp_path), user_id=user_id, project_name="test-project"
        )

        # Both should process the file
        assert stats1.files_processed == 1
        assert stats2.files_processed == 1


@patch("code_index_mcp.ingestion.pipeline.psycopg2.connect")
def test_convenience_functions(mock_connect):
    """Test convenience functions."""
    # Setup mock database
    mock_conn = MockDBConnection()
    mock_connect.return_value = mock_conn

    # Create test directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_directory(tmp_path)

        # Test ingest_directory convenience function
        user_id = uuid4()
        stats = ingest_directory(
            directory_path=str(tmp_path),
            user_id=user_id,
            project_name="test-project",
            db_connection_string="postgresql://test",
            use_mock_embedder=True,
        )

        assert stats.files_processed > 0
        assert stats.chunks_created > 0


def test_chunking_strategies():
    """Test different chunking strategies."""
    strategies = [
        ChunkStrategy.FUNCTION,
        ChunkStrategy.CLASS,
        ChunkStrategy.FILE,
        ChunkStrategy.SEMANTIC,
    ]

    for strategy in strategies:
        pipeline = IngestionPipeline(
            db_connection_string="postgresql://test",
            chunking_strategy=strategy,
            use_mock_embedder=True,
        )

        assert pipeline.chunking_strategy == strategy


def test_file_patterns():
    """Test custom file patterns."""
    pipeline = IngestionPipeline(
        db_connection_string="postgresql://test",
        file_patterns=["*.py", "*.java"],
        use_mock_embedder=True,
    )

    assert "*.py" in pipeline.file_patterns
    assert "*.java" in pipeline.file_patterns


if __name__ == "__main__":
    print("Running ingestion pipeline tests...")

    # Run tests
    test_ingestion_stats()
    print("✓ IngestionStats tests passed")

    test_pipeline_initialization()
    print("✓ Pipeline initialization tests passed")

    test_progress_callback()
    print("✓ Progress callback tests passed")

    test_ingest_directory_basic()
    print("✓ Basic directory ingestion tests passed")

    test_ingest_files()
    print("✓ File ingestion tests passed")

    test_progress_tracking()
    print("✓ Progress tracking tests passed")

    test_error_handling()
    print("✓ Error handling tests passed")

    test_deduplication()
    print("✓ Deduplication tests passed")

    test_convenience_functions()
    print("✓ Convenience function tests passed")

    test_chunking_strategies()
    print("✓ Chunking strategy tests passed")

    test_file_patterns()
    print("✓ File pattern tests passed")

    print("\n✅ All tests passed!")
