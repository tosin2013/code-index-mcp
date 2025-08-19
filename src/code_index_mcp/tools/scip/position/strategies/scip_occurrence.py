"""
SCIP occurrence-based position detection strategy.

This strategy uses SCIP occurrence data to find exact symbol positions
with high confidence.
"""

import logging
from typing import Optional, Dict, Any
from .base import PositionStrategy
from ..confidence import LocationInfo, ConfidenceLevel

logger = logging.getLogger(__name__)

# Try to import SCIP protobuf definitions
try:
    from ....scip.proto import scip_pb2
    SCIP_PROTO_AVAILABLE = True
except ImportError:
    scip_pb2 = None
    SCIP_PROTO_AVAILABLE = False


class SCIPOccurrenceStrategy(PositionStrategy):
    """
    SCIP occurrence-based position detection strategy.
    
    This strategy provides the highest confidence position detection by
    using SCIP occurrence data which contains exact position information
    from the original indexing process.
    """
    
    def __init__(self):
        """Initialize the SCIP occurrence strategy."""
        super().__init__("scip_occurrence")
    
    def get_confidence_level(self) -> ConfidenceLevel:
        """SCIP occurrences provide high confidence positions."""
        return ConfidenceLevel.HIGH
    
    def can_handle_symbol(self, scip_symbol: str, document) -> bool:
        """
        Check if document has occurrences for the symbol.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document
            
        Returns:
            True if document has occurrences we can search
        """
        return hasattr(document, 'occurrences') and document.occurrences
    
    def try_resolve(
        self,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[LocationInfo]:
        """
        Try to resolve position using SCIP occurrence data.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document containing occurrences
            context: Optional context information
            
        Returns:
            LocationInfo with high confidence if found, None otherwise
        """
        # Strategy 1: Look for definition occurrence first (most reliable)
        location = self._find_definition_occurrence(scip_symbol, document)
        if location:
            location.add_metadata('occurrence_type', 'definition')
            return location
        
        # Strategy 2: Look for any occurrence with position data
        location = self._find_any_occurrence(scip_symbol, document)
        if location:
            location.add_metadata('occurrence_type', 'reference')
            return location
        
        # No occurrences found for this symbol
        return None
    
    def _find_definition_occurrence(self, scip_symbol: str, document) -> Optional[LocationInfo]:
        """
        Find the definition occurrence for a symbol.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document
            
        Returns:
            LocationInfo if definition found, None otherwise
        """
        for occurrence in document.occurrences:
            if occurrence.symbol == scip_symbol and self._is_definition(occurrence):
                location = self._parse_occurrence_location(occurrence)
                if location:
                    location.add_metadata('is_definition', True)
                    return location
        return None
    
    def _find_any_occurrence(self, scip_symbol: str, document) -> Optional[LocationInfo]:
        """
        Find any occurrence with location data for a symbol.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document
            
        Returns:
            LocationInfo if any occurrence found, None otherwise
        """
        for occurrence in document.occurrences:
            if occurrence.symbol == scip_symbol:
                location = self._parse_occurrence_location(occurrence)
                if location:
                    location.add_metadata('is_definition', self._is_definition(occurrence))
                    location.add_metadata('symbol_roles', getattr(occurrence, 'symbol_roles', 0))
                    return location
        return None
    
    def _is_definition(self, occurrence) -> bool:
        """
        Check if an occurrence represents a definition.
        
        Args:
            occurrence: SCIP occurrence object
            
        Returns:
            True if this occurrence is a definition
        """
        if not hasattr(occurrence, 'symbol_roles'):
            return False
        
        try:
            if SCIP_PROTO_AVAILABLE:
                return bool(occurrence.symbol_roles & scip_pb2.SymbolRole.Definition)
            else:
                # Fallback: Definition role = 1
                return bool(occurrence.symbol_roles & 1)
        except (AttributeError, TypeError):
            return False
    
    def _parse_occurrence_location(self, occurrence) -> Optional[LocationInfo]:
        """
        Parse location information from SCIP occurrence.
        
        Args:
            occurrence: SCIP occurrence object
            
        Returns:
            LocationInfo if parsing successful, None otherwise
        """
        try:
            if not hasattr(occurrence, 'range') or not occurrence.range:
                return None
            
            range_obj = occurrence.range
            if not hasattr(range_obj, 'start') or not range_obj.start:
                return None
            
            start = range_obj.start
            if len(start) >= 2:
                # SCIP uses 0-based indexing, convert to 1-based
                line = start[0] + 1
                column = start[1] + 1
                
                # Create LocationInfo with metadata
                metadata = {
                    'scip_range_available': True,
                    'range_length': len(start),
                    'raw_line': start[0],
                    'raw_column': start[1]
                }
                
                # Add end position if available
                if hasattr(range_obj, 'end') and range_obj.end and len(range_obj.end) >= 2:
                    metadata.update({
                        'end_line': range_obj.end[0] + 1,
                        'end_column': range_obj.end[1] + 1,
                        'span_lines': range_obj.end[0] - start[0] + 1
                    })
                
                return LocationInfo(
                    line=line,
                    column=column,
                    confidence=ConfidenceLevel.HIGH,
                    method="scip_occurrence",
                    metadata=metadata
                )
                
        except (AttributeError, IndexError, TypeError) as e:
            logger.debug(f"Error parsing occurrence location: {e}")
        
        return None
    
    def get_occurrence_info(self, scip_symbol: str, document) -> Dict[str, Any]:
        """
        Get detailed information about occurrences for a symbol.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document
            
        Returns:
            Dictionary with occurrence statistics and information
        """
        info = {
            'total_occurrences': 0,
            'definition_occurrences': 0,
            'reference_occurrences': 0,
            'occurrences_with_position': 0,
            'role_distribution': {}
        }
        
        for occurrence in document.occurrences:
            if occurrence.symbol == scip_symbol:
                info['total_occurrences'] += 1
                
                if self._is_definition(occurrence):
                    info['definition_occurrences'] += 1
                else:
                    info['reference_occurrences'] += 1
                
                if self._parse_occurrence_location(occurrence):
                    info['occurrences_with_position'] += 1
                
                # Track role distribution
                roles = getattr(occurrence, 'symbol_roles', 0)
                role_key = str(roles)
                info['role_distribution'][role_key] = info['role_distribution'].get(role_key, 0) + 1
        
        return info