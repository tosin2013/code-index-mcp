"""
Relationship Information - New unified relationship data structures

This module defines the new relationship data structures for enhanced
symbol relationship analysis with complete SCIP standard support.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class RelationshipType(Enum):
    """Unified relationship types for all programming languages"""
    
    # Function relationships
    FUNCTION_CALL = "function_call"
    METHOD_CALL = "method_call"
    
    # Type relationships
    INHERITANCE = "inheritance"
    INTERFACE_IMPLEMENTATION = "interface_implementation"
    TYPE_REFERENCE = "type_reference"
    
    # Variable relationships
    VARIABLE_REFERENCE = "variable_reference"
    VARIABLE_ASSIGNMENT = "variable_assignment"
    
    # Module relationships
    MODULE_IMPORT = "module_import"
    MODULE_EXPORT = "module_export"
    
    # Generic relationships (fallback)
    REFERENCE = "reference"
    DEFINITION = "definition"


@dataclass
class RelationshipInfo:
    """Complete information about a single relationship"""
    
    target: str                           # Target symbol name
    target_symbol_id: str                # Complete SCIP symbol ID
    line: int                            # Line where relationship occurs
    column: int                          # Column where relationship occurs
    relationship_type: RelationshipType  # Type of relationship
    source: Optional[str] = None         # Source symbol name (for reverse relationships)
    source_symbol_id: Optional[str] = None  # Source symbol ID (for reverse relationships)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON output"""
        result = {
            "target": self.target,
            "target_symbol_id": self.target_symbol_id,
            "line": self.line,
            "column": self.column,
            "relationship_type": self.relationship_type.value
        }
        
        if self.source:
            result["source"] = self.source
        if self.source_symbol_id:
            result["source_symbol_id"] = self.source_symbol_id
            
        return result


@dataclass
class SymbolRelationships:
    """Container for all relationships of a symbol"""
    
    # Active relationships (this symbol to others)
    calls: List[RelationshipInfo] = field(default_factory=list)
    inherits_from: List[RelationshipInfo] = field(default_factory=list)
    implements: List[RelationshipInfo] = field(default_factory=list)
    references: List[RelationshipInfo] = field(default_factory=list)
    
    # Passive relationships (others to this symbol)
    called_by: List[RelationshipInfo] = field(default_factory=list)
    inherited_by: List[RelationshipInfo] = field(default_factory=list)
    implemented_by: List[RelationshipInfo] = field(default_factory=list)
    referenced_by: List[RelationshipInfo] = field(default_factory=list)
    
    def add_relationship(self, relationship: RelationshipInfo, is_reverse: bool = False):
        """Add a relationship to the appropriate category"""
        rel_type = relationship.relationship_type
        
        if is_reverse:
            # This is a reverse relationship (others -> this symbol)
            if rel_type in [RelationshipType.FUNCTION_CALL, RelationshipType.METHOD_CALL]:
                self.called_by.append(relationship)
            elif rel_type == RelationshipType.INHERITANCE:
                self.inherited_by.append(relationship)
            elif rel_type == RelationshipType.INTERFACE_IMPLEMENTATION:
                self.implemented_by.append(relationship)
            else:
                self.referenced_by.append(relationship)
        else:
            # This is a forward relationship (this symbol -> others)
            if rel_type in [RelationshipType.FUNCTION_CALL, RelationshipType.METHOD_CALL]:
                self.calls.append(relationship)
            elif rel_type == RelationshipType.INHERITANCE:
                self.inherits_from.append(relationship)
            elif rel_type == RelationshipType.INTERFACE_IMPLEMENTATION:
                self.implements.append(relationship)
            else:
                self.references.append(relationship)
    
    def get_total_count(self) -> int:
        """Get total number of relationships"""
        return (len(self.calls) + len(self.called_by) + 
                len(self.inherits_from) + len(self.inherited_by) +
                len(self.implements) + len(self.implemented_by) +
                len(self.references) + len(self.referenced_by))
    
    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Convert to dictionary format for JSON output"""
        result = {}
        
        # Only include non-empty relationship categories
        if self.calls:
            result["calls"] = [rel.to_dict() for rel in self.calls]
        if self.called_by:
            result["called_by"] = [rel.to_dict() for rel in self.called_by]
        if self.inherits_from:
            result["inherits_from"] = [rel.to_dict() for rel in self.inherits_from]
        if self.inherited_by:
            result["inherited_by"] = [rel.to_dict() for rel in self.inherited_by]
        if self.implements:
            result["implements"] = [rel.to_dict() for rel in self.implements]
        if self.implemented_by:
            result["implemented_by"] = [rel.to_dict() for rel in self.implemented_by]
        if self.references:
            result["references"] = [rel.to_dict() for rel in self.references]
        if self.referenced_by:
            result["referenced_by"] = [rel.to_dict() for rel in self.referenced_by]
            
        return result


@dataclass
class RelationshipsSummary:
    """Summary statistics for all relationships in a file"""
    
    total_relationships: int
    by_type: Dict[str, int]
    cross_file_relationships: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON output"""
        return {
            "total_relationships": self.total_relationships,
            "by_type": self.by_type,
            "cross_file_relationships": self.cross_file_relationships
        }


