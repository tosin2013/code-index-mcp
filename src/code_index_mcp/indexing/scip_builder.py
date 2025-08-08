"""SCIP Index Builder - main orchestrator for SCIP-based indexing."""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..scip.factory import SCIPIndexerFactory, SCIPIndexingError, IndexingFailedError
from ..scip.proto.scip_pb2 import (
    Index, Document, Metadata, ToolInfo,
    UnspecifiedProtocolVersion, UTF8
)
from .scanner import ProjectScanner
from .models import ValidationResult


logger = logging.getLogger(__name__)


class SCIPIndexBuilder:
    """Main builder class that orchestrates SCIP-based indexing."""

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the SCIP index builder.

        Args:
            max_workers: Maximum number of worker threads for parallel processing
        """
        self.max_workers = max_workers
        self.scip_factory = SCIPIndexerFactory()
        self.project_path = ""

    def build_scip_index(self, project_path: str) -> Index:
        """
        Build complete SCIP index for a project.

        Args:
            project_path: Path to the project root directory

        Returns:
            Complete SCIP Index structure

        Raises:
            SCIPIndexingError: If indexing fails
        """
        start_time = datetime.now()
        self.project_path = project_path

        logger.info(f"Starting SCIP indexing for project: {project_path}")

        try:
            # Step 1: Scan project directory
            scanner = ProjectScanner(project_path)
            scan_result = scanner.scan_project()

            logger.info(f"Found {len(scan_result.file_list)} files to index")

            # Step 2: Group files by the strategy that will handle them
            file_paths = [f.path for f in scan_result.file_list]
            strategy_files = self.scip_factory.group_files_by_strategy(file_paths)

            logger.info(f"Files grouped into {len(strategy_files)} strategies")

            # Step 3: Generate SCIP documents using appropriate strategies
            all_documents = []

            if self.max_workers and self.max_workers > 1:
                # Parallel processing
                all_documents = self._process_files_parallel(strategy_files, project_path)
            else:
                # Sequential processing
                all_documents = self._process_files_sequential(strategy_files, project_path)

            # Step 4: Assemble final SCIP index
            scip_index = self._assemble_scip_index(all_documents, scan_result, start_time)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info(f"SCIP indexing completed in {duration:.2f}s: {len(all_documents)} documents")

            # Step 5: Validate the index
            validation_result = self._validate_scip_index(scip_index)
            if not validation_result.is_valid:
                logger.warning(f"SCIP index validation warnings: {validation_result.warnings}")
                if validation_result.errors:
                    logger.error(f"SCIP index validation errors: {validation_result.errors}")

            return scip_index

        except Exception as e:
            logger.error(f"SCIP indexing failed: {str(e)}")
            return self._create_fallback_scip_index(project_path, str(e))

    def _process_files_sequential(self, strategy_files: Dict, project_path: str) -> List[Document]:
        """Process files sequentially using their assigned strategies."""
        all_documents = []

        for strategy, files in strategy_files.items():
            logger.info(f"Processing {len(files)} files with {strategy.get_strategy_name()}")

            try:
                documents = strategy.generate_scip_documents(files, project_path)
                all_documents.extend(documents)
                logger.info(f"SUCCESS {strategy.get_strategy_name()}: {len(documents)} documents")

            except Exception as e:
                logger.error(f"FAILED {strategy.get_strategy_name()} failed: {str(e)}")
                # Try fallback strategies for these files
                fallback_documents = self._try_fallback_strategies(files, strategy, project_path)
                all_documents.extend(fallback_documents)

        return all_documents

    def _process_files_parallel(self, strategy_files: Dict, project_path: str) -> List[Document]:
        """Process files in parallel using their assigned strategies."""
        all_documents = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit strategy tasks
            future_to_strategy = {}

            for strategy, files in strategy_files.items():
                logger.info(f"Submitting {len(files)} files to {strategy.get_strategy_name()}")
                future = executor.submit(strategy.generate_scip_documents, files, project_path)
                future_to_strategy[future] = (strategy, files)

            # Collect results as they complete
            for future in as_completed(future_to_strategy):
                strategy, files = future_to_strategy[future]

                try:
                    documents = future.result()
                    all_documents.extend(documents)
                    logger.info(f"SUCCESS {strategy.get_strategy_name()}: {len(documents)} documents")

                except Exception as e:
                    logger.error(f"FAILED {strategy.get_strategy_name()} failed: {str(e)}")
                    # Try fallback strategies for these files
                    fallback_documents = self._try_fallback_strategies(files, strategy, project_path)
                    all_documents.extend(fallback_documents)

        return all_documents

    def _try_fallback_strategies(self, failed_files: List[str], failed_strategy, project_path: str) -> List[Document]:
        """Try fallback strategies for files that failed with their primary strategy."""
        fallback_documents = []

        logger.info(f"Attempting fallback strategies for {len(failed_files)} failed files")

        for file_path in failed_files:
            extension = self._get_file_extension(file_path)

            # Get all strategies for this extension (excluding the failed one)
            strategies = self.scip_factory.get_strategies_for_extension(extension)
            fallback_strategies = [s for s in strategies if s != failed_strategy]

            success = False
            for fallback_strategy in fallback_strategies:
                try:
                    documents = fallback_strategy.generate_scip_documents([file_path], project_path)
                    fallback_documents.extend(documents)
                    logger.debug(f"SUCCESS Fallback {fallback_strategy.get_strategy_name()}: {file_path}")
                    success = True
                    break

                except Exception as e:
                    logger.debug(f"FAILED Fallback {fallback_strategy.get_strategy_name()} failed: {file_path}")
                    continue

            if not success:
                logger.warning(f"All strategies failed for: {file_path}")

        return fallback_documents

    def _assemble_scip_index(self, documents: List[Document], scan_result, start_time: datetime) -> Index:
        """Assemble the final SCIP index structure."""
        scip_index = Index()

        # Set metadata
        scip_index.metadata.CopyFrom(self._create_metadata(scan_result.project_metadata, start_time))

        # Add all documents
        scip_index.documents.extend(documents)

        # Extract and deduplicate external symbols
        external_symbols = self._extract_external_symbols(documents)
        scip_index.external_symbols.extend(external_symbols)

        logger.info(f"Assembled SCIP index: {len(documents)} documents, {len(external_symbols)} symbols")

        return scip_index

    def _create_metadata(self, project_metadata: Dict[str, Any], start_time: datetime) -> Metadata:
        """Create SCIP metadata."""
        metadata = Metadata()

        # Protocol version
        metadata.version = UnspecifiedProtocolVersion

        # Tool information
        metadata.tool_info.name = "code-index-mcp"
        metadata.tool_info.version = project_metadata.get("version", "1.2.1")  # Use project version if available
        # Add timestamp as argument
        metadata.tool_info.arguments.extend(["scip-indexing", f"started-{start_time.isoformat()}"])

        # Project root - prefer from metadata if available
        metadata.project_root = project_metadata.get("project_root", self.project_path)

        # Text encoding
        metadata.text_document_encoding = UTF8

        return metadata

    def _extract_external_symbols(self, documents: List[Document]) -> List:
        """Extract and deduplicate external symbols from documents."""
        # For now, return empty list - external symbols are an optimization
        # that we can implement later if needed
        # We collect external symbols referenced in the documents for future implementation
        external_refs = set()
        for document in documents:
            for occurrence in document.occurrences:
                if occurrence.symbol.startswith('external '):
                    external_refs.add(occurrence.symbol)

        # Return empty list for now, but log the count of external references found
        if external_refs:
            logger.debug(f"Found {len(external_refs)} external symbol references")

        return []

    def _validate_scip_index(self, scip_index: Index) -> ValidationResult:
        """Validate the completed SCIP index."""
        errors = []
        warnings = []

        # Check required fields
        if not scip_index.metadata.project_root:
            errors.append("Missing project_root in metadata")

        if not scip_index.documents:
            warnings.append("No documents in SCIP index")

        # Check document validity
        for i, document in enumerate(scip_index.documents):
            if not document.relative_path:
                errors.append(f"Document {i} missing relative_path")

            if not document.language:
                warnings.append(f"Document {i} ({document.relative_path}) missing language")

        # Check tool info
        if not scip_index.metadata.tool_info.name:
            warnings.append("Missing tool name in metadata")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _create_fallback_scip_index(self, project_path: str, error_message: str) -> Index:
        """Create a minimal fallback SCIP index when building fails."""
        scip_index = Index()

        # Create minimal metadata
        metadata = Metadata()
        metadata.tool_info.name = "code-index-mcp"
        metadata.tool_info.version = "1.2.1"
        metadata.project_root = project_path
        metadata.text_document_encoding = UTF8
        scip_index.metadata.CopyFrom(metadata)

        # Create a single document with error information
        error_doc = Document()
        error_doc.relative_path = "BUILD_ERROR.md"
        error_doc.language = "markdown"
        error_doc.text = f"# Build Error\n\nSCIP indexing failed: {error_message}\n"
        scip_index.documents.append(error_doc)

        logger.error(f"Created fallback SCIP index due to error: {error_message}")
        return scip_index

    def _get_file_extension(self, file_path: str) -> str:
        """Extract file extension from path."""
        if '.' not in file_path:
            return ''
        return '.' + file_path.split('.')[-1].lower()

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get a summary of available strategies."""
        return {
            'total_strategies': len(self.scip_factory.strategies),
            'registered_strategies': [s.get_strategy_name() for s in self.scip_factory.strategies]
        }