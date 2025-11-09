"""
Semantic search service for code chunks.

This module provides semantic code search functionality using vector similarity
with AlloyDB pgvector extension. Supports both real database and mock mode for testing.
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
import psycopg2
from psycopg2.extras import RealDictCursor

from ..embeddings.vertex_ai import VertexAIEmbedder, MockVertexAIEmbedder, EmbeddingConfig

logger = logging.getLogger(__name__)


class SemanticSearchResult:
    """
    Represents a semantic search result.
    
    Attributes:
        chunk_id: UUID of the code chunk
        file_path: Relative path to source file
        chunk_name: Name of function/class/module
        chunk_type: Type of chunk (function, class, file, block)
        line_start: Starting line number
        line_end: Ending line number
        language: Programming language
        content: Code content
        symbols: Extracted metadata (imports, calls, etc.)
        similarity_score: Cosine similarity score (0-1)
        project_name: Project name
    """
    
    def __init__(
        self,
        chunk_id: str,
        file_path: str,
        chunk_name: Optional[str],
        chunk_type: str,
        line_start: int,
        line_end: int,
        language: str,
        content: str,
        symbols: Dict[str, Any],
        similarity_score: float,
        project_name: str
    ):
        self.chunk_id = chunk_id
        self.file_path = file_path
        self.chunk_name = chunk_name
        self.chunk_type = chunk_type
        self.line_start = line_start
        self.line_end = line_end
        self.language = language
        self.content = content
        self.symbols = symbols
        self.similarity_score = similarity_score
        self.project_name = project_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "file_path": self.file_path,
            "chunk_name": self.chunk_name,
            "chunk_type": self.chunk_type,
            "line_range": f"{self.line_start}-{self.line_end}",
            "language": self.language,
            "content": self.content,
            "symbols": self.symbols,
            "similarity_score": round(self.similarity_score, 4),
            "project_name": self.project_name,
        }
    
    def __repr__(self) -> str:
        return (
            f"SemanticSearchResult(file={self.file_path}, "
            f"chunk={self.chunk_name}, score={self.similarity_score:.4f})"
        )


class SemanticSearchService:
    """
    Service for semantic code search using vector similarity.
    
    Supports both real AlloyDB connections and mock mode for testing.
    """
    
    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        embedder: Optional[VertexAIEmbedder] = None,
        use_mock: bool = False
    ):
        """
        Initialize semantic search service.
        
        Args:
            db_connection_string: PostgreSQL connection string for AlloyDB
            embedder: Vertex AI embedder (creates default if None)
            use_mock: Use mock embedder and skip real DB operations
        """
        self.db_connection_string = db_connection_string
        self.use_mock = use_mock
        
        # Initialize embedder
        if use_mock:
            self.embedder = MockVertexAIEmbedder()
        else:
            self.embedder = embedder or VertexAIEmbedder()
    
    def _get_db_connection(self):
        """Get database connection."""
        if not self.db_connection_string:
            raise ValueError("Database connection string required")
        return psycopg2.connect(self.db_connection_string, cursor_factory=RealDictCursor)
    
    def _set_user_context(self, conn, user_id: UUID):
        """Set user context for row-level security."""
        with conn.cursor() as cur:
            cur.execute("SELECT set_user_context(%s)", (str(user_id),))
        conn.commit()
    
    def semantic_search(
        self,
        query: str,
        user_id: UUID,
        project_name: Optional[str] = None,
        language: Optional[str] = None,
        top_k: int = 10,
        min_similarity: float = 0.0
    ) -> List[SemanticSearchResult]:
        """
        Search code by semantic meaning using vector similarity.
        
        Args:
            query: Natural language query (e.g., "authentication logic")
            user_id: User UUID for multi-tenancy
            project_name: Filter to specific project (optional)
            language: Filter by programming language (optional)
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (0-1)
        
        Returns:
            List of search results sorted by similarity
        """
        if self.use_mock:
            logger.warning("Mock mode: returning empty results")
            return []
        
        # Generate query embedding
        query_embedding = self.embedder.generate_embedding(
            query,
            task_type="RETRIEVAL_QUERY"
        )
        
        # Connect to database
        conn = self._get_db_connection()
        
        try:
            # Set user context for RLS
            self._set_user_context(conn, user_id)
            
            # Build WHERE clause
            where_clauses = ["p.user_id = %(user_id)s", "c.embedding IS NOT NULL"]
            params = {
                "user_id": str(user_id),
                "top_k": top_k
            }
            
            if project_name:
                where_clauses.append("p.project_name = %(project_name)s")
                params["project_name"] = project_name
            
            if language:
                where_clauses.append("c.language = %(language)s")
                params["language"] = language
            
            where_sql = " AND ".join(where_clauses)
            
            # Convert embedding to PostgreSQL array format
            embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
            
            # Execute similarity search
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT
                        c.chunk_id::text,
                        c.file_path,
                        c.chunk_name,
                        c.chunk_type,
                        c.line_start,
                        c.line_end,
                        c.language,
                        c.content,
                        c.symbols,
                        1 - (c.embedding <=> %(embedding)s::vector) AS similarity_score,
                        p.project_name
                    FROM code_chunks c
                    JOIN projects p ON c.project_id = p.project_id
                    WHERE {where_sql}
                    ORDER BY c.embedding <=> %(embedding)s::vector
                    LIMIT %(top_k)s
                """, {**params, "embedding": embedding_str})
                
                rows = cur.fetchall()
            
            # Convert to result objects
            results = []
            for row in rows:
                similarity_score = float(row['similarity_score'])
                
                # Apply minimum similarity filter
                if similarity_score < min_similarity:
                    continue
                
                result = SemanticSearchResult(
                    chunk_id=row['chunk_id'],
                    file_path=row['file_path'],
                    chunk_name=row['chunk_name'],
                    chunk_type=row['chunk_type'],
                    line_start=row['line_start'],
                    line_end=row['line_end'],
                    language=row['language'],
                    content=row['content'],
                    symbols=row['symbols'] or {},
                    similarity_score=similarity_score,
                    project_name=row['project_name']
                )
                results.append(result)
            
            return results
        
        finally:
            conn.close()
    
    def find_similar_code(
        self,
        code_snippet: str,
        user_id: UUID,
        project_name: Optional[str] = None,
        language: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.5
    ) -> List[SemanticSearchResult]:
        """
        Find code chunks similar to the provided code snippet.
        
        Args:
            code_snippet: Code to find similar implementations of
            user_id: User UUID
            project_name: Filter to specific project (optional)
            language: Filter by language (optional)
            top_k: Number of results
            min_similarity: Minimum similarity threshold
        
        Returns:
            Similar code chunks with similarity scores
        """
        # Use semantic search with code as query
        return self.semantic_search(
            query=code_snippet,
            user_id=user_id,
            project_name=project_name,
            language=language,
            top_k=top_k,
            min_similarity=min_similarity
        )
    
    def hybrid_search(
        self,
        query: str,
        user_id: UUID,
        project_name: Optional[str] = None,
        language: Optional[str] = None,
        keyword_filter: Optional[str] = None,
        top_k: int = 10,
        min_similarity: float = 0.0
    ) -> List[SemanticSearchResult]:
        """
        Hybrid search combining semantic similarity with keyword filtering.
        
        Args:
            query: Natural language query
            user_id: User UUID
            project_name: Filter to specific project
            language: Filter by language
            keyword_filter: Additional keyword to filter results
            top_k: Number of results
            min_similarity: Minimum similarity threshold
        
        Returns:
            Search results filtered and ranked by both semantic and keyword relevance
        """
        # Get semantic search results
        results = self.semantic_search(
            query=query,
            user_id=user_id,
            project_name=project_name,
            language=language,
            top_k=top_k * 2,  # Get more for filtering
            min_similarity=min_similarity
        )
        
        # Apply keyword filtering if specified
        if keyword_filter:
            keyword_lower = keyword_filter.lower()
            filtered_results = []
            
            for result in results:
                # Check if keyword appears in content, name, or file path
                if (keyword_lower in result.content.lower() or
                    (result.chunk_name and keyword_lower in result.chunk_name.lower()) or
                    keyword_lower in result.file_path.lower()):
                    
                    # Boost similarity score slightly for keyword match
                    result.similarity_score = min(1.0, result.similarity_score * 1.1)
                    filtered_results.append(result)
            
            results = filtered_results
        
        # Re-sort by adjusted similarity scores and limit
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        return results[:top_k]
    
    def search_by_function_name(
        self,
        function_name: str,
        user_id: UUID,
        project_name: Optional[str] = None,
        fuzzy: bool = True
    ) -> List[SemanticSearchResult]:
        """
        Search for functions by name (exact or fuzzy).
        
        Args:
            function_name: Function name to search for
            user_id: User UUID
            project_name: Filter to specific project
            fuzzy: Use fuzzy matching (contains) vs exact match
        
        Returns:
            Matching functions sorted by similarity
        """
        # Use semantic search with function name as query
        query = f"function named {function_name}" if fuzzy else function_name
        
        results = self.semantic_search(
            query=query,
            user_id=user_id,
            project_name=project_name,
            top_k=20
        )
        
        # Filter for functions only
        function_results = [
            r for r in results
            if r.chunk_type == 'function'
        ]
        
        # Apply name matching
        if fuzzy:
            # Filter for name contains
            function_results = [
                r for r in function_results
                if r.chunk_name and function_name.lower() in r.chunk_name.lower()
            ]
        else:
            # Exact match
            function_results = [
                r for r in function_results
                if r.chunk_name and r.chunk_name == function_name
            ]
        
        return function_results


