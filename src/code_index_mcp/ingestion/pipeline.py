"""
Ingestion pipeline for code chunks to AlloyDB.

This module orchestrates the chunk → embed → store workflow for semantic search.
It handles:
- Directory scanning and code chunking
- Embedding generation via Vertex AI
- Storage in AlloyDB with deduplication
- Progress tracking and error handling
- Incremental updates
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Set
from uuid import UUID
import psycopg2
from psycopg2.extras import execute_values
from psycopg2 import sql, IntegrityError

from .chunker import CodeChunker, CodeChunk, ChunkStrategy
from ..embeddings.vertex_ai import VertexAIEmbedder, MockVertexAIEmbedder, EmbeddingConfig

logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """
    Statistics for an ingestion run.
    
    Attributes:
        files_processed: Number of files processed
        chunks_created: Total chunks created
        chunks_inserted: Chunks successfully inserted into database
        chunks_skipped: Chunks skipped (duplicates)
        chunks_failed: Chunks that failed to insert
        embeddings_generated: Number of embeddings generated
        start_time: Start timestamp
        end_time: End timestamp
        errors: List of error messages
    """
    files_processed: int = 0
    chunks_created: int = 0
    chunks_inserted: int = 0
    chunks_skipped: int = 0
    chunks_failed: int = 0
    embeddings_generated: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    errors: List[str] = field(default_factory=list)
    
    def finish(self):
        """Mark ingestion as finished."""
        self.end_time = time.time()
    
    @property
    def duration_seconds(self) -> float:
        """Get ingestion duration in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "files_processed": self.files_processed,
            "chunks_created": self.chunks_created,
            "chunks_inserted": self.chunks_inserted,
            "chunks_skipped": self.chunks_skipped,
            "chunks_failed": self.chunks_failed,
            "embeddings_generated": self.embeddings_generated,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
        }


