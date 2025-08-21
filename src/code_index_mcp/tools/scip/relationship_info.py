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
    relationship_type: RelationshipType  # Type of relationship
    source: Optional[str] = None         # Source symbol name (for reverse relationships)
    source_symbol_id: Optional[str] = None  # Source symbol ID (for reverse relationships)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON output"""
        result = {
            "target": self.target,
            "target_symbol_id": self.target_symbol_id,
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
        """Add a relationship to the appropriate category with deduplication"""
        rel_type = relationship.relationship_type

        if is_reverse:
            # This is a reverse relationship (others -> this symbol)
            if rel_type in [RelationshipType.FUNCTION_CALL, RelationshipType.METHOD_CALL]:
                self._add_unique_relationship(self.called_by, relationship)
            elif rel_type == RelationshipType.INHERITANCE:
                self._add_unique_relationship(self.inherited_by, relationship)
            elif rel_type == RelationshipType.INTERFACE_IMPLEMENTATION:
                self._add_unique_relationship(self.implemented_by, relationship)
            else:
                self._add_unique_relationship(self.referenced_by, relationship)
        else:
            # This is a forward relationship (this symbol -> others)
            if rel_type in [RelationshipType.FUNCTION_CALL, RelationshipType.METHOD_CALL]:
                self._add_unique_relationship(self.calls, relationship)
            elif rel_type == RelationshipType.INHERITANCE:
                self._add_unique_relationship(self.inherits_from, relationship)
            elif rel_type == RelationshipType.INTERFACE_IMPLEMENTATION:
                self._add_unique_relationship(self.implements, relationship)
            else:
                self._add_unique_relationship(self.references, relationship)

    def _add_unique_relationship(self, relationship_list: List[RelationshipInfo], new_relationship: RelationshipInfo):
        """Add relationship only if it doesn't already exist"""
        for existing in relationship_list:
            if (existing.target_symbol_id == new_relationship.target_symbol_id and
                existing.relationship_type == new_relationship.relationship_type):
                return  # Skip duplicate
        relationship_list.append(new_relationship)

    def get_total_count(self) -> int:
        """Get total number of relationships"""
        return (len(self.calls) + len(self.called_by) +
                len(self.inherits_from) + len(self.inherited_by) +
                len(self.implements) + len(self.implemented_by) +
                len(self.references) + len(self.referenced_by))

    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Convert to dictionary format for JSON output - simplified for token efficiency"""
        result = {}

        # Only include called_by relationships
        if self.called_by:
            result["called_by"] = [rel.to_dict() for rel in self.called_by]

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
        self._symbol_kinds = {}  # symbol_id -> SymbolKind mapping

    def extract_relationships_from_document(self, document, scip_index=None) -> Dict[str, SymbolRelationships]:
        """
        Enhanced relationship extraction from both symbol.relationships and occurrences.

        This dual-source approach dramatically improves relationship coverage:
        - symbol.relationships: Explicit relationships (inheritance, implements)
        - occurrences: Implicit relationships (function calls, references)
        - Cross-document analysis: Enables called_by relationships across files

        Args:
            document: SCIP document containing symbols and relationships
            scip_index: Optional full SCIP index for cross-document analysis

        Returns:
            Dictionary mapping symbol_id -> SymbolRelationships
        """
        all_relationships = {}

        # Step 0: Build global symbol registry for cross-document analysis
        self._build_global_symbol_registry(document, scip_index)

        # Step 1: Extract from explicit symbol relationships (existing logic)
        self._extract_from_symbol_relationships(document, all_relationships)

        # Step 2: Extract from occurrences with cross-document support
        self._extract_from_occurrences(document, all_relationships, scip_index)

        # Step 3: Build reverse relationships with cross-document support
        self._build_reverse_relationships(all_relationships, document, scip_index)

        return all_relationships

    def _build_global_symbol_registry(self, document, scip_index=None):
        """Build comprehensive symbol registry supporting cross-document analysis."""
        # Clear previous state
        self._symbol_kinds.clear()
        
        # Build registry from current document
        self._add_document_to_registry(document)
        
        # If full index provided, build global registry for cross-document analysis
        if scip_index:
            for doc in scip_index.documents:
                if doc != document:  # Avoid duplicate processing
                    self._add_document_to_registry(doc)
    
    def _add_document_to_registry(self, document):
        """Add document symbols to the global registry."""
        for symbol_info in document.symbols:
            symbol_id = symbol_info.symbol
            self._symbol_kinds[symbol_id] = symbol_info.kind
            
            # For function symbols, also map the occurrence format (without ().suffix)
            if symbol_info.kind == 11:  # SymbolKind.Function
                if symbol_id.endswith('().'):
                    base_id = symbol_id[:-3]  # Remove '().'
                    self._symbol_kinds[base_id] = symbol_info.kind

    def _extract_from_symbol_relationships(self, document, all_relationships: Dict[str, SymbolRelationships]):
        """
        Extract relationships from explicit symbol.relationships (original logic).

        Args:
            document: SCIP document
            all_relationships: Dictionary to populate with relationships
        """
        for symbol_info in document.symbols:
            symbol_id = symbol_info.symbol
            symbol_name = symbol_info.display_name

            if not symbol_info.relationships:
                continue

            # Create or get existing relationships container
            if symbol_id not in all_relationships:
                all_relationships[symbol_id] = SymbolRelationships()

            symbol_rels = all_relationships[symbol_id]

            # Process each explicit relationship
            for scip_relationship in symbol_info.relationships:
                rel_info = self._parse_scip_relationship(
                    scip_relationship, symbol_name, symbol_id, document
                )
                if rel_info:
                    symbol_rels.add_relationship(rel_info)

    def _extract_from_occurrences(self, document, all_relationships: Dict[str, SymbolRelationships], scip_index=None):
        """
        Extract relationships from document occurrences (major new functionality).

        This extracts the majority of missing relationships, especially function calls.

        Args:
            document: SCIP document containing occurrences
            all_relationships: Dictionary to populate with relationships
        """
        # Process each occurrence to find relationships
        for occurrence in document.occurrences:
            try:
                # Skip if no symbol or range information
                if not occurrence.symbol or not hasattr(occurrence, 'range'):
                    continue

                target_symbol_id = occurrence.symbol
                roles = getattr(occurrence, 'symbol_roles', 0)

                # Skip definitions and imports - these aren't "uses" of other symbols
                if roles & 1:  # Definition role - skip
                    continue
                if roles & 2:  # Import role - skip
                    continue

                # Find which symbol contains this occurrence (context analysis)
                source_symbol_id = self._find_containing_symbol(occurrence, document)
                if not source_symbol_id or source_symbol_id == target_symbol_id:
                    continue  # Self-reference or no container found

                # Determine relationship type based on roles and symbol characteristics
                rel_type = self._determine_occurrence_relationship_type(roles, target_symbol_id, source_symbol_id)
                if not rel_type:
                    continue


                # Create relationship info
                rel_info = RelationshipInfo(
                    target=self._extract_symbol_name(target_symbol_id),
                    target_symbol_id=target_symbol_id,
                    relationship_type=rel_type
                )

                # Add to source symbol's relationships
                if source_symbol_id not in all_relationships:
                    all_relationships[source_symbol_id] = SymbolRelationships()

                all_relationships[source_symbol_id].add_relationship(rel_info)

                # For function calls, also create reverse "called_by" relationship
                # This is the key to cross-document relationship building
                if (rel_type == RelationshipType.FUNCTION_CALL or rel_type == RelationshipType.METHOD_CALL):
                    self._add_cross_document_called_by(
                        all_relationships, target_symbol_id, source_symbol_id, scip_index
                    )

            except Exception as e:
                # Log but continue processing other occurrences
                continue

    def _find_containing_symbol(self, occurrence, document) -> Optional[str]:
        """
        Find which symbol definition contains this occurrence.

        This is crucial for establishing "X calls Y" relationships.
        """
        if not hasattr(occurrence, 'range') or not occurrence.range:
            return None

        try:
            occ_line = occurrence.range.start[0] if occurrence.range.start else 0
        except (AttributeError, IndexError):
            return None

        # Find symbol definitions that could contain this occurrence
        containing_symbols = []

        for other_occurrence in document.occurrences:
            try:
                # Only consider definitions
                roles = getattr(other_occurrence, 'symbol_roles', 0)
                if not (roles & 1):  # Must be definition
                    continue

                if not hasattr(other_occurrence, 'range') or not other_occurrence.range:
                    continue

                def_line = other_occurrence.range.start[0] if other_occurrence.range.start else 0

                # Simple heuristic: find the closest preceding definition
                if def_line <= occ_line:
                    containing_symbols.append((other_occurrence.symbol, def_line))

            except Exception:
                continue

        # Return the symbol with the closest line number to the occurrence
        if containing_symbols:
            containing_symbols.sort(key=lambda x: x[1], reverse=True)  # Closest first
            return containing_symbols[0][0]

        # If no containing symbol found, use file-level context for cross-file relationships
        # This handles cases like run.py calling server.py functions
        if hasattr(document, 'relative_path') and document.relative_path:
            file_name = document.relative_path.replace('\\', '/').split('/')[-1]
            return f"local file:{file_name}"

        return None

    def _determine_occurrence_relationship_type(self, roles: int, target_symbol_id: str,
                                              source_symbol_id: str) -> Optional[RelationshipType]:
        """
        Determine relationship type from occurrence roles and symbol characteristics.

        Args:
            roles: SCIP symbol roles (bit flags)
            target_symbol_id: Symbol being referenced
            source_symbol_id: Symbol doing the referencing

        Returns:
            RelationshipType or None if not a relevant relationship
        """
        # Write access (assignment/modification)
        if roles & 4:  # Write role
            return RelationshipType.VARIABLE_ASSIGNMENT

        # Read access - determine specific type
        if roles == 0 or roles & 8:  # Read role or unspecified
            if self._is_function_symbol(target_symbol_id):
                return RelationshipType.FUNCTION_CALL if not self._is_method_symbol(target_symbol_id) else RelationshipType.METHOD_CALL
            elif self._is_class_symbol(target_symbol_id):
                return RelationshipType.TYPE_REFERENCE
            else:
                return RelationshipType.VARIABLE_REFERENCE

        # Type role
        if roles & 64:  # Type role
            return RelationshipType.TYPE_REFERENCE

        # Default to generic reference
        return RelationshipType.REFERENCE

    def _is_function_symbol(self, symbol_id: str) -> bool:
        """Check if symbol represents a function using SymbolKind."""
        # Check our symbol kinds cache
        symbol_kind = self._symbol_kinds.get(symbol_id)
        return symbol_kind == 11  # SymbolKind.Function

    def _is_method_symbol(self, symbol_id: str) -> bool:
        """Check if symbol represents a method (function within a class)."""
        return '#' in symbol_id and self._is_function_symbol(symbol_id)

    def _is_class_symbol(self, symbol_id: str) -> bool:
        """Check if symbol represents a class using SymbolKind."""
        # Check our symbol kinds cache
        symbol_kind = self._symbol_kinds.get(symbol_id)
        return symbol_kind == 3  # SymbolKind.Class


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


        return RelationshipInfo(
            target=target_name,
            target_symbol_id=target_symbol_id,
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
            # Handle file-level symbols
            if symbol_id.startswith("local file:"):
                return symbol_id[11:]  # Remove "local file:" prefix
            
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


    def _add_cross_document_called_by(self, all_relationships: Dict[str, SymbolRelationships], 
                                    target_symbol_id: str, source_symbol_id: str,
                                    scip_index=None):
        """
        Add cross-document called_by relationship.
        
        This creates the reverse relationship that enables cross-file function call tracking.
        For example, when run.py calls server.main(), we add main as called_by run.
        
        Args:
            all_relationships: Current document's relationships
            target_symbol_id: Function being called (e.g., 'local main')
            source_symbol_id: Function making the call (e.g., 'local <module>')
            scip_index: Full SCIP index for cross-document lookup
        """
        # Find the definition format symbol ID for the target function
        definition_symbol_id = self._find_definition_symbol_id(target_symbol_id, scip_index)
        if not definition_symbol_id:
            return
            
        # Create called_by relationship
        source_name = self._extract_symbol_name(source_symbol_id)
        called_by_rel = RelationshipInfo(
            target=source_name,
            target_symbol_id=source_symbol_id,
            relationship_type=RelationshipType.FUNCTION_CALL
        )
        
        # Add to target function's called_by relationships (with deduplication)
        if definition_symbol_id not in all_relationships:
            all_relationships[definition_symbol_id] = SymbolRelationships()
        
        # Check if this called_by relationship already exists to avoid duplicates
        existing_called_by = all_relationships[definition_symbol_id].called_by
        for existing_rel in existing_called_by:
            if (existing_rel.target_symbol_id == called_by_rel.target_symbol_id and
                existing_rel.relationship_type == called_by_rel.relationship_type):
                return  # Skip duplicate
            
        all_relationships[definition_symbol_id].called_by.append(called_by_rel)
        
    def _find_definition_symbol_id(self, occurrence_symbol_id: str, scip_index=None) -> Optional[str]:
        """
        Find the definition format symbol ID from occurrence format.
        
        SCIP uses different formats:
        - Occurrences: 'local main' 
        - Definitions: 'local main().'
        
        This method maps from occurrence to definition format using SymbolKind.
        """
        if not scip_index:
            return None
            
        # If already in definition format, return as-is
        if occurrence_symbol_id.endswith('().'):
            return occurrence_symbol_id
            
        # Search all documents for function symbol with this base name
        for doc in scip_index.documents:
            for symbol_info in doc.symbols:
                if symbol_info.kind == 11:  # SymbolKind.Function
                    symbol_id = symbol_info.symbol
                    if symbol_id.endswith('().'):
                        # Extract base name from definition format
                        base_name = symbol_id[:-3]  # Remove '().'
                        if base_name == occurrence_symbol_id:
                            return symbol_id
        
        return None

    def _build_reverse_relationships(self, all_relationships: Dict[str, SymbolRelationships],
                                   document, scip_index=None):
        """Build reverse relationships (called_by, inherited_by, etc.) with cross-document support"""

        # Create a comprehensive mapping of all symbols for reverse lookup
        symbol_names = {}
        
        # Add symbols from current document
        for symbol_info in document.symbols:
            symbol_names[symbol_info.symbol] = symbol_info.display_name
        
        # Add symbols from all other documents if full index provided
        if scip_index:
            for doc in scip_index.documents:
                if doc != document:  # Avoid duplicate processing
                    for symbol_info in doc.symbols:
                        if symbol_info.symbol not in symbol_names:  # Avoid overriding
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
            relationship_type=original_rel.relationship_type,
            source=original_rel.target,
            source_symbol_id=original_rel.target_symbol_id
        )

        # Add as reverse relationship
        all_relationships[target_symbol_id].add_relationship(reverse_rel, is_reverse=True)