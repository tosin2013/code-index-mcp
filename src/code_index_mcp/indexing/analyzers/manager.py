"""
Language analyzer manager for coordinating code analysis.

This module manages language-specific analyzers and coordinates the analysis
of multiple files, providing parallel processing and fallback mechanisms.
"""

import concurrent.futures
from typing import Dict, List, Optional
from ..models import FileInfo, FileAnalysisResult
from .base import LanguageAnalyzer, GenericAnalyzer
from code_index_mcp.constants import SUPPORTED_EXTENSIONS


class LanguageAnalyzerManager:
    """Manages language-specific analyzers and coordinates analysis."""
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the analyzer manager.
        
        Args:
            max_workers: Maximum number of worker threads for parallel analysis.
                        If None, uses default ThreadPoolExecutor behavior.
        """
        self.analyzers: Dict[str, LanguageAnalyzer] = {}
        self.generic_analyzer = GenericAnalyzer()
        self.max_workers = max_workers
        self.register_default_analyzers()
    
    def register_analyzer(self, analyzer: LanguageAnalyzer):
        """Register a language analyzer for specific file extensions."""
        for extension in analyzer.supported_extensions:
            self.analyzers[extension] = analyzer
    
    def register_default_analyzers(self):
        """Register all default language analyzers."""
        # Import here to avoid circular imports
        from .python_analyzer import PythonAnalyzer
        from .javascript_analyzer import JavaScriptAnalyzer
        from .java_analyzer import JavaAnalyzer
        from .go_analyzer import GoAnalyzer
        from .c_analyzer import CAnalyzer
        from .cpp_analyzer import CppAnalyzer
        from .csharp_analyzer import CSharpAnalyzer
        from .objective_c_analyzer import ObjectiveCAnalyzer
        
        # Register all analyzers
        analyzers = [
            PythonAnalyzer(),
            JavaScriptAnalyzer(),
            JavaAnalyzer(),
            GoAnalyzer(),
            CAnalyzer(),
            CppAnalyzer(),
            CSharpAnalyzer(),
            ObjectiveCAnalyzer()
        ]
        
        for analyzer in analyzers:
            self.register_analyzer(analyzer)
    
    def get_analyzer(self, file_extension: str) -> Optional[LanguageAnalyzer]:
        """Get appropriate analyzer for file extension."""
        # Only analyze files that are in our supported extensions list
        if file_extension not in SUPPORTED_EXTENSIONS:
            return None
        
        # Return specific analyzer if available, otherwise generic analyzer
        return self.analyzers.get(file_extension, self.generic_analyzer)
    
    def analyze_files(self, files_with_content: List[tuple]) -> List[FileAnalysisResult]:
        """
        Analyze multiple files in parallel using appropriate analyzers.
        
        Args:
            files_with_content: List of (FileInfo, content) tuples
            
        Returns:
            List of FileAnalysisResult objects
        """
        if not files_with_content:
            return []
        
        # For small numbers of files, process sequentially to avoid overhead
        if len(files_with_content) <= 3:
            return [self._analyze_single_file(file_info, content) 
                   for file_info, content in files_with_content]
        
        # Process files in parallel
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all analysis tasks
            future_to_file = {
                executor.submit(self._analyze_single_file, file_info, content): file_info
                for file_info, content in files_with_content
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # Create error result for failed analysis
                    error_result = FileAnalysisResult(
                        file_info=file_info,
                        functions=[],
                        classes=[],
                        imports=[],
                        language_specific={},
                        analysis_errors=[f"Analysis failed: {str(e)}"]
                    )
                    results.append(error_result)
        
        # Sort results by file ID to maintain consistent ordering
        results.sort(key=lambda r: r.file_info.id)
        return results
    
    def _analyze_single_file(self, file_info: FileInfo, content: str) -> FileAnalysisResult:
        """
        Analyze a single file with the appropriate analyzer.
        
        Args:
            file_info: FileInfo object with file metadata
            content: File content as string
            
        Returns:
            FileAnalysisResult containing extracted information
        """
        analyzer = self.get_analyzer(file_info.extension)
        
        # Skip files that are not in our supported extensions
        if analyzer is None:
            return FileAnalysisResult(
                file_info=file_info,
                functions=[],
                classes=[],
                imports=[],
                language_specific={},
                analysis_errors=[f"File extension {file_info.extension} not supported"]
            )
        
        try:
            return analyzer.analyze(content, file_info)
        except Exception as e:
            # Fallback to generic analyzer if specific analyzer fails
            try:
                result = self.generic_analyzer.analyze(content, file_info)
                result.analysis_errors.append(
                    f"Primary analyzer ({analyzer.language_name}) failed: {str(e)}, "
                    f"fell back to generic analyzer"
                )
                return result
            except Exception as fallback_error:
                # If even generic analyzer fails, return minimal result
                return FileAnalysisResult(
                    file_info=file_info,
                    functions=[],
                    classes=[],
                    imports=[],
                    language_specific={},
                    analysis_errors=[
                        f"Primary analyzer failed: {str(e)}",
                        f"Fallback analyzer failed: {str(fallback_error)}"
                    ]
                )
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions."""
        return SUPPORTED_EXTENSIONS.copy()
    
    def get_analyzer_info(self) -> Dict[str, Dict[str, any]]:
        """Get information about registered analyzers."""
        info = {}
        
        # Group extensions by analyzer
        analyzer_to_extensions = {}
        for ext, analyzer in self.analyzers.items():
            analyzer_name = analyzer.language_name
            if analyzer_name not in analyzer_to_extensions:
                analyzer_to_extensions[analyzer_name] = []
            analyzer_to_extensions[analyzer_name].append(ext)
        
        # Build info dictionary
        for analyzer_name, extensions in analyzer_to_extensions.items():
            info[analyzer_name] = {
                'extensions': sorted(extensions),
                'analyzer_class': self.analyzers[extensions[0]].__class__.__name__
            }
        
        return info