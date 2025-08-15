"""Local Reference Resolver - Cross-file reference resolution within a project."""

import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

from ..proto import scip_pb2


logger = logging.getLogger(__name__)


@dataclass
class SymbolDefinition:
    """Information about a symbol definition."""
    symbol_id: str
    file_path: str
    definition_range: scip_pb2.Range
    symbol_kind: int
    display_name: str
    documentation: List[str]


@dataclass
class SymbolReference:
    """Information about a symbol reference."""
    symbol_id: str
    file_path: str
    reference_range: scip_pb2.Range
    context_scope: List[str]


@dataclass
class SymbolRelationship:
    """Information about a relationship between symbols."""
    source_symbol_id: str
    target_symbol_id: str
    relationship_type: str  # InternalRelationshipType enum value
    relationship_data: Dict[str, Any]  # Additional relationship metadata


class LocalReferenceResolver:
    """
    Resolves references within a local project.

    This class maintains a symbol table for all definitions in the project
    and helps resolve references to their definitions.
    """

    def __init__(self, project_path: str):
        """
        Initialize reference resolver for a project.

        Args:
            project_path: Absolute path to project root
        """
        self.project_path = Path(project_path).resolve()

        # Symbol tables
        self.symbol_definitions: Dict[str, SymbolDefinition] = {}
        self.symbol_references: Dict[str, List[SymbolReference]] = {}
        
        # Relationship storage
        self.symbol_relationships: Dict[str, List[SymbolRelationship]] = {}  # source_symbol_id -> relationships
        self.reverse_relationships: Dict[str, List[SymbolRelationship]] = {}  # target_symbol_id -> relationships

        # File-based indexes for faster lookup
        self.file_symbols: Dict[str, Set[str]] = {}  # file_path -> symbol_ids
        self.symbol_by_name: Dict[str, List[str]] = {}  # display_name -> symbol_ids

        logger.debug(f"LocalReferenceResolver initialized for project: {project_path}")

    def register_symbol_definition(self,
                                  symbol_id: str,
                                  file_path: str,
                                  definition_range: scip_pb2.Range,
                                  symbol_kind: int,
                                  display_name: str,
                                  documentation: List[str] = None) -> None:
        """
        Register a symbol definition.

        Args:
            symbol_id: SCIP symbol ID
            file_path: File path relative to project root
            definition_range: SCIP Range of definition
            symbol_kind: SCIP symbol kind
            display_name: Human-readable symbol name
            documentation: Optional documentation
        """
        definition = SymbolDefinition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=definition_range,
            symbol_kind=symbol_kind,
            display_name=display_name,
            documentation=documentation or []
        )

        self.symbol_definitions[symbol_id] = definition

        # Update file index
        if file_path not in self.file_symbols:
            self.file_symbols[file_path] = set()
        self.file_symbols[file_path].add(symbol_id)

        # Update name index
        if display_name not in self.symbol_by_name:
            self.symbol_by_name[display_name] = []
        if symbol_id not in self.symbol_by_name[display_name]:
            self.symbol_by_name[display_name].append(symbol_id)

        logger.debug(f"Registered symbol definition: {display_name} -> {symbol_id}")

    def register_symbol_reference(self,
                                 symbol_id: str,
                                 file_path: str,
                                 reference_range: scip_pb2.Range,
                                 context_scope: List[str] = None) -> None:
        """
        Register a symbol reference.

        Args:
            symbol_id: SCIP symbol ID being referenced
            file_path: File path where reference occurs
            reference_range: SCIP Range of reference
            context_scope: Scope context where reference occurs
        """
        reference = SymbolReference(
            symbol_id=symbol_id,
            file_path=file_path,
            reference_range=reference_range,
            context_scope=context_scope or []
        )

        if symbol_id not in self.symbol_references:
            self.symbol_references[symbol_id] = []
        self.symbol_references[symbol_id].append(reference)

        logger.debug(f"Registered symbol reference: {symbol_id} in {file_path}")

    def resolve_reference_by_name(self,
                                 symbol_name: str,
                                 context_file: str,
                                 context_scope: List[str] = None) -> Optional[str]:
        """
        Resolve a symbol reference by name to its definition symbol ID.

        Args:
            symbol_name: Name of symbol to resolve
            context_file: File where reference occurs
            context_scope: Scope context of reference

        Returns:
            Symbol ID of definition or None if not found
        """
        context_scope = context_scope or []

        # Look for exact name matches
        if symbol_name not in self.symbol_by_name:
            return None

        candidate_symbols = self.symbol_by_name[symbol_name]

        if len(candidate_symbols) == 1:
            return candidate_symbols[0]

        # Multiple candidates - use scope-based resolution
        return self._resolve_with_scope(candidate_symbols, context_file, context_scope)

    def get_symbol_definition(self, symbol_id: str) -> Optional[SymbolDefinition]:
        """
        Get symbol definition by ID.

        Args:
            symbol_id: SCIP symbol ID

        Returns:
            SymbolDefinition or None if not found
        """
        return self.symbol_definitions.get(symbol_id)

    def get_symbol_references(self, symbol_id: str) -> List[SymbolReference]:
        """
        Get all references to a symbol.

        Args:
            symbol_id: SCIP symbol ID

        Returns:
            List of SymbolReference objects
        """
        return self.symbol_references.get(symbol_id, [])

    def get_file_symbols(self, file_path: str) -> Set[str]:
        """
        Get all symbols defined in a file.

        Args:
            file_path: File path relative to project root

        Returns:
            Set of symbol IDs defined in the file
        """
        return self.file_symbols.get(file_path, set())

    def find_symbols_by_pattern(self, pattern: str) -> List[SymbolDefinition]:
        """
        Find symbols matching a pattern.

        Args:
            pattern: Search pattern (simple substring match)

        Returns:
            List of matching SymbolDefinition objects
        """
        matches = []
        pattern_lower = pattern.lower()

        for symbol_def in self.symbol_definitions.values():
            if (pattern_lower in symbol_def.display_name.lower() or
                pattern_lower in symbol_def.symbol_id.lower()):
                matches.append(symbol_def)

        return matches

    def get_project_statistics(self) -> Dict[str, int]:
        """
        Get statistics about the symbol table including relationships.

        Returns:
            Dictionary with statistics
        """
        total_references = sum(len(refs) for refs in self.symbol_references.values())
        total_relationships = sum(len(rels) for rels in self.symbol_relationships.values())

        return {
            'total_definitions': len(self.symbol_definitions),
            'total_references': total_references,
            'total_relationships': total_relationships,
            'files_with_symbols': len(self.file_symbols),
            'unique_symbol_names': len(self.symbol_by_name),
            'symbols_with_relationships': len(self.symbol_relationships)
        }

    def _resolve_with_scope(self,
                           candidate_symbols: List[str],
                           context_file: str,
                           context_scope: List[str]) -> Optional[str]:
        """
        Resolve symbol using scope-based heuristics.

        Args:
            candidate_symbols: List of candidate symbol IDs
            context_file: File where reference occurs
            context_scope: Scope context

        Returns:
            Best matching symbol ID or None
        """
        # Scoring system for symbol resolution
        scored_candidates = []

        for symbol_id in candidate_symbols:
            definition = self.symbol_definitions.get(symbol_id)
            if not definition:
                continue

            score = 0

            # Prefer symbols from the same file
            if definition.file_path == context_file:
                score += 100

            # Prefer symbols from similar scope depth
            symbol_scope_depth = symbol_id.count('/')
            context_scope_depth = len(context_scope)
            scope_diff = abs(symbol_scope_depth - context_scope_depth)
            score += max(0, 50 - scope_diff * 10)

            # Prefer symbols with matching scope components
            for scope_component in context_scope:
                if scope_component in symbol_id:
                    score += 20

            scored_candidates.append((score, symbol_id))

        if not scored_candidates:
            return None

        # Return highest scoring candidate
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_symbol = scored_candidates[0][1]

        logger.debug(f"Resolved '{candidate_symbols}' to '{best_symbol}' "
                    f"(score: {scored_candidates[0][0]})")

        return best_symbol

    def clear(self) -> None:
        """Clear all symbol tables."""
        self.symbol_definitions.clear()
        self.symbol_references.clear()
        self.file_symbols.clear()
        self.symbol_by_name.clear()

        logger.debug("Symbol tables cleared")

    def export_symbol_table(self) -> Dict[str, any]:
        """
        Export symbol table for debugging or persistence.

        Returns:
            Dictionary representation of symbol table
        """
        return {
            'definitions': {
                symbol_id: {
                    'file_path': defn.file_path,
                    'display_name': defn.display_name,
                    'symbol_kind': defn.symbol_kind,
                    'documentation': defn.documentation
                }
                for symbol_id, defn in self.symbol_definitions.items()
            },
            'references': {
                symbol_id: len(refs)
                for symbol_id, refs in self.symbol_references.items()
            },
            'relationships': {
                symbol_id: len(rels)
                for symbol_id, rels in self.symbol_relationships.items()
            },
            'statistics': self.get_project_statistics()
        }

    def add_symbol_relationship(self,
                              source_symbol_id: str,
                              target_symbol_id: str,
                              relationship_type: str,
                              relationship_data: Dict[str, Any] = None) -> None:
        """
        Add a relationship between symbols.

        Args:
            source_symbol_id: Source symbol ID
            target_symbol_id: Target symbol ID
            relationship_type: Type of relationship (enum value as string)
            relationship_data: Additional relationship metadata
        """
        relationship = SymbolRelationship(
            source_symbol_id=source_symbol_id,
            target_symbol_id=target_symbol_id,
            relationship_type=relationship_type,
            relationship_data=relationship_data or {}
        )

        # Add to forward relationships
        if source_symbol_id not in self.symbol_relationships:
            self.symbol_relationships[source_symbol_id] = []
        self.symbol_relationships[source_symbol_id].append(relationship)

        # Add to reverse relationships for quick lookup
        if target_symbol_id not in self.reverse_relationships:
            self.reverse_relationships[target_symbol_id] = []
        self.reverse_relationships[target_symbol_id].append(relationship)

        logger.debug(f"Added relationship: {source_symbol_id} --{relationship_type}--> {target_symbol_id}")

    def get_symbol_relationships(self, symbol_id: str) -> List[SymbolRelationship]:
        """
        Get all relationships where the symbol is the source.

        Args:
            symbol_id: Symbol ID

        Returns:
            List of relationships
        """
        return self.symbol_relationships.get(symbol_id, [])

    def get_reverse_relationships(self, symbol_id: str) -> List[SymbolRelationship]:
        """
        Get all relationships where the symbol is the target.

        Args:
            symbol_id: Symbol ID

        Returns:
            List of relationships where this symbol is the target
        """
        return self.reverse_relationships.get(symbol_id, [])

    def get_all_relationships_for_symbol(self, symbol_id: str) -> Dict[str, List[SymbolRelationship]]:
        """
        Get both forward and reverse relationships for a symbol.

        Args:
            symbol_id: Symbol ID

        Returns:
            Dictionary with 'outgoing' and 'incoming' relationship lists
        """
        return {
            'outgoing': self.get_symbol_relationships(symbol_id),
            'incoming': self.get_reverse_relationships(symbol_id)
        }

    def find_relationships_by_type(self, relationship_type: str) -> List[SymbolRelationship]:
        """
        Find all relationships of a specific type.

        Args:
            relationship_type: Type of relationship to find

        Returns:
            List of matching relationships
        """
        matches = []
        for relationships in self.symbol_relationships.values():
            for rel in relationships:
                if rel.relationship_type == relationship_type:
                    matches.append(rel)
        return matches

    def remove_symbol_relationships(self, symbol_id: str) -> None:
        """
        Remove all relationships for a symbol (both as source and target).

        Args:
            symbol_id: Symbol ID to remove relationships for
        """
        # Remove as source
        if symbol_id in self.symbol_relationships:
            del self.symbol_relationships[symbol_id]

        # Remove as target
        if symbol_id in self.reverse_relationships:
            del self.reverse_relationships[symbol_id]

        # Remove from other symbols' relationships where this symbol is referenced
        for source_id, relationships in self.symbol_relationships.items():
            self.symbol_relationships[source_id] = [
                rel for rel in relationships if rel.target_symbol_id != symbol_id
            ]

        logger.debug(f"Removed all relationships for symbol: {symbol_id}")

    def get_relationship_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about relationships.

        Returns:
            Dictionary with relationship statistics
        """
        total_relationships = sum(len(rels) for rels in self.symbol_relationships.values())
        relationship_types = {}
        
        for relationships in self.symbol_relationships.values():
            for rel in relationships:
                rel_type = rel.relationship_type
                relationship_types[rel_type] = relationship_types.get(rel_type, 0) + 1

        return {
            'total_relationships': total_relationships,
            'symbols_with_outgoing_relationships': len(self.symbol_relationships),
            'symbols_with_incoming_relationships': len(self.reverse_relationships),
            'relationship_types': relationship_types
        }