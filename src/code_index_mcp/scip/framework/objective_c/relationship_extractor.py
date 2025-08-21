"""Objective-C relationship extractor implementation."""

from typing import Iterator, Optional, List
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..types import SCIPContext, Relationship
from ...core.relationship_types import InternalRelationshipType

try:
    import clang.cindex as clang
    from clang.cindex import CursorKind
    LIBCLANG_AVAILABLE = True
except ImportError:
    LIBCLANG_AVAILABLE = False
    clang = None
    CursorKind = None


class ObjectiveCRelationshipExtractor(BaseRelationshipExtractor):
    """Objective-C-specific relationship extractor using libclang analysis."""
    
    def __init__(self):
        """Initialize the Objective-C relationship extractor."""
        if not LIBCLANG_AVAILABLE:
            raise ImportError("libclang library not available")
        
        self.index = clang.Index.create()
    
    def extract_inheritance_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract inheritance relationships from Objective-C classes and protocols."""
        try:
            translation_unit = self.index.parse(context.file_path, args=['-x', 'objective-c'])
            
            for cursor in self._walk_cursor(translation_unit.cursor):
                if cursor.kind == CursorKind.OBJC_INTERFACE_DECL:
                    interface_name = cursor.spelling
                    if not interface_name:
                        continue
                    
                    interface_symbol_id = self._create_interface_symbol_id(interface_name, context)
                    
                    # Look for superclass
                    for child in cursor.get_children():
                        if child.kind == CursorKind.OBJC_SUPER_CLASS_REF:
                            parent_name = child.spelling
                            parent_symbol_id = self._create_interface_symbol_id(parent_name, context)
                            yield Relationship(
                                source_symbol=interface_symbol_id,
                                target_symbol=parent_symbol_id,
                                relationship_type=InternalRelationshipType.INHERITS
                            )
                
                elif cursor.kind == CursorKind.OBJC_PROTOCOL_DECL:
                    protocol_name = cursor.spelling
                    if not protocol_name:
                        continue
                    
                    protocol_symbol_id = self._create_protocol_symbol_id(protocol_name, context)
                    
                    # Look for protocol inheritance
                    for child in cursor.get_children():
                        if child.kind == CursorKind.OBJC_PROTOCOL_REF:
                            parent_protocol_name = child.spelling
                            parent_symbol_id = self._create_protocol_symbol_id(parent_protocol_name, context)
                            yield Relationship(
                                source_symbol=protocol_symbol_id,
                                target_symbol=parent_symbol_id,
                                relationship_type=InternalRelationshipType.INHERITS
                            )
                            
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_call_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract method call relationships."""
        try:
            translation_unit = self.index.parse(context.file_path, args=['-x', 'objective-c'])
            
            for cursor in self._walk_cursor(translation_unit.cursor):
                if cursor.kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
                    method_name = cursor.spelling
                    if not method_name:
                        continue
                    
                    method_symbol_id = self._create_method_symbol_id(method_name, context)
                    
                    # Find method calls within this method
                    for child in self._walk_cursor(cursor):
                        if child.kind == CursorKind.OBJC_MESSAGE_EXPR:
                            target_method = self._get_message_target(child)
                            if target_method and target_method != method_name:
                                target_symbol_id = self._create_method_symbol_id(target_method, context)
                                yield Relationship(
                                    source_symbol=method_symbol_id,
                                    target_symbol=target_symbol_id,
                                    relationship_type=InternalRelationshipType.CALLS
                                )
                        elif child.kind == CursorKind.CALL_EXPR:
                            # C function calls
                            target_function = child.spelling
                            if target_function and target_function != method_name:
                                target_symbol_id = self._create_function_symbol_id(target_function, context)
                                yield Relationship(
                                    source_symbol=method_symbol_id,
                                    target_symbol=target_symbol_id,
                                    relationship_type=InternalRelationshipType.CALLS
                                )
                                
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_import_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract import/dependency relationships."""
        try:
            translation_unit = self.index.parse(context.file_path, args=['-x', 'objective-c'])
            
            file_symbol_id = self._create_file_symbol_id(context.file_path)
            
            for cursor in self._walk_cursor(translation_unit.cursor):
                if cursor.kind == CursorKind.INCLUSION_DIRECTIVE:
                    include_path = self._get_include_path(cursor)
                    if include_path:
                        # Determine if it's a system header or local header
                        if include_path.startswith('<') and include_path.endswith('>'):
                            # System header
                            module_symbol_id = f"objc-system {include_path[1:-1]}"
                        elif include_path.startswith('"') and include_path.endswith('"'):
                            # Local header
                            module_symbol_id = f"local {include_path[1:-1]}"
                        else:
                            module_symbol_id = f"objc-external {include_path}"
                        
                        yield Relationship(
                            source_symbol=file_symbol_id,
                            target_symbol=module_symbol_id,
                            relationship_type=InternalRelationshipType.IMPORTS
                        )
                        
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_composition_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract composition relationships (properties, ivars)."""
        try:
            translation_unit = self.index.parse(context.file_path, args=['-x', 'objective-c'])
            
            for cursor in self._walk_cursor(translation_unit.cursor):
                if cursor.kind in [CursorKind.OBJC_INTERFACE_DECL, CursorKind.OBJC_IMPLEMENTATION_DECL]:
                    class_name = cursor.spelling
                    if not class_name:
                        continue
                    
                    class_symbol_id = self._create_class_symbol_id(class_name, context)
                    
                    # Find properties and ivars in this class
                    for child in cursor.get_children():
                        if child.kind == CursorKind.OBJC_PROPERTY_DECL:
                            property_name = child.spelling
                            if property_name:
                                property_symbol_id = self._create_property_symbol_id(property_name, class_symbol_id)
                                yield Relationship(
                                    source_symbol=class_symbol_id,
                                    target_symbol=property_symbol_id,
                                    relationship_type=InternalRelationshipType.CONTAINS
                                )
                        elif child.kind == CursorKind.OBJC_IVAR_DECL:
                            ivar_name = child.spelling
                            if ivar_name:
                                ivar_symbol_id = self._create_ivar_symbol_id(ivar_name, class_symbol_id)
                                yield Relationship(
                                    source_symbol=class_symbol_id,
                                    target_symbol=ivar_symbol_id,
                                    relationship_type=InternalRelationshipType.CONTAINS
                                )
                                
        except Exception:
            # Skip files with parsing errors
            return
    
    def extract_interface_relationships(self, context: SCIPContext) -> Iterator[Relationship]:
        """Extract protocol implementation relationships."""
        try:
            translation_unit = self.index.parse(context.file_path, args=['-x', 'objective-c'])
            
            for cursor in self._walk_cursor(translation_unit.cursor):
                if cursor.kind == CursorKind.OBJC_INTERFACE_DECL:
                    interface_name = cursor.spelling
                    if not interface_name:
                        continue
                    
                    interface_symbol_id = self._create_interface_symbol_id(interface_name, context)
                    
                    # Look for protocol conformance
                    for child in cursor.get_children():
                        if child.kind == CursorKind.OBJC_PROTOCOL_REF:
                            protocol_name = child.spelling
                            protocol_symbol_id = self._create_protocol_symbol_id(protocol_name, context)
                            yield Relationship(
                                source_symbol=interface_symbol_id,
                                target_symbol=protocol_symbol_id,
                                relationship_type=InternalRelationshipType.IMPLEMENTS
                            )
                            
        except Exception:
            # Skip files with parsing errors
            return
    
    def _walk_cursor(self, cursor) -> Iterator:
        """Walk libclang cursor tree."""
        yield cursor
        for child in cursor.get_children():
            yield from self._walk_cursor(child)
    
    def _get_message_target(self, message_expr_cursor) -> Optional[str]:
        """Extract target method name from Objective-C message expression."""
        # Get the selector name from the message expression
        for child in message_expr_cursor.get_children():
            if child.kind == CursorKind.OBJC_SELECTOR_REF:
                return child.spelling
        return None
    
    def _get_include_path(self, inclusion_cursor) -> Optional[str]:
        """Extract include path from inclusion directive."""
        # Get the included file path
        included_file = inclusion_cursor.get_included_file()
        if included_file:
            return included_file.name
        return None
    
    def _create_class_symbol_id(self, class_name: str, context: SCIPContext) -> str:
        """Create symbol ID for class."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{class_name}" if scope_path else class_name
        return f"local {local_id}#"
    
    def _create_interface_symbol_id(self, interface_name: str, context: SCIPContext) -> str:
        """Create symbol ID for interface."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{interface_name}" if scope_path else interface_name
        return f"local {local_id}#"
    
    def _create_protocol_symbol_id(self, protocol_name: str, context: SCIPContext) -> str:
        """Create symbol ID for protocol."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{protocol_name}" if scope_path else protocol_name
        return f"local {local_id}#"
    
    def _create_method_symbol_id(self, method_name: str, context: SCIPContext) -> str:
        """Create symbol ID for method."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{method_name}" if scope_path else method_name
        return f"local {local_id}()."
    
    def _create_function_symbol_id(self, function_name: str, context: SCIPContext) -> str:
        """Create symbol ID for C function."""
        scope_path = ".".join(context.scope_stack) if context.scope_stack else ""
        local_id = f"{scope_path}.{function_name}" if scope_path else function_name
        return f"local {local_id}()."
    
    def _create_property_symbol_id(self, property_name: str, class_symbol_id: str) -> str:
        """Create symbol ID for property."""
        # Extract class name from class symbol ID
        class_name = class_symbol_id.replace("local ", "").replace("#", "")
        return f"local {class_name}.{property_name}"
    
    def _create_ivar_symbol_id(self, ivar_name: str, class_symbol_id: str) -> str:
        """Create symbol ID for instance variable."""
        # Extract class name from class symbol ID
        class_name = class_symbol_id.replace("local ", "").replace("#", "")
        return f"local {class_name}.{ivar_name}"
    
    def _create_file_symbol_id(self, file_path: str) -> str:
        """Create symbol ID for file."""
        return f"local {file_path}"