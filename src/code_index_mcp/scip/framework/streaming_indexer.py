"""SCIP Streaming Indexer - Incremental and streaming index generation for large codebases."""

import logging
import json
import os
import time
from typing import Dict, List, Optional, Iterator, Callable, Any, Set
from dataclasses import dataclass, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue, Empty
import threading

from .caching_system import SCIPCacheManager, BatchProcessor
from .index_factory import SCIPIndexFactory
from ..proto import scip_pb2

logger = logging.getLogger(__name__)


@dataclass
class IndexingProgress:
    """Progress tracking for streaming indexing."""
    total_files: int
    processed_files: int
    failed_files: int
    start_time: float
    current_file: Optional[str] = None
    error_messages: List[str] = None
    
    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_files == 0:
            return 100.0
        return (self.processed_files / self.total_files) * 100.0
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed processing time."""
        return time.time() - self.start_time
    
    @property
    def estimated_remaining_time(self) -> float:
        """Estimate remaining processing time."""
        if self.processed_files == 0:
            return 0.0
        
        avg_time_per_file = self.elapsed_time / self.processed_files
        remaining_files = self.total_files - self.processed_files
        return avg_time_per_file * remaining_files


class StreamingIndexer:
    """Streaming SCIP indexer for incremental and large-scale indexing."""
    
    def __init__(self, 
                 factory: SCIPIndexFactory,
                 cache_manager: Optional[SCIPCacheManager] = None,
                 max_workers: int = 4,
                 chunk_size: int = 100):
        """Initialize streaming indexer."""
        self.factory = factory
        self.cache_manager = cache_manager or SCIPCacheManager()
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        
        # Progress tracking
        self._progress: Optional[IndexingProgress] = None
        self._progress_callbacks: List[Callable[[IndexingProgress], None]] = []
        
        # Threading
        self._stop_event = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        
        # Results queue for streaming output
        self._results_queue: Queue = Queue()
        
        logger.debug(f"Initialized streaming indexer with {max_workers} workers")
    
    def add_progress_callback(self, callback: Callable[[IndexingProgress], None]) -> None:
        """Add progress callback for monitoring."""
        self._progress_callbacks.append(callback)
    
    def index_files_streaming(self, 
                            file_paths: List[str],
                            output_callback: Optional[Callable[[scip_pb2.Document], None]] = None
                            ) -> Iterator[scip_pb2.Document]:
        """Stream index generation for files."""
        self._progress = IndexingProgress(
            total_files=len(file_paths),
            processed_files=0,
            failed_files=0,
            start_time=time.time()
        )
        
        # Start processing
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        try:
            # Submit files in chunks
            for chunk_start in range(0, len(file_paths), self.chunk_size):
                if self._stop_event.is_set():
                    break
                
                chunk_end = min(chunk_start + self.chunk_size, len(file_paths))
                chunk_files = file_paths[chunk_start:chunk_end]
                
                # Submit chunk for processing
                future = self._executor.submit(self._process_file_chunk, chunk_files)
                
                # Process results as they become available
                try:
                    chunk_results = future.result(timeout=300)  # 5 minute timeout per chunk
                    
                    for document in chunk_results:
                        if output_callback:
                            output_callback(document)
                        yield document
                        
                        # Update progress
                        self._progress.processed_files += 1
                        self._notify_progress()
                        
                except Exception as e:
                    logger.error(f"Chunk processing failed: {e}")
                    self._progress.failed_files += len(chunk_files)
                    self._progress.error_messages.append(str(e))
                    self._notify_progress()
        
        finally:
            if self._executor:
                self._executor.shutdown(wait=True)
            
            logger.info(f"Streaming indexing completed. Processed: {self._progress.processed_files}, "
                       f"Failed: {self._progress.failed_files}")
    
    def create_incremental_index(self, 
                               modified_files: List[str],
                               existing_index: Optional[scip_pb2.Index] = None
                               ) -> scip_pb2.Index:
        """Create incremental index for modified files."""
        logger.info(f"Creating incremental index for {len(modified_files)} modified files")
        
        # Start with existing index or create new one
        if existing_index:
            updated_index = scip_pb2.Index()
            updated_index.CopyFrom(existing_index)
        else:
            updated_index = scip_pb2.Index()
            updated_index.metadata.CopyFrom(self.factory.create_metadata(self.factory.project_root))
        
        # Track existing documents by path for replacement
        existing_docs_by_path = {doc.relative_path: doc for doc in updated_index.documents}
        
        # Process modified files
        new_documents = []
        for file_path in modified_files:
            try:
                # Check cache first
                cached_doc = self.cache_manager.get_document_cache(file_path)
                if cached_doc:
                    new_documents.append(cached_doc)
                    logger.debug(f"Using cached document for {file_path}")
                    continue
                
                # Read and process file
                content = self._read_file(file_path)
                if content is None:
                    logger.warning(f"Could not read file: {file_path}")
                    continue
                
                # Create new document
                document = self.factory.create_document(file_path, content)
                new_documents.append(document)
                
                # Cache the document
                self.cache_manager.cache_document(file_path, document)
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                continue
        
        # Replace or add documents in the index
        updated_documents = []
        relative_paths_processed = set()
        
        for doc in new_documents:
            updated_documents.append(doc)
            relative_paths_processed.add(doc.relative_path)
        
        # Add unchanged documents from existing index
        if existing_index:
            for doc in existing_index.documents:
                if doc.relative_path not in relative_paths_processed:
                    updated_documents.append(doc)
        
        # Update the index
        updated_index.documents[:] = updated_documents
        
        # Extract external symbols from all documents
        external_symbols = self.factory.extract_external_symbols(updated_documents)
        updated_index.external_symbols[:] = external_symbols
        
        logger.info(f"Incremental index created with {len(updated_documents)} documents")
        return updated_index
    
    def save_index_streaming(self, 
                           index: scip_pb2.Index, 
                           output_path: str,
                           compress: bool = True) -> None:
        """Save index with streaming compression for large indexes."""
        logger.info(f"Saving index to {output_path} (compress={compress})")
        
        try:
            if compress:
                # Use compression for large indexes
                import gzip
                with gzip.open(output_path, 'wb') as f:
                    f.write(index.SerializeToString())
            else:
                with open(output_path, 'wb') as f:
                    f.write(index.SerializeToString())
            
            logger.info(f"Index saved successfully to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise
    
    def load_index_streaming(self, input_path: str) -> scip_pb2.Index:
        """Load index with streaming decompression."""
        logger.info(f"Loading index from {input_path}")
        
        try:
            if input_path.endswith('.gz'):
                import gzip
                with gzip.open(input_path, 'rb') as f:
                    data = f.read()
            else:
                with open(input_path, 'rb') as f:
                    data = f.read()
            
            index = scip_pb2.Index()
            index.ParseFromString(data)
            
            logger.info(f"Index loaded successfully with {len(index.documents)} documents")
            return index
            
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            raise
    
    def watch_and_update(self, 
                        watch_directory: str,
                        output_path: str,
                        update_interval: float = 5.0) -> None:
        """Watch directory for changes and update index incrementally."""
        logger.info(f"Starting file watcher for {watch_directory}")
        
        last_update = time.time()
        known_files = set()
        last_index = None
        
        while not self._stop_event.is_set():
            try:
                # Scan for changes
                current_files = set()
                modified_files = []
                
                for ext in self.factory.get_supported_extensions():
                    pattern = f"**/*{ext}"
                    for file_path in Path(watch_directory).rglob(pattern):
                        if file_path.is_file():
                            current_files.add(str(file_path))
                            
                            # Check if file is new or modified
                            if str(file_path) not in known_files or \
                               file_path.stat().st_mtime > last_update:
                                modified_files.append(str(file_path))
                
                # Update index if there are changes
                if modified_files:
                    logger.info(f"Detected {len(modified_files)} modified files")
                    
                    # Create incremental index
                    updated_index = self.create_incremental_index(modified_files, last_index)
                    
                    # Save updated index
                    self.save_index_streaming(updated_index, output_path)
                    
                    last_index = updated_index
                    known_files = current_files
                    last_update = time.time()
                
                # Sleep before next check
                time.sleep(update_interval)
                
            except Exception as e:
                logger.error(f"Error in file watcher: {e}")
                time.sleep(update_interval)
    
    def stop(self) -> None:
        """Stop streaming indexer."""
        self._stop_event.set()
        if self._executor:
            self._executor.shutdown(wait=False)
        logger.info("Streaming indexer stopped")
    
    def get_progress(self) -> Optional[IndexingProgress]:
        """Get current indexing progress."""
        return self._progress
    
    def _process_file_chunk(self, file_paths: List[str]) -> List[scip_pb2.Document]:
        """Process a chunk of files."""
        documents = []
        
        for file_path in file_paths:
            if self._stop_event.is_set():
                break
            
            try:
                self._progress.current_file = file_path
                self._notify_progress()
                
                # Check cache first
                cached_doc = self.cache_manager.get_document_cache(file_path)
                if cached_doc:
                    documents.append(cached_doc)
                    continue
                
                # Read and process file
                content = self._read_file(file_path)
                if content is None:
                    logger.warning(f"Could not read file: {file_path}")
                    continue
                
                # Create document
                document = self.factory.create_document(file_path, content)
                documents.append(document)
                
                # Cache the document
                self.cache_manager.cache_document(file_path, document)
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                continue
        
        return documents
    
    def _notify_progress(self) -> None:
        """Notify all progress callbacks."""
        if self._progress:
            for callback in self._progress_callbacks:
                try:
                    callback(self._progress)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")
    
    def _read_file(self, file_path: str) -> Optional[str]:
        """Read file content with encoding detection."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except (OSError, PermissionError, FileNotFoundError) as e:
                logger.warning(f"Could not read {file_path}: {e}")
                return None
        
        logger.warning(f"Could not decode {file_path} with any supported encoding")
        return None


