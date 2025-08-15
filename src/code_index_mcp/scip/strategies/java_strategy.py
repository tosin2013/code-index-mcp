"""Java SCIP indexing strategy v4 - Tree-sitter based with Python strategy architecture."""

import logging
import os
from typing import List, Optional, Dict, Any, Set

try:
    import tree_sitter
    from tree_sitter_java import language as java_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType


logger = logging.getLogger(__name__)


class JavaStrategy(SCIPIndexerStrategy):
    """SCIP-compliant Java indexing strategy using Tree-sitter with Python strategy architecture."""

    SUPPORTED_EXTENSIONS = {'.java'}

    def __init__(self, priority: int = 95):
        """Initialize the Java strategy v4."""
        super().__init__(priority)
        
        if not TREE_SITTER_AVAILABLE:
            raise StrategyError("Tree-sitter not available for Java strategy")
        
        # Initialize Java parser
        java_lang = tree_sitter.Language(java_language())
        self.parser = tree_sitter.Parser(java_lang)

    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        return extension.lower() in self.SUPPORTED_EXTENSIONS and TREE_SITTER_AVAILABLE

    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "java"

    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return TREE_SITTER_AVAILABLE

    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from Java files."""
        logger.debug(f"JavaStrategy Phase 1: Processing {len(files)} files for symbol collection")
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
        logger.debug(f"JavaStrategy Phase 2: Generating documents for {len(files)} files")
        processed_count = 0
        error_count = 0
        total_occurrences = 0
        total_symbols = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                document = self._analyze_java_file(file_path, project_path, relationships)
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
        Build relationships between Java symbols.
        
        Args:
            files: List of file paths to process
            project_path: Project root path
            
        Returns:
            Dictionary mapping symbol_id -> [(target_symbol_id, relationship_type), ...]
        """
        logger.debug(f"JavaStrategy: Building symbol relationships for {len(files)} files")
        
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_java_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"JavaStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships

    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single Java file."""
        content = self._read_file_content(file_path)
        if not content:
            return

        tree = self._parse_content(content)
        if not tree:
            return

        relative_path = self._get_relative_path(file_path, project_path)
        self._collect_symbols_from_tree(tree, relative_path, content)

    def _analyze_java_file(self, file_path: str, project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> Optional[scip_pb2.Document]:
        """Analyze a single Java file and generate complete SCIP document."""
        content = self._read_file_content(file_path)
        if not content:
            return None

        tree = self._parse_content(content)
        if not tree:
            return None

        # Create SCIP document
        document = scip_pb2.Document()
        document.relative_path = self._get_relative_path(file_path, project_path)
        document.language = self.get_language_name()

        # Analyze Tree-sitter AST and generate occurrences
        self.position_calculator = PositionCalculator(content)
        occurrences, symbols = self._analyze_tree_for_document(tree, document.relative_path, content, relationships)

        # Add results to document
        document.occurrences.extend(occurrences)
        document.symbols.extend(symbols)

        logger.debug(f"Analyzed Java file {document.relative_path}: "
                    f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

        return document

    def _parse_content(self, content: str) -> Optional[tree_sitter.Tree]:
        """Parse Java content with Tree-sitter."""
        try:
            return self.parser.parse(bytes(content, "utf8"))
        except Exception as e:
            logger.error(f"Failed to parse Java content: {e}")
            return None

    def _collect_symbols_from_tree(self, tree: tree_sitter.Tree, file_path: str, content: str) -> None:
        """Collect symbols from Tree-sitter tree using integrated visitor (Phase 1)."""
        root = tree.root_node
        
        for node in self._walk_tree(root):
            if node.type == "class_declaration":
                self._register_class_symbol(node, file_path, content)
            elif node.type == "interface_declaration":
                self._register_interface_symbol(node, file_path, content)
            elif node.type == "enum_declaration":
                self._register_enum_symbol(node, file_path, content)
            elif node.type == "method_declaration":
                self._register_method_symbol(node, file_path, content)
            elif node.type == "constructor_declaration":
                self._register_constructor_symbol(node, file_path, content)

    def _analyze_tree_for_document(self, tree: tree_sitter.Tree, file_path: str, content: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> tuple[List[scip_pb2.Occurrence], List[scip_pb2.SymbolInformation]]:
        """Analyze Tree-sitter tree to generate occurrences and symbols for SCIP document (Phase 2)."""
        occurrences = []
        symbols = []
        root = tree.root_node
        
        for node in self._walk_tree(root):
            if node.type == "class_declaration":
                symbol_id = self._create_class_symbol_id(node, file_path, content)
                occurrence = self._create_class_occurrence(node, symbol_id)
                symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                
                symbol_info = self._create_class_symbol_info(node, symbol_id, content, scip_relationships)
                
                if occurrence:
                    occurrences.append(occurrence)
                if symbol_info:
                    symbols.append(symbol_info)
                    
            elif node.type == "interface_declaration":
                symbol_id = self._create_interface_symbol_id(node, file_path, content)
                occurrence = self._create_interface_occurrence(node, symbol_id)
                symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                
                symbol_info = self._create_interface_symbol_info(node, symbol_id, content, scip_relationships)
                
                if occurrence:
                    occurrences.append(occurrence)
                if symbol_info:
                    symbols.append(symbol_info)
                    
            elif node.type in ["method_declaration", "constructor_declaration"]:
                symbol_id = self._create_method_symbol_id(node, file_path, content)
                occurrence = self._create_method_occurrence(node, symbol_id)
                symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                
                symbol_info = self._create_method_symbol_info(node, symbol_id, content, scip_relationships)
                
                if occurrence:
                    occurrences.append(occurrence)
                if symbol_info:
                    symbols.append(symbol_info)
        
        return occurrences, symbols

    def _extract_java_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships from a single Java file."""
        logger.debug(f"JavaStrategy: Starting relationship extraction from {file_path}")
        
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"JavaStrategy: No content found in {file_path}")
            return {}
        
        tree = self._parse_content(content)
        if not tree:
            logger.debug(f"JavaStrategy: Failed to parse {file_path} with Tree-sitter")
            return {}
        
        relative_path = self._get_relative_path(file_path, project_path)
        relationships = self._extract_relationships_from_tree(tree, relative_path, content)
        
        logger.debug(f"JavaStrategy: Extracted {len(relationships)} relationships from {relative_path}")
        return relationships

    def _extract_relationships_from_tree(self, tree: tree_sitter.Tree, file_path: str, content: str) -> Dict[str, List[tuple]]:
        """Extract relationships from Tree-sitter AST."""
        relationships = {}
        root = tree.root_node
        
        for node in self._walk_tree(root):
            if node.type == "class_declaration":
                # Extract inheritance relationships
                class_symbol_id = self._create_class_symbol_id(node, file_path, content)
                
                # Find extends clause
                for child in node.children:
                    if child.type == "superclass":
                        for grandchild in child.children:
                            if grandchild.type == "type_identifier":
                                parent_name = grandchild.text.decode()
                                parent_symbol_id = self._create_class_symbol_id_by_name(parent_name, file_path)
                                if class_symbol_id not in relationships:
                                    relationships[class_symbol_id] = []
                                relationships[class_symbol_id].append((parent_symbol_id, InternalRelationshipType.INHERITS))
                
                # Find implements clause
                for child in node.children:
                    if child.type == "super_interfaces":
                        for interface_list in child.children:
                            if interface_list.type == "type_list":
                                for interface_type in interface_list.children:
                                    if interface_type.type == "type_identifier":
                                        interface_name = interface_type.text.decode()
                                        interface_symbol_id = self._create_interface_symbol_id_by_name(interface_name, file_path)
                                        if class_symbol_id not in relationships:
                                            relationships[class_symbol_id] = []
                                        relationships[class_symbol_id].append((interface_symbol_id, InternalRelationshipType.IMPLEMENTS))
        
        return relationships

    # Helper methods for Tree-sitter node processing
    def _walk_tree(self, node: tree_sitter.Node):
        """Walk through all nodes in a Tree-sitter tree."""
        yield node
        for child in node.children:
            yield from self._walk_tree(child)

    def _get_node_identifier(self, node: tree_sitter.Node) -> Optional[str]:
        """Get the identifier name from a Tree-sitter node."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode()
        return None

    def _get_package_name(self, tree: tree_sitter.Tree) -> str:
        """Extract package name from Tree-sitter tree."""
        root = tree.root_node
        for node in self._walk_tree(root):
            if node.type == "package_declaration":
                for child in node.children:
                    if child.type == "scoped_identifier":
                        return child.text.decode()
        return ""

    # Symbol creation methods (similar to Python strategy)
    def _register_class_symbol(self, node: tree_sitter.Node, file_path: str, content: str) -> None:
        """Register a class symbol definition."""
        name = self._get_node_identifier(node)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
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
            documentation=["Java class"]
        )

    def _register_interface_symbol(self, node: tree_sitter.Node, file_path: str, content: str) -> None:
        """Register an interface symbol definition."""
        name = self._get_node_identifier(node)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="#"
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Interface,
            display_name=name,
            documentation=["Java interface"]
        )

    def _register_enum_symbol(self, node: tree_sitter.Node, file_path: str, content: str) -> None:
        """Register an enum symbol definition."""
        name = self._get_node_identifier(node)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="#"
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Enum,
            display_name=name,
            documentation=["Java enum"]
        )

    def _register_method_symbol(self, node: tree_sitter.Node, file_path: str, content: str) -> None:
        """Register a method symbol definition."""
        name = self._get_node_identifier(node)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="()."
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Method,
            display_name=name,
            documentation=["Java method"]
        )

    def _register_constructor_symbol(self, node: tree_sitter.Node, file_path: str, content: str) -> None:
        """Register a constructor symbol definition."""
        name = self._get_node_identifier(node)
        if not name:
            return
            
        symbol_id = self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="()."
        )
        
        dummy_range = scip_pb2.Range()
        dummy_range.start.extend([0, 0])
        dummy_range.end.extend([0, 1])
        
        self.reference_resolver.register_symbol_definition(
            symbol_id=symbol_id,
            file_path=file_path,
            definition_range=dummy_range,
            symbol_kind=scip_pb2.Method,
            display_name=name,
            documentation=["Java constructor"]
        )

    # Symbol ID creation methods
    def _create_class_symbol_id(self, node: tree_sitter.Node, file_path: str, content: str) -> str:
        """Create symbol ID for a class."""
        name = self._get_node_identifier(node)
        if not name:
            return ""
        return self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="#"
        )

    def _create_class_symbol_id_by_name(self, name: str, file_path: str) -> str:
        """Create symbol ID for a class by name."""
        return self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="#"
        )

    def _create_interface_symbol_id(self, node: tree_sitter.Node, file_path: str, content: str) -> str:
        """Create symbol ID for an interface."""
        name = self._get_node_identifier(node)
        if not name:
            return ""
        return self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="#"
        )

    def _create_interface_symbol_id_by_name(self, name: str, file_path: str) -> str:
        """Create symbol ID for an interface by name."""
        return self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="#"
        )

    def _create_method_symbol_id(self, node: tree_sitter.Node, file_path: str, content: str) -> str:
        """Create symbol ID for a method."""
        name = self._get_node_identifier(node)
        if not name:
            return ""
        return self.symbol_manager.create_local_symbol(
            language="java",
            file_path=file_path,
            symbol_path=[name],
            descriptor="()."
        )

    # Occurrence creation methods (using PositionCalculator)
    def _create_class_occurrence(self, node: tree_sitter.Node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for class."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierType
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_interface_occurrence(self, node: tree_sitter.Node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for interface."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierType
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    def _create_method_occurrence(self, node: tree_sitter.Node, symbol_id: str) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence for method."""
        if not self.position_calculator:
            return None
            
        try:
            range_obj = self.position_calculator.tree_sitter_node_to_range(node)
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = scip_pb2.Definition
            occurrence.syntax_kind = scip_pb2.IdentifierFunction
            occurrence.range.CopyFrom(range_obj)
            return occurrence
        except:
            return None

    # Symbol information creation methods (with relationships)
    def _create_class_symbol_info(self, node: tree_sitter.Node, symbol_id: str, content: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for class."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = self._get_node_identifier(node) or "Unknown"
        symbol_info.kind = scip_pb2.Class
        
        # Add documentation
        symbol_info.documentation.append("Java class")
        
        # Add relationships if provided
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_interface_symbol_info(self, node: tree_sitter.Node, symbol_id: str, content: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for interface."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = self._get_node_identifier(node) or "Unknown"
        symbol_info.kind = scip_pb2.Interface
        
        symbol_info.documentation.append("Java interface")
        
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_method_symbol_info(self, node: tree_sitter.Node, symbol_id: str, content: str, relationships: Optional[List[scip_pb2.Relationship]] = None) -> scip_pb2.SymbolInformation:
        """Create SCIP symbol information for method."""
        symbol_info = scip_pb2.SymbolInformation()
        symbol_info.symbol = symbol_id
        symbol_info.display_name = self._get_node_identifier(node) or "Unknown"
        symbol_info.kind = scip_pb2.Method
        
        # Determine if it's a constructor or method
        if node.type == "constructor_declaration":
            symbol_info.documentation.append("Java constructor")
        else:
            symbol_info.documentation.append("Java method")
        
        if relationships and self.relationship_manager:
            self.relationship_manager.add_relationships_to_symbol(symbol_info, relationships)
        
        return symbol_info

    def _create_scip_relationships(self, symbol_relationships: List[tuple]) -> List[scip_pb2.Relationship]:
        """Convert internal relationships to SCIP relationships."""
        scip_relationships = []
        for target_symbol_id, relationship_type in symbol_relationships:
            relationship = scip_pb2.Relationship()
            relationship.symbol = target_symbol_id
            relationship.is_reference = True
            # Map relationship types to SCIP if needed
            scip_relationships.append(relationship)
        return scip_relationships