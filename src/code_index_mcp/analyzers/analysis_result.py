"""Standardized analysis result structure."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class Symbol:
    """Represents a code symbol (function, class, etc.)."""
    name: str
    line: int
    symbol_type: str  # 'function', 'class', 'import', 'variable', etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class AnalysisResult:
    """Standardized result structure for all analyzers."""
    # Basic file information
    file_path: str
    line_count: int
    size_bytes: int
    extension: str
    analysis_type: str
    
    # Symbols found in the file
    symbols: Dict[str, List[Symbol]] = field(default_factory=dict)
    
    # Summary counts
    counts: Dict[str, int] = field(default_factory=dict)
    
    # Language-specific metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Error information if analysis failed
    error: Optional[str] = None
    
    def add_symbol(self, symbol_type: str, name: str, line: int, metadata: Dict[str, Any] = None):
        """Add a symbol to the result."""
        if symbol_type not in self.symbols:
            self.symbols[symbol_type] = []
        
        symbol = Symbol(
            name=name,
            line=line,
            symbol_type=symbol_type,
            metadata=metadata or {}
        )
        self.symbols[symbol_type].append(symbol)
        
        # Update counts
        count_key = f"{symbol_type}_count"
        self.counts[count_key] = self.counts.get(count_key, 0) + 1
    
    def get_symbols(self, symbol_type: str) -> List[Symbol]:
        """Get symbols of a specific type."""
        return self.symbols.get(symbol_type, [])
    
    def get_count(self, symbol_type: str) -> int:
        """Get count of symbols of a specific type."""
        return self.counts.get(f"{symbol_type}_count", 0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        result = {
            "file_path": self.file_path,
            "line_count": self.line_count, 
            "size_bytes": self.size_bytes,
            "extension": self.extension,
            "analysis_type": self.analysis_type,
        }
        
        # Add error if present
        if self.error:
            result["error"] = self.error
            return result
        
        # Add symbol lists (backwards compatibility)
        for symbol_type, symbols in self.symbols.items():
            if symbol_type == "import":
                # Special handling for imports - return strings for backwards compatibility
                result["imports"] = [s.name for s in symbols]
            else:
                # Return list of dicts for other symbols
                result[f"{symbol_type}s"] = [
                    {"line": s.line, "name": s.name, **s.metadata} 
                    for s in symbols
                ]
        
        # Add counts
        result.update(self.counts)
        
        # Add metadata
        result.update(self.metadata)
        
        return result