"""Base class for all language-specific relationship extractors."""

from abc import ABC, abstractmethod
from typing import Iterator
from ..types import SCIPContext, Relationship


class BaseRelationshipExtractor(ABC):
    """Base class for all language-specific relationship extractors."""
    
    @abstractmethod
    def extract_inheritance_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract inheritance relationships - required for all OOP languages."""
        pass
    
    @abstractmethod
    def extract_call_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract call relationships - required for all languages."""
        pass
    
    @abstractmethod
    def extract_import_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract import/dependency relationships - required for all languages."""
        pass
    
    def extract_composition_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract composition relationships - optional implementation."""
        return iter([])
    
    def extract_interface_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract interface relationships - optional implementation."""
        return iter([])
    
    def extract_all_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract all relationships using implemented methods."""
        # Yield from all relationship extraction methods
        yield from self.extract_inheritance_relationships(context)
        yield from self.extract_call_relationships(context)
        yield from self.extract_import_relationships(context)
        yield from self.extract_composition_relationships(context)
        yield from self.extract_interface_relationships(context)