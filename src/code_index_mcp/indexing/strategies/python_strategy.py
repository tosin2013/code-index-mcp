"""
Python parsing strategy using AST.
"""

import ast
import logging
from typing import Dict, List, Tuple, Optional
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)


class PythonParsingStrategy(ParsingStrategy):
    """Python-specific parsing strategy using Python's built-in AST."""
    
    def get_language_name(self) -> str:
        return "python"
    
    def get_supported_extensions(self) -> List[str]:
        return ['.py', '.pyw']
    
    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Python file using AST."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        
        try:
            tree = ast.parse(content)
            # Phase 1: Extract symbol definitions
            self._visit_ast_node(tree, symbols, functions, classes, imports, file_path, content)
            # Phase 2: Analyze function calls and build relationships
            self._analyze_calls(tree, symbols, file_path)
        except SyntaxError as e:
            logger.warning(f"Syntax error in Python file {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Error parsing Python file {file_path}: {e}")
        
        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports
        )
        
        return symbols, file_info
    
    def _visit_ast_node(self, node: ast.AST, symbols: Dict, functions: List, 
                       classes: List, imports: List, file_path: str, content: str):
        """Visit AST nodes and extract symbols."""
        # Track processed nodes to avoid duplicates
        processed_nodes = set()
        
        # First pass: handle classes and mark their methods as processed
        for child in ast.walk(node):
            if isinstance(child, ast.ClassDef):
                self._handle_class(child, symbols, classes, file_path, functions)
                # Mark all methods in this class as processed
                for class_child in child.body:
                    if isinstance(class_child, ast.FunctionDef):
                        processed_nodes.add(id(class_child))
        
        # Second pass: handle standalone functions and imports
        for child in ast.walk(node):
            if isinstance(child, ast.FunctionDef) and id(child) not in processed_nodes:
                self._handle_function(child, symbols, functions, file_path)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                self._handle_import(child, imports)
    
    def _handle_function(self, node: ast.FunctionDef, symbols: Dict, functions: List, file_path: str):
        """Handle function definition."""
        func_name = node.name
        symbol_id = self._create_symbol_id(file_path, func_name)
        
        # Extract function signature
        signature = self._extract_function_signature(node)
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        symbols[symbol_id] = SymbolInfo(
            type="function",
            file=file_path,
            line=node.lineno,
            signature=signature,
            docstring=docstring
        )
        functions.append(func_name)
    
    def _handle_class(self, node: ast.ClassDef, symbols: Dict, classes: List, file_path: str, functions: List = None):
        """Handle class definition."""
        class_name = node.name
        symbol_id = self._create_symbol_id(file_path, class_name)
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        symbols[symbol_id] = SymbolInfo(
            type="class",
            file=file_path,
            line=node.lineno,
            docstring=docstring
        )
        classes.append(class_name)
        
        # Handle methods within the class
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                method_name = f"{class_name}.{child.name}"
                method_symbol_id = self._create_symbol_id(file_path, method_name)
                
                method_signature = self._extract_function_signature(child)
                method_docstring = ast.get_docstring(child)
                
                symbols[method_symbol_id] = SymbolInfo(
                    type="method",
                    file=file_path,
                    line=child.lineno,
                    signature=method_signature,
                    docstring=method_docstring
                )
                
                # Add method to functions list if provided
                if functions is not None:
                    functions.append(method_name)
    
    def _handle_import(self, node, imports: List):
        """Handle import statements."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    imports.append(f"{node.module}.{alias.name}")
    
    def _extract_function_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature from AST node."""
        # Build basic signature
        args = []
        
        # Regular arguments
        for arg in node.args.args:
            args.append(arg.arg)
        
        # Varargs (*args)
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        
        # Keyword arguments (**kwargs)
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        
        signature = f"def {node.name}({', '.join(args)}):"
        return signature

    def _analyze_calls(self, tree: ast.AST, symbols: Dict[str, SymbolInfo], file_path: str):
        """Analyze function calls and build caller-callee relationships."""
        visitor = CallAnalysisVisitor(symbols, file_path)
        visitor.visit(tree)


class CallAnalysisVisitor(ast.NodeVisitor):
    """AST visitor to analyze function calls and build caller-callee relationships."""
    
    def __init__(self, symbols: Dict[str, SymbolInfo], file_path: str):
        self.symbols = symbols
        self.file_path = file_path
        self.current_function_stack = []
        self.current_class = None
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition and track context."""
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition and track context."""
        # File path is already relative after our fix
        relative_path = self.file_path
        
        # Handle methods within classes
        if self.current_class:
            function_id = f"{relative_path}::{self.current_class}.{node.name}"
        else:
            function_id = f"{relative_path}::{node.name}"
            
        self.current_function_stack.append(function_id)
        
        # Visit all child nodes within this function
        self.generic_visit(node)
        
        # Pop the function from stack when done
        self.current_function_stack.pop()
    
    def visit_Call(self, node: ast.Call):
        """Visit function call and record relationship."""
        try:
            # Get the function name being called
            called_function = None
            
            if isinstance(node.func, ast.Name):
                # Direct function call: function_name()
                called_function = node.func.id
            elif isinstance(node.func, ast.Attribute):
                # Method call: obj.method() or module.function()
                called_function = node.func.attr
                
            if called_function and self.current_function_stack:
                # Get the current calling function
                caller_function = self.current_function_stack[-1]
                
                # Look for the called function in our symbols and add relationship
                for symbol_id, symbol_info in self.symbols.items():
                    if symbol_info.type in ["function", "method"]:
                        # Extract just the function/method name from the symbol ID
                        symbol_name = symbol_id.split("::")[-1]
                        
                        # Check for exact match or method name match (ClassName.method)
                        if (symbol_name == called_function or 
                            symbol_name.endswith(f".{called_function}")):
                            # Add caller to the called function's called_by list
                            if caller_function not in symbol_info.called_by:
                                symbol_info.called_by.append(caller_function)
                            break
        except Exception:
            # Silently handle parsing errors for complex call patterns
            pass
            
        # Continue visiting child nodes
        self.generic_visit(node)
    
