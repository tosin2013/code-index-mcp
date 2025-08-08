# pylint: disable=no-member
"""Python-specific SCIP indexing strategy using AST analysis."""

import ast
import logging
import os
from typing import List, Set, Dict, Any, Optional, Tuple
from pathlib import Path
from .base_strategy import SCIPIndexerStrategy, ConversionError
from ..proto import scip_pb2


logger = logging.getLogger(__name__)


class PythonStrategy(SCIPIndexerStrategy):
    """Strategy for Python files using AST analysis."""

    SUPPORTED_EXTENSIONS = {'.py', '.pyw'}

    def __init__(self, priority: int = 90):
        """Initialize the Python strategy."""
        super().__init__(priority)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def generate_scip_documents(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """
        Generate SCIP documents for Python files.

        Args:
            files: List of Python file paths to index
            project_path: Root path of the project

        Returns:
            List of SCIP Document objects
        """
        documents = []

        for file_path in files:
            try:
                document = self._analyze_python_file(file_path, project_path)
                if document:
                    documents.append(document)
            except Exception as e:
                logger.error(f"Failed to analyze Python file {file_path}: {str(e)}")
                # Continue with other files

        logger.info(f"Python strategy generated {len(documents)} documents")
        return documents

    def _analyze_python_file(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """
        Analyze a single Python file using AST.

        Args:
            file_path: Path to the Python file
            project_path: Root path of the project

        Returns:
            SCIP Document object or None if analysis fails
        """
        try:
            # Resolve full file path
            if not os.path.isabs(file_path):
                full_path = os.path.join(project_path, file_path)
            else:
                full_path = file_path

            # Read file content
            content = self._read_file_content(full_path)
            if content is None:
                logger.warning(f"Could not read content from {file_path}")
                return None

            # Parse Python AST
            try:
                tree = ast.parse(content, filename=full_path)
            except SyntaxError as e:
                logger.warning(f"Syntax error in {file_path}: {e}")
                return None

            # Create SCIP document
            document = scip_pb2.Document()
            document.relative_path = self._get_relative_path(file_path, project_path)
            document.language = 'python'

            # Analyze AST and extract symbols
            analyzer = PythonASTAnalyzer(document.relative_path, content)
            analyzer.visit(tree)

            # Add occurrences and symbols to document
            document.occurrences.extend(analyzer.occurrences)
            document.symbols.extend(analyzer.symbols)

            logger.debug(f"Analyzed Python file {document.relative_path}: "
                        f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

            return document

        except Exception as e:
            logger.error(f"Failed to analyze Python file {file_path}: {str(e)}")
            raise ConversionError(f"Failed to analyze {file_path}: {str(e)}") from e

    def _read_file_content(self, file_path: str) -> Optional[str]:
        """Read content from a Python file."""
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue

            logger.warning(f"Could not decode {file_path} with any encoding")
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
            # If path is not under project_path, return as-is
            return file_path

    def get_strategy_name(self) -> str:
        """Return a human-readable name for this strategy."""
        return "Python(AST)"


class PythonASTAnalyzer(ast.NodeVisitor):
    """AST visitor that extracts Python symbols and creates SCIP data."""

    def __init__(self, file_path: str, content: str):
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []
        self.scope_stack: List[str] = []  # Track current scope for qualified names

    def _create_symbol_id(self, name: str, kind: str) -> str:
        """Create a SCIP symbol identifier."""
        # Build qualified name from scope stack
        if self.scope_stack:
            qualified_name = '.'.join(self.scope_stack + [name])
        else:
            qualified_name = name

        # SCIP symbol format: scheme package_manager package_name descriptors
        # For local files, we use a simplified format
        clean_path = self.file_path.replace('/', '.').replace('\\', '.').replace('.py', '')
        return f"local {clean_path} {qualified_name}{kind}"

    def _create_occurrence(self, node: ast.AST, symbol: str, roles: int, syntax_kind: int) -> scip_pb2.Occurrence:
        """Create a SCIP occurrence for an AST node."""
        occurrence = scip_pb2.Occurrence()

        # Set position range
        if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
            start_line = node.lineno - 1  # SCIP uses 0-based line numbers
            start_col = node.col_offset

            # Try to get end position
            if hasattr(node, 'end_lineno') and hasattr(node, 'end_col_offset'):
                end_line = node.end_lineno - 1
                end_col = node.end_col_offset
            else:
                # Estimate end position based on node name if it's an identifier
                if hasattr(node, 'id'):
                    end_line = start_line
                    end_col = start_col + len(node.id)
                elif hasattr(node, 'name'):
                    end_line = start_line
                    end_col = start_col + len(node.name)
                else:
                    end_line = start_line
                    end_col = start_col + 1

            occurrence.range.start.extend([start_line, start_col])
            occurrence.range.end.extend([end_line, end_col])

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

    def visit_FunctionDef(self, node: ast.FunctionDef):  # pylint: disable=invalid-name
        """Visit function definition."""
        # Create symbol
        symbol = self._create_symbol_id(node.name, '().')

        # Create definition occurrence
        occurrence = self._create_occurrence(
            node, symbol, scip_pb2.Definition, scip_pb2.IdentifierFunctionDefinition
        )
        self.occurrences.append(occurrence)

        # Create symbol information
        documentation = []
        if ast.get_docstring(node):
            documentation.append(ast.get_docstring(node))

        # Add parameter information
        if node.args.args:
            params = [arg.arg for arg in node.args.args]
            documentation.append(f"Parameters: {', '.join(params)}")

        # Add decorator information
        if node.decorator_list:
            decorator_names = []
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorator_names.append(decorator.id)
                elif isinstance(decorator, ast.Attribute):
                    decorator_names.append(ast.unparse(decorator))
            if decorator_names:
                documentation.append(f"Decorators: {', '.join(decorator_names)}")

        symbol_info = self._create_symbol_information(
            symbol, node.name, scip_pb2.Function, documentation
        )
        self.symbols.append(symbol_info)

        # Enter function scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):  # pylint: disable=invalid-name
        """Visit async function definition."""
        # Similar to FunctionDef but mark as async
        symbol = self._create_symbol_id(node.name, '().')

        occurrence = self._create_occurrence(
            node, symbol, scip_pb2.Definition, scip_pb2.IdentifierFunctionDefinition
        )
        self.occurrences.append(occurrence)

        documentation = ["Async function"]
        if ast.get_docstring(node):
            documentation.append(ast.get_docstring(node))

        symbol_info = self._create_symbol_information(
            symbol, node.name, scip_pb2.Function, documentation
        )
        self.symbols.append(symbol_info)

        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef):  # pylint: disable=invalid-name
        """Visit class definition."""
        # Create symbol
        symbol = self._create_symbol_id(node.name, '#')

        # Create definition occurrence
        occurrence = self._create_occurrence(
            node, symbol, scip_pb2.Definition, scip_pb2.IdentifierType
        )
        self.occurrences.append(occurrence)

        # Create symbol information
        documentation = []
        if ast.get_docstring(node):
            documentation.append(ast.get_docstring(node))

        # Add base class information
        if node.bases:
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(ast.unparse(base))
            if base_names:
                documentation.append(f"Inherits from: {', '.join(base_names)}")

        # Add decorator information
        if node.decorator_list:
            decorator_names = []
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorator_names.append(decorator.id)
            if decorator_names:
                documentation.append(f"Decorators: {', '.join(decorator_names)}")

        symbol_info = self._create_symbol_information(
            symbol, node.name, scip_pb2.Class, documentation
        )
        self.symbols.append(symbol_info)

        # Enter class scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Import(self, node: ast.Import):  # pylint: disable=invalid-name
        """Visit import statement."""
        for alias in node.names:
            module_name = alias.name
            symbol = f"external {module_name}"

            occurrence = self._create_occurrence(
                node, symbol, scip_pb2.Import, scip_pb2.Identifier
            )
            self.occurrences.append(occurrence)

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):  # pylint: disable=invalid-name
        """Visit from ... import ... statement."""
        if node.module:
            for alias in node.names:
                import_name = alias.name
                symbol = f"external {node.module} {import_name}"

                occurrence = self._create_occurrence(
                    node, symbol, scip_pb2.Import, scip_pb2.Identifier
                )
                self.occurrences.append(occurrence)

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):  # pylint: disable=invalid-name
        """Visit name references."""
        # Only create occurrences for name references (not definitions)
        if isinstance(node.ctx, ast.Load):
            # This is a reference to a name
            symbol = self._create_symbol_id(node.id, '')

            occurrence = self._create_occurrence(
                node, symbol, scip_pb2.Read, scip_pb2.Identifier
            )
            self.occurrences.append(occurrence)

        self.generic_visit(node)
