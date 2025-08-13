"""
Symbol Definitions - Core data structures for enhanced symbol analysis

This module defines the data structures used by SCIPSymbolAnalyzer to represent
accurate symbol information and call relationships in a format optimized for LLM consumption.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


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


@dataclass
class CallRelationships:
    """Call relationship tracking for functions and methods."""
    local: List[str] = field(default_factory=list)
    external: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_local_call(self, function_name: str):
        """Add a local function call."""
        if function_name not in self.local:
            self.local.append(function_name)
    
    def add_external_call(self, name: str, file: str, line: int):
        """Add an external function call."""
        call_info = {"name": name, "file": file, "line": line}
        if call_info not in self.external:
            self.external.append(call_info)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON output."""
        return {
            "local": self.local,
            "external": self.external
        }


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
    
    # Call relationships (only for functions/methods)
    calls: CallRelationships = field(default_factory=lambda: CallRelationships())
    called_by: CallRelationships = field(default_factory=lambda: CallRelationships())
    
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
        return {
            "name": self.name,
            "line": self.line,
            "column": self.column,
            "class": self.class_name,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "is_async": self.is_async,
            "calls": self.calls.to_dict(),
            "called_by": self.called_by.to_dict()
        }
    
    def to_class_dict(self) -> Dict[str, Any]:
        """Convert to class format for JSON output."""
        return {
            "name": self.name,
            "line": self.line,
            "column": self.column,
            "methods": self.methods,
            "attributes": self.attributes,
            "inherits_from": self.inherits_from
        }
    
    def to_variable_dict(self) -> Dict[str, Any]:
        """Convert to variable format for JSON output."""
        return {
            "name": self.name,
            "line": self.line,
            "column": self.column,
            "is_global": self.is_global,
            "type": self.type
        }
    
    def to_constant_dict(self) -> Dict[str, Any]:
        """Convert to constant format for JSON output."""
        return {
            "name": self.name,
            "line": self.line,
            "column": self.column,
            "value": self.value
        }


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
            "status": "success"
        }