"""SCIP Index Builder - main orchestrator for SCIP-based indexing."""

import os
import fnmatch
import pathspec
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from ..scip.factory import SCIPIndexerFactory, SCIPIndexingError
from ..scip.proto import scip_pb2


logger = logging.getLogger(__name__)



@dataclass
class ValidationResult:
    """Result of SCIP index validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """Result of a project scan."""
    file_list: List[Dict[str, Any]]
    project_metadata: Dict[str, Any]


class SCIPIndexBuilder:
    """Main builder class that orchestrates SCIP-based indexing."""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers
        self.scip_factory = SCIPIndexerFactory()
        self.project_path = ""

    def build_scip_index(self, project_path: str) -> scip_pb2.Index:
        """Build complete SCIP index for a project."""
        # Build index without timing logs
        start_time = datetime.now()
        self.project_path = project_path
        
        logger.info("🚀 Starting SCIP index build for project: %s", project_path)
        logger.debug("Build configuration: max_workers=%s", self.max_workers)

        try:
            logger.info("📁 Phase 1: Scanning project files...")
            # Phase 1: scan files
            scan_result = self._scan_project_files(project_path)
            total_files_considered = len(scan_result.file_list)
            logger.info("✅ File scan completed, found %d valid files", total_files_considered)

            logger.info("🏷️ Phase 2: Grouping files by strategy...")
            file_paths = [str(f['path']) for f in scan_result.file_list]
            strategy_files = self.scip_factory.group_files_by_strategy(file_paths)
            
            for strategy, files in strategy_files.items():
                logger.info("  📋 %s: %d files", strategy.__class__.__name__, len(files))
            logger.debug("File grouping completed")

            logger.info("⚙️ Phase 3: Processing files with strategies...")
            all_documents = self._process_files(strategy_files, project_path)
            logger.info("✅ File processing completed, generated %d documents", len(all_documents))

            logger.info("🔗 Phase 4: Assembling SCIP index...")
            scip_index = self._assemble_scip_index(all_documents, scan_result, start_time)
            logger.debug("Index assembly completed")

            logger.info("🎉 SCIP index build completed successfully")

            logger.info("🔍 Phase 5: Validating SCIP index...")
            validation_result = self._validate_scip_index(scip_index)
            if not validation_result.is_valid:
                logger.warning("⚠️ Index validation found issues: %s", validation_result.errors)
            else:
                logger.info("✅ Index validation passed")

            return scip_index
        except Exception as e:
            logger.error("❌ SCIP index build failed: %s", e, exc_info=True)
            return self._create_fallback_scip_index(project_path, str(e))

    def _scan_project_files(self, project_path: str) -> ScanResult:
        """Scan project directory to get a list of files and metadata."""
        logger.debug("📂 Starting file system scan of: %s", project_path)
        files = []
        
        # Use project settings for exclude patterns
        logger.debug("🚫 Loading exclude patterns...")
        ignored_dirs = self._get_exclude_patterns()
        logger.debug("Ignored directories: %s", ignored_dirs)
        
        # Load gitignore patterns
        logger.debug("📋 Loading .gitignore patterns...")
        gitignore_spec = self._load_gitignore_patterns(project_path)
        if hasattr(gitignore_spec, 'patterns'):
            logger.debug("Found %d gitignore patterns", len(gitignore_spec.patterns))
        elif gitignore_spec:
            logger.debug("Loaded gitignore specification")
        else:
            logger.debug("No gitignore patterns found")
        
        scan_count = 0
        gitignore_skipped = 0
        hidden_files_skipped = 0
        ignored_dir_time = 0
        gitignore_check_time = 0
        
        for root, dirs, filenames in os.walk(project_path):
            scan_count += 1
            if scan_count % 100 == 0:
                logger.debug("📊 Scanned %d directories, found %d files so far...", scan_count, len(files))
                
            # Check if current root path contains any ignored directories
            ignored_dir_start = datetime.now()
            root_parts = Path(root).parts
            project_parts = Path(project_path).parts
            relative_parts = root_parts[len(project_parts):]
            
            # Skip if any part of the path is in ignored_dirs
            if any(part in ignored_dirs for part in relative_parts):
                ignored_dir_time += (datetime.now() - ignored_dir_start).total_seconds()
                logger.debug("🚫 Skipping ignored directory: %s", root)
                dirs[:] = []  # Don't descend further
                continue
                
            # Modify dirs in-place to prune the search
            original_dirs = len(dirs)
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            if len(dirs) < original_dirs:
                ignored_dir_time += (datetime.now() - ignored_dir_start).total_seconds()
                logger.debug("🚫 Filtered %d ignored subdirectories in %s", original_dirs - len(dirs), root)
            else:
                ignored_dir_time += (datetime.now() - ignored_dir_start).total_seconds()
            
            # Apply gitignore filtering to directories
            gitignore_dir_start = datetime.now()
            pre_gitignore_dirs = len(dirs)
            dirs[:] = [d for d in dirs if not self._is_gitignored(os.path.join(root, d), project_path, gitignore_spec)]
            gitignore_filtered_dirs = pre_gitignore_dirs - len(dirs)
            gitignore_check_time += (datetime.now() - gitignore_dir_start).total_seconds()
            
            if gitignore_filtered_dirs > 0:
                logger.debug("📋 .gitignore filtered %d directories in %s", gitignore_filtered_dirs, root)
            
            for filename in filenames:
                file_check_start = datetime.now()
                
                # Ignore hidden files (but allow .gitignore itself)
                if filename.startswith('.') and filename != '.gitignore':
                    hidden_files_skipped += 1
                    gitignore_check_time += (datetime.now() - file_check_start).total_seconds()
                    continue
                    
                full_path = os.path.join(root, filename)
                
                # Apply gitignore filtering to files
                if self._is_gitignored(full_path, project_path, gitignore_spec):
                    gitignore_skipped += 1
                    gitignore_check_time += (datetime.now() - file_check_start).total_seconds()
                    continue
                    
                gitignore_check_time += (datetime.now() - file_check_start).total_seconds()
                files.append(full_path)
        
        logger.info("📊 File scan summary: scanned %d directories, found %d valid files", scan_count, len(files))
        logger.info("🚫 Filtered files: %d gitignored, %d hidden files", gitignore_skipped, hidden_files_skipped)

        file_list = [{'path': f, 'is_binary': False} for f in files]
        project_metadata = {"project_name": os.path.basename(project_path)}
        return ScanResult(file_list=file_list, project_metadata=project_metadata)

    def _get_exclude_patterns(self) -> set:
        """Get exclude patterns from project settings."""
        try:
            from ..project_settings import ProjectSettings
            # Try to get patterns from project settings
            settings = ProjectSettings(self.project_path, skip_load=False)
            exclude_patterns = settings.config.get("file_watcher", {}).get("exclude_patterns", [])
            return set(exclude_patterns)
        except Exception:
            # Fallback to basic patterns if settings not available
            return {'.git', '.svn', '.hg', '__pycache__', 'node_modules', '.venv', 'venv', 
                   'build', 'dist', 'target', '.idea', '.vscode'}

    def _load_gitignore_patterns(self, project_path: str):
        """Load patterns from .gitignore file using pathspec (required)."""
        gitignore_path = os.path.join(project_path, '.gitignore')

        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    spec = pathspec.PathSpec.from_lines('gitignorestyle', f)
                return spec
            except Exception:
                logger.debug("Failed to load .gitignore via pathspec")
                return None

        return None
    
    

    def _is_gitignored(self, file_path: str, project_path: str, gitignore_spec) -> bool:
        """Check if a file or directory is ignored by .gitignore patterns using pathspec."""
        if not gitignore_spec:
            return False

        try:
            # Get relative path from project root
            rel_path = os.path.relpath(file_path, project_path)
            # Normalize path separators for cross-platform compatibility
            rel_path = rel_path.replace('\\', '/')

            return gitignore_spec.match_file(rel_path)
        except Exception:
            return False
    
    

    def _process_files(self, strategy_files: Dict, project_path: str) -> List[scip_pb2.Document]:
        """Process files using appropriate strategies, either sequentially or in parallel."""
        if self.max_workers and self.max_workers > 1:
            return self._process_files_parallel(strategy_files, project_path)
        return self._process_files_sequential(strategy_files, project_path)

    def _process_files_sequential(self, strategy_files: Dict, project_path: str) -> List[scip_pb2.Document]:
        """Process files sequentially."""
        logger.debug("🔄 Processing files sequentially (single-threaded)")
        all_documents = []
        
        for strategy, files in strategy_files.items():
            strategy_name = strategy.__class__.__name__
            logger.info("⚙️ Processing %d files with %s...", len(files), strategy_name)
            
            try:
                documents = strategy.generate_scip_documents(files, project_path)
                logger.info("✅ %s completed, generated %d documents", strategy_name, len(documents))
                all_documents.extend(documents)
            except Exception as e:
                logger.error("❌ %s failed: %s", strategy_name, e, exc_info=True)
                logger.info("🔄 Trying fallback strategies for %d files...", len(files))
                fallback_docs = self._try_fallback_strategies(files, strategy, project_path)
                all_documents.extend(fallback_docs)
                logger.info("📄 Fallback generated %d documents", len(fallback_docs))
        
        return all_documents

    def _process_files_parallel(self, strategy_files: Dict, project_path: str) -> List[scip_pb2.Document]:
        """Process files in parallel."""
        all_documents = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_strategy = {
                executor.submit(s.generate_scip_documents, f, project_path): (s, f)
                for s, f in strategy_files.items()
            }
            for future in as_completed(future_to_strategy):
                strategy, files = future_to_strategy[future]
                try:
                    documents = future.result()
                    all_documents.extend(documents)
                    
                except Exception as e:
                    all_documents.extend(self._try_fallback_strategies(files, strategy, project_path))
        return all_documents

    def _try_fallback_strategies(self, failed_files: List[str], failed_strategy, project_path: str) -> List[scip_pb2.Document]:
        """Try fallback strategies for files that failed."""
        fallback_documents = []
        
        for file_path in failed_files:
            extension = self._get_file_extension(file_path)
            strategies = self.scip_factory.get_strategies_for_extension(extension)
            fallback_strategies = [s for s in strategies if s != failed_strategy]

            success = False
            for fallback in fallback_strategies:
                try:
                    docs = fallback.generate_scip_documents([file_path], project_path)
                    fallback_documents.extend(docs)
                    success = True
                    break
                except Exception:
                    pass

            if not success:
                pass
        return fallback_documents

    def _assemble_scip_index(self, documents: List[scip_pb2.Document], scan_result: ScanResult, start_time: datetime) -> scip_pb2.Index:
        """Assemble the final SCIP index."""
        scip_index = scip_pb2.Index()
        scip_index.metadata.CopyFrom(self._create_metadata(scan_result.project_metadata, start_time))
        scip_index.documents.extend(documents)
        external_symbols = self._extract_external_symbols(documents)
        scip_index.external_symbols.extend(external_symbols)
        
        return scip_index

    def _create_metadata(self, project_metadata: Dict[str, Any], start_time: datetime) -> scip_pb2.Metadata:
        """Create SCIP metadata."""
        metadata = scip_pb2.Metadata()
        metadata.version = scip_pb2.ProtocolVersion.UnspecifiedProtocolVersion
        metadata.tool_info.name = "code-index-mcp"
        metadata.tool_info.version = "1.2.1"
        metadata.tool_info.arguments.extend(["scip-indexing"])
        metadata.project_root = self.project_path
        metadata.text_document_encoding = scip_pb2.TextDocumentEncoding.UTF8
        return metadata

    def _extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List[scip_pb2.SymbolInformation]:
        """Extract and deduplicate external symbols from strategies."""
        external_symbols = []
        seen_symbols = set()
        
        # Collect external symbols from all strategies
        for strategy in self.scip_factory.strategies:
            try:
                strategy_external_symbols = strategy.get_external_symbols()
                for symbol_info in strategy_external_symbols:
                    symbol_id = symbol_info.symbol
                    if symbol_id not in seen_symbols:
                        external_symbols.append(symbol_info)
                        seen_symbols.add(symbol_id)
            except Exception as e:
                # Strategy might not support external symbols yet
                continue
        
        return external_symbols

    def _validate_scip_index(self, scip_index: scip_pb2.Index) -> ValidationResult:
        """Validate the completed SCIP index."""
        errors, warnings = [], []
        if not scip_index.metadata.project_root:
            errors.append("Missing project_root in metadata")
        if not scip_index.documents:
            warnings.append("No documents in SCIP index")
        for i, doc in enumerate(scip_index.documents):
            if not doc.relative_path:
                errors.append(f"Document {i} missing relative_path")
            if not doc.language:
                warnings.append(f"Document {i} ({doc.relative_path}) missing language")
        if not scip_index.metadata.tool_info.name:
            warnings.append("Missing tool name in metadata")
        return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)

    def _create_fallback_scip_index(self, project_path: str, error_message: str) -> scip_pb2.Index:
        """Create a minimal fallback SCIP index on failure."""
        scip_index = scip_pb2.Index()
        metadata = scip_pb2.Metadata()
        metadata.tool_info.name = "code-index-mcp"
        metadata.tool_info.version = "1.2.1"
        metadata.project_root = project_path
        metadata.text_document_encoding = scip_pb2.TextDocumentEncoding.UTF8
        scip_index.metadata.CopyFrom(metadata)

        error_doc = scip_pb2.Document()
        error_doc.relative_path = "BUILD_ERROR.md"
        error_doc.language = "markdown"
        error_doc.text = f"# Build Error\n\nSCIP indexing failed: {error_message}\n"
        scip_index.documents.append(error_doc)

        
        return scip_index

    def _get_file_extension(self, file_path: str) -> str:
        """Extract file extension."""
        return os.path.splitext(file_path)[1].lower()

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get a summary of available strategies."""
        return {
            'total_strategies': len(self.scip_factory.strategies),
            'registered_strategies': [s.get_strategy_name() for s in self.scip_factory.strategies]
        }
