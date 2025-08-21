"""Python enum mapper implementation."""

from ..base.enum_mapper import BaseEnumMapper
from ...proto import scip_pb2


class PythonEnumMapper(BaseEnumMapper):
    """Python-specific enum mapper for SCIP compliance."""
    
    # Python symbol kind mappings
    SYMBOL_KIND_MAP = {
        'function': scip_pb2.Function,
        'async_function': scip_pb2.Function,
        'method': scip_pb2.Method,
        'class': scip_pb2.Class,
        'variable': scip_pb2.Variable,
        'constant': scip_pb2.Constant,
        'module': scip_pb2.Module,
        'parameter': scip_pb2.Parameter,
        'property': scip_pb2.Property,
        'constructor': scip_pb2.Constructor,
        'field': scip_pb2.Field,
        'namespace': scip_pb2.Namespace,
    }
    
    # Python syntax kind mappings (using actual SCIP protobuf attributes)
    SYNTAX_KIND_MAP = {
        'function_definition': scip_pb2.IdentifierFunctionDefinition,
        'class_definition': scip_pb2.IdentifierType,
        'variable_definition': scip_pb2.IdentifierLocal,  # Use IdentifierLocal instead of IdentifierVariable
        'parameter_definition': scip_pb2.IdentifierParameter,
        'identifier': scip_pb2.Identifier,
        'keyword': scip_pb2.IdentifierKeyword,
        'string_literal': scip_pb2.StringLiteral,
        'numeric_literal': scip_pb2.NumericLiteral,
        'boolean_literal': scip_pb2.BooleanLiteral,
        'comment': scip_pb2.Comment,
        'punctuation': scip_pb2.PunctuationDelimiter,
    }
    
    # Python symbol role mappings (using official SCIP protobuf attributes)
    SYMBOL_ROLE_MAP = {
        'definition': scip_pb2.Definition,
        'import': scip_pb2.Import,
        'write': scip_pb2.Write,         # Official SCIP naming
        'read': scip_pb2.Read,           # Official SCIP naming  
        'generated': scip_pb2.Generated,
        'test': scip_pb2.Test,
        'type': scip_pb2.Type,           # Add missing Type role
        'reference': scip_pb2.Read,      # Default reference is read access
    }
    
    def map_symbol_kind(self, language_kind: str) -> int:
        """Map Python symbol type to SCIP SymbolKind."""
        kind = self.SYMBOL_KIND_MAP.get(language_kind, scip_pb2.UnspecifiedSymbolKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SymbolKind'):
            raise ValueError(f"Invalid SymbolKind: {kind} for language_kind: {language_kind}")
        
        return kind
    
    def map_syntax_kind(self, language_syntax: str) -> int:
        """Map Python syntax element to SCIP SyntaxKind."""
        kind = self.SYNTAX_KIND_MAP.get(language_syntax, scip_pb2.UnspecifiedSyntaxKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SyntaxKind'):
            raise ValueError(f"Invalid SyntaxKind: {kind} for language_syntax: {language_syntax}")
        
        return kind
    
    def map_symbol_role(self, language_role: str) -> int:
        """Map Python symbol role to SCIP SymbolRole."""
        role = self.SYMBOL_ROLE_MAP.get(language_role, scip_pb2.Read)
        
        # Validate enum value
        if not self.validate_enum_value(role, 'SymbolRole'):
            raise ValueError(f"Invalid SymbolRole: {role} for language_role: {language_role}")
        
        return role
    
    def get_python_node_symbol_kind(self, node_type: str) -> str:
        """
        Map Python AST node type to internal symbol kind string.
        
        Args:
            node_type: Python AST node type (e.g., 'FunctionDef', 'ClassDef')
            
        Returns:
            Internal symbol kind string for use with map_symbol_kind()
        """
        node_kind_map = {
            'FunctionDef': 'function',
            'AsyncFunctionDef': 'async_function',
            'ClassDef': 'class',
            'Assign': 'variable',
            'AnnAssign': 'variable',
            'AugAssign': 'variable',
            'arg': 'parameter',
            'Import': 'module',
            'ImportFrom': 'module',
        }
        
        return node_kind_map.get(node_type, 'variable')
    
    def get_python_node_syntax_kind(self, node_type: str, context: str = None) -> str:
        """
        Map Python AST node type to internal syntax kind string.
        
        Args:
            node_type: Python AST node type
            context: Additional context for disambiguation
            
        Returns:
            Internal syntax kind string for use with map_syntax_kind()
        """
        node_syntax_map = {
            'FunctionDef': 'function_definition',
            'AsyncFunctionDef': 'function_definition',
            'ClassDef': 'class_definition',
            'Assign': 'variable_definition',
            'AnnAssign': 'variable_definition',
            'Name': 'identifier',
            'Str': 'string_literal',
            'Num': 'numeric_literal',
            'Constant': 'numeric_literal',  # Python 3.8+
            'NameConstant': 'boolean_literal',  # True, False, None
        }
        
        return node_syntax_map.get(node_type, 'identifier')
    
    def get_python_node_symbol_role(self, node_type: str, context: str = None) -> str:
        """
        Map Python AST node type to internal symbol role string.
        
        Args:
            node_type: Python AST node type
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
        elif node_type in ['FunctionDef', 'AsyncFunctionDef', 'ClassDef']:
            return 'definition'
        else:
            return 'reference'
    
    def is_valid_python_symbol_kind(self, symbol_kind: str) -> bool:
        """Check if symbol kind is valid for Python."""
        return symbol_kind in self.SYMBOL_KIND_MAP
    
    def is_valid_python_syntax_kind(self, syntax_kind: str) -> bool:
        """Check if syntax kind is valid for Python."""
        return syntax_kind in self.SYNTAX_KIND_MAP
    
    def is_valid_python_symbol_role(self, symbol_role: str) -> bool:
        """Check if symbol role is valid for Python."""
        return symbol_role in self.SYMBOL_ROLE_MAP
    
    def get_python_type_reference_role(self) -> str:
        """Get symbol role for type references (e.g., in annotations)."""
        return 'type'
    
    def get_all_python_symbol_kinds(self) -> list:
        """Get all available Python symbol kinds."""
        return list(self.SYMBOL_KIND_MAP.keys())
    
    def get_all_python_syntax_kinds(self) -> list:
        """Get all available Python syntax kinds."""
        return list(self.SYNTAX_KIND_MAP.keys())
    
    def get_all_python_symbol_roles(self) -> list:
        """Get all available Python symbol roles."""
        return list(self.SYMBOL_ROLE_MAP.keys())