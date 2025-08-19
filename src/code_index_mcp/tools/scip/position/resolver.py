"""
Main position resolution system.

This module provides the PositionResolver that coordinates different position
detection strategies to find symbol positions with appropriate confidence levels.
"""

import logging
from typing import Optional, Dict, Any, List
from .confidence import LocationInfo, ConfidenceLevel
from .strategies.scip_occurrence import SCIPOccurrenceStrategy
from .strategies.tree_sitter_strategy import TreeSitterStrategy
from .strategies.heuristic import HeuristicStrategy
from .strategies.base import PositionStrategy

logger = logging.getLogger(__name__)


class PositionResolver:
    """
    Main position resolution coordinator.
    
    This class manages multiple position detection strategies and applies them
    in order of confidence level to find the best possible position for SCIP symbols.
    
    Strategy Order (by confidence):
    1. SCIPOccurrenceStrategy (HIGH) - Uses SCIP occurrence data
    2. TreeSitterStrategy (MEDIUM) - Uses AST analysis 
    3. HeuristicStrategy (LOW) - Uses pattern matching and estimation
    """
    
    def __init__(self):
        """Initialize the position resolver with default strategies."""
        self._strategies: List[PositionStrategy] = []
        self._strategy_cache: Dict[str, PositionStrategy] = {}
        self._resolution_cache: Dict[str, LocationInfo] = {}
        self._setup_default_strategies()
    
    def _setup_default_strategies(self) -> None:
        """Setup default position detection strategies in order of confidence."""
        self._strategies = [
            SCIPOccurrenceStrategy(),  # Highest confidence
            TreeSitterStrategy(),      # Medium confidence
            HeuristicStrategy()        # Lowest confidence (fallback)
        ]
        
        # Build strategy cache for quick lookup
        for strategy in self._strategies:
            self._strategy_cache[strategy.name] = strategy
        
        logger.debug(f"Initialized position resolver with {len(self._strategies)} strategies")
    
    def resolve_position(
        self,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None,
        preferred_confidence: Optional[ConfidenceLevel] = None
    ) -> Optional[LocationInfo]:
        """
        Resolve position for a SCIP symbol using the best available strategy.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: Document containing source text or SCIP data
            context: Optional context information (file path, project info, etc.)
            preferred_confidence: Minimum confidence level required
            
        Returns:
            LocationInfo with the best confidence available, or None if not found
        """
        if not scip_symbol:
            return None
        
        # Check cache first
        cache_key = self._create_cache_key(scip_symbol, context)
        if cache_key in self._resolution_cache:
            cached_result = self._resolution_cache[cache_key]
            if self._meets_confidence_requirement(cached_result, preferred_confidence):
                return cached_result
        
        # Try strategies in order of confidence
        best_location = None
        
        for strategy in self._strategies:
            try:
                # Check if strategy can handle this symbol
                if not strategy.can_handle_symbol(scip_symbol, document):
                    continue
                
                # Try to resolve position
                location = strategy.try_resolve(scip_symbol, document, context)
                
                if location:
                    # Add strategy information to metadata
                    location.add_metadata('strategy_used', strategy.name)
                    location.add_metadata('strategy_confidence', strategy.get_confidence_level().value)
                    
                    # Check if this meets our confidence requirements
                    if self._meets_confidence_requirement(location, preferred_confidence):
                        # Cache and return immediately if confidence requirement is met
                        self._resolution_cache[cache_key] = location
                        logger.debug(f"Resolved {scip_symbol} using {strategy.name} with {location.confidence.value} confidence")
                        return location
                    
                    # Keep track of best location found so far
                    if not best_location or location.confidence > best_location.confidence:
                        best_location = location
                        
            except Exception as e:
                logger.debug(f"Strategy {strategy.name} failed for {scip_symbol}: {e}")
                continue
        
        # Cache the best result found (even if it doesn't meet preferred confidence)
        if best_location:
            self._resolution_cache[cache_key] = best_location
            logger.debug(f"Resolved {scip_symbol} using fallback with {best_location.confidence.value} confidence")
        
        return best_location
    
    def resolve_multiple_positions(
        self,
        symbols: List[str],
        document,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Optional[LocationInfo]]:
        """
        Resolve positions for multiple SCIP symbols efficiently.
        
        Args:
            symbols: List of SCIP symbol identifiers
            document: Document containing source text or SCIP data
            context: Optional context information
            
        Returns:
            Dictionary mapping symbol -> LocationInfo (or None if not found)
        """
        results = {}
        
        for symbol in symbols:
            results[symbol] = self.resolve_position(symbol, document, context)
        
        return results
    
    def try_strategy(
        self,
        strategy_name: str,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[LocationInfo]:
        """
        Try a specific strategy to resolve a position.
        
        Args:
            strategy_name: Name of the strategy to use
            scip_symbol: SCIP symbol identifier
            document: Document containing source text or SCIP data
            context: Optional context information
            
        Returns:
            LocationInfo if the strategy succeeds, None otherwise
        """
        if strategy_name not in self._strategy_cache:
            logger.warning(f"Unknown strategy: {strategy_name}")
            return None
        
        strategy = self._strategy_cache[strategy_name]
        
        if not strategy.can_handle_symbol(scip_symbol, document):
            return None
        
        try:
            location = strategy.try_resolve(scip_symbol, document, context)
            if location:
                location.add_metadata('strategy_used', strategy.name)
                location.add_metadata('strategy_confidence', strategy.get_confidence_level().value)
            return location
        except Exception as e:
            logger.debug(f"Strategy {strategy_name} failed for {scip_symbol}: {e}")
            return None
    
    def get_available_strategies(self) -> List[str]:
        """
        Get list of available strategy names.
        
        Returns:
            List of strategy names
        """
        return [strategy.name for strategy in self._strategies]
    
    def get_strategy_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all available strategies.
        
        Returns:
            List of dictionaries with strategy information
        """
        return [
            {
                'name': strategy.name,
                'confidence_level': strategy.get_confidence_level().value,
                'description': strategy.__class__.__doc__.strip().split('\n')[0] if strategy.__class__.__doc__ else ''
            }
            for strategy in self._strategies
        ]
    
    def add_strategy(self, strategy: PositionStrategy, priority: Optional[int] = None) -> None:
        """
        Add a custom position detection strategy.
        
        Args:
            strategy: PositionStrategy instance to add
            priority: Optional priority (lower number = higher priority)
                     If None, adds at appropriate position based on confidence
        """
        if priority is not None:
            self._strategies.insert(priority, strategy)
        else:
            # Insert based on confidence level
            inserted = False
            for i, existing_strategy in enumerate(self._strategies):
                if strategy.get_confidence_level() > existing_strategy.get_confidence_level():
                    self._strategies.insert(i, strategy)
                    inserted = True
                    break
            
            if not inserted:
                self._strategies.append(strategy)
        
        # Update cache
        self._strategy_cache[strategy.name] = strategy
        
        logger.debug(f"Added strategy {strategy.name} with {strategy.get_confidence_level().value} confidence")
    
    def remove_strategy(self, strategy_name: str) -> bool:
        """
        Remove a strategy by name.
        
        Args:
            strategy_name: Name of the strategy to remove
            
        Returns:
            True if strategy was removed, False if not found
        """
        if strategy_name not in self._strategy_cache:
            return False
        
        strategy = self._strategy_cache[strategy_name]
        self._strategies.remove(strategy)
        del self._strategy_cache[strategy_name]
        
        logger.debug(f"Removed strategy {strategy_name}")
        return True
    
    def clear_cache(self) -> None:
        """Clear all cached resolution results."""
        self._resolution_cache.clear()
        logger.debug("Cleared position resolution cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'cache_size': len(self._resolution_cache),
            'strategies_count': len(self._strategies),
            'strategy_names': self.get_available_strategies()
        }
    
    def find_best_positions(
        self,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None,
        max_results: int = 3
    ) -> List[LocationInfo]:
        """
        Find multiple possible positions for a symbol using different strategies.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: Document containing source text or SCIP data
            context: Optional context information
            max_results: Maximum number of results to return
            
        Returns:
            List of LocationInfo objects sorted by confidence
        """
        positions = []
        
        for strategy in self._strategies[:max_results]:
            try:
                if strategy.can_handle_symbol(scip_symbol, document):
                    location = strategy.try_resolve(scip_symbol, document, context)
                    if location:
                        location.add_metadata('strategy_used', strategy.name)
                        location.add_metadata('strategy_confidence', strategy.get_confidence_level().value)
                        positions.append(location)
            except Exception as e:
                logger.debug(f"Strategy {strategy.name} failed for {scip_symbol}: {e}")
        
        # Sort by confidence level (highest first)
        positions.sort(key=lambda x: x.confidence, reverse=True)
        
        return positions[:max_results]
    
    def _create_cache_key(self, scip_symbol: str, context: Optional[Dict[str, Any]]) -> str:
        """Create a cache key for resolution results."""
        if not context:
            return scip_symbol
        
        # Include relevant context in cache key
        relevant_keys = ['file_path', 'language', 'project_path']
        context_parts = []
        
        for key in relevant_keys:
            if key in context:
                context_parts.append(f"{key}:{context[key]}")
        
        if context_parts:
            return f"{scip_symbol}#{':'.join(context_parts)}"
        return scip_symbol
    
    def _meets_confidence_requirement(
        self, 
        location: LocationInfo, 
        preferred_confidence: Optional[ConfidenceLevel]
    ) -> bool:
        """Check if location meets the preferred confidence requirement."""
        if preferred_confidence is None:
            return True
        return location.confidence >= preferred_confidence
    
    def diagnose_resolution(
        self,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Diagnose position resolution for debugging purposes.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: Document containing source text or SCIP data
            context: Optional context information
            
        Returns:
            Dictionary with diagnostic information
        """
        diagnosis = {
            'symbol': scip_symbol,
            'strategies_tested': [],
            'successful_strategies': [],
            'failed_strategies': [],
            'best_result': None,
            'context_available': context is not None,
            'document_type': type(document).__name__
        }
        
        for strategy in self._strategies:
            strategy_info = {
                'name': strategy.name,
                'confidence_level': strategy.get_confidence_level().value,
                'can_handle': False,
                'result': None,
                'error': None
            }
            
            try:
                strategy_info['can_handle'] = strategy.can_handle_symbol(scip_symbol, document)
                
                if strategy_info['can_handle']:
                    location = strategy.try_resolve(scip_symbol, document, context)
                    if location:
                        strategy_info['result'] = location.to_dict()
                        diagnosis['successful_strategies'].append(strategy.name)
                        
                        if not diagnosis['best_result'] or location.confidence > ConfidenceLevel(diagnosis['best_result']['confidence']):
                            diagnosis['best_result'] = location.to_dict()
                    else:
                        diagnosis['failed_strategies'].append(strategy.name)
                else:
                    diagnosis['failed_strategies'].append(strategy.name)
                    
            except Exception as e:
                strategy_info['error'] = str(e)
                diagnosis['failed_strategies'].append(strategy.name)
            
            diagnosis['strategies_tested'].append(strategy_info)
        
        return diagnosis


# Global resolver instance for convenience
_resolver_instance: Optional[PositionResolver] = None


def get_position_resolver() -> PositionResolver:
    """
    Get the global position resolver instance.
    
    Returns:
        Global PositionResolver instance
    """
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = PositionResolver()
    return _resolver_instance


def resolve_position(
    scip_symbol: str,
    document,
    context: Optional[Dict[str, Any]] = None,
    preferred_confidence: Optional[ConfidenceLevel] = None
) -> Optional[LocationInfo]:
    """
    Convenience function to resolve a position using the global resolver.
    
    Args:
        scip_symbol: SCIP symbol identifier
        document: Document containing source text or SCIP data
        context: Optional context information
        preferred_confidence: Minimum confidence level required
        
    Returns:
        LocationInfo with the best confidence available, or None if not found
    """
    return get_position_resolver().resolve_position(
        scip_symbol, document, context, preferred_confidence
    )