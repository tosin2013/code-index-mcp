"""Objective-C enum mapper implementation."""

from typing import Dict
from ..base.enum_mapper import BaseEnumMapper
from ...proto import scip_pb2


class ObjectiveCEnumMapper(BaseEnumMapper):
    """Objective-C-specific enum mapper for SCIP compliance."""
    
    # Objective-C symbol kind mappings
    SYMBOL_KIND_MAP = {
        'method': scip_pb2.Method,
        'class': scip_pb2.Class,
        'interface': scip_pb2.Interface,
        'protocol': scip_pb2.Interface,  # Protocols are similar to interfaces
        'category': scip_pb2.Class,  # Categories extend classes
        'enum': scip_pb2.Enum,
        'field': scip_pb2.Field,
        'property': scip_pb2.Property,
        'variable': scip_pb2.Variable,
        'parameter': scip_pb2.Parameter,
        'function': scip_pb2.Function,
        'macro': scip_pb2.Macro,
        'constant': scip_pb2.Constant,
        'typedef': scip_pb2.Type,
        'struct': scip_pb2.Struct,
        'union': scip_pb2.Struct,
        'ivar': scip_pb2.Field,  # Instance variables
    }
    
    # Objective-C syntax kind mappings
    SYNTAX_KIND_MAP = {
        'method_declaration': scip_pb2.IdentifierFunctionDefinition,
        'class_declaration': scip_pb2.IdentifierType,
        'interface_declaration': scip_pb2.IdentifierType,
        'protocol_declaration': scip_pb2.IdentifierType,
        'category_declaration': scip_pb2.IdentifierType,
        'enum_declaration': scip_pb2.IdentifierType,
        'field_declaration': scip_pb2.IdentifierAttribute,
        'property_declaration': scip_pb2.IdentifierAttribute,
        'variable_declaration': scip_pb2.IdentifierLocal,
        'parameter_declaration': scip_pb2.IdentifierParameter,
        'function_declaration': scip_pb2.IdentifierFunctionDefinition,
        'macro_declaration': scip_pb2.IdentifierKeyword,
        'typedef_declaration': scip_pb2.IdentifierType,
        'struct_declaration': scip_pb2.IdentifierType,
        'union_declaration': scip_pb2.IdentifierType,
        'identifier': scip_pb2.Identifier,
        'keyword': scip_pb2.IdentifierKeyword,
        'string_literal': scip_pb2.StringLiteral,
        'numeric_literal': scip_pb2.NumericLiteral,
        'boolean_literal': scip_pb2.BooleanLiteral,
        'comment': scip_pb2.Comment,
        'punctuation': scip_pb2.PunctuationDelimiter,
    }
    
    # Objective-C symbol role mappings (official SCIP naming)
    SYMBOL_ROLE_MAP = {
        'definition': scip_pb2.Definition,
        'import': scip_pb2.Import,
        'write': scip_pb2.Write,        # Official SCIP naming
        'read': scip_pb2.Read,          # Official SCIP naming
        'generated': scip_pb2.Generated,
        'test': scip_pb2.Test,
        'type': scip_pb2.Type,          # Add missing Type role
        'reference': scip_pb2.Read,     # Default reference is read access
    }
    
    def map_symbol_kind(self, language_kind: str) -> int:
        """Map Objective-C symbol type to SCIP SymbolKind."""
        kind = self.SYMBOL_KIND_MAP.get(language_kind, scip_pb2.UnspecifiedSymbolKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SymbolKind'):
            raise ValueError(f"Invalid SymbolKind: {kind} for language_kind: {language_kind}")
        
        return kind
    
    def map_syntax_kind(self, language_syntax: str) -> int:
        """Map Objective-C syntax element to SCIP SyntaxKind."""
        kind = self.SYNTAX_KIND_MAP.get(language_syntax, scip_pb2.UnspecifiedSyntaxKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SyntaxKind'):
            raise ValueError(f"Invalid SyntaxKind: {kind} for language_syntax: {language_syntax}")
        
        return kind
    
    def map_symbol_role(self, language_role: str) -> int:
        """Map Objective-C symbol role to SCIP SymbolRole."""
        role = self.SYMBOL_ROLE_MAP.get(language_role, scip_pb2.Read)
        
        # Validate enum value
        if not self.validate_enum_value(role, 'SymbolRole'):
            raise ValueError(f"Invalid SymbolRole: {role} for language_role: {language_role}")
        
        return role
    
    def get_objc_cursor_symbol_kind(self, cursor_kind: str) -> str:
        """
        Map libclang cursor kind to internal symbol kind string.
        
        Args:
            cursor_kind: libclang cursor kind (e.g., 'OBJC_INTERFACE_DECL', 'OBJC_INSTANCE_METHOD_DECL')
            
        Returns:
            Internal symbol kind string for use with map_symbol_kind()
        """
        cursor_kind_map = {
            'OBJC_INTERFACE_DECL': 'interface',
            'OBJC_IMPLEMENTATION_DECL': 'class',
            'OBJC_PROTOCOL_DECL': 'protocol',
            'OBJC_CATEGORY_DECL': 'category',
            'OBJC_CATEGORY_IMPL_DECL': 'category',
            'OBJC_INSTANCE_METHOD_DECL': 'method',
            'OBJC_CLASS_METHOD_DECL': 'method',
            'OBJC_PROPERTY_DECL': 'property',
            'OBJC_IVAR_DECL': 'ivar',
            'CLASS_DECL': 'class',
            'STRUCT_DECL': 'struct',
            'UNION_DECL': 'union',
            'ENUM_DECL': 'enum',
            'FUNCTION_DECL': 'function',
            'VAR_DECL': 'variable',
            'PARM_DECL': 'parameter',
            'FIELD_DECL': 'field',
            'TYPEDEF_DECL': 'typedef',
            'MACRO_DEFINITION': 'macro',
            'ENUM_CONSTANT_DECL': 'constant',
        }
        
        return cursor_kind_map.get(cursor_kind, 'variable')
    
    def get_objc_cursor_syntax_kind(self, cursor_kind: str, context: str = None) -> str:
        """
        Map libclang cursor kind to internal syntax kind string.
        
        Args:
            cursor_kind: libclang cursor kind
            context: Additional context for disambiguation
            
        Returns:
            Internal syntax kind string for use with map_syntax_kind()
        """
        cursor_syntax_map = {
            'OBJC_INTERFACE_DECL': 'interface_declaration',
            'OBJC_IMPLEMENTATION_DECL': 'class_declaration',
            'OBJC_PROTOCOL_DECL': 'protocol_declaration',
            'OBJC_CATEGORY_DECL': 'category_declaration',
            'OBJC_CATEGORY_IMPL_DECL': 'category_declaration',
            'OBJC_INSTANCE_METHOD_DECL': 'method_declaration',
            'OBJC_CLASS_METHOD_DECL': 'method_declaration',
            'OBJC_PROPERTY_DECL': 'property_declaration',
            'OBJC_IVAR_DECL': 'field_declaration',
            'CLASS_DECL': 'class_declaration',
            'STRUCT_DECL': 'struct_declaration',
            'UNION_DECL': 'union_declaration',
            'ENUM_DECL': 'enum_declaration',
            'FUNCTION_DECL': 'function_declaration',
            'VAR_DECL': 'variable_declaration',
            'PARM_DECL': 'parameter_declaration',
            'FIELD_DECL': 'field_declaration',
            'TYPEDEF_DECL': 'typedef_declaration',
            'MACRO_DEFINITION': 'macro_declaration',
        }
        
        return cursor_syntax_map.get(cursor_kind, 'identifier')
    
    def get_objc_cursor_symbol_role(self, cursor_kind: str, context: str = None) -> str:
        """
        Map libclang cursor kind to internal symbol role string.
        
        Args:
            cursor_kind: libclang cursor kind
            context: Additional context (e.g., 'in_assignment', 'in_call')
            
        Returns:
            Internal symbol role string for use with map_symbol_role()
        """
        if context == 'definition':
            return 'definition'
        elif context == 'assignment':
            return 'write'
        elif context == 'import':
            return 'import'
        elif cursor_kind in ['OBJC_INTERFACE_DECL', 'OBJC_IMPLEMENTATION_DECL', 'OBJC_PROTOCOL_DECL',
                            'OBJC_CATEGORY_DECL', 'OBJC_INSTANCE_METHOD_DECL', 'OBJC_CLASS_METHOD_DECL', 'OBJC_PROPERTY_DECL',
                            'CLASS_DECL', 'STRUCT_DECL', 'FUNCTION_DECL', 'VAR_DECL', 'TYPEDEF_DECL']:
            return 'definition'
        else:
            return 'reference'
    
    def is_valid_objc_symbol_kind(self, symbol_kind: str) -> bool:
        """Check if symbol kind is valid for Objective-C."""
        return symbol_kind in self.SYMBOL_KIND_MAP
    
    def is_valid_objc_syntax_kind(self, syntax_kind: str) -> bool:
        """Check if syntax kind is valid for Objective-C."""
        return syntax_kind in self.SYNTAX_KIND_MAP
    
    def is_valid_objc_symbol_role(self, symbol_role: str) -> bool:
        """Check if symbol role is valid for Objective-C."""
        return symbol_role in self.SYMBOL_ROLE_MAP
    
    def get_all_objc_symbol_kinds(self) -> list:
        """Get all available Objective-C symbol kinds."""
        return list(self.SYMBOL_KIND_MAP.keys())
    
    def get_all_objc_syntax_kinds(self) -> list:
        """Get all available Objective-C syntax kinds."""
        return list(self.SYNTAX_KIND_MAP.keys())
    
    def get_all_objc_symbol_roles(self) -> list:
        """Get all available Objective-C symbol roles."""
        return list(self.SYMBOL_ROLE_MAP.keys())
    
    def get_objective_c_specific_kinds(self) -> Dict[str, str]:
        """Get Objective-C-specific symbol kinds."""
        return {
            'interface': 'interface',
            'protocol': 'protocol',
            'category': 'category',
            'property': 'property',
            'ivar': 'ivar',
            'class_method': 'method',
            'instance_method': 'method',
        }