"""Fallback enum mapper implementation."""

from typing import Dict, Optional
from ..base.enum_mapper import BaseEnumMapper
from ...proto import scip_pb2


class FallbackEnumMapper(BaseEnumMapper):
    """Fallback enum mapper for basic SCIP enum mappings."""
    
    def __init__(self):
        """Initialize fallback enum mapper with minimal mappings."""
        super().__init__()
        
        # Minimal symbol kind mappings for fallback
        self._symbol_kind_map = {
            'file': scip_pb2.File,
            'text': scip_pb2.File,
            'unknown': scip_pb2.UnspecifiedSymbolKind,
        }
        
        # Minimal symbol role mappings
        self._symbol_role_map = {
            'definition': scip_pb2.Definition,
            'reference': scip_pb2.Read,
        }
        
        # Minimal syntax kind mappings
        self._syntax_kind_map = {
            'file': scip_pb2.UnspecifiedSyntaxKind,
            'text': scip_pb2.UnspecifiedSyntaxKind,
            'identifier': scip_pb2.IdentifierKeyword,
        }
    
    def map_symbol_kind(self, fallback_kind: str) -> int:
        """Map fallback symbol kind to SCIP SymbolKind enum."""
        kind = self._symbol_kind_map.get(fallback_kind.lower())
        if kind is not None:
            return kind
        
        # Default to File for fallback
        return scip_pb2.File
    
    def map_symbol_role(self, fallback_role: str) -> int:
        """Map fallback symbol role to SCIP SymbolRole enum."""
        role = self._symbol_role_map.get(fallback_role.lower())
        if role is not None:
            return role
        
        # Default to Definition for fallback
        return scip_pb2.Definition
    
    def map_syntax_kind(self, fallback_syntax: str) -> int:
        """Map fallback syntax kind to SCIP SyntaxKind enum."""
        syntax = self._syntax_kind_map.get(fallback_syntax.lower())
        if syntax is not None:
            return syntax
        
        # Default to UnspecifiedSyntaxKind for fallback
        return scip_pb2.UnspecifiedSyntaxKind
    
    def get_symbol_kind_name(self, kind: int) -> Optional[str]:
        """Get human-readable name for symbol kind."""
        reverse_map = {v: k for k, v in self._symbol_kind_map.items()}
        return reverse_map.get(kind)
    
    def get_symbol_role_name(self, role: int) -> Optional[str]:
        """Get human-readable name for symbol role."""
        reverse_map = {v: k for k, v in self._symbol_role_map.items()}
        return reverse_map.get(role)
    
    def get_syntax_kind_name(self, syntax: int) -> Optional[str]:
        """Get human-readable name for syntax kind."""
        reverse_map = {v: k for k, v in self._syntax_kind_map.items()}
        return reverse_map.get(syntax)
    
    def validate_symbol_kind(self, kind: int) -> bool:
        """Validate if symbol kind is valid."""
        # Accept all valid SCIP symbol kinds
        return 0 <= kind <= 64
    
    def validate_symbol_role(self, role: int) -> bool:
        """Validate if symbol role is valid."""
        # Accept all valid SCIP symbol roles
        return 0 <= role <= 32
    
    def validate_syntax_kind(self, syntax: int) -> bool:
        """Validate if syntax kind is valid."""
        # Accept all valid SCIP syntax kinds
        return 0 <= syntax <= 1000
    
    def get_supported_symbol_kinds(self) -> Dict[str, int]:
        """Get all supported symbol kinds."""
        return self._symbol_kind_map.copy()
    
    def get_supported_symbol_roles(self) -> Dict[str, int]:
        """Get all supported symbol roles."""
        return self._symbol_role_map.copy()
    
    def get_supported_syntax_kinds(self) -> Dict[str, int]:
        """Get all supported syntax kinds."""
        return self._syntax_kind_map.copy()