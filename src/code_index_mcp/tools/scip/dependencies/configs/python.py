"""
Python-specific dependency configuration.

This module provides Python-specific dependency classification rules,
including comprehensive standard library detection and pip package management.
"""

import json
import re
import logging
from typing import Set, Dict, List, Optional, Pattern
from .base import BaseDependencyConfig

logger = logging.getLogger(__name__)


class PythonDependencyConfig(BaseDependencyConfig):
    """
    Python-specific dependency configuration.

    Handles Python import classification with support for:
    - Comprehensive standard library detection
    - pip/conda package management
    - Virtual environment detection
    - Relative and absolute import patterns
    - PEP 420 namespace packages
    """

    def get_language_name(self) -> str:
        return "python"

    def get_stdlib_modules(self) -> Set[str]:
        """Return comprehensive Python standard library modules."""
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

    def _compile_patterns(self) -> None:
        """Compile Python-specific regex patterns."""
        try:
            self._third_party_patterns = [
                # Standard package names
                re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$'),
                # Namespace packages (PEP 420)
                re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$'),
                # Common third-party patterns
                re.compile(r'^(django|flask|requests|numpy|pandas|matplotlib|scipy|tensorflow|pytorch|sklearn)'),
            ]

            self._local_patterns = [
                # Relative imports
                re.compile(r'^\.+'),
                # Project-specific patterns
                re.compile(r'^(src|lib|app|project)\.'),
                re.compile(r'^(tests?|test_)'),
                # Common local patterns
                re.compile(r'^(utils|helpers|common|core|models|views|controllers)$'),
            ]
        except Exception as e:
            logger.warning(f"Error compiling Python patterns: {e}")

    def _classify_import_impl(self, import_path: str, context: Dict[str, any] = None) -> str:
        """Python-specific import classification."""
        # Handle special cases
        if import_path.startswith('__'):
            # Dunder modules are usually built-in or special
            return 'standard_library'

        # Check for common third-party packages
        common_third_party = {
            'numpy', 'pandas', 'matplotlib', 'scipy', 'sklearn', 'tensorflow',
            'torch', 'pytorch', 'requests', 'urllib3', 'beautifulsoup4',
            'django', 'flask', 'fastapi', 'sqlalchemy', 'alembic',
            'pytest', 'mock', 'coverage', 'tox', 'black', 'flake8',
            'mypy', 'isort', 'autopep8', 'yapf', 'pylint', 'bandit',
            'click', 'typer', 'pydantic', 'marshmallow', 'cerberus',
            'redis', 'celery', 'kombu', 'amqp', 'boto3', 'botocore',
            'psycopg2', 'pymongo', 'elasticsearch', 'kafka-python',
            'pillow', 'opencv-python', 'imageio', 'plotly', 'seaborn',
            'jupyter', 'ipython', 'notebook', 'jupyterlab'
        }

        base_package = self.get_package_name_from_import(import_path)
        if base_package in common_third_party:
            return 'third_party'

        # Check context for pip indicators
        if context:
            pip_indicators = context.get('pip_packages', set())
            if base_package in pip_indicators:
                return 'third_party'

            # Check for requirements.txt or setup.py dependencies
            project_deps = context.get('project_dependencies', set())
            if base_package in project_deps:
                return 'third_party'

        # Default to third_party for unknown packages
        return 'third_party'

    def normalize_import_path(self, raw_path: str) -> str:
        """Normalize Python import path."""
        # Remove common prefixes and suffixes
        normalized = raw_path.strip()

        # Handle namespace packages
        if normalized.endswith('.__init__'):
            normalized = normalized[:-9]

        # Normalize path separators to dots
        normalized = normalized.replace('/', '.')

        return normalized

    def get_package_manager_files(self) -> Set[str]:
        """Return Python package manager files."""
        return {
            'requirements.txt',
            'requirements-dev.txt',
            'requirements-test.txt',
            'setup.py',
            'setup.cfg',
            'pyproject.toml',
            'Pipfile',
            'Pipfile.lock',
            'poetry.lock',
            'conda.yaml',
            'environment.yml',
            'environment.yaml'
        }

    def extract_dependencies_from_file(self, file_path: str, file_content: str) -> List[str]:
        """Extract dependencies from Python package manager files."""
        dependencies = []

        try:
            if file_path.endswith('requirements.txt'):
                dependencies = self._parse_requirements_txt(file_content)
            elif file_path.endswith('setup.py'):
                dependencies = self._parse_setup_py(file_content)
            elif file_path.endswith('pyproject.toml'):
                dependencies = self._parse_pyproject_toml(file_content)
            elif file_path.endswith('Pipfile'):
                dependencies = self._parse_pipfile(file_content)
            elif file_path.endswith('.lock'):
                dependencies = self._parse_lock_file(file_path, file_content)
        except Exception as e:
            logger.debug(f"Error parsing {file_path}: {e}")

        return dependencies

    def _parse_requirements_txt(self, content: str) -> List[str]:
        """Parse requirements.txt file."""
        dependencies = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract package name (before version specifiers)
                package = re.split(r'[><=!]', line)[0].strip()
                if package:
                    dependencies.append(package)
        return dependencies

    def _parse_setup_py(self, content: str) -> List[str]:
        """Parse setup.py file for dependencies."""
        dependencies = []
        try:
            # Look for install_requires or setup() calls
            install_requires_match = re.search(
                r'install_requires\s*=\s*\[(.*?)\]',
                content,
                re.DOTALL
            )
            if install_requires_match:
                deps_str = install_requires_match.group(1)
                # Extract quoted strings
                for match in re.finditer(r'["\']([^"\']+)["\']', deps_str):
                    package = re.split(r'[><=!]', match.group(1))[0].strip()
                    if package:
                        dependencies.append(package)
        except Exception as e:
            logger.debug(f"Error parsing setup.py: {e}")

        return dependencies

    def _parse_pyproject_toml(self, content: str) -> List[str]:
        """Parse pyproject.toml file."""
        dependencies = []
        try:
            # This would require toml parsing library
            # For now, use simple regex approach
            deps_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if deps_match:
                deps_str = deps_match.group(1)
                for match in re.finditer(r'["\']([^"\']+)["\']', deps_str):
                    package = re.split(r'[><=!]', match.group(1))[0].strip()
                    if package:
                        dependencies.append(package)
        except Exception as e:
            logger.debug(f"Error parsing pyproject.toml: {e}")

        return dependencies

    def _parse_pipfile(self, content: str) -> List[str]:
        """Parse Pipfile for dependencies."""
        dependencies = []
        try:
            # Look for [packages] section
            in_packages_section = False
            for line in content.splitlines():
                line = line.strip()
                if line == '[packages]':
                    in_packages_section = True
                    continue
                elif line.startswith('[') and in_packages_section:
                    break
                elif in_packages_section and '=' in line:
                    package = line.split('=')[0].strip().strip('"\'')
                    if package:
                        dependencies.append(package)
        except Exception as e:
            logger.debug(f"Error parsing Pipfile: {e}")

        return dependencies

    def _parse_lock_file(self, file_path: str, content: str) -> List[str]:
        """Parse lock files (Pipfile.lock, poetry.lock)."""
        dependencies = []
        try:
            if 'Pipfile.lock' in file_path:
                # JSON format
                data = json.loads(content)
                if 'default' in data:
                    dependencies.extend(data['default'].keys())
                if 'develop' in data:
                    dependencies.extend(data['develop'].keys())
            elif 'poetry.lock' in file_path:
                # TOML format - simplified parsing
                for line in content.splitlines():
                    if line.startswith('name = '):
                        name = line.split('=')[1].strip().strip('"\'')
                        if name:
                            dependencies.append(name)
        except Exception as e:
            logger.debug(f"Error parsing lock file {file_path}: {e}")

        return dependencies

    def is_scoped_package(self, import_path: str) -> bool:
        """Check if import is a namespace package."""
        return '.' in import_path and not import_path.startswith('.')

    def supports_version_detection(self) -> bool:
        """Python supports version detection through various methods."""
        return True

    def detect_package_version(self, package_name: str, context: Dict[str, any] = None) -> Optional[str]:
        """Detect Python package version from context."""
        if not context:
            return None

        # Check lock files first (most reliable)
        lock_data = context.get('lock_file_data', {})
        if package_name in lock_data:
            return lock_data[package_name].get('version')

        # Check installed packages (if available)
        installed_packages = context.get('installed_packages', {})
        if package_name in installed_packages:
            return installed_packages[package_name]

        return None
