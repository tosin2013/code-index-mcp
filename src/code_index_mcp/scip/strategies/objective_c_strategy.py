"""
Objective-C Strategy for SCIP indexing using libclang.

This strategy uses libclang to parse Objective-C source files (.m, .mm, .h)
and extract symbol information following SCIP standards.
"""

import logging
import os
from typing import List, Set, Optional, Tuple, Dict, Any
from pathlib import Path

try:
    import clang.cindex as clang
    from clang.cindex import CursorKind, TypeKind
    LIBCLANG_AVAILABLE = True
except ImportError:
    LIBCLANG_AVAILABLE = False
    clang = None
    CursorKind = None
    TypeKind = None

from .base_strategy import SCIPIndexerStrategy, StrategyError
from ..proto import scip_pb2
from ..core.position_calculator import PositionCalculator
from ..core.relationship_types import InternalRelationshipType

logger = logging.getLogger(__name__)


class ObjectiveCStrategy(SCIPIndexerStrategy):
    """SCIP indexing strategy for Objective-C using libclang."""
    
    SUPPORTED_EXTENSIONS = {'.m', '.mm', '.h'}
    
    def __init__(self, priority: int = 95):
        """Initialize the Objective-C strategy."""
        super().__init__(priority)
        self._processed_symbols: Set[str] = set()
        self._symbol_counter = 0
        self.project_path: Optional[str] = None
        
    def can_handle(self, extension: str, file_path: str) -> bool:
        """Check if this strategy can handle the file type."""
        if not LIBCLANG_AVAILABLE:
            logger.warning("libclang not available for Objective-C processing")
            return False
        return extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def get_language_name(self) -> str:
        """Get the language name for SCIP symbol generation."""
        return "objc"
    
    def is_available(self) -> bool:
        """Check if this strategy is available."""
        return LIBCLANG_AVAILABLE
    
    def _collect_symbol_definitions(self, files: List[str], project_path: str) -> None:
        """Phase 1: Collect all symbol definitions from Objective-C files."""
        logger.debug(f"ObjectiveCStrategy Phase 1: Processing {len(files)} files for symbol collection")
        
        # Store project path for use in import classification
        self.project_path = project_path
        
        processed_count = 0
        error_count = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                self._collect_symbols_from_file(file_path, project_path)
                processed_count += 1
                
                if i % 10 == 0 or i == len(files):
                    logger.debug(f"Phase 1 progress: {i}/{len(files)} files, last file: {relative_path}")
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"Phase 1 failed for {relative_path}: {e}")
                continue
        
        logger.info(f"Phase 1 summary: {processed_count} files processed, {error_count} errors")

    def _generate_documents_with_references(self, files: List[str], project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> List[scip_pb2.Document]:
        """Phase 3: Generate complete SCIP documents with resolved references."""
        documents = []
        logger.debug(f"ObjectiveCStrategy Phase 3: Generating documents for {len(files)} files")
        processed_count = 0
        error_count = 0
        total_occurrences = 0
        total_symbols = 0
        
        for i, file_path in enumerate(files, 1):
            relative_path = os.path.relpath(file_path, project_path)
            
            try:
                document = self._analyze_objc_file(file_path, project_path, relationships)
                if document:
                    documents.append(document)
                    total_occurrences += len(document.occurrences)
                    total_symbols += len(document.symbols)
                    processed_count += 1
                    
                if i % 10 == 0 or i == len(files):
                    logger.debug(f"Phase 3 progress: {i}/{len(files)} files, "
                               f"last file: {relative_path}, "
                               f"{len(document.occurrences) if document else 0} occurrences")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Phase 3 failed for {relative_path}: {e}")
                continue
        
        logger.info(f"Phase 3 summary: {processed_count} documents generated, {error_count} errors, "
                   f"{total_occurrences} total occurrences, {total_symbols} total symbols")
        
        return documents

    def _build_symbol_relationships(self, files: List[str], project_path: str) -> Dict[str, List[tuple]]:
        """Phase 2: Build relationships between Objective-C symbols."""
        logger.debug(f"ObjectiveCStrategy: Building symbol relationships for {len(files)} files")
        all_relationships = {}
        
        for file_path in files:
            try:
                file_relationships = self._extract_relationships_from_file(file_path, project_path)
                all_relationships.update(file_relationships)
            except Exception as e:
                logger.warning(f"Failed to extract relationships from {file_path}: {e}")
        
        total_symbols_with_relationships = len(all_relationships)
        total_relationships = sum(len(rels) for rels in all_relationships.values())
        
        logger.debug(f"ObjectiveCStrategy: Built {total_relationships} relationships for {total_symbols_with_relationships} symbols")
        return all_relationships
    
    def _collect_symbols_from_file(self, file_path: str, project_path: str) -> None:
        """Collect symbol definitions from a single Objective-C file using libclang."""
        content = self._read_file_content(file_path)
        if not content:
            logger.debug(f"Empty file skipped: {os.path.relpath(file_path, project_path)}")
            return

        try:
            # Parse with libclang
            index = clang.Index.create()
            translation_unit = index.parse(
                file_path,
                args=['-ObjC', '-x', 'objective-c'],
                options=clang.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
            )
            
            if not translation_unit:
                logger.debug(f"Parse failed: {os.path.relpath(file_path, project_path)}")
                return
            
            # Reset processed symbols for each file
            self._processed_symbols.clear()
            self._symbol_counter = 0
            
            # Traverse AST to collect symbols
            relative_path = self._get_relative_path(file_path, project_path)
            self._traverse_clang_ast_for_symbols(translation_unit.cursor, relative_path, content, file_path)
            
            # Extract imports/dependencies and register with symbol manager
            self._extract_and_register_imports(translation_unit.cursor, file_path, project_path)
            
            logger.debug(f"Symbol collection completed - {relative_path}")
            
        except Exception as e:
            logger.error(f"Error processing {file_path} with libclang: {e}")

    def _extract_and_register_imports(self, cursor: 'clang.Cursor', file_path: str, project_path: str) -> None:
        """Extract imports from AST and register them with the symbol manager."""
        try:
            # Traverse AST to find all import statements
            self._traverse_ast_for_import_registration(cursor, file_path, project_path)
            
        except Exception as e:
            logger.error(f"Error extracting imports from {file_path}: {e}")

    def _traverse_ast_for_import_registration(self, cursor: 'clang.Cursor', file_path: str, project_path: str) -> None:
        """Traverse AST specifically to register imports with the symbol manager."""
        try:
            # Process current cursor for import registration
            if cursor.kind == CursorKind.INCLUSION_DIRECTIVE:
                self._register_import_with_symbol_manager(cursor, file_path, project_path)
            
            # Recursively process children
            for child in cursor.get_children():
                self._traverse_ast_for_import_registration(child, file_path, project_path)
                
        except Exception as e:
            logger.error(f"Error traversing AST for import registration: {e}")

    def _register_import_with_symbol_manager(self, cursor: 'clang.Cursor', file_path: str, project_path: str) -> None:
        """Register a single import with the symbol manager."""
        try:
            # Try to get the included file path
            include_path = None
            framework_name = None
            
            # Method 1: Try to get the included file (may fail for system headers)
            try:
                included_file = cursor.get_included_file()
                if included_file:
                    include_path = str(included_file)
                    logger.debug(f"Got include path from file: {include_path}")
            except Exception as e:
                logger.debug(f"Failed to get included file: {e}")
            
            # Method 2: Try to get from cursor spelling (the actual #import statement)
            spelling = cursor.spelling
            if spelling:
                logger.debug(f"Got cursor spelling: {spelling}")
                # Extract framework name from spelling like "Foundation/Foundation.h" or "Person.h"
                framework_name = self._extract_framework_name_from_spelling(spelling)
                if framework_name:
                    logger.debug(f"Extracted framework name from spelling: {framework_name}")
                    
                    # Classify based on spelling pattern
                    import_type = self._classify_import_from_spelling(spelling)
                    logger.debug(f"Classified import as: {import_type}")
                    
                    # Only register external dependencies (not local files)
                    if import_type in ['standard_library', 'third_party']:
                        if not self.symbol_manager:
                            logger.error("Symbol manager is None!")
                            return
                            
                        # Determine version if possible (for now, leave empty)
                        version = ""
                        
                        logger.debug(f"Registering external symbol: {framework_name}")
                        
                        # Register the import with the moniker manager
                        symbol_id = self.symbol_manager.create_external_symbol(
                            language="objc",
                            package_name=framework_name,
                            module_path=framework_name,
                            symbol_name="*",  # Framework-level import
                            version=version,
                            alias=None
                        )
                        
                        logger.debug(f"Registered external dependency: {framework_name} ({import_type}) -> {symbol_id}")
                        return
                    else:
                        logger.debug(f"Skipping local import: {framework_name} ({import_type})")
                        return
            
            # Method 3: Fallback to include_path if we have it
            if include_path:
                logger.debug(f"Processing include path: {include_path}")
                
                # Extract framework/module name
                framework_name = self._extract_framework_name(include_path, cursor)
                if not framework_name:
                    logger.debug(f"No framework name extracted from {include_path}")
                    return
                    
                logger.debug(f"Extracted framework name: {framework_name}")
                
                # Classify the import type
                import_type = self._classify_objc_import(include_path)
                logger.debug(f"Classified import as: {import_type}")
                
                # Only register external dependencies (not local files)
                if import_type in ['standard_library', 'third_party']:
                    if not self.symbol_manager:
                        logger.error("Symbol manager is None!")
                        return
                        
                    # Determine version if possible (for now, leave empty)
                    version = self._extract_framework_version(include_path)
                    
                    logger.debug(f"Registering external symbol: {framework_name}")
                    
                    # Register the import with the moniker manager
                    symbol_id = self.symbol_manager.create_external_symbol(
                        language="objc",
                        package_name=framework_name,
                        module_path=framework_name,
                        symbol_name="*",  # Framework-level import
                        version=version,
                        alias=None
                    )
                    
                    logger.debug(f"Registered external dependency: {framework_name} ({import_type}) -> {symbol_id}")
                else:
                    logger.debug(f"Skipping local import: {framework_name} ({import_type})")
            else:
                logger.debug("No include path or spelling found for cursor")
            
        except Exception as e:
            logger.error(f"Error registering import with symbol manager: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _extract_framework_name_from_spelling(self, spelling: str) -> Optional[str]:
        """Extract framework name from cursor spelling."""
        try:
            # Remove quotes and angle brackets
            clean_spelling = spelling.strip('"<>')
            
            # For framework imports like "Foundation/Foundation.h"
            if '/' in clean_spelling:
                parts = clean_spelling.split('/')
                if len(parts) >= 2:
                    framework_name = parts[0]
                    return framework_name
                    
            # For simple includes like "MyHeader.h"
            header_name = clean_spelling.replace('.h', '').replace('.m', '').replace('.mm', '')
            return header_name
            
        except Exception as e:
            logger.debug(f"Error extracting framework name from spelling {spelling}: {e}")
            return None

    def _classify_import_from_spelling(self, spelling: str) -> str:
        """Classify import based on spelling pattern."""
        try:
            # Remove quotes and angle brackets
            clean_spelling = spelling.strip('"<>')
            
            # Check if it's a known system framework by name (since cursor.spelling doesn't include brackets)
            if '/' in clean_spelling:
                framework_name = clean_spelling.split('/')[0]
                system_frameworks = {
                    'Foundation', 'UIKit', 'CoreData', 'CoreGraphics', 'QuartzCore',
                    'AVFoundation', 'CoreLocation', 'MapKit', 'CoreAnimation',
                    'Security', 'SystemConfiguration', 'CFNetwork', 'CoreFoundation',
                    'AppKit', 'Cocoa', 'WebKit', 'JavaScriptCore', 'Metal', 'MetalKit',
                    'GameplayKit', 'SpriteKit', 'SceneKit', 'ARKit', 'Vision', 'CoreML'
                }
                if framework_name in system_frameworks:
                    return 'standard_library'
            
            # Check for single framework names (like just "Foundation.h")
            framework_name_only = clean_spelling.replace('.h', '').replace('.framework', '')
            system_frameworks = {
                'Foundation', 'UIKit', 'CoreData', 'CoreGraphics', 'QuartzCore',
                'AVFoundation', 'CoreLocation', 'MapKit', 'CoreAnimation',
                'Security', 'SystemConfiguration', 'CFNetwork', 'CoreFoundation',
                'AppKit', 'Cocoa', 'WebKit', 'JavaScriptCore', 'Metal', 'MetalKit',
                'GameplayKit', 'SpriteKit', 'SceneKit', 'ARKit', 'Vision', 'CoreML'
            }
            if framework_name_only in system_frameworks:
                return 'standard_library'
            
            # Angle brackets indicate system headers (if we had them)
            if spelling.startswith('<') and spelling.endswith('>'):
                return 'standard_library'
            
            # Quotes indicate local or third-party headers
            elif spelling.startswith('"') and spelling.endswith('"'):
                # Check for common third-party patterns
                if any(pattern in clean_spelling.lower() for pattern in ['pods/', 'carthage/', 'node_modules/']):
                    return 'third_party'
                
                # Default for quoted imports
                return 'local'
            
            # Check for common third-party patterns in the path
            if any(pattern in clean_spelling.lower() for pattern in ['pods/', 'carthage/', 'node_modules/']):
                return 'third_party'
            
            # Check if it looks like a local header (simple filename)
            if '/' not in clean_spelling and clean_spelling.endswith('.h'):
                return 'local'
            
            # Fallback: if it contains system-like paths, classify as standard_library
            if any(pattern in clean_spelling.lower() for pattern in ['/system/', '/usr/', '/applications/xcode']):
                return 'standard_library'
            
            # Default fallback
            return 'local'
            
        except Exception as e:
            logger.debug(f"Error classifying import from spelling {spelling}: {e}")
            return 'local'

    def _extract_framework_version(self, include_path: str) -> str:
        """Extract framework version from include path if available."""
        # For now, return empty string. Could be enhanced to detect versions
        # from CocoaPods Podfile.lock, Carthage, or other dependency managers
        return ""

    def _analyze_objc_file(self, file_path: str, project_path: str, relationships: Optional[Dict[str, List[tuple]]] = None) -> Optional[scip_pb2.Document]:
        """Analyze a single Objective-C file and generate complete SCIP document."""
        content = self._read_file_content(file_path)
        if not content:
            return None

        try:
            # Parse with libclang
            index = clang.Index.create()
            translation_unit = index.parse(
                file_path,
                args=['-ObjC', '-x', 'objective-c'],
                options=clang.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
            )
            
            if not translation_unit:
                return None

            # Create SCIP document
            document = scip_pb2.Document()
            document.relative_path = self._get_relative_path(file_path, project_path)
            document.language = self._get_document_language(file_path)

            # Initialize position calculator
            self.position_calculator = PositionCalculator(content)
            
            # Reset processed symbols for each file
            self._processed_symbols.clear()
            self._symbol_counter = 0
            
            # Generate occurrences and symbols
            occurrences = []
            symbols = []
            
            # Traverse AST for document generation
            self._traverse_clang_ast_for_document(translation_unit.cursor, content, occurrences, symbols, relationships)

            # Add results to document
            document.occurrences.extend(occurrences)
            document.symbols.extend(symbols)

            logger.debug(f"Analyzed Objective-C file {document.relative_path}: "
                        f"{len(document.occurrences)} occurrences, {len(document.symbols)} symbols")

            return document
            
        except Exception as e:
            logger.error(f"Error analyzing {file_path} with libclang: {e}")
            return None

    def _traverse_clang_ast_for_symbols(self, cursor: 'clang.Cursor', file_path: str, content: str, full_file_path: str) -> None:
        """Traverse libclang AST for symbol definitions (Phase 1)."""
        try:
            # Process current cursor
            self._process_cursor_for_symbols(cursor, file_path, content, full_file_path)
            
            # Recursively process children
            for child in cursor.get_children():
                self._traverse_clang_ast_for_symbols(child, file_path, content, full_file_path)
                
        except Exception as e:
            logger.error(f"Error traversing AST for symbols: {e}")

    def _traverse_clang_ast_for_imports(self, cursor: 'clang.Cursor', file_path: str, imports: 'ImportGroup') -> None:
        """Traverse libclang AST specifically for import/include statements."""
        try:
            # Process current cursor for imports
            self._process_cursor_for_imports(cursor, file_path, imports)
            
            # Recursively process children
            for child in cursor.get_children():
                self._traverse_clang_ast_for_imports(child, file_path, imports)
                
        except Exception as e:
            logger.error(f"Error traversing AST for imports: {e}")

    def _traverse_clang_ast_for_document(self, cursor: 'clang.Cursor', content: str, occurrences: List, symbols: List, relationships: Optional[Dict[str, List[tuple]]] = None) -> None:
        """Traverse libclang AST for document generation (Phase 3)."""
        try:
            # Process current cursor
            self._process_cursor_for_document(cursor, content, occurrences, symbols, relationships)
            
            # Recursively process children
            for child in cursor.get_children():
                self._traverse_clang_ast_for_document(child, content, occurrences, symbols, relationships)
                
        except Exception as e:
            logger.error(f"Error traversing AST for document: {e}")

    def _process_cursor_for_symbols(self, cursor: 'clang.Cursor', file_path: str, content: str, full_file_path: str) -> None:
        """Process a cursor for symbol registration (Phase 1)."""
        try:
            # Skip invalid cursors or those outside our file
            if not cursor.location.file or cursor.spelling == "":
                return

            # Check if cursor is in the file we're processing
            cursor_file = str(cursor.location.file)
            if not cursor_file.endswith(os.path.basename(full_file_path)):
                return
                
            cursor_kind = cursor.kind
            symbol_name = cursor.spelling
            
            # Map libclang cursor kinds to SCIP symbols
            symbol_info = self._map_cursor_to_symbol(cursor, symbol_name)
            if not symbol_info:
                return
            
            symbol_id, symbol_kind, symbol_roles = symbol_info
            
            # Avoid duplicates
            duplicate_key = f"{symbol_id}:{cursor.location.line}:{cursor.location.column}"
            if duplicate_key in self._processed_symbols:
                return
            self._processed_symbols.add(duplicate_key)
            
            # Calculate position
            location = cursor.location
            if location.line is not None and location.column is not None:
                # libclang uses 1-based indexing, convert to 0-based
                line = location.line - 1
                column = location.column - 1
                
                # Calculate end position (approximate)
                end_line = line
                end_column = column + len(symbol_name)
                
                # Register symbol with reference resolver
                if self.position_calculator:
                    range_obj = self.position_calculator.line_col_to_range(line, column, end_line, end_column)
                else:
                    # Create a simple range object if position_calculator is not available
                    from ..proto.scip_pb2 import Range
                    range_obj = Range()
                    range_obj.start.extend([line, column])
                    range_obj.end.extend([end_line, end_column])
                self.reference_resolver.register_symbol_definition(
                    symbol_id=symbol_id,
                    file_path=file_path,
                    definition_range=range_obj,
                    symbol_kind=symbol_kind,
                    display_name=symbol_name,
                    documentation=[f"Objective-C {cursor_kind.name}"]
                )
                
                logger.debug(f"Registered Objective-C symbol: {symbol_name} ({cursor_kind.name}) at {line}:{column}")
            
        except Exception as e:
            logger.error(f"Error processing cursor for symbols {cursor.spelling}: {e}")

    def _process_cursor_for_document(self, cursor: 'clang.Cursor', content: str, occurrences: List, symbols: List, relationships: Optional[Dict[str, List[tuple]]] = None) -> None:
        """Process a cursor for document generation (Phase 3)."""
        try:
            # Skip invalid cursors or those outside our file
            if not cursor.location.file or cursor.spelling == "":
                return
                
            cursor_kind = cursor.kind
            symbol_name = cursor.spelling
            
            # Map libclang cursor kinds to SCIP symbols
            symbol_info = self._map_cursor_to_symbol(cursor, symbol_name)
            if not symbol_info:
                return
            
            symbol_id, symbol_kind, symbol_roles = symbol_info
            
            # Avoid duplicates
            duplicate_key = f"{symbol_id}:{cursor.location.line}:{cursor.location.column}"
            if duplicate_key in self._processed_symbols:
                return
            self._processed_symbols.add(duplicate_key)
            
            # Calculate position
            location = cursor.location
            if location.line is not None and location.column is not None:
                # libclang uses 1-based indexing, convert to 0-based
                line = location.line - 1
                column = location.column - 1
                
                # Calculate end position (approximate)
                end_line = line
                end_column = column + len(symbol_name)
                
                # Create SCIP occurrence
                occurrence = self._create_occurrence(symbol_id, line, column, end_line, end_column, symbol_roles)
                if occurrence:
                    occurrences.append(occurrence)
                
                # Get relationships for this symbol
                symbol_relationships = relationships.get(symbol_id, []) if relationships else []
                scip_relationships = self._create_scip_relationships(symbol_relationships) if symbol_relationships else []
                
                # Create SCIP symbol information with relationships
                symbol_info_obj = self._create_symbol_information_with_relationships(symbol_id, symbol_name, symbol_kind, scip_relationships)
                if symbol_info_obj:
                    symbols.append(symbol_info_obj)
                
                logger.debug(f"Added Objective-C symbol: {symbol_name} ({cursor_kind.name}) at {line}:{column} with {len(scip_relationships)} relationships")
            
        except Exception as e:
            logger.error(f"Error processing cursor for document {cursor.spelling}: {e}")

    def _process_cursor_for_imports(self, cursor: 'clang.Cursor', file_path: str, imports: 'ImportGroup') -> None:
        """Process a cursor for import/include statements."""
        try:
            # Skip invalid cursors or those outside our file
            if not cursor.location.file:
                return

            cursor_kind = cursor.kind
            
            # Process inclusion directives (#import, #include, @import)
            if cursor_kind == CursorKind.INCLUSION_DIRECTIVE:
                self._process_inclusion_directive(cursor, file_path, imports)
                
        except Exception as e:
            logger.error(f"Error processing cursor for imports: {e}")

    def _process_inclusion_directive(self, cursor: 'clang.Cursor', file_path: str, imports: 'ImportGroup') -> None:
        """Process a single #import/#include/@import directive."""
        try:
            # Get the included file
            included_file = cursor.get_included_file()
            if not included_file:
                return
                
            include_path = str(included_file)
            
            # Extract framework/module name
            framework_name = self._extract_framework_name(include_path, cursor)
            if not framework_name:
                return
                
            # Classify the import type
            import_type = self._classify_objc_import(include_path)
            
            # Add to imports
            imports.add_import(framework_name, import_type)
            
            # Register with moniker manager for external dependencies
            if import_type in ['standard_library', 'third_party'] and self.symbol_manager:
                self._register_framework_dependency(framework_name, import_type, include_path)
                
            logger.debug(f"Processed import: {framework_name} ({import_type}) from {include_path}")
            
        except Exception as e:
            logger.error(f"Error processing inclusion directive: {e}")

    def _extract_framework_name(self, include_path: str, cursor: 'clang.Cursor') -> Optional[str]:
        """Extract framework/module name from include path."""
        try:
            # Get the original spelling from the cursor (what was actually written)
            spelling = cursor.spelling
            if spelling:
                # Remove quotes and angle brackets
                clean_spelling = spelling.strip('"<>')
                
                # For framework imports like <Foundation/Foundation.h>
                if '/' in clean_spelling:
                    parts = clean_spelling.split('/')
                    if len(parts) >= 2:
                        framework_name = parts[0]
                        # Common iOS/macOS frameworks
                        if framework_name in ['Foundation', 'UIKit', 'CoreData', 'CoreGraphics', 
                                            'QuartzCore', 'AVFoundation', 'CoreLocation', 'MapKit']:
                            return framework_name
                        # For other frameworks, use the framework name
                        return framework_name
                    
                # For simple includes like "MyHeader.h"
                header_name = clean_spelling.replace('.h', '').replace('.m', '').replace('.mm', '')
                return header_name
            
            # Fallback: extract from full path
            if '/' in include_path:
                path_parts = include_path.split('/')
                
                # Look for .framework in path
                for i, part in enumerate(path_parts):
                    if part.endswith('.framework') and i + 1 < len(path_parts):
                        return part.replace('.framework', '')
                
                # Look for Headers directory (common in frameworks)
                if 'Headers' in path_parts:
                    headers_idx = path_parts.index('Headers')
                    if headers_idx > 0:
                        framework_part = path_parts[headers_idx - 1]
                        if framework_part.endswith('.framework'):
                            return framework_part.replace('.framework', '')
                
                # Use the filename without extension
                filename = path_parts[-1]
                return filename.replace('.h', '').replace('.m', '').replace('.mm', '')
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting framework name from {include_path}: {e}")
            return None

    def _classify_objc_import(self, include_path: str) -> str:
        """Classify Objective-C import as system, third-party, or local."""
        try:
            # System frameworks (typical macOS/iOS system paths)
            system_indicators = [
                '/Applications/Xcode.app/',
                '/System/Library/',
                '/usr/include/',
                'Platforms/iPhoneOS.platform/',
                'Platforms/iPhoneSimulator.platform/',
                'Platforms/MacOSX.platform/'
            ]
            
            for indicator in system_indicators:
                if indicator in include_path:
                    return 'standard_library'
            
            # Common system frameworks by name
            system_frameworks = {
                'Foundation', 'UIKit', 'CoreData', 'CoreGraphics', 'QuartzCore',
                'AVFoundation', 'CoreLocation', 'MapKit', 'CoreAnimation',
                'Security', 'SystemConfiguration', 'CFNetwork', 'CoreFoundation',
                'AppKit', 'Cocoa', 'WebKit', 'JavaScriptCore'
            }
            
            for framework in system_frameworks:
                if f'/{framework}.framework/' in include_path or f'{framework}/' in include_path:
                    return 'standard_library'
            
            # Third-party dependency managers
            third_party_indicators = [
                '/Pods/',           # CocoaPods
                '/Carthage/',       # Carthage
                '/node_modules/',   # React Native
                '/DerivedData/',    # Sometimes used for third-party
            ]
            
            for indicator in third_party_indicators:
                if indicator in include_path:
                    return 'third_party'
            
            # Check if it's within the project directory
            if hasattr(self, 'project_path') and self.project_path:
                if include_path.startswith(str(self.project_path)):
                    return 'local'
            
            # Check for relative paths (usually local)
            if include_path.startswith('./') or include_path.startswith('../'):
                return 'local'
            
            # If path contains common local indicators
            if any(indicator in include_path.lower() for indicator in ['src/', 'source/', 'include/', 'headers/']):
                return 'local'
            
            # Default to third-party for unknown external dependencies
            return 'third_party'
            
        except Exception as e:
            logger.debug(f"Error classifying import {include_path}: {e}")
            return 'third_party'

    def _register_framework_dependency(self, framework_name: str, import_type: str, include_path: str) -> None:
        """Register framework dependency with moniker manager."""
        try:
            if not self.symbol_manager:
                return
                
            # Determine package manager based on import type and path
            if import_type == 'standard_library':
                manager = 'system'
            elif '/Pods/' in include_path:
                manager = 'cocoapods'
            elif '/Carthage/' in include_path:
                manager = 'carthage'
            else:
                manager = 'unknown'
            
            # Register the external symbol for the framework
            self.symbol_manager.create_external_symbol(
                language="objc",
                package_name=framework_name,
                module_path=framework_name,
                symbol_name="*",  # Framework-level import
                version="",  # Version detection could be added later
                alias=None
            )
            
            logger.debug(f"Registered framework dependency: {framework_name} via {manager}")
            
        except Exception as e:
            logger.error(f"Error registering framework dependency {framework_name}: {e}")
    
    def _map_cursor_to_symbol(self, cursor: 'clang.Cursor', symbol_name: str) -> Optional[Tuple[str, int, int]]:
        """Map libclang cursor to SCIP symbol information."""
        try:
            cursor_kind = cursor.kind
            
            # Map Objective-C specific cursors
            if cursor_kind == CursorKind.OBJC_INTERFACE_DECL:
                # @interface ClassName
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Class, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.OBJC_PROTOCOL_DECL:
                # @protocol ProtocolName
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Interface, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.OBJC_CATEGORY_DECL:
                # @interface ClassName (CategoryName)
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Class, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.OBJC_INSTANCE_METHOD_DECL:
                # Instance method: - (void)methodName
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Method, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.OBJC_CLASS_METHOD_DECL:
                # Class method: + (void)methodName
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Method, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.OBJC_PROPERTY_DECL:
                # @property declaration
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Property, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.OBJC_IVAR_DECL:
                # Instance variable
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Field, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.OBJC_IMPLEMENTATION_DECL:
                # @implementation ClassName
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Class, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.OBJC_CATEGORY_IMPL_DECL:
                # @implementation ClassName (CategoryName)
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Class, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.FUNCTION_DECL:
                # Regular C function
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Function, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.VAR_DECL:
                # Variable declaration
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.Variable, scip_pb2.SymbolRole.Definition)
                
            elif cursor_kind == CursorKind.TYPEDEF_DECL:
                # Type definition
                symbol_id = f"local {self._get_local_id_for_cursor(cursor)}"
                return (symbol_id, scip_pb2.SymbolKind.TypeParameter, scip_pb2.SymbolRole.Definition)
            
            # Add more cursor mappings as needed
            return None
            
        except Exception as e:
            logger.error(f"Error mapping cursor {symbol_name}: {e}")
            return None
    
    def _get_local_id(self) -> str:
        """Generate unique local symbol ID."""
        self._symbol_counter += 1
        return f"objc_{self._symbol_counter}"
    
    def _get_local_id_for_cursor(self, cursor: 'clang.Cursor') -> str:
        """Generate consistent local symbol ID based on cursor properties."""
        # Create deterministic ID based on cursor type, name, and location
        cursor_type = cursor.kind.name.lower()
        symbol_name = cursor.spelling or "unnamed"
        line = cursor.location.line
        
        return f"{cursor_type}_{symbol_name}_{line}"
    
    def _create_occurrence(self, symbol_id: str, start_line: int, start_col: int, 
                          end_line: int, end_col: int, symbol_roles: int) -> Optional[scip_pb2.Occurrence]:
        """Create SCIP occurrence."""
        try:
            occurrence = scip_pb2.Occurrence()
            occurrence.symbol = symbol_id
            occurrence.symbol_roles = symbol_roles
            occurrence.range.start.extend([start_line, start_col])
            occurrence.range.end.extend([end_line, end_col])
            
            return occurrence
            
        except Exception as e:
            logger.error(f"Error creating occurrence: {e}")
            return None
    
    def _create_symbol_information(self, symbol_id: str, display_name: str, symbol_kind: int) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information."""
        try:
            symbol_info = scip_pb2.SymbolInformation()
            symbol_info.symbol = symbol_id
            symbol_info.kind = symbol_kind
            symbol_info.display_name = display_name
            
            return symbol_info
            
        except Exception as e:
            logger.error(f"Error creating symbol information: {e}")
            return None
    
    def _create_symbol_information_with_relationships(self, symbol_id: str, display_name: str, symbol_kind: int, relationships: List['scip_pb2.Relationship']) -> Optional[scip_pb2.SymbolInformation]:
        """Create SCIP symbol information with relationships."""
        try:
            symbol_info = scip_pb2.SymbolInformation()
            symbol_info.symbol = symbol_id
            symbol_info.kind = symbol_kind
            symbol_info.display_name = display_name
            
            # Add relationships if provided
            if relationships:
                symbol_info.relationships.extend(relationships)
            
            return symbol_info
            
        except Exception as e:
            logger.error(f"Error creating symbol information with relationships: {e}")
            return None

    def _extract_relationships_from_file(self, file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships from a single Objective-C file using libclang."""
        content = self._read_file_content(file_path)
        if not content:
            return {}
        
        try:
            # Parse with libclang
            index = clang.Index.create()
            translation_unit = index.parse(
                file_path,
                args=['-ObjC', '-x', 'objective-c'],
                options=clang.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
            )
            
            if not translation_unit:
                return {}
            
            return self._extract_relationships_from_ast(translation_unit.cursor, file_path, project_path)
            
        except Exception as e:
            logger.error(f"Error extracting relationships from {file_path}: {e}")
            return {}
    
    def _extract_relationships_from_ast(self, cursor: 'clang.Cursor', file_path: str, project_path: str) -> Dict[str, List[tuple]]:
        """Extract relationships from libclang AST."""
        relationships = {}
        relative_path = self._get_relative_path(file_path, project_path)
        
        # Track current method context for method calls
        current_method_symbol = None
        
        def traverse_for_relationships(cursor_node, parent_method=None):
            """Recursively traverse AST to find relationships."""
            nonlocal current_method_symbol
            
            try:
                # Skip if cursor is not in our file
                if not cursor_node.location.file or cursor_node.spelling == "":
                    pass
                else:
                    cursor_file = str(cursor_node.location.file)
                    if cursor_file.endswith(os.path.basename(file_path)):
                        cursor_kind = cursor_node.kind
                        
                        # Track method context
                        if cursor_kind in (CursorKind.OBJC_INSTANCE_METHOD_DECL, CursorKind.OBJC_CLASS_METHOD_DECL):
                            method_symbol_id = f"local {self._get_local_id_for_cursor(cursor_node)}"
                            current_method_symbol = method_symbol_id
                            parent_method = method_symbol_id
                        
                        # Detect Objective-C method calls
                        elif cursor_kind == CursorKind.OBJC_MESSAGE_EXPR:
                            if parent_method:
                                # Get the method being called
                                called_method = self._extract_method_from_message_expr(cursor_node)
                                if called_method:
                                    target_symbol_id = f"local objc_call_{called_method}_{cursor_node.location.line}"
                                    
                                    if parent_method not in relationships:
                                        relationships[parent_method] = []
                                    relationships[parent_method].append((target_symbol_id, InternalRelationshipType.CALLS))
                                    
                                    logger.debug(f"Found method call: {parent_method} -> {target_symbol_id}")
                        
                        # Detect C function calls
                        elif cursor_kind == CursorKind.CALL_EXPR:
                            if parent_method:
                                function_name = cursor_node.spelling
                                if function_name:
                                    target_symbol_id = f"local c_func_{function_name}_{cursor_node.location.line}"
                                    
                                    if parent_method not in relationships:
                                        relationships[parent_method] = []
                                    relationships[parent_method].append((target_symbol_id, InternalRelationshipType.CALLS))
                                    
                                    logger.debug(f"Found function call: {parent_method} -> {target_symbol_id}")
                
                # Recursively process children
                for child in cursor_node.get_children():
                    traverse_for_relationships(child, parent_method)
                    
            except Exception as e:
                logger.error(f"Error processing cursor for relationships: {e}")
        
        # Start traversal
        traverse_for_relationships(cursor)
        
        return relationships
    
    def _extract_method_from_message_expr(self, cursor: 'clang.Cursor') -> Optional[str]:
        """Extract method name from Objective-C message expression."""
        try:
            # Get the selector/method name from the message expression
            # This is a simplified extraction - could be enhanced
            for child in cursor.get_children():
                if child.kind == CursorKind.OBJC_MESSAGE_EXPR:
                    return child.spelling
                elif child.spelling and len(child.spelling) > 0:
                    # Try to get method name from any meaningful child
                    return child.spelling
            
            # Fallback: use the cursor's own spelling if available
            return cursor.spelling if cursor.spelling else None
            
        except Exception as e:
            logger.error(f"Error extracting method from message expression: {e}")
            return None
    
    def _create_scip_relationships(self, relationships: List[tuple]) -> List['scip_pb2.Relationship']:
        """Convert internal relationships to SCIP relationships."""
        scip_relationships = []
        
        for target_symbol, relationship_type in relationships:
            try:
                relationship = scip_pb2.Relationship()
                relationship.symbol = target_symbol
                
                # Map relationship type to SCIP flags
                if relationship_type == InternalRelationshipType.CALLS:
                    relationship.is_reference = True
                elif relationship_type == InternalRelationshipType.INHERITS:
                    relationship.is_reference = True
                elif relationship_type == InternalRelationshipType.IMPLEMENTS:
                    relationship.is_implementation = True
                else:
                    relationship.is_reference = True  # Default fallback
                
                scip_relationships.append(relationship)
                
            except Exception as e:
                logger.error(f"Error creating SCIP relationship: {e}")
                continue
        
        return scip_relationships

    def _get_document_language(self, file_path: str) -> str:
        """Get the document language identifier."""
        if file_path.endswith('.mm'):
            return 'objcpp'
        return 'objc'

    # Utility methods from base strategy
    def _read_file_content(self, file_path: str) -> Optional[str]:
        """Read file content safely."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return None

    def _get_relative_path(self, file_path: str, project_path: str) -> str:
        """Get relative path from project root."""
        return os.path.relpath(file_path, project_path).replace(os.sep, '/')

    def get_supported_languages(self) -> List[str]:
        """Return list of supported language identifiers."""
        return ["objective-c", "objc", "objective-c-header"]


class StrategyError(Exception):
    """Exception raised when a strategy cannot process files."""
    pass