# Convenience functions

def semantic_search(
    query: str,
    user_id: UUID,
    db_connection_string: str,
    project_name: Optional[str] = None,
    language: Optional[str] = None,
    top_k: int = 10,
    use_mock: bool = False
) -> List[Dict[str, Any]]:
    """
    Convenience function for semantic code search.
    
    Args:
        query: Natural language query
        user_id: User UUID
        db_connection_string: AlloyDB connection string
        project_name: Filter to specific project
        language: Filter by language
        top_k: Number of results
        use_mock: Use mock mode for testing
    
    Returns:
        List of search result dictionaries
    """
    service = SemanticSearchService(
        db_connection_string=db_connection_string,
        use_mock=use_mock
    )
    
    results = service.semantic_search(
        query=query,
        user_id=user_id,
        project_name=project_name,
        language=language,
        top_k=top_k
    )
    
    return [r.to_dict() for r in results]


def find_similar_code(
    code_snippet: str,
    user_id: UUID,
    db_connection_string: str,
    project_name: Optional[str] = None,
    top_k: int = 5,
    use_mock: bool = False
) -> List[Dict[str, Any]]:
    """
    Convenience function to find similar code.
    
    Args:
        code_snippet: Code to find similar implementations of
        user_id: User UUID
        db_connection_string: AlloyDB connection string
        project_name: Filter to specific project
        top_k: Number of results
        use_mock: Use mock mode for testing
    
    Returns:
        List of similar code result dictionaries
    """
    service = SemanticSearchService(
        db_connection_string=db_connection_string,
        use_mock=use_mock
    )
    
    results = service.find_similar_code(
        code_snippet=code_snippet,
        user_id=user_id,
        project_name=project_name,
        top_k=top_k
    )
    
    return [r.to_dict() for r in results]

