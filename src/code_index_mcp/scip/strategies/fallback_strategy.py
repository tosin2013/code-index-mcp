"""Simplified fallback SCIP indexing strategy - minimal file information only."""

import logging
import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ...constants import SUPPORTED_EXTENSIONS


logger = logging.getLogger(__name__)


class FallbackStrategy(SCIPIndexerStrategy):
    """Simplified SCIP-compliant fallback strategy providing only basic file information."""

    def __init__(self, priority: int = 10):
        """Initialize the fallback strategy with low priority."""
        super().__init__(priority)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """This strategy can handle supported file extensions as a last resort."""
        return extension.lower() in SUPPORTED_EXTENSIONS

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "text"  # Generic text language

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return True  # Always available as fallback

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Simple file counting - no symbol collection."""
        logger.debug(f"FallbackStrategy Phase 1: Processing {len(files)} files for basic cataloging")
        processed_count = 0

        for file_path in files:
            try:
                relative_path = os.path.relpath(file_path, project_path)
                # Just count files, no symbol extraction
                processed_count += 1
                logger.debug(f"Registered file: {relative_path}")
            except Exception as e:
                logger.warning(f"Phase 1 failed for {file_path}: {e}")
                continue

        logger.info(f"Phase 1 summary: {processed_count} files registered")

    def _generate_documents_with_references(self, files: List[str], project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> List[scip_pb2.Document]:
        """Phase 2: Generate minimal SCIP documents with basic file information."""
        documents = []
        logger.debug(f"FallbackStrategy Phase 2: Creating basic documents for {len(files)} files")
        processed_count = 0

        for file_path in files:
            try:
                document = self._create_basic_document(file_path, project_path)
                if document:
                    documents.append(document)
                    processed_count += 1

            except Exception as e:
                logger.warning(f"Phase 2 failed for {file_path}: {e}")
                continue

        logger.info(f"Phase 2 summary: {processed_count} basic documents created")
        return documents

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """Skip relationship building - return empty dict."""
        logger.debug("FallbackStrategy: Skipping relationship building (minimal mode)")
        return {}

    def _create_basic_document(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """Create a minimal SCIP document with basic file information."""
        try:
            # Check if file exists and get basic info
            if not os.path.exists(file_path):
                return None

            file_stats = os.stat(file_path)
            relative_path = os.path.relpath(file_path, project_path)

            # Create basic document
            document = scip_pb2.Document()
            document.relative_path = relative_path
            document.language = self._detect_language_from_extension(Path(file_path).suffix)

            # Add basic file symbol
            file_name = Path(file_path).stem
            symbol_id = self.symbol_manager.create_local_symbol(
                language=document.language,
                file_path=relative_path,
                symbol_path=[file_name],
                descriptor=""
            )

            # Create minimal symbol information
            symbol_info = scip_pb2.SymbolInformation()
            symbol_info.symbol = symbol_id
            symbol_info.display_name = file_name
            symbol_info.kind = scip_pb2.File
            symbol_info.documentation.append(
                f"File: {relative_path} ({document.language})"
            )

            document.symbols.append(symbol_info)

            logger.debug(f"Created basic document for: {relative_path}")
            return document

        except Exception as e:
            logger.warning(f"Failed to create basic document for {file_path}: {e}")
            return None

    def _detect_language_from_extension(self, extension: str) -> str:
        """Detect specific language from extension."""
        extension_mapping = {
            # Programming languages
            '.c': 'c',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c++': 'cpp',
            '.h': 'c', '.hpp': 'cpp', '.hh': 'cpp', '.hxx': 'cpp',
            '.js': 'javascript', '.mjs': 'javascript', '.jsx': 'javascript',
            '.ts': 'typescript', '.tsx': 'typescript',
            '.py': 'python', '.pyi': 'python', '.pyx': 'python',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.cs': 'csharp',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin', '.kts': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.lua': 'lua',
            '.perl': 'perl', '.pl': 'perl',
            '.zig': 'zig',
            '.dart': 'dart',

            # Web and markup
            '.html': 'html', '.htm': 'html',
            '.css': 'css',
            '.scss': 'scss', '.sass': 'sass',
            '.less': 'less',
            '.vue': 'vue',
            '.svelte': 'svelte',
            '.astro': 'astro',

            # Data and config
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml', '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'ini',
            '.conf': 'ini',

            # Documentation
            '.md': 'markdown', '.markdown': 'markdown',
            '.mdx': 'mdx',
            '.tex': 'latex',
            '.rst': 'rst',

            # Database and query
            '.sql': 'sql',
            '.cql': 'cql',
            '.cypher': 'cypher',
            '.sparql': 'sparql',
            '.graphql': 'graphql', '.gql': 'graphql',

            # Shell and scripts
            '.sh': 'shell', '.bash': 'bash',
            '.zsh': 'zsh', '.fish': 'fish',
            '.ps1': 'powershell',
            '.bat': 'batch', '.cmd': 'batch',

            # Template languages
            '.handlebars': 'handlebars', '.hbs': 'handlebars',
            '.ejs': 'ejs',
            '.pug': 'pug',
            '.mustache': 'mustache',

            # Other
            '.dockerfile': 'dockerfile',
            '.gitignore': 'gitignore',
            '.env': 'dotenv',
        }

        return extension_mapping.get(extension.lower(), 'text')
