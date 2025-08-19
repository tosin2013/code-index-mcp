"""
Position resolution system for SCIP symbols.

This package provides the modular position resolution system that replaces
complex position detection logic in SCIPSymbolAnalyzer, following the
refactoring plan for better maintainability and accuracy.

Key Components:
- PositionResolver: Main position resolution engine using strategy pattern
- PositionStrategy: Abstract base for position detection strategies
- SCIPOccurrenceStrategy: SCIP occurrence-based position detection (high confidence)
- TreeSitterStrategy: Tree-sitter AST-based position detection (medium confidence)
- HeuristicStrategy: Fallback heuristic position detection (low confidence)
- PositionCalculator: Utility for position calculations and conversions
- LocationInfo: Enhanced location information with confidence levels

The system provides:
- Multi-layered position detection with confidence scoring
- Fallback mechanisms for robust symbol location
- Caching for performance optimization
- Integration with SCIPSymbolManager
- Support for different SCIP symbol formats
"""

from .resolver import PositionResolver, get_position_resolver, resolve_position
from .calculator import PositionCalculator
from .confidence import ConfidenceLevel, LocationInfo
from .strategies import (
    PositionStrategy,
    SCIPOccurrenceStrategy,
    TreeSitterStrategy,
    HeuristicStrategy
)

__all__ = [
    'PositionResolver',
    'get_position_resolver',
    'resolve_position',
    'PositionCalculator',
    'ConfidenceLevel',
    'LocationInfo',
    'PositionStrategy',
    'SCIPOccurrenceStrategy',
    'TreeSitterStrategy',
    'HeuristicStrategy'
]