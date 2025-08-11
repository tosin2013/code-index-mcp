"""
Code Intelligence Service - Business logic for code analysis and understanding.

This service handles the business logic for analyzing code files, extracting
intelligence, and providing comprehensive code insights. It composes technical
tools to achieve business goals.
"""

import os
from typing import Dict, Any
from dataclasses import dataclass

from .base_service import BaseService
from ..tools.scip import SCIPIndexTool, SCIPQueryTool
from ..tools.filesystem import FileSystemTool


@dataclass
class CodeAnalysisResult:
    """Business result for code analysis operations."""
    file_path: str
    language: str
    analysis_type: str  # 'scip_intelligence' or 'basic_analysis'
    structure: Dict[str, Any]
    metadata: Dict[str, Any]
    insights: list[str]


class CodeIntelligenceService(BaseService):
    """
    Business service for code analysis and intelligence.

    This service orchestrates code analysis workflows by composing
    technical tools to achieve business goals like understanding code
    structure, extracting insights, and providing comprehensive analysis.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self._scip_index_tool = SCIPIndexTool()
        self._scip_query_tool = SCIPQueryTool(self._scip_index_tool)
        self._filesystem_tool = FileSystemTool()

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

        # Business workflow: Execute analysis
        result = self._execute_analysis_workflow(file_path)

        # Business result formatting
        return self._format_analysis_result(result)

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

    def _execute_analysis_workflow(self, file_path: str) -> CodeAnalysisResult:
        """
        Execute the core file analysis business workflow.

        Args:
            file_path: File path to analyze

        Returns:
            CodeAnalysisResult with analysis data
        """
        # Business decision: Choose analysis strategy
        analysis_strategy = self._choose_analysis_strategy(file_path)

        if analysis_strategy == 'scip_intelligence':
            return self._perform_scip_analysis(file_path)
        else:
            return self._perform_basic_analysis(file_path)

    def _choose_analysis_strategy(self, file_path: str) -> str:
        """
        Business logic to choose the best analysis strategy.

        Args:
            file_path: File path to analyze

        Returns:
            Analysis strategy: 'scip_intelligence' or 'basic_analysis'
        """
        # Business rule: Try SCIP analysis first if index is available
        if self._scip_index_tool.is_index_available():
            # Check if file is in SCIP index
            file_intelligence = self._scip_query_tool.get_file_intelligence(file_path)
            if file_intelligence:
                return 'scip_intelligence'

        # Business rule: Fall back to basic analysis
        return 'basic_analysis'

    def _perform_scip_analysis(self, file_path: str) -> CodeAnalysisResult:
        """
        Business logic for SCIP-based intelligent analysis.
        
        Args:
            file_path: File path to analyze
        
        Returns:
            CodeAnalysisResult with SCIP intelligence
        """

        # Get SCIP intelligence
        file_intelligence = self._scip_query_tool.get_file_intelligence(file_path)
        if not file_intelligence:
            # Fallback to basic analysis if SCIP data not available
            return self._perform_basic_analysis(file_path)

        # Get additional file system data
        full_path = os.path.join(self.base_path, file_path)
        file_stats = self._filesystem_tool.get_file_stats(full_path)

        # Business logic: Build comprehensive structure analysis
        structure = {
            'symbols': {
                'classes': [s for s in file_intelligence.symbols if s.kind == 'class'],
                'functions': [s for s in file_intelligence.symbols if s.kind in ['function', 'method']],
                'variables': [s for s in file_intelligence.symbols if s.kind == 'variable'],
                'constants': [s for s in file_intelligence.symbols if s.kind == 'constant'],
                'total_symbols': len(file_intelligence.symbols)
            },
            'dependencies': {
                'imports': file_intelligence.imports,
                'exports': file_intelligence.exports,
                'import_count': len(file_intelligence.imports)
            },
            'complexity': file_intelligence.complexity_metrics,
            'code_metrics': {
                'line_count': file_intelligence.line_count,
                'estimated_complexity': file_intelligence.complexity_metrics.get('estimated_complexity', 0)
            }
        }

        # Business logic: Generate metadata
        metadata = {
            'file_size_bytes': file_stats['size_bytes'],
            'file_size_category': self._filesystem_tool.get_file_size_category(full_path),
            'last_modified': file_stats['modified_time'],
            'analysis_source': 'scip_index',
            'scip_language': file_intelligence.language,
            'detected_language': self._filesystem_tool.detect_language_from_extension(file_path)
        }

        # Business logic: Generate insights
        insights = self._generate_scip_insights(file_intelligence, structure)

        return CodeAnalysisResult(
            file_path=file_path,
            language=file_intelligence.language,
            analysis_type='scip_intelligence',
            structure=structure,
            metadata=metadata,
            insights=insights
        )

    def _perform_basic_analysis(self, file_path: str) -> CodeAnalysisResult:
        """
        Business logic for basic file analysis when SCIP is not available.
        
        Args:
            file_path: File path to analyze
        
        Returns:
            CodeAnalysisResult with basic analysis
        """

        # Get file system data
        full_path = os.path.join(self.base_path, file_path)
        file_stats = self._filesystem_tool.get_file_stats(full_path)
        line_count = self._filesystem_tool.count_lines(full_path)
        language = self._filesystem_tool.detect_language_from_extension(file_path)

        # Business logic: Build basic structure
        structure = {
            'basic_info': {
                'line_count': line_count,
                'language': language,
                'file_type': 'code' if language != 'unknown' else 'text'
            },
            'file_characteristics': {
                'size_category': self._filesystem_tool.get_file_size_category(full_path),
                'is_text_file': self._filesystem_tool.is_text_file(full_path)
            }
        }

        # Business logic: Generate metadata
        metadata = {
            'file_size_bytes': file_stats['size_bytes'],
            'file_size_category': self._filesystem_tool.get_file_size_category(full_path),
            'last_modified': file_stats['modified_time'],
            'analysis_source': 'basic_filesystem',
            'detected_language': language,
            'extension': file_stats['extension']
        }

        # Business logic: Generate basic insights
        insights = self._generate_basic_insights(structure, metadata)

        return CodeAnalysisResult(
            file_path=file_path,
            language=language,
            analysis_type='basic_analysis',
            structure=structure,
            metadata=metadata,
            insights=insights
        )

    def _generate_scip_insights(self, file_intelligence, structure: Dict[str, Any]) -> list[str]:
        """
        Business logic to generate insights from SCIP analysis.

        Args:
            file_intelligence: SCIP file intelligence data
            structure: Analyzed structure data

        Returns:
            List of business insights
        """
        insights = []

        # Complexity insights
        complexity = structure['complexity'].get('estimated_complexity', 0)
        if complexity > 20:
            insights.append("High complexity detected - consider refactoring for better maintainability")
        elif complexity < 5:
            insights.append("Low complexity - well-structured and maintainable code")

        # Symbol insights
        symbol_count = structure['symbols']['total_symbols']
        if symbol_count > 50:
            insights.append("Large number of symbols - consider splitting into smaller modules")
        elif symbol_count == 0:
            insights.append("No symbols detected - may be a configuration or data file")

        # Dependency insights
        import_count = structure['dependencies']['import_count']
        if import_count > 20:
            insights.append("High number of imports - check for unnecessary dependencies")
        elif import_count == 0:
            insights.append("No imports detected - self-contained module")

        # Language-specific insights
        if file_intelligence.language == 'python':
            class_count = len(structure['symbols']['classes'])
            function_count = len(structure['symbols']['functions'])
            if class_count > function_count:
                insights.append("Object-oriented design - class-heavy implementation")
            elif function_count > class_count * 3:
                insights.append("Functional design - function-heavy implementation")

        return insights

    def _generate_basic_insights(self, structure: Dict[str, Any], metadata: Dict[str, Any]) -> list[str]:
        """
        Business logic to generate insights from basic analysis.

        Args:
            structure: Basic structure data
            metadata: File metadata

        Returns:
            List of basic insights
        """
        insights = []

        # Size insights
        size_category = metadata['file_size_category']
        if size_category == 'very_large':
            insights.append("Very large file - consider splitting for better maintainability")
        elif size_category == 'tiny':
            insights.append("Small file - likely a configuration or utility module")

        # Line count insights
        line_count = structure['basic_info']['line_count']
        if line_count > 1000:
            insights.append("High line count - consider refactoring into smaller modules")
        elif line_count < 50:
            insights.append("Concise implementation - well-focused module")

        # Language insights
        language = structure['basic_info']['language']
        if language == 'unknown':
            insights.append("Unknown file type - may need specialized analysis")
        else:
            insights.append(f"Detected as {language} code - basic analysis available")

        return insights

    def _format_analysis_result(self, result: CodeAnalysisResult) -> Dict[str, Any]:
        """
        Format the analysis result according to business requirements.

        Args:
            result: Analysis result data

        Returns:
            Formatted result dictionary for MCP response
        """
        return {
            'file_info': {
                'path': result.file_path,
                'language': result.language,
                'analysis_type': result.analysis_type
            },
            'structure': result.structure,
            'metadata': result.metadata,
            'insights': result.insights,
            'status': 'success'
        }
