"""Fallback SCIP indexing strategy - SCIP standard compliant."""

import logging
import os
import re
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType
from ...constants import SUPPORTED_EXTENSIONS


logger = logging.getLogger(__name__)


class FallbackStrategy(SCIPIndexerStrategy):
    """SCIP-compliant fallback strategy for files without specific language support."""

    def __init__(self, priority: int = 10):
        """Initialize the fallback strategy with low priority."""
        super().__init__(priority)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """This strategy can handle supported file extensions as a last resort."""
        return extension.lower() in SUPPORTED_EXTENSIONS

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "text"  # Generic text language

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return True  # Always available as fallback

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from text files."""
        logger.debug(f"FallbackStrategy Phase 1: Processing {len(files)} files for symbol collection")
        processed_count = 0
        error_count = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                self._collect_symbols_from_file(file_path, project_path)
                processed_count += 1
                
                if i % 10 == 0 or i == len(files):
                    logger.debug(f"Phase 1 progress: {i}/{len(files)} files, last file: {relative_path}")
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"Phase 1 failed for {relative_path}: {e}")
                continue
        
        logger.info(f"Phase 1 summary: {processed_count} files processed, {error_count} errors")

    def _generate_documents_with_references(self, files: List[str], project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> List[scip_pb2.Document]:
        """Phase 2: Generate complete SCIP documents with resolved references."""
        documents = []
        logger.debug(f"FallbackStrategy Phase 2: Generating documents for {len(files)} files")
        processed_count = 0
        error_count = 0
        total_occurrences = 0
        total_symbols = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                document = self._analyze_text_file(file_path, project_path, relationships)
                if document:
                    documents.append(document)
                    total_occurrences += len(document.occurrences)
                    total_symbols += len(document.symbols)
                    processed_count += 1
                    
                if i % 10 == 0 or i == len(files):
                    logger.debug(f"Phase 2 progress: {i}/{len(files)} files, "
                               f"last file: {relative_path}, "
                               f"{len(document.occurrences) if document else 0} occurrences")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Phase 2 failed for {relative_path}: {e}")
                continue
        
        logger.info(f"Phase 2 summary: {processed_count} documents generated, {error_count} errors, "
                   f"{total_occurrences} total occurrences, {total_symbols} total symbols")
        
        return documents

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single text file."""
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {os.path.relpath(file_path, project_path)}")
            return

        # Collect symbols using pattern matching
        relative_path = self._get_relative_path(file_path, project_path)
        self._collect_symbols_from_text(relative_path, content)
        logger.debug(f"Symbol collection - {relative_path}")

    def _analyze_text_file(self, file_path: str, project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> Optional[scip_pb2.Document]:
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
        occurrences, symbols = self._analyze_text_content_for_document(document.relative_path, content, document.language, relationships)

        # Add results to document
        document.occurrences.extend(occurrences)
        document.symbols.extend(symbols)

        logger.debug(f"Analyzed text file {document.relative_path}: "
                    f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """
        Build basic relationships using generic patterns.
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        logger.debug(f"FallbackStrategy: Building symbol relationships for {len(files)} files")
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"FallbackStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships

    def _extract_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract basic relationships using generic patterns."""
        content = self._read_file_content(file_path)
        if not content:
            return {}
        
        relationships = {}
        relative_path = self._get_relative_path(file_path, project_path)
        
        # Generic function call patterns
        function_call_pattern = r"(\w+)\s*\("
        function_def_patterns = [
            r"function\s+(\w+)\s*\(",  # JavaScript
            r"def\s+(\w+)\s*\(",       # Python
            r"fn\s+(\w+)\s*\(",        # Rust/Zig
            r"func\s+(\w+)\s*\(",      # Go/Swift
        ]
        
        # Basic function definition extraction
        for pattern in function_def_patterns:
            for match in re.finditer(pattern, content):
                function_name = match.group(1)
                # Could expand to extract calls within function context
        
        logger.debug(f"Extracted {len(relationships)} relationships from {relative_path}")
        return relationships

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

    # Symbol collection methods (Phase 1)
    def _collect_symbols_from_text(self, file_path: str, content: str) -> None:
        """Collect symbols from text content using pattern matching."""
        lines = content.split('\n')
        
        # Determine if this looks like code
        if self._is_code_like(content):
            self._collect_code_symbols(file_path, lines)
        else:
            # For non-code files, just create a basic file symbol
            self._collect_file_symbol(file_path)

    def _collect_code_symbols(self, file_path: str, lines: List[str]):
        """Collect symbols from code-like content."""
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

        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith(('#', '//', '/*', '*', '--', ';')):
                continue

            # Look for function-like patterns
            for pattern in patterns['function_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._register_symbol(name, file_path, "().", "Function-like construct")

            # Look for class-like patterns
            for pattern in patterns['class_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._register_symbol(name, file_path, "#", "Type definition")

            # Look for constant-like patterns
            for pattern in patterns['constant_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        self._register_symbol(name, file_path, "", "Variable or constant")

            # Look for config-like patterns
            for pattern in patterns['config_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and len(name) > 1:
                        self._register_symbol(name, file_path, "", "Configuration key")

    def _collect_file_symbol(self, file_path: str):
        """Create a basic file-level symbol for non-code files."""
        file_name = Path(file_path).stem
        self._register_symbol(file_name, file_path, "", "File")

    def _register_symbol(self, name: str, file_path: str, descriptor: str, description: str):
        """Register a symbol with the reference resolver."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="text",
            file_path=file_path,
            symbol_path=[name],
            descriptor=descriptor
        )
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.UnspecifiedSymbolKind,
            display_name=name,
            documentation=[description]
        )

    # Document analysis methods (Phase 2)
    def _analyze_text_content_for_document(self, file_path: str, content: str, language: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple:
        """Analyze text content and generate SCIP data."""
        lines = content.split('\n')
        
        # Determine if this looks like code
        if self._is_code_like(content):
            return self._analyze_code_for_document(file_path, lines, language, relationships)
        else:
            # For non-code files, just create a basic file symbol
            return self._analyze_file_for_document(file_path, language)

    def _analyze_code_for_document(self, file_path: str, lines: List[str], language: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple:
        """Analyze code patterns and create symbols for document."""
        occurrences = []
        symbols = []
        
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
                re.compile(r'^[\[(\w+)\]]', re.MULTILINE),  # INI sections
            ]
        }

        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith(('#', '//', '/*', '*', '--', ';')):
                continue

            # Look for function-like patterns
            for pattern in patterns['function_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        occ, sym = self._create_symbol_for_document(
                            line_num, name, file_path, scip_pb2.Function, "().", 
                            f"Function-like construct in {language}",
                            relationships
                        )
                        if occ: occurrences.append(occ)
                        if sym: symbols.append(sym)

            # Look for class-like patterns
            for pattern in patterns['class_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        occ, sym = self._create_symbol_for_document(
                            line_num, name, file_path, scip_pb2.Class, "#", 
                            f"Type definition in {language}",
                            relationships
                        )
                        if occ: occurrences.append(occ)
                        if sym: symbols.append(sym)

            # Look for constant-like patterns
            for pattern in patterns['constant_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and name.isidentifier() and len(name) > 1:
                        occ, sym = self._create_symbol_for_document(
                            line_num, name, file_path, scip_pb2.Variable, "", 
                            f"Variable or constant in {language}",
                            relationships
                        )
                        if occ: occurrences.append(occ)
                        if sym: symbols.append(sym)

            # Look for config-like patterns
            for pattern in patterns['config_like']:
                match = pattern.search(line)
                if match:
                    name = match.group(1)
                    if name and len(name) > 1:
                        occ, sym = self._create_symbol_for_document(
                            line_num, name, file_path, scip_pb2.Constant, "", 
                            f"Configuration key in {language}",
                            relationships
                        )
                        if occ: occurrences.append(occ)
                        if sym: symbols.append(sym)
        
        return occurrences, symbols

    def _analyze_file_for_document(self, file_path: str, language: str) -> tuple:
        """Create a basic file-level symbol for non-code files."""
        file_name = Path(file_path).stem
        
        symbol_id = self.symbol_manager.create_local_symbol(
            language="text",
            file_path=file_path,
            symbol_path=[file_name],
            descriptor=""
        )
        
        # Create symbol information only (no occurrence for file-level symbols)
        symbol_info = self._create_symbol_information(
            symbol_id, file_name, scip_pb2.File, f"{language.title()} file"
        )
        
        return [], [symbol_info]

    def _create_symbol_for_document(self, line_num: int, name: str, file_path: str, 
                                   symbol_kind: int, descriptor: str, description: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple:
        """Create a symbol with occurrence and information for document."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="text",
            file_path=file_path,
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
        
        # Create symbol information
        symbol_relationships = relationships.get(symbol_id, []) if relationships else []
        scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
        symbol_info = self._create_symbol_information(
            symbol_id, name, symbol_kind, description, scip_relationships
        )
        
        return occurrence, symbol_info

    # Utility methods
    def _is_code_like(self, content: str) -> bool:
        """Determine if the file appears to be code-like."""
        # Check for common code indicators
        code_indicators = [
            r'\bfunction\b', r'\bdef\b', r'\bclass\b', r'\binterface\b',
            r'\bstruct\b', r'\benum\b', r'\bconst\b', r'\bvar\b', r'\blet\b',
            r'[{}();]', r'=\s*function', r'=>', r'\bif\b', r'\bfor\b', r'\bwhile\b'
        ]
        
        code_score = 0
        for pattern in code_indicators:
            if re.search(pattern, content, re.IGNORECASE):
                code_score += 1
        
        # If we find multiple code indicators, treat as code
        return code_score >= 3

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
                                  symbol_kind: int, description: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = display_name
        symbol_info.kind = symbol_kind
        symbol_info.documentation.append(description)
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        return symbol_info