"""
Confidence level management and enhanced location information.

This module provides enhanced location information with confidence levels
for position resolution results.
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """
    Position detection confidence levels.

    Indicates the reliability of position detection results based on
    the method used and available data quality.
    """
    HIGH = "high"           # SCIP occurrence data with exact positions
    MEDIUM = "medium"       # Tree-sitter AST analysis or symbol structure inference
    LOW = "low"             # Heuristic fallback or partial data
    UNKNOWN = "unknown"     # Default/fallback position with minimal confidence

    def __lt__(self, other):
        """Allow confidence level comparison."""
        if not isinstance(other, ConfidenceLevel):
            return NotImplemented
        order = [ConfidenceLevel.UNKNOWN, ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]
        return order.index(self) < order.index(other)

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other


@dataclass
class LocationInfo:
    """
    Enhanced location information with confidence and metadata.

    Provides comprehensive location information including confidence levels,
    detection method metadata, and optional context information.
    """
    line: int
    column: int
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    method: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate location information after initialization."""
        if self.line < 1:
            logger.warning(f"Invalid line number: {self.line}, setting to 1")
            self.line = 1

        if self.column < 1:
            logger.warning(f"Invalid column number: {self.column}, setting to 1")
            self.column = 1

        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def from_scip_occurrence(cls, occurrence, method: str = "scip_occurrence") -> 'LocationInfo':
        """
        Create LocationInfo from SCIP occurrence data.

        Args:
            occurrence: SCIP occurrence object
            method: Detection method name

        Returns:
            LocationInfo with high confidence
        """
        try:
            if not hasattr(occurrence, 'range') or not occurrence.range:
                return cls.default_location(method="scip_occurrence_no_range")

            range_obj = occurrence.range
            if not hasattr(range_obj, 'start') or not range_obj.start:
                return cls.default_location(method="scip_occurrence_no_start")

            start = range_obj.start
            if len(start) >= 2:
                # SCIP uses 0-based indexing, convert to 1-based
                line = start[0] + 1
                column = start[1] + 1

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

                return cls(
                    line=line,
                    column=column,
                    confidence=ConfidenceLevel.HIGH,
                    method=method,
                    metadata=metadata
                )

        except (AttributeError, IndexError, TypeError) as e:
            logger.debug(f"Error creating LocationInfo from SCIP occurrence: {e}")

        return cls.default_location(method="scip_occurrence_error")

    @classmethod
    def from_tree_sitter(
        cls,
        line: int,
        column: int,
        node_info: Optional[Dict[str, Any]] = None,
        method: str = "tree_sitter"
    ) -> 'LocationInfo':
        """
        Create LocationInfo from Tree-sitter analysis.

        Args:
            line: Line number (1-based)
            column: Column number (1-based)
            node_info: Optional AST node information
            method: Detection method name

        Returns:
            LocationInfo with medium confidence
        """
        metadata = {
            'tree_sitter_analysis': True
        }

        if node_info:
            metadata.update({
                'node_type': node_info.get('type'),
                'node_text': node_info.get('text', '')[:50],  # Truncate long text
                'node_start_byte': node_info.get('start_byte'),
                'node_end_byte': node_info.get('end_byte'),
                'node_children_count': node_info.get('children_count', 0)
            })

        return cls(
            line=max(1, line),
            column=max(1, column),
            confidence=ConfidenceLevel.MEDIUM,
            method=method,
            metadata=metadata
        )

    @classmethod
    def from_heuristic(
        cls,
        line: int,
        column: int,
        heuristic_type: str,
        method: str = "heuristic"
    ) -> 'LocationInfo':
        """
        Create LocationInfo from heuristic analysis.

        Args:
            line: Line number (1-based)
            column: Column number (1-based)
            heuristic_type: Type of heuristic used
            method: Detection method name

        Returns:
            LocationInfo with low confidence
        """
        metadata = {
            'heuristic_type': heuristic_type,
            'estimated': True
        }

        return cls(
            line=max(1, line),
            column=max(1, column),
            confidence=ConfidenceLevel.LOW,
            method=method,
            metadata=metadata
        )

    @classmethod
    def default_location(cls, method: str = "default") -> 'LocationInfo':
        """
        Create default LocationInfo for fallback cases.

        Args:
            method: Detection method name

        Returns:
            LocationInfo with unknown confidence at (1,1)
        """
        return cls(
            line=1,
            column=1,
            confidence=ConfidenceLevel.UNKNOWN,
            method=method,
            metadata={'fallback': True}
        )

    def is_reliable(self) -> bool:
        """
        Check if the location information is reliable.

        Returns:
            True if confidence is medium or high
        """
        return self.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def is_high_confidence(self) -> bool:
        """
        Check if the location has high confidence.

        Returns:
            True if confidence is high
        """
        return self.confidence == ConfidenceLevel.HIGH

    def update_confidence(self, new_confidence: ConfidenceLevel, reason: str = "") -> None:
        """
        Update confidence level with optional reason.

        Args:
            new_confidence: New confidence level
            reason: Optional reason for the update
        """
        old_confidence = self.confidence
        self.confidence = new_confidence

        if not self.metadata:
            self.metadata = {}

        self.metadata.update({
            'confidence_updated': True,
            'previous_confidence': old_confidence.value,
            'update_reason': reason
        })

        logger.debug(f"Updated confidence from {old_confidence.value} to {new_confidence.value}: {reason}")

    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata information.

        Args:
            key: Metadata key
            value: Metadata value
        """
        if not self.metadata:
            self.metadata = {}
        self.metadata[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert LocationInfo to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'line': self.line,
            'column': self.column,
            'confidence': self.confidence.value,
            'method': self.method,
            'metadata': self.metadata or {}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LocationInfo':
        """
        Create LocationInfo from dictionary.

        Args:
            data: Dictionary with location data

        Returns:
            LocationInfo instance
        """
        confidence_str = data.get('confidence', 'unknown')
        try:
            confidence = ConfidenceLevel(confidence_str)
        except ValueError:
            confidence = ConfidenceLevel.UNKNOWN

        return cls(
            line=data.get('line', 1),
            column=data.get('column', 1),
            confidence=confidence,
            method=data.get('method'),
            metadata=data.get('metadata', {})
        )

    def __str__(self) -> str:
        """String representation of LocationInfo."""
        return f"LocationInfo(line={self.line}, column={self.column}, confidence={self.confidence.value})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"LocationInfo(line={self.line}, column={self.column}, confidence={self.confidence.value}, method={self.method})"