class IndexMerger:
    """Utility for merging multiple SCIP indexes."""
    
    @staticmethod
    def merge_indexes(indexes: List[scip_pb2.Index], 
                     output_metadata: Optional[scip_pb2.Metadata] = None) -> scip_pb2.Index:
        """Merge multiple SCIP indexes into one."""
        if not indexes:
            raise ValueError("No indexes provided for merging")
        
        logger.info(f"Merging {len(indexes)} indexes")
        
        merged_index = scip_pb2.Index()
        
        # Use provided metadata or first index's metadata
        if output_metadata:
            merged_index.metadata.CopyFrom(output_metadata)
        else:
            merged_index.metadata.CopyFrom(indexes[0].metadata)
        
        # Collect all documents and external symbols
        all_documents = []
        all_external_symbols = []
        seen_document_paths = set()
        seen_external_symbols = set()
        
        for index in indexes:
            # Add documents (avoid duplicates by path)
            for doc in index.documents:
                if doc.relative_path not in seen_document_paths:
                    all_documents.append(doc)
                    seen_document_paths.add(doc.relative_path)
                else:
                    logger.warning(f"Duplicate document path: {doc.relative_path}")
            
            # Add external symbols (avoid duplicates by symbol ID)
            for ext_symbol in index.external_symbols:
                if ext_symbol.symbol not in seen_external_symbols:
                    all_external_symbols.append(ext_symbol)
                    seen_external_symbols.add(ext_symbol.symbol)
        
        merged_index.documents.extend(all_documents)
        merged_index.external_symbols.extend(all_external_symbols)
        
        logger.info(f"Merged index contains {len(all_documents)} documents "
                   f"and {len(all_external_symbols)} external symbols")
        
        return merged_index