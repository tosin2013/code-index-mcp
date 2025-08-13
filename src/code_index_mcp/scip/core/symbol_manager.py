"""SCIP Symbol Manager - Standard-compliant symbol ID generation with moniker support."""

import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from .moniker_manager import MonikerManager, PackageInfo


logger = logging.getLogger(__name__)


@dataclass
class SCIPSymbolInfo:
    """Information about a SCIP symbol."""
    scheme: str          # scip-python, scip-javascript, etc.
    manager: str         # local, pypi, npm, maven, etc.
    package: str         # package/project name
    version: str         # version (for external packages)
    descriptors: str     # symbol path with descriptors


class SCIPSymbolManager:
    """
    Standard SCIP Symbol Manager for local projects with cross-repository support.
    
    Generates symbol IDs that comply with SCIP specification:
    Format: {scheme} {manager} {package} {version} {descriptors}
    
    For local projects:
    - scheme: scip-{language}
    - manager: local
    - package: project name
    - version: empty (local projects don't have versions)
    - descriptors: file_path/symbol_path{descriptor}
    
    For external packages:
    - scheme: scip-{language}
    - manager: npm, pip, maven, etc.
    - package: external package name
    - version: package version
    - descriptors: module_path/symbol_path{descriptor}
    """
    
    def __init__(self, project_path: str, project_name: Optional[str] = None):
        """
        Initialize symbol manager for a project.
        
        Args:
            project_path: Absolute path to project root
            project_name: Project name (defaults to directory name)
        """
        self.project_path = Path(project_path).resolve()
        self.project_name = project_name or self.project_path.name
        
        # Normalize project name for SCIP (replace invalid characters)
        self.project_name = self._normalize_package_name(self.project_name)
        
        # Initialize moniker manager for cross-repository support
        self.moniker_manager = MonikerManager(str(self.project_path), self.project_name)
        
        logger.debug(f"SCIPSymbolManager initialized for project: {self.project_name}")
    
    def create_local_symbol(self, 
                           language: str,
                           file_path: str,
                           symbol_path: List[str],
                           descriptor: str = "") -> str:
        """
        Create a local symbol ID following SCIP standard.
        
        Args:
            language: Programming language (python, javascript, java, etc.)
            file_path: File path relative to project root
            symbol_path: List of symbol components (module, class, function, etc.)
            descriptor: SCIP descriptor ((), #, ., etc.)
            
        Returns:
            Standard SCIP symbol ID
            
        Example:
            create_local_symbol("python", "src/main.py", ["MyClass", "method"], "()")
            -> "scip-python local myproject src/main.py/MyClass#method()."
        """
        # Normalize inputs
        scheme = f"scip-{language.lower()}"
        manager = "local"
        package = self.project_name
        version = ""  # Local projects don't have versions
        
        # Build descriptors path
        normalized_file_path = self._normalize_file_path(file_path)
        symbol_components = symbol_path.copy()
        
        if symbol_components:
            # Last component gets the descriptor
            last_symbol = symbol_components[-1] + descriptor
            symbol_components[-1] = last_symbol
            
            descriptors = f"{normalized_file_path}/{'/'.join(symbol_components)}"
        else:
            descriptors = normalized_file_path
        
        # Build final symbol ID
        parts = [scheme, manager, package]
        if version:
            parts.append(version)
        parts.append(descriptors)
        
        symbol_id = " ".join(parts)
        
        logger.debug(f"Created local symbol: {symbol_id}")
        return symbol_id
    
    def create_builtin_symbol(self, language: str, builtin_name: str) -> str:
        """
        Create a symbol ID for built-in language constructs.
        
        Args:
            language: Programming language
            builtin_name: Name of built-in (str, int, Object, etc.)
            
        Returns:
            SCIP symbol ID for built-in
        """
        scheme = f"scip-{language.lower()}"
        manager = "builtin"
        package = language.lower()
        descriptors = builtin_name
        
        return f"{scheme} {manager} {package} {descriptors}"
    
    def create_stdlib_symbol(self, 
                            language: str,
                            module_name: str,
                            symbol_name: str,
                            descriptor: str = "") -> str:
        """
        Create a symbol ID for standard library symbols.
        
        Args:
            language: Programming language
            module_name: Standard library module name
            symbol_name: Symbol name within module
            descriptor: SCIP descriptor
            
        Returns:
            SCIP symbol ID for standard library symbol
        """
        scheme = f"scip-{language.lower()}"
        manager = "stdlib"
        package = language.lower()
        descriptors = f"{module_name}/{symbol_name}{descriptor}"
        
        return f"{scheme} {manager} {package} {descriptors}"

    def create_external_symbol(self,
                              language: str,
                              package_name: str,
                              module_path: str,
                              symbol_name: str,
                              descriptor: str = "",
                              version: Optional[str] = None,
                              alias: Optional[str] = None) -> str:
        """
        Create a symbol ID for external package symbols using moniker manager.
        
        Args:
            language: Programming language
            package_name: External package name
            module_path: Module path within package
            symbol_name: Symbol name
            descriptor: SCIP descriptor
            version: Package version
            alias: Local alias for the symbol
            
        Returns:
            SCIP symbol ID for external symbol
        """
        return self.moniker_manager.register_import(
            package_name=package_name,
            symbol_name=symbol_name,
            module_path=module_path,
            alias=alias,
            version=version
        )

    def register_export(self,
                       symbol_name: str,
                       symbol_kind: str,
                       file_path: str,
                       is_default: bool = False) -> str:
        """
        Register a symbol as exportable from this project.
        
        Args:
            symbol_name: Name of the exported symbol
            symbol_kind: Kind of symbol (function, class, etc.)
            file_path: File path where symbol is defined
            is_default: Whether this is a default export
            
        Returns:
            SCIP symbol ID for the exported symbol
        """
        normalized_file_path = self._normalize_file_path(file_path)
        return self.moniker_manager.register_export(
            symbol_name=symbol_name,
            symbol_kind=symbol_kind,
            module_path=normalized_file_path,
            is_default=is_default
        )

    def resolve_import_reference(self, symbol_name: str, context_file: str) -> Optional[str]:
        """
        Resolve a symbol reference to an imported external symbol.
        
        Args:
            symbol_name: Name of the symbol being referenced
            context_file: File where the reference occurs
            
        Returns:
            SCIP symbol ID if resolved to external import, None otherwise
        """
        return self.moniker_manager.resolve_import_reference(symbol_name, context_file)

    def get_external_symbols(self):
        """Get external symbol information for the index."""
        return self.moniker_manager.get_external_symbol_information()

    def get_dependencies(self) -> Dict[str, PackageInfo]:
        """Get information about detected external dependencies."""
        return self.moniker_manager.get_dependency_info()
    
    def parse_symbol(self, symbol_id: str) -> Optional[SCIPSymbolInfo]:
        """
        Parse a SCIP symbol ID into components.
        
        Args:
            symbol_id: SCIP symbol ID to parse
            
        Returns:
            SCIPSymbolInfo object or None if parsing fails
        """
        try:
            parts = symbol_id.split(" ", 4)
            if len(parts) < 4:
                return None
            
            scheme = parts[0]
            manager = parts[1]
            package = parts[2]
            
            # Handle version (optional)
            if len(parts) == 5:
                version = parts[3]
                descriptors = parts[4]
            else:
                version = ""
                descriptors = parts[3]
            
            return SCIPSymbolInfo(
                scheme=scheme,
                manager=manager,
                package=package,
                version=version,
                descriptors=descriptors
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse symbol ID '{symbol_id}': {e}")
            return None
    
    def get_file_path_from_symbol(self, symbol_id: str) -> Optional[str]:
        """
        Extract file path from a local symbol ID.
        
        Args:
            symbol_id: SCIP symbol ID
            
        Returns:
            File path or None if not a local symbol
        """
        symbol_info = self.parse_symbol(symbol_id)
        if not symbol_info or symbol_info.manager != "local":
            return None
        
        # Extract file path from descriptors (before first '/')
        descriptors = symbol_info.descriptors
        if "/" in descriptors:
            return descriptors.split("/", 1)[0]
        
        return descriptors
    
    def _normalize_package_name(self, name: str) -> str:
        """Normalize package name for SCIP compatibility."""
        # Replace invalid characters with underscores
        import re
        normalized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        
        # Ensure it starts with a letter or underscore
        if normalized and not normalized[0].isalpha() and normalized[0] != '_':
            normalized = f"_{normalized}"
        
        return normalized.lower()
    
    def _normalize_file_path(self, file_path: str) -> str:
        """Normalize file path for SCIP descriptors."""
        # Convert to forward slashes and remove leading slash
        normalized = file_path.replace('\\', '/')
        if normalized.startswith('/'):
            normalized = normalized[1:]
        
        return normalized
    
    def get_project_info(self) -> Dict[str, Any]:
        """Get project information."""
        return {
            'project_path': str(self.project_path),
            'project_name': self.project_name,
            'normalized_name': self.project_name
        }