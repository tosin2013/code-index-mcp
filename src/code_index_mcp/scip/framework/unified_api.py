"""SCIP Framework Unified API - Single entry point for all SCIP framework functionality."""

import logging
import os
from typing import Dict, List, Optional, Set, Any, Callable, Iterator
from pathlib import Path
from dataclasses import dataclass

from .index_factory import SCIPIndexFactory
from .python import create_python_scip_factory, PythonSCIPIndexFactory
from .javascript import create_javascript_scip_factory, JavaScriptSCIPIndexFactory  
from .java import create_java_scip_factory, JavaSCIPIndexFactory
from .fallback import create_fallback_scip_factory, FallbackSCIPIndexFactory
from .caching_system import SCIPCacheManager, BatchProcessor
from .streaming_indexer import StreamingIndexer, IndexingProgress, IndexMerger
from .compliance_validator import SCIPComplianceValidator
from ..proto import scip_pb2

logger = logging.getLogger(__name__)


@dataclass
class SCIPConfig:
    """Configuration for SCIP framework."""
    project_root: str
    cache_enabled: bool = True
    cache_dir: Optional[str] = None
    max_workers: int = 4
    batch_size: int = 50
    streaming_chunk_size: int = 100
    validate_compliance: bool = True
    supported_languages: Optional[Set[str]] = None
    exclude_patterns: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.supported_languages is None:
            self.supported_languages = {'python', 'javascript', 'typescript', 'java', 'fallback'}
        
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                '__pycache__', '.git', 'node_modules', '.vscode', 
                '.idea', '*.pyc', '*.pyo', '*.class'
            ]


