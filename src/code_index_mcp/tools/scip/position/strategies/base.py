"""
Base position detection strategy.

This module provides the abstract base class for all position detection strategies.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from ..confidence import LocationInfo, ConfidenceLevel

logger = logging.getLogger(__name__)


class PositionStrategy(ABC):
    """
    Abstract base class for position detection strategies.

    Each strategy implements a different approach to detecting symbol positions
    with varying levels of accuracy and confidence.
    """

    def __init__(self, name: str):
        """
        Initialize the position strategy.

        Args:
            name: Human-readable name for this strategy
        """
        self.name = name
        self._stats = {
            'attempts': 0,
            'successes': 0,
            'failures': 0
        }

    @abstractmethod
    def try_resolve(
        self,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[LocationInfo]:
        """
        Attempt to resolve symbol position using this strategy.

        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document containing symbols and occurrences
            context: Optional context information (symbol parser, etc.)

        Returns:
            LocationInfo if position found, None otherwise
        """
        pass

    @abstractmethod
    def get_confidence_level(self) -> ConfidenceLevel:
        """
        Return the confidence level this strategy typically provides.

        Returns:
            ConfidenceLevel for this strategy's results
        """
        pass

    def get_priority(self) -> int:
        """
        Get priority for this strategy (higher = tried first).

        Returns:
            Priority value (0-100, where 100 is highest priority)
        """
        # Map confidence levels to priorities
        confidence_priorities = {
            ConfidenceLevel.HIGH: 90,
            ConfidenceLevel.MEDIUM: 60,
            ConfidenceLevel.LOW: 30,
            ConfidenceLevel.UNKNOWN: 10
        }
        return confidence_priorities.get(self.get_confidence_level(), 50)

    def can_handle_symbol(self, scip_symbol: str, document) -> bool:
        """
        Check if this strategy can handle the given symbol.

        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document

        Returns:
            True if strategy can attempt to resolve this symbol
        """
        # Default implementation: can handle any symbol
        return True

    def resolve(
        self,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[LocationInfo]:
        """
        Public method to resolve position with statistics tracking.

        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document
            context: Optional context information

        Returns:
            LocationInfo if position found, None otherwise
        """
        self._stats['attempts'] += 1

        try:
            if not self.can_handle_symbol(scip_symbol, document):
                self._stats['failures'] += 1
                return None

            result = self.try_resolve(scip_symbol, document, context)

            if result is not None:
                self._stats['successes'] += 1
                # Ensure the result has proper metadata
                if not result.metadata:
                    result.metadata = {}
                result.metadata['strategy'] = self.name
                result.metadata['strategy_confidence'] = self.get_confidence_level().value

                logger.debug(f"Strategy '{self.name}' resolved {scip_symbol} at {result.line}:{result.column}")
                return result
            else:
                self._stats['failures'] += 1
                return None

        except Exception as e:
            self._stats['failures'] += 1
            logger.debug(f"Strategy '{self.name}' failed for {scip_symbol}: {e}")
            return None

    def get_success_rate(self) -> float:
        """
        Get success rate for this strategy.

        Returns:
            Success rate as a float between 0.0 and 1.0
        """
        if self._stats['attempts'] == 0:
            return 0.0
        return self._stats['successes'] / self._stats['attempts']

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics for this strategy.

        Returns:
            Dictionary with strategy statistics
        """
        return {
            'name': self.name,
            'confidence_level': self.get_confidence_level().value,
            'priority': self.get_priority(),
            'success_rate': self.get_success_rate(),
            **self._stats
        }

    def reset_stats(self) -> None:
        """Reset strategy statistics."""
        self._stats = {
            'attempts': 0,
            'successes': 0,
            'failures': 0
        }
        logger.debug(f"Reset statistics for strategy '{self.name}'")

    def __str__(self) -> str:
        """String representation of the strategy."""
        return f"{self.__class__.__name__}(name='{self.name}', confidence={self.get_confidence_level().value})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"{self.__class__.__name__}(name='{self.name}', "
                f"confidence={self.get_confidence_level().value}, "
                f"success_rate={self.get_success_rate():.2f})")