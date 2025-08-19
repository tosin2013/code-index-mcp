"""
JavaScript/TypeScript-specific dependency configuration.

This module provides JavaScript and TypeScript specific dependency classification,
including npm/yarn package management and Node.js built-in modules.
"""

import json
import re
import logging
from typing import Set, Dict, List, Optional
from .base import BaseDependencyConfig

logger = logging.getLogger(__name__)


class JavaScriptDependencyConfig(BaseDependencyConfig):
    """
    JavaScript/TypeScript-specific dependency configuration.

    Handles JavaScript and TypeScript import classification with support for:
    - Node.js built-in modules
    - npm/yarn package management
    - ES6 modules and CommonJS
    - Scoped packages (@scope/package)
    - Relative and absolute imports
    """

    def get_language_name(self) -> str:
        return "javascript"

    def get_stdlib_modules(self) -> Set[str]:
        """Return Node.js built-in modules."""
        return {
            # Node.js built-in modules
            'assert', 'async_hooks', 'buffer', 'child_process', 'cluster',
            'console', 'constants', 'crypto', 'dgram', 'dns', 'domain',
            'events', 'fs', 'http', 'http2', 'https', 'inspector',
            'module', 'net', 'os', 'path', 'perf_hooks', 'process',
            'punycode', 'querystring', 'readline', 'repl', 'stream',
            'string_decoder', 'timers', 'tls', 'trace_events', 'tty',
            'url', 'util', 'v8', 'vm', 'worker_threads', 'zlib'
        }

    def _compile_patterns(self) -> None:
        """Compile JavaScript-specific regex patterns."""
        try:
            self._third_party_patterns = [
                # Standard npm package names
                re.compile(r'^[a-z][a-z0-9-._]*$'),
                # Scoped packages
                re.compile(r'^@[a-z0-9-]+/[a-z0-9-._]+$'),
                # Common frameworks and libraries
                re.compile(r'^(react|vue|angular|express|lodash|jquery)'),
            ]

            self._local_patterns = [
                # Relative imports
                re.compile(r'^\.\.?/'),
                # Absolute local paths
                re.compile(r'^/[^/]'),
                # Webpack aliases
                re.compile(r'^@/'),
                re.compile(r'^~/'),
                # Common local patterns
                re.compile(r'^(src|lib|components|utils|helpers)/'),
            ]
        except Exception as e:
            logger.warning(f"Error compiling JavaScript patterns: {e}")

    def _classify_import_impl(self, import_path: str, context: Dict[str, any] = None) -> str:
        """JavaScript-specific import classification."""
        # Handle scoped packages
        if import_path.startswith('@'):
            return 'third_party'

        # Check for common third-party packages
        common_third_party = {
            'react', 'vue', 'angular', 'svelte', 'jquery', 'lodash',
            'express', 'koa', 'fastify', 'next', 'nuxt', 'gatsby',
            'webpack', 'vite', 'rollup', 'parcel', 'babel', 'typescript',
            'eslint', 'prettier', 'jest', 'mocha', 'cypress', 'playwright',
            'axios', 'fetch', 'node-fetch', 'superagent', 'got',
            'moment', 'dayjs', 'date-fns', 'luxon',
            'styled-components', 'emotion', '@emotion/react',
            'material-ui', '@mui/material', 'antd', 'bootstrap',
            'tailwindcss', 'bulma', 'semantic-ui-react',
            'redux', 'mobx', 'zustand', 'recoil', 'rxjs',
            'graphql', 'apollo-client', '@apollo/client',
            'socket.io', 'ws', 'uuid', 'bcrypt', 'jsonwebtoken',
            'mongoose', 'sequelize', 'prisma', 'typeorm'
        }

        base_package = self.get_package_name_from_import(import_path)
        if base_package in common_third_party:
            return 'third_party'

        # Check context for npm/yarn info
        if context:
            # Check package.json dependencies
            npm_deps = context.get('npm_dependencies', set())
            if base_package in npm_deps:
                return 'third_party'

            # Check node_modules
            node_modules = context.get('node_modules', set())
            if base_package in node_modules:
                return 'third_party'

        # Default to third_party for JavaScript ecosystem
        return 'third_party'

    def normalize_import_path(self, raw_path: str) -> str:
        """Normalize JavaScript import path."""
        normalized = raw_path.strip()

        # Remove file extensions
        for ext in ['.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs']:
            if normalized.endswith(ext):
                normalized = normalized[:-len(ext)]
                break

        # Remove /index suffix
        if normalized.endswith('/index'):
            normalized = normalized[:-6]

        return normalized

    def get_package_manager_files(self) -> Set[str]:
        """Return JavaScript package manager files."""
        return {
            'package.json',
            'package-lock.json',
            'yarn.lock',
            'pnpm-lock.yaml',
            'npm-shrinkwrap.json',
            'lerna.json',
            'rush.json'
        }

    def extract_dependencies_from_file(self, file_path: str, file_content: str) -> List[str]:
        """Extract dependencies from JavaScript package manager files."""
        dependencies = []

        try:
            if file_path.endswith('package.json'):
                dependencies = self._parse_package_json(file_content)
            elif file_path.endswith('package-lock.json'):
                dependencies = self._parse_package_lock(file_content)
            elif file_path.endswith('yarn.lock'):
                dependencies = self._parse_yarn_lock(file_content)
            elif file_path.endswith('pnpm-lock.yaml'):
                dependencies = self._parse_pnpm_lock(file_content)
        except Exception as e:
            logger.debug(f"Error parsing JavaScript dependency file {file_path}: {e}")

        return dependencies

    def _parse_package_json(self, content: str) -> List[str]:
        """Parse package.json for dependencies."""
        dependencies = []
        try:
            data = json.loads(content)

            # Extract from different dependency sections
            for section in ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies']:
                if section in data and isinstance(data[section], dict):
                    dependencies.extend(data[section].keys())

        except Exception as e:
            logger.debug(f"Error parsing package.json: {e}")

        return dependencies

    def _parse_package_lock(self, content: str) -> List[str]:
        """Parse package-lock.json for dependencies."""
        dependencies = []
        try:
            data = json.loads(content)

            # Extract from packages section (npm v7+)
            if 'packages' in data:
                for package_path in data['packages']:
                    if package_path.startswith('node_modules/'):
                        package_name = package_path[13:]  # Remove 'node_modules/' prefix
                        if package_name and not package_name.startswith('@'):
                            dependencies.append(package_name)
                        elif package_name.startswith('@'):
                            # Handle scoped packages
                            dependencies.append(package_name)

            # Extract from dependencies section (npm v6)
            elif 'dependencies' in data:
                dependencies.extend(data['dependencies'].keys())

        except Exception as e:
            logger.debug(f"Error parsing package-lock.json: {e}")

        return dependencies

    def _parse_yarn_lock(self, content: str) -> List[str]:
        """Parse yarn.lock for dependencies."""
        dependencies = []
        try:
            # Parse yarn.lock format
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '@' in line and ':' in line:
                    # Extract package name from yarn.lock entry
                    package_spec = line.split(':')[0].strip()
                    if '"' in package_spec:
                        package_name = package_spec.split('"')[1]
                        if package_name and package_name not in dependencies:
                            # Remove version specifier
                            base_name = package_name.split('@')[0] if not package_name.startswith('@') else '@' + package_name.split('@')[1]
                            if base_name:
                                dependencies.append(base_name)

        except Exception as e:
            logger.debug(f"Error parsing yarn.lock: {e}")

        return dependencies

    def _parse_pnpm_lock(self, content: str) -> List[str]:
        """Parse pnpm-lock.yaml for dependencies."""
        dependencies = []
        try:
            # Simple YAML parsing for dependencies
            in_deps_section = False
            for line in content.splitlines():
                line = line.strip()
                if line in ['dependencies:', 'devDependencies:']:
                    in_deps_section = True
                    continue
                elif line and not line.startswith(' ') and in_deps_section:
                    in_deps_section = False
                elif in_deps_section and ':' in line:
                    dep_name = line.split(':')[0].strip()
                    if dep_name and not dep_name.startswith('#'):
                        dependencies.append(dep_name)

        except Exception as e:
            logger.debug(f"Error parsing pnpm-lock.yaml: {e}")

        return dependencies

    def is_scoped_package(self, import_path: str) -> bool:
        """Check if import is a scoped npm package."""
        return import_path.startswith('@') and '/' in import_path

    def get_package_name_from_import(self, import_path: str) -> str:
        """Extract package name from JavaScript import path."""
        # Handle scoped packages
        if import_path.startswith('@'):
            parts = import_path.split('/')
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
            return parts[0]

        # Regular packages
        return import_path.split('/')[0]

    def supports_version_detection(self) -> bool:
        """JavaScript supports version detection through package files."""
        return True

    def detect_package_version(self, package_name: str, context: Dict[str, any] = None) -> Optional[str]:
        """Detect JavaScript package version from context."""
        if not context:
            return None

        # Check package-lock.json or yarn.lock data
        lock_data = context.get('lock_file_data', {})
        if package_name in lock_data:
            return lock_data[package_name].get('version')

        # Check package.json dependencies
        package_json = context.get('package_json', {})
        for dep_section in ['dependencies', 'devDependencies', 'peerDependencies']:
            if dep_section in package_json and package_name in package_json[dep_section]:
                return package_json[dep_section][package_name]

        return None
