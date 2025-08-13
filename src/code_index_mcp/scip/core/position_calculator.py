"""SCIP Position Calculator - Accurate position calculation for SCIP ranges."""

import ast
import logging
from typing import Tuple, List, Optional
try:
    import tree_sitter
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class PositionCalculator:
    """
    Accurate position calculator for SCIP ranges.
    
    Handles conversion from various source positions (AST nodes, Tree-sitter nodes,
    line/column positions) to precise SCIP Range objects.
    """
    
    def __init__(self, content: str, encoding: str = 'utf-8'):
        """
        Initialize position calculator with file content.
        
        Args:
            content: File content as string
            encoding: File encoding (default: utf-8)
        """
        self.content = content
        self.encoding = encoding
        self.lines = content.split('\n')
        
        # Build byte offset mapping for accurate position calculation
        self._build_position_maps()
        
        logger.debug(f"PositionCalculator initialized for {len(self.lines)} lines")
    
    def _build_position_maps(self):
        """Build mapping tables for efficient position conversion."""
        # Build line start byte offsets
        self.line_start_bytes: List[int] = [0]
        
        content_bytes = self.content.encode(self.encoding)
        current_byte = 0
        
        for line in self.lines[:-1]:  # Exclude last line
            line_bytes = line.encode(self.encoding)
            current_byte += len(line_bytes) + 1  # +1 for newline
            self.line_start_bytes.append(current_byte)
    
    def ast_node_to_range(self, node: ast.AST) -> scip_pb2.Range:
        """
        Convert Python AST node to SCIP Range.
        
        Args:
            node: Python AST node
            
        Returns:
            SCIP Range object
        """
        range_obj = scip_pb2.Range()
        
        if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
            # Python AST uses 1-based line numbers, SCIP uses 0-based
            start_line = node.lineno - 1
            start_col = node.col_offset
            
            # Try to get end position
            if hasattr(node, 'end_lineno') and hasattr(node, 'end_col_offset'):
                end_line = node.end_lineno - 1
                end_col = node.end_col_offset
            else:
                # Estimate end position
                end_line, end_col = self._estimate_ast_end_position(node, start_line, start_col)
            
            range_obj.start.extend([start_line, start_col])
            range_obj.end.extend([end_line, end_col])
        else:
            # Fallback for nodes without position info
            range_obj.start.extend([0, 0])
            range_obj.end.extend([0, 1])
        
        return range_obj
    
    def tree_sitter_node_to_range(self, node) -> scip_pb2.Range:
        """
        Convert Tree-sitter node to SCIP Range.
        
        Args:
            node: Tree-sitter Node object
            
        Returns:
            SCIP Range object
        """
        if not TREE_SITTER_AVAILABLE:
            logger.warning("Tree-sitter not available, using fallback range")
            range_obj = scip_pb2.Range()
            range_obj.start.extend([0, 0])
            range_obj.end.extend([0, 1])
            return range_obj
        
        range_obj = scip_pb2.Range()
        
        # Tree-sitter provides byte offsets, convert to line/column
        start_line, start_col = self.byte_to_line_col(node.start_byte)
        end_line, end_col = self.byte_to_line_col(node.end_byte)
        
        range_obj.start.extend([start_line, start_col])
        range_obj.end.extend([end_line, end_col])
        
        return range_obj
    
    def line_col_to_range(self, 
                         start_line: int, 
                         start_col: int,
                         end_line: Optional[int] = None,
                         end_col: Optional[int] = None,
                         name_length: int = 1) -> scip_pb2.Range:
        """
        Create SCIP Range from line/column positions.
        
        Args:
            start_line: Start line (0-based)
            start_col: Start column (0-based)
            end_line: End line (optional)
            end_col: End column (optional)
            name_length: Length of symbol name for end position estimation
            
        Returns:
            SCIP Range object
        """
        range_obj = scip_pb2.Range()
        
        # Use provided end position or estimate
        if end_line is not None and end_col is not None:
            final_end_line = end_line
            final_end_col = end_col
        else:
            final_end_line = start_line
            final_end_col = start_col + name_length
        
        range_obj.start.extend([start_line, start_col])
        range_obj.end.extend([final_end_line, final_end_col])
        
        return range_obj
    
    def byte_to_line_col(self, byte_offset: int) -> Tuple[int, int]:
        """
        Convert byte offset to line/column position.
        
        Args:
            byte_offset: Byte offset in file
            
        Returns:
            Tuple of (line, column) - both 0-based
        """
        if byte_offset < 0:
            return (0, 0)
        
        # Find the line containing this byte offset
        line_num = 0
        for i, line_start in enumerate(self.line_start_bytes):
            if byte_offset < line_start:
                line_num = i - 1
                break
        else:
            line_num = len(self.line_start_bytes) - 1
        
        # Ensure line_num is valid
        line_num = max(0, min(line_num, len(self.lines) - 1))
        
        # Calculate column within the line
        line_start_byte = self.line_start_bytes[line_num]
        byte_in_line = byte_offset - line_start_byte
        
        # Convert byte offset to character offset within line
        if line_num < len(self.lines):
            line_content = self.lines[line_num]
            try:
                # Convert byte offset to character offset
                line_bytes = line_content.encode(self.encoding)
                if byte_in_line <= len(line_bytes):
                    char_offset = len(line_bytes[:byte_in_line].decode(self.encoding, errors='ignore'))
                else:
                    char_offset = len(line_content)
            except (UnicodeDecodeError, UnicodeEncodeError):
                # Fallback to byte offset as character offset
                char_offset = min(byte_in_line, len(line_content))
        else:
            char_offset = 0
        
        return (line_num, char_offset)
    
    def find_name_in_line(self, line_num: int, name: str) -> Tuple[int, int]:
        """
        Find the position of a name within a line.
        
        Args:
            line_num: Line number (0-based)
            name: Name to find
            
        Returns:
            Tuple of (start_col, end_col) or (0, len(name)) if not found
        """
        if line_num < 0 or line_num >= len(self.lines):
            return (0, len(name))
        
        line_content = self.lines[line_num]
        start_col = line_content.find(name)
        
        if start_col == -1:
            # Try to find word boundary match
            import re
            pattern = r'\b' + re.escape(name) + r'\b'
            match = re.search(pattern, line_content)
            if match:
                start_col = match.start()
            else:
                start_col = 0
        
        end_col = start_col + len(name)
        return (start_col, end_col)
    
    def _estimate_ast_end_position(self, 
                                  node: ast.AST, 
                                  start_line: int, 
                                  start_col: int) -> Tuple[int, int]:
        """
        Estimate end position for AST nodes without end position info.
        
        Args:
            node: AST node
            start_line: Start line
            start_col: Start column
            
        Returns:
            Tuple of (end_line, end_col)
        """
        # Try to get name length from common node types
        name_length = 1
        
        if hasattr(node, 'id'):  # Name nodes
            name_length = len(node.id)
        elif hasattr(node, 'name'):  # Function/Class definition nodes
            name_length = len(node.name)
        elif hasattr(node, 'arg'):  # Argument nodes
            name_length = len(node.arg)
        elif hasattr(node, 'attr'):  # Attribute nodes
            name_length = len(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            name_length = len(str(node.value)) + 2  # Add quotes
        
        # For most cases, end position is on the same line
        end_line = start_line
        end_col = start_col + name_length
        
        # Ensure end position doesn't exceed line length
        if start_line < len(self.lines):
            line_length = len(self.lines[start_line])
            end_col = min(end_col, line_length)
        
        return (end_line, end_col)
    
    def validate_range(self, range_obj: scip_pb2.Range) -> bool:
        """
        Validate that a SCIP Range is within file bounds.
        
        Args:
            range_obj: SCIP Range to validate
            
        Returns:
            True if range is valid
        """
        if len(range_obj.start) != 2 or len(range_obj.end) != 2:
            return False
        
        start_line, start_col = range_obj.start[0], range_obj.start[1]
        end_line, end_col = range_obj.end[0], range_obj.end[1]
        
        # Check line bounds
        if start_line < 0 or start_line >= len(self.lines):
            return False
        if end_line < 0 or end_line >= len(self.lines):
            return False
        
        # Check column bounds
        if start_line < len(self.lines):
            if start_col < 0 or start_col > len(self.lines[start_line]):
                return False
        
        if end_line < len(self.lines):
            if end_col < 0 or end_col > len(self.lines[end_line]):
                return False
        
        # Check that start <= end
        if start_line > end_line:
            return False
        if start_line == end_line and start_col > end_col:
            return False
        
        return True