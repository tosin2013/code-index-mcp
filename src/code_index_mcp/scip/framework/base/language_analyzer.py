"""Base language analyzer class for different parsing approaches."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class BaseLanguageAnalyzer(ABC):
    """Base class for language-specific analyzers (AST, regex, tree-sitter, etc.)."""
    
    @abstractmethod
    def parse(self, content: str, filename: str = "<unknown>"):
        """Parse source code content into an internal representation."""
        pass
    
    @abstractmethod
    def is_symbol_definition(self, node) -> bool:
        """Check if a node represents a symbol definition."""
        pass
    
    @abstractmethod
    def is_symbol_reference(self, node) -> bool:
        """Check if a node represents a symbol reference."""
        pass
    
    @abstractmethod
    def get_symbol_name(self, node) -> Optional[str]:
        """Extract symbol name from a node."""
        pass
    
    @abstractmethod
    def get_node_position(self, node) -> tuple:
        """Get position information from a node."""
        pass
    
    def extract_symbols(self, content: str) -> List[Dict[str, Any]]:
        """Extract all symbols from content - default implementation."""
        symbols = []
        try:
            parsed = self.parse(content)
            nodes = self.walk(parsed) if hasattr(self, 'walk') else [parsed]
            
            for node in nodes:
                if self.is_symbol_definition(node):
                    symbol_name = self.get_symbol_name(node)
                    if symbol_name:
                        position = self.get_node_position(node)
                        symbols.append({
                            'name': symbol_name,
                            'position': position,
                            'node': node
                        })
        except Exception:
            pass
        
        return symbols
    
    def extract_references(self, content: str) -> List[Dict[str, Any]]:
        """Extract all symbol references from content - default implementation."""
        references = []
        try:
            parsed = self.parse(content)
            nodes = self.walk(parsed) if hasattr(self, 'walk') else [parsed]
            
            for node in nodes:
                if self.is_symbol_reference(node):
                    symbol_name = self.get_symbol_name(node)
                    if symbol_name:
                        position = self.get_node_position(node)
                        references.append({
                            'name': symbol_name,
                            'position': position,
                            'node': node
                        })
        except Exception:
            pass
        
        return references