"""
SCIP Query Tool - Pure technical component for querying SCIP index data.

This tool handles low-level SCIP data queries without any business logic.
It provides technical capabilities for extracting code intelligence from SCIP indexes.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ...scip.proto.scip_pb2 import Index as SCIPIndex, Document as SCIPDocument
from .scip_index_tool import SCIPIndexTool


@dataclass
class SymbolInfo:
    """Technical data structure for symbol information."""
    name: str
    kind: str
    location: Dict[str, int]
    scope: str
    documentation: List[str]


@dataclass
class FileIntelligence:
    """Technical data structure for file intelligence."""
    file_path: str
    language: str
    line_count: int
    symbols: List[SymbolInfo]
    imports: List[str]
    exports: List[str]
    complexity_metrics: Dict[str, float]


class SCIPQueryTool:
    """
    Pure technical component for querying SCIP index data.

    This tool provides low-level SCIP query capabilities without any
    business logic or decision making. It extracts raw intelligence
    data from SCIP indexes.
    """

    def __init__(self, scip_index_tool: SCIPIndexTool):
        self._scip_index_tool = scip_index_tool

    def get_file_intelligence(self, file_path: str) -> Optional[FileIntelligence]:
        """
        Extract comprehensive intelligence for a specific file.

        Args:
            file_path: Relative path to the file

        Returns:
            FileIntelligence object or None if file not found

        Raises:
            RuntimeError: If SCIP index is not available
        """
        if not self._scip_index_tool.is_index_available():
            raise RuntimeError("SCIP index is not available")

        # Find the document in SCIP index
        document = self._find_document(file_path)
        if not document:
            return None

        # Extract intelligence data
        symbols = self._extract_symbols(document)
        imports = self._extract_imports(document)
        exports = self._extract_exports(document)
        complexity = self._calculate_complexity_metrics(document)
        line_count = self._estimate_line_count(document)

        return FileIntelligence(
            file_path=file_path,
            language=document.language,
            line_count=line_count,
            symbols=symbols,
            imports=imports,
            exports=exports,
            complexity_metrics=complexity
        )



    def _find_document(self, file_path: str) -> Optional[SCIPDocument]:
        """Find SCIP document for the given file path."""
        raw_index = self._scip_index_tool.get_raw_index()
        if not raw_index:
            return None

        # Normalize path for comparison
        normalized_path = file_path.replace('\\', '/')

        for document in raw_index.documents:
            if document.relative_path == normalized_path:
                return document

        return None

    def _extract_symbols(self, document: SCIPDocument) -> List[SymbolInfo]:
        """Extract symbol information from SCIP document."""
        symbols = []

        for symbol_info in document.symbols:
            symbol_data = SymbolInfo(
                name=symbol_info.display_name,
                kind=self._get_symbol_type_name(symbol_info.kind),
                location=self._get_symbol_location(symbol_info.symbol, document),
                scope=self._extract_symbol_scope(symbol_info.symbol),
                documentation=list(symbol_info.documentation) if symbol_info.documentation else []
            )
            symbols.append(symbol_data)

        return symbols

    def _extract_imports(self, document: SCIPDocument) -> List[str]:
        """Extract import statements from SCIP document."""
        imports = []

        for occurrence in document.occurrences:
            if occurrence.symbol.startswith('external '):
                import_info = self._parse_external_symbol(occurrence.symbol)
                if import_info not in imports:
                    imports.append(import_info)

        return imports

    def _extract_exports(self, document: SCIPDocument) -> List[str]:
        """Extract export statements from SCIP document."""
        exports = []

        # Basic export detection from SCIP document symbols
        # Look for symbols that might be exports (public symbols, etc.)
        try:
            for symbol in document.symbols:
                # Check if symbol appears to be an export
                # This is a simplified heuristic - real export detection would be more complex
                if hasattr(symbol, 'symbol') and symbol.symbol:
                    symbol_name = symbol.symbol
                    # Look for common export patterns
                    if (not symbol_name.startswith('local ') and
                        not symbol_name.startswith('_') and
                        '.' not in symbol_name):  # Avoid nested/private symbols
                        exports.append(symbol_name)
        except (AttributeError, TypeError):
            # Handle cases where document structure is different than expected
            pass

        # Remove duplicates and return
        return list(set(exports))

    def _calculate_complexity_metrics(self, document: SCIPDocument) -> Dict[str, float]:
        """Calculate basic complexity metrics from SCIP document."""
        metrics = {
            'symbol_count': len(document.symbols),
            'occurrence_count': len(document.occurrences),
            'estimated_complexity': 0.0
        }

        # Simple complexity estimation based on symbol types
        complexity_weights = {
            3: 2.0,   # Class
            6: 1.5,   # Function
            7: 1.5,   # Method
            13: 0.5,  # Variable
        }

        total_complexity = 0.0
        for symbol_info in document.symbols:
            weight = complexity_weights.get(symbol_info.kind, 1.0)
            total_complexity += weight

        metrics['estimated_complexity'] = total_complexity

        return metrics

    def _estimate_line_count(self, document: SCIPDocument) -> int:
        """Estimate line count from SCIP document."""
        # This is a rough estimation based on occurrences
        # In a real implementation, we might need to read the actual file
        max_line = 0

        for occurrence in document.occurrences:
            if occurrence.range.start:
                line = occurrence.range.start[0] + 1
                max_line = max(max_line, line)

        return max_line if max_line > 0 else 1

    def _get_symbol_type_name(self, kind: int) -> str:
        """Convert SCIP symbol kind to human-readable type."""
        kind_names = {
            3: 'class',
            6: 'function',
            7: 'method',
            8: 'property',
            9: 'field',
            11: 'enum',
            12: 'interface',
            13: 'variable',
            14: 'constant',
            23: 'struct'
        }
        return kind_names.get(kind, 'unknown')

    def _get_symbol_location(self, symbol_id: str, document: SCIPDocument) -> Dict[str, int]:
        """Get location of symbol definition."""
        for occurrence in document.occurrences:
            if occurrence.symbol == symbol_id and occurrence.symbol_roles & 1:  # Definition
                if occurrence.range.start:
                    return {
                        'line': occurrence.range.start[0] + 1,
                        'column': occurrence.range.start[1] + 1
                    }

        return {'line': 1, 'column': 1}

    def _extract_symbol_scope(self, symbol_id: str) -> str:
        """Extract scope/namespace from symbol ID."""
        # SCIP symbol format parsing - simplified
        parts = symbol_id.split()
        if len(parts) >= 3:
            return parts[2].split('.')[0] if '.' in parts[2] else 'global'
        return 'global'

    def _parse_external_symbol(self, symbol: str) -> str:
        """Parse external symbol reference."""
        # Remove 'external ' prefix and extract module name
        cleaned = symbol.replace('external ', '')
        parts = cleaned.split()
        return parts[0] if parts else 'unknown'
