"""SCIP Index Builder - main orchestrator for SCIP-based indexing."""

import os
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from ..scip.factory import SCIPIndexerFactory, SCIPIndexingError
from ..scip.proto import scip_pb2



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
        start_time = datetime.now()
        self.project_path = project_path
        

        try:
            scan_result = self._scan_project_files(project_path)

            file_paths = [str(f['path']) for f in scan_result.file_list]
            strategy_files = self.scip_factory.group_files_by_strategy(file_paths)

            all_documents = self._process_files(strategy_files, project_path)

            scip_index = self._assemble_scip_index(all_documents, scan_result, start_time)
            duration = (datetime.now() - start_time).total_seconds()

            validation_result = self._validate_scip_index(scip_index)
            if not validation_result.is_valid:
                if validation_result.errors:
                    pass

            return scip_index
        except Exception as e:
            return self._create_fallback_scip_index(project_path, str(e))

    def _scan_project_files(self, project_path: str) -> ScanResult:
        """Scan project directory to get a list of files and metadata."""
        files = []
        # Use project settings for exclude patterns
        ignored_dirs = self._get_exclude_patterns()
        # Load gitignore patterns
        gitignore_patterns = self._load_gitignore_patterns(project_path)
        
        for root, dirs, filenames in os.walk(project_path):
            # Check if current root path contains any ignored directories
            root_parts = Path(root).parts
            project_parts = Path(project_path).parts
            relative_parts = root_parts[len(project_parts):]
            
            # Skip if any part of the path is in ignored_dirs
            if any(part in ignored_dirs for part in relative_parts):
                dirs[:] = []  # Don't descend further
                continue
                
            # Modify dirs in-place to prune the search
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            # Apply gitignore filtering to directories
            dirs[:] = [d for d in dirs if not self._is_gitignored(os.path.join(root, d), project_path, gitignore_patterns)]
            
            for filename in filenames:
                # Ignore hidden files (but allow .gitignore itself)
                if filename.startswith('.') and filename != '.gitignore':
                    continue
                    
                full_path = os.path.join(root, filename)
                
                # Apply gitignore filtering to files
                if self._is_gitignored(full_path, project_path, gitignore_patterns):
                    continue
                    
                files.append(full_path)

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

    def _load_gitignore_patterns(self, project_path: str) -> List[str]:
        """Load patterns from .gitignore file."""
        gitignore_path = os.path.join(project_path, '.gitignore')
        patterns = []
        
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith('#'):
                            patterns.append(line)
            except Exception:
                pass  # Ignore errors reading .gitignore
        
        return patterns

    def _is_gitignored(self, file_path: str, project_path: str, gitignore_patterns: List[str]) -> bool:
        """Check if a file or directory is ignored by .gitignore patterns."""
        if not gitignore_patterns:
            return False
            
        # Get relative path from project root
        try:
            rel_path = os.path.relpath(file_path, project_path)
            # Normalize path separators for cross-platform compatibility
            rel_path = rel_path.replace('\\', '/')
            
            # Check each gitignore pattern
            for pattern in gitignore_patterns:
                # Handle negation patterns (starting with !)
                if pattern.startswith('!'):
                    continue  # Skip negation for now (simplified implementation)
                    
                # Add trailing slash for directory patterns
                if pattern.endswith('/'):
                    pattern = pattern.rstrip('/')
                    # Check if it's a directory and matches pattern
                    if os.path.isdir(file_path) and fnmatch.fnmatch(rel_path, pattern):
                        return True
                    # Also check if any parent directory matches
                    path_parts = rel_path.split('/')
                    for i in range(len(path_parts)):
                        if fnmatch.fnmatch('/'.join(path_parts[:i+1]), pattern):
                            return True
                else:
                    # Check file or directory name
                    if fnmatch.fnmatch(rel_path, pattern):
                        return True
                    # Check if any parent directory or file in path matches
                    path_parts = rel_path.split('/')
                    for part in path_parts:
                        if fnmatch.fnmatch(part, pattern):
                            return True
                        
        except Exception:
            pass
            
        return False

    def _process_files(self, strategy_files: Dict, project_path: str) -> List[scip_pb2.Document]:
        """Process files using appropriate strategies, either sequentially or in parallel."""
        if self.max_workers and self.max_workers > 1:
            return self._process_files_parallel(strategy_files, project_path)
        return self._process_files_sequential(strategy_files, project_path)

    def _process_files_sequential(self, strategy_files: Dict, project_path: str) -> List[scip_pb2.Document]:
        """Process files sequentially."""
        all_documents = []
        for strategy, files in strategy_files.items():
            
            try:
                documents = strategy.generate_scip_documents(files, project_path)
                all_documents.extend(documents)
            except Exception as e:
                all_documents.extend(self._try_fallback_strategies(files, strategy, project_path))
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

    def _extract_external_symbols(self, documents: List[scip_pb2.Document]) -> List:
        """Extract and deduplicate external symbols."""
        return []

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
