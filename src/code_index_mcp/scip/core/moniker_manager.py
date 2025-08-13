"""
Moniker Manager - handles import/export monikers for cross-repository navigation.

Monikers in SCIP enable cross-repository symbol resolution by providing standardized
identifiers for external packages, modules, and dependencies.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple, NamedTuple
from pathlib import Path
from dataclasses import dataclass, field

from ..proto import scip_pb2


logger = logging.getLogger(__name__)


@dataclass
class PackageInfo:
    """Information about an external package."""
    manager: str  # e.g., "npm", "pip", "maven", "cargo"
    name: str     # Package name
    version: str  # Package version (optional)
    
    def to_scip_package(self) -> str:
        """Convert to SCIP package format."""
        if self.version:
            return f"{self.manager} {self.name} {self.version}"
        return f"{self.manager} {self.name}"


@dataclass
class ImportedSymbol:
    """Represents an imported symbol from external package."""
    package_info: PackageInfo
    module_path: str  # Module path within package
    symbol_name: str  # Symbol name
    alias: Optional[str] = None  # Local alias if any
    import_kind: str = "default"  # "default", "named", "namespace", "side_effect"
    
    @property
    def local_name(self) -> str:
        """Get the local name used in code."""
        return self.alias or self.symbol_name


@dataclass 
class ExportedSymbol:
    """Represents a symbol exported by this package."""
    symbol_name: str
    symbol_kind: str  # "function", "class", "variable", "type", etc.
    module_path: str  # Path within this package
    is_default: bool = False
    
    
class MonikerManager:
    """
    Manages import/export monikers for cross-repository symbol resolution.
    
    Key responsibilities:
    1. Track external package dependencies
    2. Generate SCIP symbols for imported symbols
    3. Create external symbol information
    4. Support package manager integration (npm, pip, maven, etc.)
    """
    
    def __init__(self, project_path: str, project_name: str):
        """
        Initialize moniker manager.
        
        Args:
            project_path: Root path of the current project
            project_name: Name of the current project
        """
        self.project_path = project_path
        self.project_name = project_name
        
        # Track imported symbols from external packages
        self.imported_symbols: Dict[str, ImportedSymbol] = {}
        
        # Track symbols exported by this project
        self.exported_symbols: Dict[str, ExportedSymbol] = {}
        
        # Package dependency information
        self.dependencies: Dict[str, PackageInfo] = {}
        
        # Cache for generated SCIP symbol IDs
        self._symbol_cache: Dict[str, str] = {}
        
        # Registry of known package managers and their patterns
        self.package_managers = {
            "npm": PackageManagerConfig(
                name="npm",
                config_files=["package.json", "package-lock.json", "yarn.lock"],
                import_patterns=[
                    r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
                    r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
                ]
            ),
            "pip": PackageManagerConfig(
                name="pip", 
                config_files=["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
                import_patterns=[
                    r"from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)",
                    r"import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)"
                ]
            ),
            "maven": PackageManagerConfig(
                name="maven",
                config_files=["pom.xml", "build.gradle", "build.gradle.kts"],
                import_patterns=[
                    r"import\s+([a-zA-Z_][a-zA-Z0-9_.]*)"
                ]
            ),
            "cargo": PackageManagerConfig(
                name="cargo",
                config_files=["Cargo.toml", "Cargo.lock"],
                import_patterns=[
                    r"use\s+([a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_][a-zA-Z0-9_]*)*)"
                ]
            )
        }
        
        # Detect project package manager
        self.detected_manager = self._detect_package_manager()
        
        logger.debug(f"Initialized MonikerManager for {project_name} with {self.detected_manager or 'no'} package manager")

    def register_import(self,
                       package_name: str,
                       symbol_name: str,
                       module_path: str = "",
                       alias: Optional[str] = None,
                       import_kind: str = "named",
                       version: Optional[str] = None) -> str:
        """
        Register an imported symbol from external package.
        
        Args:
            package_name: Name of the external package
            symbol_name: Name of the imported symbol
            module_path: Module path within package
            alias: Local alias for the symbol
            import_kind: Type of import (default, named, namespace, side_effect)
            version: Package version if known
            
        Returns:
            SCIP symbol ID for the imported symbol
        """
        # Create package info
        manager = self.detected_manager or "unknown"
        package_info = PackageInfo(manager, package_name, version or "")
        
        # Create imported symbol
        imported_symbol = ImportedSymbol(
            package_info=package_info,
            module_path=module_path,
            symbol_name=symbol_name,
            alias=alias,
            import_kind=import_kind
        )
        
        # Generate cache key
        cache_key = f"{package_name}.{module_path}.{symbol_name}"
        
        # Store imported symbol
        self.imported_symbols[cache_key] = imported_symbol
        self.dependencies[package_name] = package_info
        
        # Generate SCIP symbol ID
        symbol_id = self._generate_external_symbol_id(imported_symbol)
        self._symbol_cache[cache_key] = symbol_id
        
        logger.debug(f"Registered import: {cache_key} -> {symbol_id}")
        return symbol_id

    def register_export(self,
                       symbol_name: str,
                       symbol_kind: str,
                       module_path: str,
                       is_default: bool = False) -> str:
        """
        Register a symbol exported by this project.
        
        Args:
            symbol_name: Name of the exported symbol
            symbol_kind: Kind of symbol (function, class, etc.)
            module_path: Module path within this project
            is_default: Whether this is a default export
            
        Returns:
            SCIP symbol ID for the exported symbol
        """
        exported_symbol = ExportedSymbol(
            symbol_name=symbol_name,
            symbol_kind=symbol_kind,
            module_path=module_path,
            is_default=is_default
        )
        
        cache_key = f"export.{module_path}.{symbol_name}"
        self.exported_symbols[cache_key] = exported_symbol
        
        # Generate local symbol ID (this will be accessible to other projects)
        symbol_id = self._generate_export_symbol_id(exported_symbol)
        self._symbol_cache[cache_key] = symbol_id
        
        logger.debug(f"Registered export: {cache_key} -> {symbol_id}")
        return symbol_id

    def get_external_symbol_information(self) -> List[scip_pb2.SymbolInformation]:
        """
        Generate external symbol information for all imported symbols.
        
        Returns:
            List of SymbolInformation for external symbols
        """
        external_symbols = []
        
        for cache_key, imported_symbol in self.imported_symbols.items():
            symbol_id = self._symbol_cache.get(cache_key)
            if not symbol_id:
                continue
                
            symbol_info = scip_pb2.SymbolInformation()
            symbol_info.symbol = symbol_id
            symbol_info.display_name = imported_symbol.local_name
            symbol_info.kind = self._infer_symbol_kind(imported_symbol.symbol_name)
            
            # Add package information to documentation
            pkg = imported_symbol.package_info
            documentation = [
                f"External symbol from {pkg.name}",
                f"Package manager: {pkg.manager}"
            ]
            if pkg.version:
                documentation.append(f"Version: {pkg.version}")
            if imported_symbol.module_path:
                documentation.append(f"Module: {imported_symbol.module_path}")
                
            symbol_info.documentation.extend(documentation)
            
            external_symbols.append(symbol_info)
            
        logger.info(f"Generated {len(external_symbols)} external symbol information entries")
        return external_symbols

    def resolve_import_reference(self, symbol_name: str, context_file: str) -> Optional[str]:
        """
        Resolve a symbol reference to an imported symbol.
        
        Args:
            symbol_name: Name of the symbol being referenced
            context_file: File where the reference occurs
            
        Returns:
            SCIP symbol ID if the symbol is an import, None otherwise
        """
        # Look for exact matches first
        for cache_key, imported_symbol in self.imported_symbols.items():
            if imported_symbol.local_name == symbol_name:
                return self._symbol_cache.get(cache_key)
                
        # Look for partial matches (e.g., module.symbol)
        for cache_key, imported_symbol in self.imported_symbols.items():
            if symbol_name.startswith(imported_symbol.local_name + "."):
                # This might be a member access on imported module
                base_symbol_id = self._symbol_cache.get(cache_key)
                if base_symbol_id:
                    # Create symbol ID for the member
                    member_name = symbol_name[len(imported_symbol.local_name) + 1:]
                    return self._generate_member_symbol_id(imported_symbol, member_name)
                    
        return None

    def get_dependency_info(self) -> Dict[str, PackageInfo]:
        """Get information about all detected dependencies."""
        return self.dependencies.copy()

    def _detect_package_manager(self) -> Optional[str]:
        """Detect which package manager this project uses."""
        project_root = Path(self.project_path)
        
        for manager_name, config in self.package_managers.items():
            for config_file in config.config_files:
                if (project_root / config_file).exists():
                    logger.info(f"Detected {manager_name} package manager")
                    return manager_name
                    
        return None

    def _generate_external_symbol_id(self, imported_symbol: ImportedSymbol) -> str:
        """Generate SCIP symbol ID for external symbol."""
        pkg = imported_symbol.package_info
        
        # SCIP format: scheme manager package version descriptors
        parts = ["scip-python" if pkg.manager == "pip" else f"scip-{pkg.manager}"]
        parts.append(pkg.manager)
        parts.append(pkg.name)
        
        if pkg.version:
            parts.append(pkg.version)
        
        # Add module path if present
        if imported_symbol.module_path:
            parts.append(imported_symbol.module_path.replace("/", "."))
            
        # Add symbol descriptor
        if imported_symbol.symbol_name:
            parts.append(f"{imported_symbol.symbol_name}.")
        
        return " ".join(parts)

    def _generate_export_symbol_id(self, exported_symbol: ExportedSymbol) -> str:
        """Generate SCIP symbol ID for exported symbol."""
        # For exports, use local scheme but make it accessible
        manager = self.detected_manager or "local"
        
        parts = [f"scip-{manager}", manager, self.project_name]
        
        if exported_symbol.module_path:
            parts.append(exported_symbol.module_path.replace("/", "."))
            
        # Add appropriate descriptor based on symbol kind
        descriptor = self._get_symbol_descriptor(exported_symbol.symbol_kind)
        parts.append(f"{exported_symbol.symbol_name}{descriptor}")
        
        return " ".join(parts)

    def _generate_member_symbol_id(self, imported_symbol: ImportedSymbol, member_name: str) -> str:
        """Generate symbol ID for a member of an imported symbol."""
        base_id = self._generate_external_symbol_id(imported_symbol)
        
        # Remove the trailing descriptor and add member
        if base_id.endswith("."):
            base_id = base_id[:-1]
            
        return f"{base_id}#{member_name}."

    def _get_symbol_descriptor(self, symbol_kind: str) -> str:
        """Get SCIP descriptor suffix for symbol kind."""
        descriptors = {
            "function": "().",
            "method": "().",
            "class": "#",
            "interface": "#", 
            "type": "#",
            "variable": ".",
            "constant": ".",
            "module": "/",
            "namespace": "/"
        }
        return descriptors.get(symbol_kind.lower(), ".")

    def _infer_symbol_kind(self, symbol_name: str) -> int:
        """Infer SCIP symbol kind from symbol name."""
        # Simple heuristics - could be enhanced with actual type information
        if symbol_name.istitle():  # CamelCase suggests class/type
            return scip_pb2.Class
        elif symbol_name.isupper():  # UPPER_CASE suggests constant
            return scip_pb2.Constant
        elif "." in symbol_name:  # Dotted suggests module/namespace
            return scip_pb2.Module
        else:
            return scip_pb2.Function  # Default assumption


@dataclass
class PackageManagerConfig:
    """Configuration for a specific package manager."""
    name: str
    config_files: List[str] = field(default_factory=list)
    import_patterns: List[str] = field(default_factory=list)