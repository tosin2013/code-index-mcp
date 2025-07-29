"""
File operations service for the Code Index MCP server.

This service handles file content retrieval, file analysis,
and file metadata operations.
"""

import os
from typing import Dict, Any
from mcp.server.fastmcp import Context

from .base_service import BaseService
from ..utils import ResponseFormatter
from ..analyzers.analyzer_factory import AnalyzerFactory


class FileService(BaseService):
    """
    Service for managing file operations and analysis.
    
    This service handles:
    - File content retrieval with security validation
    - File analysis and summarization
    - File metadata operations
    - Language-specific file analysis
    """
    

    
    def get_file_content(self, file_path: str) -> str:
        """
        Get the content of a specific file.
        
        Handles the logic for files://{file_path} MCP resource.
        
        Args:
            file_path: Path to the file (relative to project root)
            
        Returns:
            File content as string
            
        Raises:
            ValueError: If project is not set up or file path is invalid
            FileNotFoundError: If file does not exist
            UnicodeDecodeError: If file is binary or uses unsupported encoding
        """
        self._require_project_setup()
        self._require_valid_file_path(file_path)
        
        # Normalize the file path
        norm_path = os.path.normpath(file_path)
        full_path = os.path.join(self.base_path, norm_path)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            raise UnicodeDecodeError(
                'utf-8', b'', 0, 1, 
                f"File {file_path} appears to be a binary file or uses unsupported encoding."
            )
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise FileNotFoundError(f"Error reading file: {e}") from e
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a file and return summary information.
        
        Handles the logic for get_file_summary MCP tool.
        
        Args:
            file_path: Path to the file (relative to project root)
            
        Returns:
            Dictionary with file analysis results including:
            - Line count, size, extension, language
            - Functions, classes, imports found
            - Language-specific analysis data
            
        Raises:
            ValueError: If project is not set up or file path is invalid
        """
        self._require_project_setup()
        self._require_valid_file_path(file_path)
        
        # Normalize the file path
        norm_path = os.path.normpath(file_path)
        full_path = os.path.join(self.base_path, norm_path)
        
        # Get file extension for language-specific analysis
        _, ext = os.path.splitext(norm_path)
        
        try:
            # Try to get cached analysis from index if available
            if self.index_cache and 'files' in self.index_cache:
                for file_entry in self.index_cache['files']:
                    if file_entry.get('path') == norm_path:
                        # Return structured data from the index
                        return ResponseFormatter.file_summary_response(
                            file_path=norm_path,
                            line_count=file_entry.get('line_count', 0),
                            size_bytes=file_entry.get('size', 0),
                            extension=ext,
                            language=file_entry.get('language', 'unknown'),
                            functions=file_entry.get('functions', []),
                            classes=file_entry.get('classes', []),
                            imports=file_entry.get('imports', []),
                            language_specific=file_entry.get('language_specific', {}),
                            from_index=True
                        )
            
            # Get file content for analysis
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic file info
            lines = content.splitlines()
            line_count = len(lines)
            size_bytes = os.path.getsize(full_path)
            
            # Use the analyzer framework for language-specific analysis
            try:
                analyzer = AnalyzerFactory.get_analyzer(ext)
                if analyzer is None:
                    return ResponseFormatter.file_summary_response(
                        file_path=norm_path,
                        line_count=line_count,
                        size_bytes=size_bytes,
                        extension=ext,
                        error="No analyzer available for this file type"
                    )
                
                analysis_result = analyzer.analyze(content, norm_path, full_path)
                return analysis_result.to_dict()
                
            except Exception as e:
                # Fallback to basic summary if analyzer fails
                return ResponseFormatter.file_summary_response(
                    file_path=norm_path,
                    line_count=line_count,
                    size_bytes=size_bytes,
                    extension=ext,
                    error=f"Analysis failed: {str(e)}"
                )
                
        except (OSError, UnicodeDecodeError, ValueError) as e:
            raise ValueError(f"Error analyzing file: {e}") from e
    
    def validate_file_path(self, file_path: str) -> bool:
        """
        Validate a file path for security and accessibility.
        
        Args:
            file_path: Path to validate
            
        Returns:
            True if path is valid and accessible, False otherwise
        """
        if not self.base_path:
            return False
        
        error = self._validate_file_path(file_path)
        return error is None