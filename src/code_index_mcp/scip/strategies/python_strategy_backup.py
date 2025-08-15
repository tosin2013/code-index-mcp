"""Python SCIP indexing strategy - SCIP standard compliant."""

import ast
import logging
import os
from typing import List, Optional, Dict, Any, Set
from pathlib import Path

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType


logger = logging.getLogger(__name__)


class PythonStrategy(SCIPIndexerStrategy):
    """SCIP-compliant Python indexing strategy using AST analysis."""

    SUPPORTED_EXTENSIONS = {'.py', '.pyw'}

    def __init__(self, priority: int = 90):
        """Initialize the Python strategy."""
        super().__init__(priority)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "python"

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from Python files."""
        logger.debug(f"PythonStrategy Phase 1: Processing {len(files)} files for symbol collection")
        processed_count = 0
        error_count = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                self._collect_symbols_from_file(file_path, project_path)
                processed_count += 1
                
                if i % 10 == 0 or i == len(files):  # Progress every 10 files or at end
                    logger.debug(f"Phase 1 progress: {i}/{len(files)} files, last file: {relative_path}")
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"Phase 1 failed for {relative_path}: {e}")
                continue
        
        logger.info(f"Phase 1 summary: {processed_count} files processed, {error_count} errors")

    def _generate_documents_with_references(self, files: List[str], project_path: str) -> List[scip_pb2.Document]:
        """Phase 2: Generate complete SCIP documents with resolved references."""
        documents = []
        logger.debug(f"PythonStrategy Phase 2: Generating documents for {len(files)} files")
        processed_count = 0
        error_count = 0
        total_occurrences = 0
        total_symbols = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                document = self._analyze_python_file(file_path, project_path)
                if document:
                    documents.append(document)
                    total_occurrences += len(document.occurrences)
                    total_symbols += len(document.symbols)
                    processed_count += 1
                    
                if i % 10 == 0 or i == len(files):  # Progress every 10 files or at end
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
        """Collect symbol definitions from a single Python file."""
        
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {os.path.relpath(file_path, project_path)}")
            return

        # Parse AST
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {os.path.relpath(file_path, project_path)}: {e}")
            return

        # Collect symbols
        relative_path = self._get_relative_path(file_path, project_path)
        collector = PythonSymbolCollector(
            relative_path, content, self.symbol_manager, self.reference_resolver
        )
        collector.visit(tree)
        logger.debug(f"Symbol collection - {relative_path}")

    def _analyze_python_file(self, file_path: str, project_path: str) -> Optional[scip_pb2.Document]:
        """Analyze a single Python file and generate complete SCIP document."""
        relative_path = self._get_relative_path(file_path, project_path)
        
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {relative_path}")
            return None

        # Parse AST
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {relative_path}: {e}")
            return None

        # Create SCIP document
        document = scip_pb2.Document()
        document.relative_path = relative_path
        document.language = self.get_language_name()

        # Analyze AST and generate occurrences
        self.position_calculator = PositionCalculator(content)
        
        analyzer = PythonAnalyzer(
            document.relative_path,
            content,
            self.symbol_manager,
            self.position_calculator,
            self.reference_resolver
        )
        
        analyzer.visit(tree)

        # Add results to document
        document.occurrences.extend(analyzer.occurrences)
        document.symbols.extend(analyzer.symbols)
        
        logger.debug(f"Document analysis - {relative_path}: "
                    f"-> {len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document


class PythonSymbolCollector(ast.NodeVisitor):
    """AST visitor that collects Python symbol definitions (Phase 1)."""

    def __init__(self, file_path: str, content: str, symbol_manager, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.symbol_manager = symbol_manager
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []  # Track current scope

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition."""
        self._register_function_symbol(node, node.name, is_async=False)
        
        # Enter function scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition."""
        self._register_function_symbol(node, node.name, is_async=True)
        
        # Enter function scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition."""
        self._register_class_symbol(node, node.name)
        
        # Enter class scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def _register_function_symbol(self, node: ast.AST, name: str, is_async: bool = False):
        """Register a function symbol definition."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="python",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor="()."
        )
        
        # Create a dummy range for registration (will be calculated properly in Phase 2)
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        documentation = []
        if is_async:
            documentation.append("Async function")
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=self.file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Function,
            display_name=name,
            documentation=documentation
        )

    def _register_class_symbol(self, node: ast.AST, name: str):
        """Register a class symbol definition."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="python",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor="#"
        )
        
        # Create a dummy range for registration
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=self.file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Class,
            display_name=name,
            documentation=["Python class"]
        )