class SCIPRelationshipReader:
    """Reads and parses relationships from SCIP index"""
    
    def __init__(self):
        """Initialize the relationship reader"""
        pass
    
    def extract_relationships_from_document(self, document) -> Dict[str, SymbolRelationships]:
        """
        Extract all relationships from a SCIP document
        
        Args:
            document: SCIP document containing symbols and relationships
            
        Returns:
            Dictionary mapping symbol_id -> SymbolRelationships
        """
        all_relationships = {}
        
        # Process each symbol in the document
        for symbol_info in document.symbols:
            symbol_id = symbol_info.symbol
            symbol_name = symbol_info.display_name
            
            if not symbol_info.relationships:
                continue
                
            # Create relationships container for this symbol
            symbol_rels = SymbolRelationships()
            
            # Process each relationship
            for scip_relationship in symbol_info.relationships:
                rel_info = self._parse_scip_relationship(
                    scip_relationship, symbol_name, symbol_id, document
                )
                if rel_info:
                    symbol_rels.add_relationship(rel_info)
            
            if symbol_rels.get_total_count() > 0:
                all_relationships[symbol_id] = symbol_rels
        
        # Build reverse relationships
        self._build_reverse_relationships(all_relationships, document)
        
        return all_relationships
    
    def _parse_scip_relationship(self, scip_relationship, source_name: str, 
                                source_symbol_id: str, document) -> Optional[RelationshipInfo]:
        """
        Parse a single SCIP relationship into RelationshipInfo
        
        Args:
            scip_relationship: SCIP Relationship object
            source_name: Name of the source symbol
            source_symbol_id: SCIP ID of the source symbol
            document: SCIP document for context
            
        Returns:
            RelationshipInfo object or None if parsing fails
        """
        target_symbol_id = scip_relationship.symbol
        
        # Extract target symbol name from symbol ID
        target_name = self._extract_symbol_name(target_symbol_id)
        
        # Determine relationship type from SCIP flags
        rel_type = self._determine_relationship_type(scip_relationship, target_symbol_id)
        
        # Find the location where this relationship occurs
        line, column = self._find_relationship_location(
            source_symbol_id, target_symbol_id, document
        )
        
        return RelationshipInfo(
            target=target_name,
            target_symbol_id=target_symbol_id,
            line=line,
            column=column,
            relationship_type=rel_type
        )
    
    def _determine_relationship_type(self, scip_relationship, target_symbol_id: str) -> RelationshipType:
        """Determine the relationship type from SCIP flags and symbol ID"""
        
        # Check SCIP relationship flags
        if scip_relationship.is_implementation:
            return RelationshipType.INTERFACE_IMPLEMENTATION
        elif scip_relationship.is_type_definition:
            return RelationshipType.TYPE_REFERENCE
        elif scip_relationship.is_definition:
            return RelationshipType.DEFINITION
        elif scip_relationship.is_reference:
            # Need to determine if it's inheritance, call, or reference
            if target_symbol_id.endswith("#"):
                # Class symbol - could be inheritance or type reference
                return RelationshipType.INHERITANCE  # Assume inheritance for now
            elif target_symbol_id.endswith("()."):
                # Function symbol - function call
                return RelationshipType.FUNCTION_CALL
            else:
                # Generic reference
                return RelationshipType.REFERENCE
        else:
            # Fallback
            return RelationshipType.REFERENCE
    
    def _extract_symbol_name(self, symbol_id: str) -> str:
        """Extract the symbol name from SCIP symbol ID"""
        try:
            # SCIP symbol format: scip-<language> <manager> <package> <file_path>/<symbol_path>
            if "/" in symbol_id:
                symbol_part = symbol_id.split("/")[-1]
                # Remove descriptor suffix (like #, ()., etc.)
                if symbol_part.endswith("#"):
                    return symbol_part[:-1]
                elif symbol_part.endswith("()."):
                    return symbol_part[:-3]
                else:
                    return symbol_part
            return symbol_id
        except:
            return symbol_id
    
    def _find_relationship_location(self, source_symbol_id: str, target_symbol_id: str, 
                                  document) -> tuple[int, int]:
        """Find the line and column where the relationship occurs"""
        
        # Look for occurrences that reference the target symbol
        for occurrence in document.occurrences:
            if occurrence.symbol == target_symbol_id:
                if hasattr(occurrence, 'range') and occurrence.range:
                    start = occurrence.range.start
                    if len(start) >= 2:
                        return start[0] + 1, start[1] + 1  # Convert to 1-based indexing
        
        # Fallback: look for the source symbol definition
        for occurrence in document.occurrences:
            if occurrence.symbol == source_symbol_id:
                if hasattr(occurrence, 'range') and occurrence.range:
                    start = occurrence.range.start
                    if len(start) >= 2:
                        return start[0] + 1, start[1] + 1  # Convert to 1-based indexing
        
        # Default fallback
        return 0, 0
    
    def _build_reverse_relationships(self, all_relationships: Dict[str, SymbolRelationships], 
                                   document):
        """Build reverse relationships (called_by, inherited_by, etc.)"""
        
        # Create a mapping of all symbols for reverse lookup
        symbol_names = {}
        for symbol_info in document.symbols:
            symbol_names[symbol_info.symbol] = symbol_info.display_name
        
        # Build reverse relationships (iterate over a copy to avoid modification during iteration)
        for source_symbol_id, source_rels in list(all_relationships.items()):
            source_name = symbol_names.get(source_symbol_id, "unknown")
            
            # Process each forward relationship to create reverse relationships
            for rel in source_rels.calls:
                self._add_reverse_relationship(
                    all_relationships, rel.target_symbol_id, rel, source_name, source_symbol_id
                )
            
            for rel in source_rels.inherits_from:
                self._add_reverse_relationship(
                    all_relationships, rel.target_symbol_id, rel, source_name, source_symbol_id
                )
            
            for rel in source_rels.implements:
                self._add_reverse_relationship(
                    all_relationships, rel.target_symbol_id, rel, source_name, source_symbol_id
                )
            
            for rel in source_rels.references:
                self._add_reverse_relationship(
                    all_relationships, rel.target_symbol_id, rel, source_name, source_symbol_id
                )
    
    def _add_reverse_relationship(self, all_relationships: Dict[str, SymbolRelationships],
                                target_symbol_id: str, original_rel: RelationshipInfo,
                                source_name: str, source_symbol_id: str):
        """Add a reverse relationship to the target symbol"""
        
        if target_symbol_id not in all_relationships:
            all_relationships[target_symbol_id] = SymbolRelationships()
        
        # Create reverse relationship
        reverse_rel = RelationshipInfo(
            target=source_name,
            target_symbol_id=source_symbol_id,
            line=original_rel.line,
            column=original_rel.column,
            relationship_type=original_rel.relationship_type,
            source=original_rel.target,
            source_symbol_id=original_rel.target_symbol_id
        )
        
        # Add as reverse relationship
        all_relationships[target_symbol_id].add_relationship(reverse_rel, is_reverse=True)