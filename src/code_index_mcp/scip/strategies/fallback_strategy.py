# pylint: disable=no-member
"""Fallback SCIP indexing strategy for unsupported file types."""

import logging
import os
import re
from typing import List, Set, Dict, Any, Optional
from pathlib import Path
from .base_strategy import SCIPIndexerStrategy, ConversionError
from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class FallbackStrategy(SCIPIndexerStrategy):
    """Fallback strategy for files that don't have specific language support."""

    def __init__(self, priority: int = 10):
        """Initialize the fallback strategy with low priority."""
        super().__init__(priority)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """This strategy can handle any file type as a last resort."""
        return True

    def generate_scip_documents(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """
        Generate basic SCIP documents for unsupported files.

        Args:
            files: List of file paths to index
            project_path: Root path of the project

        Returns:
            List of basic SCIP Document objects
        """
        documents = []

        for file_path in files:
            try:
                document = self._create_basic_document(file_path, project_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"Failed to create basic document for {file_path}: {str(e)}")
                # Continue with other files

        logger.info(f"Fallback strategy created {len(documents)} basic documents")
        return documents

    def _create_basic_document(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """
        Create a basic SCIP document with minimal information.

        Args:
            file_path: Path to the file
            project_path: Root path of the project

        Returns:
            Basic SCIP Document object
        """
        try:
            # Create SCIP document
            document = scip_pb2.Document()
            document.relative_path = self._get_relative_path(file_path, project_path)
            document.language = self._detect_language_from_extension(Path(file_path).suffix)

            # Resolve full file path
            if not os.path.isabs(file_path):
                full_path = os.path.join(project_path, file_path)
            else:
                full_path = file_path

            # Try to read file for basic analysis
            content = self._read_file_content(full_path)
            if content:
                # Perform basic text analysis
                analyzer = BasicTextAnalyzer(document.relative_path, content, document.language)
                analyzer.analyze()

                # Add basic occurrences and symbols
                document.occurrences.extend(analyzer.occurrences)
                document.symbols.extend(analyzer.symbols)

            logger.debug(f"Created basic document for {document.relative_path} "
                        f"({document.language}): {len(document.occurrences)} occurrences")

            return document

        except Exception as e:
            logger.error(f"Failed to create basic document for {file_path}: {str(e)}")
            return None

    def _read_file_content(self, file_path: str) -> Optional[str]:
        """Read file content with multiple encoding attempts."""
        try:
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue

            logger.warning(f"Could not decode {file_path} with any text encoding")
            return None

        except (OSError, PermissionError, FileNotFoundError) as e:
            logger.warning(f"Could not read {file_path}: {str(e)}")
            return None

    def _get_relative_path(self, file_path: str, project_path: str) -> str:
        """Get relative path from project root."""
        try:
            path = Path(file_path)
            if path.is_absolute():
                return str(path.relative_to(Path(project_path)))
            return file_path
        except ValueError:
            return file_path

    def _detect_language_from_extension(self, extension: str) -> str:
        """Detect language from file extension."""
        extension_mapping = {
            # Programming languages
            '.c': 'c',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c++': 'cpp',
            '.h': 'c', '.hpp': 'cpp', '.hh': 'cpp', '.hxx': 'cpp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.cs': 'csharp',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin', '.kts': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.lua': 'lua',
            '.perl': 'perl', '.pl': 'perl',
            '.zig': 'zig',
            '.dart': 'dart',

            # Web and markup
            '.html': 'html', '.htm': 'html',
            '.css': 'css',
            '.scss': 'scss', '.sass': 'sass',
            '.less': 'less',
            '.vue': 'vue',
            '.svelte': 'svelte',
            '.astro': 'astro',

            # Data and config
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml', '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'ini',
            '.conf': 'ini',

            # Documentation
            '.md': 'markdown', '.markdown': 'markdown',
            '.mdx': 'mdx',
            '.tex': 'latex',
            '.rst': 'rst',

            # Database and query
            '.sql': 'sql',
            '.cql': 'cql',
            '.cypher': 'cypher',
            '.sparql': 'sparql',
            '.graphql': 'graphql', '.gql': 'graphql',

            # Shell and scripts
            '.sh': 'shell', '.bash': 'bash',
            '.zsh': 'zsh', '.fish': 'fish',
            '.ps1': 'powershell',
            '.bat': 'batch', '.cmd': 'batch',

            # Template languages
            '.handlebars': 'handlebars', '.hbs': 'handlebars',
            '.ejs': 'ejs',
            '.pug': 'pug',
            '.mustache': 'mustache',

            # Other
            '.dockerfile': 'dockerfile',
            '.gitignore': 'gitignore',
            '.env': 'dotenv',
        }

        return extension_mapping.get(extension.lower(), 'text')

    def get_strategy_name(self) -> str:
        """Return a human-readable name for this strategy."""
        return "Fallback(BasicText)"


class BasicTextAnalyzer:
    """Basic text analyzer that extracts simple patterns from any text file."""

    def __init__(self, file_path: str, content: str, language: str):
        self.file_path = file_path
        self.content = content
        self.language = language
        self.lines = content.split('\n')
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

    def analyze(self):
        """Perform basic text analysis."""
        # Only do basic analysis for code-like files
        if self._is_code_like():
            self._find_basic_patterns()
        else:
            # For non-code files, just create a basic file symbol
            self._create_file_symbol()

    def _is_code_like(self) -> bool:
        """Determine if the file appears to be code-like."""
        code_languages = {
            'c', 'cpp', 'go', 'rust', 'ruby', 'csharp', 'php', 'swift',
            'kotlin', 'scala', 'r', 'lua', 'perl', 'zig', 'dart',
            'css', 'scss', 'sass', 'less', 'sql', 'shell', 'bash',
            'powershell', 'batch'
        }

        return self.language in code_languages

    def _find_basic_patterns(self):
        """Find basic patterns that might indicate functions or important constructs."""

        # Basic patterns for different languages
        patterns = {
            'function_like': [
                re.compile(r'(?:^|\s)(?:function|def|fn|func)\s+(\w+)', re.IGNORECASE),
                re.compile(r'(?:^|\s)(\w+)\s*\([^)]*\)\s*{'),  # C-style functions
                re.compile(r'(?:^|\s)(\w+)\s*:=?\s*function'),  # JS arrow functions
            ],
            'class_like': [
                re.compile(r'(?:^|\s)(?:class|struct|interface|enum)\s+(\w+)', re.IGNORECASE),
            ],
            'constant_like': [
                re.compile(r'(?:^|\s)(?:const|let|var|#define)\s+(\w+)', re.IGNORECASE),
                re.compile(r'(?:^|\s)(\w+)\s*[:=]\s*[^=]'),  # Simple assignments
            ]
        }

        for line_num, line in enumerate(self.lines):
            line = line.strip()
            if not line or line.startswith(('#', '//', '/*', '*', '--')):
                continue

            # Look for function-like patterns
            for pattern in patterns['function_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier():
                        self._add_function_like(line_num, name)

            # Look for class-like patterns
            for pattern in patterns['class_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier():
                        self._add_class_like(line_num, name)

            # Look for constant-like patterns
            for pattern in patterns['constant_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._add_constant_like(line_num, name)

    def _create_file_symbol(self):
        """Create a basic file-level symbol for non-code files."""
        file_name = Path(self.file_path).stem
        symbol_id = self._create_symbol_id(file_name, '')

        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.kind = scip_pb2.File
        symbol_info.display_name = file_name
        symbol_info.documentation.append(f"{self.language.title()} file")

        self.symbols.append(symbol_info)

    def _add_function_like(self, line_num: int, name: str):
        """Add a function-like symbol."""
        symbol_id = self._create_symbol_id(name, '().')

        occurrence = self._create_occurrence(line_num, name, symbol_id,
                                           scip_pb2.Definition, scip_pb2.IdentifierFunction)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Function,
                                                     [f"Function-like construct in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_class_like(self, line_num: int, name: str):
        """Add a class-like symbol."""
        symbol_id = self._create_symbol_id(name, '#')

        occurrence = self._create_occurrence(line_num, name, symbol_id,
                                           scip_pb2.Definition, scip_pb2.IdentifierType)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Class,
                                                     [f"Type definition in {self.language}"])
        self.symbols.append(symbol_info)

    def _add_constant_like(self, line_num: int, name: str):
        """Add a constant-like symbol."""
        symbol_id = self._create_symbol_id(name, '')

        occurrence = self._create_occurrence(line_num, name, symbol_id,
                                           scip_pb2.Definition, scip_pb2.IdentifierConstant)
        self.occurrences.append(occurrence)

        symbol_info = self._create_symbol_information(symbol_id, name, scip_pb2.Constant,
                                                     [f"Constant or variable in {self.language}"])
        self.symbols.append(symbol_info)

    def _create_symbol_id(self, name: str, kind: str) -> str:
        """Create a SCIP symbol identifier."""
        clean_path = (self.file_path.replace('/', '.').replace('\\', '.')
                      .replace('.', '_'))  # Replace dots to avoid conflicts
        return f"local {clean_path} {name}{kind}"

    def _create_occurrence(self, line_num: int, name: str, symbol: str,
                          roles: int, syntax_kind: int) -> scip_pb2.Occurrence:
        """Create a SCIP occurrence."""
        occurrence = scip_pb2.Occurrence()

        # Find the position of the name in the line
        line_content = self.lines[line_num]
        col_start = line_content.find(name)
        if col_start == -1:
            col_start = 0
        col_end = col_start + len(name)

        occurrence.range.start.extend([line_num, col_start])
        occurrence.range.end.extend([line_num, col_end])
        occurrence.symbol = symbol
        occurrence.symbol_roles = roles
        occurrence.syntax_kind = syntax_kind

        return occurrence

    def _create_symbol_information(self, symbol: str, name: str, kind: int,
                                  documentation: List[str] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol
        symbol_info.kind = kind
        symbol_info.display_name = name

        if documentation:
            symbol_info.documentation.extend(documentation)

        return symbol_info
