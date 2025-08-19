"""
Zig language-specific SCIP symbol analyzer.

This module handles Zig-specific logic extracted from the monolithic
SCIPSymbolAnalyzer, including Zig import classification and standard library detection.
"""

import logging
from typing import Dict, List, Optional, Any, Set
from .base import BaseLanguageAnalyzer
from ..symbol_definitions import ImportGroup

logger = logging.getLogger(__name__)


class ZigAnalyzer(BaseLanguageAnalyzer):
    """
    Zig language-specific SCIP symbol analyzer.

    Handles Zig-specific import parsing, dependency classification,
    and symbol metadata extraction.
    """

    def _get_language_name(self) -> str:
        return "zig"

    def _build_standard_library_modules(self) -> Set[str]:
        """Build comprehensive Zig standard library module set."""
        return {
            # Core standard library
            'std', 'builtin', 'testing',

            # Data structures and algorithms
            'math', 'mem', 'sort', 'hash', 'crypto',

            # Text and formatting
            'fmt', 'ascii', 'unicode', 'json',

            # System interaction
            'os', 'fs', 'process', 'thread', 'atomic',

            # Networking and I/O
            'net', 'http', 'io',

            # Compression and encoding
            'compress', 'base64',

            # Development and debugging
            'debug', 'log', 'meta', 'comptime',

            # Utilities
            'rand', 'time', 'zig',

            # Platform-specific
            'c', 'wasm',

            # Build system
            'build', 'target'
        }

    def _classify_dependency_impl(self, module_name: str) -> str:
        """
        Classify Zig dependency based on module patterns.

        Args:
            module_name: Zig module name to classify

        Returns:
            Classification: 'standard_library', 'third_party', or 'local'
        """
        # Local imports (relative paths or .zig files)
        if (module_name.startswith('./') or
            module_name.startswith('../') or
            module_name.endswith('.zig')):
            return 'local'

        # Standard library check
        if module_name in self.get_standard_library_modules():
            return 'standard_library'

        # Check for common Zig package patterns
        if any(pattern in module_name for pattern in ['zig-', 'pkg/', 'deps/']):
            return 'third_party'

        # Everything else is third_party (Zig doesn't have as many stdlib modules as Python)
        return 'third_party'

    def extract_imports(self, document, imports: ImportGroup, symbol_parser=None) -> None:
        """
        Extract Zig imports from SCIP document.

        Args:
            document: SCIP document containing symbols and occurrences
            imports: ImportGroup to populate with extracted imports
            symbol_parser: Optional SCIPSymbolManager for enhanced parsing
        """
        if not symbol_parser:
            logger.debug("No symbol parser available for Zig import extraction")
            return

        try:
            seen_modules = set()

            # Extract from occurrences with Import role
            for occurrence in document.occurrences:
                if not self.is_import_occurrence(occurrence):
                    continue

                symbol_info = symbol_parser.parse_symbol(occurrence.symbol)
                if not symbol_info:
                    continue

                # Handle Zig-specific patterns
                if symbol_info.manager == 'local':
                    # Local imports: extract from descriptors
                    module_path = self._extract_zig_local_module_path(symbol_info.descriptors)
                    if module_path and module_path not in seen_modules:
                        import_type = self.classify_dependency(module_path)
                        imports.add_import(module_path, import_type)
                        seen_modules.add(module_path)

                elif symbol_info.manager in ['system', 'stdlib']:
                    # Standard library imports
                    module_name = self._extract_module_from_descriptors(symbol_info.descriptors)
                    if module_name and module_name not in seen_modules:
                        imports.add_import(module_name, 'standard_library')
                        seen_modules.add(module_name)

                elif symbol_info.manager in ['third_party', 'pkg']:
                    # Third-party packages
                    package_name = symbol_info.package or self._extract_module_from_descriptors(symbol_info.descriptors)
                    if package_name and package_name not in seen_modules:
                        imports.add_import(package_name, 'third_party')
                        seen_modules.add(package_name)

            logger.debug(f"Extracted {len(seen_modules)} Zig imports")

        except Exception as e:
            logger.debug(f"Error extracting Zig imports: {e}")

    def _extract_symbol_metadata_impl(self, symbol_info, document) -> Dict[str, Any]:
        """
        Extract Zig-specific symbol metadata.

        Args:
            symbol_info: SCIP symbol information
            document: SCIP document

        Returns:
            Dictionary with Zig-specific metadata
        """
        metadata = {
            'language': 'zig',
            'source': 'zig_analyzer'
        }

        try:
            # Extract type information from signature
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                signature = symbol_info.signature
                metadata['signature'] = signature

                # Parse Zig-specific type patterns
                if ':' in signature:
                    # Variable/field type: name: Type
                    type_part = signature.split(':', 1)[1].strip()
                    metadata['type'] = type_part

                # Parse function return type (Zig uses different syntax)
                if '!' in signature:
                    # Error union type
                    metadata['can_error'] = True

                if 'comptime' in signature:
                    metadata['is_comptime'] = True

                if 'pub' in signature:
                    metadata['is_public'] = True
                else:
                    metadata['is_private'] = True

            # Extract documentation if available
            if hasattr(symbol_info, 'documentation') and symbol_info.documentation:
                metadata['documentation'] = symbol_info.documentation

            # Classify symbol characteristics
            symbol = getattr(symbol_info, 'symbol', '')
            if symbol:
                metadata['scope'] = self._classify_zig_symbol_scope(symbol)
                metadata['is_test'] = self._is_zig_test_symbol(symbol)
                metadata['is_generic'] = self._is_zig_generic_symbol(symbol)

        except Exception as e:
            logger.debug(f"Error extracting Zig metadata: {e}")
            metadata['extraction_error'] = str(e)

        return metadata

    def _extract_zig_local_module_path(self, descriptors: str) -> Optional[str]:
        """
        Extract local module path from descriptors for Zig.

        Args:
            descriptors: SCIP descriptors string

        Returns:
            Module path or None
        """
        try:
            # Handle Zig descriptors like:
            # 'test/sample-projects/zig/code-index-example/src/main.zig/std.' -> 'std'
            # 'src/utils.zig/helper_function' -> 'utils'
            if '/' in descriptors:
                parts = descriptors.split('/')
                if len(parts) >= 2:
                    # For Zig: if we have a .zig file, the symbol after it is the import
                    for i, part in enumerate(parts):
                        if part.endswith('.zig') and i + 1 < len(parts):
                            # Next part is the imported symbol/module
                            symbol_name = parts[i + 1].rstrip('.')
                            return symbol_name

                    # Fallback: traditional file-based extraction
                    file_part = parts[0]
                    if file_part.endswith('.zig'):
                        return file_part[:-4]  # Remove .zig extension
                    return file_part
            return None
        except Exception:
            return None

    def _extract_module_from_descriptors(self, descriptors: str) -> Optional[str]:
        """
        Extract module name from SCIP descriptors for Zig.

        Args:
            descriptors: SCIP descriptors string

        Returns:
            Module name or None
        """
        try:
            # Handle descriptors like 'std/' or 'std/mem'
            if '/' in descriptors:
                return descriptors.split('/')[0]
            return descriptors.strip('/.')
        except Exception:
            return None

    def _classify_zig_symbol_scope(self, symbol: str) -> str:
        """
        Classify Zig symbol scope.

        Args:
            symbol: SCIP symbol string

        Returns:
            Scope classification
        """
        # Zig doesn't use # for scope like other languages
        if '/' in symbol:
            parts = symbol.count('/')
            if parts == 1:
                return 'module'
            elif parts >= 2:
                return 'nested'
        return 'global'

    def _is_zig_test_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is a Zig test.

        Args:
            symbol: SCIP symbol string

        Returns:
            True if symbol appears to be a test
        """
        try:
            # Zig tests often contain 'test' in their symbol path
            return 'test' in symbol.lower()
        except Exception:
            return False

    def _is_zig_generic_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is a generic (comptime) function/type.

        Args:
            symbol: SCIP symbol string

        Returns:
            True if symbol appears to be generic
        """
        try:
            # This would require more sophisticated analysis
            # For now, just check for common generic patterns
            return 'comptime' in symbol.lower() or 'generic' in symbol.lower()
        except Exception:
            return False