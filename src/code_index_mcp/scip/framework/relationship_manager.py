"""SCIP Relationship Manager - Comprehensive symbol relationship extraction and management."""

import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass

from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class RelationshipType(Enum):
    """Standard relationship types for symbol analysis."""
    INHERITANCE = "inheritance"
    IMPLEMENTATION = "implementation"
    COMPOSITION = "composition"
    DEPENDENCY = "dependency"
    CALL = "call"
    IMPORT = "import"
    REFERENCE = "reference"
    TYPE_DEFINITION = "type_definition"
    OVERRIDE = "override"
    INSTANTIATION = "instantiation"


@dataclass(frozen=True)
class SymbolRelationship:
    """Immutable symbol relationship representation."""
    source_symbol: str
    target_symbol: str
    relationship_type: RelationshipType
    confidence: float = 1.0
    source_location: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None


class SCIPRelationshipManager:
    """
    Comprehensive relationship manager for SCIP symbol relationships.
    
    This manager handles the extraction, validation, and conversion of symbol
    relationships to SCIP format, ensuring complete relationship networks.
    """
    
    def __init__(self):
        """Initialize the relationship manager."""
        self._relationships: Dict[str, List[SymbolRelationship]] = {}
        self._reverse_relationships: Dict[str, List[SymbolRelationship]] = {}
        self._relationship_count_by_type: Dict[RelationshipType, int] = {}
        
        # Initialize counters
        for rel_type in RelationshipType:
            self._relationship_count_by_type[rel_type] = 0
            
        logger.debug("Initialized SCIP Relationship Manager")
    
    def add_relationship(self, 
                        source_symbol: str, 
                        target_symbol: str, 
                        relationship_type: RelationshipType,
                        confidence: float = 1.0,
                        source_location: Optional[str] = None,
                        additional_info: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a symbol relationship to the manager.
        
        Args:
            source_symbol: Source symbol ID
            target_symbol: Target symbol ID  
            relationship_type: Type of relationship
            confidence: Confidence level (0.0-1.0)
            source_location: Location where relationship was detected
            additional_info: Additional metadata about the relationship
        """
        if not self._validate_symbol_id(source_symbol):
            logger.warning(f"Invalid source symbol ID: {source_symbol}")
            return
            
        if not self._validate_symbol_id(target_symbol):
            logger.warning(f"Invalid target symbol ID: {target_symbol}")
            return
        
        if not 0.0 <= confidence <= 1.0:
            logger.warning(f"Invalid confidence value: {confidence}, setting to 1.0")
            confidence = 1.0
        
        relationship = SymbolRelationship(
            source_symbol=source_symbol,
            target_symbol=target_symbol,
            relationship_type=relationship_type,
            confidence=confidence,
            source_location=source_location,
            additional_info=additional_info or {}
        )
        
        # Add to forward relationships
        if source_symbol not in self._relationships:
            self._relationships[source_symbol] = []
        
        # Check for duplicates
        existing = [r for r in self._relationships[source_symbol] 
                   if r.target_symbol == target_symbol and r.relationship_type == relationship_type]
        if existing:
            logger.debug(f"Duplicate relationship ignored: {source_symbol} -> {target_symbol} ({relationship_type})")
            return
        
        self._relationships[source_symbol].append(relationship)
        
        # Add to reverse relationships
        if target_symbol not in self._reverse_relationships:
            self._reverse_relationships[target_symbol] = []
        self._reverse_relationships[target_symbol].append(relationship)
        
        # Update counters
        self._relationship_count_by_type[relationship_type] += 1
        
        logger.debug(f"Added relationship: {source_symbol} --{relationship_type.value}--> {target_symbol}")
    
    def get_relationships(self, symbol_id: str) -> List[SymbolRelationship]:
        """
        Get all outgoing relationships for a symbol.
        
        Args:
            symbol_id: Symbol ID to get relationships for
            
        Returns:
            List of relationships where symbol is the source
        """
        return self._relationships.get(symbol_id, [])
    
    def get_reverse_relationships(self, symbol_id: str) -> List[SymbolRelationship]:
        """
        Get all incoming relationships for a symbol.
        
        Args:
            symbol_id: Symbol ID to get incoming relationships for
            
        Returns:
            List of relationships where symbol is the target
        """
        return self._reverse_relationships.get(symbol_id, [])
    
    def get_relationships_by_type(self, 
                                 symbol_id: str, 
                                 relationship_type: RelationshipType) -> List[SymbolRelationship]:
        """
        Get relationships of a specific type for a symbol.
        
        Args:
            symbol_id: Symbol ID
            relationship_type: Type of relationship to filter by
            
        Returns:
            List of relationships of the specified type
        """
        all_relationships = self.get_relationships(symbol_id)
        return [r for r in all_relationships if r.relationship_type == relationship_type]
    
    def has_relationship(self, 
                        source_symbol: str, 
                        target_symbol: str, 
                        relationship_type: Optional[RelationshipType] = None) -> bool:
        """
        Check if a relationship exists between two symbols.
        
        Args:
            source_symbol: Source symbol ID
            target_symbol: Target symbol ID
            relationship_type: Optional specific relationship type to check
            
        Returns:
            True if relationship exists
        """
        relationships = self.get_relationships(source_symbol)
        
        for rel in relationships:
            if rel.target_symbol == target_symbol:
                if relationship_type is None or rel.relationship_type == relationship_type:
                    return True
        
        return False
    
    def get_inheritance_chain(self, symbol_id: str) -> List[str]:
        """
        Get the complete inheritance chain for a symbol.
        
        Args:
            symbol_id: Symbol ID to get inheritance chain for
            
        Returns:
            List of symbol IDs in inheritance order (immediate parent first)
        """
        chain = []
        visited = set()
        current = symbol_id
        
        while current and current not in visited:
            visited.add(current)
            inheritance_rels = self.get_relationships_by_type(current, RelationshipType.INHERITANCE)
            
            if inheritance_rels:
                # Take the first inheritance relationship
                parent = inheritance_rels[0].target_symbol
                chain.append(parent)
                current = parent
            else:
                break
        
        return chain
    
    def get_call_graph(self, symbol_id: str, max_depth: int = 5) -> Dict[str, List[str]]:
        """
        Get the call graph for a symbol (what it calls).
        
        Args:
            symbol_id: Symbol ID to get call graph for
            max_depth: Maximum depth to traverse
            
        Returns:
            Dictionary mapping symbol IDs to their called functions
        """
        call_graph = {}
        visited = set()
        
        def traverse(current_symbol: str, depth: int):
            if depth >= max_depth or current_symbol in visited:
                return
            
            visited.add(current_symbol)
            call_relationships = self.get_relationships_by_type(current_symbol, RelationshipType.CALL)
            
            if call_relationships:
                called_symbols = [r.target_symbol for r in call_relationships]
                call_graph[current_symbol] = called_symbols
                
                # Recursively traverse called functions
                for called_symbol in called_symbols:
                    traverse(called_symbol, depth + 1)
        
        traverse(symbol_id, 0)
        return call_graph
    
    def get_dependency_graph(self, symbol_id: str) -> Dict[str, List[str]]:
        """
        Get the dependency graph for a symbol.
        
        Args:
            symbol_id: Symbol ID to get dependencies for
            
        Returns:
            Dictionary mapping symbol to its dependencies
        """
        dependency_rels = self.get_relationships_by_type(symbol_id, RelationshipType.DEPENDENCY)
        import_rels = self.get_relationships_by_type(symbol_id, RelationshipType.IMPORT)
        
        dependencies = []
        dependencies.extend([r.target_symbol for r in dependency_rels])
        dependencies.extend([r.target_symbol for r in import_rels])
        
        return {symbol_id: dependencies} if dependencies else {}
    
    def convert_to_scip_relationships(self, symbol_id: str) -> List[scip_pb2.Relationship]:
        """
        Convert symbol relationships to SCIP Relationship objects.
        
        Args:
            symbol_id: Symbol ID to convert relationships for
            
        Returns:
            List of SCIP Relationship objects
        """
        relationships = self.get_relationships(symbol_id)
        scip_relationships = []
        
        for rel in relationships:
            scip_rel = scip_pb2.Relationship()
            scip_rel.symbol = rel.target_symbol
            
            # Map relationship types to SCIP boolean flags
            if rel.relationship_type == RelationshipType.REFERENCE:
                scip_rel.is_reference = True
            elif rel.relationship_type == RelationshipType.IMPLEMENTATION:
                scip_rel.is_implementation = True
            elif rel.relationship_type == RelationshipType.TYPE_DEFINITION:
                scip_rel.is_type_definition = True
            elif rel.relationship_type == RelationshipType.INHERITANCE:
                scip_rel.is_definition = True  # Inheritance implies definition relationship
            else:
                # For other relationship types, mark as reference
                scip_rel.is_reference = True
            
            scip_relationships.append(scip_rel)
        
        return scip_relationships
    
    def add_inheritance_relationship(self, child_symbol: str, parent_symbol: str, 
                                   confidence: float = 1.0, source_location: Optional[str] = None):
        """Add an inheritance relationship (child inherits from parent)."""
        self.add_relationship(
            child_symbol, parent_symbol, RelationshipType.INHERITANCE,
            confidence=confidence, source_location=source_location,
            additional_info={"relationship_description": f"{child_symbol} inherits from {parent_symbol}"}
        )
    
    def add_call_relationship(self, caller_symbol: str, callee_symbol: str,
                             confidence: float = 1.0, source_location: Optional[str] = None):
        """Add a call relationship (caller calls callee)."""
        self.add_relationship(
            caller_symbol, callee_symbol, RelationshipType.CALL,
            confidence=confidence, source_location=source_location,
            additional_info={"relationship_description": f"{caller_symbol} calls {callee_symbol}"}
        )
    
    def add_import_relationship(self, importer_symbol: str, imported_symbol: str,
                               confidence: float = 1.0, source_location: Optional[str] = None):
        """Add an import relationship (importer imports imported)."""
        self.add_relationship(
            importer_symbol, imported_symbol, RelationshipType.IMPORT,
            confidence=confidence, source_location=source_location,
            additional_info={"relationship_description": f"{importer_symbol} imports {imported_symbol}"}
        )
    
    def add_composition_relationship(self, composite_symbol: str, component_symbol: str,
                                   confidence: float = 1.0, source_location: Optional[str] = None):
        """Add a composition relationship (composite contains component)."""
        self.add_relationship(
            composite_symbol, component_symbol, RelationshipType.COMPOSITION,
            confidence=confidence, source_location=source_location,
            additional_info={"relationship_description": f"{composite_symbol} contains {component_symbol}"}
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about relationships."""
        total_symbols_with_relationships = len(self._relationships)
        total_relationships = sum(len(rels) for rels in self._relationships.values())
        
        return {
            "total_symbols_with_relationships": total_symbols_with_relationships,
            "total_relationships": total_relationships,
            "relationships_by_type": dict(self._relationship_count_by_type),
            "average_relationships_per_symbol": (
                total_relationships / total_symbols_with_relationships 
                if total_symbols_with_relationships > 0 else 0
            ),
            "symbols_with_incoming_relationships": len(self._reverse_relationships)
        }
    
    def validate_relationship_integrity(self) -> List[str]:
        """
        Validate the integrity of all relationships.
        
        Returns:
            List of validation warnings/errors
        """
        issues = []
        
        # Check for circular inheritance
        for symbol_id in self._relationships:
            chain = self.get_inheritance_chain(symbol_id)
            if symbol_id in chain:
                issues.append(f"Circular inheritance detected for {symbol_id}")
        
        # Check for self-references (except for specific types)
        for symbol_id, relationships in self._relationships.items():
            for rel in relationships:
                if rel.target_symbol == symbol_id and rel.relationship_type not in [
                    RelationshipType.REFERENCE, RelationshipType.CALL
                ]:
                    issues.append(f"Self-reference detected: {symbol_id} -> {rel.relationship_type.value}")
        
        # Check confidence levels
        for relationships in self._relationships.values():
            for rel in relationships:
                if rel.confidence < 0.5:
                    issues.append(f"Low confidence relationship: {rel.source_symbol} -> {rel.target_symbol} ({rel.confidence})")
        
        return issues
    
    def _validate_symbol_id(self, symbol_id: str) -> bool:
        """Validate symbol ID format."""
        return bool(symbol_id and isinstance(symbol_id, str) and len(symbol_id.strip()) > 0)
    
    def clear(self):
        """Clear all relationships."""
        self._relationships.clear()
        self._reverse_relationships.clear()
        for rel_type in RelationshipType:
            self._relationship_count_by_type[rel_type] = 0
        logger.debug("Cleared all relationships")
    
    def export_relationships(self) -> Dict[str, Any]:
        """Export all relationships for serialization."""
        exported = {}
        for symbol_id, relationships in self._relationships.items():
            exported[symbol_id] = []
            for rel in relationships:
                exported[symbol_id].append({
                    "target_symbol": rel.target_symbol,
                    "relationship_type": rel.relationship_type.value,
                    "confidence": rel.confidence,
                    "source_location": rel.source_location,
                    "additional_info": rel.additional_info
                })
        return exported