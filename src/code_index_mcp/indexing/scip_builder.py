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

from ..scip.language_manager import SCIPLanguageManager, LanguageNotSupportedException
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
    """Main builder class that orchestrates SCIP-based indexing with new language manager."""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers
        self.language_manager: Optional[SCIPLanguageManager] = None
        self.project_path = ""

    def build_scip_index(self, project_path: str) -> scip_pb2.Index:
        """Build complete SCIP index for a project."""
        start_time = datetime.now()
        self.project_path = project_path
        
        # Initialize language manager for this project
        self.language_manager = SCIPLanguageManager(project_path)
        
        logger.info("🚀 Starting SCIP index build for project: %s", project_path)
        logger.debug("Build configuration: max_workers=%s", self.max_workers)

        try:
            logger.info("📁 Phase 1: Scanning project files...")
            # Phase 1: scan files
            scan_result = self._scan_project_files(project_path)
            total_files_considered = len(scan_result.file_list)
            logger.info("✅ File scan completed, found %d valid files", total_files_considered)

            logger.info("🏷️ Phase 2: Analyzing language distribution...")
            file_paths = [str(f['path']) for f in scan_result.file_list]
            language_stats = self.language_manager.get_language_statistics(file_paths)
            
            for language, count in language_stats.items():
                logger.info("  📋 %s: %d files", language, count)
            logger.debug("Language analysis completed")

            logger.info("⚙️ Phase 3: Processing files with language manager...")
            # Use the new language manager to create the complete index directly
            scip_index = self.language_manager.create_complete_index(file_paths)
            logger.info("✅ File processing completed, generated %d documents", len(scip_index.documents))

            logger.info("🔗 Phase 4: Adding metadata...")
            self._add_build_metadata(scip_index, scan_result, start_time)
            logger.debug("Metadata addition completed")

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

    def _add_build_metadata(self, scip_index: scip_pb2.Index, scan_result: ScanResult, start_time: datetime) -> None:
        """Add build metadata to the SCIP index."""
        build_time = datetime.now() - start_time
        
        # Add tool info to metadata if not already present
        if not scip_index.metadata.tool_info.name:
            scip_index.metadata.tool_info.name = "code-index-mcp"
            scip_index.metadata.tool_info.version = "2.1.0"  # Version with new architecture
        
        # Add project info
        if not scip_index.metadata.project_root:
            scip_index.metadata.project_root = self.project_path
        
        logger.debug(f"Added build metadata: {len(scip_index.documents)} documents, build time: {build_time}")
    
    def _create_fallback_scip_index(self, project_path: str, error_message: str) -> scip_pb2.Index:
        """Create a minimal fallback SCIP index when build fails."""
        logger.warning("Creating fallback SCIP index due to error: %s", error_message)
        
        try:
            # Use fallback language manager
            fallback_manager = SCIPLanguageManager(project_path)
            fallback_factory = fallback_manager.get_factory('fallback')
            
            # Create minimal index with just metadata
            index = scip_pb2.Index()
            index.metadata.CopyFrom(fallback_factory.create_metadata(project_path))
            
            # Add error document
            error_doc = scip_pb2.Document()
            error_doc.relative_path = "BUILD_ERROR.md"
            error_doc.language = "markdown"
            error_doc.text = f"# Build Error\n\nSCIP indexing failed: {error_message}\n"
            index.documents.append(error_doc)
            
            logger.info("Created fallback SCIP index with basic metadata")
            return index
            
        except Exception as e:
            logger.error(f"Failed to create fallback index: {e}")
            # Return completely empty index as last resort
            return scip_pb2.Index()

    def _scan_project_files(self, project_path: str) -> ScanResult:
        """Scan project directory to get a list of files and metadata."""
        logger.debug("📂 Starting file system scan of: %s", project_path)
        files = []
        
        # Use project settings for exclude patterns
        logger.debug("🚫 Loading exclude patterns...")
        default_exclude = self._get_default_exclude_patterns()
        gitignore_spec = self._load_gitignore_patterns(project_path)
        
        total_scanned = 0
        excluded_count = 0
        included_count = 0
        
        try:
            for root, dirs, filenames in os.walk(project_path):
                total_scanned += len(filenames)
                
                # Filter directories to skip excluded ones
                dirs[:] = [d for d in dirs if not any(pattern in d for pattern in default_exclude)]
                
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    
                    # Check default exclude patterns
                    if any(pattern in file_path for pattern in default_exclude):
                        excluded_count += 1
                        continue
                    
                    # Check gitignore patterns
                    if self._is_gitignored(file_path, project_path, gitignore_spec):
                        excluded_count += 1
                        continue
                    
                    # Include file
                    file_info = {
                        'path': Path(file_path),
                        'relative_path': os.path.relpath(file_path, project_path),
                        'size': os.path.getsize(file_path),
                        'extension': os.path.splitext(filename)[1].lower()
                    }
                    files.append(file_info)
                    included_count += 1
        
        except Exception as e:
            logger.error("❌ File scan failed: %s", e)
            raise
        
        logger.debug("📊 File scan results: %d total, %d included, %d excluded", 
                    total_scanned, included_count, excluded_count)
        
        project_metadata = {
            'project_path': project_path,
            'project_name': os.path.basename(project_path),
            'total_files_scanned': total_scanned,
            'files_included': included_count,
            'files_excluded': excluded_count,
            'scan_timestamp': datetime.now().isoformat()
        }
        
        return ScanResult(file_list=files, project_metadata=project_metadata)

    def _get_default_exclude_patterns(self) -> set:
        """Get default patterns to exclude from indexing."""
        return {'.git', '.svn', '.hg', '__pycache__', 'node_modules', '.venv', 'venv', 
               'build', 'dist', 'target', '.idea', '.vscode'}

    def _load_gitignore_patterns(self, project_path: str):
        """Load patterns from .gitignore file using pathspec."""
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

    def get_language_summary(self) -> Dict[str, Any]:
        """Get a summary of available languages."""
        if not self.language_manager:
            return {"error": "Language manager not initialized"}
            
        return {
            'supported_languages': list(self.language_manager.get_supported_languages()),
            'project_path': self.project_path
        }