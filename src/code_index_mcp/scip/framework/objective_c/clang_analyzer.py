"""Objective-C libclang analyzer implementation."""

from typing import Iterator, Optional, Set, List, Dict, Any
from ..types import SCIPContext
from ..base.language_analyzer import BaseLanguageAnalyzer

try:
    import clang.cindex as clang
    from clang.cindex import CursorKind, TypeKind
    LIBCLANG_AVAILABLE = True
except ImportError:
    LIBCLANG_AVAILABLE = False
    clang = None
    CursorKind = None
    TypeKind = None


class ObjectiveCClangAnalyzer(BaseLanguageAnalyzer):
    """Objective-C analyzer using libclang for AST parsing."""
    
    def __init__(self):
        """Initialize the Objective-C libclang analyzer."""
        if not LIBCLANG_AVAILABLE:
            raise ImportError("libclang library not available")
        
        self.index = clang.Index.create()
        self._processed_cursors: Set[int] = set()
    
    def parse(self, content: str, filename: str = "<unknown>"):
        """Parse Objective-C source code into libclang AST."""
        try:
            # Create a temporary file for parsing
            args = ['-x', 'objective-c', '-I/usr/include', '-I/usr/local/include']
            return self.index.parse(filename, args=args, unsaved_files=[(filename, content)])
        except Exception as e:
            raise SyntaxError(f"Objective-C syntax error in {filename}: {e}")
    
    def walk(self, translation_unit) -> Iterator:
        """Walk libclang cursor nodes, avoiding duplicates."""
        for cursor in self._walk_cursor(translation_unit.cursor):
            cursor_id = hash((cursor.spelling, cursor.location.line, cursor.location.column))
            if cursor_id not in self._processed_cursors:
                self._processed_cursors.add(cursor_id)
                yield cursor
    
    def _walk_cursor(self, cursor) -> Iterator:
        """Recursively walk cursor nodes."""
        yield cursor
        for child in cursor.get_children():
            yield from self._walk_cursor(child)
    
    def is_symbol_definition(self, cursor) -> bool:
        """Check if libclang cursor represents a symbol definition."""
        return cursor.kind in {
            CursorKind.OBJC_INTERFACE_DECL,
            CursorKind.OBJC_IMPLEMENTATION_DECL,
            CursorKind.OBJC_PROTOCOL_DECL,
            CursorKind.OBJC_CATEGORY_DECL,
            CursorKind.OBJC_CATEGORY_IMPL_DECL,
            CursorKind.OBJC_INSTANCE_METHOD_DECL,
            CursorKind.OBJC_CLASS_METHOD_DECL,
            CursorKind.OBJC_PROPERTY_DECL,
            CursorKind.OBJC_IVAR_DECL,
            CursorKind.CLASS_DECL,
            CursorKind.STRUCT_DECL,
            CursorKind.UNION_DECL,
            CursorKind.ENUM_DECL,
            CursorKind.FUNCTION_DECL,
            CursorKind.VAR_DECL,
            CursorKind.FIELD_DECL,
            CursorKind.TYPEDEF_DECL,
            CursorKind.MACRO_DEFINITION,
            CursorKind.ENUM_CONSTANT_DECL,
        }
    
    def is_symbol_reference(self, cursor) -> bool:
        """Check if libclang cursor represents a symbol reference."""
        return cursor.kind in {
            CursorKind.DECL_REF_EXPR,
            CursorKind.MEMBER_REF_EXPR,
            CursorKind.OBJC_MESSAGE_EXPR,
            CursorKind.OBJC_SELECTOR_REF,
            CursorKind.OBJC_PROTOCOL_REF,
            CursorKind.OBJC_CLASS_REF,
            CursorKind.OBJC_SUPER_CLASS_REF,
            CursorKind.TYPE_REF,
            CursorKind.CALL_EXPR,
        }
    
    def get_symbol_name(self, cursor) -> Optional[str]:
        """Extract symbol name from libclang cursor."""
        return cursor.spelling if cursor.spelling else None
    
    def get_node_position(self, cursor) -> tuple:
        """Get position information from libclang cursor."""
        start_line = cursor.location.line - 1  # Convert to 0-based
        start_col = cursor.location.column - 1
        
        # Estimate end position based on symbol name length
        if cursor.spelling:
            end_line = start_line
            end_col = start_col + len(cursor.spelling)
        else:
            end_line = start_line
            end_col = start_col + 1
        
        return (start_line, start_col, end_line, end_col)
    
    def extract_interface_info(self, translation_unit) -> List[Dict[str, Any]]:
        """Extract Objective-C interface information from the AST."""
        interfaces = []
        
        for cursor in self._walk_cursor(translation_unit.cursor):
            if cursor.kind == CursorKind.OBJC_INTERFACE_DECL:
                interface_info = {
                    'name': cursor.spelling,
                    'type': 'interface',
                    'position': self.get_node_position(cursor),
                    'superclass': self._extract_superclass(cursor),
                    'protocols': self._extract_protocols(cursor),
                    'methods': self._extract_interface_methods(cursor),
                    'properties': self._extract_interface_properties(cursor),
                }
                interfaces.append(interface_info)
        
        return interfaces
    
    def extract_implementation_info(self, translation_unit) -> List[Dict[str, Any]]:
        """Extract Objective-C implementation information from the AST."""
        implementations = []
        
        for cursor in self._walk_cursor(translation_unit.cursor):
            if cursor.kind == CursorKind.OBJC_IMPLEMENTATION_DECL:
                impl_info = {
                    'name': cursor.spelling,
                    'type': 'implementation',
                    'position': self.get_node_position(cursor),
                    'methods': self._extract_implementation_methods(cursor),
                    'ivars': self._extract_implementation_ivars(cursor),
                }
                implementations.append(impl_info)
        
        return implementations
    
    def extract_protocol_info(self, translation_unit) -> List[Dict[str, Any]]:
        """Extract Objective-C protocol information from the AST."""
        protocols = []
        
        for cursor in self._walk_cursor(translation_unit.cursor):
            if cursor.kind == CursorKind.OBJC_PROTOCOL_DECL:
                protocol_info = {
                    'name': cursor.spelling,
                    'type': 'protocol',
                    'position': self.get_node_position(cursor),
                    'parent_protocols': self._extract_parent_protocols(cursor),
                    'methods': self._extract_protocol_methods(cursor),
                    'properties': self._extract_protocol_properties(cursor),
                }
                protocols.append(protocol_info)
        
        return protocols
    
    def extract_method_info(self, translation_unit) -> List[Dict[str, Any]]:
        """Extract method information from the AST."""
        methods = []
        
        for cursor in self._walk_cursor(translation_unit.cursor):
            if cursor.kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
                method_info = {
                    'name': cursor.spelling,
                    'type': 'instance_method' if cursor.objc_method_kind == 1 else 'class_method',
                    'position': self.get_node_position(cursor),
                    'return_type': self._extract_return_type(cursor),
                    'parameters': self._extract_method_parameters(cursor),
                    'is_definition': cursor.is_definition(),
                }
                methods.append(method_info)
        
        return methods
    
    def extract_property_info(self, translation_unit) -> List[Dict[str, Any]]:
        """Extract property information from the AST."""
        properties = []
        
        for cursor in self._walk_cursor(translation_unit.cursor):
            if cursor.kind == CursorKind.OBJC_PROPERTY_DECL:
                property_info = {
                    'name': cursor.spelling,
                    'type': 'property',
                    'position': self.get_node_position(cursor),
                    'property_type': self._extract_property_type(cursor),
                    'attributes': self._extract_property_attributes(cursor),
                }
                properties.append(property_info)
        
        return properties
    
    def extract_include_statements(self, translation_unit) -> List[str]:
        """Extract include statements from the AST."""
        includes = []
        
        for cursor in self._walk_cursor(translation_unit.cursor):
            if cursor.kind == CursorKind.INCLUSION_DIRECTIVE:
                included_file = cursor.get_included_file()
                if included_file:
                    includes.append(included_file.name)
        
        return includes
    
    def extract_category_info(self, translation_unit) -> List[Dict[str, Any]]:
        """Extract Objective-C category information from the AST."""
        categories = []
        
        for cursor in self._walk_cursor(translation_unit.cursor):
            if cursor.kind in [CursorKind.OBJC_CATEGORY_DECL, CursorKind.OBJC_CATEGORY_IMPL_DECL]:
                category_info = {
                    'name': cursor.spelling,
                    'type': 'category_interface' if cursor.kind == CursorKind.OBJC_CATEGORY_DECL else 'category_implementation',
                    'position': self.get_node_position(cursor),
                    'extended_class': self._extract_extended_class(cursor),
                    'methods': self._extract_category_methods(cursor),
                }
                categories.append(category_info)
        
        return categories
    
    def _extract_superclass(self, interface_cursor) -> Optional[str]:
        """Extract superclass name from interface declaration."""
        for child in interface_cursor.get_children():
            if child.kind == CursorKind.OBJC_SUPER_CLASS_REF:
                return child.spelling
        return None
    
    def _extract_protocols(self, interface_cursor) -> List[str]:
        """Extract protocol names from interface declaration."""
        protocols = []
        for child in interface_cursor.get_children():
            if child.kind == CursorKind.OBJC_PROTOCOL_REF:
                protocols.append(child.spelling)
        return protocols
    
    def _extract_parent_protocols(self, protocol_cursor) -> List[str]:
        """Extract parent protocol names from protocol declaration."""
        protocols = []
        for child in protocol_cursor.get_children():
            if child.kind == CursorKind.OBJC_PROTOCOL_REF:
                protocols.append(child.spelling)
        return protocols
    
    def _extract_interface_methods(self, interface_cursor) -> List[str]:
        """Extract method names from interface declaration."""
        methods = []
        for child in interface_cursor.get_children():
            if child.kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
                methods.append(child.spelling)
        return methods
    
    def _extract_implementation_methods(self, impl_cursor) -> List[str]:
        """Extract method names from implementation."""
        methods = []
        for child in impl_cursor.get_children():
            if child.kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
                methods.append(child.spelling)
        return methods
    
    def _extract_protocol_methods(self, protocol_cursor) -> List[str]:
        """Extract method names from protocol declaration."""
        methods = []
        for child in protocol_cursor.get_children():
            if child.kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
                methods.append(child.spelling)
        return methods
    
    def _extract_category_methods(self, category_cursor) -> List[str]:
        """Extract method names from category."""
        methods = []
        for child in category_cursor.get_children():
            if child.kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
                methods.append(child.spelling)
        return methods
    
    def _extract_interface_properties(self, interface_cursor) -> List[str]:
        """Extract property names from interface declaration."""
        properties = []
        for child in interface_cursor.get_children():
            if child.kind == CursorKind.OBJC_PROPERTY_DECL:
                properties.append(child.spelling)
        return properties
    
    def _extract_protocol_properties(self, protocol_cursor) -> List[str]:
        """Extract property names from protocol declaration."""
        properties = []
        for child in protocol_cursor.get_children():
            if child.kind == CursorKind.OBJC_PROPERTY_DECL:
                properties.append(child.spelling)
        return properties
    
    def _extract_implementation_ivars(self, impl_cursor) -> List[str]:
        """Extract instance variable names from implementation."""
        ivars = []
        for child in impl_cursor.get_children():
            if child.kind == CursorKind.OBJC_IVAR_DECL:
                ivars.append(child.spelling)
        return ivars
    
    def _extract_extended_class(self, category_cursor) -> Optional[str]:
        """Extract the class name that a category extends."""
        # The extended class is typically the first child that's a class reference
        for child in category_cursor.get_children():
            if child.kind == CursorKind.OBJC_CLASS_REF:
                return child.spelling
        return None
    
    def _extract_return_type(self, method_cursor) -> Optional[str]:
        """Extract return type from method declaration."""
        return method_cursor.result_type.spelling if method_cursor.result_type else None
    
    def _extract_method_parameters(self, method_cursor) -> List[Dict[str, str]]:
        """Extract parameter information from method declaration."""
        parameters = []
        for child in method_cursor.get_children():
            if child.kind == CursorKind.PARM_DECL:
                param_info = {
                    'name': child.spelling,
                    'type': child.type.spelling if child.type else 'unknown'
                }
                parameters.append(param_info)
        return parameters
    
    def _extract_property_type(self, property_cursor) -> Optional[str]:
        """Extract property type from property declaration."""
        return property_cursor.type.spelling if property_cursor.type else None
    
    def _extract_property_attributes(self, property_cursor) -> List[str]:
        """Extract property attributes (readonly, strong, etc.)."""
        # This is a simplified implementation - libclang doesn't easily expose
        # property attributes, so we'd need to parse the source text for full accuracy
        return []