class SCIPFrameworkAPI:
    """Unified API for SCIP framework - single entry point for all functionality."""
    
    def __init__(self, config: SCIPConfig):
        """Initialize SCIP framework with configuration."""
        self.config = config
        
        # Initialize core components
        self.cache_manager = None
        if config.cache_enabled:
            self.cache_manager = SCIPCacheManager(
                cache_dir=config.cache_dir,
                max_memory_entries=1000
            )
        
        self.validator = SCIPComplianceValidator() if config.validate_compliance else None
        
        # Language-specific factories
        self._factories: Dict[str, SCIPIndexFactory] = {}
        self._init_factories()
        
        # Streaming components
        self._streaming_indexers: Dict[str, StreamingIndexer] = {}
        
        logger.info(f"Initialized SCIP Framework API for project: {config.project_root}")
        logger.info(f"Supported languages: {config.supported_languages}")
    
    def detect_project_languages(self, scan_depth: int = 3) -> Set[str]:
        """Automatically detect programming languages in the project."""
        detected_languages = set()
        project_path = Path(self.config.project_root)
        
        # Language detection by file extensions
        language_extensions = {
            'python': {'.py', '.pyw', '.pyx'},
            'javascript': {'.js', '.jsx', '.mjs', '.cjs'},
            'typescript': {'.ts', '.tsx'},
            'java': {'.java'},
            'fallback': set()  # Fallback handles everything else
        }
        
        # Scan project files
        for depth in range(scan_depth + 1):
            pattern = '*/' * depth + '*'
            
            for file_path in project_path.glob(pattern):
                if file_path.is_file():
                    file_ext = file_path.suffix.lower()
                    
                    for lang, extensions in language_extensions.items():
                        if file_ext in extensions and lang in self.config.supported_languages:
                            detected_languages.add(lang)
        
        logger.info(f"Detected languages: {detected_languages}")
        return detected_languages
    
    def create_complete_index(self, 
                            languages: Optional[Set[str]] = None,
                            progress_callback: Optional[Callable[[IndexingProgress], None]] = None
                            ) -> scip_pb2.Index:
        """Create complete SCIP index for the project."""
        if languages is None:
            languages = self.detect_project_languages()
        
        logger.info(f"Creating complete index for languages: {languages}")
        
        # Collect all files by language
        files_by_language = self._collect_files_by_language(languages)
        
        # Create index with metadata
        index = scip_pb2.Index()
        
        # Use first available factory for metadata (they should be consistent)
        first_factory = next(iter(self._factories.values()))
        index.metadata.CopyFrom(first_factory.create_metadata(self.config.project_root))
        
        # Process files by language
        all_documents = []
        all_external_symbols = []
        
        for language, file_paths in files_by_language.items():
            if language not in self._factories:
                logger.warning(f"No factory available for language: {language}")
                continue
            
            logger.info(f"Processing {len(file_paths)} {language} files")
            
            # Get streaming indexer for this language
            streaming_indexer = self._get_streaming_indexer(language)
            if progress_callback:
                streaming_indexer.add_progress_callback(progress_callback)
            
            # Process files with streaming
            language_documents = list(streaming_indexer.index_files_streaming(file_paths))
            all_documents.extend(language_documents)
            
            # Extract external symbols
            factory = self._factories[language]
            external_symbols = factory.extract_external_symbols(language_documents)
            all_external_symbols.extend(external_symbols)
        
        # Add all documents and external symbols to index
        index.documents.extend(all_documents)
        index.external_symbols.extend(all_external_symbols)
        
        # Validate if requested
        if self.validator:
            is_valid = self.validator.validate_index(index)
            if not is_valid:
                logger.warning("Generated index failed compliance validation")
                validation_summary = self.validator.get_validation_summary()
                logger.warning(f"Validation errors: {validation_summary['error_messages']}")
        
        logger.info(f"Complete index created with {len(all_documents)} documents "
                   f"and {len(all_external_symbols)} external symbols")
        
        return index
    
    def create_incremental_index(self, 
                               modified_files: List[str],
                               existing_index_path: Optional[str] = None
                               ) -> scip_pb2.Index:
        """Create incremental index for modified files."""
        logger.info(f"Creating incremental index for {len(modified_files)} files")
        
        # Load existing index if provided
        existing_index = None
        if existing_index_path and os.path.exists(existing_index_path):
            try:
                streaming_indexer = next(iter(self._streaming_indexers.values()))
                existing_index = streaming_indexer.load_index_streaming(existing_index_path)
                logger.info(f"Loaded existing index with {len(existing_index.documents)} documents")
            except Exception as e:
                logger.warning(f"Failed to load existing index: {e}")
        
        # Group files by language
        files_by_language = self._group_files_by_language(modified_files)
        
        # Create incremental updates for each language
        language_indexes = []
        for language, file_paths in files_by_language.items():
            if language not in self._factories:
                continue
            
            streaming_indexer = self._get_streaming_indexer(language)
            lang_index = streaming_indexer.create_incremental_index(file_paths, existing_index)
            language_indexes.append(lang_index)
        
        # Merge language indexes
        if len(language_indexes) == 1:
            return language_indexes[0]
        elif len(language_indexes) > 1:
            return IndexMerger.merge_indexes(language_indexes)
        else:
            # No valid files to process
            return existing_index or scip_pb2.Index()
    
    def save_index(self, 
                  index: scip_pb2.Index, 
                  output_path: str,
                  compress: bool = True) -> None:
        """Save SCIP index to file."""
        streaming_indexer = self._get_any_streaming_indexer()
        streaming_indexer.save_index_streaming(index, output_path, compress)
    
    def load_index(self, input_path: str) -> scip_pb2.Index:
        """Load SCIP index from file."""
        streaming_indexer = self._get_any_streaming_indexer()
        return streaming_indexer.load_index_streaming(input_path)
    
    def validate_index(self, index: scip_pb2.Index) -> Dict[str, Any]:
        """Validate SCIP index compliance."""
        if not self.validator:
            return {"validation_enabled": False}
        
        is_valid = self.validator.validate_index(index)
        return {
            "is_valid": is_valid,
            "validation_enabled": True,
            **self.validator.get_validation_summary()
        }
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        if not self.cache_manager:
            return {"cache_enabled": False}
        
        return {
            "cache_enabled": True,
            **self.cache_manager.get_cache_statistics()
        }
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        if self.cache_manager:
            self.cache_manager.invalidate_all_cache()
            logger.info("Cache cleared")
    
    def start_file_watcher(self, 
                          output_path: str,
                          update_interval: float = 5.0) -> None:
        """Start file watcher for automatic index updates."""
        # Use Python factory's streaming indexer for watching
        # (could be enhanced to support multiple languages)
        streaming_indexer = self._get_streaming_indexer('python')
        streaming_indexer.watch_and_update(
            self.config.project_root,
            output_path,
            update_interval
        )
    
    def stop_all_watchers(self) -> None:
        """Stop all file watchers and streaming indexers."""
        for indexer in self._streaming_indexers.values():
            indexer.stop()
        logger.info("All watchers stopped")
    
    def analyze_symbol_relationships(self, index: scip_pb2.Index) -> Dict[str, Any]:
        """Analyze symbol relationships in the index."""
        relationship_stats = {
            "total_symbols": len(index.external_symbols),
            "documents_with_symbols": 0,
            "symbols_per_document": {},
            "symbol_types": {},
            "relationship_patterns": []
        }
        
        # Analyze documents
        for doc in index.documents:
            symbol_count = len(doc.symbols)
            occurrence_count = len(doc.occurrences)
            
            if symbol_count > 0:
                relationship_stats["documents_with_symbols"] += 1
            
            relationship_stats["symbols_per_document"][doc.relative_path] = {
                "symbols": symbol_count,
                "occurrences": occurrence_count
            }
            
            # Analyze symbol types in document
            for symbol in doc.symbols:
                symbol_kind_name = self._get_symbol_kind_name(symbol.kind)
                if symbol_kind_name not in relationship_stats["symbol_types"]:
                    relationship_stats["symbol_types"][symbol_kind_name] = 0
                relationship_stats["symbol_types"][symbol_kind_name] += 1
        
        return relationship_stats
    
    def export_index_json(self, index: scip_pb2.Index, output_path: str) -> None:
        """Export index to JSON format for analysis."""
        from google.protobuf.json_format import MessageToDict
        
        try:
            index_dict = MessageToDict(index)
            
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(index_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Index exported to JSON: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to export index to JSON: {e}")
            raise
    
    def get_framework_info(self) -> Dict[str, Any]:
        """Get comprehensive framework information."""
        return {
            "config": {
                "project_root": self.config.project_root,
                "cache_enabled": self.config.cache_enabled,
                "max_workers": self.config.max_workers,
                "batch_size": self.config.batch_size,
                "supported_languages": list(self.config.supported_languages),
                "validate_compliance": self.config.validate_compliance
            },
            "factories": list(self._factories.keys()),
            "streaming_indexers": list(self._streaming_indexers.keys()),
            "cache_statistics": self.get_cache_statistics(),
            "detected_languages": list(self.detect_project_languages())
        }
    
    def _init_factories(self) -> None:
        """Initialize language-specific factories."""
        if 'python' in self.config.supported_languages:
            self._factories['python'] = create_python_scip_factory(self.config.project_root)
        
        if 'javascript' in self.config.supported_languages or 'typescript' in self.config.supported_languages:
            self._factories['javascript'] = create_javascript_scip_factory(self.config.project_root)
            self._factories['typescript'] = self._factories['javascript']  # Same factory
        
        if 'java' in self.config.supported_languages:
            self._factories['java'] = create_java_scip_factory(self.config.project_root)
        
        if 'fallback' in self.config.supported_languages:
            self._factories['fallback'] = create_fallback_scip_factory(self.config.project_root)
    
    def _get_streaming_indexer(self, language: str) -> StreamingIndexer:
        """Get or create streaming indexer for language."""
        if language not in self._streaming_indexers:
            if language not in self._factories:
                raise ValueError(f"No factory available for language: {language}")
            
            factory = self._factories[language]
            self._streaming_indexers[language] = StreamingIndexer(
                factory=factory,
                cache_manager=self.cache_manager,
                max_workers=self.config.max_workers,
                chunk_size=self.config.streaming_chunk_size
            )
        
        return self._streaming_indexers[language]
    
    def _get_any_streaming_indexer(self) -> StreamingIndexer:
        """Get any available streaming indexer."""
        if not self._streaming_indexers:
            # Create one for the first available language
            first_language = next(iter(self._factories.keys()))
            return self._get_streaming_indexer(first_language)
        
        return next(iter(self._streaming_indexers.values()))
    
    def _collect_files_by_language(self, languages: Set[str]) -> Dict[str, List[str]]:
        """Collect all project files grouped by language."""
        files_by_language = {lang: [] for lang in languages}
        
        project_path = Path(self.config.project_root)
        
        # Language to extensions mapping
        language_extensions = {
            'python': {'.py', '.pyw', '.pyx'},
            'javascript': {'.js', '.jsx', '.mjs', '.cjs'},
            'typescript': {'.ts', '.tsx'},
            'java': {'.java'}
        }
        
        # Scan all files
        for file_path in project_path.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Skip excluded patterns
            if self._should_exclude_file(str(file_path)):
                continue
            
            file_ext = file_path.suffix.lower()
            
            # Categorize by language
            for lang in languages:
                if lang in language_extensions:
                    if file_ext in language_extensions[lang]:
                        files_by_language[lang].append(str(file_path))
                        break
        
        # Log file counts
        for lang, files in files_by_language.items():
            if files:
                logger.info(f"Found {len(files)} {lang} files")
        
        return files_by_language
    
    def _group_files_by_language(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """Group given files by language."""
        files_by_language = {}
        
        language_extensions = {
            'python': {'.py', '.pyw', '.pyx'},
            'javascript': {'.js', '.jsx', '.mjs', '.cjs'},
            'typescript': {'.ts', '.tsx'},
            'java': {'.java'}
        }
        
        for file_path in file_paths:
            file_ext = Path(file_path).suffix.lower()
            
            for lang, extensions in language_extensions.items():
                if file_ext in extensions and lang in self.config.supported_languages:
                    if lang not in files_by_language:
                        files_by_language[lang] = []
                    files_by_language[lang].append(file_path)
                    break
        
        return files_by_language
    
    def _should_exclude_file(self, file_path: str) -> bool:
        """Check if file should be excluded based on patterns."""
        path_str = str(file_path)
        
        for pattern in self.config.exclude_patterns:
            if pattern in path_str:
                return True
        
        return False
    
    def _get_symbol_kind_name(self, symbol_kind: int) -> str:
        """Get human-readable symbol kind name."""
        # Use enum mapper from any factory
        if self._factories:
            factory = next(iter(self._factories.values()))
            if hasattr(factory, '_enum_mapper'):
                return factory._enum_mapper.get_symbol_kind_name(symbol_kind) or f"Unknown({symbol_kind})"
        
        return f"SymbolKind({symbol_kind})"


# Convenience function for quick setup
def create_scip_framework(project_root: str, **kwargs) -> SCIPFrameworkAPI:
    """Create SCIP framework with default configuration."""
    config = SCIPConfig(project_root=project_root, **kwargs)
    return SCIPFrameworkAPI(config)