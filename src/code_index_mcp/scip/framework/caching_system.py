"""SCIP Framework Caching System - Performance optimization with intelligent caching."""

import logging
import hashlib
import pickle
import os
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

from ..proto import scip_pb2

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    data: Any
    created_at: datetime
    file_hash: str
    access_count: int = 0
    last_accessed: Optional[datetime] = None


class SCIPCacheManager:
    """Advanced caching system for SCIP framework with intelligent invalidation."""
    
    def __init__(self, cache_dir: Optional[str] = None, max_memory_entries: int = 1000):
        """Initialize cache manager."""
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / ".scip_cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # In-memory cache for frequently accessed items
        self._memory_cache: Dict[str, CacheEntry] = {}
        self.max_memory_entries = max_memory_entries
        
        # File modification tracking
        self._file_hashes: Dict[str, str] = {}
        
        # Performance metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_invalidations = 0
        
        logger.debug(f"Initialized SCIP cache manager with directory: {self.cache_dir}")
    
    def get_document_cache(self, file_path: str) -> Optional[scip_pb2.Document]:
        """Get cached document if valid."""
        cache_key = self._get_cache_key("document", file_path)
        
        # Check if file has been modified
        if self._is_file_modified(file_path):
            self._invalidate_file_cache(file_path)
            return None
        
        # Try memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            self._cache_hits += 1
            logger.debug(f"Memory cache hit for document: {file_path}")
            return entry.data
        
        # Try disk cache
        disk_entry = self._load_from_disk(cache_key)
        if disk_entry:
            # Move to memory cache for faster access
            self._memory_cache[cache_key] = disk_entry
            self._cache_hits += 1
            logger.debug(f"Disk cache hit for document: {file_path}")
            return disk_entry.data
        
        self._cache_misses += 1
        return None
    
    def cache_document(self, file_path: str, document: scip_pb2.Document) -> None:
        """Cache document with file modification tracking."""
        cache_key = self._get_cache_key("document", file_path)
        file_hash = self._calculate_file_hash(file_path)
        
        entry = CacheEntry(
            data=document,
            created_at=datetime.now(),
            file_hash=file_hash
        )
        
        # Store in memory cache
        self._memory_cache[cache_key] = entry
        self._file_hashes[file_path] = file_hash
        
        # Evict old entries if memory cache is full
        self._evict_old_entries()
        
        # Store on disk for persistence
        self._save_to_disk(cache_key, entry)
        
        logger.debug(f"Cached document: {file_path}")
    
    def get_symbol_cache(self, symbol_id: str) -> Optional[scip_pb2.SymbolInformation]:
        """Get cached symbol information."""
        cache_key = self._get_cache_key("symbol", symbol_id)
        
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            self._cache_hits += 1
            return entry.data
        
        disk_entry = self._load_from_disk(cache_key)
        if disk_entry:
            self._memory_cache[cache_key] = disk_entry
            self._cache_hits += 1
            return disk_entry.data
        
        self._cache_misses += 1
        return None
    
    def cache_symbol(self, symbol_id: str, symbol_info: scip_pb2.SymbolInformation) -> None:
        """Cache symbol information."""
        cache_key = self._get_cache_key("symbol", symbol_id)
        
        entry = CacheEntry(
            data=symbol_info,
            created_at=datetime.now(),
            file_hash=""  # Symbols don't have associated files directly
        )
        
        self._memory_cache[cache_key] = entry
        self._save_to_disk(cache_key, entry)
        
        logger.debug(f"Cached symbol: {symbol_id}")
    
    def get_relationship_cache(self, source_symbol: str, target_symbol: str) -> Optional[List[str]]:
        """Get cached relationships between symbols."""
        cache_key = self._get_cache_key("relationship", f"{source_symbol}::{target_symbol}")
        
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            entry.access_count += 1
            self._cache_hits += 1
            return entry.data
        
        self._cache_misses += 1
        return None
    
    def cache_relationships(self, source_symbol: str, target_symbol: str, relationships: List[str]) -> None:
        """Cache relationships between symbols."""
        cache_key = self._get_cache_key("relationship", f"{source_symbol}::{target_symbol}")
        
        entry = CacheEntry(
            data=relationships,
            created_at=datetime.now(),
            file_hash=""
        )
        
        self._memory_cache[cache_key] = entry
        logger.debug(f"Cached relationships: {source_symbol} -> {target_symbol}")
    
    def invalidate_file_cache(self, file_path: str) -> None:
        """Invalidate all cache entries related to a file."""
        self._invalidate_file_cache(file_path)
    
    def invalidate_all_cache(self) -> None:
        """Clear all caches."""
        self._memory_cache.clear()
        self._file_hashes.clear()
        
        # Clear disk cache
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                cache_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete cache file {cache_file}: {e}")
        
        self._cache_invalidations += 1
        logger.info("Invalidated all caches")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests) if total_requests > 0 else 0
        
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": f"{hit_rate:.2%}",
            "memory_entries": len(self._memory_cache),
            "max_memory_entries": self.max_memory_entries,
            "cache_invalidations": self._cache_invalidations,
            "tracked_files": len(self._file_hashes),
            "cache_directory": str(self.cache_dir)
        }
    
    def _get_cache_key(self, cache_type: str, identifier: str) -> str:
        """Generate cache key for identifier."""
        return f"{cache_type}_{hashlib.md5(identifier.encode()).hexdigest()}"
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except (OSError, IOError) as e:
            logger.warning(f"Failed to calculate hash for {file_path}: {e}")
            return ""
    
    def _is_file_modified(self, file_path: str) -> bool:
        """Check if file has been modified since last cache."""
        if file_path not in self._file_hashes:
            return True
        
        current_hash = self._calculate_file_hash(file_path)
        return current_hash != self._file_hashes[file_path]
    
    def _invalidate_file_cache(self, file_path: str) -> None:
        """Invalidate cache entries for a specific file."""
        # Remove from file hash tracking
        if file_path in self._file_hashes:
            del self._file_hashes[file_path]
        
        # Find and remove related cache entries
        document_key = self._get_cache_key("document", file_path)
        if document_key in self._memory_cache:
            del self._memory_cache[document_key]
        
        # Remove from disk cache
        cache_file = self.cache_dir / f"{document_key}.cache"
        if cache_file.exists():
            try:
                cache_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete cache file {cache_file}: {e}")
        
        self._cache_invalidations += 1
        logger.debug(f"Invalidated cache for file: {file_path}")
    
    def _evict_old_entries(self) -> None:
        """Evict least recently used entries when memory cache is full."""
        if len(self._memory_cache) <= self.max_memory_entries:
            return
        
        # Sort by last accessed time (least recent first)
        sorted_entries = sorted(
            self._memory_cache.items(),
            key=lambda x: x[1].last_accessed or x[1].created_at
        )
        
        # Remove oldest 10% of entries
        entries_to_remove = max(1, len(sorted_entries) // 10)
        for i in range(entries_to_remove):
            key_to_remove = sorted_entries[i][0]
            del self._memory_cache[key_to_remove]
        
        logger.debug(f"Evicted {entries_to_remove} cache entries")
    
    def _save_to_disk(self, cache_key: str, entry: CacheEntry) -> None:
        """Save cache entry to disk."""
        try:
            cache_file = self.cache_dir / f"{cache_key}.cache"
            with open(cache_file, 'wb') as f:
                pickle.dump(entry, f)
        except (OSError, IOError, pickle.PickleError) as e:
            logger.warning(f"Failed to save cache entry {cache_key}: {e}")
    
    def _load_from_disk(self, cache_key: str) -> Optional[CacheEntry]:
        """Load cache entry from disk."""
        try:
            cache_file = self.cache_dir / f"{cache_key}.cache"
            if not cache_file.exists():
                return None
            
            # Check if cache file is too old (older than 24 hours)
            if time.time() - cache_file.stat().st_mtime > 86400:  # 24 hours
                cache_file.unlink()
                return None
            
            with open(cache_file, 'rb') as f:
                entry = pickle.load(f)
                entry.last_accessed = datetime.now()
                return entry
                
        except (OSError, IOError, pickle.PickleError) as e:
            logger.warning(f"Failed to load cache entry {cache_key}: {e}")
            return None


class BatchProcessor:
    """Batch processing system for optimized SCIP index generation."""
    
    def __init__(self, cache_manager: SCIPCacheManager, batch_size: int = 50):
        """Initialize batch processor."""
        self.cache_manager = cache_manager
        self.batch_size = batch_size
        self._pending_documents: List[Tuple[str, str]] = []  # (file_path, content)
        self._processed_count = 0
        
    def add_file(self, file_path: str, content: str) -> None:
        """Add file to processing batch."""
        self._pending_documents.append((file_path, content))
        
        # Process batch when it reaches the target size
        if len(self._pending_documents) >= self.batch_size:
            self.process_batch()
    
    def process_batch(self) -> List[scip_pb2.Document]:
        """Process current batch of files."""
        if not self._pending_documents:
            return []
        
        logger.info(f"Processing batch of {len(self._pending_documents)} files")
        documents = []
        
        for file_path, content in self._pending_documents:
            # Check cache first
            cached_doc = self.cache_manager.get_document_cache(file_path)
            if cached_doc:
                documents.append(cached_doc)
                logger.debug(f"Using cached document for {file_path}")
            else:
                # Process file (this would be implemented by the specific factory)
                logger.debug(f"Processing file {file_path}")
                # Placeholder for actual processing
                documents.append(scip_pb2.Document())
        
        self._processed_count += len(self._pending_documents)
        self._pending_documents.clear()
        
        logger.info(f"Completed batch processing. Total processed: {self._processed_count}")
        return documents
    
    def finalize(self) -> List[scip_pb2.Document]:
        """Process any remaining files in the batch."""
        return self.process_batch()
    
    def get_stats(self) -> Dict[str, int]:
        """Get batch processing statistics."""
        return {
            "processed_files": self._processed_count,
            "pending_files": len(self._pending_documents),
            "batch_size": self.batch_size
        }