class PythonAnalyzer(ast.NodeVisitor):
    """AST visitor that generates complete SCIP data (Phase 2)."""

    def __init__(self, file_path: str, content: str, symbol_manager, position_calculator, reference_resolver):
        self.file_path = file_path
        self.content = content
        self.symbol_manager = symbol_manager
        self.position_calculator = position_calculator
        self.reference_resolver = reference_resolver
        self.scope_stack: List[str] = []
        
        # Results
        self.occurrences: List[scip_pb2.Occurrence] = []
        self.symbols: List[scip_pb2.SymbolInformation] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition."""
        self._handle_function_definition(node, node.name, is_async=False)
        
        # Enter function scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition."""
        self._handle_function_definition(node, node.name, is_async=True)
        
        # Enter function scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition."""
        self._handle_class_definition(node, node.name)
        
        # Enter class scope
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Import(self, node: ast.Import):
        """Visit import statement."""
        for alias in node.names:
            self._handle_import(node, alias.name, alias.asname)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Visit from ... import ... statement."""
        module_name = node.module or ""
        for alias in node.names:
            self._handle_from_import(node, module_name, alias.name, alias.asname)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        """Visit name references."""
        if isinstance(node.ctx, ast.Load):
            # This is a reference to a name
            self._handle_name_reference(node, node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        """Visit attribute access."""
        if isinstance(node.ctx, ast.Load):
            self._handle_attribute_reference(node, node.attr)
        self.generic_visit(node)

    def _handle_function_definition(self, node: ast.AST, name: str, is_async: bool = False):
        """Handle function definition."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="python",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor="()."
        )
        
        # Create definition occurrence
        range_obj = self.position_calculator.ast_node_to_range(node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierFunction
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        documentation = []
        if is_async:
            documentation.append("Async function")
        
        # Add docstring if available
        docstring = ast.get_docstring(node)
        if docstring:
            documentation.append(docstring)
        
        # Add parameter information
        if hasattr(node, 'args') and node.args.args:
            params = [arg.arg for arg in node.args.args]
            documentation.append(f"Parameters: {', '.join(params)}")
        
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Function, documentation
        )
        self.symbols.append(symbol_info)

    def _handle_class_definition(self, node: ast.AST, name: str):
        """Handle class definition."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="python",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [name],
            descriptor="#"
        )
        
        # Create definition occurrence
        range_obj = self.position_calculator.ast_node_to_range(node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Definition, scip_pb2.IdentifierType
        )
        self.occurrences.append(occurrence)
        
        # Create symbol information
        documentation = ["Python class"]
        
        # Add docstring if available
        docstring = ast.get_docstring(node)
        if docstring:
            documentation.append(docstring)
        
        # Add base class information
        if hasattr(node, 'bases') and node.bases:
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(ast.unparse(base))
            if base_names:
                documentation.append(f"Inherits from: {', '.join(base_names)}")
        
        symbol_info = self._create_symbol_information(
            symbol_id, name, scip_pb2.Class, documentation
        )
        self.symbols.append(symbol_info)

    def _handle_import(self, node: ast.AST, module_name: str, alias_name: Optional[str]):
        """Handle import statement with moniker support."""
        display_name = alias_name or module_name
        
        # Determine if this is a standard library or external package import
        if self._is_stdlib_module(module_name):
            # Standard library import
            symbol_id = self.symbol_manager.create_stdlib_symbol(
                language="python",
                module_name=module_name,
                symbol_name="",
                descriptor=""
            )
        elif self._is_external_package(module_name):
            # External package import using moniker system
            symbol_id = self.symbol_manager.create_external_symbol(
                language="python",
                package_name=self._extract_package_name(module_name),
                module_path=self._extract_module_path(module_name),
                symbol_name="",
                alias=alias_name
            )
        else:
            # Local project import
            symbol_id = self.symbol_manager.create_local_symbol(
                language="python",
                file_path=f"{module_name.replace('.', '/')}.py",
                symbol_path=[],
                descriptor=""
            )
        
        range_obj = self.position_calculator.ast_node_to_range(node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Import, scip_pb2.IdentifierNamespace
        )
        self.occurrences.append(occurrence)

    def _handle_from_import(self, node: ast.AST, module_name: str, import_name: str, alias_name: Optional[str]):
        """Handle from ... import ... statement with moniker support."""
        display_name = alias_name or import_name
        
        # Determine if this is a standard library or external package import
        if self._is_stdlib_module(module_name):
            # Standard library import
            symbol_id = self.symbol_manager.create_stdlib_symbol(
                language="python",
                module_name=module_name,
                symbol_name=import_name,
                descriptor=""
            )
        elif self._is_external_package(module_name):
            # External package import using moniker system
            symbol_id = self.symbol_manager.create_external_symbol(
                language="python",
                package_name=self._extract_package_name(module_name),
                module_path=self._extract_module_path(module_name),
                symbol_name=import_name,
                alias=alias_name,
                descriptor=self._infer_descriptor_from_name(import_name)
            )
        else:
            # Local project import
            symbol_id = self.symbol_manager.create_local_symbol(
                language="python",
                file_path=f"{module_name.replace('.', '/')}.py",
                symbol_path=[import_name],
                descriptor=self._infer_descriptor_from_name(import_name)
            )
        
        range_obj = self.position_calculator.ast_node_to_range(node)
        occurrence = self._create_occurrence(
            symbol_id, range_obj, scip_pb2.Import, scip_pb2.Identifier
        )
        self.occurrences.append(occurrence)

    def _handle_name_reference(self, node: ast.AST, name: str):
        """Handle name reference with import resolution."""
        # First try to resolve to imported external symbol
        imported_symbol_id = self.symbol_manager.resolve_import_reference(name, self.file_path)
        
        if imported_symbol_id:
            # This is a reference to an imported symbol
            range_obj = self.position_calculator.ast_node_to_range(node)
            occurrence = self._create_occurrence(
                imported_symbol_id, range_obj, 0, scip_pb2.Identifier  # 0 = reference role
            )
            self.occurrences.append(occurrence)
            return
            
        # Try to resolve local reference
        resolved_symbol_id = self.reference_resolver.resolve_reference_by_name(
            symbol_name=name,
            context_file=self.file_path,
            context_scope=self.scope_stack
        )
        
        if resolved_symbol_id:
            # Create reference occurrence
            range_obj = self.position_calculator.ast_node_to_range(node)
            occurrence = self._create_occurrence(
                resolved_symbol_id, range_obj, 0, scip_pb2.Identifier  # 0 = reference role
            )
            self.occurrences.append(occurrence)
            
            # Register the reference
            self.reference_resolver.register_symbol_reference(
                symbol_id=resolved_symbol_id,
                file_path=self.file_path,
                reference_range=range_obj,
                context_scope=self.scope_stack
            )

    def _handle_attribute_reference(self, node: ast.AST, attr_name: str):
        """Handle attribute reference."""
        # For now, create a simple local reference
        # In a full implementation, this would resolve through the object type
        range_obj = self.position_calculator.ast_node_to_range(node)
        
        # Try to create a local symbol for the attribute
        symbol_id = self.symbol_manager.create_local_symbol(
            language="python",
            file_path=self.file_path,
            symbol_path=self.scope_stack + [attr_name],
            descriptor=""
        )
        
        occurrence = self._create_occurrence(
            symbol_id, range_obj, 0, scip_pb2.Identifier
        )
        self.occurrences.append(occurrence)

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

    def _is_stdlib_module(self, module_name: str) -> bool:
        """Check if module is part of Python standard library."""
        # Standard library modules (partial list - could be expanded)
        stdlib_modules = {
            'os', 'sys', 'json', 'datetime', 'collections', 'itertools',
            'functools', 'typing', 're', 'math', 'random', 'pathlib',
            'urllib', 'http', 'email', 'csv', 'xml', 'html', 'sqlite3',
            'threading', 'asyncio', 'multiprocessing', 'subprocess',
            'unittest', 'logging', 'configparser', 'argparse', 'io',
            'shutil', 'glob', 'tempfile', 'zipfile', 'tarfile',
            'pickle', 'base64', 'hashlib', 'hmac', 'secrets', 'uuid',
            'time', 'calendar', 'zoneinfo', 'locale', 'gettext',
            'decimal', 'fractions', 'statistics', 'cmath', 'bisect',
            'heapq', 'queue', 'weakref', 'copy', 'pprint', 'reprlib',
            'enum', 'dataclasses', 'contextlib', 'abc', 'atexit',
            'traceback', 'gc', 'inspect', 'site', 'warnings', 'keyword',
            'builtins', '__future__', 'imp', 'importlib', 'pkgutil',
            'modulefinder', 'runpy', 'ast', 'dis', 'pickletools'
        }
        
        # Get the root module name (e.g., 'os.path' -> 'os')
        root_module = module_name.split('.')[0]
        return root_module in stdlib_modules

    def _is_external_package(self, module_name: str) -> bool:
        """Check if module is from an external package (not stdlib, not local)."""
        # If it's stdlib, it's not external
        if self._is_stdlib_module(module_name):
            return False
            
        # Check if it starts with known external package patterns
        # (This could be enhanced with actual dependency parsing)
        external_patterns = [
            'numpy', 'pandas', 'scipy', 'matplotlib', 'seaborn',
            'sklearn', 'torch', 'tensorflow', 'keras', 'cv2',
            'requests', 'urllib3', 'httpx', 'aiohttp',
            'flask', 'django', 'fastapi', 'starlette',
            'sqlalchemy', 'psycopg2', 'pymongo', 'redis',
            'pytest', 'unittest2', 'mock', 'nose',
            'click', 'typer', 'argparse', 'fire',
            'pyyaml', 'toml', 'configparser', 'python-dotenv',
            'pillow', 'imageio', 'opencv', 'scikit',
            'beautifulsoup4', 'lxml', 'scrapy',
            'celery', 'rq', 'dramatiq',
            'pydantic', 'marshmallow', 'cerberus',
            'cryptography', 'bcrypt', 'passlib'
        ]
        
        root_module = module_name.split('.')[0]
        return any(root_module.startswith(pattern) for pattern in external_patterns)

    def _extract_package_name(self, module_name: str) -> str:
        """Extract package name from module path."""
        # For most packages, the root module is the package name
        root_module = module_name.split('.')[0]
        
        # Handle special cases where module name differs from package name
        package_mapping = {
            'cv2': 'opencv-python',
            'sklearn': 'scikit-learn',
            'PIL': 'Pillow',
            'bs4': 'beautifulsoup4',
            'yaml': 'PyYAML',
        }
        
        return package_mapping.get(root_module, root_module)

    def _extract_module_path(self, module_name: str) -> str:
        """Extract module path within package."""
        parts = module_name.split('.')
        if len(parts) > 1:
            # Return submodule path (everything after package name)
            return '/'.join(parts[1:])
        return ""

    def _infer_descriptor_from_name(self, name: str) -> str:
        """Infer SCIP descriptor from symbol name."""
        # Simple heuristics for Python symbols
        if name.isupper():  # Constants like MAX_SIZE
            return "."
        elif name.istitle():  # Classes like MyClass
            return "#"
        elif name.endswith('Error') or name.endswith('Exception'):  # Exception classes
            return "#"
        else:  # Functions, variables, etc.
            return "()." if name.islower() else "."

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """
        Build relationships between Python symbols.
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        logger.debug(f"PythonStrategy: Building symbol relationships for {len(files)} files")
        
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"PythonStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships

    def _extract_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """
        Extract relationships from a single Python file.
        
        Args:
            file_path: File to analyze
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        content = self._read_file_content(file_path)
        if not content:
            return {}
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return {}
        
        extractor = PythonRelationshipExtractor(
            file_path=file_path,
            project_path=project_path,
            symbol_manager=self.symbol_manager
        )
        
        extractor.visit(tree)
        return extractor.get_relationships()


class PythonRelationshipExtractor(ast.NodeVisitor):
    """
    AST visitor for extracting Python symbol relationships.
    """
    
    def __init__(self, file_path: str, project_path: str, symbol_manager):
        self.file_path = file_path
        self.project_path = project_path
        self.symbol_manager = symbol_manager
        self.relationships = {}
        self.current_scope = []
        self.current_class = None
        self.current_function = None
        
    def get_relationships(self) -> Dict[str, List[tuple]]:
        """Get extracted relationships."""
        return self.relationships
    
    def _add_relationship(self, source_symbol_id: str, target_symbol_id: str, relationship_type: InternalRelationshipType):
        """Add a relationship to the collection."""
        if source_symbol_id not in self.relationships:
            self.relationships[source_symbol_id] = []
        self.relationships[source_symbol_id].append((target_symbol_id, relationship_type))
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition and extract inheritance relationships."""
        old_class = self.current_class
        self.current_class = node.name
        self.current_scope.append(node.name)
        
        # Generate class symbol ID
        class_symbol_id = self._generate_symbol_id(self.current_scope, "#")
        
        # Extract inheritance relationships
        for base in node.bases:
            if isinstance(base, ast.Name):
                # Direct inheritance: class Child(Parent)
                parent_symbol_id = self._generate_symbol_id([base.id], "#")
                self._add_relationship(
                    class_symbol_id, 
                    parent_symbol_id, 
                    InternalRelationshipType.INHERITS
                )
            elif isinstance(base, ast.Attribute):
                # Module-qualified inheritance: class Child(module.Parent)
                parent_name = self._extract_attribute_name(base)
                parent_symbol_id = self._generate_symbol_id([parent_name], "#")
                self._add_relationship(
                    class_symbol_id,
                    parent_symbol_id,
                    InternalRelationshipType.INHERITS
                )
        
        # Visit class body
        self.generic_visit(node)
        
        self.current_scope.pop()
        self.current_class = old_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition and extract call relationships."""
        old_function = self.current_function
        self.current_function = node.name
        self.current_scope.append(node.name)
        
        # Generate function symbol ID
        function_symbol_id = self._generate_symbol_id(self.current_scope, "().")
        
        # Extract function calls from body
        call_extractor = FunctionCallExtractor(function_symbol_id, self)
        for stmt in node.body:
            call_extractor.visit(stmt)
        
        # Visit function body
        self.generic_visit(node)
        
        self.current_scope.pop()
        self.current_function = old_function
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition."""
        # Treat async functions the same as regular functions
        self.visit_FunctionDef(node)
    
    def _generate_symbol_id(self, symbol_path: List[str], descriptor: str) -> str:
        """Generate SCIP symbol ID for a symbol."""
        if self.symbol_manager:
            return self.symbol_manager.create_local_symbol(
                language="python",
                file_path=self.file_path,
                symbol_path=symbol_path,
                descriptor=descriptor
            )
        return f"local {'/'.join(symbol_path)}{descriptor}"
    
    def _extract_attribute_name(self, node: ast.Attribute) -> str:
        """Extract full name from attribute node (e.g., 'module.Class')."""
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._extract_attribute_name(node.value)}.{node.attr}"
        return node.attr


class FunctionCallExtractor(ast.NodeVisitor):
    """
    Specialized visitor for extracting function calls within a function.
    """
    
    def __init__(self, source_function_id: str, parent_extractor):
        self.source_function_id = source_function_id
        self.parent_extractor = parent_extractor
    
    def visit_Call(self, node: ast.Call):
        """Visit function call and extract relationship."""
        target_name = None
        
        if isinstance(node.func, ast.Name):
            # Simple function call: func()
            target_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Method call or module function call: obj.method() or module.func()
            target_name = self.parent_extractor._extract_attribute_name(node.func)
        
        if target_name:
            # Generate target symbol ID
            target_symbol_id = self.parent_extractor._generate_symbol_id([target_name], "().")
            
            # Add call relationship
            self.parent_extractor._add_relationship(
                self.source_function_id,
                target_symbol_id,
                InternalRelationshipType.CALLS
            )
        
        # Continue visiting nested calls
        self.generic_visit(node)