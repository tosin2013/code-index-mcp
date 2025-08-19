"""
Zig-specific dependency configuration.

This module provides Zig-specific dependency classification rules,
including standard library detection and package management.
"""

import re
import logging
from typing import Set, Dict, List, Optional
from .base import BaseDependencyConfig

logger = logging.getLogger(__name__)


class ZigDependencyConfig(BaseDependencyConfig):
    """
    Zig-specific dependency configuration.

    Handles Zig import classification with support for:
    - Zig standard library detection
    - Package manager (zigmod, gyro) support
    - Local .zig file imports
    - System library detection
    """

    def get_language_name(self) -> str:
        return "zig"

    def get_stdlib_modules(self) -> Set[str]:
        """Return comprehensive Zig standard library modules."""
        return {
            # Core standard library
            'std', 'builtin', 'testing',

            # Data structures and algorithms
            'math', 'mem', 'sort', 'hash', 'crypto',

            # Text and formatting
            'fmt', 'ascii', 'unicode', 'json',

            # System interaction
            'os', 'fs', 'process', 'thread', 'atomic',

            # Networking and I/O
            'net', 'http', 'io',

            # Compression and encoding
            'compress', 'base64',

            # Development and debugging
            'debug', 'log', 'meta', 'comptime',

            # Utilities
            'rand', 'time', 'zig',

            # Platform-specific
            'c', 'wasm',

            # Build system
            'build', 'target'
        }

    def _compile_patterns(self) -> None:
        """Compile Zig-specific regex patterns."""
        try:
            self._third_party_patterns = [
                # Package names (typically lowercase with hyphens)
                re.compile(r'^[a-z][a-z0-9-]*$'),
                # Zig package patterns
                re.compile(r'^zig-'),
                # GitHub-style packages
                re.compile(r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$'),
            ]

            self._local_patterns = [
                # Relative paths
                re.compile(r'^\.\.?/'),
                # .zig files
                re.compile(r'\.zig$'),
                # Local project paths
                re.compile(r'^src/'),
                re.compile(r'^lib/'),
            ]
        except Exception as e:
            logger.warning(f"Error compiling Zig patterns: {e}")

    def _classify_import_impl(self, import_path: str, context: Dict[str, any] = None) -> str:
        """Zig-specific import classification."""
        # Handle .zig file extensions
        if import_path.endswith('.zig'):
            return 'local'

        # Check for common third-party Zig packages
        common_third_party = {
            'zigmod', 'gyro', 'known-folders', 'zig-args', 'zig-clap',
            'zig-network', 'zig-sqlite', 'zig-json', 'zig-yaml',
            'raylib-zig', 'mach', 'zls', 'zig-gamedev'
        }

        base_package = self.get_package_name_from_import(import_path)
        if base_package in common_third_party:
            return 'third_party'

        # Check context for package manager info
        if context:
            # Check build.zig dependencies
            build_deps = context.get('build_dependencies', set())
            if base_package in build_deps:
                return 'third_party'

            # Check package manager files
            pkg_deps = context.get('package_dependencies', set())
            if base_package in pkg_deps:
                return 'third_party'

        # If it's not stdlib or clearly local, assume third_party
        return 'third_party'

    def normalize_import_path(self, raw_path: str) -> str:
        """Normalize Zig import path."""
        normalized = raw_path.strip()

        # Remove .zig extension for consistency
        if normalized.endswith('.zig'):
            normalized = normalized[:-4]

        # Normalize path separators
        normalized = normalized.replace('\\', '/')

        return normalized

    def get_package_manager_files(self) -> Set[str]:
        """Return Zig package manager files."""
        return {
            'build.zig',
            'build.zig.zon',
            'zigmod.yml',
            'zigmod.lock',
            'gyro.zzz',
            'deps.zig'
        }

    def extract_dependencies_from_file(self, file_path: str, file_content: str) -> List[str]:
        """Extract dependencies from Zig package manager files."""
        dependencies = []

        try:
            if file_path.endswith('build.zig'):
                dependencies = self._parse_build_zig(file_content)
            elif file_path.endswith('build.zig.zon'):
                dependencies = self._parse_build_zon(file_content)
            elif file_path.endswith('zigmod.yml'):
                dependencies = self._parse_zigmod_yml(file_content)
            elif file_path.endswith('gyro.zzz'):
                dependencies = self._parse_gyro_zzz(file_content)
        except Exception as e:
            logger.debug(f"Error parsing Zig dependency file {file_path}: {e}")

        return dependencies

    def _parse_build_zig(self, content: str) -> List[str]:
        """Parse build.zig for dependencies."""
        dependencies = []
        try:
            # Look for addPackage or dependency declarations
            for line in content.splitlines():
                line = line.strip()
                # Simple pattern matching for package declarations
                if 'addPackage' in line or 'dependency' in line:
                    # Extract quoted strings that might be package names
                    matches = re.findall(r'["\']([a-zA-Z0-9_-]+)["\']', line)
                    dependencies.extend(matches)
        except Exception as e:
            logger.debug(f"Error parsing build.zig: {e}")

        return dependencies

    def _parse_build_zon(self, content: str) -> List[str]:
        """Parse build.zig.zon file."""
        dependencies = []
        try:
            # Look for .dependencies section
            in_deps_section = False
            for line in content.splitlines():
                line = line.strip()
                if '.dependencies' in line:
                    in_deps_section = True
                    continue
                elif in_deps_section and line.startswith('}'):
                    break
                elif in_deps_section and '=' in line:
                    # Extract dependency name
                    dep_name = line.split('=')[0].strip().strip('.')
                    if dep_name:
                        dependencies.append(dep_name)
        except Exception as e:
            logger.debug(f"Error parsing build.zig.zon: {e}")

        return dependencies

    def _parse_zigmod_yml(self, content: str) -> List[str]:
        """Parse zigmod.yml file."""
        dependencies = []
        try:
            # Simple YAML parsing for dependencies section
            in_deps_section = False
            for line in content.splitlines():
                line = line.strip()
                if line.startswith('dependencies:'):
                    in_deps_section = True
                    continue
                elif in_deps_section and line.startswith('-'):
                    # Extract dependency info
                    if 'src:' in line:
                        # Extract from src: field
                        match = re.search(r'src:\s*([^\s]+)', line)
                        if match:
                            src = match.group(1)
                            # Extract package name from URL or path
                            if '/' in src:
                                dep_name = src.split('/')[-1]
                                if dep_name:
                                    dependencies.append(dep_name)
                elif in_deps_section and not line.startswith(' ') and not line.startswith('-'):
                    break
        except Exception as e:
            logger.debug(f"Error parsing zigmod.yml: {e}")

        return dependencies

    def _parse_gyro_zzz(self, content: str) -> List[str]:
        """Parse gyro.zzz file."""
        dependencies = []
        try:
            # Look for deps section in gyro format
            for line in content.splitlines():
                line = line.strip()
                if line.startswith('deps:'):
                    # Extract dependencies from gyro format
                    deps_part = line[5:].strip()
                    if deps_part:
                        # Simple parsing of dependency list
                        for dep in deps_part.split():
                            if dep:
                                dependencies.append(dep)
        except Exception as e:
            logger.debug(f"Error parsing gyro.zzz: {e}")

        return dependencies

    def get_package_name_from_import(self, import_path: str) -> str:
        """Extract package name from Zig import path."""
        # Handle different Zig import patterns
        if '/' in import_path:
            # GitHub-style: owner/repo
            parts = import_path.split('/')
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
            return parts[0]

        # Remove .zig extension if present
        if import_path.endswith('.zig'):
            import_path = import_path[:-4]

        return import_path
