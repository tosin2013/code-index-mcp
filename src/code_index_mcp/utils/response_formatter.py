"""
Response formatting utilities for the MCP server.

This module provides consistent response formatting functions used across
services to ensure uniform response structures and formats.
"""

import json
from typing import Any, Dict, List, Optional, Union


class ResponseFormatter:
    """
    Helper class for formatting responses consistently across services.
    
    This class provides static methods for formatting different types of
    responses in a consistent manner.
    """
    
    @staticmethod
    def success_response(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format a successful operation response.
        
        Args:
            message: Success message
            data: Optional additional data to include
            
        Returns:
            Formatted success response dictionary
        """
        response = {"status": "success", "message": message}
        if data:
            response.update(data)
        return response
    
    @staticmethod
    def error_response(message: str, error_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Format an error response.
        
        Args:
            message: Error message
            error_code: Optional error code for categorization
            
        Returns:
            Formatted error response dictionary
        """
        response = {"error": message}
        if error_code:
            response["error_code"] = error_code
        return response
    
    @staticmethod
    def file_list_response(files: List[str], status_message: str) -> Dict[str, Any]:
        """
        Format a file list response for find_files operations.
        
        Args:
            files: List of file paths
            status_message: Status message describing the operation result
            
        Returns:
            Formatted file list response
        """
        return {
            "files": files,
            "status": status_message
        }
    
    @staticmethod
    def search_results_response(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format search results response.
        
        Args:
            results: List of search result dictionaries
            
        Returns:
            Formatted search results response
        """
        return {
            "results": results
        }
    
    @staticmethod
    def config_response(config_data: Dict[str, Any]) -> str:
        """
        Format configuration data as JSON string.
        
        Args:
            config_data: Configuration data dictionary
            
        Returns:
            JSON formatted configuration string
        """
        return json.dumps(config_data, indent=2)
    
    @staticmethod
    def stats_response(stats_data: Dict[str, Any]) -> str:
        """
        Format statistics data as JSON string.
        
        Args:
            stats_data: Statistics data dictionary
            
        Returns:
            JSON formatted statistics string
        """
        return json.dumps(stats_data, indent=2)
    
    @staticmethod
    def file_summary_response(
        file_path: str,
        line_count: int,
        size_bytes: int,
        extension: str,
        language: str = "unknown",
        functions: Optional[List[str]] = None,
        classes: Optional[List[str]] = None,
        imports: Optional[List[str]] = None,
        language_specific: Optional[Dict[str, Any]] = None,
        from_index: bool = False,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format file summary response.
        
        Args:
            file_path: Path to the file
            line_count: Number of lines in the file
            size_bytes: File size in bytes
            extension: File extension
            language: Programming language detected
            functions: List of function names found
            classes: List of class names found
            imports: List of import statements
            language_specific: Language-specific analysis data
            from_index: Whether data came from index cache
            error: Error message if analysis failed
            
        Returns:
            Formatted file summary response
        """
        response = {
            "file_path": file_path,
            "line_count": line_count,
            "size_bytes": size_bytes,
            "extension": extension,
            "language": language,
            "functions": functions or [],
            "classes": classes or [],
            "imports": imports or [],
            "language_specific": language_specific or {},
            "from_index": from_index
        }
        
        if error:
            response["error"] = error
        
        return response
    
    @staticmethod
    def directory_info_response(
        temp_directory: str,
        exists: bool,
        is_directory: bool = False,
        contents: Optional[List[str]] = None,
        subdirectories: Optional[List[Dict[str, Any]]] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format directory information response.
        
        Args:
            temp_directory: Path to the directory
            exists: Whether the directory exists
            is_directory: Whether the path is a directory
            contents: List of directory contents
            subdirectories: List of subdirectory information
            error: Error message if operation failed
            
        Returns:
            Formatted directory info response
        """
        response = {
            "temp_directory": temp_directory,
            "exists": exists,
            "is_directory": is_directory
        }
        
        if contents is not None:
            response["contents"] = contents
        
        if subdirectories is not None:
            response["subdirectories"] = subdirectories
        
        if error:
            response["error"] = error
        
        return response
    
    @staticmethod
    def settings_info_response(
        settings_directory: str,
        temp_directory: str,
        temp_directory_exists: bool,
        config: Dict[str, Any],
        stats: Dict[str, Any],
        exists: bool,
        status: str = "configured",
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format settings information response.
        
        Args:
            settings_directory: Path to settings directory
            temp_directory: Path to temp directory
            temp_directory_exists: Whether temp directory exists
            config: Configuration data
            stats: Statistics data
            exists: Whether settings directory exists
            status: Status of the configuration
            message: Optional status message
            
        Returns:
            Formatted settings info response
        """
        response = {
            "settings_directory": settings_directory,
            "temp_directory": temp_directory,
            "temp_directory_exists": temp_directory_exists,
            "config": config,
            "stats": stats,
            "exists": exists
        }
        
        if status != "configured":
            response["status"] = status
        
        if message:
            response["message"] = message
        
        return response