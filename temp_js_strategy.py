"""JavaScript/TypeScript SCIP indexing strategy - SCIP standard compliant."""

import logging
import os
from typing import List, Optional, Dict, Any, Set

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType

# Tree-sitter imports
try:
    import tree_sitter
    from tree_sitter_javascript import language as js_language
    from tree_sitter_typescript import language as ts_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    tree_sitter = None
    js_language = None
    ts_language = None

logger = logging.getLogger(__name__)


class JavaScriptStrategy(SCIPIndexerStrategy):
    """SCIP-compliant JavaScript/TypeScript indexing strategy using Tree-sitter."""

    SUPPORTED_EXTENSIONS = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}

    def __init__(self, priority: int = 95):
        """Initialize the JavaScript/TypeScript strategy."""
        super().__init__(priority)
        
        # Initialize parsers if Tree-sitter is available
        if TREE_SITTER_AVAILABLE:
            try:
                js_lang = tree_sitter.Language(js_language())
                ts_lang = tree_sitter.Language(ts_language())
                
                self.js_parser = tree_sitter.Parser(js_lang)
                self.ts_parser = tree_sitter.Parser(ts_lang)
                logger.info("JavaScript strategy initialized with Tree-sitter support")
            except Exception as e:
                logger.warning(f"Failed to initialize Tree-sitter parsers: {e}")
                self.js_parser = None
                self.ts_parser = None
        else:
            self.js_parser = None
            self.ts_parser = None
            raise StrategyError("Tree-sitter not available for JavaScript/TypeScript strategy")

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "javascript"  # Use 'javascript' for both JS and TS

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        if not TREE_SITTER_AVAILABLE or not self.js_parser or not self.ts_parser:
            raise StrategyError("Tree-sitter not available for JavaScript/TypeScript strategy")
        return True

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from JavaScript/TypeScript files."""
        logger.debug(f"JavaScriptStrategy Phase 1: Processing {len(files)} files for symbol collection")
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
        logger.debug(f"JavaScriptStrategy Phase 2: Generating documents for {len(files)} files")
        processed_count = 0
        error_count = 0
        total_occurrences = 0
        total_symbols = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                document = self._analyze_js_file(file_path, project_path, relationships)
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

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """
        Build relationships between JavaScript/TypeScript symbols.
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        logger.debug(f"JavaScriptStrategy: Building symbol relationships for {len(files)} files")
        
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_js_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"JavaScriptStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single JavaScript/TypeScript file."""
        
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {os.path.relpath(file_path, project_path)}")
            return

        # Parse with Tree-sitter
        try:
            tree = self._parse_js_content(content, file_path)
            if not tree or not tree.root_node:
                raise StrategyError(f"Failed to parse {os.path.relpath(file_path, project_path)}")
        except Exception as e:
            raise StrategyError(f"Parse error in {os.path.relpath(file_path, project_path)}: {e}")

        # Collect symbols using Tree-sitter
        relative_path = self._get_relative_path(file_path, project_path)
        self._collect_symbols_from_tree(tree, relative_path, content)
        logger.debug(f"Symbol collection - {relative_path}")

    def _analyze_js_file(self, file_path: str, project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> Optional[scip_pb2.Document]:
        """Analyze a single JavaScript/TypeScript file and generate complete SCIP document."""
        relative_path = self._get_relative_path(file_path, project_path)
        
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {relative_path}")
            return None

        # Parse with Tree-sitter
        try:
            tree = self._parse_js_content(content, file_path)
            if not tree or not tree.root_node:
                raise StrategyError(f"Failed to parse {relative_path}")
        except Exception as e:
            raise StrategyError(f"Parse error in {relative_path}: {e}")

        # Create SCIP document
        document = scip_pb2.Document()
        document.relative_path = relative_path
        document.language = self.get_language_name()

        # Analyze tree and generate occurrences
        self.position_calculator = PositionCalculator(content)
        occurrences, symbols = self._analyze_tree_for_document(tree, relative_path, content, relationships)
        
        # Add results to document
        document.occurrences.extend(occurrences)
        document.symbols.extend(symbols)
        
        logger.debug(f"Document analysis - {relative_path}: "
                    f"-> {len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _extract_js_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """
        Extract relationships from a single JavaScript/TypeScript file.
        
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
            tree = self._parse_js_content(content, file_path)
            if not tree or not tree.root_node:
                raise StrategyError(f"Failed to parse {file_path} for relationship extraction")
        except Exception as e:
            raise StrategyError(f"Parse error in {file_path}: {e}")
        
        return self._extract_relationships_from_tree(tree, file_path, project_path)

    def _parse_js_content(self, content: str, file_path: str):
        """Parse JavaScript/TypeScript content using Tree-sitter parser."""
        if not TREE_SITTER_AVAILABLE or not self.js_parser or not self.ts_parser:
            raise StrategyError("Tree-sitter not available for JavaScript/TypeScript parsing")
            
        # Determine parser based on file extension
        extension = os.path.splitext(file_path)[1].lower()
        
        if extension in {'.ts', '.tsx'}:
            parser = self.ts_parser
        else:
            parser = self.js_parser
        
        try:
            content_bytes = content.encode('utf-8')
            return parser.parse(content_bytes)
        except Exception as e:
            raise StrategyError(f"Failed to parse {file_path} with Tree-sitter: {e}")
    

    def _collect_symbols_from_tree(self, tree, file_path: str, content: str) -> None:
        """Collect symbols from Tree-sitter tree."""
        
        def visit_node(node, scope_stack=[]):
            node_type = node.type
            
            if node_type in ['function_declaration', 'method_definition', 'arrow_function']:
                self._register_js_function(node, file_path, scope_stack)
            elif node_type in ['class_declaration']:
                self._register_js_class(node, file_path, scope_stack)
                
            # Recursively visit children
            for child in node.children:
                visit_node(child, scope_stack)
        
        visit_node(tree.root_node)

    def _analyze_tree_for_document(self, tree, file_path: str, content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple:
        """Analyze Tree-sitter tree to generate occurrences and symbols for SCIP document."""
        occurrences = []
        symbols = []
        
        def visit_node(node, scope_stack=[]):
            node_type = node.type
            
            if node_type in ['function_declaration', 'method_definition', 'arrow_function']:
                name = self._get_js_function_name(node)
                if name:
                    symbol_id = self._create_js_function_symbol_id(name, file_path, scope_stack)
                    occurrence = self._create_js_function_occurrence(node, symbol_id)
                    symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                    scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                    symbol_info = self._create_js_function_symbol_info(node, symbol_id, name, scip_relationships)
                    
                    if occurrence:
                        occurrences.append(occurrence)
                    if symbol_info:
                        symbols.append(symbol_info)
                        
            elif node_type in ['class_declaration']:
                name = self._get_js_class_name(node)
                if name:
                    symbol_id = self._create_js_class_symbol_id(name, file_path, scope_stack)
                    occurrence = self._create_js_class_occurrence(node, symbol_id)
                    symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                    scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                    symbol_info = self._create_js_class_symbol_info(node, symbol_id, name, scip_relationships)
                    
                    if occurrence:
                        occurrences.append(occurrence)
                    if symbol_info:
                        symbols.append(symbol_info)
                        
            # Recursively visit children
            for child in node.children:
                visit_node(child, scope_stack)
        
        visit_node(tree.root_node)
        return occurrences, symbols

    def _extract_relationships_from_tree(self, tree, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships from Tree-sitter tree."""
        relationships = {}
        
        def visit_node(node, scope_stack=[]):
            node_type = node.type
            
            if node_type == 'class_declaration':
                # Extract inheritance relationships for ES6 classes
                class_name = self._get_js_class_name(node)
                if class_name:
                    class_symbol_id = self._create_js_class_symbol_id(class_name, file_path, scope_stack)
                    
                    # Look for extends clause
                    for child in node.children:
                        if child.type == 'class_heritage':
                            for heritage_child in child.children:
                                if heritage_child.type == 'identifier':
                                    parent_name = self._get_node_text(heritage_child)
                                    if parent_name:
                                        parent_symbol_id = self._create_js_class_symbol_id(parent_name, file_path, scope_stack)
                                        if class_symbol_id not in relationships:
                                            relationships[class_symbol_id] = []
                                        relationships[class_symbol_id].append((parent_symbol_id, InternalRelationshipType.INHERITS))
                        
            elif node_type in ['function_declaration', 'method_definition', 'arrow_function']:
                # Extract function call relationships
                function_name = self._get_js_function_name(node)
                if function_name:
                    function_symbol_id = self._create_js_function_symbol_id(function_name, file_path, scope_stack)
                    
                    # Find call expressions within this function
                    self._extract_calls_from_node(node, function_symbol_id, relationships, file_path, scope_stack)
                        
            # Recursively visit children
            for child in node.children:
                visit_node(child, scope_stack)
        
        visit_node(tree.root_node)
        return relationships

    def _extract_calls_from_node(self, node, source_symbol_id: str, relationships: Dict, file_path: str, scope_stack: List):
        """Extract function calls from a node."""
        
        def visit_for_calls(n):
            if n.type == 'call_expression':
                # Get the function being called
                function_node = n.children[0] if n.children else None
                if function_node:
                    if function_node.type == 'identifier':
                        target_name = self._get_node_text(function_node)
                        if target_name:
                            target_symbol_id = self._create_js_function_symbol_id(target_name, file_path, scope_stack)
                            if source_symbol_id not in relationships:
                                relationships[source_symbol_id] = []
                            relationships[source_symbol_id].append((target_symbol_id, InternalRelationshipType.CALLS))
                            
            for child in n.children:
                visit_for_calls(child)
        
        visit_for_calls(node)

    # Helper methods for Tree-sitter node processing
    def _get_node_text(self, node) -> Optional[str]:
        """Get text content of a Tree-sitter node."""
        if hasattr(node, 'text'):
            try:
                return node.text.decode('utf-8')
            except:
                pass
        return None

    def _get_js_function_name(self, node) -> Optional[str]:
        """Extract function name from function node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._get_node_text(child)
        return None

    def _get_js_class_name(self, node) -> Optional[str]:
        """Extract class name from class node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._get_node_text(child)
        return None

    # Symbol registration and creation methods
    def _register_js_function(self, node, file_path: str, scope_stack: List[str]) -> None:
        """Register a JavaScript function symbol definition."""
        name = self._get_js_function_name(node)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="javascript",
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
            documentation=["JavaScript function"]
        )

    def _register_js_class(self, node, file_path: str, scope_stack: List[str]) -> None:
        """Register a JavaScript class symbol definition."""
        name = self._get_js_class_name(node)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="javascript",
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
            documentation=["JavaScript class"]
        )

    def _create_js_function_symbol_id(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for JavaScript function."""
        return self.symbol_manager.create_local_symbol(
            language="javascript",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="()."
        )

    def _create_js_class_symbol_id(self, name: str, file_path: str, scope_stack: List[str]) -> str:
        """Create symbol ID for JavaScript class."""
        return self.symbol_manager.create_local_symbol(
            language="javascript",
            file_path=file_path,
            symbol_path=scope_stack + [name],
            descriptor="#"
        )

    def _create_js_function_occurrence(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for JavaScript function."""
        if not self.position_calculator:
            return None
            
        try:
            # Convert Tree-sitter node to range (simplified)
            range_obj = scip_pb2.Range()
            range_obj.start.extend([node.start_point[0], node.start_point[1]])
            range_obj.end.extend([node.end_point[0], node.end_point[1]])
            
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierFunction
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_js_class_occurrence(self, node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for JavaScript class."""
        if not self.position_calculator:
            return None
            
        try:
            # Convert Tree-sitter node to range (simplified)
            range_obj = scip_pb2.Range()
            range_obj.start.extend([node.start_point[0], node.start_point[1]])
            range_obj.end.extend([node.end_point[0], node.end_point[1]])
            
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierType
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_js_function_symbol_info(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for JavaScript function."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        symbol_info.kind = scip_pb2.Function
        symbol_info.documentation.append("JavaScript function")
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        return symbol_info

    def _create_js_class_symbol_info(self, node, symbol_id: str, name: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for JavaScript class."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = name
        symbol_info.kind = scip_pb2.Class
        symbol_info.documentation.append("JavaScript class")
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        return symbol_info
