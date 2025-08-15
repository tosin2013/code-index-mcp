"""
Symbol Definitions - Core data structures for enhanced symbol analysis

This module defines the data structures used by SCIPSymbolAnalyzer to represent
accurate symbol information and call relationships in a format optimized for LLM consumption.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .relationship_info import SymbolRelationships, RelationshipsSummary


class SymbolLocationError(Exception):
    """Raised when symbol location cannot be determined from SCIP data."""
    pass


class SymbolResolutionError(Exception):
    """Raised when symbol cannot be resolved or parsed."""
    pass


@dataclass
class LocationInfo:
    """Precise location information for a symbol."""
    line: int
    column: int
    confidence: str = 'high'  # 'high', 'fallback', 'estimated'
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary format for JSON output."""
        return {"line": self.line, "column": self.column}


# CallRelationships class removed - now using unified SymbolRelationships


@dataclass
class SymbolDefinition:
    """Enhanced symbol definition with accurate metadata."""
    name: str
    line: int
    column: int
    symbol_type: str  # 'function', 'method', 'class', 'variable', 'constant'
    
    # Optional metadata
    class_name: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False
    
    # Unified relationships (for all symbol types)
    relationships: SymbolRelationships = field(default_factory=lambda: SymbolRelationships())
    
    # Additional class-specific fields
    methods: List[str] = field(default_factory=list)  # For classes
    attributes: List[str] = field(default_factory=list)  # For classes
    inherits_from: List[str] = field(default_factory=list)  # For classes
    
    # Variable/constant-specific fields
    is_global: Optional[bool] = None  # For variables
    type: Optional[str] = None  # For variables
    value: Optional[str] = None  # For constants
    
    # Internal tracking
    scip_symbol: str = ""  # Original SCIP symbol for debugging
    
    def is_callable(self) -> bool:
        """Check if this symbol represents a callable (function/method)."""
        return self.symbol_type in ['function', 'method']
    
    def is_class_member(self) -> bool:
        """Check if this symbol belongs to a class."""
        return self.class_name is not None
    
    def to_function_dict(self) -> Dict[str, Any]:
        """Convert to function format for JSON output."""
        result = {
            "name": self.name,
            "line": self.line,
            "column": self.column,
            "class": self.class_name,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "is_async": self.is_async
        }
        
        # Add relationships if they exist
        relationships_dict = self.relationships.to_dict()
        if relationships_dict:
            result["relationships"] = relationships_dict
            
        return result
    
    def to_class_dict(self) -> Dict[str, Any]:
        """Convert to class format for JSON output."""
        result = {
            "name": self.name,
            "line": self.line,
            "column": self.column,
            "methods": self.methods,
            "attributes": self.attributes,
            "inherits_from": self.inherits_from
        }
        
        # Add relationships if they exist
        relationships_dict = self.relationships.to_dict()
        if relationships_dict:
            result["relationships"] = relationships_dict
            
        return result
    
    def to_variable_dict(self) -> Dict[str, Any]:
        """Convert to variable format for JSON output."""
        result = {
            "name": self.name,
            "line": self.line,
            "column": self.column,
            "is_global": self.is_global,
            "type": self.type
        }
        
        # Add relationships if they exist
        relationships_dict = self.relationships.to_dict()
        if relationships_dict:
            result["relationships"] = relationships_dict
            
        return result
    
    def to_constant_dict(self) -> Dict[str, Any]:
        """Convert to constant format for JSON output."""
        return {
            "name": self.name,
            "line": self.line,
            "column": self.column,
            "value": self.value
        }
    
    # to_scip_relationships method removed - now using unified SymbolRelationships structure


@dataclass
class ImportGroup:
    """Organized import information."""
    standard_library: List[str] = field(default_factory=list)
    third_party: List[str] = field(default_factory=list) 
    local: List[str] = field(default_factory=list)
    
    def add_import(self, module_name: str, import_type: str = 'unknown'):
        """Add an import to the appropriate group."""
        if import_type == 'standard_library':
            if module_name not in self.standard_library:
                self.standard_library.append(module_name)
        elif import_type == 'third_party':
            if module_name not in self.third_party:
                self.third_party.append(module_name)
        elif import_type == 'local':
            if module_name not in self.local:
                self.local.append(module_name)
    
    def to_dict(self) -> Dict[str, List[str]]:
        """Convert to dictionary format for JSON output."""
        return {
            "standard_library": self.standard_library,
            "third_party": self.third_party,
            "local": self.local
        }


