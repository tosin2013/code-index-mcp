"""SCIP Compliance Validator - Runtime verification for SCIP standard compliance."""

import logging
import re
from typing import List, Dict, Optional, Tuple, Any
from .types import SCIPPositionInfo
from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class SCIPComplianceValidator:
    """SCIP compliance validator for runtime verification of generated content."""
    
    # SCIP symbol ID format patterns
    LOCAL_SYMBOL_PATTERN = re.compile(r'^local\s+.+$')
    GLOBAL_SYMBOL_PATTERN = re.compile(r'^[^\s]+\s+[^\s]+\s+[^\s]+(\s+[^\s]+)?\s+.+$')
    
    def __init__(self):
        """Initialize compliance validator."""
        self.validation_errors = []
        self.validation_warnings = []
    
    def validate_document(self, document: scip_pb2.Document) -> bool:
        """
        Validate complete SCIP document for compliance.
        
        Args:
            document: SCIP Document to validate
            
        Returns:
            True if document is compliant, False otherwise
        """
        self.clear_validation_results()
        
        try:
            # Validate document structure
            self._validate_document_structure(document)
            
            # Validate all symbol occurrences
            for occurrence in document.occurrences:
                self._validate_occurrence(occurrence)
            
            # Validate all symbol information
            for symbol_info in document.symbols:
                self._validate_symbol_information(symbol_info)
            
            # Check for consistency between occurrences and symbols
            self._validate_occurrence_symbol_consistency(document)
            
            # Log validation results
            if self.validation_errors:
                logger.error(f"Document validation failed with {len(self.validation_errors)} errors")
                for error in self.validation_errors:
                    logger.error(f"  - {error}")
                return False
            
            if self.validation_warnings:
                logger.warning(f"Document validation completed with {len(self.validation_warnings)} warnings")
                for warning in self.validation_warnings:
                    logger.warning(f"  - {warning}")
            
            logger.debug("Document validation passed")
            return True
            
        except Exception as e:
            self._add_error(f"Validation exception: {e}")
            return False
    
    def validate_index(self, index: scip_pb2.Index) -> bool:
        """
        Validate complete SCIP index for compliance.
        
        Args:
            index: SCIP Index to validate
            
        Returns:
            True if index is compliant, False otherwise
        """
        self.clear_validation_results()
        
        try:
            # Validate index metadata
            if index.HasField('metadata'):
                self._validate_metadata(index.metadata)
            else:
                self._add_error("Index missing required metadata")
            
            # Validate all documents
            for document in index.documents:
                if not self.validate_document(document):
                    self._add_error(f"Document validation failed: {document.relative_path}")
            
            # Validate external symbols
            for external_symbol in index.external_symbols:
                self._validate_symbol_information(external_symbol)
            
            return len(self.validation_errors) == 0
            
        except Exception as e:
            self._add_error(f"Index validation exception: {e}")
            return False
    
    def validate_symbol_id(self, symbol_id: str) -> bool:
        """
        Validate symbol ID against SCIP grammar.
        
        Args:
            symbol_id: Symbol ID to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not symbol_id:
            return False
        
        if symbol_id.startswith('local '):
            return self._validate_local_symbol(symbol_id[6:])
        else:
            return self._validate_global_symbol(symbol_id)
    
    def validate_position(self, position: SCIPPositionInfo, content: str) -> bool:
        """
        Validate position information against content.
        
        Args:
            position: Position to validate
            content: Source content
            
        Returns:
            True if position is valid, False otherwise
        """
        try:
            # Basic position validation
            if not position.validate():
                return False
            
            # Document bounds validation
            if not self._is_within_document_bounds(position, content):
                return False
            
            # UTF-8 compliance validation
            if not self._is_utf8_compliant(position, content):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Position validation error: {e}")
            return False
    
    def _validate_document_structure(self, document: scip_pb2.Document) -> None:
        """Validate basic document structure."""
        if not document.relative_path:
            self._add_error("Document missing relative_path")
        
        if not document.language:
            self._add_warning("Document missing language specification")
        
        # Check path format
        if '\\' in document.relative_path:
            self._add_warning("Document path should use forward slashes")
    
    def _validate_occurrence(self, occurrence: scip_pb2.Occurrence) -> None:
        """Validate SCIP occurrence."""
        # Validate symbol ID
        if not self.validate_symbol_id(occurrence.symbol):
            self._add_error(f"Invalid symbol ID in occurrence: {occurrence.symbol}")
        
        # Validate symbol roles
        if not self._validate_symbol_roles(occurrence.symbol_roles):
            self._add_error(f"Invalid symbol roles: {occurrence.symbol_roles}")
        
        # Validate syntax kind
        if not self._validate_syntax_kind(occurrence.syntax_kind):
            self._add_error(f"Invalid syntax kind: {occurrence.syntax_kind}")
        
        # Validate range
        if occurrence.HasField('range'):
            self._validate_range(occurrence.range)
    
    def _validate_symbol_information(self, symbol_info: scip_pb2.SymbolInformation) -> None:
        """Validate SCIP symbol information."""
        # Validate symbol ID
        if not self.validate_symbol_id(symbol_info.symbol):
            self._add_error(f"Invalid symbol ID in symbol info: {symbol_info.symbol}")
        
        # Validate symbol kind
        if not self._validate_symbol_kind(symbol_info.kind):
            self._add_error(f"Invalid symbol kind: {symbol_info.kind}")
        
        # Validate display name
        if not symbol_info.display_name:
            self._add_warning(f"Symbol missing display name: {symbol_info.symbol}")
    
    def _validate_metadata(self, metadata: scip_pb2.Metadata) -> None:
        """Validate SCIP metadata."""
        if not metadata.HasField('tool_info'):
            self._add_error("Metadata missing tool_info")
        else:
            if not metadata.tool_info.name:
                self._add_error("Metadata tool_info missing name")
            if not metadata.tool_info.version:
                self._add_warning("Metadata tool_info missing version")
        
        if not metadata.project_root:
            self._add_error("Metadata missing project_root")
        
        # Validate text encoding
        if metadata.text_document_encoding == scip_pb2.UnspecifiedTextDocumentEncoding:
            self._add_warning("Metadata has unspecified text encoding")
    
    def _validate_range(self, range_obj: scip_pb2.Range) -> None:
        """Validate SCIP range object."""
        if len(range_obj.start) < 2 or len(range_obj.end) < 2:
            self._add_error("Range missing start or end positions (need [line, character])")
            return
        
        start_line, start_char = range_obj.start[0], range_obj.start[1]
        end_line, end_char = range_obj.end[0], range_obj.end[1]
        
        # Validate position ordering
        if start_line > end_line or (start_line == end_line and start_char > end_char):
            self._add_error(f"Invalid range: start position after end position")
        
        # Validate non-negative positions
        if start_line < 0 or start_char < 0 or end_line < 0 or end_char < 0:
            self._add_error("Range positions cannot be negative")
    
    def _validate_occurrence_symbol_consistency(self, document: scip_pb2.Document) -> None:
        """Validate consistency between occurrences and symbol definitions."""
        defined_symbols = {symbol.symbol for symbol in document.symbols}
        referenced_symbols = {occ.symbol for occ in document.occurrences}
        
        # Check for undefined symbols (warnings, not errors)
        undefined_refs = referenced_symbols - defined_symbols
        for undefined_symbol in undefined_refs:
            if undefined_symbol.startswith('local '):
                self._add_warning(f"Reference to undefined local symbol: {undefined_symbol}")
    
    def _validate_local_symbol(self, local_id: str) -> bool:
        """Validate local symbol format."""
        return bool(local_id and not local_id.startswith(' ') and not local_id.endswith(' '))
    
    def _validate_global_symbol(self, symbol_id: str) -> bool:
        """Validate global symbol format."""
        parts = symbol_id.split(' ')
        return len(parts) >= 3 and all(part.strip() for part in parts)
    
    def _validate_symbol_kind(self, kind: int) -> bool:
        """Validate SymbolKind enum value."""
        return 0 <= kind <= 64  # SCIP SymbolKind range (updated to match actual protobuf)
    
    def _validate_syntax_kind(self, kind: int) -> bool:
        """Validate SyntaxKind enum value."""
        return 0 <= kind <= 29  # SCIP SyntaxKind range
    
    def _validate_symbol_roles(self, roles: int) -> bool:
        """Validate SymbolRole bit flags."""
        valid_flags = [1, 2, 4, 8, 16, 32]  # Definition, Import, WriteAccess, ReadAccess, Generated, Test
        
        if roles in valid_flags:
            return True
        
        # Check if it's a valid combination of flags
        return (roles & ~sum(valid_flags)) == 0 and roles > 0
    
    def _is_within_document_bounds(self, position: SCIPPositionInfo, content: str) -> bool:
        """Check if position is within document boundaries."""
        lines = content.split('\n')
        return (
            0 <= position.start_line < len(lines) and
            0 <= position.end_line < len(lines) and
            0 <= position.start_column <= len(lines[position.start_line]) and
            0 <= position.end_column <= len(lines[position.end_line])
        )
    
    def _is_utf8_compliant(self, position: SCIPPositionInfo, content: str) -> bool:
        """Validate UTF-8 character position accuracy."""
        try:
            lines = content.split('\n')
            
            # Test encoding/decoding at position boundaries
            if position.start_line < len(lines):
                start_line_text = lines[position.start_line][:position.start_column]
                start_line_text.encode('utf-8').decode('utf-8')
            
            if position.end_line < len(lines):
                end_line_text = lines[position.end_line][:position.end_column]
                end_line_text.encode('utf-8').decode('utf-8')
            
            return True
            
        except (UnicodeEncodeError, UnicodeDecodeError, IndexError):
            return False
    
    def _add_error(self, message: str) -> None:
        """Add validation error."""
        self.validation_errors.append(message)
    
    def _add_warning(self, message: str) -> None:
        """Add validation warning."""
        self.validation_warnings.append(message)
    
    def clear_validation_results(self) -> None:
        """Clear previous validation results."""
        self.validation_errors.clear()
        self.validation_warnings.clear()
    
    def get_validation_summary(self) -> dict:
        """Get summary of validation results."""
        return {
            'errors': len(self.validation_errors),
            'warnings': len(self.validation_warnings),
            'error_messages': self.validation_errors.copy(),
            'warning_messages': self.validation_warnings.copy(),
            'is_valid': len(self.validation_errors) == 0
        }