"""
JavaScript parsing strategy using tree-sitter.
"""

import logging
from typing import Dict, List, Tuple, Optional
from .base_strategy import ParsingStrategy
from ..models.symbol_info import SymbolInfo
from ..models.file_info import FileInfo

logger = logging.getLogger(__name__)

try:
    import tree_sitter
    import tree_sitter_javascript
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter not available, JavaScript parsing will be limited")


class JavaScriptParsingStrategy(ParsingStrategy):
    """JavaScript-specific parsing strategy using tree-sitter."""
    
    def __init__(self):
        if TREE_SITTER_AVAILABLE:
            self.js_language = tree_sitter.Language(tree_sitter_javascript.language())
        else:
            self.js_language = None
    
    def get_language_name(self) -> str:
        return "javascript"
    
    def get_supported_extensions(self) -> List[str]:
        return ['.js', '.jsx', '.mjs', '.cjs']
    
    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse JavaScript file using tree-sitter."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        exports = []
        
        if not TREE_SITTER_AVAILABLE or not self.js_language:
            logger.info(f"Tree-sitter not available, using fallback for {file_path}")
            return self._fallback_parse(file_path, content)
        
        try:
            parser = tree_sitter.Parser(self.js_language)
            tree = parser.parse(content.encode('utf8'))
            self._traverse_js_node(tree.root_node, content, file_path, symbols, functions, classes, imports, exports)
        except Exception as e:
            logger.warning(f"Error parsing JavaScript file {file_path}: {e}, falling back to regex parsing")
            return self._fallback_parse(file_path, content)
        
        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            exports=exports
        )
        
        return symbols, file_info
    
    def _traverse_js_node(self, node, content: str, file_path: str, symbols: Dict[str, SymbolInfo], 
                         functions: List[str], classes: List[str], imports: List[str], exports: List[str]):
        """Traverse JavaScript AST node."""
        if node.type == 'function_declaration':
            name = self._get_function_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                signature = self._get_js_function_signature(node, content)
                symbols[symbol_id] = SymbolInfo(
                    type="function",
                    file=file_path,
                    line=node.start_point[0] + 1,
                    signature=signature
                )
                functions.append(name)
        
        elif node.type == 'class_declaration':
            name = self._get_class_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                symbols[symbol_id] = SymbolInfo(
                    type="class",
                    file=file_path,
                    line=node.start_point[0] + 1
                )
                classes.append(name)
        
        elif node.type == 'method_definition':
            method_name = self._get_method_name(node, content)
            class_name = self._find_parent_class(node, content)
            if method_name and class_name:
                symbol_id = self._create_symbol_id(file_path, f"{class_name}.{method_name}")
                signature = self._get_js_function_signature(node, content)
                symbols[symbol_id] = SymbolInfo(
                    type="method",
                    file=file_path,
                    line=node.start_point[0] + 1,
                    signature=signature
                )
        
        # Continue traversing children
        for child in node.children:
            self._traverse_js_node(child, content, file_path, symbols, functions, classes, imports, exports)
    
    def _get_function_name(self, node, content: str) -> Optional[str]:
        """Extract function name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None
    
    def _get_class_name(self, node, content: str) -> Optional[str]:
        """Extract class name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None
    
    def _get_method_name(self, node, content: str) -> Optional[str]:
        """Extract method name from tree-sitter node."""
        for child in node.children:
            if child.type == 'property_identifier':
                return content[child.start_byte:child.end_byte]
        return None
    
    def _find_parent_class(self, node, content: str) -> Optional[str]:
        """Find the parent class of a method."""
        parent = node.parent
        while parent:
            if parent.type == 'class_declaration':
                return self._get_class_name(parent, content)
            parent = parent.parent
        return None
    
    def _get_js_function_signature(self, node, content: str) -> str:
        """Extract JavaScript function signature."""
        return content[node.start_byte:node.end_byte].split('\n')[0].strip()
    
    def _fallback_parse(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Enhanced fallback parsing when tree-sitter is not available."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        
        # Phase 1: Extract symbols using enhanced regex-based parsing
        lines = content.splitlines()
        current_class = None
        
        for i, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            # Import/require statements
            if line.startswith('const ') and 'require(' in line:
                import_name = self._extract_js_require(line)
                if import_name:
                    imports.append(import_name)
            elif line.startswith('import ') and ' from ' in line:
                import_name = self._extract_js_import(line)
                if import_name:
                    imports.append(import_name)
            
            # Class declarations
            elif line.startswith('class '):
                class_name = self._extract_js_class_name(line)
                if class_name:
                    current_class = class_name
                    symbol_id = self._create_symbol_id(file_path, class_name)
                    symbols[symbol_id] = SymbolInfo(
                        type="class",
                        file=file_path,
                        line=i + 1
                    )
                    classes.append(class_name)
            
            # Function declarations (standalone)
            elif line.startswith('function '):
                func_name = self._extract_js_function_name(line)
                if func_name:
                    symbol_id = self._create_symbol_id(file_path, func_name)
                    symbols[symbol_id] = SymbolInfo(
                        type="function",
                        file=file_path,
                        line=i + 1,
                        signature=line
                    )
                    functions.append(func_name)
            
            # Method declarations (inside classes) - async method() { or method() {
            elif current_class and (line.endswith('{') or '{' in line) and '(' in line and ')' in line:
                method_name = self._extract_js_method_name(line)
                if method_name and not line.startswith('//') and 'function' not in line:
                    symbol_id = self._create_symbol_id(file_path, f"{current_class}.{method_name}")
                    symbols[symbol_id] = SymbolInfo(
                        type="method",
                        file=file_path,
                        line=i + 1,
                        signature=line.replace('{', '').strip()
                    )
                    functions.append(method_name)  # Add to functions list for summary
            
            # Reset class context on closing brace (simplified)
            elif line == '}' and current_class:
                # Very basic heuristic - this could be improved
                if original_line.strip() == '}' and i < len(lines) - 1:
                    current_class = None
        
        # Phase 2: Add call relationship analysis
        self._analyze_js_calls(content, symbols, file_path)
        
        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(lines),
            symbols={"functions": functions, "classes": classes},
            imports=imports
        )
        
        return symbols, file_info
    
    def _extract_js_function_name(self, line: str) -> Optional[str]:
        """Extract function name from JavaScript function declaration."""
        try:
            # function functionName(...) or function functionName(...)
            parts = line.split('(')[0].split()
            if len(parts) >= 2 and parts[0] == 'function':
                return parts[1]
        except:
            pass
        return None
    
    def _extract_js_class_name(self, line: str) -> Optional[str]:
        """Extract class name from JavaScript class declaration."""
        try:
            # class ClassName { or class ClassName extends ...
            parts = line.split()
            if len(parts) >= 2 and parts[0] == 'class':
                class_name = parts[1]
                # Remove any trailing characters like { or extends
                if '{' in class_name:
                    class_name = class_name.split('{')[0]
                if 'extends' in class_name:
                    class_name = class_name.split('extends')[0]
                return class_name.strip()
        except:
            pass
        return None
    
    def _extract_js_method_name(self, line: str) -> Optional[str]:
        """Extract method name from JavaScript method declaration."""
        try:
            # async methodName(params) { or methodName(params) {
            line = line.strip()
            if line.startswith('async '):
                line = line[6:].strip()
            
            if '(' in line:
                method_name = line.split('(')[0].strip()
                # Remove access modifiers and keywords
                for modifier in ['static', 'get', 'set']:
                    if method_name.startswith(modifier + ' '):
                        method_name = method_name[len(modifier):].strip()
                
                return method_name if method_name and method_name.replace('_', '').isalnum() else None
        except:
            pass
        return None
    
    def _extract_js_require(self, line: str) -> Optional[str]:
        """Extract module name from require statement."""
        try:
            # const something = require('module') or require('module')
            if 'require(' in line:
                start = line.find("require('") + 9
                if start == 8:  # require(" format
                    start = line.find('require("') + 9
                if start > 8:
                    end = line.find("'", start)
                    if end == -1:
                        end = line.find('"', start)
                    if end > start:
                        return line[start:end]
        except:
            pass
        return None
    
    def _extract_js_import(self, line: str) -> Optional[str]:
        """Extract module name from ES6 import statement."""
        try:
            # import { something } from 'module' or import something from 'module'
            if ' from ' in line:
                module_part = line.split(' from ')[-1].strip()
                module_name = module_part.strip('\'"').replace("'", "").replace('"', '').replace(';', '')
                return module_name
        except:
            pass
        return None
    
    def _analyze_js_calls(self, content: str, symbols: Dict[str, SymbolInfo], file_path: str):
        """Analyze JavaScript function calls for relationships."""
        lines = content.splitlines()
        current_function = None
        
        for i, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            # Track current function context
            if 'function ' in line or (line.endswith('{') and '(' in line and ')' in line):
                func_name = self._extract_function_from_line(line)
                if func_name:
                    current_function = self._create_symbol_id(file_path, func_name)
            
            # Find function calls: functionName() or obj.methodName()
            if current_function and ('(' in line and ')' in line):
                called_functions = self._extract_called_functions(line)
                for called_func in called_functions:
                    # Find the called function in symbols and add relationship
                    for symbol_id, symbol_info in symbols.items():
                        if called_func in symbol_id.split("::")[-1]:
                            if current_function not in symbol_info.called_by:
                                symbol_info.called_by.append(current_function)
    
    def _extract_function_from_line(self, line: str) -> Optional[str]:
        """Extract function name from a line that defines a function."""
        if 'function ' in line:
            return self._extract_js_function_name(line)
        elif line.endswith('{') and '(' in line:
            return self._extract_js_method_name(line)
        return None
    
    def _extract_called_functions(self, line: str) -> List[str]:
        """Extract function names that are being called in this line."""
        import re
        called_functions = []
        
        # Find patterns like: functionName( or obj.methodName(
        patterns = [
            r'(\w+)\s*\(',  # functionName(
            r'\.(\w+)\s*\(',  # .methodName(
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, line)
            called_functions.extend(matches)
        
        return called_functions