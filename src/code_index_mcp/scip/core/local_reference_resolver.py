"""Local Reference Resolver - Cross-file reference resolution within a project."""

import logging
from typing import Dict, List, Optional, Set, Tuple
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
        Get statistics about the symbol table.

        Returns:
            Dictionary with statistics
        """
        total_references = sum(len(refs) for refs in self.symbol_references.values())

        return {
            'total_definitions': len(self.symbol_definitions),
            'total_references': total_references,
            'files_with_symbols': len(self.file_symbols),
            'unique_symbol_names': len(self.symbol_by_name)
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
            'statistics': self.get_project_statistics()
        }