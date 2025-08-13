"""
Code Intelligence Service - Business logic for code analysis and understanding.

This service handles the business logic for analyzing code files, extracting
intelligence, and providing comprehensive code insights. It composes technical
tools to achieve business goals.
"""

import os
from typing import Dict, Any

from .base_service import BaseService
from ..tools.filesystem import FileSystemTool


class CodeIntelligenceService(BaseService):
    """
    Business service for code analysis and intelligence.

    This service orchestrates code analysis workflows by composing
    technical tools to achieve business goals like understanding code
    structure, extracting insights, and providing comprehensive analysis.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self._filesystem_tool = FileSystemTool()
        # Use new enhanced symbol analyzer instead of legacy SCIPQueryTool
        from ..tools.scip.scip_symbol_analyzer import SCIPSymbolAnalyzer
        self._symbol_analyzer = SCIPSymbolAnalyzer()

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a file and return comprehensive intelligence.

        This is the main business method that orchestrates the file analysis
        workflow, choosing the best analysis strategy and providing rich
        insights about the code.

        Args:
            file_path: Path to the file to analyze (relative to project root)

        Returns:
            Dictionary with comprehensive file analysis

        Raises:
            ValueError: If file path is invalid or analysis fails
        """
        # Business validation
        self._validate_analysis_request(file_path)

        # Use enhanced SCIP analysis
        analysis = self._perform_enhanced_scip_analysis(file_path)

        # Direct conversion to output format (no intermediate transformations)
        return analysis.to_dict()

    def _validate_analysis_request(self, file_path: str) -> None:
        """
        Validate the file analysis request according to business rules.

        Args:
            file_path: File path to validate

        Raises:
            ValueError: If validation fails
        """
        # Business rule: Project must be set up
        self._require_project_setup()

        # Business rule: File path must be valid
        self._require_valid_file_path(file_path)

        # Business rule: File must exist
        full_path = os.path.join(self.base_path, file_path)
        if not os.path.exists(full_path):
            raise ValueError(f"File does not exist: {file_path}")




    def _get_scip_tool(self):
        """Get SCIP tool instance from the index manager."""
        if self.index_manager:
            # Access the SCIP tool from unified index manager
            return self.index_manager._get_scip_tool()
        return None

    def _perform_enhanced_scip_analysis(self, file_path: str):
        """
        Enhanced SCIP analysis using the new symbol analyzer.
        
        Args:
            file_path: File path to analyze
        
        Returns:
            FileAnalysis object with accurate symbol information
        """
        # Get SCIP tool for index access
        scip_tool = self._get_scip_tool()
        if not scip_tool:
            raise RuntimeError("SCIP tool is not available for file analysis")
        
        # Get raw SCIP index
        scip_index = scip_tool.get_raw_index()
        if not scip_index:
            raise RuntimeError("SCIP index is not available for file analysis")
        
        # Use enhanced analyzer for accurate symbol analysis
        return self._symbol_analyzer.analyze_file(file_path, scip_index)

