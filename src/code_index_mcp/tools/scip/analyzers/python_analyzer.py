"""
Python language-specific SCIP symbol analyzer.

This module handles Python-specific logic extracted from the monolithic
SCIPSymbolAnalyzer, following the refactoring plan for modular architecture.
"""

import logging
from typing import Dict, List, Optional, Any, Set
from .base import BaseLanguageAnalyzer
from ..symbol_definitions import ImportGroup

logger = logging.getLogger(__name__)


class PythonAnalyzer(BaseLanguageAnalyzer):
    """
    Python language-specific SCIP symbol analyzer.

    Handles Python-specific import parsing, dependency classification,
    and symbol metadata extraction.
    """

    def _get_language_name(self) -> str:
        return "python"

    def _build_standard_library_modules(self) -> Set[str]:
        """Build comprehensive Python standard library module set."""
        return {
            # Core modules
            'os', 'sys', 'json', 'time', 'datetime', 'logging', 'pathlib',
            'typing', 'dataclasses', 'functools', 'itertools', 'collections',
            're', 'math', 'random', 'threading', 'subprocess', 'shutil',
            'contextlib', 'traceback', 'warnings', 'weakref', 'copy',
            'pickle', 'base64', 'hashlib', 'hmac', 'uuid', 'urllib',
            'http', 'socketserver', 'email', 'mimetypes', 'csv', 'configparser',
            'argparse', 'getopt', 'tempfile', 'glob', 'fnmatch', 'linecache',
            'pprint', 'textwrap', 'string', 'struct', 'codecs', 'unicodedata',
            'io', 'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile',

            # Network and web
            'socket', 'ssl', 'ftplib', 'poplib', 'imaplib', 'smtplib',
            'xmlrpc', 'webbrowser',

            # Data formats
            'xml', 'html', 'sqlite3', 'dbm', 'marshal',

            # Development tools
            'unittest', 'doctest', 'pdb', 'profile', 'cProfile', 'timeit',
            'trace', 'cgitb', 'py_compile', 'compileall', 'dis', 'pickletools',

            # System services
            'errno', 'ctypes', 'syslog', 'curses', 'platform',

            # Internationalization
            'locale', 'gettext',

            # Multimedia
            'audioop', 'wave', 'chunk', 'sunau', 'aifc', 'colorsys',

            # Cryptographic services
            'secrets', 'hashlib', 'hmac',

            # File and directory access
            'stat', 'fileinput', 'filecmp', 'shutil', 'macpath',

            # Data persistence
            'shelve', 'copyreg',

            # Data compression and archiving
            'zlib', 'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile',

            # File formats
            'csv', 'netrc', 'xdrlib', 'plistlib',

            # Internet protocols and support
            'ipaddress', 'mailbox', 'mimetypes',

            # Structured markup processing tools
            'html', 'xml',

            # Internet data handling
            'json', 'base64', 'binascii', 'uu', 'quopri',

            # Numeric and mathematical modules
            'numbers', 'decimal', 'fractions', 'statistics', 'cmath',

            # Functional programming modules
            'operator', 'functools', 'itertools',

            # Python language services
            'ast', 'symtable', 'symbol', 'token', 'tokenize', 'keyword',
            'tabnanny', 'pyclbr', 'py_compile', 'compileall', 'dis',
            'pickletools', 'distutils',

            # Importing modules
            'importlib', 'pkgutil', 'modulefinder', 'runpy',

            # Python runtime services
            'atexit', 'gc', 'inspect', 'site', '__future__', '__main__',

            # Custom Python interpreters
            'code', 'codeop',

            # MS Windows specific services
            'msvcrt', 'winreg', 'winsound',

            # Unix specific services
            'posix', 'pwd', 'grp', 'crypt', 'termios', 'tty', 'pty',
            'fcntl', 'pipes', 'resource', 'nis', 'syslog',

            # Superseded modules
            'optparse', 'imp'
        }

    def _classify_dependency_impl(self, module_name: str) -> str:
        """
        Classify Python dependency based on module patterns.

        Args:
            module_name: Python module name to classify

        Returns:
            Classification: 'standard_library', 'third_party', or 'local'
        """
        # Local imports (relative imports or project-specific patterns)
        if module_name.startswith('.'):
            return 'local'

        # Check for common project patterns
        if any(pattern in module_name for pattern in ['src.', 'lib.', 'app.', 'project.']):
            return 'local'

        # Standard library check
        base_module = module_name.split('.')[0]
        if base_module in self.get_standard_library_modules():
            return 'standard_library'

        # Everything else is third_party
        return 'third_party'

    def extract_imports(self, document, imports: ImportGroup, symbol_parser=None) -> None:
        """
        Extract Python imports from SCIP document.

        Args:
            document: SCIP document containing symbols and occurrences
            imports: ImportGroup to populate with extracted imports
            symbol_parser: Optional SCIPSymbolManager for enhanced parsing
        """
        if not symbol_parser:
            logger.debug("No symbol parser available for Python import extraction")
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

                # Handle based on manager type
                if symbol_info.manager == 'stdlib':
                    module_name = self._extract_module_from_descriptors(symbol_info.descriptors)
                    if module_name and module_name not in seen_modules:
                        imports.add_import(module_name, 'standard_library')
                        seen_modules.add(module_name)

                elif symbol_info.manager == 'pip':
                    # pip packages: package name is the module name
                    package_name = symbol_info.package
                    if package_name and package_name not in seen_modules:
                        imports.add_import(package_name, 'third_party')
                        seen_modules.add(package_name)

                elif symbol_info.manager == 'local':
                    # Local imports: extract module path from descriptors
                    module_path = self._extract_local_module_path(symbol_info.descriptors)
                    if module_path and module_path not in seen_modules:
                        imports.add_import(module_path, 'local')
                        seen_modules.add(module_path)

            logger.debug(f"Extracted {len(seen_modules)} Python imports")

        except Exception as e:
            logger.debug(f"Error extracting Python imports: {e}")

    def _extract_symbol_metadata_impl(self, symbol_info, document) -> Dict[str, Any]:
        """
        Extract Python-specific symbol metadata.

        Args:
            symbol_info: SCIP symbol information
            document: SCIP document

        Returns:
            Dictionary with Python-specific metadata
        """
        metadata = {
            'language': 'python',
            'source': 'python_analyzer'
        }

        try:
            # Extract documentation/docstring
            if hasattr(symbol_info, 'documentation') and symbol_info.documentation:
                metadata['documentation'] = symbol_info.documentation

                # Parse special documentation markers from Python AST analyzer
                for doc_line in symbol_info.documentation:
                    if doc_line.startswith('Parameters: '):
                        param_str = doc_line[12:]
                        metadata['parameters'] = [p.strip() for p in param_str.split(',') if p.strip()]
                    elif doc_line == 'Async function':
                        metadata['is_async'] = True
                    elif doc_line.startswith('Decorators: '):
                        decorator_str = doc_line[12:]
                        metadata['decorators'] = [d.strip() for d in decorator_str.split(',') if d.strip()]

            # Extract type information from signature
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                signature = symbol_info.signature
                metadata['signature'] = signature

                # Parse return type
                if '->' in signature:
                    return_type = signature.split('->')[-1].strip()
                    metadata['return_type'] = return_type

                # Parse parameters from signature
                if '(' in signature and ')' in signature and 'parameters' not in metadata:
                    metadata['parameters'] = self._parse_signature_parameters(signature)

                # Parse variable type annotation
                if ':' in signature and '->' not in signature:
                    type_part = signature.split(':')[1].strip()
                    metadata['type'] = type_part

                # Parse constant value
                if '=' in signature:
                    value_part = signature.split('=')[1].strip()
                    metadata['value'] = value_part

            # Classify symbol role
            symbol = getattr(symbol_info, 'symbol', '')
            if symbol:
                metadata['scope'] = self._classify_symbol_scope(symbol)
                metadata['is_private'] = self._is_private_symbol(symbol)
                metadata['is_dunder'] = self._is_dunder_method(symbol)

        except Exception as e:
            logger.debug(f"Error extracting Python metadata: {e}")
            metadata['extraction_error'] = str(e)

        return metadata

    def _extract_module_from_descriptors(self, descriptors: str) -> Optional[str]:
        """
        Extract module name from SCIP descriptors for Python.

        Args:
            descriptors: SCIP descriptors string

        Returns:
            Module name or None
        """
        try:
            # Handle descriptors like 'os/' or 'pathlib/Path'
            if '/' in descriptors:
                return descriptors.split('/')[0]
            return descriptors.strip('/')
        except Exception:
            return None

    def _extract_local_module_path(self, descriptors: str) -> Optional[str]:
        """
        Extract local module path from descriptors for Python.

        Args:
            descriptors: SCIP descriptors string

        Returns:
            Module path or None
        """
        try:
            # Handle descriptors like 'utils.py/helper_function' -> 'utils'
            # or 'services/user_service.py/UserService' -> 'services.user_service'
            if '/' in descriptors:
                parts = descriptors.split('/')
                if len(parts) >= 2:
                    file_part = parts[0]
                    if file_part.endswith('.py'):
                        return file_part[:-3].replace('/', '.')
                    return file_part.replace('/', '.')
            return None
        except Exception:
            return None

    def _parse_signature_parameters(self, signature: str) -> List[str]:
        """
        Parse parameter names from Python function signature.

        Args:
            signature: Function signature string

        Returns:
            List of parameter names
        """
        try:
            if '(' in signature and ')' in signature:
                param_section = signature.split('(')[1].split(')')[0]
                if not param_section.strip():
                    return []

                params = []
                for param in param_section.split(','):
                    param = param.strip()
                    if param:
                        # Extract parameter name (before type annotation)
                        param_name = param.split(':')[0].strip()
                        if param_name:
                            params.append(param_name)

                return params
        except Exception as e:
            logger.debug(f"Error parsing Python signature parameters: {e}")

        return []

    def _classify_symbol_scope(self, symbol: str) -> str:
        """
        Classify Python symbol scope (global, class, function).

        Args:
            symbol: SCIP symbol string

        Returns:
            Scope classification
        """
        if '#' not in symbol:
            return 'global'
        elif symbol.count('#') == 1:
            return 'class'
        else:
            return 'function'

    def _is_private_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is private (starts with underscore).

        Args:
            symbol: SCIP symbol string

        Returns:
            True if symbol appears to be private
        """
        try:
            # Extract symbol name from various SCIP formats
            if '#' in symbol:
                name = symbol.split('#')[-1]
            elif '/' in symbol:
                name = symbol.split('/')[-1]
            else:
                name = symbol.split('.')[-1]

            # Clean up name
            name = name.rstrip('().#')
            return name.startswith('_') and not name.startswith('__')
        except Exception:
            return False

    def _is_dunder_method(self, symbol: str) -> bool:
        """
        Check if symbol is a dunder (double underscore) method.

        Args:
            symbol: SCIP symbol string

        Returns:
            True if symbol appears to be a dunder method
        """
        try:
            # Extract symbol name
            if '#' in symbol:
                name = symbol.split('#')[-1]
            elif '/' in symbol:
                name = symbol.split('/')[-1]
            else:
                name = symbol.split('.')[-1]

            # Clean up name
            name = name.rstrip('().#')
            return name.startswith('__') and name.endswith('__')
        except Exception:
            return False
