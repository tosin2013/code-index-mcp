"""SCIP Indexer Factory - manages and selects appropriate indexing strategies."""

import logging
from typing import List, Dict, Set, Optional
from .strategies.base_strategy import SCIPIndexerStrategy
from .strategies.python_strategy import PythonStrategy
from .strategies.javascript_strategy import JavaScriptStrategy
from .strategies.java_strategy import JavaStrategy
from .strategies.objective_c_strategy import ObjectiveCStrategy
from .strategies.zig_strategy import ZigStrategy
from .strategies.fallback_strategy import FallbackStrategy
from ..constants import SUPPORTED_EXTENSIONS


logger = logging.getLogger(__name__)


class SCIPIndexerFactory:
    """Factory for creating and managing SCIP indexing strategies."""
    
    def __init__(self):
        """Initialize the factory with all available strategies."""
        self.strategies: List[SCIPIndexerStrategy] = []
        self.strategy_cache: Dict[str, SCIPIndexerStrategy] = {}
        self._register_all_strategies()
        self._validate_coverage()
    
    def _register_all_strategies(self):
        """Register all available strategies in priority order."""
        logger.info("Registering SCIP indexing strategies (SCIP compliant)...")
        
        # Language-specific strategies (high priority: 95)
        language_strategies = [
            PythonStrategy(priority=95),
            JavaScriptStrategy(priority=95),
            JavaStrategy(priority=95),
            ObjectiveCStrategy(priority=95),
            ZigStrategy(priority=95),
        ]
        
        for strategy in language_strategies:
            self.register_strategy(strategy)
            logger.debug(f"Registered {strategy.get_strategy_name()}")
        
        # Fallback strategy (lowest priority: 10)
        fallback = FallbackStrategy(priority=10)
        self.register_strategy(fallback)
        logger.debug(f"Registered {fallback.get_strategy_name()}")
        
        logger.info(f"Registered {len(self.strategies)} strategies")
    
    def register_strategy(self, strategy: SCIPIndexerStrategy):
        """
        Register a new strategy.
        
        Args:
            strategy: The strategy to register
        """
        self.strategies.append(strategy)
        # Sort strategies by priority (highest first)
        self.strategies.sort(key=lambda s: s.get_priority(), reverse=True)
    
    def get_strategy(self, extension: str, file_path: str = "") -> SCIPIndexerStrategy:
        """
        Get the best strategy for a file type.
        
        Args:
            extension: File extension (e.g., '.py')
            file_path: Optional full file path for context
            
        Returns:
            Best available strategy for the file type
            
        Raises:
            StrategySelectionError: If no suitable strategy is found
        """
        # Check cache first
        cache_key = f"{extension}:{file_path}"
        if cache_key in self.strategy_cache:
            return self.strategy_cache[cache_key]
        
        # Find the highest priority strategy that can handle this file
        for strategy in self.strategies:
            if strategy.can_handle(extension, file_path):
                self.strategy_cache[cache_key] = strategy
                return strategy
        
        # No strategy found
        raise StrategySelectionError(f"No strategy available for extension '{extension}'")
    
    def get_strategies_for_extension(self, extension: str) -> List[SCIPIndexerStrategy]:
        """
        Get all strategies that can handle a file extension.
        
        Args:
            extension: File extension to check
            
        Returns:
            List of strategies, ordered by priority
        """
        return [s for s in self.strategies if s.can_handle(extension, "")]
    
    def list_supported_extensions(self) -> Set[str]:
        """
        Get all file extensions supported by registered strategies.
        
        Returns:
            Set of supported file extensions
        """
        supported = set()
        
        # Add extensions from all registered strategies
        for strategy in self.strategies:
            if isinstance(strategy, PythonStrategy):
                supported.update({'.py', '.pyw'})
            elif isinstance(strategy, JavaScriptStrategy):
                supported.update({'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'})
            elif isinstance(strategy, JavaStrategy):
                supported.update({'.java'})
            elif isinstance(strategy, ObjectiveCStrategy):
                supported.update({'.m', '.mm'})
            elif isinstance(strategy, ZigStrategy):
                supported.update({'.zig', '.zon'})
            elif isinstance(strategy, FallbackStrategy):
                # Fallback supports everything, but we don't want to list everything here
                pass
        
        return supported
    
    def group_files_by_strategy(self, file_paths: List[str]) -> Dict[SCIPIndexerStrategy, List[str]]:
        """
        Group files by the strategy that should handle them.
        
        Args:
            file_paths: List of file paths to group
            
        Returns:
            Dictionary mapping strategies to their file lists
        """
        strategy_files = {}
        
        for file_path in file_paths:
            # Get file extension
            extension = self._get_file_extension(file_path)
            
            try:
                strategy = self.get_strategy(extension, file_path)
                if strategy not in strategy_files:
                    strategy_files[strategy] = []
                strategy_files[strategy].append(file_path)
            except StrategySelectionError:
                # Skip files we can't handle
                logger.debug(f"No strategy available for file: {file_path}")
                continue
        
        return strategy_files
    
    def _get_file_extension(self, file_path: str) -> str:
        """Extract file extension from path."""
        if '.' not in file_path:
            return ''
        return '.' + file_path.split('.')[-1].lower()
    
    def _validate_coverage(self):
        """Validate that we have reasonable coverage of supported file types."""
        if not self.strategies:
            logger.warning("No SCIP strategies registered - indexing will not work")
            return
        
        logger.info(f"SCIP factory initialized with {len(self.strategies)} strategies")


# Exception classes
class SCIPIndexingError(Exception):
    """Base exception for SCIP indexing errors."""


class StrategySelectionError(SCIPIndexingError):
    """Raised when no suitable strategy can be found for a file."""


class IndexingFailedError(SCIPIndexingError):
    """Raised when indexing fails for a file or project."""