"""
Code chunking module for semantic search.

This module splits code into searchable chunks using tree-sitter and AST parsing,
extracting functions, classes, and other code structures along with their metadata.
"""

import ast
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ChunkStrategy(Enum):
    """Chunking strategy for code files."""

    FUNCTION = "function"  # Split by functions/methods
    CLASS = "class"  # Split by classes
    FILE = "file"  # Whole file as one chunk
    SEMANTIC = "semantic"  # Smart chunking with overlap


@dataclass
class CodeChunk:
    """
    Represents a chunk of code for embedding and semantic search.

    Attributes:
        file_path: Relative path to the source file
        chunk_type: Type of chunk ('function', 'class', 'file', 'block')
        chunk_name: Name of the function/class/module
        line_start: Starting line number
        line_end: Ending line number
        language: Programming language
        content: The actual code content
        content_hash: SHA256 hash for deduplication
        symbols: Extracted metadata (imports, calls, variables, etc.)
        context_before: Optional context from before the chunk
        context_after: Optional context from after the chunk
    """

    file_path: str
    chunk_type: str
    chunk_name: Optional[str]
    line_start: int
    line_end: int
    language: str
    content: str
    content_hash: str
    symbols: Dict[str, Any] = field(default_factory=dict)
    context_before: Optional[str] = None
    context_after: Optional[str] = None

    def __post_init__(self):
        """Calculate content hash if not provided."""
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary for storage."""
        return {
            "file_path": self.file_path,
            "chunk_type": self.chunk_type,
            "chunk_name": self.chunk_name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "language": self.language,
            "content": self.content,
            "content_hash": self.content_hash,
            "symbols": self.symbols,
        }


class CodeChunker:
    """
    Chunker for splitting code files into searchable units.

    Supports multiple chunking strategies and extracts metadata for
    semantic search and embedding generation.
    """

    # Maximum chunk size in characters (for fallback)
    MAX_CHUNK_SIZE = 8000

    # Overlap size for semantic chunking (in lines)
    OVERLAP_LINES = 3

    def __init__(self, strategy: ChunkStrategy = ChunkStrategy.FUNCTION):
        """
        Initialize code chunker.

        Args:
            strategy: Chunking strategy to use
        """
        self.strategy = strategy
        self.language_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".m": "objective-c",
            ".zig": "zig",
            # Documentation and config files
            ".md": "markdown",
            ".txt": "text",
            ".rst": "restructuredtext",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".toml": "toml",
        }

    def chunk_file(
        self, file_path: str, content: str, relative_path: Optional[str] = None
    ) -> List[CodeChunk]:
        """
        Chunk a single file into searchable units.

        Args:
            file_path: Path to the file
            content: File content
            relative_path: Relative path for storage (defaults to file_path)

        Returns:
            List of code chunks
        """
        if relative_path is None:
            relative_path = file_path

        # Detect language
        language = self._detect_language(file_path)

        # Choose chunking method based on language and strategy
        if language == "python":
            chunks = self._chunk_python(relative_path, content, language)
        elif language in ("javascript", "typescript"):
            chunks = self._chunk_js_ts(relative_path, content, language)
        elif language == "markdown":
            chunks = self._chunk_markdown(relative_path, content, language)
        else:
            # Fallback to simple chunking
            chunks = self._chunk_simple(relative_path, content, language)

        # Apply semantic strategy if requested
        if self.strategy == ChunkStrategy.SEMANTIC:
            chunks = self._add_overlap_context(chunks, content)

        return chunks

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.language_extensions.get(ext, "unknown")

    def _chunk_python(self, file_path: str, content: str, language: str) -> List[CodeChunk]:
        """
        Chunk Python file using AST parsing.

        Extracts functions, classes, and methods as separate chunks.
        """
        chunks = []

        try:
            tree = ast.parse(content)
            lines = content.splitlines()

            # Extract module-level imports
            module_imports = self._extract_imports(tree)

            # Process each top-level node
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    chunk = self._extract_function_chunk(
                        node, file_path, lines, language, module_imports
                    )
                    if chunk:
                        chunks.append(chunk)

                elif isinstance(node, ast.ClassDef):
                    chunk = self._extract_class_chunk(
                        node, file_path, lines, language, module_imports
                    )
                    if chunk:
                        chunks.append(chunk)

            # If no chunks extracted, fall back to file-level chunk
            if not chunks:
                chunks = [self._create_file_chunk(file_path, content, language)]

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            chunks = [self._create_file_chunk(file_path, content, language)]
        except Exception as e:
            logger.error(f"Error chunking {file_path}: {e}")
            chunks = [self._create_file_chunk(file_path, content, language)]

        return chunks

    def _extract_function_chunk(
        self,
        node: ast.FunctionDef,
        file_path: str,
        lines: List[str],
        language: str,
        module_imports: List[str],
    ) -> Optional[CodeChunk]:
        """Extract a function as a code chunk."""
        try:
            # Get function bounds
            line_start = node.lineno
            line_end = node.end_lineno if hasattr(node, "end_lineno") else line_start

            # Extract function content
            content = "\n".join(lines[line_start - 1 : line_end])

            # Extract metadata
            symbols = {
                "function_name": node.name,
                "parameters": [arg.arg for arg in node.args.args],
                "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list],
                "imports": module_imports,
                "docstring": ast.get_docstring(node),
                "calls": self._extract_function_calls(node),
            }

            # Add return type if available
            if node.returns:
                symbols["return_type"] = ast.unparse(node.returns)

            return CodeChunk(
                file_path=file_path,
                chunk_type="function",
                chunk_name=node.name,
                line_start=line_start,
                line_end=line_end,
                language=language,
                content=content,
                content_hash="",  # Will be computed in __post_init__
                symbols=symbols,
            )

        except Exception as e:
            logger.warning(f"Error extracting function {node.name}: {e}")
            return None

    def _extract_class_chunk(
        self,
        node: ast.ClassDef,
        file_path: str,
        lines: List[str],
        language: str,
        module_imports: List[str],
    ) -> Optional[CodeChunk]:
        """Extract a class as a code chunk."""
        try:
            # Get class bounds
            line_start = node.lineno
            line_end = node.end_lineno if hasattr(node, "end_lineno") else line_start

            # Extract class content
            content = "\n".join(lines[line_start - 1 : line_end])

            # Extract methods
            methods = [
                m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]

            # Extract metadata
            symbols = {
                "class_name": node.name,
                "base_classes": [ast.unparse(base) for base in node.bases],
                "methods": methods,
                "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list],
                "imports": module_imports,
                "docstring": ast.get_docstring(node),
            }

            return CodeChunk(
                file_path=file_path,
                chunk_type="class",
                chunk_name=node.name,
                line_start=line_start,
                line_end=line_end,
                language=language,
                content=content,
                content_hash="",
                symbols=symbols,
            )

        except Exception as e:
            logger.warning(f"Error extracting class {node.name}: {e}")
            return None

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract all imports from the module."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)

        return imports

    def _extract_function_calls(self, node: ast.AST) -> List[str]:
        """Extract function calls within a node."""
        calls = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)

        return list(set(calls))  # Deduplicate

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Get the name of a decorator."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
        return ast.unparse(decorator)

    def _chunk_js_ts(self, file_path: str, content: str, language: str) -> List[CodeChunk]:
        """
        Chunk JavaScript/TypeScript file.

        For now, uses simple pattern matching. Can be enhanced with tree-sitter later.
        """
        # Simplified implementation - can be enhanced with tree-sitter
        return [self._create_file_chunk(file_path, content, language)]

    def _chunk_markdown(self, file_path: str, content: str, language: str) -> List[CodeChunk]:
        """
        Chunk markdown files by headers for semantic search.

        Splits content by markdown headers (# ## ### etc.), keeping
        related content together. Extracts header hierarchy for metadata.

        Args:
            file_path: Path to the markdown file
            content: File content
            language: 'markdown'

        Returns:
            List of code chunks split by headers
        """
        import re

        chunks = []
        lines = content.splitlines()

        # Pattern to match markdown headers (# Header, ## Header, etc.)
        header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        current_section = []
        current_header = None
        current_level = 0
        section_start_line = 1

        for i, line in enumerate(lines, 1):
            match = header_pattern.match(line)

            if match:
                # Found a new header - save previous section if exists
                if current_section:
                    section_content = "\n".join(current_section)
                    chunks.append(
                        CodeChunk(
                            file_path=file_path,
                            chunk_type="section",
                            chunk_name=current_header or "Introduction",
                            line_start=section_start_line,
                            line_end=i - 1,
                            language=language,
                            content=section_content,
                            content_hash="",
                            symbols={
                                "header": current_header,
                                "level": current_level,
                                "type": "markdown_section",
                            },
                        )
                    )

                # Start new section
                header_level = len(match.group(1))
                header_text = match.group(2).strip()
                current_section = [line]
                current_header = header_text
                current_level = header_level
                section_start_line = i
            else:
                # Add line to current section
                current_section.append(line)

        # Add final section
        if current_section:
            section_content = "\n".join(current_section)
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    chunk_type="section",
                    chunk_name=current_header or "Content",
                    line_start=section_start_line,
                    line_end=len(lines),
                    language=language,
                    content=section_content,
                    content_hash="",
                    symbols={
                        "header": current_header,
                        "level": current_level,
                        "type": "markdown_section",
                    },
                )
            )

        # If no headers found, treat as single chunk
        if not chunks:
            chunks = [self._create_file_chunk(file_path, content, language)]

        return chunks

    def _chunk_simple(self, file_path: str, content: str, language: str) -> List[CodeChunk]:
        """
        Simple chunking strategy for unsupported languages.

        Splits file into chunks of MAX_CHUNK_SIZE characters.
        """
        chunks = []
        lines = content.splitlines()

        if len(content) <= self.MAX_CHUNK_SIZE:
            # File is small enough, use as single chunk
            return [self._create_file_chunk(file_path, content, language)]

        # Split into chunks
        current_chunk_lines = []
        current_size = 0
        chunk_start_line = 1

        for i, line in enumerate(lines, 1):
            line_size = len(line) + 1  # +1 for newline

            if current_size + line_size > self.MAX_CHUNK_SIZE and current_chunk_lines:
                # Create chunk
                chunk_content = "\n".join(current_chunk_lines)
                chunks.append(
                    CodeChunk(
                        file_path=file_path,
                        chunk_type="block",
                        chunk_name=f"block_{chunk_start_line}_{i-1}",
                        line_start=chunk_start_line,
                        line_end=i - 1,
                        language=language,
                        content=chunk_content,
                        content_hash="",
                        symbols={},
                    )
                )

                # Start new chunk
                current_chunk_lines = [line]
                current_size = line_size
                chunk_start_line = i
            else:
                current_chunk_lines.append(line)
                current_size += line_size

        # Add final chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    chunk_type="block",
                    chunk_name=f"block_{chunk_start_line}_{len(lines)}",
                    line_start=chunk_start_line,
                    line_end=len(lines),
                    language=language,
                    content=chunk_content,
                    content_hash="",
                    symbols={},
                )
            )

        return chunks

    def _create_file_chunk(self, file_path: str, content: str, language: str) -> CodeChunk:
        """Create a single chunk for the entire file."""
        lines = content.splitlines()

        return CodeChunk(
            file_path=file_path,
            chunk_type="file",
            chunk_name=Path(file_path).stem,
            line_start=1,
            line_end=len(lines),
            language=language,
            content=content,
            content_hash="",
            symbols={
                "file_name": Path(file_path).name,
                "line_count": len(lines),
            },
        )

    def _add_overlap_context(self, chunks: List[CodeChunk], full_content: str) -> List[CodeChunk]:
        """
        Add overlapping context to chunks for better semantic search.

        Adds OVERLAP_LINES before and after each chunk.
        """
        lines = full_content.splitlines()

        for chunk in chunks:
            # Add context before
            context_start = max(1, chunk.line_start - self.OVERLAP_LINES)
            if context_start < chunk.line_start:
                chunk.context_before = "\n".join(lines[context_start - 1 : chunk.line_start - 1])

            # Add context after
            context_end = min(len(lines), chunk.line_end + self.OVERLAP_LINES)
            if context_end > chunk.line_end:
                chunk.context_after = "\n".join(lines[chunk.line_end : context_end])

        return chunks


def chunk_file(
    file_path: str,
    content: str,
    strategy: ChunkStrategy = ChunkStrategy.FUNCTION,
    relative_path: Optional[str] = None,
) -> List[CodeChunk]:
    """
    Convenience function to chunk a single file.

    Args:
        file_path: Path to the file
        content: File content
        strategy: Chunking strategy to use
        relative_path: Relative path for storage

    Returns:
        List of code chunks
    """
    chunker = CodeChunker(strategy=strategy)
    return chunker.chunk_file(file_path, content, relative_path)


def chunk_directory(
    directory: str,
    strategy: ChunkStrategy = ChunkStrategy.FUNCTION,
    file_patterns: Optional[List[str]] = None,
) -> Dict[str, List[CodeChunk]]:
    """
    Chunk all files in a directory.

    Args:
        directory: Directory path
        strategy: Chunking strategy to use
        file_patterns: File patterns to include (e.g., ['*.py', '*.js'])

    Returns:
        Dictionary mapping file paths to their chunks
    """
    chunker = CodeChunker(strategy=strategy)
    results = {}

    dir_path = Path(directory)
    if not dir_path.exists():
        logger.error(f"Directory not found: {directory}")
        return results

    # Default patterns
    if file_patterns is None:
        file_patterns = ["*.py", "*.js", "*.ts", "*.java", "*.go"]

    # Process files
    for pattern in file_patterns:
        for file_path in dir_path.rglob(pattern):
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    relative_path = str(file_path.relative_to(dir_path))
                    chunks = chunker.chunk_file(str(file_path), content, relative_path)
                    results[relative_path] = chunks
                    logger.info(f"Chunked {relative_path}: {len(chunks)} chunks")

                except Exception as e:
                    logger.error(f"Error chunking {file_path}: {e}")

    return results
