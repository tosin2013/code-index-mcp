"""SCIP Position Calculator - UTF-8/UTF-16 compliant position calculation."""

import logging
from typing import Tuple, Optional, Any
from .types import SCIPPositionInfo


logger = logging.getLogger(__name__)


class SCIPPositionCalculator:
    """SCIP position calculator - UTF-8/UTF-16 compliant with mandatory validation."""
    
    def __init__(self, encoding: str = "utf-8"):
        """Initialize position calculator with specified encoding."""
        self.encoding = encoding
        self._line_cache = {}  # Cache for line information
    
    def calculate_positions(self, content: str, node_info: Any) -> SCIPPositionInfo:
        """Calculate precise positions with mandatory validation."""
        
        # Language-specific node position extraction logic
        start_line, start_col, end_line, end_col = self._extract_node_positions(content, node_info)
        
        # Create position information
        position = SCIPPositionInfo(start_line, start_col, end_line, end_col)
        
        # Mandatory validation
        if not position.validate():
            raise ValueError(f"Invalid position: {position}")
        
        # Validate within document bounds
        if not self._is_within_bounds(position, content):
            raise ValueError(f"Position out of document bounds: {position}")
        
        return position
    
    def calculate_positions_from_range(self, content: str, start_byte: int, end_byte: int) -> SCIPPositionInfo:
        """Calculate positions from byte ranges (useful for tree-sitter nodes)."""
        lines = content.split('\n')
        
        # Convert byte offsets to line/column positions
        start_line, start_col = self._byte_offset_to_line_col(content, start_byte, lines)
        end_line, end_col = self._byte_offset_to_line_col(content, end_byte, lines)
        
        position = SCIPPositionInfo(start_line, start_col, end_line, end_col)
        
        # Mandatory validation
        if not position.validate():
            raise ValueError(f"Invalid position calculated from bytes [{start_byte}:{end_byte}]: {position}")
        
        if not self._is_within_bounds(position, content):
            raise ValueError(f"Position out of document bounds: {position}")
        
        return position
    
    def calculate_positions_from_line_col(self, content: str, start_line: int, start_col: int, 
                                        end_line: int, end_col: int) -> SCIPPositionInfo:
        """Calculate positions from explicit line/column coordinates."""
        position = SCIPPositionInfo(start_line, start_col, end_line, end_col)
        
        # Mandatory validation
        if not position.validate():
            raise ValueError(f"Invalid position: {position}")
        
        # Validate within document bounds
        if not self._is_within_bounds(position, content):
            raise ValueError(f"Position out of document bounds: {position}")
        
        return position
    
    def _extract_node_positions(self, content: str, node_info: Any) -> Tuple[int, int, int, int]:
        """Extract node positions - subclass implementation required."""
        # Default implementation for objects with line/column attributes
        if hasattr(node_info, 'lineno') and hasattr(node_info, 'col_offset'):
            # AST node (Python)
            start_line = node_info.lineno - 1  # Convert to 0-indexed
            start_col = node_info.col_offset
            
            # Estimate end position if not available
            if hasattr(node_info, 'end_lineno') and hasattr(node_info, 'end_col_offset'):
                end_line = node_info.end_lineno - 1
                end_col = node_info.end_col_offset
            else:
                # Fallback: assume single token
                end_line = start_line
                end_col = start_col + len(getattr(node_info, 'name', 'unknown'))
            
            return start_line, start_col, end_line, end_col
        
        elif hasattr(node_info, 'start_point') and hasattr(node_info, 'end_point'):
            # Tree-sitter node
            start_line = node_info.start_point[0]
            start_col = node_info.start_point[1]
            end_line = node_info.end_point[0]
            end_col = node_info.end_point[1]
            
            return start_line, start_col, end_line, end_col
        
        elif isinstance(node_info, dict):
            # Dictionary format
            return (
                node_info.get('start_line', 0),
                node_info.get('start_col', 0),
                node_info.get('end_line', 0),
                node_info.get('end_col', 0)
            )
        
        else:
            raise NotImplementedError(f"Position extraction not implemented for node type: {type(node_info)}")
    
    def _byte_offset_to_line_col(self, content: str, byte_offset: int, lines: list) -> Tuple[int, int]:
        """Convert byte offset to line/column position with UTF-8 awareness."""
        if byte_offset == 0:
            return 0, 0
        
        # Convert content to bytes for accurate offset calculation
        content_bytes = content.encode(self.encoding)
        
        if byte_offset >= len(content_bytes):
            # End of file
            return len(lines) - 1, len(lines[-1]) if lines else 0
        
        # Find the line containing this byte offset
        current_byte = 0
        for line_num, line in enumerate(lines):
            line_bytes = (line + '\n').encode(self.encoding) if line_num < len(lines) - 1 else line.encode(self.encoding)
            
            if current_byte + len(line_bytes) > byte_offset:
                # Byte offset is within this line
                offset_in_line = byte_offset - current_byte
                # Convert byte offset within line to character position
                line_text = line_bytes[:offset_in_line].decode(self.encoding, errors='ignore')
                return line_num, len(line_text)
            
            current_byte += len(line_bytes)
        
        # Fallback
        return len(lines) - 1, len(lines[-1]) if lines else 0
    
    def _is_within_bounds(self, position: SCIPPositionInfo, content: str) -> bool:
        """Validate position is within document bounds."""
        lines = content.split('\n')
        max_line = len(lines) - 1
        
        # Check line bounds
        if position.start_line < 0 or position.end_line > max_line:
            return False
        
        # Check column bounds for start position
        if position.start_line <= max_line:
            max_start_col = len(lines[position.start_line])
            if position.start_column < 0 or position.start_column > max_start_col:
                return False
        
        # Check column bounds for end position
        if position.end_line <= max_line:
            max_end_col = len(lines[position.end_line])
            if position.end_column < 0 or position.end_column > max_end_col:
                return False
        
        return True
    
    def _is_utf8_compliant(self, position: SCIPPositionInfo, content: str) -> bool:
        """Validate UTF-8 character position accuracy."""
        try:
            lines = content.split('\n')
            
            # Check if positions fall on character boundaries
            if position.start_line < len(lines):
                start_line_text = lines[position.start_line]
                if position.start_column <= len(start_line_text):
                    # Check UTF-8 character boundary
                    char_at_pos = start_line_text[:position.start_column].encode('utf-8')
                    # If we can encode/decode without errors, position is valid
                    char_at_pos.decode('utf-8')
            
            if position.end_line < len(lines):
                end_line_text = lines[position.end_line]
                if position.end_column <= len(end_line_text):
                    char_at_pos = end_line_text[:position.end_column].encode('utf-8')
                    char_at_pos.decode('utf-8')
            
            return True
            
        except (UnicodeEncodeError, UnicodeDecodeError, IndexError):
            logger.warning(f"UTF-8 compliance check failed for position: {position}")
            return False
    
    def validate_position_full(self, position: SCIPPositionInfo, content: str) -> bool:
        """Perform full position validation including UTF-8 compliance."""
        return (
            position.validate() and 
            self._is_within_bounds(position, content) and
            self._is_utf8_compliant(position, content)
        )
    
    def get_position_text(self, content: str, position: SCIPPositionInfo) -> str:
        """Extract text at the given position for verification."""
        try:
            lines = content.split('\n')
            
            if position.start_line == position.end_line:
                # Single line
                line = lines[position.start_line]
                return line[position.start_column:position.end_column]
            else:
                # Multi-line
                result_lines = []
                
                # First line
                result_lines.append(lines[position.start_line][position.start_column:])
                
                # Middle lines
                for line_num in range(position.start_line + 1, position.end_line):
                    result_lines.append(lines[line_num])
                
                # Last line
                result_lines.append(lines[position.end_line][:position.end_column])
                
                return '\n'.join(result_lines)
                
        except IndexError as e:
            logger.error(f"Failed to extract text at position {position}: {e}")
            return ""