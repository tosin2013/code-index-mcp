"""
Position calculation utilities.

This module provides utilities for position calculations, conversions,
and position-related operations for SCIP symbol analysis.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from .confidence import LocationInfo, ConfidenceLevel

logger = logging.getLogger(__name__)


class PositionCalculator:
    """
    Utility class for position calculations and conversions.

    Provides methods for:
    - Converting between different position formats
    - Calculating position offsets and distances
    - Validating and normalizing positions
    - Estimating positions based on context
    """

    def __init__(self):
        """Initialize the position calculator."""
        self._line_cache: Dict[str, List[int]] = {}  # Cache for line start byte positions

    def convert_byte_to_line_column(
        self,
        byte_offset: int,
        file_content: str,
        file_key: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        Convert byte offset to line and column numbers.

        Args:
            byte_offset: Byte offset in file
            file_content: File content string
            file_key: Optional cache key for the file

        Returns:
            Tuple of (line, column) - both 1-based
        """
        if byte_offset < 0:
            return 1, 1

        if byte_offset >= len(file_content):
            # Return end of file position
            lines = file_content.splitlines()
            if lines:
                return len(lines), len(lines[-1]) + 1
            return 1, 1

        # Get line start positions (cached)
        line_starts = self._get_line_starts(file_content, file_key)

        # Binary search to find line
        line_number = self._binary_search_line(line_starts, byte_offset)

        # Calculate column within the line
        line_start = line_starts[line_number - 1]  # line_number is 1-based
        column = byte_offset - line_start + 1  # Convert to 1-based

        return line_number, column

    def convert_line_column_to_byte(
        self,
        line: int,
        column: int,
        file_content: str,
        file_key: Optional[str] = None
    ) -> int:
        """
        Convert line and column to byte offset.

        Args:
            line: Line number (1-based)
            column: Column number (1-based)
            file_content: File content string
            file_key: Optional cache key for the file

        Returns:
            Byte offset in file
        """
        if line < 1 or column < 1:
            return 0

        # Get line start positions (cached)
        line_starts = self._get_line_starts(file_content, file_key)

        if line > len(line_starts):
            # Beyond end of file
            return len(file_content)

        line_start = line_starts[line - 1]  # Convert to 0-based
        byte_offset = line_start + column - 1  # Convert column to 0-based

        # Ensure we don't go beyond file end
        return min(byte_offset, len(file_content))

    def estimate_position_by_symbol_type(
        self,
        symbol_type: str,
        document_info: Optional[Dict[str, Any]] = None
    ) -> LocationInfo:
        """
        Estimate position based on symbol type characteristics.

        Args:
            symbol_type: Type of symbol (class, function, variable, etc.)
            document_info: Optional document information for better estimation

        Returns:
            LocationInfo with estimated position
        """
        # Default positions based on common patterns
        type_positions = {
            'class': (1, 1),      # Classes usually at file start
            'interface': (1, 1),   # Interfaces usually at file start
            'module': (1, 1),      # Modules at file start
            'namespace': (1, 1),   # Namespaces at file start
            'function': (5, 1),    # Functions after imports
            'method': (10, 5),     # Methods inside classes
            'variable': (3, 1),    # Variables after imports
            'constant': (2, 1),    # Constants near file start
            'field': (8, 5),       # Fields inside classes/structs
            'property': (12, 5),   # Properties inside classes
            'enum': (1, 1),        # Enums at file start
            'enum_member': (15, 5), # Enum members inside enums
        }

        default_line, default_column = type_positions.get(symbol_type, (1, 1))

        # Adjust based on document info
        if document_info:
            # If we have information about document size, adjust positions
            estimated_lines = document_info.get('estimated_lines', 100)
            symbol_count = document_info.get('symbol_count', 10)

            if symbol_count > 0:
                # Distribute symbols throughout the file
                if symbol_type in ['method', 'field', 'property']:
                    # These are typically inside classes, estimate deeper in file
                    default_line = min(estimated_lines // 2, default_line + symbol_count)
                elif symbol_type in ['function', 'variable']:
                    # These might be distributed throughout
                    default_line = min(estimated_lines // 3, default_line + (symbol_count // 2))

        return LocationInfo.from_heuristic(
            line=default_line,
            column=default_column,
            heuristic_type=f"symbol_type_{symbol_type}",
            method="position_calculator_estimate"
        )

    def estimate_position_in_class(
        self,
        class_location: LocationInfo,
        member_index: int = 0,
        member_type: str = "method"
    ) -> LocationInfo:
        """
        Estimate position of a class member relative to class location.

        Args:
            class_location: Location of the containing class
            member_index: Index of the member within the class
            member_type: Type of class member

        Returns:
            LocationInfo with estimated member position
        """
        if not class_location.is_reliable():
            # If class location is unreliable, use basic estimation
            return self.estimate_position_by_symbol_type(member_type)

        # Estimate member position based on class location
        base_line = class_location.line
        base_column = class_location.column

        # Different member types have different typical offsets
        member_offsets = {
            'field': (2, 4),
            'property': (3, 4),
            'method': (4, 4),
            'constructor': (1, 4),
            'destructor': (5, 4),
        }

        line_offset, column_offset = member_offsets.get(member_type, (3, 4))

        # Add index-based spacing
        estimated_line = base_line + line_offset + (member_index * 2)
        estimated_column = base_column + column_offset

        metadata = {
            'class_line': class_location.line,
            'class_column': class_location.column,
            'member_index': member_index,
            'member_type': member_type,
            'based_on_class_location': True
        }

        return LocationInfo(
            line=estimated_line,
            column=estimated_column,
            confidence=ConfidenceLevel.LOW,
            method="class_member_estimation",
            metadata=metadata
        )

    def calculate_distance(self, loc1: LocationInfo, loc2: LocationInfo) -> int:
        """
        Calculate distance between two locations (in lines).

        Args:
            loc1: First location
            loc2: Second location

        Returns:
            Distance in lines (absolute value)
        """
        return abs(loc1.line - loc2.line)

    def is_within_range(
        self,
        location: LocationInfo,
        start_line: int,
        end_line: int
    ) -> bool:
        """
        Check if location is within a line range.

        Args:
            location: Location to check
            start_line: Start of range (inclusive)
            end_line: End of range (inclusive)

        Returns:
            True if location is within range
        """
        return start_line <= location.line <= end_line

    def adjust_position_for_language(
        self,
        location: LocationInfo,
        language: str,
        symbol_type: str
    ) -> LocationInfo:
        """
        Adjust position based on language-specific conventions.

        Args:
            location: Original location
            language: Programming language
            symbol_type: Type of symbol

        Returns:
            Adjusted LocationInfo
        """
        # Language-specific adjustments
        adjustments = {
            'python': self._adjust_for_python,
            'javascript': self._adjust_for_javascript,
            'typescript': self._adjust_for_javascript,  # Same as JS
            'zig': self._adjust_for_zig,
            'objective-c': self._adjust_for_objc,
        }

        adjust_func = adjustments.get(language.lower())
        if adjust_func:
            return adjust_func(location, symbol_type)

        return location

    def validate_position(
        self,
        location: LocationInfo,
        max_line: Optional[int] = None,
        max_column: Optional[int] = None
    ) -> LocationInfo:
        """
        Validate and correct position if necessary.

        Args:
            location: Location to validate
            max_line: Maximum valid line number
            max_column: Maximum valid column number

        Returns:
            Validated LocationInfo
        """
        corrected_line = max(1, location.line)
        corrected_column = max(1, location.column)

        if max_line and corrected_line > max_line:
            corrected_line = max_line

        if max_column and corrected_column > max_column:
            corrected_column = max_column

        if corrected_line != location.line or corrected_column != location.column:
            # Position was corrected, update metadata
            validated_location = LocationInfo(
                line=corrected_line,
                column=corrected_column,
                confidence=location.confidence,
                method=location.method,
                metadata=location.metadata.copy() if location.metadata else {}
            )

            validated_location.add_metadata('position_corrected', True)
            validated_location.add_metadata('original_line', location.line)
            validated_location.add_metadata('original_column', location.column)

            return validated_location

        return location

    def _get_line_starts(self, file_content: str, file_key: Optional[str]) -> List[int]:
        """Get cached line start positions."""
        if file_key and file_key in self._line_cache:
            return self._line_cache[file_key]

        line_starts = [0]  # First line starts at byte 0
        for i, char in enumerate(file_content):
            if char == '\n':
                line_starts.append(i + 1)

        if file_key:
            self._line_cache[file_key] = line_starts

        return line_starts

    def _binary_search_line(self, line_starts: List[int], byte_offset: int) -> int:
        """Binary search to find line number for byte offset."""
        left, right = 0, len(line_starts) - 1

        while left <= right:
            mid = (left + right) // 2

            if mid == len(line_starts) - 1:
                # Last line
                return mid + 1
            elif line_starts[mid] <= byte_offset < line_starts[mid + 1]:
                return mid + 1  # Convert to 1-based
            elif byte_offset < line_starts[mid]:
                right = mid - 1
            else:
                left = mid + 1

        return len(line_starts)  # Fallback to last line

    def _adjust_for_python(self, location: LocationInfo, symbol_type: str) -> LocationInfo:
        """Python-specific position adjustments."""
        # Python functions/classes typically have decorators above them
        if symbol_type in ['function', 'method', 'class'] and location.line > 1:
            # Assume decorators might be present, adjust upward slightly
            adjusted_line = max(1, location.line - 1)
            if adjusted_line != location.line:
                location.add_metadata('python_decorator_adjustment', True)
                location.line = adjusted_line

        return location

    def _adjust_for_javascript(self, location: LocationInfo, symbol_type: str) -> LocationInfo:
        """JavaScript/TypeScript-specific position adjustments."""
        # No specific adjustments needed for now
        return location

    def _adjust_for_zig(self, location: LocationInfo, symbol_type: str) -> LocationInfo:
        """Zig-specific position adjustments."""
        # No specific adjustments needed for now
        return location

    def _adjust_for_objc(self, location: LocationInfo, symbol_type: str) -> LocationInfo:
        """Objective-C specific position adjustments."""
        # Objective-C methods often have + or - prefix
        if symbol_type == 'method' and location.column > 1:
            # Adjust column to account for method prefix
            adjusted_column = max(1, location.column - 1)
            if adjusted_column != location.column:
                location.add_metadata('objc_method_prefix_adjustment', True)
                location.column = adjusted_column

        return location

    def clear_cache(self) -> None:
        """Clear the line position cache."""
        self._line_cache.clear()
        logger.debug("Cleared position calculator cache")
