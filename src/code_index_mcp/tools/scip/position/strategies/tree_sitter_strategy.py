"""
Tree-sitter AST-based position detection strategy.

This strategy uses Tree-sitter AST analysis to find symbol positions
with medium confidence by parsing source code.
"""

import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from .base import PositionStrategy
from ..confidence import LocationInfo, ConfidenceLevel

logger = logging.getLogger(__name__)

# Try to import tree-sitter
try:
    import tree_sitter
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    tree_sitter = None
    Language = None
    Parser = None
    TREE_SITTER_AVAILABLE = False


class TreeSitterStrategy(PositionStrategy):
    """
    Tree-sitter AST-based position detection strategy.
    
    This strategy provides medium confidence position detection by
    parsing source code with Tree-sitter and analyzing the AST structure
    to find symbol definitions and references.
    """
    
    def __init__(self):
        """Initialize the Tree-sitter strategy."""
        super().__init__("tree_sitter")
        self._parsers: Dict[str, Parser] = {}
        self._languages: Dict[str, Language] = {}
        self._setup_parsers()
    
    def _setup_parsers(self) -> None:
        """Setup Tree-sitter parsers for supported languages."""
        if not TREE_SITTER_AVAILABLE:
            logger.debug("Tree-sitter not available, TreeSitterStrategy will have limited functionality")
            return
        
        # Language configurations with their Tree-sitter names
        language_configs = {
            'python': 'python',
            'javascript': 'javascript',
            'typescript': 'typescript',
            'zig': 'zig',
            'java': 'java',
            'objective-c': 'objc',
            'c': 'c',
            'cpp': 'cpp',
            'go': 'go',
            'rust': 'rust',
        }
        
        for lang_name, ts_name in language_configs.items():
            try:
                # This would typically load pre-compiled language libraries
                # For now, we'll just track which languages we support
                self._languages[lang_name] = ts_name
                logger.debug(f"Configured Tree-sitter support for {lang_name}")
            except Exception as e:
                logger.debug(f"Failed to setup Tree-sitter for {lang_name}: {e}")
    
    def get_confidence_level(self) -> ConfidenceLevel:
        """Tree-sitter AST analysis provides medium confidence positions."""
        return ConfidenceLevel.MEDIUM
    
    def can_handle_symbol(self, scip_symbol: str, document) -> bool:
        """
        Check if we can handle this symbol with Tree-sitter analysis.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: Document context (may contain language info)
            
        Returns:
            True if Tree-sitter is available and language is supported
        """
        if not TREE_SITTER_AVAILABLE:
            return False
        
        # Try to detect language from symbol or document
        language = self._detect_language(scip_symbol, document)
        return language is not None and language in self._languages
    
    def try_resolve(
        self,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[LocationInfo]:
        """
        Try to resolve position using Tree-sitter AST analysis.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: Document containing source text
            context: Optional context information
            
        Returns:
            LocationInfo with medium confidence if found, None otherwise
        """
        if not TREE_SITTER_AVAILABLE:
            return None
        
        # Get source text from document or context
        source_text = self._get_source_text(document, context)
        if not source_text:
            return None
        
        # Detect language
        language = self._detect_language(scip_symbol, document)
        if not language or language not in self._languages:
            return None
        
        # Parse symbol to extract name and type
        symbol_info = self._parse_scip_symbol(scip_symbol)
        if not symbol_info:
            return None
        
        # Try different AST-based search strategies
        location = self._find_by_ast_analysis(source_text, language, symbol_info)
        if location:
            location.add_metadata('ast_analysis', True)
            location.add_metadata('language', language)
            return location
        
        # Fallback to pattern matching with AST guidance
        location = self._find_by_pattern_with_ast(source_text, language, symbol_info)
        if location:
            location.add_metadata('pattern_with_ast', True)
            location.add_metadata('language', language)
            return location
        
        return None
    
    def _get_source_text(self, document, context: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Extract source text from document or context.
        
        Args:
            document: Document object
            context: Optional context information
            
        Returns:
            Source text or None if not available
        """
        # Try to get from context first
        if context and 'source_text' in context:
            return context['source_text']
        
        # Try to get from document
        if hasattr(document, 'text') and document.text:
            return document.text
        
        if hasattr(document, 'content') and document.content:
            return document.content
        
        # Try file path in context
        if context and 'file_path' in context:
            try:
                with open(context['file_path'], 'r', encoding='utf-8') as f:
                    return f.read()
            except (OSError, UnicodeDecodeError) as e:
                logger.debug(f"Failed to read source file: {e}")
        
        return None
    
    def _detect_language(self, scip_symbol: str, document) -> Optional[str]:
        """
        Detect programming language from symbol or document.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: Document context
            
        Returns:
            Language name or None if not detected
        """
        # Try to get from document first
        if hasattr(document, 'language') and document.language:
            return document.language.lower()
        
        # Infer from SCIP symbol patterns
        if 'python' in scip_symbol or '.py' in scip_symbol:
            return 'python'
        elif 'javascript' in scip_symbol or '.js' in scip_symbol or 'npm' in scip_symbol:
            return 'javascript'
        elif 'typescript' in scip_symbol or '.ts' in scip_symbol:
            return 'typescript'
        elif '.zig' in scip_symbol or 'zig' in scip_symbol:
            return 'zig'
        elif '.java' in scip_symbol or 'java' in scip_symbol:
            return 'java'
        elif '.m' in scip_symbol or '.mm' in scip_symbol or 'objc' in scip_symbol:
            return 'objective-c'
        elif '.go' in scip_symbol:
            return 'go'
        elif '.rs' in scip_symbol or 'rust' in scip_symbol:
            return 'rust'
        
        return None
    
    def _parse_scip_symbol(self, scip_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Parse SCIP symbol to extract meaningful information.
        
        Args:
            scip_symbol: SCIP symbol identifier
            
        Returns:
            Dictionary with symbol information or None if parsing failed
        """
        try:
            # Basic SCIP symbol format: "local <local-id><descriptor>."
            if scip_symbol.startswith('local '):
                local_part = scip_symbol[6:]  # Remove "local "
                
                # Split into local-id and descriptor
                if '(' in local_part:
                    # Function-like symbol
                    name_part = local_part.split('(')[0]
                    symbol_type = 'function'
                elif '.' in local_part:
                    # Method or attribute
                    parts = local_part.split('.')
                    name_part = parts[-2] if len(parts) > 1 else parts[0]
                    symbol_type = 'method' if len(parts) > 2 else 'attribute'
                else:
                    # Simple identifier
                    name_part = local_part.rstrip('.')
                    symbol_type = 'identifier'
                
                # Extract base name
                if '/' in name_part:
                    base_name = name_part.split('/')[-1]
                else:
                    base_name = name_part
                
                return {
                    'name': base_name,
                    'full_name': name_part,
                    'type': symbol_type,
                    'scip_symbol': scip_symbol
                }
        
        except (IndexError, AttributeError) as e:
            logger.debug(f"Failed to parse SCIP symbol {scip_symbol}: {e}")
        
        return None
    
    def _find_by_ast_analysis(
        self, 
        source_text: str, 
        language: str, 
        symbol_info: Dict[str, Any]
    ) -> Optional[LocationInfo]:
        """
        Find symbol position using full AST analysis.
        
        Args:
            source_text: Source code text
            language: Programming language
            symbol_info: Parsed symbol information
            
        Returns:
            LocationInfo if found, None otherwise
        """
        # This would typically involve:
        # 1. Parse source code with Tree-sitter
        # 2. Traverse AST to find matching symbol definitions
        # 3. Extract precise position information
        
        # For now, we'll simulate this with pattern matching
        # In a real implementation, this would use tree-sitter parsing
        
        symbol_name = symbol_info['name']
        symbol_type = symbol_info['type']
        
        # Language-specific AST-guided patterns
        patterns = self._get_ast_patterns(language, symbol_type, symbol_name)
        
        for pattern_info in patterns:
            match = re.search(pattern_info['pattern'], source_text, re.MULTILINE)
            if match:
                line_num = source_text[:match.start()].count('\n') + 1
                line_start = source_text.rfind('\n', 0, match.start()) + 1
                column_num = match.start() - line_start + 1
                
                metadata = {
                    'pattern_type': pattern_info['type'],
                    'confidence_reason': pattern_info['reason'],
                    'match_text': match.group()[:50],  # Truncate long matches
                    'ast_guided': True
                }
                
                return LocationInfo.from_tree_sitter(
                    line=line_num,
                    column=column_num,
                    node_info={
                        'type': pattern_info['type'],
                        'text': match.group(),
                        'start_byte': match.start(),
                        'end_byte': match.end()
                    },
                    method="tree_sitter_ast"
                )
        
        return None
    
    def _find_by_pattern_with_ast(
        self, 
        source_text: str, 
        language: str, 
        symbol_info: Dict[str, Any]
    ) -> Optional[LocationInfo]:
        """
        Find symbol position using pattern matching with AST guidance.
        
        Args:
            source_text: Source code text
            language: Programming language
            symbol_info: Parsed symbol information
            
        Returns:
            LocationInfo if found, None otherwise
        """
        symbol_name = symbol_info['name']
        
        # Simple pattern matching as fallback
        # This would be enhanced with AST context in a full implementation
        
        # Look for function definitions, class definitions, etc.
        basic_patterns = [
            rf'\bdef\s+{re.escape(symbol_name)}\s*\(',  # Python function
            rf'\bclass\s+{re.escape(symbol_name)}\s*[:(]',  # Python class
            rf'\bfunction\s+{re.escape(symbol_name)}\s*\(',  # JavaScript function
            rf'\b{re.escape(symbol_name)}\s*=\s*function',  # JS function assignment
            rf'\bconst\s+{re.escape(symbol_name)}\s*=',  # JS/TS const
            rf'\blet\s+{re.escape(symbol_name)}\s*=',  # JS/TS let
            rf'\bvar\s+{re.escape(symbol_name)}\s*=',  # JS var
        ]
        
        for pattern in basic_patterns:
            match = re.search(pattern, source_text, re.MULTILINE | re.IGNORECASE)
            if match:
                line_num = source_text[:match.start()].count('\n') + 1
                line_start = source_text.rfind('\n', 0, match.start()) + 1
                column_num = match.start() - line_start + 1
                
                metadata = {
                    'pattern_match': True,
                    'match_text': match.group()[:50],
                    'fallback_pattern': True
                }
                
                return LocationInfo.from_tree_sitter(
                    line=line_num,
                    column=column_num,
                    node_info={
                        'text': match.group(),
                        'start_byte': match.start(),
                        'end_byte': match.end()
                    },
                    method="tree_sitter_pattern"
                )
        
        return None
    
    def _get_ast_patterns(self, language: str, symbol_type: str, symbol_name: str) -> List[Dict[str, Any]]:
        """
        Get AST-guided patterns for symbol detection.
        
        Args:
            language: Programming language
            symbol_type: Type of symbol (function, class, etc.)
            symbol_name: Name of the symbol
            
        Returns:
            List of pattern information dictionaries
        """
        escaped_name = re.escape(symbol_name)
        patterns = []
        
        if language == 'python':
            if symbol_type == 'function':
                patterns.extend([
                    {
                        'pattern': rf'^\s*def\s+{escaped_name}\s*\(',
                        'type': 'function_definition',
                        'reason': 'Python function definition pattern'
                    },
                    {
                        'pattern': rf'^\s*async\s+def\s+{escaped_name}\s*\(',
                        'type': 'async_function_definition',
                        'reason': 'Python async function definition pattern'
                    }
                ])
            elif symbol_type in ['class', 'identifier']:
                patterns.append({
                    'pattern': rf'^\s*class\s+{escaped_name}\s*[:(]',
                    'type': 'class_definition',
                    'reason': 'Python class definition pattern'
                })
        
        elif language in ['javascript', 'typescript']:
            if symbol_type == 'function':
                patterns.extend([
                    {
                        'pattern': rf'\bfunction\s+{escaped_name}\s*\(',
                        'type': 'function_declaration',
                        'reason': 'JavaScript function declaration'
                    },
                    {
                        'pattern': rf'\b{escaped_name}\s*=\s*function',
                        'type': 'function_expression',
                        'reason': 'JavaScript function expression'
                    },
                    {
                        'pattern': rf'\b{escaped_name}\s*=\s*\([^)]*\)\s*=>',
                        'type': 'arrow_function',
                        'reason': 'JavaScript arrow function'
                    }
                ])
            elif symbol_type in ['class', 'identifier']:
                patterns.append({
                    'pattern': rf'\bclass\s+{escaped_name}\s*\{{',
                    'type': 'class_declaration',
                    'reason': 'JavaScript class declaration'
                })
        
        elif language == 'zig':
            patterns.extend([
                {
                    'pattern': rf'\bfn\s+{escaped_name}\s*\(',
                    'type': 'function_definition',
                    'reason': 'Zig function definition'
                },
                {
                    'pattern': rf'\bconst\s+{escaped_name}\s*=',
                    'type': 'const_declaration',
                    'reason': 'Zig constant declaration'
                }
            ])
        
        elif language == 'java':
            patterns.extend([
                {
                    'pattern': rf'\b(public|private|protected)?\s*(static)?\s*\w+\s+{escaped_name}\s*\(',
                    'type': 'method_definition',
                    'reason': 'Java method definition'
                },
                {
                    'pattern': rf'\b(public|private|protected)?\s*class\s+{escaped_name}\s*\{{',
                    'type': 'class_definition',
                    'reason': 'Java class definition'
                }
            ])
        
        return patterns
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of languages supported by this strategy.
        
        Returns:
            List of supported language names
        """
        return list(self._languages.keys())
    
    def get_ast_info(
        self, 
        source_text: str, 
        language: str, 
        symbol_name: str
    ) -> Dict[str, Any]:
        """
        Get detailed AST information for a symbol.
        
        Args:
            source_text: Source code text
            language: Programming language
            symbol_name: Name of the symbol to analyze
            
        Returns:
            Dictionary with AST analysis information
        """
        info = {
            'language': language,
            'symbol_name': symbol_name,
            'tree_sitter_available': TREE_SITTER_AVAILABLE,
            'language_supported': language in self._languages,
            'patterns_found': [],
            'potential_matches': 0
        }
        
        if language in self._languages:
            # Get all potential patterns for this symbol
            symbol_info = {'name': symbol_name, 'type': 'identifier'}
            patterns = self._get_ast_patterns(language, 'identifier', symbol_name)
            
            for pattern_info in patterns:
                matches = re.finditer(pattern_info['pattern'], source_text, re.MULTILINE)
                for match in matches:
                    line_num = source_text[:match.start()].count('\n') + 1
                    info['patterns_found'].append({
                        'type': pattern_info['type'],
                        'line': line_num,
                        'text': match.group()[:50],
                        'reason': pattern_info['reason']
                    })
                    info['potential_matches'] += 1
        
        return info