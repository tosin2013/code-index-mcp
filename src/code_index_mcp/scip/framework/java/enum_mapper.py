"""Java enum mapper implementation."""

from ..base.enum_mapper import BaseEnumMapper
from ...proto import scip_pb2


class JavaEnumMapper(BaseEnumMapper):
    """Java-specific enum mapper for SCIP compliance."""
    
    # Java symbol kind mappings
    SYMBOL_KIND_MAP = {
        'method': scip_pb2.Method,
        'class': scip_pb2.Class,
        'interface': scip_pb2.Interface,
        'enum': scip_pb2.Enum,
        'field': scip_pb2.Field,
        'variable': scip_pb2.Variable,
        'parameter': scip_pb2.Parameter,
        'constructor': scip_pb2.Constructor,
        'package': scip_pb2.Package,
        'annotation': scip_pb2.Interface,
        'constant': scip_pb2.Constant,
        'local_variable': scip_pb2.Variable,
        'type_parameter': scip_pb2.TypeParameter,
    }
    
    # Java syntax kind mappings
    SYNTAX_KIND_MAP = {
        'method_declaration': scip_pb2.IdentifierFunctionDefinition,
        'class_declaration': scip_pb2.IdentifierType,
        'interface_declaration': scip_pb2.IdentifierType,
        'enum_declaration': scip_pb2.IdentifierType,
        'field_declaration': scip_pb2.IdentifierAttribute,
        'variable_declaration': scip_pb2.IdentifierLocal,
        'parameter_declaration': scip_pb2.IdentifierParameter,
        'constructor_declaration': scip_pb2.IdentifierFunctionDefinition,
        'annotation_declaration': scip_pb2.IdentifierType,
        'identifier': scip_pb2.Identifier,
        'keyword': scip_pb2.IdentifierKeyword,
        'string_literal': scip_pb2.StringLiteral,
        'numeric_literal': scip_pb2.NumericLiteral,
        'boolean_literal': scip_pb2.BooleanLiteral,
        'comment': scip_pb2.Comment,
        'punctuation': scip_pb2.PunctuationDelimiter,
    }
    
    # Java symbol role mappings (official SCIP naming)
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
        """Map Java symbol type to SCIP SymbolKind."""
        kind = self.SYMBOL_KIND_MAP.get(language_kind, scip_pb2.UnspecifiedSymbolKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SymbolKind'):
            raise ValueError(f"Invalid SymbolKind: {kind} for language_kind: {language_kind}")
        
        return kind
    
    def map_syntax_kind(self, language_syntax: str) -> int:
        """Map Java syntax element to SCIP SyntaxKind."""
        kind = self.SYNTAX_KIND_MAP.get(language_syntax, scip_pb2.UnspecifiedSyntaxKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SyntaxKind'):
            raise ValueError(f"Invalid SyntaxKind: {kind} for language_syntax: {language_syntax}")
        
        return kind
    
    def map_symbol_role(self, language_role: str) -> int:
        """Map Java symbol role to SCIP SymbolRole."""
        role = self.SYMBOL_ROLE_MAP.get(language_role, scip_pb2.Read)
        
        # Validate enum value
        if not self.validate_enum_value(role, 'SymbolRole'):
            raise ValueError(f"Invalid SymbolRole: {role} for language_role: {language_role}")
        
        return role
    
    def get_java_node_symbol_kind(self, node_type: str) -> str:
        """
        Map Java tree-sitter node type to internal symbol kind string.
        
        Args:
            node_type: Java tree-sitter node type (e.g., 'method_declaration', 'class_declaration')
            
        Returns:
            Internal symbol kind string for use with map_symbol_kind()
        """
        node_kind_map = {
            'method_declaration': 'method',
            'constructor_declaration': 'constructor',
            'class_declaration': 'class',
            'interface_declaration': 'interface',
            'enum_declaration': 'enum',
            'field_declaration': 'field',
            'local_variable_declaration': 'local_variable',
            'formal_parameter': 'parameter',
            'annotation_type_declaration': 'annotation',
            'type_parameter': 'type_parameter',
        }
        
        return node_kind_map.get(node_type, 'variable')
    
    def get_java_node_syntax_kind(self, node_type: str, context: str = None) -> str:
        """
        Map Java tree-sitter node type to internal syntax kind string.
        
        Args:
            node_type: Java tree-sitter node type
            context: Additional context for disambiguation
            
        Returns:
            Internal syntax kind string for use with map_syntax_kind()
        """
        node_syntax_map = {
            'method_declaration': 'method_declaration',
            'constructor_declaration': 'constructor_declaration',
            'class_declaration': 'class_declaration',
            'interface_declaration': 'interface_declaration',
            'enum_declaration': 'enum_declaration',
            'field_declaration': 'field_declaration',
            'local_variable_declaration': 'variable_declaration',
            'formal_parameter': 'parameter_declaration',
            'annotation_type_declaration': 'annotation_declaration',
            'identifier': 'identifier',
            'string_literal': 'string_literal',
            'decimal_integer_literal': 'numeric_literal',
            'hex_integer_literal': 'numeric_literal',
            'octal_integer_literal': 'numeric_literal',
            'binary_integer_literal': 'numeric_literal',
            'decimal_floating_point_literal': 'numeric_literal',
            'hex_floating_point_literal': 'numeric_literal',
            'true': 'boolean_literal',
            'false': 'boolean_literal',
            'null_literal': 'boolean_literal',
        }
        
        return node_syntax_map.get(node_type, 'identifier')
    
    def get_java_node_symbol_role(self, node_type: str, context: str = None) -> str:
        """
        Map Java tree-sitter node type to internal symbol role string.
        
        Args:
            node_type: Java tree-sitter node type
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
        elif node_type in ['method_declaration', 'constructor_declaration', 'class_declaration', 
                          'interface_declaration', 'enum_declaration', 'field_declaration',
                          'annotation_type_declaration']:
            return 'definition'
        else:
            return 'reference'
    
    def is_valid_java_symbol_kind(self, symbol_kind: str) -> bool:
        """Check if symbol kind is valid for Java."""
        return symbol_kind in self.SYMBOL_KIND_MAP
    
    def is_valid_java_syntax_kind(self, syntax_kind: str) -> bool:
        """Check if syntax kind is valid for Java."""
        return syntax_kind in self.SYNTAX_KIND_MAP
    
    def is_valid_java_symbol_role(self, symbol_role: str) -> bool:
        """Check if symbol role is valid for Java."""
        return symbol_role in self.SYMBOL_ROLE_MAP
    
    def get_all_java_symbol_kinds(self) -> list:
        """Get all available Java symbol kinds."""
        return list(self.SYMBOL_KIND_MAP.keys())
    
    def get_all_java_syntax_kinds(self) -> list:
        """Get all available Java syntax kinds."""
        return list(self.SYNTAX_KIND_MAP.keys())
    
    def get_all_java_symbol_roles(self) -> list:
        """Get all available Java symbol roles."""
        return list(self.SYMBOL_ROLE_MAP.keys())
    
    def get_java_type_reference_role(self) -> str:
        """Get symbol role for type references (e.g., in generic parameters)."""
        return 'type'