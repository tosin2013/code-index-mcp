"""SCIP Language Manager - Direct factory management without strategy layer."""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any

from .framework.types import SCIPContext
from .framework.base.index_factory import SCIPIndexFactory
from .proto import scip_pb2

# Import all language factory creators
from .framework.python import create_python_scip_factory
from .framework.javascript import create_javascript_scip_factory
from .framework.java import create_java_scip_factory
from .framework.objective_c import create_objective_c_scip_factory
from .framework.zig import create_zig_scip_factory
from .framework.fallback import create_fallback_scip_factory

logger = logging.getLogger(__name__)


class LanguageNotSupportedException(Exception):
    """Exception raised when a language is not supported."""
    pass


class SCIPLanguageManager:
    """
    Direct language management for SCIP indexing without strategy abstraction layer.
    
    This manager directly handles language detection, factory selection, and file processing
    without the overhead of the strategy pattern. It provides a cleaner, more efficient
    approach to SCIP index generation.
    """
    
    def __init__(self, project_root: str):
        """Initialize the language manager for a specific project."""
        self.project_root = project_root
        
        # Language factory creators mapping
        self._factory_creators: Dict[str, Callable[[str], SCIPIndexFactory]] = {
            'python': create_python_scip_factory,
            'javascript': create_javascript_scip_factory,
            'typescript': create_javascript_scip_factory,  # Same as JavaScript
            'java': create_java_scip_factory,
            'objective_c': create_objective_c_scip_factory,
            'zig': create_zig_scip_factory,
            'fallback': create_fallback_scip_factory
        }
        
        # Language priority for detection conflicts
        self._language_priority = {
            'python': 90,
            'javascript': 85,
            'typescript': 85,
            'java': 80,
            'objective_c': 75,
            'zig': 70,
            'fallback': 10  # Always lowest priority
        }
        
        # Extension to language mapping
        self._extension_mapping = {
            # Python
            '.py': 'python',
            '.pyw': 'python', 
            '.pyx': 'python',
            '.pyi': 'python',
            
            # JavaScript/TypeScript
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.mjs': 'javascript',
            '.cjs': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            
            # Java
            '.java': 'java',
            
            # Objective-C
            '.m': 'objective_c',
            '.mm': 'objective_c',
            '.h': 'objective_c',  # Could be C/C++ too, but we'll handle with priority
            
            # Zig
            '.zig': 'zig',
            '.zon': 'zig',
        }
        
        # Factory cache to avoid recreating
        self._factory_cache: Dict[str, SCIPIndexFactory] = {}
        
        logger.info(f"Initialized SCIP Language Manager for project: {project_root}")
        logger.info(f"Supported languages: {list(self._factory_creators.keys())}")
    
    def detect_language(self, file_path: str) -> str:
        """
        Detect the programming language for a given file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Language identifier string
        """
        extension = Path(file_path).suffix.lower()
        
        # Direct mapping for most cases
        if extension in self._extension_mapping:
            return self._extension_mapping[extension]
        
        # Special handling for ambiguous extensions
        if extension == '.h':
            # Could be C, C++, or Objective-C
            # For now, default to objective_c, but could add content-based detection
            return 'objective_c'
        
        # Default to fallback for unknown extensions
        return 'fallback'
    
    def get_factory(self, language: str) -> SCIPIndexFactory:
        """
        Get or create a factory for the specified language.
        
        Args:
            language: Language identifier
            
        Returns:
            SCIP Index Factory for the language
            
        Raises:
            LanguageNotSupportedException: If language is not supported
        """
        if language not in self._factory_creators:
            raise LanguageNotSupportedException(f"Language '{language}' is not supported")
        
        # Check cache first
        if language not in self._factory_cache:
            factory_creator = self._factory_creators[language]
            self._factory_cache[language] = factory_creator(self.project_root)
            logger.debug(f"Created new {language} factory for project {self.project_root}")
        
        return self._factory_cache[language]
    
    def get_factory_for_file(self, file_path: str) -> SCIPIndexFactory:
        """
        Get the appropriate factory for a specific file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SCIP Index Factory for the file's language
        """
        language = self.detect_language(file_path)
        return self.get_factory(language)
    
    def process_file(self, file_path: str) -> Optional[scip_pb2.Document]:
        """
        Process a single file and generate SCIP document.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            SCIP Document or None if processing failed
        """
        try:
            # Get appropriate factory
            factory = self.get_factory_for_file(file_path)
            
            # Read file content
            content = self._read_file_content(file_path)
            if not content:
                return None
            
            # Create context
            relative_path = os.path.relpath(file_path, self.project_root)
            context = SCIPContext(
                file_path=relative_path,
                content=content,
                scope_stack=[],
                imports={}
            )
            
            # Generate document
            document = factory.create_document(file_path, content)
            
            if document:
                logger.debug(f"Successfully processed {relative_path} with {len(document.symbols)} symbols")
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return None
    
    def process_files(self, file_paths: List[str]) -> List[scip_pb2.Document]:
        """
        Process multiple files and generate SCIP documents.
        
        Args:
            file_paths: List of file paths to process
            
        Returns:
            List of SCIP Documents
        """
        documents = []
        processed_count = 0
        error_count = 0
        
        # Group files by language for efficiency
        files_by_language = self._group_files_by_language(file_paths)
        
        for language, files in files_by_language.items():
            if not files:
                continue
                
            logger.info(f"Processing {len(files)} {language} files")
            
            try:
                factory = self.get_factory(language)
                
                for i, file_path in enumerate(files, 1):
                    document = self.process_file(file_path)
                    if document:
                        documents.append(document)
                        processed_count += 1
                    else:
                        error_count += 1
                    
                    # Progress logging
                    if i % 10 == 0 or i == len(files):
                        relative_path = os.path.relpath(file_path, self.project_root)
                        logger.debug(f"{language} progress: {i}/{len(files)} files, last: {relative_path}")
                        
            except Exception as e:
                logger.error(f"Failed to process {language} files: {e}")
                error_count += len(files)
                continue
        
        logger.info(f"Processing complete: {processed_count} documents generated, {error_count} errors")
        return documents
    
    def create_complete_index(self, file_paths: Optional[List[str]] = None) -> scip_pb2.Index:
        """
        Create a complete SCIP index for the project.
        
        Args:
            file_paths: Optional list of specific files to process. If None, auto-discover.
            
        Returns:
            Complete SCIP Index
        """
        if file_paths is None:
            file_paths = self._discover_project_files()
        
        logger.info(f"Creating complete SCIP index for {len(file_paths)} files")
        
        # Create index with metadata
        index = scip_pb2.Index()
        
        # Use any factory to create metadata (they should be consistent)
        try:
            fallback_factory = self.get_factory('fallback')
            index.metadata.CopyFrom(fallback_factory.create_metadata(self.project_root))
        except Exception as e:
            logger.warning(f"Failed to create metadata: {e}")
        
        # Process all files
        documents = self.process_files(file_paths)
        index.documents.extend(documents)
        
        # Extract external symbols
        all_external_symbols = []
        files_by_language = self._group_files_by_language(file_paths)
        
        for language, files in files_by_language.items():
            if not files:
                continue
                
            try:
                factory = self.get_factory(language)
                language_documents = [doc for doc in documents if self._get_document_language(doc) == language]
                external_symbols = factory.extract_external_symbols(language_documents)
                all_external_symbols.extend(external_symbols)
            except Exception as e:
                logger.warning(f"Failed to extract external symbols for {language}: {e}")
        
        index.external_symbols.extend(all_external_symbols)
        
        # Build cross-document relationships after all documents are processed
        logger.info("Building cross-document relationships...")
        self._build_cross_document_relationships(index)
        
        logger.info(f"Complete index created with {len(documents)} documents and {len(all_external_symbols)} external symbols")
        return index
    
    def _build_cross_document_relationships(self, index: scip_pb2.Index) -> None:
        """
        Build cross-document relationships using language-specific processing.
        
        This method delegates relationship building to individual language factories
        to handle language-specific module systems and import semantics correctly.
        """
        logger.info("Building cross-document relationships using language-specific processing...")
        
        # Group documents by language for language-specific processing
        files_by_language = self._group_documents_by_language(index.documents)
        
        total_relationships_added = 0
        
        for language, documents in files_by_language.items():
            if not documents:
                continue
                
            try:
                logger.info(f"Processing cross-document relationships for {len(documents)} {language} files")
                factory = self.get_factory(language)
                
                # Delegate to language-specific implementation
                relationships_added = factory.build_cross_document_relationships(documents, index)
                total_relationships_added += relationships_added
                
                logger.info(f"Added {relationships_added} relationships for {language} files")
                
            except Exception as e:
                logger.warning(f"Failed to build cross-document relationships for {language}: {e}")
                # Fallback to legacy unified processing for this language
                self._build_cross_document_relationships_legacy(index, documents)
        
        logger.info(f"Total cross-document relationships added: {total_relationships_added}")
    
    def _build_cross_document_relationships_legacy(self, index: scip_pb2.Index, documents_filter: List[scip_pb2.Document] = None) -> None:
        """
        Legacy unified cross-document relationship building as fallback.
        
        This is the original implementation kept for fallback purposes.
        """
        logger.info("Using legacy cross-document relationship building")
        
        # Use provided documents or all documents in index
        documents_to_process = documents_filter if documents_filter else index.documents
        
        # Step 1: Build global symbol registry
        symbol_registry = {}
        for doc in documents_to_process:
            for symbol_info in doc.symbols:
                symbol_id = symbol_info.symbol
                symbol_registry[symbol_id] = (doc, symbol_info)
                
                # Also register without suffix for function symbols
                if symbol_info.kind == 11:  # SymbolKind.Function
                    if symbol_id.endswith('().'):
                        base_id = symbol_id[:-3]  # Remove '().'
                        symbol_registry[base_id] = (doc, symbol_info)
        
        logger.debug(f"Built legacy symbol registry with {len(symbol_registry)} entries")
        
        # Step 2: Analyze occurrences to build relationships
        relationships_added = 0
        for source_doc in documents_to_process:
            for occurrence in source_doc.occurrences:
                # Skip if not a reference (we want ReadAccess = 8)
                if not (occurrence.symbol_roles & 8):
                    continue
                
                # Skip if it's also a definition (Definition = 1)
                if occurrence.symbol_roles & 1:
                    continue
                
                target_symbol_id = occurrence.symbol
                
                # Find the target symbol being referenced
                target_entry = symbol_registry.get(target_symbol_id)
                if not target_entry:
                    continue
                
                target_doc, target_symbol_info = target_entry
                
                # Skip self-references within same symbol
                source_symbol_id = self._find_containing_symbol(occurrence, source_doc)
                if not source_symbol_id or source_symbol_id == target_symbol_id:
                    continue
                
                # Create relationship (target is called by source)
                # Only add if it's a function being called
                if target_symbol_info.kind == 11:  # SymbolKind.Function
                    relationship = scip_pb2.Relationship()
                    relationship.symbol = source_symbol_id
                    relationship.is_reference = True
                    relationship.is_implementation = False
                    relationship.is_type_definition = False
                    relationship.is_definition = False
                    
                    # Check if this relationship already exists to avoid duplicates
                    already_exists = any(
                        rel.symbol == source_symbol_id 
                        for rel in target_symbol_info.relationships
                    )
                    
                    if not already_exists:
                        target_symbol_info.relationships.append(relationship)
                        relationships_added += 1
        
        logger.info(f"Added {relationships_added} legacy cross-document relationships")
    
    def _find_containing_symbol(self, occurrence, document) -> Optional[str]:
        """
        Find which symbol contains this occurrence based on position.
        
        Args:
            occurrence: The occurrence to locate
            document: The document containing the occurrence
            
        Returns:
            Symbol ID of the containing symbol, or None if not found
        """
        if not occurrence.range or not occurrence.range.start:
            return None
        
        occurrence_line = occurrence.range.start[0] if len(occurrence.range.start) > 0 else 0
        
        # Find the symbol that contains this occurrence
        best_symbol = None
        for symbol_info in document.symbols:
            # We need to determine if the occurrence is within this symbol's scope
            # This is a simplified approach - ideally we'd have proper scope ranges
            # For now, we'll use a heuristic based on symbol type
            
            # If it's a module-level symbol (no parent), it could contain the occurrence
            if not best_symbol:
                best_symbol = symbol_info.symbol
        
        # If no containing symbol found, use file-level context
        if not best_symbol and document.relative_path:
            file_name = document.relative_path.replace('\\', '/').split('/')[-1]
            return f"local {file_name}#"
        
        return best_symbol
    
    def get_supported_languages(self) -> Set[str]:
        """Get all supported languages."""
        return set(self._factory_creators.keys())
    
    def get_language_statistics(self, file_paths: List[str]) -> Dict[str, int]:
        """Get statistics about language distribution in file list."""
        stats = {}
        for file_path in file_paths:
            language = self.detect_language(file_path)
            stats[language] = stats.get(language, 0) + 1
        return stats
    
    def _read_file_content(self, file_path: str) -> Optional[str]:
        """Read file content safely."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return None
    
    def _group_files_by_language(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """Group files by their detected language."""
        groups = {}
        for file_path in file_paths:
            language = self.detect_language(file_path)
            if language not in groups:
                groups[language] = []
            groups[language].append(file_path)
        return groups
    
    def _group_documents_by_language(self, documents: List[scip_pb2.Document]) -> Dict[str, List[scip_pb2.Document]]:
        """Group SCIP documents by their language."""
        groups = {}
        for doc in documents:
            language = self._get_document_language(doc)
            if language not in groups:
                groups[language] = []
            groups[language].append(doc)
        return groups
    
    def _discover_project_files(self) -> List[str]:
        """Auto-discover files in the project directory."""
        files = []
        project_path = Path(self.project_root)
        
        # Common exclude patterns
        exclude_patterns = {
            '.git', '__pycache__', 'node_modules', '.vscode', '.idea',
            '.pytest_cache', '.mypy_cache', 'dist', 'build'
        }
        
        for file_path in project_path.rglob('*'):
            if file_path.is_file():
                # Skip excluded directories
                if any(part in exclude_patterns for part in file_path.parts):
                    continue
                
                # Only include files with known extensions or force fallback
                extension = file_path.suffix.lower()
                if extension in self._extension_mapping or extension:
                    files.append(str(file_path))
        
        logger.info(f"Discovered {len(files)} files in project")
        return files
    
    def _get_document_language(self, document: scip_pb2.Document) -> str:
        """Extract language from document."""
        if hasattr(document, 'language') and document.language:
            return document.language
        
        # Fallback: detect from file path
        return self.detect_language(document.relative_path) if document.relative_path else 'fallback'


# Convenience function for quick usage
def create_language_manager(project_root: str) -> SCIPLanguageManager:
    """Create a new SCIP Language Manager for the given project."""
    return SCIPLanguageManager(project_root)