@dataclass
class FileAnalysis:
    """Complete file analysis result matching the exact output specification."""
    file_path: str
    language: str
    line_count: int
    size_bytes: int = 0
    
    # Symbol collections organized by type
    functions: List[SymbolDefinition] = field(default_factory=list)
    classes: List[SymbolDefinition] = field(default_factory=list)
    variables: List[SymbolDefinition] = field(default_factory=list)
    constants: List[SymbolDefinition] = field(default_factory=list)
    
    # Dependency information
    imports: ImportGroup = field(default_factory=lambda: ImportGroup())
    
    # Relationship summary
    relationships_summary: Optional[RelationshipsSummary] = None
    
    def add_symbol(self, symbol: SymbolDefinition):
        """Add a symbol to the appropriate collection based on its type."""
        if symbol.symbol_type == 'function' or symbol.symbol_type == 'method':
            self.functions.append(symbol)
        elif symbol.symbol_type == 'class':
            self.classes.append(symbol)
        elif symbol.symbol_type == 'variable':
            self.variables.append(symbol)
        elif symbol.symbol_type == 'constant':
            self.constants.append(symbol)
    
    def get_function_by_name(self, name: str) -> Optional[SymbolDefinition]:
        """Find a function by name."""
        for func in self.functions:
            if func.name == name:
                return func
        return None
    
    def get_class_by_name(self, name: str) -> Optional[SymbolDefinition]:
        """Find a class by name."""
        for cls in self.classes:
            if cls.name == name:
                return cls
        return None
    
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to final JSON output format - EXACT specification."""
        return {
            "file_path": self.file_path,
            "language": self.language,
            "basic_info": {
                "line_count": self.line_count
            },
            "symbols": {
                "functions": [func.to_function_dict() for func in self.functions],
                "classes": [cls.to_class_dict() for cls in self.classes],
                "variables": [var.to_variable_dict() for var in self.variables],
                "constants": [const.to_constant_dict() for const in self.constants]
            },
            "dependencies": {
                "imports": self.imports.to_dict()
            },
            "relationships_summary": self.relationships_summary.to_dict() if self.relationships_summary else {
                "total_relationships": 0,
                "by_type": {},
                "cross_file_relationships": 0
            },
            "status": "success"
        }
    
    def to_scip_relationships(self, symbol_manager=None) -> Dict[str, List[tuple]]:
        """
        Extract all SCIP relationships from this file analysis.
        
        This method provides a unified interface to get all symbol relationships
        in SCIP format, compatible with the relationship management system.
        
        Args:
            symbol_manager: Optional symbol manager for generating proper symbol IDs
            
        Returns:
            Dictionary mapping source_symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        all_relationships = {}
        
        # Process all symbol types
        all_symbols = self.functions + self.classes + self.variables + self.constants
        
        for symbol in all_symbols:
            # Create source symbol ID
            if symbol_manager:
                source_symbol_id = symbol_manager.create_local_symbol(
                    language=self.language,
                    file_path=self.file_path,
                    symbol_path=[symbol.name],
                    descriptor=self._get_symbol_descriptor(symbol)
                )
            else:
                source_symbol_id = f"local {symbol.name}{self._get_symbol_descriptor(symbol)}"
            
            # Get relationships for this symbol
            symbol_relationships = symbol.to_scip_relationships(symbol_manager, self.language, self.file_path)
            
            if symbol_relationships:
                all_relationships[source_symbol_id] = symbol_relationships
        
        return all_relationships
    
    def _get_symbol_descriptor(self, symbol: SymbolDefinition) -> str:
        """Get SCIP descriptor suffix for a symbol."""
        if symbol.symbol_type in ['function', 'method']:
            return "()."
        elif symbol.symbol_type == 'class':
            return "#"
        else:
            return ""