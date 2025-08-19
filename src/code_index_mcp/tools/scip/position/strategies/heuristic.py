"""
Heuristic-based position detection strategy.

This strategy uses heuristic analysis and pattern matching to find symbol
positions with low confidence as a fallback when other methods fail.
"""

import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from .base import PositionStrategy
from ..confidence import LocationInfo, ConfidenceLevel

logger = logging.getLogger(__name__)


class HeuristicStrategy(PositionStrategy):
    """
    Heuristic-based position detection strategy.
    
    This strategy provides low confidence position detection using
    pattern matching, text search, and educated guesses when more
    reliable methods are not available.
    """
    
    def __init__(self):
        """Initialize the heuristic strategy."""
        super().__init__("heuristic")
        self._common_patterns = self._build_common_patterns()
    
    def _build_common_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Build common symbol detection patterns across languages."""
        return {
            'function_patterns': [
                {
                    'pattern': r'\bdef\s+{name}\s*\(',
                    'language': 'python',
                    'confidence_boost': 0.8,
                    'description': 'Python function definition'
                },
                {
                    'pattern': r'\bfunction\s+{name}\s*\(',
                    'language': 'javascript',
                    'confidence_boost': 0.8,
                    'description': 'JavaScript function declaration'
                },
                {
                    'pattern': r'\bfn\s+{name}\s*\(',
                    'language': 'zig',
                    'confidence_boost': 0.8,
                    'description': 'Zig function definition'
                },
                {
                    'pattern': r'\b{name}\s*=\s*function',
                    'language': 'javascript',
                    'confidence_boost': 0.7,
                    'description': 'JavaScript function expression'
                },
                {
                    'pattern': r'\b{name}\s*=\s*\([^)]*\)\s*=>',
                    'language': 'javascript',
                    'confidence_boost': 0.7,
                    'description': 'JavaScript arrow function'
                }
            ],
            'class_patterns': [
                {
                    'pattern': r'\bclass\s+{name}\s*[:({{]',
                    'language': 'python',
                    'confidence_boost': 0.9,
                    'description': 'Python class definition'
                },
                {
                    'pattern': r'\bclass\s+{name}\s*\{{',
                    'language': 'javascript',
                    'confidence_boost': 0.9,
                    'description': 'JavaScript class declaration'
                },
                {
                    'pattern': r'\b@interface\s+{name}\s*[:(]',
                    'language': 'objective-c',
                    'confidence_boost': 0.9,
                    'description': 'Objective-C interface declaration'
                }
            ],
            'variable_patterns': [
                {
                    'pattern': r'\b{name}\s*=',
                    'language': 'general',
                    'confidence_boost': 0.5,
                    'description': 'Variable assignment'
                },
                {
                    'pattern': r'\bconst\s+{name}\s*=',
                    'language': 'javascript',
                    'confidence_boost': 0.7,
                    'description': 'JavaScript const declaration'
                },
                {
                    'pattern': r'\blet\s+{name}\s*=',
                    'language': 'javascript',
                    'confidence_boost': 0.7,
                    'description': 'JavaScript let declaration'
                },
                {
                    'pattern': r'\bvar\s+{name}\s*=',
                    'language': 'javascript',
                    'confidence_boost': 0.6,
                    'description': 'JavaScript var declaration'
                }
            ],
            'import_patterns': [
                {
                    'pattern': r'\bfrom\s+\S+\s+import\s+.*{name}',
                    'language': 'python',
                    'confidence_boost': 0.6,
                    'description': 'Python import statement'
                },
                {
                    'pattern': r'\bimport\s+.*{name}',
                    'language': 'python',
                    'confidence_boost': 0.6,
                    'description': 'Python import statement'
                },
                {
                    'pattern': r'\bimport\s+\{{.*{name}.*\}}',
                    'language': 'javascript',
                    'confidence_boost': 0.6,
                    'description': 'JavaScript named import'
                }
            ]
        }
    
    def get_confidence_level(self) -> ConfidenceLevel:
        """Heuristic analysis provides low confidence positions."""
        return ConfidenceLevel.LOW
    
    def can_handle_symbol(self, scip_symbol: str, document) -> bool:
        """
        Check if we can attempt heuristic analysis for this symbol.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: Document context
            
        Returns:
            Always True as this is the fallback strategy
        """
        # Heuristic strategy can always attempt to find a symbol
        return True
    
    def try_resolve(
        self,
        scip_symbol: str,
        document,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[LocationInfo]:
        """
        Try to resolve position using heuristic analysis.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: Document containing source text or metadata
            context: Optional context information
            
        Returns:
            LocationInfo with low confidence if found, None otherwise
        """
        # Get source text
        source_text = self._get_source_text(document, context)
        if not source_text:
            return None
        
        # Parse symbol information
        symbol_info = self._parse_symbol(scip_symbol)
        if not symbol_info:
            return None
        
        # Try different heuristic approaches in order of confidence
        strategies = [
            self._find_by_definition_patterns,
            self._find_by_usage_patterns,
            self._find_by_text_search,
            self._find_by_line_estimation
        ]
        
        best_location = None
        best_confidence_score = 0.0
        
        for strategy_func in strategies:
            try:
                location = strategy_func(source_text, symbol_info, context)
                if location:
                    confidence_score = location.metadata.get('confidence_score', 0.0)
                    if confidence_score > best_confidence_score:
                        best_location = location
                        best_confidence_score = confidence_score
            except Exception as e:
                logger.debug(f"Heuristic strategy failed: {strategy_func.__name__}: {e}")
        
        return best_location
    
    def _get_source_text(self, document, context: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract source text from document or context."""
        # Try context first
        if context:
            if 'source_text' in context:
                return context['source_text']
            if 'file_content' in context:
                return context['file_content']
        
        # Try document
        if hasattr(document, 'text') and document.text:
            return document.text
        if hasattr(document, 'content') and document.content:
            return document.content
        
        # Try reading from file path
        if context and 'file_path' in context:
            try:
                with open(context['file_path'], 'r', encoding='utf-8') as f:
                    return f.read()
            except (OSError, UnicodeDecodeError) as e:
                logger.debug(f"Failed to read source file: {e}")
        
        return None
    
    def _parse_symbol(self, scip_symbol: str) -> Optional[Dict[str, Any]]:
        """Parse SCIP symbol to extract useful information."""
        try:
            info = {
                'original': scip_symbol,
                'name': None,
                'type': 'unknown',
                'scope': [],
                'language': None
            }
            
            # Extract from SCIP symbol format
            if scip_symbol.startswith('local '):
                local_part = scip_symbol[6:]
                
                # Remove descriptor suffix
                if local_part.endswith('.'):
                    local_part = local_part[:-1]
                
                # Parse different symbol types
                if '(' in local_part:
                    # Function-like symbol
                    base_name = local_part.split('(')[0]
                    info['type'] = 'function'
                elif local_part.count('.') > 0:
                    # Nested symbol (method, attribute, etc.)
                    parts = local_part.split('.')
                    base_name = parts[-1]
                    info['scope'] = parts[:-1]
                    info['type'] = 'method' if len(parts) > 1 else 'attribute'
                else:
                    # Simple identifier
                    base_name = local_part
                    info['type'] = 'identifier'
                
                # Clean up name
                if '/' in base_name:
                    info['name'] = base_name.split('/')[-1]
                else:
                    info['name'] = base_name
                
                # Try to infer language
                info['language'] = self._infer_language(scip_symbol)
                
                return info
                
        except Exception as e:
            logger.debug(f"Failed to parse symbol {scip_symbol}: {e}")
        
        return None
    
    def _infer_language(self, scip_symbol: str) -> Optional[str]:
        """Infer programming language from SCIP symbol."""
        symbol_lower = scip_symbol.lower()
        
        if '.py' in symbol_lower or 'python' in symbol_lower:
            return 'python'
        elif '.js' in symbol_lower or '.ts' in symbol_lower or 'javascript' in symbol_lower:
            return 'javascript'
        elif '.zig' in symbol_lower:
            return 'zig'
        elif '.java' in symbol_lower:
            return 'java'
        elif '.m' in symbol_lower or '.mm' in symbol_lower or 'objc' in symbol_lower:
            return 'objective-c'
        elif '.go' in symbol_lower:
            return 'go'
        elif '.rs' in symbol_lower:
            return 'rust'
        
        return None
    
    def _find_by_definition_patterns(
        self, 
        source_text: str, 
        symbol_info: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[LocationInfo]:
        """Find symbol using definition patterns."""
        symbol_name = symbol_info['name']
        symbol_type = symbol_info['type']
        language = symbol_info['language']
        
        if not symbol_name:
            return None
        
        # Get relevant patterns based on symbol type
        pattern_groups = []
        if symbol_type == 'function':
            pattern_groups.append(self._common_patterns['function_patterns'])
        elif symbol_type in ['class', 'identifier']:
            pattern_groups.append(self._common_patterns['class_patterns'])
            pattern_groups.append(self._common_patterns['variable_patterns'])
        else:
            pattern_groups.append(self._common_patterns['variable_patterns'])
        
        best_match = None
        best_confidence = 0.0
        
        for patterns in pattern_groups:
            for pattern_info in patterns:
                # Filter by language if known
                if language and pattern_info['language'] != 'general' and pattern_info['language'] != language:
                    continue
                
                # Format pattern with symbol name
                pattern = pattern_info['pattern'].format(name=re.escape(symbol_name))
                
                match = re.search(pattern, source_text, re.MULTILINE | re.IGNORECASE)
                if match:
                    confidence = pattern_info['confidence_boost']
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = (match, pattern_info)
        
        if best_match:
            match, pattern_info = best_match
            line_num = source_text[:match.start()].count('\n') + 1
            line_start = source_text.rfind('\n', 0, match.start()) + 1
            column_num = match.start() - line_start + 1
            
            return LocationInfo.from_heuristic(
                line=line_num,
                column=column_num,
                heuristic_type="definition_pattern",
                method=f"heuristic_pattern_{pattern_info['language']}"
            )
        
        return None
    
    def _find_by_usage_patterns(
        self, 
        source_text: str, 
        symbol_info: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[LocationInfo]:
        """Find symbol by looking for usage patterns."""
        symbol_name = symbol_info['name']
        
        if not symbol_name:
            return None
        
        # Look for the symbol in import statements first
        import_patterns = self._common_patterns['import_patterns']
        
        for pattern_info in import_patterns:
            pattern = pattern_info['pattern'].format(name=re.escape(symbol_name))
            match = re.search(pattern, source_text, re.MULTILINE)
            
            if match:
                line_num = source_text[:match.start()].count('\n') + 1
                line_start = source_text.rfind('\n', 0, match.start()) + 1
                column_num = match.start() - line_start + 1
                
                metadata = {
                    'confidence_score': 0.6,
                    'usage_type': 'import',
                    'pattern_description': pattern_info['description']
                }
                
                location = LocationInfo.from_heuristic(
                    line=line_num,
                    column=column_num,
                    heuristic_type="usage_pattern",
                    method="heuristic_import"
                )
                location.metadata.update(metadata)
                return location
        
        return None
    
    def _find_by_text_search(
        self, 
        source_text: str, 
        symbol_info: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[LocationInfo]:
        """Find symbol using simple text search."""
        symbol_name = symbol_info['name']
        
        if not symbol_name or len(symbol_name) < 2:
            return None
        
        # Look for word boundary matches
        pattern = rf'\b{re.escape(symbol_name)}\b'
        matches = list(re.finditer(pattern, source_text))
        
        if matches:
            # Use the first match (usually the definition)
            match = matches[0]
            line_num = source_text[:match.start()].count('\n') + 1
            line_start = source_text.rfind('\n', 0, match.start()) + 1
            column_num = match.start() - line_start + 1
            
            metadata = {
                'confidence_score': 0.3,
                'total_matches': len(matches),
                'search_method': 'text_search'
            }
            
            location = LocationInfo.from_heuristic(
                line=line_num,
                column=column_num,
                heuristic_type="text_search",
                method="heuristic_text_search"
            )
            location.metadata.update(metadata)
            return location
        
        return None
    
    def _find_by_line_estimation(
        self, 
        source_text: str, 
        symbol_info: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Optional[LocationInfo]:
        """Estimate position based on file structure and symbol type."""
        total_lines = source_text.count('\n') + 1
        
        # Make educated guesses based on symbol type and common patterns
        estimated_line = 1
        confidence_score = 0.1
        
        symbol_type = symbol_info['type']
        
        if symbol_type == 'function':
            # Functions often appear in the middle of files
            estimated_line = max(1, total_lines // 3)
            confidence_score = 0.2
        elif symbol_type == 'class':
            # Classes often appear early in files
            estimated_line = max(1, total_lines // 4)
            confidence_score = 0.15
        elif symbol_type == 'import':
            # Imports usually at the top
            estimated_line = min(10, total_lines // 10)
            confidence_score = 0.25
        else:
            # Default to somewhere in the first half
            estimated_line = max(1, total_lines // 2)
        
        metadata = {
            'confidence_score': confidence_score,
            'estimation_method': 'line_estimation',
            'total_lines': total_lines,
            'symbol_type': symbol_type
        }
        
        location = LocationInfo.from_heuristic(
            line=estimated_line,
            column=1,
            heuristic_type="line_estimation",
            method="heuristic_estimation"
        )
        location.metadata.update(metadata)
        return location
    
    def find_all_occurrences(
        self, 
        symbol_name: str, 
        source_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[LocationInfo]:
        """
        Find all occurrences of a symbol in source text.
        
        Args:
            symbol_name: Name of the symbol to find
            source_text: Source code text
            context: Optional context information
            
        Returns:
            List of LocationInfo objects for all occurrences
        """
        occurrences = []
        
        if not symbol_name or len(symbol_name) < 2:
            return occurrences
        
        # Find all word boundary matches
        pattern = rf'\b{re.escape(symbol_name)}\b'
        matches = re.finditer(pattern, source_text)
        
        for i, match in enumerate(matches):
            line_num = source_text[:match.start()].count('\n') + 1
            line_start = source_text.rfind('\n', 0, match.start()) + 1
            column_num = match.start() - line_start + 1
            
            metadata = {
                'occurrence_index': i,
                'confidence_score': 0.3,
                'search_method': 'all_occurrences'
            }
            
            location = LocationInfo.from_heuristic(
                line=line_num,
                column=column_num,
                heuristic_type="occurrence",
                method="heuristic_all_occurrences"
            )
            location.metadata.update(metadata)
            occurrences.append(location)
        
        return occurrences
    
    def get_heuristic_confidence(
        self, 
        symbol_info: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate heuristic confidence score for a symbol.
        
        Args:
            symbol_info: Parsed symbol information
            context: Optional context information
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.3  # Base confidence for heuristic methods
        
        # Boost confidence based on symbol characteristics
        if symbol_info.get('type') == 'function':
            base_confidence += 0.2
        elif symbol_info.get('type') == 'class':
            base_confidence += 0.15
        
        # Boost if we have language information
        if symbol_info.get('language'):
            base_confidence += 0.1
        
        # Boost if symbol name is longer (less likely to be false positive)
        name_length = len(symbol_info.get('name', ''))
        if name_length > 5:
            base_confidence += 0.1
        elif name_length > 10:
            base_confidence += 0.15
        
        return min(1.0, base_confidence)