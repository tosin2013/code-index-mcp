"""
Zig parsing strategy using regex patterns with tree-sitter fallback.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from .base_strategy import ParsingStrategy
from ..models.symbol_info import SymbolInfo
from ..models.file_info import FileInfo

logger = logging.getLogger(__name__)

try:
    import tree_sitter
    import tree_sitter_zig
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter-zig not available, using regex fallback")


class ZigParsingStrategy(ParsingStrategy):
    """Zig parsing strategy using regex patterns with tree-sitter fallback."""
    
    def __init__(self):
        if TREE_SITTER_AVAILABLE:
            self.zig_language = tree_sitter.Language(tree_sitter_zig.language())
        else:
            self.zig_language = None
    
    def get_language_name(self) -> str:
        return "zig"
    
    def get_supported_extensions(self) -> List[str]:
        return ['.zig', '.zon']
    
    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Zig file using regex patterns."""
        # For now, use regex parsing even if tree-sitter is available
        # Tree-sitter-zig might not be stable yet
        return self._regex_parse(file_path, content)
    
    def _regex_parse(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Zig file using regex patterns."""
        symbols = {}
        functions = []
        classes = []  # Zig uses structs, not classes
        imports = []
        
        lines = content.splitlines()
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Import statements (const x = @import(...))
            if '@import(' in line:
                import_match = re.search(r'@import\("([^"]+)"\)', line)
                if import_match:
                    imports.append(import_match.group(1))
            
            # Function declarations (pub fn, fn)
            elif re.match(r'(pub\s+)?fn\s+\w+', line):
                func_match = re.match(r'(?:pub\s+)?fn\s+(\w+)', line)
                if func_match:
                    func_name = func_match.group(1)
                    symbol_id = self._create_symbol_id(file_path, func_name)
                    symbols[symbol_id] = SymbolInfo(
                        type="function",
                        file=file_path,
                        line=i + 1,
                        signature=line
                    )
                    functions.append(func_name)
            
            # Struct declarations
            elif re.match(r'const\s+\w+\s*=\s*struct\s*\{', line):
                struct_match = re.match(r'const\s+(\w+)\s*=\s*struct', line)
                if struct_match:
                    struct_name = struct_match.group(1)
                    symbol_id = self._create_symbol_id(file_path, struct_name)
                    symbols[symbol_id] = SymbolInfo(
                        type="struct",
                        file=file_path,
                        line=i + 1
                    )
                    classes.append(struct_name)
            
            # Union declarations
            elif re.match(r'const\s+\w+\s*=\s*union', line):
                union_match = re.match(r'const\s+(\w+)\s*=\s*union', line)
                if union_match:
                    union_name = union_match.group(1)
                    symbol_id = self._create_symbol_id(file_path, union_name)
                    symbols[symbol_id] = SymbolInfo(
                        type="union",
                        file=file_path,
                        line=i + 1
                    )
                    classes.append(union_name)
            
            # Enum declarations
            elif re.match(r'const\s+\w+\s*=\s*enum', line):
                enum_match = re.match(r'const\s+(\w+)\s*=\s*enum', line)
                if enum_match:
                    enum_name = enum_match.group(1)
                    symbol_id = self._create_symbol_id(file_path, enum_name)
                    symbols[symbol_id] = SymbolInfo(
                        type="enum",
                        file=file_path,
                        line=i + 1
                    )
                    classes.append(enum_name)
        
        # Phase 2: Add call relationship analysis
        self._analyze_zig_calls(content, symbols, file_path)
        
        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(lines),
            symbols={"functions": functions, "classes": classes},
            imports=imports
        )
        
        return symbols, file_info
    
    def _analyze_zig_calls(self, content: str, symbols: Dict[str, SymbolInfo], file_path: str):
        """Analyze Zig function calls for relationships."""
        lines = content.splitlines()
        current_function = None
        
        for i, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            # Track current function context
            if line.startswith('fn '):
                func_name = self._extract_zig_function_name(line)
                if func_name:
                    current_function = self._create_symbol_id(file_path, func_name)
            
            # Find function calls: functionName() or obj.methodName()
            if current_function and ('(' in line and ')' in line):
                called_functions = self._extract_zig_called_functions(line)
                for called_func in called_functions:
                    # Find the called function in symbols and add relationship
                    for symbol_id, symbol_info in symbols.items():
                        if called_func in symbol_id.split("::")[-1]:
                            if current_function not in symbol_info.called_by:
                                symbol_info.called_by.append(current_function)
    
    def _extract_zig_function_name(self, line: str) -> Optional[str]:
        """Extract function name from Zig function declaration."""
        try:
            # fn functionName(...) or pub fn functionName(...)
            import re
            match = re.search(r'fn\s+(\w+)\s*\(', line)
            if match:
                return match.group(1)
        except:
            pass
        return None
    
    def _extract_zig_called_functions(self, line: str) -> List[str]:
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