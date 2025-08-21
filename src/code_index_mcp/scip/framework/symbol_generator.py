"""SCIP Symbol Generator - Strict format compliance for SCIP symbol ID generation."""

import re
import logging
from typing import Optional
from .types import SCIPSymbolDescriptor


logger = logging.getLogger(__name__)


class SCIPSymbolGenerator:
    """SCIP standard symbol generator - strict format compliance."""
    
    # SCIP symbol format validation patterns
    SCHEME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9\-_]*$')
    LOCAL_ID_PATTERN = re.compile(r'^[^\s]+$')
    GLOBAL_SYMBOL_PATTERN = re.compile(r'^[^\s]+\s+[^\s]+\s+[^\s]+(\s+[^\s]+)?$')
    
    def __init__(self, scheme: str, package_manager: str, package_name: str, version: str):
        """Initialize symbol generator with validation."""
        self._validate_scheme(scheme)
        self._validate_package_info(package_manager, package_name, version)
        
        self.scheme = scheme
        self.package = f"{package_manager} {package_name} {version}"
    
    def create_local_symbol(self, descriptor: SCIPSymbolDescriptor) -> str:
        """Create local symbol ID - enforced SCIP format."""
        local_id = descriptor.to_scip_descriptor()
        
        # Validate local ID format
        if not self._is_valid_local_id(local_id):
            raise ValueError(f"Invalid local symbol ID: {local_id}")
        
        return f"local {local_id}"
    
    def create_global_symbol(self, descriptor: SCIPSymbolDescriptor) -> str:
        """Create global symbol ID - complete SCIP format."""
        descriptor_str = descriptor.to_scip_descriptor()
        
        symbol_id = f"{self.scheme} {self.package} {descriptor_str}"
        
        # Validate global symbol format
        if not self._is_valid_global_symbol(symbol_id):
            raise ValueError(f"Invalid global symbol ID: {symbol_id}")
        
        return symbol_id
    
    def _validate_scheme(self, scheme: str) -> None:
        """Validate scheme format against SCIP standards."""
        if not scheme:
            raise ValueError("Scheme cannot be empty")
        
        if not self.SCHEME_PATTERN.match(scheme):
            raise ValueError(f"Invalid scheme format: {scheme}. Must match pattern: {self.SCHEME_PATTERN.pattern}")
        
        if ' ' in scheme.replace('  ', ''):  # Allow double space escaping
            raise ValueError(f"Scheme cannot contain spaces: {scheme}")
    
    def _validate_package_info(self, package_manager: str, package_name: str, version: str) -> None:
        """Validate package information components."""
        if not package_manager:
            raise ValueError("Package manager cannot be empty")
        if not package_name:
            raise ValueError("Package name cannot be empty")
        
        # Version can be empty for local projects
        for component in [package_manager, package_name, version]:
            if component and (' ' in component):
                raise ValueError(f"Package component cannot contain spaces: {component}")
    
    def _is_valid_local_id(self, local_id: str) -> bool:
        """Validate local ID format compliance."""
        if not local_id:
            return False
        
        # Check for leading/trailing spaces
        if local_id.startswith(' ') or local_id.endswith(' '):
            return False
        
        # Check basic pattern compliance
        return self.LOCAL_ID_PATTERN.match(local_id) is not None
    
    def _is_valid_global_symbol(self, symbol_id: str) -> bool:
        """Validate global symbol format compliance."""
        if not symbol_id:
            return False
        
        # Split into components
        parts = symbol_id.split(' ')
        if len(parts) < 4:
            return False
        
        # Validate each part is non-empty
        return all(part.strip() for part in parts)
    
    def validate_symbol_id(self, symbol_id: str) -> bool:
        """Validate any symbol ID against SCIP grammar."""
        if not symbol_id:
            return False
        
        if symbol_id.startswith('local '):
            return self._is_valid_local_id(symbol_id[6:])
        else:
            return self._is_valid_global_symbol(symbol_id)
    
    def parse_symbol_id(self, symbol_id: str) -> Optional[dict]:
        """Parse symbol ID into components for analysis."""
        if not self.validate_symbol_id(symbol_id):
            return None
        
        if symbol_id.startswith('local '):
            return {
                'type': 'local',
                'local_id': symbol_id[6:],
                'scheme': None,
                'package': None,
                'descriptor': symbol_id[6:]
            }
        else:
            parts = symbol_id.split(' ', 3)
            if len(parts) >= 4:
                return {
                    'type': 'global',
                    'scheme': parts[0],
                    'manager': parts[1],
                    'package': parts[2],
                    'descriptor': parts[3]
                }
        
        return None
    
    def get_generator_info(self) -> dict:
        """Get information about this generator instance."""
        return {
            'scheme': self.scheme,
            'package': self.package,
            'validation_patterns': {
                'scheme': self.SCHEME_PATTERN.pattern,
                'local_id': self.LOCAL_ID_PATTERN.pattern,
                'global_symbol': self.GLOBAL_SYMBOL_PATTERN.pattern
            }
        }