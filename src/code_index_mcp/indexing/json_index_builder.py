"""
JSON Index Builder - Clean implementation using Strategy pattern.

This replaces the monolithic parser implementation with a clean,
maintainable Strategy pattern architecture.
"""

import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from .strategies import StrategyFactory
from .models import SymbolInfo, FileInfo
from ..constants import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


@dataclass
class IndexMetadata:
    """Metadata for the JSON index."""
    project_path: str
    indexed_files: int
    index_version: str
    timestamp: str
    languages: List[str]
    total_symbols: int = 0
    specialized_parsers: int = 0
    fallback_files: int = 0


class JSONIndexBuilder:
    """
    Main index builder using Strategy pattern for language parsing.

    This class orchestrates the index building process by:
    1. Discovering files in the project
    2. Using StrategyFactory to get appropriate parsers
    3. Extracting symbols and metadata
    4. Assembling the final JSON index
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.in_memory_index: Optional[Dict[str, Any]] = None
        self.strategy_factory = StrategyFactory()

        logger.info(f"Initialized JSON index builder for {project_path}")
        strategy_info = self.strategy_factory.get_strategy_info()
        logger.info(f"Available parsing strategies: {len(strategy_info)} types")

        # Log specialized vs fallback coverage
        specialized = len(self.strategy_factory.get_specialized_extensions())
        fallback = len(self.strategy_factory.get_fallback_extensions())
        logger.info(f"Specialized parsers: {specialized} extensions, Fallback coverage: {fallback} extensions")

    def build_index(self) -> Dict[str, Any]:
        """
        Build the complete index using Strategy pattern.

        Returns:
            Complete JSON index with metadata, symbols, and file information
        """
        logger.info("Building JSON index using Strategy pattern...")
        start_time = time.time()

        all_symbols = {}
        all_files = {}
        languages = set()
        specialized_count = 0
        fallback_count = 0

        # Get specialized extensions for tracking
        specialized_extensions = set(self.strategy_factory.get_specialized_extensions())

        # Traverse project files
        for file_path in self._get_supported_files():
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                ext = Path(file_path).suffix.lower()

                # Convert to relative path first
                rel_path = os.path.relpath(file_path, self.project_path).replace('\\', '/')

                # Get appropriate strategy
                strategy = self.strategy_factory.get_strategy(ext)

                # Track strategy usage
                if ext in specialized_extensions:
                    specialized_count += 1
                else:
                    fallback_count += 1

                # Parse file using strategy with relative path
                symbols, file_info = strategy.parse_file(rel_path, content)

                # Add to index
                all_symbols.update(symbols)
                all_files[rel_path] = file_info
                languages.add(file_info.language)

                logger.debug(f"Parsed {rel_path}: {len(symbols)} symbols ({file_info.language})")

            except Exception as e:
                logger.warning(f"Error processing {file_path}: {e}")

        # Build index metadata
        metadata = IndexMetadata(
            project_path=self.project_path,
            indexed_files=len(all_files),
            index_version="2.0.0-strategy",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            languages=sorted(list(languages)),
            total_symbols=len(all_symbols),
            specialized_parsers=specialized_count,
            fallback_files=fallback_count
        )

        # Assemble final index
        index = {
            "metadata": asdict(metadata),
            "symbols": {k: asdict(v) for k, v in all_symbols.items()},
            "files": {k: asdict(v) for k, v in all_files.items()}
        }

        # Cache in memory
        self.in_memory_index = index

        elapsed = time.time() - start_time
        logger.info(f"Built index with {len(all_symbols)} symbols from {len(all_files)} files in {elapsed:.2f}s")
        logger.info(f"Languages detected: {sorted(languages)}")
        logger.info(f"Strategy usage: {specialized_count} specialized, {fallback_count} fallback")

        return index

    def get_index(self) -> Optional[Dict[str, Any]]:
        """Get the current in-memory index."""
        return self.in_memory_index

    def clear_index(self):
        """Clear the in-memory index."""
        self.in_memory_index = None
        logger.debug("Cleared in-memory index")

    def _get_supported_files(self) -> List[str]:
        """
        Get all supported files in the project.

        Returns:
            List of file paths that can be parsed
        """
        supported_files = []
        supported_extensions = set(SUPPORTED_EXTENSIONS)

        try:
            for root, dirs, files in os.walk(self.project_path):
                # Skip hidden directories and common ignore patterns
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    '__pycache__', 'node_modules', '.git', '.svn', '.hg',
                    '.vscode', '.idea', 'target', 'build', 'dist'
                }]

                for file in files:
                    if file.startswith('.'):
                        continue

                    file_path = os.path.join(root, file)
                    ext = Path(file_path).suffix.lower()

                    if ext in supported_extensions:
                        supported_files.append(file_path)

        except Exception as e:
            logger.error(f"Error scanning directory {self.project_path}: {e}")

        logger.debug(f"Found {len(supported_files)} supported files")
        return supported_files

    def save_index(self, index: Dict[str, Any], index_path: str) -> bool:
        """
        Save index to disk.

        Args:
            index: Index data to save
            index_path: Path where to save the index

        Returns:
            True if successful, False otherwise
        """
        try:
            import json
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved index to {index_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save index to {index_path}: {e}")
            return False

    def load_index(self, index_path: str) -> Optional[Dict[str, Any]]:
        """
        Load index from disk.

        Args:
            index_path: Path to the index file

        Returns:
            Index data if successful, None otherwise
        """
        try:
            if not os.path.exists(index_path):
                logger.debug(f"Index file not found: {index_path}")
                return None

            import json
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)

            # Cache in memory
            self.in_memory_index = index
            logger.info(f"Loaded index from {index_path}")
            return index

        except Exception as e:
            logger.error(f"Failed to load index from {index_path}: {e}")
            return None

    def get_parsing_statistics(self) -> Dict[str, Any]:
        """
        Get detailed statistics about parsing capabilities.

        Returns:
            Dictionary with parsing statistics and strategy information
        """
        strategy_info = self.strategy_factory.get_strategy_info()

        return {
            "total_strategies": len(strategy_info),
            "specialized_languages": [lang for lang in strategy_info.keys() if not lang.startswith('fallback_')],
            "fallback_languages": [lang.replace('fallback_', '') for lang in strategy_info.keys() if lang.startswith('fallback_')],
            "total_extensions": len(self.strategy_factory.get_all_supported_extensions()),
            "specialized_extensions": len(self.strategy_factory.get_specialized_extensions()),
            "fallback_extensions": len(self.strategy_factory.get_fallback_extensions()),
            "strategy_details": strategy_info
        }

    def get_file_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Get symbols for a specific file.

        Args:
            file_path: Relative path to the file

        Returns:
            List of symbols in the file
        """
        if not self.in_memory_index:
            logger.warning("Index not loaded")
            return []

        try:
            # Normalize file path
            file_path = file_path.replace('\\', '/')
            if file_path.startswith('./'):
                file_path = file_path[2:]

            # Get file info
            file_info = self.in_memory_index["files"].get(file_path)
            if not file_info:
                logger.warning(f"File not found in index: {file_path}")
                return []

            # Work directly with global symbols for this file
            global_symbols = self.in_memory_index.get("symbols", {})
            result = []
            
            # Find all symbols for this file directly from global symbols
            for symbol_id, symbol_data in global_symbols.items():
                symbol_file = symbol_data.get("file", "").replace("\\", "/")
                
                # Check if this symbol belongs to our file
                if symbol_file == file_path:
                    symbol_type = symbol_data.get("type", "unknown")
                    symbol_name = symbol_id.split("::")[-1]  # Extract symbol name from ID
                    
                    # Create symbol info
                    symbol_info = {
                        "name": symbol_name,
                        "called_by": symbol_data.get("called_by", []),
                        "line": symbol_data.get("line"),
                        "signature": symbol_data.get("signature")
                    }
                    
                    # Categorize by type
                    if symbol_type in ["function", "method"]:
                        result.append(symbol_info)
                    elif symbol_type == "class":
                        result.append(symbol_info)

            # Sort by line number for consistent ordering
            result.sort(key=lambda x: x.get("line", 0))
            
            return result

        except Exception as e:
            logger.error(f"Error getting file symbols for {file_path}: {e}")
            return []
