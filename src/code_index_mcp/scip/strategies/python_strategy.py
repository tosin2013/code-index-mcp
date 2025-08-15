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

    def _generate_documents_with_references(self, files: List[str], project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> List[scip_pb2.Document]:
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
                document = self._analyze_python_file(file_path, project_path, relationships)
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

        # Collect symbols using integrated visitor
        relative_path = self._get_relative_path(file_path, project_path)
        self._collect_symbols_from_ast(tree, relative_path, content)
        logger.debug(f"Symbol collection - {relative_path}")

    def _analyze_python_file(self, file_path: str, project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> Optional[scip_pb2.Document]:
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
        
        occurrences, symbols = self._analyze_ast_for_document(tree, relative_path, content, relationships)
        
        # Add results to document
        document.occurrences.extend(occurrences)
        document.symbols.extend(symbols)
        
        logger.debug(f"Document analysis - {relative_path}: "
                    f"-> {len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

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
        
        return self._extract_relationships_from_ast(tree, file_path, project_path)

    def _collect_symbols_from_ast(self, tree: ast.AST, file_path: str, content: str) -> None:
        """Collect symbols from AST using integrated visitor."""
        scope_stack = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                self._register_function_symbol(node, node.name, file_path, scope_stack)
            elif isinstance(node, ast.ClassDef):
                self._register_class_symbol(node, node.name, file_path, scope_stack)

    def _analyze_ast_for_document(self, tree: ast.AST, file_path: str, content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[List[scip_pb2.Occurrence], List[scip_pb2.SymbolInformation]]:
        """Analyze AST to generate occurrences and symbols for SCIP document."""
        occurrences = []
        symbols = []
        scope_stack = []
        
        # Simple implementation - can be enhanced later
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                symbol_id = self._create_function_symbol_id(node.name, file_path, scope_stack)
                occurrence = self._create_function_occurrence(node, symbol_id)
                # Get relationships for this symbol
                symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                
                symbol_info = self._create_function_symbol_info(node, symbol_id, scip_relationships)
                
                if occurrence:
                    occurrences.append(occurrence)
                if symbol_info:
                    symbols.append(symbol_info)
                    
            elif isinstance(node, ast.ClassDef):
                symbol_id = self._create_class_symbol_id(node.name, file_path, scope_stack)
                occurrence = self._create_class_occurrence(node, symbol_id)
                # Get relationships for this symbol
                symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                
                symbol_info = self._create_class_symbol_info(node, symbol_id, scip_relationships)
                
                if occurrence:
                    occurrences.append(occurrence)
                if symbol_info:
                    symbols.append(symbol_info)
        
        return occurrences, symbols

    def _extract_relationships_from_ast(self, tree: ast.AST, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships from AST."""
        relationships = {}
        scope_stack = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Extract inheritance relationships
                relative_path = self._get_relative_path(file_path, project_path)
                class_symbol_id = self._create_class_symbol_id(node.name, relative_path, scope_stack)
                
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        parent_symbol_id = self._create_class_symbol_id(base.id, relative_path, scope_stack)
                        if class_symbol_id not in relationships:
                            relationships[class_symbol_id] = []
                        relationships[class_symbol_id].append((parent_symbol_id, InternalRelationshipType.INHERITS))
                        
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Extract function call relationships
                relative_path = self._get_relative_path(file_path, project_path)
                function_symbol_id = self._create_function_symbol_id(node.name, relative_path, scope_stack)
                
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            target_symbol_id = self._create_function_symbol_id(child.func.id, relative_path, scope_stack)
                            if function_symbol_id not in relationships:
                                relationships[function_symbol_id] = []
                            relationships[function_symbol_id].append((target_symbol_id, InternalRelationshipType.CALLS))
        
        return relationships

    # Helper methods
    def _register_function_symbol(self, node: ast.AST, name: str, file_path: str, scope_stack: List[str]) -> None:
        """Register a function symbol definition."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="python",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="()."
        )
        
        # Create a dummy range for registration
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Function,
            display_name=name,
            documentation=["Python function"]
        )

    def _register_class_symbol(self, node: ast.AST, name: str, file_path: str, scope_stack: List[str]) -> None:
        """Register a class symbol definition."""
        symbol_id = self.symbol_manager.create_local_symbol(
            language="python",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="#"
        )
        
        # Create a dummy range for registration
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Class,
            display_name=name,
            documentation=["Python class"]
        )

    def _create_function_symbol_id(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for function."""
        return self.symbol_manager.create_local_symbol(
            language="python",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="()."
        )

    def _create_class_symbol_id(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for class."""
        return self.symbol_manager.create_local_symbol(
            language="python",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="#"
        )

    def _create_function_occurrence(self, node: ast.AST, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for function."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.ast_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierFunction
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_class_occurrence(self, node: ast.AST, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for class."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.ast_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierType
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_function_symbol_info(self, node: ast.AST, symbol_id: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for function."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = node.name
        symbol_info.kind = scip_pb2.Function
        
        # Add docstring if available
        docstring = ast.get_docstring(node)
        if docstring:
            symbol_info.documentation.append(docstring)
        
        # Add relationships if provided
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_class_symbol_info(self, node: ast.AST, symbol_id: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for class."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = node.name
        symbol_info.kind = scip_pb2.Class
        
        # Add docstring if available
        docstring = ast.get_docstring(node)
        if docstring:
            symbol_info.documentation.append(docstring)
        
        # Add relationships if provided
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info