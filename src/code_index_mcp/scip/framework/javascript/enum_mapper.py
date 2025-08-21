"""JavaScript enum mapper implementation."""

from typing import Dict
from ..base.enum_mapper import BaseEnumMapper
from ...proto import scip_pb2


class JavaScriptEnumMapper(BaseEnumMapper):
    """JavaScript/TypeScript-specific enum mapper for SCIP compliance."""
    
    # JavaScript symbol kind mappings
    SYMBOL_KIND_MAP = {
        'function': scip_pb2.Function,
        'arrow_function': scip_pb2.Function,
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
        'interface': scip_pb2.Interface,
        'type': scip_pb2.Type,
        'object': scip_pb2.Object,
        'enum': scip_pb2.Enum,
    }
    
    # JavaScript syntax kind mappings
    SYNTAX_KIND_MAP = {
        'function_definition': scip_pb2.IdentifierFunctionDefinition,
        'class_definition': scip_pb2.IdentifierType,
        'variable_definition': scip_pb2.IdentifierLocal,
        'parameter_definition': scip_pb2.IdentifierParameter,
        'property_definition': scip_pb2.IdentifierAttribute,
        'method_definition': scip_pb2.IdentifierFunctionDefinition,
        'interface_definition': scip_pb2.IdentifierType,
        'type_definition': scip_pb2.IdentifierType,
        'identifier': scip_pb2.Identifier,
        'keyword': scip_pb2.IdentifierKeyword,
        'string_literal': scip_pb2.StringLiteral,
        'numeric_literal': scip_pb2.NumericLiteral,
        'boolean_literal': scip_pb2.BooleanLiteral,
        'regex_literal': scip_pb2.RegexEscape,
        'comment': scip_pb2.Comment,
        'punctuation': scip_pb2.PunctuationDelimiter,
        'operator': scip_pb2.PunctuationDelimiter,
    }
    
    # JavaScript symbol role mappings (official SCIP naming)
    SYMBOL_ROLE_MAP = {
        'definition': scip_pb2.Definition,
        'import': scip_pb2.Import,
        'write': scip_pb2.Write,        # Official SCIP naming
        'read': scip_pb2.Read,          # Official SCIP naming
        'generated': scip_pb2.Generated,
        'test': scip_pb2.Test,
        'type': scip_pb2.Type,          # Add missing Type role
        'reference': scip_pb2.Read,     # Default reference is read access
        'export': scip_pb2.Definition,  # Exports are definitions
    }
    
    def map_symbol_kind(self, language_kind: str) -> int:
        """Map JavaScript symbol type to SCIP SymbolKind."""
        kind = self.SYMBOL_KIND_MAP.get(language_kind, scip_pb2.UnspecifiedSymbolKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SymbolKind'):
            raise ValueError(f"Invalid SymbolKind: {kind} for language_kind: {language_kind}")
        
        return kind
    
    def map_syntax_kind(self, language_syntax: str) -> int:
        """Map JavaScript syntax element to SCIP SyntaxKind."""
        kind = self.SYNTAX_KIND_MAP.get(language_syntax, scip_pb2.UnspecifiedSyntaxKind)
        
        # Validate enum value
        if not self.validate_enum_value(kind, 'SyntaxKind'):
            raise ValueError(f"Invalid SyntaxKind: {kind} for language_syntax: {language_syntax}")
        
        return kind
    
    def map_symbol_role(self, language_role: str) -> int:
        """Map JavaScript symbol role to SCIP SymbolRole."""
        role = self.SYMBOL_ROLE_MAP.get(language_role, scip_pb2.Read)
        
        # Validate enum value
        if not self.validate_enum_value(role, 'SymbolRole'):
            raise ValueError(f"Invalid SymbolRole: {role} for language_role: {language_role}")
        
        return role
    
    def get_javascript_pattern_symbol_kind(self, pattern_type: str) -> str:
        """
        Map JavaScript pattern type to internal symbol kind string.
        
        Args:
            pattern_type: Pattern type from regex matches (e.g., 'function', 'class')
            
        Returns:
            Internal symbol kind string for use with map_symbol_kind()
        """
        pattern_kind_map = {
            'function': 'function',
            'arrow_function': 'arrow_function',
            'class': 'class',
            'const': 'constant',
            'let': 'variable',
            'var': 'variable',
            'method': 'method',
            'object_method': 'function',
            'constructor': 'constructor',
            'interface': 'interface',
            'type': 'type',
            'enum': 'enum',
            'namespace': 'namespace',
        }
        
        return pattern_kind_map.get(pattern_type, 'variable')
    
    def get_javascript_pattern_syntax_kind(self, pattern_type: str, context: str = None) -> str:
        """
        Map JavaScript pattern type to internal syntax kind string.
        
        Args:
            pattern_type: Pattern type from regex matches
            context: Additional context for disambiguation
            
        Returns:
            Internal syntax kind string for use with map_syntax_kind()
        """
        pattern_syntax_map = {
            'function': 'function_definition',
            'arrow_function': 'function_definition',
            'class': 'class_definition',
            'const': 'variable_definition',
            'let': 'variable_definition',
            'var': 'variable_definition',
            'method': 'method_definition',
            'object_method': 'function_definition',
            'interface': 'interface_definition',
            'type': 'type_definition',
            'identifier': 'identifier',
            'string': 'string_literal',
            'number': 'numeric_literal',
            'boolean': 'boolean_literal',
            'regex': 'regex_literal',
        }
        
        return pattern_syntax_map.get(pattern_type, 'identifier')
    
    def get_javascript_pattern_symbol_role(self, pattern_type: str, context: str = None) -> str:
        """
        Map JavaScript pattern type to internal symbol role string.
        
        Args:
            pattern_type: Pattern type from regex matches
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
        elif context == 'export':
            return 'export'
        elif pattern_type in ['function', 'arrow_function', 'class', 'method', 'object_method', 
                             'const', 'let', 'var', 'interface', 'type']:
            return 'definition'
        else:
            return 'reference'
    
    def get_typescript_specific_kinds(self) -> Dict[str, str]:
        """Get TypeScript-specific symbol kinds."""
        return {
            'interface': 'interface',
            'type_alias': 'type',
            'enum': 'enum',
            'namespace': 'namespace',
            'generic_type': 'type',
            'union_type': 'type',
            'intersection_type': 'type',
        }
    
    def get_javascript_type_reference_role(self) -> str:
        """Get symbol role for type references (e.g., in TypeScript annotations)."""
        return 'type'
    
    def is_valid_javascript_symbol_kind(self, symbol_kind: str) -> bool:
        """Check if symbol kind is valid for JavaScript."""
        return symbol_kind in self.SYMBOL_KIND_MAP
    
    def is_valid_javascript_syntax_kind(self, syntax_kind: str) -> bool:
        """Check if syntax kind is valid for JavaScript."""
        return syntax_kind in self.SYNTAX_KIND_MAP
    
    def is_valid_javascript_symbol_role(self, symbol_role: str) -> bool:
        """Check if symbol role is valid for JavaScript."""
        return symbol_role in self.SYMBOL_ROLE_MAP
    
    def get_all_javascript_symbol_kinds(self) -> list:
        """Get all available JavaScript symbol kinds."""
        return list(self.SYMBOL_KIND_MAP.keys())
    
    def get_all_javascript_syntax_kinds(self) -> list:
        """Get all available JavaScript syntax kinds."""
        return list(self.SYNTAX_KIND_MAP.keys())
    
    def get_all_javascript_symbol_roles(self) -> list:
        """Get all available JavaScript symbol roles."""
        return list(self.SYMBOL_ROLE_MAP.keys())
    
    def supports_typescript(self) -> bool:
        """Check if TypeScript features are supported."""
        return True
    
    def get_es6_feature_kinds(self) -> Dict[str, str]:
        """Get ES6+ specific feature mappings."""
        return {
            'arrow_function': 'function',
            'class': 'class',
            'const': 'constant',
            'let': 'variable',
            'destructuring': 'variable',
            'spread_operator': 'operator',
            'template_literal': 'string_literal',
            'async_function': 'function',
            'generator_function': 'function',
            'module_export': 'module',
            'module_import': 'module',
        }