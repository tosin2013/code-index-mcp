"""Zig enum mapper implementation."""

from typing import Dict
from ..base.enum_mapper import BaseEnumMapper
from ...proto import scip_pb2


class ZigEnumMapper(BaseEnumMapper):
    """Zig-specific enum mapper for SCIP compliance."""
    
    # Zig symbol kind mappings
    SYMBOL_KIND_MAP = {
        'function': scip_pb2.Function,
        'method': scip_pb2.Method,
        'struct': scip_pb2.Struct,
        'union': scip_pb2.Struct,
        'enum': scip_pb2.Enum,
        'field': scip_pb2.Field,
        'variable': scip_pb2.Variable,
        'parameter': scip_pb2.Parameter,
        'constant': scip_pb2.Constant,
        'type': scip_pb2.Type,
        'namespace': scip_pb2.Namespace,
        'module': scip_pb2.Module,
        'local_variable': scip_pb2.Variable,
        'global_variable': scip_pb2.Variable,
        'error_set': scip_pb2.Type,
        'test_declaration': scip_pb2.Function,
        'comptime_declaration': scip_pb2.Function,
    }
    
    # Zig syntax kind mappings
    SYNTAX_KIND_MAP = {
        'function_declaration': scip_pb2.IdentifierFunctionDefinition,
        'struct_declaration': scip_pb2.IdentifierType,
        'union_declaration': scip_pb2.IdentifierType,
        'enum_declaration': scip_pb2.IdentifierType,
        'field_declaration': scip_pb2.IdentifierAttribute,
        'variable_declaration': scip_pb2.IdentifierLocal,
        'parameter_declaration': scip_pb2.IdentifierParameter,
        'constant_declaration': scip_pb2.IdentifierConstant,
        'type_declaration': scip_pb2.IdentifierType,
        'test_declaration': scip_pb2.IdentifierFunctionDefinition,
        'comptime_declaration': scip_pb2.IdentifierFunctionDefinition,
        'identifier': scip_pb2.Identifier,
        'keyword': scip_pb2.IdentifierKeyword,
        'string_literal': scip_pb2.StringLiteral,
        'numeric_literal': scip_pb2.NumericLiteral,
        'boolean_literal': scip_pb2.BooleanLiteral,
        'comment': scip_pb2.Comment,
        'punctuation': scip_pb2.PunctuationDelimiter,
    }
    
    # Zig symbol role mappings (official SCIP naming)
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
        """Map Zig symbol type to SCIP SymbolKind."""
        kind = self.SYMBOL_KIND_MAP.get(language_kind, scip_pb2.UnspecifiedSymbolKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SymbolKind'):
            raise ValueError(f"Invalid SymbolKind: {kind} for language_kind: {language_kind}")
        
        return kind
    
    def map_syntax_kind(self, language_syntax: str) -> int:
        """Map Zig syntax element to SCIP SyntaxKind."""
        kind = self.SYNTAX_KIND_MAP.get(language_syntax, scip_pb2.UnspecifiedSyntaxKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SyntaxKind'):
            raise ValueError(f"Invalid SyntaxKind: {kind} for language_syntax: {language_syntax}")
        
        return kind
    
    def map_symbol_role(self, language_role: str) -> int:
        """Map Zig symbol role to SCIP SymbolRole."""
        role = self.SYMBOL_ROLE_MAP.get(language_role, scip_pb2.Read)
        
        # Validate enum value
        if not self.validate_enum_value(role, 'SymbolRole'):
            raise ValueError(f"Invalid SymbolRole: {role} for language_role: {language_role}")
        
        return role
    
    def get_zig_node_symbol_kind(self, node_type: str) -> str:
        """
        Map Zig tree-sitter node type to internal symbol kind string.
        
        Args:
            node_type: Zig tree-sitter node type (e.g., 'function_declaration', 'struct_declaration')
            
        Returns:
            Internal symbol kind string for use with map_symbol_kind()
        """
        node_kind_map = {
            'function_declaration': 'function',
            'struct_declaration': 'struct',
            'union_declaration': 'union',
            'enum_declaration': 'enum',
            'field_declaration': 'field',
            'variable_declaration': 'variable',
            'parameter_declaration': 'parameter',
            'constant_declaration': 'constant',
            'type_declaration': 'type',
            'test_declaration': 'test_declaration',
            'comptime_declaration': 'comptime_declaration',
            'error_set_declaration': 'error_set',
            'container_field': 'field',
            'builtin_call_expr': 'function',
        }
        
        return node_kind_map.get(node_type, 'variable')
    
    def get_zig_node_syntax_kind(self, node_type: str, context: str = None) -> str:
        """
        Map Zig tree-sitter node type to internal syntax kind string.
        
        Args:
            node_type: Zig tree-sitter node type
            context: Additional context for disambiguation
            
        Returns:
            Internal syntax kind string for use with map_syntax_kind()
        """
        node_syntax_map = {
            'function_declaration': 'function_declaration',
            'struct_declaration': 'struct_declaration',
            'union_declaration': 'union_declaration',
            'enum_declaration': 'enum_declaration',
            'field_declaration': 'field_declaration',
            'variable_declaration': 'variable_declaration',
            'parameter_declaration': 'parameter_declaration',
            'constant_declaration': 'constant_declaration',
            'type_declaration': 'type_declaration',
            'test_declaration': 'test_declaration',
            'comptime_declaration': 'comptime_declaration',
            'identifier': 'identifier',
            'string_literal': 'string_literal',
            'integer_literal': 'numeric_literal',
            'float_literal': 'numeric_literal',
            'builtin_identifier': 'keyword',
            'boolean_literal': 'boolean_literal',
        }
        
        return node_syntax_map.get(node_type, 'identifier')
    
    def get_zig_node_symbol_role(self, node_type: str, context: str = None) -> str:
        """
        Map Zig tree-sitter node type to internal symbol role string.
        
        Args:
            node_type: Zig tree-sitter node type
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
        elif context == 'test':
            return 'test'
        elif node_type in ['function_declaration', 'struct_declaration', 'union_declaration', 
                          'enum_declaration', 'field_declaration', 'variable_declaration',
                          'constant_declaration', 'type_declaration', 'test_declaration']:
            return 'definition'
        else:
            return 'reference'
    
    def is_valid_zig_symbol_kind(self, symbol_kind: str) -> bool:
        """Check if symbol kind is valid for Zig."""
        return symbol_kind in self.SYMBOL_KIND_MAP
    
    def is_valid_zig_syntax_kind(self, syntax_kind: str) -> bool:
        """Check if syntax kind is valid for Zig."""
        return syntax_kind in self.SYNTAX_KIND_MAP
    
    def is_valid_zig_symbol_role(self, symbol_role: str) -> bool:
        """Check if symbol role is valid for Zig."""
        return symbol_role in self.SYMBOL_ROLE_MAP
    
    def get_all_zig_symbol_kinds(self) -> list:
        """Get all available Zig symbol kinds."""
        return list(self.SYMBOL_KIND_MAP.keys())
    
    def get_all_zig_syntax_kinds(self) -> list:
        """Get all available Zig syntax kinds."""
        return list(self.SYNTAX_KIND_MAP.keys())
    
    def get_all_zig_symbol_roles(self) -> list:
        """Get all available Zig symbol roles."""
        return list(self.SYMBOL_ROLE_MAP.keys())
    
    def get_zig_specific_kinds(self) -> Dict[str, str]:
        """Get Zig-specific symbol kinds."""
        return {
            'error_set': 'error_set',
            'test_declaration': 'test_declaration',
            'comptime_declaration': 'comptime_declaration',
            'builtin_function': 'function',
            'global_variable': 'global_variable',
            'local_variable': 'local_variable',
        }