"""SCIP Framework Types - Core type definitions for SCIP standard compliance."""

from dataclasses import dataclass
from typing import List, Dict, Protocol, Iterator, Tuple, Optional
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class SCIPSymbolDescriptor:
    """SCIP symbol descriptor - immutable data structure for symbol information."""
    name: str
    kind: str  # function, class, variable, etc.
    scope_path: List[str]
    descriptor_suffix: str  # (). # (param) etc.
    
    def to_scip_descriptor(self) -> str:
        """Convert to SCIP standard descriptor format."""
        scope = ".".join(self.scope_path) if self.scope_path else ""
        full_path = f"{scope}.{self.name}" if scope else self.name
        return f"{full_path}{self.descriptor_suffix}"


@dataclass(frozen=True)
class SCIPPositionInfo:
    """SCIP position information - immutable position data with validation."""
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    
    def validate(self) -> bool:
        """Validate position information for SCIP compliance."""
        return (
            self.start_line <= self.end_line and 
            (self.start_line < self.end_line or self.start_column <= self.end_column) and
            all(x >= 0 for x in [self.start_line, self.start_column, self.end_line, self.end_column])
        )


@dataclass
class SCIPSymbolContext:
    """Context information for symbol extraction and processing."""
    file_path: str
    content: str
    scope_stack: List[str]
    imports: Dict[str, str]
    
    def with_scope(self, scope_name: str) -> 'SCIPSymbolContext':
        """Create new context with additional scope."""
        return SCIPSymbolContext(
            file_path=self.file_path,
            content=self.content,
            scope_stack=self.scope_stack + [scope_name],
            imports=self.imports.copy()
        )


# Alias for compatibility
SCIPContext = SCIPSymbolContext

# Import and alias Relationship type
from .relationship_manager import SymbolRelationship
Relationship = SymbolRelationship


class SCIPSymbolExtractor(Protocol):
    """Symbol extractor protocol - mandatory interface for symbol extraction."""
    
    def extract_symbols(self, context: SCIPSymbolContext) -> Iterator[SCIPSymbolDescriptor]:
        """Extract symbol definitions from context."""
        ...
    
    def extract_references(self, context: SCIPSymbolContext) -> Iterator[Tuple[SCIPSymbolDescriptor, SCIPPositionInfo]]:
        """Extract symbol references with position information."""
        ...
    
    def extract_relationships(self, context: SCIPSymbolContext) -> Iterator[Tuple[str, str, str]]:
        """Extract symbol relationships (source, target, relationship_type)."""
        ...