class IngestionPipeline:
    """
    Pipeline for ingesting code into AlloyDB for semantic search.
    
    Orchestrates:
    1. Code chunking (via CodeChunker)
    2. Embedding generation (via VertexAIEmbedder)
    3. Storage in AlloyDB (with deduplication)
    4. Progress tracking
    """
    
    def __init__(
        self,
        db_connection_string: str,
        embedder: Optional[VertexAIEmbedder] = None,
        chunking_strategy: ChunkStrategy = ChunkStrategy.FUNCTION,
        file_patterns: Optional[List[str]] = None,
        use_mock_embedder: bool = False
    ):
        """
        Initialize ingestion pipeline.
        
        Args:
            db_connection_string: PostgreSQL connection string for AlloyDB
            embedder: Vertex AI embedder (creates default if None)
            chunking_strategy: Strategy for code chunking
            file_patterns: File patterns to include (e.g., ['*.py', '*.js'])
            use_mock_embedder: Use mock embedder for local testing (no GCP costs)
        """
        self.db_connection_string = db_connection_string
        self.chunking_strategy = chunking_strategy
        self.file_patterns = file_patterns or ['*.py', '*.js', '*.ts', '*.java', '*.go']
        
        # Initialize chunker
        self.chunker = CodeChunker(strategy=chunking_strategy)
        
        # Initialize embedder
        if use_mock_embedder:
            logger.info("Using MockVertexAIEmbedder (no GCP costs)")
            self.embedder = MockVertexAIEmbedder()
        else:
            self.embedder = embedder or VertexAIEmbedder()
        
        # Progress callback
        self.progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    
    def set_progress_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Set callback for progress updates.
        
        Args:
            callback: Function to call with (message, stats) on progress
        """
        self.progress_callback = callback
    
    def _report_progress(self, message: str, stats: Optional[Dict[str, Any]] = None):
        """Report progress via callback and logging."""
        logger.info(message)
        if self.progress_callback:
            self.progress_callback(message, stats or {})
    
    def _get_db_connection(self):
        """Create database connection."""
        return psycopg2.connect(self.db_connection_string)
    
    def _ensure_schema_exists(self, conn):
        """
        Ensure required database schema exists (idempotent).
        Creates tables, functions, indexes, and RLS policies if they don't exist.

        Note: If tables already exist (e.g., from docker-compose initialization
        or AlloyDB setup), this will skip creation to avoid schema conflicts.
        """
        # Check if schema already exists with correct structure
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'code_chunks'
                )
            """)
            table_exists = cur.fetchone()[0]

            if table_exists:
                # Check if it has the correct structure (project_id column)
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = 'code_chunks'
                        AND column_name = 'project_id'
                    )
                """)
                has_project_id = cur.fetchone()[0]

                if has_project_id:
                    logger.info("✓ Database schema already exists with correct structure (normalized with project_id)")
                    return
                else:
                    logger.warning("⚠️  code_chunks table exists but has old schema structure. Manual migration required.")
                    raise ValueError(
                        "Schema mismatch: code_chunks table exists but does not have project_id column. "
                        "Please apply the correct schema using deployment/gcp/local-postgres-schema.sql"
                    )

        # Schema creation SQL (only used for fresh databases)
        schema_sql = """
        -- Enable required extensions
        CREATE EXTENSION IF NOT EXISTS vector;

        -- Create user context function for RLS
        CREATE OR REPLACE FUNCTION set_user_context(user_uuid UUID) 
        RETURNS void AS $$
        BEGIN
            PERFORM set_config('app.user_id', user_uuid::text, false);
        END;
        $$ LANGUAGE plpgsql;

        -- Create code_chunks table
        CREATE TABLE IF NOT EXISTS code_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            project_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            chunk_type TEXT NOT NULL CHECK (chunk_type IN ('function', 'class', 'file', 'block')),
            chunk_content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            language TEXT,
            start_line INTEGER,
            end_line INTEGER,
            embedding vector(768),
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Create indexes (IF NOT EXISTS available in PostgreSQL 9.5+)
        CREATE INDEX IF NOT EXISTS idx_code_chunks_user_project 
            ON code_chunks(user_id, project_name);
        CREATE INDEX IF NOT EXISTS idx_code_chunks_file_path 
            ON code_chunks(user_id, file_path);
        CREATE INDEX IF NOT EXISTS idx_code_chunks_content_hash 
            ON code_chunks(content_hash);
        CREATE INDEX IF NOT EXISTS idx_code_chunks_language 
            ON code_chunks(language);

        -- Create HNSW index for vector similarity search
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'idx_code_chunks_embedding_hnsw'
                AND n.nspname = 'public'
            ) THEN
                CREATE INDEX idx_code_chunks_embedding_hnsw 
                    ON code_chunks USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
            END IF;
        END $$;

        -- Enable Row-Level Security
        ALTER TABLE code_chunks ENABLE ROW LEVEL SECURITY;

        -- RLS Policy: Users can only see their own data
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies 
                WHERE tablename = 'code_chunks' 
                AND policyname = 'user_isolation_policy'
            ) THEN
                CREATE POLICY user_isolation_policy ON code_chunks
                    FOR ALL
                    USING (user_id = current_setting('app.user_id')::UUID);
            END IF;
        END $$;

        -- Create projects table for metadata
        CREATE TABLE IF NOT EXISTS projects (
            project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            project_name TEXT NOT NULL,
            gcs_bucket TEXT,
            gcs_prefix TEXT,
            total_files INTEGER DEFAULT 0,
            total_chunks INTEGER DEFAULT 0,
            last_ingestion_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(user_id, project_name)
        );

        -- Enable RLS on projects
        ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
        
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies 
                WHERE tablename = 'projects' 
                AND policyname = 'projects_user_isolation_policy'
            ) THEN
                CREATE POLICY projects_user_isolation_policy ON projects
                    FOR ALL
                    USING (user_id = current_setting('app.user_id')::UUID);
            END IF;
        END $$;
        """
        
        try:
            with conn.cursor() as cur:
                logger.info("Ensuring database schema exists...")
                cur.execute(schema_sql)
                conn.commit()
                logger.info("✓ Database schema ready")
        except Exception as e:
            logger.error(f"Failed to ensure schema: {e}")
            raise
    
    def _set_user_context(self, conn, user_id: UUID):
        """Set user context for row-level security."""
        with conn.cursor() as cur:
            cur.execute("SELECT set_user_context(%s)", (str(user_id),))
        conn.commit()
    
    def _get_or_create_project(
        self,
        conn,
        user_id: UUID,
        project_name: str,
        gcs_bucket: str,
        gcs_prefix: str
    ) -> UUID:
        """
        Get existing project or create new one.
        
        Returns:
            Project UUID
        """
        with conn.cursor() as cur:
            # Try to get existing project
            cur.execute(
                """
                SELECT project_id FROM projects
                WHERE user_id = %s AND project_name = %s
                """,
                (str(user_id), project_name)
            )
            
            result = cur.fetchone()
            if result:
                project_id = result[0]
                logger.info(f"Using existing project: {project_id}")
                return UUID(str(project_id))
            
            # Create new project
            cur.execute(
                """
                INSERT INTO projects (user_id, project_name, gcs_bucket, gcs_prefix)
                VALUES (%s, %s, %s, %s)
                RETURNING project_id
                """,
                (str(user_id), project_name, gcs_bucket, gcs_prefix)
            )
            
            project_id = cur.fetchone()[0]
            conn.commit()
            logger.info(f"Created new project: {project_id}")
            return UUID(str(project_id))
    
    def _insert_chunks_batch(
        self,
        conn,
        project_id: UUID,
        chunks_with_embeddings: List[tuple],
        commit_hash: Optional[str] = None,
        branch_name: Optional[str] = None,
        author_name: Optional[str] = None,
        commit_timestamp: Optional[str] = None
    ) -> tuple:
        """
        Insert chunks with embeddings into database.

        Args:
            conn: Database connection
            project_id: Project UUID
            chunks_with_embeddings: List of (chunk, embedding) tuples
            commit_hash: Git commit SHA (40 chars) for provenance tracking
            branch_name: Git branch name
            author_name: Git commit author
            commit_timestamp: Git commit timestamp (ISO format)

        Returns:
            Tuple of (inserted_count, skipped_count, failed_count)
        """
        inserted = 0
        skipped = 0
        failed = 0

        with conn.cursor() as cur:
            for chunk, embedding in chunks_with_embeddings:
                try:
                    # Convert embedding to PostgreSQL array format
                    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

                    # Insert chunk (deduplication via UNIQUE constraint)
                    # Include Git provenance for delta-based synchronization
                    cur.execute(
                        """
                        INSERT INTO code_chunks (
                            project_id, file_path, chunk_type, chunk_name,
                            line_start, line_end, language, content,
                            content_hash, symbols, embedding,
                            commit_hash, branch_name, author_name, commit_timestamp
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector,
                            %s, %s, %s, %s
                        )
                        ON CONFLICT (project_id, content_hash) DO NOTHING
                        RETURNING chunk_id
                        """,
                        (
                            str(project_id),
                            chunk.file_path,
                            chunk.chunk_type,
                            chunk.chunk_name,
                            chunk.line_start,
                            chunk.line_end,
                            chunk.language,
                            chunk.content,
                            chunk.content_hash,
                            psycopg2.extras.Json(chunk.symbols),
                            embedding_str,
                            commit_hash,
                            branch_name,
                            author_name,
                            commit_timestamp
                        )
                    )

                    result = cur.fetchone()
                    if result:
                        inserted += 1
                    else:
                        skipped += 1  # Duplicate

                except Exception as e:
                    logger.error(f"Error inserting chunk {chunk.chunk_name}: {e}")
                    failed += 1
                    conn.rollback()

            conn.commit()

        return (inserted, skipped, failed)
    
    def _update_project_stats(
        self,
        conn,
        project_id: UUID,
        total_chunks: int,
        total_files: int
    ):
        """Update project statistics."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE projects
                SET
                    total_chunks = %s,
                    total_files = %s,
                    last_indexed_at = NOW()
                WHERE project_id = %s
                """,
                (total_chunks, total_files, str(project_id))
            )
        conn.commit()
    
    def ingest_directory(
        self,
        directory_path: str,
        user_id: UUID,
        project_name: str,
        gcs_bucket: str = "",
        gcs_prefix: str = "",
        commit_hash: Optional[str] = None,
        branch_name: Optional[str] = None,
        author_name: Optional[str] = None,
        commit_timestamp: Optional[str] = None
    ) -> IngestionStats:
        """
        Ingest code from a directory into AlloyDB.

        Args:
            directory_path: Path to directory containing code files
            user_id: User UUID for multi-tenancy
            project_name: Project name
            gcs_bucket: GCS bucket name (for project metadata)
            gcs_prefix: GCS prefix (for project metadata)
            commit_hash: Git commit SHA (40 chars) for provenance tracking
            branch_name: Git branch name
            author_name: Git commit author
            commit_timestamp: Git commit timestamp (ISO format)

        Returns:
            IngestionStats with results
        """
        stats = IngestionStats()
        
        try:
            # Connect to database
            self._report_progress(f"Connecting to AlloyDB...", {})
            conn = self._get_db_connection()
            
            # Ensure schema exists (idempotent - safe to run every time)
            self._ensure_schema_exists(conn)
            
            # Set user context for RLS
            self._set_user_context(conn, user_id)
            
            # Get or create project
            self._report_progress(f"Setting up project: {project_name}", {})
            project_id = self._get_or_create_project(
                conn, user_id, project_name, gcs_bucket, gcs_prefix
            )
            
            # Scan and chunk files
            self._report_progress(f"Scanning directory: {directory_path}", {})
            dir_path = Path(directory_path)
            
            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {directory_path}")
            
            all_chunks = []
            processed_files = set()
            
            # Process files by pattern
            for pattern in self.file_patterns:
                for file_path in dir_path.rglob(pattern):
                    if file_path.is_file() and str(file_path) not in processed_files:
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            relative_path = str(file_path.relative_to(dir_path))
                            
                            # Chunk file
                            chunks = self.chunker.chunk_file(
                                str(file_path),
                                content,
                                relative_path
                            )
                            
                            all_chunks.extend(chunks)
                            processed_files.add(str(file_path))
                            stats.files_processed += 1
                            stats.chunks_created += len(chunks)
                            
                            self._report_progress(
                                f"Chunked {relative_path}: {len(chunks)} chunks",
                                {"files": stats.files_processed, "chunks": stats.chunks_created}
                            )
                        
                        except Exception as e:
                            error_msg = f"Error processing {file_path}: {e}"
                            logger.error(error_msg)
                            stats.errors.append(error_msg)
            
            if not all_chunks:
                logger.warning("No chunks created from directory")
                stats.finish()
                return stats
            
            self._report_progress(
                f"Created {len(all_chunks)} chunks from {stats.files_processed} files",
                stats.to_dict()
            )
            
            # Generate embeddings
            self._report_progress(
                f"Generating embeddings for {len(all_chunks)} chunks...",
                stats.to_dict()
            )
            
            chunks_with_embeddings = self.embedder.embed_code_chunks(
                all_chunks,
                use_metadata=True,
                show_progress=True
            )
            
            stats.embeddings_generated = len(chunks_with_embeddings)
            
            self._report_progress(
                f"Generated {stats.embeddings_generated} embeddings",
                stats.to_dict()
            )
            
            # Insert chunks in batches (for better performance)
            batch_size = 50
            for i in range(0, len(chunks_with_embeddings), batch_size):
                batch = chunks_with_embeddings[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(chunks_with_embeddings) + batch_size - 1) // batch_size
                
                self._report_progress(
                    f"Storing batch {batch_num}/{total_batches} ({len(batch)} chunks)...",
                    stats.to_dict()
                )
                
                inserted, skipped, failed = self._insert_chunks_batch(
                    conn, project_id, batch,
                    commit_hash=commit_hash,
                    branch_name=branch_name,
                    author_name=author_name,
                    commit_timestamp=commit_timestamp
                )
                
                stats.chunks_inserted += inserted
                stats.chunks_skipped += skipped
                stats.chunks_failed += failed
            
            # Update project statistics
            self._update_project_stats(
                conn,
                project_id,
                stats.chunks_inserted,
                stats.files_processed
            )
            
            # Clean up
            conn.close()
            
            stats.finish()
            
            self._report_progress(
                f"✅ Ingestion complete!",
                stats.to_dict()
            )
            
            logger.info(
                f"Ingestion summary: {stats.files_processed} files, "
                f"{stats.chunks_inserted} inserted, {stats.chunks_skipped} skipped, "
                f"{stats.chunks_failed} failed, "
                f"duration: {stats.duration_seconds:.2f}s"
            )
        
        except Exception as e:
            error_msg = f"Ingestion pipeline failed: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            stats.finish()
            raise
        
        return stats
    
    def ingest_files(
        self,
        file_paths: List[str],
        user_id: UUID,
        project_name: str,
        gcs_bucket: str = "",
        gcs_prefix: str = "",
        commit_hash: Optional[str] = None,
        branch_name: Optional[str] = None,
        author_name: Optional[str] = None,
        commit_timestamp: Optional[str] = None
    ) -> IngestionStats:
        """
        Ingest specific files into AlloyDB.

        Args:
            file_paths: List of file paths to ingest
            user_id: User UUID
            project_name: Project name
            gcs_bucket: GCS bucket name
            gcs_prefix: GCS prefix
            commit_hash: Git commit SHA (40 chars) for provenance tracking
            branch_name: Git branch name
            author_name: Git commit author
            commit_timestamp: Git commit timestamp (ISO format)

        Returns:
            IngestionStats with results
        """
        stats = IngestionStats()
        
        try:
            # Connect to database
            conn = self._get_db_connection()
            
            # Ensure schema exists (idempotent - safe to run every time)
            self._ensure_schema_exists(conn)
            
            self._set_user_context(conn, user_id)
            
            # Get or create project
            project_id = self._get_or_create_project(
                conn, user_id, project_name, gcs_bucket, gcs_prefix
            )
            
            all_chunks = []
            
            # Process each file
            for file_path in file_paths:
                try:
                    path = Path(file_path)
                    if not path.exists():
                        logger.warning(f"File not found: {file_path}")
                        continue
                    
                    content = path.read_text(encoding='utf-8')
                    
                    # Chunk file
                    chunks = self.chunker.chunk_file(
                        str(path),
                        content,
                        str(path.name)
                    )
                    
                    all_chunks.extend(chunks)
                    stats.files_processed += 1
                    stats.chunks_created += len(chunks)
                
                except Exception as e:
                    error_msg = f"Error processing {file_path}: {e}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)
            
            if not all_chunks:
                logger.warning("No chunks created from files")
                stats.finish()
                return stats
            
            # Generate embeddings
            chunks_with_embeddings = self.embedder.embed_code_chunks(
                all_chunks,
                use_metadata=True,
                show_progress=True
            )
            
            stats.embeddings_generated = len(chunks_with_embeddings)
            
            # Insert chunks
            inserted, skipped, failed = self._insert_chunks_batch(
                conn, project_id, chunks_with_embeddings,
                commit_hash=commit_hash,
                branch_name=branch_name,
                author_name=author_name,
                commit_timestamp=commit_timestamp
            )
            
            stats.chunks_inserted = inserted
            stats.chunks_skipped = skipped
            stats.chunks_failed = failed
            
            # Update project statistics
            self._update_project_stats(
                conn,
                project_id,
                stats.chunks_inserted,
                stats.files_processed
            )
            
            conn.close()
            stats.finish()
        
        except Exception as e:
            error_msg = f"File ingestion failed: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            stats.finish()
            raise
        
        return stats


# Convenience functions

def ingest_directory(
    directory_path: str,
    user_id: UUID,
    project_name: str,
    db_connection_string: str,
    gcs_bucket: str = "",
    gcs_prefix: str = "",
    use_mock_embedder: bool = False,
    progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    commit_hash: Optional[str] = None,
    branch_name: Optional[str] = None,
    author_name: Optional[str] = None,
    commit_timestamp: Optional[str] = None
) -> IngestionStats:
    """
    Convenience function to ingest a directory.

    Args:
        directory_path: Path to directory
        user_id: User UUID
        project_name: Project name
        db_connection_string: AlloyDB connection string
        gcs_bucket: GCS bucket name
        gcs_prefix: GCS prefix
        use_mock_embedder: Use mock embedder for testing
        progress_callback: Optional callback for progress updates
        commit_hash: Git commit SHA (40 chars) for provenance tracking
        branch_name: Git branch name
        author_name: Git commit author
        commit_timestamp: Git commit timestamp (ISO format)

    Returns:
        IngestionStats with results
    """
    pipeline = IngestionPipeline(
        db_connection_string=db_connection_string,
        use_mock_embedder=use_mock_embedder
    )

    if progress_callback:
        pipeline.set_progress_callback(progress_callback)

    return pipeline.ingest_directory(
        directory_path,
        user_id,
        project_name,
        gcs_bucket,
        gcs_prefix,
        commit_hash=commit_hash,
        branch_name=branch_name,
        author_name=author_name,
        commit_timestamp=commit_timestamp
    )


def ingest_files(
    file_paths: List[str],
    user_id: UUID,
    project_name: str,
    db_connection_string: str,
    gcs_bucket: str = "",
    gcs_prefix: str = "",
    use_mock_embedder: bool = False,
    commit_hash: Optional[str] = None,
    branch_name: Optional[str] = None,
    author_name: Optional[str] = None,
    commit_timestamp: Optional[str] = None
) -> IngestionStats:
    """
    Convenience function to ingest specific files.

    Args:
        file_paths: List of file paths
        user_id: User UUID
        project_name: Project name
        db_connection_string: AlloyDB connection string
        gcs_bucket: GCS bucket name
        gcs_prefix: GCS prefix
        use_mock_embedder: Use mock embedder for testing
        commit_hash: Git commit SHA (40 chars) for provenance tracking
        branch_name: Git branch name
        author_name: Git commit author
        commit_timestamp: Git commit timestamp (ISO format)

    Returns:
        IngestionStats with results
    """
    pipeline = IngestionPipeline(
        db_connection_string=db_connection_string,
        use_mock_embedder=use_mock_embedder
    )

    return pipeline.ingest_files(
        file_paths,
        user_id,
        project_name,
        gcs_bucket,
        gcs_prefix,
        commit_hash=commit_hash,
        branch_name=branch_name,
        author_name=author_name,
        commit_timestamp=commit_timestamp
    )

