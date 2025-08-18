"""
SCIP Symbol Analyzer - Enhanced symbol analysis for accurate code intelligence

This module provides the main SCIPSymbolAnalyzer class that replaces the legacy
SCIPQueryTool with accurate symbol location detection, proper type classification,
and comprehensive call relationship analysis.
"""

import os
import logging
from typing import Dict, List, Optional, Any, Set
from functools import lru_cache

from .symbol_definitions import (
    SymbolDefinition, FileAnalysis, ImportGroup, LocationInfo,
    SymbolLocationError, SymbolResolutionError
)
from .relationship_info import SCIPRelationshipReader
from ...scip.core.symbol_manager import SCIPSymbolManager

logger = logging.getLogger(__name__)

# Try to import SCIP protobuf definitions
try:
    from ...scip.proto import scip_pb2
    SCIP_PROTO_AVAILABLE = True
except ImportError:
    scip_pb2 = None
    SCIP_PROTO_AVAILABLE = False
    logger.warning("SCIP protobuf definitions not available")


class SCIPSymbolAnalyzer:
    """
    Enhanced SCIP symbol analyzer with accurate position detection and call relationships.
    
    This class replaces the legacy SCIPQueryTool and provides:
    - Accurate symbol location extraction from SCIP Range data
    - Proper symbol type classification using SCIP SymbolKind enum
    - Comprehensive call relationship analysis
    - Cross-file symbol resolution
    - LLM-optimized output formatting
    """
    
    def __init__(self):
        """Initialize the symbol analyzer."""
        self._symbol_kind_cache: Dict[int, str] = {}
        self._scip_symbol_cache: Dict[str, Dict[str, Any]] = {}
        self._symbol_parser: Optional[SCIPSymbolManager] = None
        self._relationship_reader = SCIPRelationshipReader()
        
        # Initialize SCIP symbol kind mapping
        self._init_symbol_kind_mapping()
    
    def _init_symbol_kind_mapping(self):
        """Initialize SCIP SymbolKind enum mapping."""
        if not SCIP_PROTO_AVAILABLE:
            # Fallback numeric mapping when protobuf not available
            self._symbol_kind_map = {
                3: 'class',       # CLASS
                11: 'function',   # FUNCTION  
                14: 'method',     # METHOD
                29: 'variable',   # VARIABLE
                4: 'constant',    # CONSTANT
                6: 'enum',        # ENUM
                7: 'enum_member', # ENUM_MEMBER
                9: 'field',       # FIELD
                23: 'property',   # PROPERTY
                5: 'constructor', # CONSTRUCTOR
                15: 'module',     # MODULE
                16: 'namespace',  # NAMESPACE
                12: 'interface',  # INTERFACE
                25: 'struct',     # STRUCT
                33: 'trait',      # TRAIT
                35: 'macro',      # MACRO
            }
        else:
            # Use actual protobuf enum when available
            self._symbol_kind_map = {}
            # Will be populated dynamically using scip_pb2.SymbolKind.Name()
    
    def analyze_file(self, file_path: str, scip_index) -> FileAnalysis:
        """
        Main entry point for file analysis.
        
        Args:
            file_path: Relative path to the file to analyze
            scip_index: SCIP index containing all project data
            
        Returns:
            FileAnalysis object with complete symbol information
            
        Raises:
            ValueError: If file not found or analysis fails
        """
        try:
            logger.debug(f"Starting analysis for file: {file_path}")
            
            # Initialize symbol parser from index metadata (for scip-* symbol parsing)
            try:
                project_root = getattr(getattr(scip_index, 'metadata', None), 'project_root', '') or ''
                if project_root:
                    self._symbol_parser = SCIPSymbolManager(project_root)
            except Exception:
                self._symbol_parser = None

            # Step 1: Find the document in SCIP index
            document = self._find_document(file_path, scip_index)
            if not document:
                logger.warning(f"Document not found in SCIP index: {file_path}")
                return self._create_empty_analysis(file_path)
            
            logger.debug(f"Found document with {len(document.symbols)} symbols")
            
            # Step 2: Extract all symbols with accurate metadata
            symbols = self._extract_all_symbols(document)
            logger.debug(f"Extracted {len(symbols)} symbols")
            
            # Step 3: Extract call relationships
            self._extract_call_relationships(document, symbols, scip_index)
            logger.debug("Completed call relationship extraction")
            
            # Step 4: Organize results into final structure
            result = self._organize_results(document, symbols, scip_index)
            logger.debug(f"Analysis complete: {len(result.functions)} functions, {len(result.classes)} classes")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze file {file_path}: {e}")
            # Return partial analysis rather than failing completely
            return self._create_error_analysis(file_path, str(e))
    
    def _find_document(self, file_path: str, scip_index) -> Optional[Any]:
        """
        Find the SCIP document for the given file path.
        
        Args:
            file_path: File path to search for
            scip_index: SCIP index object
            
        Returns:
            SCIP document or None if not found
        """
        if not hasattr(scip_index, 'documents'):
            logger.error("Invalid SCIP index: missing documents attribute")
            return None
        
        # Normalize path for comparison
        normalized_target = self._normalize_path(file_path)
        
        # Try exact match first
        for document in scip_index.documents:
            if self._normalize_path(document.relative_path) == normalized_target:
                return document
        
        # Try case-insensitive match
        normalized_lower = normalized_target.lower()
        for document in scip_index.documents:
            if self._normalize_path(document.relative_path).lower() == normalized_lower:
                logger.debug(f"Found case-insensitive match for {file_path}")
                return document
        
        return None
    
    def _normalize_path(self, path: str) -> str:
        """Normalize file path for consistent comparison."""
        return path.replace('\\', '/').lstrip('./')
    
    def _extract_all_symbols(self, document) -> Dict[str, SymbolDefinition]:
        """
        Extract all symbols from the document in a single pass.
        
        Args:
            document: SCIP document object
            
        Returns:
            Dictionary mapping SCIP symbols to SymbolDefinition objects
        """
        symbols = {}
        
        for symbol_info in document.symbols:
            try:
                # Extract basic symbol information
                scip_symbol = symbol_info.symbol
                display_name = getattr(symbol_info, 'display_name', '')
                symbol_kind = getattr(symbol_info, 'kind', 0)
                
                # Parse symbol name and classification
                parsed_name, class_name = self._parse_symbol_identity(scip_symbol, display_name)
                if not parsed_name:
                    continue
                
                # Get symbol type from SCIP kind
                symbol_type = self._classify_symbol_type(symbol_kind, scip_symbol)
                
                # Extract precise location
                # Extract location (never fails now)
                location = self._extract_precise_location(scip_symbol, document)
                
                # Debug: Check location type
                if not isinstance(location, LocationInfo):
                    logger.error(f"Location extraction returned wrong type: {type(location)} for symbol {scip_symbol}")
                    location = LocationInfo(line=1, column=1)  # Fallback
                
                # Create symbol definition
                symbol_def = SymbolDefinition(
                    name=parsed_name,
                    line=location.line,
                    column=location.column,
                    symbol_type=symbol_type,
                    class_name=class_name,
                    scip_symbol=scip_symbol
                )
                
                # Extract additional metadata
                self._enrich_symbol_metadata(symbol_def, symbol_info, document)
                
                symbols[scip_symbol] = symbol_def
                logger.debug(f"Processed symbol: {parsed_name} ({symbol_type}) at {location.line}:{location.column}")
                
            except Exception as e:
                logger.warning(f"Failed to process symbol {getattr(symbol_info, 'symbol', 'unknown')}: {e}")
                continue
        
        return symbols
    
    def _parse_symbol_identity(self, scip_symbol: str, display_name: str = '') -> tuple[str, Optional[str]]:
        """
        Parse symbol name and class ownership from SCIP symbol string.
        
        Args:
            scip_symbol: SCIP symbol identifier
            display_name: Display name from symbol info
            
        Returns:
            Tuple of (symbol_name, class_name)
        """
        # Use display name if available and meaningful
        if display_name and not display_name.startswith('__'):
            name = display_name
        else:
            # Extract from SCIP symbol
            name = self._extract_name_from_scip_symbol(scip_symbol)
        
        # Extract class name if this is a class member
        class_name = self._extract_class_name(scip_symbol)
        
        return name, class_name
    
    @lru_cache(maxsize=500)
    def _extract_name_from_scip_symbol(self, scip_symbol: str) -> str:
        """Extract clean, human-readable symbol name from SCIP symbol identifier."""
        try:
            if scip_symbol.startswith('local:'):
                # local:src.module.Class#method_name().
                symbol_path = scip_symbol[6:]  # Remove 'local:' prefix
                
                if '#' in symbol_path:
                    # Method or field: extract after '#'
                    method_part = symbol_path.split('#')[-1]
                    return self._clean_symbol_name(method_part)
                else:
                    # Class or top-level function: extract last part
                    class_part = symbol_path.split('.')[-1]
                    return self._clean_symbol_name(class_part)
                    
            elif scip_symbol.startswith('external:'):
                # external:module.path/ClassName#method_name().
                if '/' in scip_symbol:
                    after_slash = scip_symbol.split('/')[-1]
                    if '#' in after_slash:
                        method_part = after_slash.split('#')[-1]
                        return self._clean_symbol_name(method_part)
                    else:
                        return self._clean_symbol_name(after_slash)
                else:
                    # Just module reference
                    module_part = scip_symbol[9:]  # Remove 'external:'
                    return self._clean_symbol_name(module_part.split('.')[-1])
            
            # Fallback: clean up whatever we have
            return self._clean_symbol_name(scip_symbol.split('/')[-1].split('#')[-1])
            
        except Exception as e:
            logger.debug(f"Error extracting name from {scip_symbol}: {e}")
            return "unknown"
    
    def _clean_symbol_name(self, raw_name: str) -> str:
        """Clean symbol name for human readability."""
        # Remove common suffixes and prefixes
        cleaned = raw_name.rstrip('().#')
        
        # Remove module path prefixes if present
        if '.' in cleaned:
            cleaned = cleaned.split('.')[-1]
        
        # Handle special cases
        if not cleaned or cleaned.isdigit():
            return "unknown"
            
        return cleaned
    
    @lru_cache(maxsize=500)
    def _extract_class_name(self, scip_symbol: str) -> Optional[str]:
        """Extract clean class name if this symbol belongs to a class.

        Supports:
        - Legacy local/external formats with '#': local:...Class#method / external:.../Class#method
        - Current scip-* local format where descriptors encode path as
          <file_path>/<Class>/<method>().
        """
        try:
            # Newer scip-* local symbols: parse descriptors path
            if scip_symbol.startswith('scip-'):
                parts = scip_symbol.split(' ', 4)
                descriptors = parts[4] if len(parts) == 5 else (parts[3] if len(parts) >= 4 else '')
                if descriptors:
                    components = [p for p in descriptors.split('/') if p]
                    if len(components) >= 2:
                        candidate = components[-2]
                        return candidate if candidate and not candidate.isdigit() else None

            if '#' not in scip_symbol:
                return None

            if scip_symbol.startswith('local:'):
                # local:src.module.ClassName#method
                symbol_path = scip_symbol[6:]  # Remove 'local:'
                class_part = symbol_path.split('#')[0]

                # Extract just the class name (last part of module path)
                if '.' in class_part:
                    class_name = class_part.split('.')[-1]
                else:
                    class_name = class_part

                return class_name if class_name and not class_name.isdigit() else None

            elif scip_symbol.startswith('external:'):
                # external:module/ClassName#method
                if '/' in scip_symbol:
                    path_part = scip_symbol.split('/')[-1]
                    if '#' in path_part:
                        class_name = path_part.split('#')[0]
                        return class_name if class_name and not class_name.isdigit() else None

        except Exception as e:
            logger.debug(f"Error extracting class name from {scip_symbol}: {e}")

        return None
    
    def _classify_symbol_type(self, scip_kind: int, scip_symbol: str) -> str:
        """
        Classify symbol type using SCIP SymbolKind enum.
        
        Args:
            scip_kind: SCIP SymbolKind enum value
            scip_symbol: SCIP symbol string for additional context
            
        Returns:
            Standardized symbol type string
        """
        # Try to get cached result
        if scip_kind in self._symbol_kind_cache:
            base_type = self._symbol_kind_cache[scip_kind]
        else:
            base_type = self._get_scip_kind_name(scip_kind)
            self._symbol_kind_cache[scip_kind] = base_type
        
        # Refine classification based on index symbol structure
        if base_type == 'function':
            # Legacy/colon formats use '#'
            if '#' in scip_symbol:
                return 'method'
            # Current scip-* local descriptors path: <file_path>/<Class>/<method>().
            if scip_symbol.startswith('scip-'):
                parts = scip_symbol.split(' ', 4)
                descriptors = parts[4] if len(parts) == 5 else (parts[3] if len(parts) >= 4 else '')
                if descriptors:
                    components = [p for p in descriptors.split('/') if p]
                    if len(components) >= 2:
                        last_comp = components[-1]
                        if last_comp.endswith('().') or last_comp.endswith('()'):
                            return 'method'
        
        return base_type
    
    def _get_scip_kind_name(self, kind: int) -> str:
        """Get symbol type name from SCIP SymbolKind."""
        if SCIP_PROTO_AVAILABLE:
            try:
                # Use protobuf enum name
                enum_name = scip_pb2.SymbolKind.Name(kind)
                return self._normalize_kind_name(enum_name)
            except (ValueError, AttributeError):
                pass
        
        # Fallback to numeric mapping
        return self._symbol_kind_map.get(kind, 'unknown')
    
    def _normalize_kind_name(self, enum_name: str) -> str:
        """Normalize SCIP enum name to standard type."""
        enum_name = enum_name.lower()
        
        # Map SCIP names to our standard names
        if enum_name == 'class':
            return 'class'
        elif enum_name in ['function', 'func']:
            return 'function'
        elif enum_name == 'method':
            return 'method'
        elif enum_name in ['variable', 'var']:
            return 'variable'
        elif enum_name in ['constant', 'const']:
            return 'constant'
        elif enum_name == 'field':
            return 'field'
        elif enum_name == 'property':
            return 'property'
        else:
            return enum_name
    
    def _extract_precise_location(self, scip_symbol: str, document) -> LocationInfo:
        """
        Never-fail location extraction with intelligent fallbacks using SCIPSymbolManager.
        
        Args:
            scip_symbol: SCIP symbol identifier
            document: SCIP document containing occurrences
            
        Returns:
            LocationInfo with best available location and confidence level
        """
        # Layer 1: Standard SCIP occurrence location
        location = self._find_definition_location(scip_symbol, document)
        if location:
            location.confidence = 'definition'
            return location
        
        location = self._find_any_location(scip_symbol, document)
        if location:
            location.confidence = 'occurrence' 
            return location
        
        # Layer 2: SCIPSymbolManager-based symbol structure inference
        if self._symbol_parser:
            location = self._infer_location_from_symbol_structure(scip_symbol, document)
            if location:
                location.confidence = 'inferred'
                return location
        
        # Layer 3: Symbol type-based default location
        location = self._get_default_location_by_symbol_type(scip_symbol)
        location.confidence = 'default'
        return location
    
    def _find_definition_location(self, scip_symbol: str, document) -> Optional[LocationInfo]:
        """Find the definition occurrence for a symbol."""
        for occurrence in document.occurrences:
            if occurrence.symbol == scip_symbol and self._is_definition(occurrence):
                location = self._parse_occurrence_location(occurrence)
                if location:
                    return location
        return None
    
    def _find_any_location(self, scip_symbol: str, document) -> Optional[LocationInfo]:
        """Find any occurrence with location data for a symbol."""
        for occurrence in document.occurrences:
            if occurrence.symbol == scip_symbol:
                location = self._parse_occurrence_location(occurrence)
                if location:
                    return location
        return None
    
    def _is_definition(self, occurrence) -> bool:
        """Check if an occurrence represents a definition."""
        if not hasattr(occurrence, 'symbol_roles'):
            return False
        
        try:
            if SCIP_PROTO_AVAILABLE:
                return bool(occurrence.symbol_roles & scip_pb2.SymbolRole.Definition)
            else:
                # Fallback: Definition role = 1
                return bool(occurrence.symbol_roles & 1)
        except (AttributeError, TypeError):
            return False
    
    def _parse_occurrence_location(self, occurrence) -> Optional[LocationInfo]:
        """Parse location information from SCIP occurrence."""
        try:
            if not hasattr(occurrence, 'range') or not occurrence.range:
                return None
            
            range_obj = occurrence.range
            if not hasattr(range_obj, 'start') or not range_obj.start:
                return None
            
            start = range_obj.start
            if len(start) >= 2:
                # SCIP uses 0-based indexing, convert to 1-based
                line = start[0] + 1
                column = start[1] + 1
                return LocationInfo(line=line, column=column)
        
        except (AttributeError, IndexError, TypeError) as e:
            logger.debug(f"Failed to parse occurrence location: {e}")
        
        return None
    
    def _enrich_symbol_metadata(self, symbol: SymbolDefinition, symbol_info, document):
        """Enrich symbol with additional metadata from SCIP data."""
        # Extract documentation if available
        if hasattr(symbol_info, 'documentation') and symbol_info.documentation:
            # Could extract docstrings here if needed
            pass
        
        # For functions/methods, extract parameter information
        if symbol.is_callable():
            symbol.parameters = self._extract_function_parameters(symbol.scip_symbol, symbol_info, document)
            symbol.return_type = self._extract_return_type(symbol.scip_symbol, symbol_info)
            symbol.is_async = self._is_async_function(symbol.scip_symbol, symbol_info)
        
        # For classes, extract methods and attributes
        elif symbol.symbol_type == 'class':
            symbol.methods, symbol.attributes = self._extract_class_members(symbol.scip_symbol, document)
            symbol.inherits_from = self._extract_inheritance(symbol.scip_symbol, symbol_info)
        
        # For variables, extract type and scope information
        elif symbol.symbol_type == 'variable':
            symbol.type = self._extract_variable_type(symbol.scip_symbol, symbol_info)
            symbol.is_global = self._is_global_variable(symbol.scip_symbol, document)
        
        # For constants, extract value if available
        elif symbol.symbol_type == 'constant':
            symbol.value = self._extract_constant_value(symbol.scip_symbol, symbol_info)
    
    def _extract_call_relationships(self, document, symbols: Dict[str, SymbolDefinition], scip_index):
        """
        Extract all relationships from SCIP document using the new relationship reader.
        
        Args:
            document: SCIP document containing symbols and relationships
            symbols: Dictionary of extracted symbols
            scip_index: Full SCIP index for cross-file resolution
        """
        logger.debug("Starting relationship extraction using SCIP relationship reader")
        
        # Use the new relationship reader to extract all relationships
        all_relationships = self._relationship_reader.extract_relationships_from_document(document)
        
        # Assign relationships to symbols
        for symbol_id, symbol_def in symbols.items():
            if symbol_id in all_relationships:
                symbol_def.relationships = all_relationships[symbol_id]
                logger.debug(f"Assigned {symbol_def.relationships.get_total_count()} relationships to {symbol_def.name}")
        
        logger.debug(f"Relationship extraction completed for {len(symbols)} symbols")
    
    def _organize_results(self, document, symbols: Dict[str, SymbolDefinition], scip_index=None) -> FileAnalysis:
        """
        Organize extracted symbols into final FileAnalysis structure.
        
        Args:
            document: SCIP document
            symbols: Extracted symbol definitions
            scip_index: Full SCIP index for external symbol extraction
            
        Returns:
            FileAnalysis with organized results
        """
        # Create file analysis result
        result = FileAnalysis(
            file_path=document.relative_path,
            language=document.language,
            line_count=self._estimate_line_count(document),
            size_bytes=0  # TODO: Could get from filesystem if needed
        )
        
        # Add symbols to appropriate collections
        for symbol in symbols.values():
            result.add_symbol(symbol)
        
        # Extract import information from occurrences
        self._extract_imports(document, result.imports)
        
        # Also extract imports from external symbols (for strategies like Objective-C)
        if scip_index:
            self._extract_imports_from_external_symbols(scip_index, result.imports)
        
        return result

    
    
    def _estimate_line_count(self, document) -> int:
        """Estimate line count from document data."""
        # Try to get from document text if available
        if hasattr(document, 'text') and document.text:
            return len(document.text.splitlines())
        
        # Fallback: estimate from occurrence ranges
        max_line = 0
        for occurrence in document.occurrences:
            try:
                if occurrence.range and occurrence.range.start:
                    line = occurrence.range.start[0] + 1
                    max_line = max(max_line, line)
            except (AttributeError, IndexError):
                continue
        
        return max_line if max_line > 0 else 100  # Default estimate
    
    def _is_function_call(self, occurrence) -> bool:
        """
        Check if an occurrence represents a function call.
        
        Based on debug analysis, function calls have roles=0 in our SCIP data,
        so we need to identify them by other characteristics.
        
        Args:
            occurrence: SCIP occurrence object
            
        Returns:
            True if this occurrence is a function call
        """
        try:
            symbol = occurrence.symbol
            roles = getattr(occurrence, 'symbol_roles', 0)
            
            # Check if it's a definition (role = 1) - these are NOT calls
            if roles & 1:
                return False
            
            # Check if it's an import (role = 2) - these are NOT calls 
            if roles & 2:
                return False
            
            # For roles = 0, check if it looks like a function call by symbol format
            if roles == 0:
                # Function calls typically have () in the symbol
                if '()' in symbol:
                    # But exclude definitions at line start positions
                    if hasattr(occurrence, 'range') and occurrence.range:
                        if hasattr(occurrence.range, 'start') and occurrence.range.start:
                            line = occurrence.range.start[0] + 1
                            col = occurrence.range.start[1] + 1
                            # Function definitions usually start at column 1 or 5 (indented)
                            # Function calls are usually at higher column positions
                            return col > 5
                    return True
            
            # Traditional role-based detection as fallback
            if SCIP_PROTO_AVAILABLE:
                return bool(roles & (scip_pb2.SymbolRole.Read | scip_pb2.SymbolRole.Reference))
            else:
                # Fallback: Read=8, Reference=4
                return bool(roles & (8 | 4))
                
        except (AttributeError, TypeError):
            return False
    
    def _find_containing_function(self, occurrence, function_symbols: Dict[str, SymbolDefinition], document) -> Optional[SymbolDefinition]:
        """
        Find which function contains the given occurrence.
        
        Args:
            occurrence: SCIP occurrence object
            function_symbols: Map of SCIP symbols to function definitions
            document: SCIP document
            
        Returns:
            SymbolDefinition of the containing function, or None
        """
        try:
            occurrence_line = self._get_occurrence_line(occurrence)
            if occurrence_line <= 0:
                return None
            
            # Find the function that contains this line
            best_match = None
            best_distance = float('inf')
            
            for scip_symbol, func_def in function_symbols.items():
                # Function should start before or at the occurrence line
                if func_def.line <= occurrence_line:
                    distance = occurrence_line - func_def.line
                    if distance < best_distance:
                        best_distance = distance
                        best_match = func_def
            
            return best_match
            
        except Exception as e:
            logger.debug(f"Error finding containing function: {e}")
            return None
    
    def _get_occurrence_line(self, occurrence) -> int:
        """Extract line number from SCIP occurrence."""
        try:
            if hasattr(occurrence, 'range') and occurrence.range:
                if hasattr(occurrence.range, 'start') and occurrence.range.start:
                    return occurrence.range.start[0] + 1  # Convert to 1-based
        except (AttributeError, IndexError, TypeError):
            pass
        return 0
    
    def _resolve_call_target(self, target_symbol: str, scip_index, current_document) -> Optional[Dict[str, Any]]:
        """Use SCIPSymbolManager to resolve call target information.
        
        Args:
            target_symbol: SCIP symbol being called
            scip_index: Full SCIP index for cross-file lookup
            current_document: Current document for local symbol context
            
        Returns:
            Dictionary with call target information or None
        """
        if not self._symbol_parser:
            return self._fallback_resolve_target(target_symbol, current_document)
        
        try:
            # Use SCIPSymbolManager to parse symbol
            symbol_info = self._symbol_parser.parse_symbol(target_symbol)
            if not symbol_info:
                return None
            
            # Extract clear symbol name from descriptors
            target_name = self._extract_symbol_name_from_descriptors(symbol_info.descriptors)
            
            # Handle based on manager type
            if symbol_info.manager == 'local':
                # Local call: use existing file path extraction
                file_path = self._symbol_parser.get_file_path_from_symbol(target_symbol)
                target_line = self._find_local_symbol_location(target_symbol, current_document)
                return {
                    'name': target_name,
                    'scope': 'local',
                    'file': file_path or current_document.relative_path,
                    'line': target_line
                }
            
            elif symbol_info.manager in ['stdlib', 'pip', 'npm']:
                # External call: get info from parsed results
                return {
                    'name': target_name,
                    'scope': 'external',
                    'package': symbol_info.package,
                    'module': self._extract_module_from_descriptors(symbol_info.descriptors)
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error resolving call target {target_symbol}: {e}")
            return None
    
    
    def _find_symbol_definition(self, target_symbol: str, scip_index) -> tuple[Optional[str], int]:
        """
        Find the definition location of a symbol in the SCIP index.
        
        Args:
            target_symbol: SCIP symbol to find
            scip_index: Full SCIP index
            
        Returns:
            Tuple of (file_path, line_number) or (None, 0) if not found
        """
        try:
            for document in scip_index.documents:
                for occurrence in document.occurrences:
                    if (occurrence.symbol == target_symbol and 
                        self._is_definition(occurrence)):
                        line = self._get_occurrence_line(occurrence)
                        return document.relative_path, line
        except Exception as e:
            logger.debug(f"Error finding symbol definition: {e}")
        
        return None, 0
    
    def _extract_symbol_name_from_descriptors(self, descriptors: str) -> str:
        """Extract symbol name from SCIP descriptors."""
        # utils.py/helper_function() -> helper_function
        # MyClass/method() -> method
        if '/' in descriptors:
            symbol_part = descriptors.split('/')[-1]
            return symbol_part.rstrip('().')
        return descriptors.rstrip('().')
    
    def _extract_module_from_descriptors(self, descriptors: str) -> Optional[str]:
        """Extract module name from descriptors."""
        # os/ -> os, pathlib/Path -> pathlib
        if '/' in descriptors:
            return descriptors.split('/')[0]
        return descriptors.strip('/')
    
    def _fallback_resolve_target(self, target_symbol: str, current_document) -> Optional[Dict[str, Any]]:
        """Fallback resolution when SCIPSymbolManager is not available."""
        try:
            # Parse the target symbol using legacy method
            target_name, target_class = self._parse_symbol_identity(target_symbol)
            if not target_name:
                return None
            
            # Basic resolution for legacy formats
            if target_symbol.startswith('local:'):
                target_location = self._find_local_symbol_location(target_symbol, current_document)
                return {
                    'name': target_name,
                    'scope': 'local', 
                    'file': current_document.relative_path,
                    'line': target_location
                }
            
            return {
                'name': target_name,
                'scope': 'unknown',
                'file': 'unknown',
                'line': 0
            }
            
        except Exception as e:
            logger.debug(f"Fallback resolution failed for {target_symbol}: {e}")
            return None
    
    def _find_local_symbol_location(self, target_symbol: str, document) -> int:
        """Find the line number for a local symbol definition."""
        try:
            for occurrence in document.occurrences:
                if (occurrence.symbol == target_symbol and 
                    self._is_definition(occurrence)):
                    return self._get_occurrence_line(occurrence)
        except Exception as e:
            logger.debug(f"Error finding local symbol location: {e}")
        return 0
    

    
    def _extract_imports(self, document, imports: ImportGroup):
        """Use SCIPSymbolManager to correctly parse imports."""
        if not self._symbol_parser:
            logger.debug("No symbol parser available, skipping import extraction")
            return
            
        try:
            seen_modules = set()
            
            # Method 1: Extract from occurrences with Import role (traditional approach)
            for occurrence in document.occurrences:
                # Only process Import role symbols
                if not self._is_import_occurrence(occurrence):
                    continue
                    
                symbol_info = self._symbol_parser.parse_symbol(occurrence.symbol)
                if not symbol_info:
                    continue
                
                # Handle based on manager type
                if symbol_info.manager == 'stdlib':
                    module_name = self._extract_module_from_descriptors(symbol_info.descriptors)
                    if module_name and module_name not in seen_modules:
                        imports.add_import(module_name, 'standard_library')
                        seen_modules.add(module_name)
                        
                elif symbol_info.manager == 'pip':
                    # pip packages: package name is the module name
                    package_name = symbol_info.package
                    if package_name and package_name not in seen_modules:
                        imports.add_import(package_name, 'third_party') 
                        seen_modules.add(package_name)
                        
                elif symbol_info.manager == 'local':
                    # Local imports: extract module path from descriptors
                    module_path = self._extract_local_module_path(symbol_info.descriptors)
                    if module_path and module_path not in seen_modules:
                        imports.add_import(module_path, 'local')
                        seen_modules.add(module_path)
            
            logger.debug(f"Extracted {len(seen_modules)} unique imports from SCIP occurrences")
            
        except Exception as e:
            logger.debug(f"Error extracting imports from occurrences: {e}")

    def _extract_imports_from_external_symbols(self, scip_index, imports: ImportGroup):
        """Extract imports from SCIP index external symbols (for strategies like Objective-C)."""
        try:
            if not hasattr(scip_index, 'external_symbols'):
                logger.debug("No external_symbols in SCIP index")
                return
                
            seen_modules = set()
            
            for symbol_info in scip_index.external_symbols:
                if not symbol_info.symbol:
                    continue
                    
                # Parse the external symbol
                parsed_symbol = self._symbol_parser.parse_symbol(symbol_info.symbol) if self._symbol_parser else None
                if not parsed_symbol:
                    # Fallback: try to extract framework name from symbol string
                    framework_name = self._extract_framework_from_symbol_string(symbol_info.symbol)
                    if framework_name and framework_name not in seen_modules:
                        # Classify based on symbol pattern
                        import_type = self._classify_external_symbol(symbol_info.symbol)
                        imports.add_import(framework_name, import_type)
                        seen_modules.add(framework_name)
                        logger.debug(f"Extracted external dependency: {framework_name} ({import_type})")
                    continue
                
                # Handle based on manager type
                if parsed_symbol.manager in ['system', 'unknown']:
                    # For Objective-C system frameworks
                    package_name = parsed_symbol.package
                    if package_name and package_name not in seen_modules:
                        imports.add_import(package_name, 'standard_library')
                        seen_modules.add(package_name)
                        
                elif parsed_symbol.manager in ['cocoapods', 'carthage']:
                    # Third-party Objective-C dependencies
                    package_name = parsed_symbol.package
                    if package_name and package_name not in seen_modules:
                        imports.add_import(package_name, 'third_party')
                        seen_modules.add(package_name)
            
            logger.debug(f"Extracted {len(seen_modules)} unique imports from external symbols")
            
        except Exception as e:
            logger.debug(f"Error extracting imports from external symbols: {e}")

    def _extract_framework_from_symbol_string(self, symbol_string: str) -> Optional[str]:
        """Extract framework name from SCIP symbol string."""
        try:
            # Handle symbols like "scip-unknown unknown Foundation Foundation *."
            parts = symbol_string.split()
            if len(parts) >= 4:
                # The package name is typically the 3rd or 4th part
                for part in parts[2:5]:  # Check parts 2, 3, 4
                    if part and part != 'unknown' and not part.endswith('.'):
                        return part
            return None
        except Exception:
            return None

    def _classify_external_symbol(self, symbol_string: str) -> str:
        """Classify external symbol as standard_library, third_party, or local."""
        try:
            # Check for known system frameworks
            system_frameworks = {
                'Foundation', 'UIKit', 'CoreData', 'CoreGraphics', 'QuartzCore',
                'AVFoundation', 'CoreLocation', 'MapKit', 'CoreAnimation',
                'Security', 'SystemConfiguration', 'CFNetwork', 'CoreFoundation',
                'AppKit', 'Cocoa', 'WebKit', 'JavaScriptCore'
            }
            
            for framework in system_frameworks:
                if framework in symbol_string:
                    return 'standard_library'
            
            # Check for third-party indicators
            if any(indicator in symbol_string.lower() for indicator in ['cocoapods', 'carthage', 'pods']):
                return 'third_party'
            
            return 'standard_library'  # Default for external symbols
            
        except Exception:
            return 'standard_library'
    
    def _parse_external_module(self, external_symbol: str) -> Optional[Dict[str, str]]:
        """Parse external SCIP symbol to extract module information."""
        try:
            if not external_symbol.startswith('external:'):
                return None
            
            # Remove 'external:' prefix and parse path
            symbol_path = external_symbol[9:]
            
            # Extract base module path (before '/' or '#')
            if '/' in symbol_path:
                module_path = symbol_path.split('/')[0]
            elif '#' in symbol_path:
                module_path = symbol_path.split('#')[0]
            else:
                module_path = symbol_path
            
            # Clean up module path
            module_path = module_path.rstrip('.')
            if not module_path:
                return None
            
            # Categorize the import
            category = self._categorize_import(module_path)
            
            return {
                'module': module_path,
                'category': category
            }
            
        except Exception as e:
            logger.debug(f"Error parsing external module {external_symbol}: {e}")
            return None
    
    def _categorize_import(self, module_path: str) -> str:
        """Categorize import as standard_library, third_party, or local."""
        # Standard library modules (common ones)
        stdlib_modules = {
            'os', 'sys', 'json', 'time', 'datetime', 'logging', 'pathlib',
            'typing', 'dataclasses', 'functools', 'itertools', 'collections',
            're', 'math', 'random', 'threading', 'subprocess', 'shutil',
            'contextlib', 'traceback', 'warnings', 'weakref', 'copy',
            'pickle', 'base64', 'hashlib', 'hmac', 'uuid', 'urllib',
            'http', 'socketserver', 'email', 'mimetypes', 'csv', 'configparser',
            'argparse', 'getopt', 'tempfile', 'glob', 'fnmatch', 'linecache',
            'pprint', 'textwrap', 'string', 'struct', 'codecs', 'unicodedata',
            'io', 'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile'
        }
        
        # Local imports (relative imports or project-specific patterns)
        if module_path.startswith('.'):
            return 'local'
        
        # Check for common project patterns
        if any(pattern in module_path for pattern in ['src.', 'lib.', 'app.', 'project.']):
            return 'local'
        
        # Standard library check
        base_module = module_path.split('.')[0]
        if base_module in stdlib_modules:
            return 'standard_library'
        
        # Everything else is third_party
        return 'third_party'
    
    
    def _is_import_occurrence(self, occurrence) -> bool:
        """Check if occurrence represents an import."""
        # Import role = 2 (based on debug results)
        return hasattr(occurrence, 'symbol_roles') and (occurrence.symbol_roles & 2)
    
    def _extract_local_module_path(self, descriptors: str) -> Optional[str]:
        """Extract module path from local descriptors."""
        # utils.py/helper_function() -> utils
        # services/user_service.py/UserService -> services.user_service
        if '/' in descriptors:
            file_part = descriptors.split('/')[0]
            if file_part.endswith('.py'):
                return file_part[:-3].replace('/', '.')
            return file_part.replace('/', '.')
        return None
    
    def _extract_class_name_from_descriptors(self, descriptors: str) -> Optional[str]:
        """Extract class name from descriptors."""
        # test_empty_functions.py/TestClass# -> TestClass
        # test_empty_functions.py/TestClass/method() -> TestClass (if this is class symbol)
        parts = descriptors.split('/')
        if len(parts) >= 2:
            class_part = parts[1]
            # Remove trailing # if present (class symbols end with #)
            return class_part.rstrip('#')
        return None
    
    def _is_class_member(self, descriptors: str, class_name: str) -> bool:
        """Check if descriptors belongs to specified class member."""
        # test_empty_functions.py/TestClass/method_one() contains TestClass
        return f"/{class_name}/" in descriptors
    
    def _extract_member_name(self, descriptors: str, class_name: str) -> Optional[str]:
        """Extract class member name."""
        # test_empty_functions.py/TestClass/method_one() -> method_one
        if f"/{class_name}/" in descriptors:
            after_class = descriptors.split(f"/{class_name}/", 1)[1]
            return after_class.rstrip('().')
        return None
    
    def _is_method_kind(self, kind: int) -> bool:
        """Check if SCIP kind represents a method or function."""
        method_kinds = {'function', 'method'}
        kind_name = self._get_scip_kind_name(kind)
        return kind_name in method_kinds
    
    def _infer_location_from_symbol_structure(self, scip_symbol: str, document) -> Optional[LocationInfo]:
        """Infer location based on symbol structure using SCIPSymbolManager."""
        symbol_info = self._symbol_parser.parse_symbol(scip_symbol)
        if not symbol_info:
            return None
        
        try:
            # Strategy 1: If class member, estimate based on class location
            if '/' in symbol_info.descriptors:
                parts = symbol_info.descriptors.split('/')
                if len(parts) >= 3:  # file.py/ClassName/member
                    class_symbol = f"{symbol_info.scheme} {symbol_info.manager} {symbol_info.package} {'/'.join(parts[:2])}"
                    class_location = self._find_symbol_location_in_document(class_symbol, document)
                    if class_location:
                        # Members usually 2-10 lines after class definition
                        return LocationInfo(
                            line=class_location.line + 3,
                            column=class_location.column + 4
                        )
            
            # Strategy 2: Estimate based on file path (if symbol belongs to current file)
            if symbol_info.manager == 'local':
                file_path = self._symbol_parser.get_file_path_from_symbol(scip_symbol)
                if file_path and file_path in document.relative_path:
                    return self._estimate_position_in_file(symbol_info.descriptors, document)
            
        except Exception as e:
            logger.debug(f"Symbol location inference failed: {e}")
        
        return None
    
    def _find_symbol_location_in_document(self, target_symbol: str, document) -> Optional[LocationInfo]:
        """Find location of target symbol in document."""
        for occurrence in document.occurrences:
            if occurrence.symbol == target_symbol:
                location = self._parse_occurrence_location(occurrence)
                if location:
                    return location
        return None
    
    def _estimate_position_in_file(self, descriptors: str, document) -> Optional[LocationInfo]:
        """Estimate position based on descriptors and document structure."""
        # Simple heuristic: estimate line based on symbol type
        if 'class' in descriptors.lower():
            return LocationInfo(line=max(1, len(document.occurrences) // 4), column=1)
        elif any(marker in descriptors.lower() for marker in ['function', 'method']):
            return LocationInfo(line=max(5, len(document.occurrences) // 2), column=1)
        else:
            return LocationInfo(line=1, column=1)
    
    def _get_default_location_by_symbol_type(self, scip_symbol: str) -> LocationInfo:
        """Provide reasonable default location based on symbol type."""
        symbol_lower = scip_symbol.lower()
        if 'class' in symbol_lower:
            return LocationInfo(line=1, column=1)  # Classes usually at file start
        elif any(marker in symbol_lower for marker in ['function', 'method']):
            return LocationInfo(line=5, column=1)  # Functions usually after imports
        else:
            return LocationInfo(line=1, column=1)  # Other symbols default position
    
    def _create_empty_analysis(self, file_path: str) -> FileAnalysis:
        """Create empty analysis result for missing files."""
        return FileAnalysis(
            file_path=file_path,
            language='unknown',
            line_count=0,
            size_bytes=0
        )
    
    def _create_error_analysis(self, file_path: str, error_message: str) -> FileAnalysis:
        """Create error analysis result."""
        logger.error(f"Analysis error for {file_path}: {error_message}")
        result = FileAnalysis(
            file_path=file_path,
            language='unknown',
            line_count=0,
            size_bytes=0
        )
        # Could add error information to metadata if needed
        return result
    
    def _extract_function_parameters(self, scip_symbol: str, symbol_info, document) -> List[str]:
        """
        Extract function parameter names from SCIP data.
        
        Args:
            scip_symbol: SCIP symbol identifier
            symbol_info: SCIP symbol information
            document: SCIP document containing occurrences
            
        Returns:
            List of parameter names
        """
        try:
            # Try to extract from documentation (Python strategy stores params here)
            if hasattr(symbol_info, 'documentation') and symbol_info.documentation:
                for doc_line in symbol_info.documentation:
                    if doc_line.startswith('Parameters: '):
                        param_str = doc_line[12:]  # Remove 'Parameters: '
                        return [p.strip() for p in param_str.split(',') if p.strip()]
            
            # Try to extract from symbol information signature
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                return self._parse_signature_parameters(symbol_info.signature)
            
            # Fallback: try to extract from symbol occurrences and surrounding context
            return self._extract_parameters_from_occurrences(scip_symbol, document)
            
        except Exception as e:
            logger.debug(f"Failed to extract parameters for {scip_symbol}: {e}")
            return []
    
    def _parse_signature_parameters(self, signature: str) -> List[str]:
        """Parse parameter names from function signature."""
        try:
            # Basic signature parsing - handle common patterns
            if '(' in signature and ')' in signature:
                param_section = signature.split('(')[1].split(')')[0]
                if not param_section.strip():
                    return []
                
                params = []
                for param in param_section.split(','):
                    param = param.strip()
                    if param:
                        # Extract parameter name (before type annotation if present)
                        param_name = param.split(':')[0].strip()
                        if param_name and param_name != 'self':
                            params.append(param_name)
                        elif param_name == 'self':
                            params.append('self')
                
                return params
                
        except Exception as e:
            logger.debug(f"Error parsing signature parameters: {e}")
        
        return []
    
    def _extract_parameters_from_occurrences(self, scip_symbol: str, document) -> List[str]:
        """Extract parameters by analyzing symbol occurrences in the document."""
        # This is a simplified implementation
        # A more sophisticated approach would analyze the AST or source code directly
        return []
    
    def _extract_return_type(self, scip_symbol: str, symbol_info) -> Optional[str]:
        """Extract return type from SCIP data."""
        try:
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                signature = symbol_info.signature
                if '->' in signature:
                    return_part = signature.split('->')[-1].strip()
                    return return_part if return_part else None
        except Exception as e:
            logger.debug(f"Error extracting return type for {scip_symbol}: {e}")
        return None
    
    def _is_async_function(self, scip_symbol: str, symbol_info) -> bool:
        """Check if function is async based on SCIP data."""
        try:
            # Check documentation for async marker (Python AST analyzer stores this)
            if hasattr(symbol_info, 'documentation') and symbol_info.documentation:
                for doc_line in symbol_info.documentation:
                    if doc_line == 'Async function':
                        return True
            
            # Fallback: check signature
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                return 'async' in symbol_info.signature.lower()
        except Exception as e:
            logger.debug(f"Error checking async status for {scip_symbol}: {e}")
        return False
    
    def _extract_class_members(self, class_scip_symbol: str, document) -> tuple[List[str], List[str]]:
        """Use SCIPSymbolManager to parse class members."""
        methods = []
        attributes = []
        
        if not self._symbol_parser:
            return methods, attributes
        
        try:
            # Parse class symbol to get descriptors
            class_info = self._symbol_parser.parse_symbol(class_scip_symbol) 
            if not class_info:
                return methods, attributes
            
            # Extract class name from descriptors: file.py/ClassName -> ClassName
            class_name = self._extract_class_name_from_descriptors(class_info.descriptors)
            if not class_name:
                return methods, attributes
            
            # Find all class members by looking for matching descriptors
            for symbol_info in document.symbols:
                if not self._symbol_parser:
                    continue
                    
                member_info = self._symbol_parser.parse_symbol(symbol_info.symbol)
                if not member_info or member_info.manager != 'local':
                    continue
                
                # Check if this symbol belongs to the class
                if self._is_class_member(member_info.descriptors, class_name):
                    member_name = self._extract_member_name(member_info.descriptors, class_name)
                    if member_name:
                        # Classify based on SCIP kind
                        if self._is_method_kind(symbol_info.kind):
                            methods.append(member_name)
                        else:
                            attributes.append(member_name)
                        
        except Exception as e:
            logger.debug(f"Error extracting class members for {class_scip_symbol}: {e}")
        
        return methods, attributes
    
    def _extract_inheritance(self, class_scip_symbol: str, symbol_info) -> List[str]:
        """Extract class inheritance information from SCIP data."""
        # This would require more sophisticated SCIP relationship analysis
        # For now, return empty list
        return []
    
    def _extract_variable_type(self, scip_symbol: str, symbol_info) -> Optional[str]:
        """Extract variable type from SCIP data."""
        try:
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                # Try to extract type annotation
                signature = symbol_info.signature
                if ':' in signature:
                    type_part = signature.split(':')[1].strip()
                    return type_part if type_part else None
        except Exception as e:
            logger.debug(f"Error extracting variable type for {scip_symbol}: {e}")
        return None
    
    def _is_global_variable(self, scip_symbol: str, document) -> Optional[bool]:
        """Check if variable is global based on SCIP symbol structure."""
        try:
            # Global variables typically don't have class context
            if '#' not in scip_symbol:
                return True
            return False
        except Exception as e:
            logger.debug(f"Error checking global status for {scip_symbol}: {e}")
        return None
    
    def _extract_constant_value(self, scip_symbol: str, symbol_info) -> Optional[str]:
        """Extract constant value from SCIP data."""
        try:
            if hasattr(symbol_info, 'signature') and symbol_info.signature:
                signature = symbol_info.signature
                if '=' in signature:
                    value_part = signature.split('=')[1].strip()
                    return value_part if value_part else None
        except Exception as e:
            logger.debug(f"Error extracting constant value for {scip_symbol}: {e}")
        return None
    
    def extract_scip_relationships(self, file_path: str, scip_index) -> Dict[str, List[tuple]]:
        """
        Extract SCIP relationships from a file using the enhanced analysis pipeline.
        
        This method provides integration between the symbol analyzer and the new
        SCIP relationship management system introduced in the implementation plan.
        
        Args:
            file_path: Relative path to the file to analyze
            scip_index: SCIP index containing all project data
            
        Returns:
            Dictionary mapping source_symbol_id -> [(target_symbol_id, relationship_type), ...]
            Compatible with SCIPRelationshipManager input format
            
        Raises:
            ValueError: If file analysis fails or file not found
        """
        try:
            # Perform complete file analysis
            file_analysis = self.analyze_file(file_path, scip_index)
            
            # Extract all SCIP relationships using the enhanced data structures
            relationships = file_analysis.to_scip_relationships(self._symbol_parser)
            
            logger.debug(f"Extracted SCIP relationships for {file_path}: "
                        f"{len(relationships)} symbols with relationships, "
                        f"{sum(len(rels) for rels in relationships.values())} total relationships")
            
            return relationships
            
        except Exception as e:
            logger.error(f"Failed to extract SCIP relationships from {file_path}: {e}")
            raise ValueError(f"SCIP relationship extraction failed: {e}")
    
    def batch_extract_relationships(self, file_paths: List[str], scip_index) -> Dict[str, Dict[str, List[tuple]]]:
        """
        Extract SCIP relationships from multiple files efficiently.
        
        This method provides batch processing capabilities for the relationship
        management system, optimizing performance for large codebases.
        
        Args:
            file_paths: List of relative file paths to analyze
            scip_index: SCIP index containing all project data
            
        Returns:
            Dictionary mapping file_path -> {source_symbol_id -> [(target_symbol_id, relationship_type), ...]}
        """
        results = {}
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                relationships = self.extract_scip_relationships(file_path, scip_index)
                results[file_path] = relationships
                
                if i % 10 == 0 or i == len(file_paths):
                    logger.debug(f"Batch relationship extraction progress: {i}/{len(file_paths)} files")
                    
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
                results[file_path] = {}  # Empty result for failed files
                continue
        
        total_files = len(results)
        total_relationships = sum(
            sum(len(rels) for rels in file_rels.values())
            for file_rels in results.values()
        )
        
        logger.info(f"Batch relationship extraction completed: {total_files} files, {total_relationships} total relationships")
        
        return results