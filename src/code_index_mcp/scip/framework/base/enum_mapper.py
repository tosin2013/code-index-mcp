"""Base enum mapper class for SCIP compliance."""

from abc import ABC, abstractmethod


class BaseEnumMapper(ABC):
    """Base enum mapper class - mandatory implementation for all languages."""
    
    @abstractmethod
    def map_symbol_kind(self, language_kind: str) -> int:
        """Map language-specific type to SCIP SymbolKind."""
        pass
    
    @abstractmethod  
    def map_syntax_kind(self, language_syntax: str) -> int:
        """Map language-specific syntax to SCIP SyntaxKind."""
        pass
    
    @abstractmethod
    def map_symbol_role(self, language_role: str) -> int:
        """Map language-specific role to SCIP SymbolRole."""
        pass
    
    def validate_enum_value(self, enum_value: int, enum_type: str) -> bool:
        """Validate enum value validity."""
        valid_ranges = {
            'SymbolKind': range(0, 65),  # Updated range based on actual protobuf
            'SyntaxKind': range(0, 30),  # 0-29 according to SCIP standard  
            'SymbolRole': [1, 2, 4, 8, 16, 32]  # Bit flags
        }
        
        if enum_type in valid_ranges:
            if enum_type == 'SymbolRole':
                return enum_value in valid_ranges[enum_type] or any(enum_value & flag for flag in valid_ranges[enum_type])
            else:
                return enum_value in valid_ranges[enum_type]
        
        return False