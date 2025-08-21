"""Java tree-sitter analyzer implementation."""

from typing import Iterator, Optional, Set, List, Dict, Any
from ..types import SCIPContext
from ..base.language_analyzer import BaseLanguageAnalyzer

try:
    import tree_sitter
    from tree_sitter_java import language as java_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class JavaTreeSitterAnalyzer(BaseLanguageAnalyzer):
    """Java analyzer using tree-sitter for AST parsing."""
    
    def __init__(self):
        """Initialize the Java tree-sitter analyzer."""
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("Tree-sitter Java library not available")
        
        java_lang = tree_sitter.Language(java_language())
        self.parser = tree_sitter.Parser(java_lang)
        self._processed_nodes: Set[int] = set()
    
    def parse(self, content: str, filename: str = "<unknown>"):
        """Parse Java source code into tree-sitter AST."""
        try:
            return self.parser.parse(bytes(content, 'utf8'))
        except Exception as e:
            raise SyntaxError(f"Java syntax error in {filename}: {e}")
    
    def walk(self, tree) -> Iterator:
        """Walk tree-sitter tree nodes, avoiding duplicates."""
        for node in self._walk_node(tree.root_node):
            node_id = id(node)
            if node_id not in self._processed_nodes:
                self._processed_nodes.add(node_id)
                yield node
    
    def _walk_node(self, node) -> Iterator:
        """Recursively walk tree nodes."""
        yield node
        for child in node.children:
            yield from self._walk_node(child)
    
    def is_symbol_definition(self, node) -> bool:
        """Check if tree-sitter node represents a symbol definition."""
        return node.type in {
            'class_declaration',
            'interface_declaration',
            'enum_declaration',
            'method_declaration',
            'constructor_declaration',
            'field_declaration',
            'local_variable_declaration',
            'formal_parameter',
            'annotation_type_declaration',
        }
    
    def is_symbol_reference(self, node) -> bool:
        """Check if tree-sitter node represents a symbol reference."""
        return node.type in {
            'identifier',
            'type_identifier',
            'method_invocation',
            'field_access',
        }
    
    def get_symbol_name(self, node) -> Optional[str]:
        """Extract symbol name from tree-sitter node."""
        if node.type in ['class_declaration', 'interface_declaration', 'enum_declaration',
                        'method_declaration', 'constructor_declaration', 'annotation_type_declaration']:
            identifier_node = self._find_child_by_type(node, 'identifier')
            if identifier_node:
                return identifier_node.text.decode('utf8')
        
        elif node.type == 'field_declaration':
            # Field declarations can have multiple declarators
            declarator = self._find_child_by_type(node, 'variable_declarator')
            if declarator:
                identifier = self._find_child_by_type(declarator, 'identifier')
                if identifier:
                    return identifier.text.decode('utf8')
        
        elif node.type == 'local_variable_declaration':
            declarator = self._find_child_by_type(node, 'variable_declarator')
            if declarator:
                identifier = self._find_child_by_type(declarator, 'identifier')
                if identifier:
                    return identifier.text.decode('utf8')
        
        elif node.type == 'formal_parameter':
            identifier = self._find_child_by_type(node, 'identifier')
            if identifier:
                return identifier.text.decode('utf8')
        
        elif node.type in ['identifier', 'type_identifier']:
            return node.text.decode('utf8')
        
        return None
    
    def get_node_position(self, node) -> tuple:
        """Get position information from tree-sitter node."""
        start_line = node.start_point[0]
        start_col = node.start_point[1]
        end_line = node.end_point[0]
        end_col = node.end_point[1]
        
        return (start_line, start_col, end_line, end_col)
    
    def extract_class_info(self, tree) -> List[Dict[str, Any]]:
        """Extract class information from the AST."""
        classes = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'class_declaration':
                class_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'class',
                    'position': self.get_node_position(node),
                    'modifiers': self._extract_modifiers(node),
                    'superclass': self._extract_superclass(node),
                    'interfaces': self._extract_implemented_interfaces(node),
                    'methods': self._extract_class_methods(node),
                    'fields': self._extract_class_fields(node),
                }
                classes.append(class_info)
        
        return classes
    
    def extract_interface_info(self, tree) -> List[Dict[str, Any]]:
        """Extract interface information from the AST."""
        interfaces = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'interface_declaration':
                interface_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'interface',
                    'position': self.get_node_position(node),
                    'modifiers': self._extract_modifiers(node),
                    'extends': self._extract_extended_interfaces(node),
                    'methods': self._extract_interface_methods(node),
                }
                interfaces.append(interface_info)
        
        return interfaces
    
    def extract_method_info(self, tree) -> List[Dict[str, Any]]:
        """Extract method information from the AST."""
        methods = []
        
        for node in self._walk_node(tree.root_node):
            if node.type in ['method_declaration', 'constructor_declaration']:
                method_info = {
                    'name': self.get_symbol_name(node),
                    'type': 'constructor' if node.type == 'constructor_declaration' else 'method',
                    'position': self.get_node_position(node),
                    'modifiers': self._extract_modifiers(node),
                    'return_type': self._extract_return_type(node),
                    'parameters': self._extract_method_parameters(node),
                    'throws': self._extract_throws_clause(node),
                }
                methods.append(method_info)
        
        return methods
    
    def extract_import_statements(self, tree) -> List[str]:
        """Extract import statements from the AST."""
        imports = []
        
        for node in self._walk_node(tree.root_node):
            if node.type == 'import_declaration':
                import_path = self._extract_import_path(node)
                if import_path:
                    imports.append(import_path)
        
        return imports
    
    def extract_package_declaration(self, tree) -> Optional[str]:
        """Extract package declaration from the AST."""
        for node in self._walk_node(tree.root_node):
            if node.type == 'package_declaration':
                return self._extract_package_name(node)
        return None
    
    def _find_child_by_type(self, node, node_type: str):
        """Find first child node of specified type."""
        for child in node.children:
            if child.type == node_type:
                return child
        return None
    
    def _find_children_by_type(self, node, node_type: str) -> List:
        """Find all child nodes of specified type."""
        children = []
        for child in node.children:
            if child.type == node_type:
                children.append(child)
        return children
    
    def _extract_modifiers(self, node) -> List[str]:
        """Extract modifiers from a declaration node."""
        modifiers = []
        modifiers_node = self._find_child_by_type(node, 'modifiers')
        if modifiers_node:
            for child in modifiers_node.children:
                if child.type in ['public', 'private', 'protected', 'static', 'final', 
                                'abstract', 'synchronized', 'volatile', 'transient', 'native']:
                    modifiers.append(child.type)
        return modifiers
    
    def _extract_superclass(self, class_node) -> Optional[str]:
        """Extract superclass name from class declaration."""
        superclass_node = self._find_child_by_type(class_node, 'superclass')
        if superclass_node:
            type_node = self._find_child_by_type(superclass_node, 'type_identifier')
            if type_node:
                return type_node.text.decode('utf8')
        return None
    
    def _extract_implemented_interfaces(self, class_node) -> List[str]:
        """Extract implemented interface names from class declaration."""
        interfaces = []
        interfaces_node = self._find_child_by_type(class_node, 'super_interfaces')
        if interfaces_node:
            for interface_node in self._find_children_by_type(interfaces_node, 'type_identifier'):
                interfaces.append(interface_node.text.decode('utf8'))
        return interfaces
    
    def _extract_extended_interfaces(self, interface_node) -> List[str]:
        """Extract extended interface names from interface declaration."""
        interfaces = []
        extends_node = self._find_child_by_type(interface_node, 'extends_interfaces')
        if extends_node:
            for interface_node in self._find_children_by_type(extends_node, 'type_identifier'):
                interfaces.append(interface_node.text.decode('utf8'))
        return interfaces
    
    def _extract_class_methods(self, class_node) -> List[str]:
        """Extract method names from class declaration."""
        methods = []
        for child in class_node.children:
            if child.type in ['method_declaration', 'constructor_declaration']:
                method_name = self.get_symbol_name(child)
                if method_name:
                    methods.append(method_name)
        return methods
    
    def _extract_class_fields(self, class_node) -> List[str]:
        """Extract field names from class declaration."""
        fields = []
        for child in class_node.children:
            if child.type == 'field_declaration':
                field_name = self.get_symbol_name(child)
                if field_name:
                    fields.append(field_name)
        return fields
    
    def _extract_interface_methods(self, interface_node) -> List[str]:
        """Extract method names from interface declaration."""
        methods = []
        for child in interface_node.children:
            if child.type == 'method_declaration':
                method_name = self.get_symbol_name(child)
                if method_name:
                    methods.append(method_name)
        return methods
    
    def _extract_return_type(self, method_node) -> Optional[str]:
        """Extract return type from method declaration."""
        # Constructor declarations don't have return types
        if method_node.type == 'constructor_declaration':
            return None
        
        # Look for various return type patterns
        for child in method_node.children:
            if child.type in ['type_identifier', 'primitive_type', 'array_type', 'generic_type']:
                return child.text.decode('utf8')
        return None
    
    def _extract_method_parameters(self, method_node) -> List[Dict[str, str]]:
        """Extract parameter information from method declaration."""
        parameters = []
        formal_params_node = self._find_child_by_type(method_node, 'formal_parameters')
        if formal_params_node:
            for param_node in self._find_children_by_type(formal_params_node, 'formal_parameter'):
                param_name = self.get_symbol_name(param_node)
                param_type = self._extract_parameter_type(param_node)
                if param_name:
                    parameters.append({
                        'name': param_name,
                        'type': param_type or 'unknown'
                    })
        return parameters
    
    def _extract_parameter_type(self, param_node) -> Optional[str]:
        """Extract parameter type from formal parameter node."""
        for child in param_node.children:
            if child.type in ['type_identifier', 'primitive_type', 'array_type', 'generic_type']:
                return child.text.decode('utf8')
        return None
    
    def _extract_throws_clause(self, method_node) -> List[str]:
        """Extract throws clause from method declaration."""
        throws = []
        throws_node = self._find_child_by_type(method_node, 'throws')
        if throws_node:
            for exception_node in self._find_children_by_type(throws_node, 'type_identifier'):
                throws.append(exception_node.text.decode('utf8'))
        return throws
    
    def _extract_import_path(self, import_node) -> Optional[str]:
        """Extract import path from import declaration."""
        for child in import_node.children:
            if child.type in ['scoped_identifier', 'identifier']:
                return child.text.decode('utf8')
        return None
    
    def _extract_package_name(self, package_node) -> Optional[str]:
        """Extract package name from package declaration."""
        for child in package_node.children:
            if child.type in ['scoped_identifier', 'identifier']:
                return child.text.decode('utf8')
        return None