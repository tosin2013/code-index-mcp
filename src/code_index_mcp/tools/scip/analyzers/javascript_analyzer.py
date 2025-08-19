"""
JavaScript/TypeScript language-specific SCIP symbol analyzer.

This module handles JavaScript and TypeScript specific logic for import parsing,
dependency classification, and symbol metadata extraction.
"""

import logging
from typing import Dict, List, Optional, Any, Set
from .base import BaseLanguageAnalyzer
from ..symbol_definitions import ImportGroup

logger = logging.getLogger(__name__)


class JavaScriptAnalyzer(BaseLanguageAnalyzer):
    """
    JavaScript/TypeScript language-specific SCIP symbol analyzer.

    Handles JavaScript and TypeScript specific import parsing, dependency
    classification, and symbol metadata extraction.
    """

    def _get_language_name(self) -> str:
        return "javascript"

    def _build_standard_library_modules(self) -> Set[str]:
        """Build JavaScript/Node.js built-in modules set."""
        return {
            # Node.js built-in modules
            'assert', 'async_hooks', 'buffer', 'child_process', 'cluster',
            'console', 'constants', 'crypto', 'dgram', 'dns', 'domain',
            'events', 'fs', 'http', 'http2', 'https', 'inspector',
            'module', 'net', 'os', 'path', 'perf_hooks', 'process',
            'punycode', 'querystring', 'readline', 'repl', 'stream',
            'string_decoder', 'timers', 'tls', 'trace_events', 'tty',
            'url', 'util', 'v8', 'vm', 'worker_threads', 'zlib',

            # Web APIs (for browser environment)
            'window', 'document', 'navigator', 'location', 'history',
            'localStorage', 'sessionStorage', 'fetch', 'XMLHttpRequest',
            'WebSocket', 'Worker', 'ServiceWorker', 'MessageChannel',
            'BroadcastChannel', 'AbortController', 'URL', 'URLSearchParams',
            'Blob', 'File', 'FileReader', 'FormData', 'Headers',
            'Request', 'Response', 'ReadableStream', 'WritableStream',
            'TransformStream', 'TextEncoder', 'TextDecoder',
            'Intl', 'JSON', 'Math', 'Date', 'RegExp', 'Promise',
            'Proxy', 'Reflect', 'Symbol', 'Map', 'Set', 'WeakMap',
            'WeakSet', 'ArrayBuffer', 'DataView', 'Int8Array',
            'Uint8Array', 'Int16Array', 'Uint16Array', 'Int32Array',
            'Uint32Array', 'Float32Array', 'Float64Array', 'BigInt64Array',
            'BigUint64Array'
        }

    def _classify_dependency_impl(self, module_name: str) -> str:
        """
        Classify JavaScript/TypeScript dependency based on module patterns.

        Args:
            module_name: Module name to classify

        Returns:
            Classification: 'standard_library', 'third_party', or 'local'
        """
        # Local imports (relative paths)
        if module_name.startswith('./') or module_name.startswith('../'):
            return 'local'

        # Absolute local imports (no node_modules)
        if module_name.startswith('/') or module_name.startswith('~'):
            return 'local'

        # Check for common project patterns
        if any(pattern in module_name for pattern in ['src/', 'lib/', 'app/', '@/']):
            return 'local'

        # Node.js built-in modules
        base_module = module_name.split('/')[0]
        if base_module in self.get_standard_library_modules():
            return 'standard_library'

        # Check for common scoped packages (third-party)
        if module_name.startswith('@'):
            return 'third_party'

        # Common third-party indicators
        third_party_indicators = {
            'react', 'vue', 'angular', 'jquery', 'lodash', 'moment',
            'express', 'koa', 'fastify', 'webpack', 'babel', 'eslint',
            'typescript', 'jest', 'mocha', 'chai', 'sinon', 'cypress',
            'puppeteer', 'playwright', 'storybook', 'next', 'nuxt',
            'gatsby', 'vite', 'rollup', 'parcel', 'styled-components',
            'emotion', 'material-ui', 'antd', 'bootstrap', 'tailwind'
        }

        if base_module in third_party_indicators:
            return 'third_party'

        # Everything else is likely third_party in JavaScript ecosystem
        return 'third_party'

    def extract_imports(self, document, imports: ImportGroup, symbol_parser=None) -> None:
        """
        Extract JavaScript/TypeScript imports from SCIP document.

        Args:
            document: SCIP document containing symbols and occurrences
            imports: ImportGroup to populate with extracted imports
            symbol_parser: Optional SCIPSymbolManager for enhanced parsing
        """
        try:
            seen_modules = set()

            if symbol_parser:
                # Extract using symbol parser
                for occurrence in document.occurrences:
                    if not self.is_import_occurrence(occurrence):
                        continue

                    symbol_info = symbol_parser.parse_symbol(occurrence.symbol)
                    if not symbol_info:
                        continue

                    # Handle different manager types
                    if symbol_info.manager == 'npm':
                        # npm packages
                        package_name = symbol_info.package or self._extract_package_from_descriptors(symbol_info.descriptors)
                        if package_name and package_name not in seen_modules:
                            classification = self.classify_dependency(package_name)
                            imports.add_import(package_name, classification)
                            seen_modules.add(package_name)

                    elif symbol_info.manager in ['builtin', 'node']:
                        # Node.js built-ins
                        module_name = self._extract_module_from_descriptors(symbol_info.descriptors)
                        if module_name and module_name not in seen_modules:
                            imports.add_import(module_name, 'standard_library')
                            seen_modules.add(module_name)

                    elif symbol_info.manager == 'local':
                        # Local imports
                        module_path = self._extract_local_module_path(symbol_info.descriptors)
                        if module_path and module_path not in seen_modules:
                            imports.add_import(module_path, 'local')
                            seen_modules.add(module_path)

            else:
                # Fallback: basic extraction without symbol parser
                self._extract_imports_fallback(document, imports, seen_modules)

            logger.debug(f"Extracted {len(seen_modules)} JavaScript imports")

        except Exception as e:
            logger.debug(f"Error extracting JavaScript imports: {e}")

    def _extract_symbol_metadata_impl(self, symbol_info, document) -> Dict[str, Any]:
        """
        Extract JavaScript/TypeScript specific symbol metadata.

        Args:
            symbol_info: SCIP symbol information
            document: SCIP document

        Returns:
            Dictionary with JavaScript/TypeScript specific metadata
        """
        metadata = {
            'language': 'javascript',
            'source': 'javascript_analyzer'
        }

        try:
            # Extract type information (especially for TypeScript)
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                signature = symbol_info.signature
                metadata['signature'] = signature

                # Parse TypeScript-specific patterns
                if '=>' in signature:
                    metadata['is_arrow_function'] = True

                if 'async' in signature:
                    metadata['is_async'] = True

                if 'export' in signature:
                    metadata['is_exported'] = True

                if 'default' in signature:
                    metadata['is_default_export'] = True

                # Parse function parameters
                if '(' in signature and ')' in signature:
                    params = self._parse_js_parameters(signature)
                    if params:
                        metadata['parameters'] = params

                # Parse return type (TypeScript)
                if ':' in signature and '=>' not in signature:
                    parts = signature.split(':')
                    if len(parts) > 1:
                        type_part = parts[-1].strip()
                        metadata['type'] = type_part

            # Extract symbol characteristics
            symbol = getattr(symbol_info, 'symbol', '')
            if symbol:
                metadata['is_class'] = self._is_js_class(symbol)
                metadata['is_interface'] = self._is_ts_interface(symbol)
                metadata['is_type'] = self._is_ts_type(symbol)
                metadata['is_enum'] = self._is_ts_enum(symbol)
                metadata['is_namespace'] = self._is_ts_namespace(symbol)
                metadata['scope'] = self._classify_js_scope(symbol)

            # Extract JSDoc documentation
            if hasattr(symbol_info, 'documentation') and symbol_info.documentation:
                metadata['documentation'] = symbol_info.documentation
                metadata['has_jsdoc'] = any('@' in line for line in symbol_info.documentation)

        except Exception as e:
            logger.debug(f"Error extracting JavaScript metadata: {e}")
            metadata['extraction_error'] = str(e)

        return metadata

    def _extract_package_from_descriptors(self, descriptors: str) -> Optional[str]:
        """
        Extract package name from SCIP descriptors for JavaScript.

        Args:
            descriptors: SCIP descriptors string

        Returns:
            Package name or None
        """
        try:
            # Handle descriptors like 'react/' or 'lodash/map'
            if '/' in descriptors:
                package_part = descriptors.split('/')[0]
                # Handle scoped packages like @types/node
                if package_part.startswith('@'):
                    parts = descriptors.split('/')
                    if len(parts) >= 2:
                        return f"{parts[0]}/{parts[1]}"
                return package_part
            return descriptors.strip('/')
        except Exception:
            return None

    def _extract_local_module_path(self, descriptors: str) -> Optional[str]:
        """
        Extract local module path from descriptors for JavaScript.

        Args:
            descriptors: SCIP descriptors string

        Returns:
            Module path or None
        """
        try:
            # Handle local JavaScript imports
            if '/' in descriptors:
                parts = descriptors.split('/')
                if len(parts) >= 1:
                    file_part = parts[0]
                    # Remove common JavaScript extensions
                    for ext in ['.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs']:
                        if file_part.endswith(ext):
                            file_part = file_part[:-len(ext)]
                            break
                    return file_part
            return None
        except Exception:
            return None

    def _extract_imports_fallback(self, document, imports: ImportGroup, seen_modules: Set[str]) -> None:
        """Fallback import extraction without symbol parser."""
        try:
            for occurrence in document.occurrences:
                if not self.is_import_occurrence(occurrence):
                    continue

                symbol = occurrence.symbol
                module_name = self.extract_module_from_symbol(symbol)
                if module_name and module_name not in seen_modules:
                    classification = self.classify_dependency(module_name)
                    imports.add_import(module_name, classification)
                    seen_modules.add(module_name)
        except Exception as e:
            logger.debug(f"Error in JavaScript fallback import extraction: {e}")

    def _parse_js_parameters(self, signature: str) -> List[str]:
        """
        Parse parameter names from JavaScript/TypeScript function signature.

        Args:
            signature: Function signature string

        Returns:
            List of parameter names
        """
        try:
            if '(' in signature and ')' in signature:
                # Find the parameter section
                start = signature.find('(')
                end = signature.find(')', start)
                if start < end:
                    param_section = signature[start + 1:end]
                    if not param_section.strip():
                        return []

                    params = []
                    # Split by comma, but be careful of nested parentheses and generics
                    current_param = ""
                    paren_depth = 0
                    bracket_depth = 0

                    for char in param_section:
                        if char == '(':
                            paren_depth += 1
                        elif char == ')':
                            paren_depth -= 1
                        elif char == '<':
                            bracket_depth += 1
                        elif char == '>':
                            bracket_depth -= 1
                        elif char == ',' and paren_depth == 0 and bracket_depth == 0:
                            params.append(current_param.strip())
                            current_param = ""
                            continue

                        current_param += char

                    if current_param.strip():
                        params.append(current_param.strip())

                    # Extract just parameter names (before : or =)
                    param_names = []
                    for param in params:
                        # Handle destructuring and rest parameters
                        param = param.strip()
                        if param.startswith('...'):
                            param = param[3:].strip()

                        # Extract name before type annotation or default value
                        if ':' in param:
                            param = param.split(':')[0].strip()
                        elif '=' in param:
                            param = param.split('=')[0].strip()

                        if param and not param.startswith('{') and not param.startswith('['):
                            param_names.append(param)

                    return param_names
        except Exception as e:
            logger.debug(f"Error parsing JavaScript parameters: {e}")

        return []

    def _is_js_class(self, symbol: str) -> bool:
        """Check if symbol represents a JavaScript class."""
        try:
            return 'class' in symbol.lower() or '/Class' in symbol
        except Exception:
            return False

    def _is_ts_interface(self, symbol: str) -> bool:
        """Check if symbol represents a TypeScript interface."""
        try:
            return 'interface' in symbol.lower() or '/Interface' in symbol
        except Exception:
            return False

    def _is_ts_type(self, symbol: str) -> bool:
        """Check if symbol represents a TypeScript type alias."""
        try:
            return 'type' in symbol.lower() and not 'typeof' in symbol.lower()
        except Exception:
            return False

    def _is_ts_enum(self, symbol: str) -> bool:
        """Check if symbol represents a TypeScript enum."""
        try:
            return 'enum' in symbol.lower() or '/Enum' in symbol
        except Exception:
            return False

    def _is_ts_namespace(self, symbol: str) -> bool:
        """Check if symbol represents a TypeScript namespace."""
        try:
            return 'namespace' in symbol.lower() or '/Namespace' in symbol
        except Exception:
            return False

    def _classify_js_scope(self, symbol: str) -> str:
        """
        Classify JavaScript symbol scope.

        Args:
            symbol: SCIP symbol string

        Returns:
            Scope classification
        """
        # Basic scope classification for JavaScript
        if '//' in symbol or symbol.count('/') > 2:
            return 'nested'
        elif '/' in symbol:
            return 'module'
        else:
            return 'global'