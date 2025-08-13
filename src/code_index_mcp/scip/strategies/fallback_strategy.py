"""Fallback SCIP indexing strategy v2 - SCIP standard compliant."""

import logging
import os
import re
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ...constants import SUPPORTED_EXTENSIONS


logger = logging.getLogger(__name__)


class FallbackStrategy(SCIPIndexerStrategy):
    """SCIP-compliant fallback strategy for files without specific language support."""

    def __init__(self, priority: int = 10):
        """Initialize the fallback strategy v2 with low priority."""
        super().__init__(priority)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """This strategy can handle supported file extensions as a last resort."""
        return extension.lower() in SUPPORTED_EXTENSIONS

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "text"  # Generic text language

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from text files."""
        for file_path in files:
            try:
                self._collect_symbols_from_file(file_path, project_path)
            except Exception as e:
                logger.warning(f"Failed to collect symbols from {file_path}: {e}")
                continue

    def _generate_documents_with_references(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """Phase 2: Generate complete SCIP documents with resolved references."""
        documents = []
        
        for file_path in files:
            try:
                document = self._analyze_text_file(file_path, project_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"Failed to analyze text file {file_path}: {e}")
                continue
        
        return documents

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single text file."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return

        # Collect symbols using pattern matching
        relative_path = self._get_relative_path(file_path, project_path)
        collector = TextSymbolCollector(
            relative_path, content, self.symbol_manager, self.reference_resolver
        )
        collector.analyze()

    def _analyze_text_file(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """Analyze a single text file and generate complete SCIP document."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            return None

        # Create SCIP document
        document = scip_pb2.Document()
        document.relative_path = self._get_relative_path(file_path, project_path)
        document.language = self._detect_language_from_extension(Path(file_path).suffix)

        # Analyze content and generate occurrences
        self.position_calculator = PositionCalculator(content)
        analyzer = TextAnalyzer(
            document.relative_path,
            content,
            document.language,
            self.symbol_manager,
            self.position_calculator,
            self.reference_resolver
        )
        analyzer.analyze()

        # Add results to document
        document.occurrences.extend(analyzer.occurrences)
        document.symbols.extend(analyzer.symbols)

        logger.debug(f"Analyzed text file {document.relative_path}: "
                    f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _detect_language_from_extension(self, extension: str) -> str:
        """Detect specific language from extension."""
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


class TextSymbolCollector:
    """Basic text analyzer that collects symbols using pattern matching (Phase 1)."""

    def __init__(self, file_path: str, content: str, symbol_manager, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')
        self.symbol_manager = symbol_manager
        self.reference_resolver = reference_resolver

    def analyze(self):
        """Analyze text content using pattern matching."""
        # Determine if this looks like code
        if self._is_code_like():
            self._find_code_patterns()
        else:
            # For non-code files, just create a basic file symbol
            self._create_file_symbol()

    def _is_code_like(self) -> bool:
        """Determine if the file appears to be code-like."""
        # Check for common code indicators
        code_indicators = [
            r'\bfunction\b', r'\bdef\b', r'\bclass\b', r'\binterface\b',
            r'\bstruct\b', r'\benum\b', r'\bconst\b', r'\bvar\b', r'\blet\b',
            r'[{}();]', r'=\s*function', r'=>', r'\bif\b', r'\bfor\b', r'\bwhile\b'
        ]
        
        code_score = 0
        for pattern in code_indicators:
            if re.search(pattern, self.content, re.IGNORECASE):
                code_score += 1
        
        # If we find multiple code indicators, treat as code
        return code_score >= 3

    def _find_code_patterns(self):
        """Find basic patterns that might indicate functions or important constructs."""
        patterns = {
            'function_like': [
                re.compile(r'(?:^|\s)(?:function|def|fn|func)\s+(\w+)', re.IGNORECASE | re.MULTILINE),
                re.compile(r'(?:^|\s)(\w+)\s*\([^)]*\)\s*[{:]', re.MULTILINE),  # Function definitions
                re.compile(r'(?:^|\s)(\w+)\s*:=?\s*function', re.IGNORECASE | re.MULTILINE),  # JS functions
            ],
            'class_like': [
                re.compile(r'(?:^|\s)(?:class|struct|interface|enum)\s+(\w+)', re.IGNORECASE | re.MULTILINE),
            ],
            'constant_like': [
                re.compile(r'(?:^|\s)(?:const|let|var|#define)\s+(\w+)', re.IGNORECASE | re.MULTILINE),
                re.compile(r'(?:^|\s)(\w+)\s*[:=]\s*[^=]', re.MULTILINE),  # Simple assignments
            ],
            'config_like': [
                re.compile(r'^(\w+)\s*[:=]', re.MULTILINE),  # Config keys
                re.compile(r'^\[(\w+)\]', re.MULTILINE),  # INI sections
            ]
        }

        for line_num, line in enumerate(self.lines):
            line = line.strip()
            if not line or line.startswith(('#', '//', '/*', '*', '--', ';')):
                continue

            # Look for function-like patterns
            for pattern in patterns['function_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._register_symbol(name, scip_pb2.Function, "().", ["Function-like construct"])

            # Look for class-like patterns
            for pattern in patterns['class_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._register_symbol(name, scip_pb2.Class, "#", ["Type definition"])

            # Look for constant-like patterns
            for pattern in patterns['constant_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._register_symbol(name, scip_pb2.Variable, "", ["Variable or constant"])

            # Look for config-like patterns
            for pattern in patterns['config_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and len(name) > 1:
                        self._register_symbol(name, scip_pb2.Constant, "", ["Configuration key"])

    def _create_file_symbol(self):
        """Create a basic file-level symbol for non-code files."""
        file_name = Path(self.file_path).stem
        self._register_symbol(file_name, scip_pb2.File, "", ["File"])

    def _register_symbol(self, name: str, symbol_kind: int, descriptor: str, documentation: List[str]):
        """Register a symbol with the reference resolver."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="text",
            file_path=self.file_path,
            symbol_path=[name],
            descriptor=descriptor
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=self.file_path,
            definition_range=dummy_range,
            symbol_kind=symbol_kind,
            display_name=name,
            documentation=documentation
        )


class TextAnalyzer:
    """Basic text analyzer that generates complete SCIP data (Phase 2)."""

    def __init__(self, file_path: str, content: str, language: str,
                 symbol_manager, position_calculator, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.language = language
        self.lines = content.split('\n')
        self.symbol_manager = symbol_manager
        self.position_calculator = position_calculator
        self.reference_resolver = reference_resolver
        
        # Results
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

    def analyze(self):
        """Analyze text content and generate SCIP data."""
        # Determine if this looks like code
        if self._is_code_like():
            self._analyze_code_patterns()
        else:
            # For non-code files, just create a basic file symbol
            self._create_file_symbol()

    def _is_code_like(self) -> bool:
        """Determine if the file appears to be code-like."""
        # Same logic as collector
        code_indicators = [
            r'\bfunction\b', r'\bdef\b', r'\bclass\b', r'\binterface\b',
            r'\bstruct\b', r'\benum\b', r'\bconst\b', r'\bvar\b', r'\blet\b',
            r'[{}();]', r'=\s*function', r'=>', r'\bif\b', r'\bfor\b', r'\bwhile\b'
        ]
        
        code_score = 0
        for pattern in code_indicators:
            if re.search(pattern, self.content, re.IGNORECASE):
                code_score += 1
        
        return code_score >= 3

    def _analyze_code_patterns(self):
        """Analyze code patterns and create symbols."""
        patterns = {
            'function_like': [
                re.compile(r'(?:^|\s)(?:function|def|fn|func)\s+(\w+)', re.IGNORECASE | re.MULTILINE),
                re.compile(r'(?:^|\s)(\w+)\s*\([^)]*\)\s*[{:]', re.MULTILINE),
                re.compile(r'(?:^|\s)(\w+)\s*:=?\s*function', re.IGNORECASE | re.MULTILINE),
            ],
            'class_like': [
                re.compile(r'(?:^|\s)(?:class|struct|interface|enum)\s+(\w+)', re.IGNORECASE | re.MULTILINE),
            ],
            'constant_like': [
                re.compile(r'(?:^|\s)(?:const|let|var|#define)\s+(\w+)', re.IGNORECASE | re.MULTILINE),
                re.compile(r'(?:^|\s)(\w+)\s*[:=]\s*[^=]', re.MULTILINE),
            ],
            'config_like': [
                re.compile(r'^(\w+)\s*[:=]', re.MULTILINE),
                re.compile(r'^\[(\w+)\]', re.MULTILINE),
            ]
        }

        for line_num, line in enumerate(self.lines):
            line = line.strip()
            if not line or line.startswith(('#', '//', '/*', '*', '--', ';')):
                continue

            # Look for function-like patterns
            for pattern in patterns['function_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._create_symbol(line_num, name, scip_pb2.Function, "().", 
                                          [f"Function-like construct in {self.language}"])

            # Look for class-like patterns
            for pattern in patterns['class_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._create_symbol(line_num, name, scip_pb2.Class, "#", 
                                          [f"Type definition in {self.language}"])

            # Look for constant-like patterns
            for pattern in patterns['constant_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._create_symbol(line_num, name, scip_pb2.Variable, "", 
                                          [f"Variable or constant in {self.language}"])

            # Look for config-like patterns
            for pattern in patterns['config_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and len(name) > 1:
                        self._create_symbol(line_num, name, scip_pb2.Constant, "", 
                                          [f"Configuration key in {self.language}"])

    def _create_file_symbol(self):
        """Create a basic file-level symbol for non-code files."""
        file_name = Path(self.file_path).stem
        
        symbol_id = self.symbol_manager.create_local_symbol(
            language="text",
            file_path=self.file_path,
            symbol_path=[file_name],
            descriptor=""
        )
        
        # Create symbol information only (no occurrence for file-level symbols)
        symbol_info = self._create_symbol_information(
            symbol_id, file_name, scip_pb2.File, [f"{self.language.title()} file"]
        )
        self.symbols.append(symbol_info)

    def _create_symbol(self, line_num: int, name: str, symbol_kind: int, 
                      descriptor: str, documentation: List[str]):
        """Create a symbol with occurrence and information."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="text",
            file_path=self.file_path,
            symbol_path=[name],
            descriptor=descriptor
        )
        
        # Create definition occurrence
        start_col, end_col = self.position_calculator.find_name_in_line(line_num, name)
        range_obj = self.position_calculator.line_col_to_range(
            line_num, start_col, line_num, end_col
        )
        
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.Identifier
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        symbol_info = self._create_symbol_information(
            symbol_id, name, symbol_kind, documentation
        )
        self.symbols.append(symbol_info)

    def _create_occurrence(self, symbol_id: str, range_obj: scip_pb2.Range, 
                          symbol_roles: int, syntax_kind: int) -> scip_pb2.Occurrence:
        """Create a SCIP occurrence."""
        occurrence = scip_pb2.Occurrence()
        occurrence.symbol = symbol_id
        occurrence.symbol_roles = symbol_roles
        occurrence.syntax_kind = syntax_kind
        occurrence.range.CopyFrom(range_obj)
        return occurrence

    def _create_symbol_information(self, symbol_id: str, display_name: str, 
                                  symbol_kind: int, documentation: List[str] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = display_name
        symbol_info.kind = symbol_kind
        
        if documentation:
            symbol_info.documentation.extend(documentation)
        
        return symbol_info
