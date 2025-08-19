"""
Dependency registry and caching system.

This module provides centralized caching and registry functionality for
dependency classification results and metadata.
"""

import time
import logging
from typing import Dict, Optional, Any, Set, List, Tuple
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class DependencyRegistry:
    """
    Centralized registry and caching system for dependency classification.

    Provides:
    - Classification result caching
    - Dependency metadata storage
    - Performance statistics
    - Cache management and cleanup
    """

    def __init__(self, max_cache_size: int = 10000, cache_ttl: int = 3600):
        """
        Initialize the dependency registry.

        Args:
            max_cache_size: Maximum number of entries to cache
            cache_ttl: Cache time-to-live in seconds
        """
        self.max_cache_size = max_cache_size
        self.cache_ttl = cache_ttl

        # Classification cache: {cache_key: (classification, timestamp)}
        self._classification_cache: Dict[str, Tuple[str, float]] = {}

        # Dependency metadata cache: {language: {package: metadata}}
        self._metadata_cache: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

        # Standard library cache: {language: (modules_set, timestamp)}
        self._stdlib_cache: Dict[str, Tuple[Set[str], float]] = {}

        # Package manager file cache: {language: (files_set, timestamp)}
        self._package_files_cache: Dict[str, Tuple[Set[str], float]] = {}

        # Statistics
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'classifications_performed': 0,
            'cache_evictions': 0,
            'last_cleanup': time.time()
        }

        # Classification counters
        self._classification_counts = Counter()

    def cache_classification(self, cache_key: str, classification: str) -> None:
        """
        Cache a dependency classification result.

        Args:
            cache_key: Unique cache key for the classification
            classification: Classification result to cache
        """
        current_time = time.time()

        # Check if cache is full and needs cleanup
        if len(self._classification_cache) >= self.max_cache_size:
            self._cleanup_cache()

        # Store the classification with timestamp
        self._classification_cache[cache_key] = (classification, current_time)
        self._classification_counts[classification] += 1
        self._stats['classifications_performed'] += 1

        logger.debug(f"Cached classification: {cache_key} -> {classification}")

    def get_cached_classification(self, cache_key: str) -> Optional[str]:
        """
        Retrieve a cached classification result.

        Args:
            cache_key: Cache key to look up

        Returns:
            Cached classification or None if not found/expired
        """
        if cache_key not in self._classification_cache:
            self._stats['cache_misses'] += 1
            return None

        classification, timestamp = self._classification_cache[cache_key]
        current_time = time.time()

        # Check if the cache entry has expired
        if current_time - timestamp > self.cache_ttl:
            del self._classification_cache[cache_key]
            self._stats['cache_misses'] += 1
            logger.debug(f"Cache entry expired: {cache_key}")
            return None

        self._stats['cache_hits'] += 1
        return classification

    def cache_dependency_metadata(
        self,
        language: str,
        package_name: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Cache dependency metadata.

        Args:
            language: Programming language
            package_name: Package/dependency name
            metadata: Metadata to cache
        """
        self._metadata_cache[language][package_name] = {
            **metadata,
            'cached_at': time.time()
        }
        logger.debug(f"Cached metadata for {language}:{package_name}")

    def get_cached_metadata(
        self,
        language: str,
        package_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached dependency metadata.

        Args:
            language: Programming language
            package_name: Package/dependency name

        Returns:
            Cached metadata or None if not found/expired
        """
        if language not in self._metadata_cache:
            return None

        if package_name not in self._metadata_cache[language]:
            return None

        metadata = self._metadata_cache[language][package_name]
        current_time = time.time()

        # Check if metadata has expired
        cached_at = metadata.get('cached_at', 0)
        if current_time - cached_at > self.cache_ttl:
            del self._metadata_cache[language][package_name]
            return None

        return metadata

    def cache_standard_library_modules(self, language: str, modules: Set[str]) -> None:
        """
        Cache standard library modules for a language.

        Args:
            language: Programming language
            modules: Set of standard library module names
        """
        self._stdlib_cache[language] = (modules, time.time())
        logger.debug(f"Cached {len(modules)} stdlib modules for {language}")

    def get_cached_standard_library_modules(self, language: str) -> Optional[Set[str]]:
        """
        Retrieve cached standard library modules.

        Args:
            language: Programming language

        Returns:
            Set of standard library modules or None if not cached/expired
        """
        if language not in self._stdlib_cache:
            return None

        modules, timestamp = self._stdlib_cache[language]
        current_time = time.time()

        # Stdlib modules rarely change, use longer TTL
        if current_time - timestamp > self.cache_ttl * 24:  # 24x longer TTL
            del self._stdlib_cache[language]
            return None

        return modules

    def cache_package_manager_files(self, language: str, files: Set[str]) -> None:
        """
        Cache package manager files for a language.

        Args:
            language: Programming language
            files: Set of package manager file names
        """
        self._package_files_cache[language] = (files, time.time())
        logger.debug(f"Cached {len(files)} package manager files for {language}")

    def get_cached_package_manager_files(self, language: str) -> Optional[Set[str]]:
        """
        Retrieve cached package manager files.

        Args:
            language: Programming language

        Returns:
            Set of package manager files or None if not cached/expired
        """
        if language not in self._package_files_cache:
            return None

        files, timestamp = self._package_files_cache[language]
        current_time = time.time()

        # Package manager files rarely change, use longer TTL
        if current_time - timestamp > self.cache_ttl * 12:  # 12x longer TTL
            del self._package_files_cache[language]
            return None

        return files

    def get_dependency_list(self, language: str, classification: str) -> List[str]:
        """
        Get list of dependencies of a specific classification for a language.

        Args:
            language: Programming language
            classification: Classification type to filter by

        Returns:
            List of dependency names
        """
        if language not in self._metadata_cache:
            return []

        dependencies = []
        for package_name, metadata in self._metadata_cache[language].items():
            if metadata.get('classification') == classification:
                dependencies.append(package_name)

        return dependencies

    def get_classification_summary(self) -> Dict[str, int]:
        """
        Get summary of classification counts.

        Returns:
            Dictionary with classification counts
        """
        return dict(self._classification_counts)

    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        current_time = time.time()

        # Clean classification cache
        expired_keys = []
        for cache_key, (classification, timestamp) in self._classification_cache.items():
            if current_time - timestamp > self.cache_ttl:
                expired_keys.append(cache_key)

        for key in expired_keys:
            del self._classification_cache[key]
            self._stats['cache_evictions'] += 1

        # Clean metadata cache
        for language in list(self._metadata_cache.keys()):
            expired_packages = []
            for package, metadata in self._metadata_cache[language].items():
                cached_at = metadata.get('cached_at', 0)
                if current_time - cached_at > self.cache_ttl:
                    expired_packages.append(package)

            for package in expired_packages:
                del self._metadata_cache[language][package]

            # Remove empty language entries
            if not self._metadata_cache[language]:
                del self._metadata_cache[language]

        # Clean stdlib cache
        expired_langs = []
        for language, (modules, timestamp) in self._stdlib_cache.items():
            if current_time - timestamp > self.cache_ttl * 24:
                expired_langs.append(language)

        for lang in expired_langs:
            del self._stdlib_cache[lang]

        # Clean package files cache
        expired_langs = []
        for language, (files, timestamp) in self._package_files_cache.items():
            if current_time - timestamp > self.cache_ttl * 12:
                expired_langs.append(language)

        for lang in expired_langs:
            del self._package_files_cache[lang]

        self._stats['last_cleanup'] = current_time
        logger.debug(f"Cache cleanup completed, evicted {len(expired_keys)} classification entries")

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._classification_cache.clear()
        self._metadata_cache.clear()
        self._stdlib_cache.clear()
        self._package_files_cache.clear()

        # Reset stats but keep historical counters
        self._stats.update({
            'cache_hits': 0,
            'cache_misses': 0,
            'cache_evictions': 0,
            'last_cleanup': time.time()
        })

        logger.debug("Cleared all dependency registry cache")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with statistics
        """
        current_time = time.time()

        stats = {
            **self._stats,
            'cache_size': len(self._classification_cache),
            'metadata_entries': sum(len(packages) for packages in self._metadata_cache.values()),
            'stdlib_languages': len(self._stdlib_cache),
            'package_files_languages': len(self._package_files_cache),
            'classification_counts': dict(self._classification_counts),
            'cache_hit_rate': (
                self._stats['cache_hits'] /
                max(1, self._stats['cache_hits'] + self._stats['cache_misses'])
            ),
            'uptime': current_time - self._stats['last_cleanup']
        }

        return stats

    def optimize_cache(self) -> None:
        """Optimize cache for better performance."""
        # Remove least recently used entries if cache is getting full
        if len(self._classification_cache) > self.max_cache_size * 0.8:
            current_time = time.time()

            # Sort by timestamp and remove oldest entries
            sorted_entries = sorted(
                self._classification_cache.items(),
                key=lambda x: x[1][1]  # Sort by timestamp
            )

            # Remove oldest 20% of entries
            remove_count = int(len(sorted_entries) * 0.2)
            for i in range(remove_count):
                cache_key, (classification, timestamp) = sorted_entries[i]
                del self._classification_cache[cache_key]
                self._stats['cache_evictions'] += 1

            logger.debug(f"Optimized cache, removed {remove_count} oldest entries")
