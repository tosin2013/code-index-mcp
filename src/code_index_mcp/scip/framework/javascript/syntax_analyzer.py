"""JavaScript syntax analyzer implementation."""

import re
from typing import Dict, List, Optional, Set, Tuple, Any


class JavaScriptSyntaxAnalyzer:
    """JavaScript/TypeScript syntax analyzer using regex patterns."""
    
    def __init__(self):
        """Initialize the syntax analyzer."""
        self._symbol_patterns = self._build_symbol_patterns()
        self._occurrence_patterns = self._build_occurrence_patterns()
        self._import_patterns = self._build_import_patterns()
        self._comment_patterns = self._build_comment_patterns()
    
    def get_symbol_patterns(self) -> Dict[str, str]:
        """Get regex patterns for symbol definitions."""
        return self._symbol_patterns
    
    def get_occurrence_patterns(self) -> Dict[str, str]:
        """Get regex patterns for symbol occurrences."""
        return self._occurrence_patterns
    
    def get_import_patterns(self) -> Dict[str, str]:
        """Get regex patterns for import statements."""
        return self._import_patterns
    
    def _build_symbol_patterns(self) -> Dict[str, str]:
        """Build regex patterns for JavaScript symbol definitions."""
        return {
            # Function declarations
            'function': r'function\s+(\w+)\s*\(',
            
            # Arrow functions
            'arrow_function': r'(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|\w+)\s*=>\s*',
            
            # Class declarations
            'class': r'class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{',
            
            # Method definitions (inside classes or objects)
            'method': r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{',
            
            # Object method assignment
            'object_method': r'(\w+)\s*:\s*(?:async\s+)?function\s*\([^)]*\)\s*\{',
            
            # Variable declarations
            'const': r'const\s+(\w+)(?:\s*:\s*[^=]+)?\s*=',
            'let': r'let\s+(\w+)(?:\s*:\s*[^=]+)?(?:\s*=|;)',
            'var': r'var\s+(\w+)(?:\s*:\s*[^=]+)?(?:\s*=|;)',
            
            # TypeScript interfaces
            'interface': r'interface\s+(\w+)(?:\s+extends\s+[^{]+)?\s*\{',
            
            # TypeScript type aliases
            'type': r'type\s+(\w+)(?:<[^>]*>)?\s*=',
            
            # TypeScript enums
            'enum': r'enum\s+(\w+)\s*\{',
            
            # TypeScript namespaces
            'namespace': r'namespace\s+(\w+)\s*\{',
            
            # Constructor functions (legacy pattern)
            'constructor': r'function\s+(\w+)\s*\([^)]*\)\s*\{[^}]*this\.',
            
            # Module exports
            'export_function': r'export\s+(?:default\s+)?function\s+(\w+)\s*\(',
            'export_class': r'export\s+(?:default\s+)?class\s+(\w+)',
            'export_const': r'export\s+const\s+(\w+)\s*=',
            
            # Destructuring assignments
            'destructure': r'(?:const|let|var)\s*\{\s*(\w+)(?:\s*,\s*\w+)*\s*\}\s*=',
        }
    
    def _build_occurrence_patterns(self) -> Dict[str, str]:
        """Build regex patterns for symbol occurrences/references."""
        return {
            # Function calls
            'function_call': r'(\w+)\s*\(',
            
            # Method calls
            'method_call': r'(\w+)\.(\w+)\s*\(',
            
            # Property access
            'property_access': r'(\w+)\.(\w+)(?!\s*\()',
            
            # Variable references
            'identifier': r'\b(\w+)\b',
            
            # this references
            'this_reference': r'this\.(\w+)',
            
            # super references
            'super_reference': r'super\.(\w+)',
            
            # Template literal expressions
            'template_expression': r'\$\{([^}]+)\}',
            
            # Assignment targets
            'assignment': r'(\w+)\s*[+\-*/%&|^]?=',
            
            # Function parameters
            'parameter': r'function\s+\w+\s*\(([^)]*)\)',
            
            # Object literal properties
            'object_property': r'(\w+)\s*:',
        }
    
    def _build_import_patterns(self) -> Dict[str, str]:
        """Build regex patterns for import statements."""
        return {
            # ES6 imports
            'es6_import': r'import\s+(?:\{([^}]+)\}|(\w+)|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]',
            
            # Default imports
            'default_import': r'import\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
            
            # Named imports
            'named_import': r'import\s+\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]',
            
            # Namespace imports
            'namespace_import': r'import\s+\*\s+as\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
            
            # Side effect imports
            'side_effect_import': r'import\s+[\'"]([^\'"]+)[\'"]',
            
            # CommonJS require
            'require': r'(?:const|let|var)\s+(?:\{([^}]+)\}|(\w+))\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            
            # Dynamic imports
            'dynamic_import': r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            
            # Re-exports
            'export_from': r'export\s+(?:\{([^}]+)\}|\*(?:\s+as\s+(\w+))?)\s+from\s+[\'"]([^\'"]+)[\'"]',
        }
    
    def _build_comment_patterns(self) -> Dict[str, str]:
        """Build regex patterns for comments."""
        return {
            'single_line': r'//.*$',
            'multi_line': r'/\*[\s\S]*?\*/',
            'jsdoc': r'/\*\*[\s\S]*?\*/',
        }
    
    def extract_functions(self, content: str) -> List[Dict[str, Any]]:
        """Extract function information from JavaScript content."""
        functions = []
        
        # Function declarations
        for match in re.finditer(self._symbol_patterns['function'], content, re.MULTILINE):
            functions.append({
                'name': match.group(1),
                'type': 'function',
                'start': match.start(),
                'end': match.end(),
                'line': content[:match.start()].count('\n')
            })
        
        # Arrow functions
        for match in re.finditer(self._symbol_patterns['arrow_function'], content, re.MULTILINE):
            functions.append({
                'name': match.group(1),
                'type': 'arrow_function',
                'start': match.start(),
                'end': match.end(),
                'line': content[:match.start()].count('\n')
            })
        
        # Methods
        for match in re.finditer(self._symbol_patterns['method'], content, re.MULTILINE):
            functions.append({
                'name': match.group(1),
                'type': 'method',
                'start': match.start(),
                'end': match.end(),
                'line': content[:match.start()].count('\n')
            })
        
        return functions
    
    def extract_classes(self, content: str) -> List[Dict[str, Any]]:
        """Extract class information from JavaScript content."""
        classes = []
        
        for match in re.finditer(self._symbol_patterns['class'], content, re.MULTILINE):
            class_info = {
                'name': match.group(1),
                'type': 'class',
                'start': match.start(),
                'end': match.end(),
                'line': content[:match.start()].count('\n'),
                'methods': [],
                'properties': []
            }
            
            # Extract class body
            class_body = self._extract_class_body(content, match.end())
            if class_body:
                class_info['methods'] = self._extract_class_methods(class_body)
                class_info['properties'] = self._extract_class_properties(class_body)
            
            classes.append(class_info)
        
        return classes
    
    def extract_variables(self, content: str) -> List[Dict[str, Any]]:
        """Extract variable declarations from JavaScript content."""
        variables = []
        
        for var_type in ['const', 'let', 'var']:
            pattern = self._symbol_patterns[var_type]
            for match in re.finditer(pattern, content, re.MULTILINE):
                variables.append({
                    'name': match.group(1),
                    'type': var_type,
                    'start': match.start(),
                    'end': match.end(),
                    'line': content[:match.start()].count('\n')
                })
        
        return variables
    
    def extract_imports(self, content: str) -> List[Dict[str, Any]]:
        """Extract import statements from JavaScript content."""
        imports = []
        
        for import_type, pattern in self._import_patterns.items():
            for match in re.finditer(pattern, content, re.MULTILINE):
                import_info = {
                    'type': import_type,
                    'start': match.start(),
                    'end': match.end(),
                    'line': content[:match.start()].count('\n'),
                    'raw': match.group(0)
                }
                
                # Extract specific information based on import type
                if import_type == 'es6_import':
                    import_info['module'] = match.group(4) if match.lastindex >= 4 else match.group(3)
                    import_info['imports'] = match.group(1) if match.group(1) else match.group(2)
                elif import_type in ['default_import', 'namespace_import']:
                    import_info['name'] = match.group(1)
                    import_info['module'] = match.group(2)
                elif import_type == 'require':
                    import_info['module'] = match.group(3) if match.lastindex >= 3 else match.group(2)
                    import_info['name'] = match.group(2) if match.lastindex >= 2 else match.group(1)
                elif import_type == 'dynamic_import':
                    import_info['module'] = match.group(1)
                
                imports.append(import_info)
        
        return imports
    
    def extract_exports(self, content: str) -> List[Dict[str, Any]]:
        """Extract export statements from JavaScript content."""
        exports = []
        
        export_patterns = {
            'export_default': r'export\s+default\s+(?:function\s+(\w+)|class\s+(\w+)|(\w+))',
            'export_named': r'export\s+\{([^}]+)\}',
            'export_function': r'export\s+function\s+(\w+)',
            'export_class': r'export\s+class\s+(\w+)',
            'export_const': r'export\s+const\s+(\w+)',
        }
        
        for export_type, pattern in export_patterns.items():
            for match in re.finditer(pattern, content, re.MULTILINE):
                exports.append({
                    'type': export_type,
                    'name': match.group(1) if match.group(1) else match.group(0),
                    'start': match.start(),
                    'end': match.end(),
                    'line': content[:match.start()].count('\n')
                })
        
        return exports
    
    def remove_comments(self, content: str) -> str:
        """Remove comments from JavaScript content."""
        # Remove single-line comments
        content = re.sub(self._comment_patterns['single_line'], '', content, flags=re.MULTILINE)
        
        # Remove multi-line comments
        content = re.sub(self._comment_patterns['multi_line'], '', content, flags=re.DOTALL)
        
        return content
    
    def extract_string_literals(self, content: str) -> List[Dict[str, Any]]:
        """Extract string literals from JavaScript content."""
        string_patterns = {
            'single_quote': r"'([^'\\]|\\.)*'",
            'double_quote': r'"([^"\\\\]|\\\\.)*"',
            'template_literal': r'`([^`\\\\]|\\\\.)*`',
        }
        
        strings = []
        for string_type, pattern in string_patterns.items():
            for match in re.finditer(pattern, content, re.MULTILINE):
                strings.append({
                    'type': string_type,
                    'value': match.group(0),
                    'start': match.start(),
                    'end': match.end(),
                    'line': content[:match.start()].count('\n')
                })
        
        return strings
    
    def _extract_class_body(self, content: str, start_pos: int) -> str:
        """Extract the body of a class from start position."""
        brace_count = 0
        i = start_pos
        
        # Find the opening brace
        while i < len(content) and content[i] != '{':
            i += 1
        
        if i >= len(content):
            return ""
        
        start_body = i + 1
        brace_count = 1
        i += 1
        
        # Find the matching closing brace
        while i < len(content) and brace_count > 0:
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
            i += 1
        
        if brace_count == 0:
            return content[start_body:i-1]
        
        return ""
    
    def _extract_class_methods(self, class_body: str) -> List[str]:
        """Extract method names from class body."""
        methods = []
        
        method_pattern = r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(method_pattern, class_body, re.MULTILINE):
            methods.append(match.group(1))
        
        return methods
    
    def _extract_class_properties(self, class_body: str) -> List[str]:
        """Extract property names from class body."""
        properties = []
        
        property_patterns = [
            r'(\w+)\s*=',  # Property assignment
            r'(\w+)\s*;',  # Property declaration (TypeScript)
        ]
        
        for pattern in property_patterns:
            for match in re.finditer(pattern, class_body, re.MULTILINE):
                prop_name = match.group(1)
                if prop_name not in ['constructor'] and not prop_name.startswith('_'):
                    properties.append(prop_name)
        
        return properties
    
    def is_typescript_file(self, file_path: str) -> bool:
        """Check if file is TypeScript based on extension."""
        return file_path.endswith(('.ts', '.tsx'))
    
    def extract_typescript_features(self, content: str) -> Dict[str, List[Dict[str, Any]]]:
        """Extract TypeScript-specific features."""
        if not self.is_typescript_file:
            return {}
        
        features = {
            'interfaces': [],
            'types': [],
            'enums': [],
            'namespaces': []
        }
        
        # Extract interfaces
        for match in re.finditer(self._symbol_patterns['interface'], content, re.MULTILINE):
            features['interfaces'].append({
                'name': match.group(1),
                'start': match.start(),
                'end': match.end(),
                'line': content[:match.start()].count('\n')
            })
        
        # Extract type aliases
        for match in re.finditer(self._symbol_patterns['type'], content, re.MULTILINE):
            features['types'].append({
                'name': match.group(1),
                'start': match.start(),
                'end': match.end(),
                'line': content[:match.start()].count('\n')
            })
        
        # Extract enums
        for match in re.finditer(self._symbol_patterns['enum'], content, re.MULTILINE):
            features['enums'].append({
                'name': match.group(1),
                'start': match.start(),
                'end': match.end(),
                'line': content[:match.start()].count('\n')
            })
        
        # Extract namespaces
        for match in re.finditer(self._symbol_patterns['namespace'], content, re.MULTILINE):
            features['namespaces'].append({
                'name': match.group(1),
                'start': match.start(),
                'end': match.end(),
                'line': content[:match.start()].count('\n')
            })
        
        return features