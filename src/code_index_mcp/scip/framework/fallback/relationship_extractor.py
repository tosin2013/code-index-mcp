"""Fallback relationship extractor implementation."""

from typing import List, Dict, Set, Optional, Any
from ..base.relationship_extractor import BaseRelationshipExtractor
from ..relationship_manager import SymbolRelationship, RelationshipType
from ..types import SCIPContext


class FallbackRelationshipExtractor(BaseRelationshipExtractor):
    """Fallback relationship extractor - minimal relationship analysis."""
    
    def __init__(self):
        """Initialize fallback relationship extractor."""
        super().__init__()
    
    def extract_symbol_relationships(self, context: SCIPContext) -> List[SymbolRelationship]:
        """Extract symbol relationships from fallback context (minimal analysis)."""
        relationships = []
        
        # For fallback, we only create minimal file-level relationships
        try:
            file_symbol = self._create_file_symbol_id(context.file_path)
            
            # Create self-relationship for the file
            relationships.append(SymbolRelationship(
                source_symbol=file_symbol,
                target_symbol=file_symbol,
                relationship_type=RelationshipType.CONTAINS,
                source_location=(0, 0),
                target_location=(0, 0),
                context_info={
                    "type": "file_self_reference",
                    "description": f"File contains itself: {context.file_path}"
                }
            ))
            
        except Exception:
            # Silently handle any errors in fallback mode
            pass
        
        return relationships
    
    def extract_import_relationships(self, context: SCIPContext) -> List[SymbolRelationship]:
        """Extract import relationships (none for fallback)."""
        return []  # Fallback doesn't analyze imports
    
    def extract_inheritance_relationships(self, context: SCIPContext) -> List[SymbolRelationship]:
        """Extract inheritance relationships (none for fallback)."""
        return []  # Fallback doesn't analyze inheritance
    
    def extract_call_relationships(self, context: SCIPContext) -> List[SymbolRelationship]:
        """Extract call relationships (none for fallback)."""
        return []  # Fallback doesn't analyze function calls
    
    def extract_field_access_relationships(self, context: SCIPContext) -> List[SymbolRelationship]:
        """Extract field access relationships (none for fallback)."""
        return []  # Fallback doesn't analyze field access
    
    def extract_type_relationships(self, context: SCIPContext) -> List[SymbolRelationship]:
        """Extract type relationships (none for fallback)."""
        return []  # Fallback doesn't analyze types
    
    def resolve_cross_file_references(self, 
                                    local_relationships: List[SymbolRelationship],
                                    global_symbol_map: Dict[str, Any]) -> List[SymbolRelationship]:
        """Resolve cross-file references (none for fallback)."""
        return local_relationships  # No cross-file analysis in fallback
    
    def get_relationship_statistics(self) -> Dict[str, int]:
        """Get relationship extraction statistics."""
        return {
            "total_relationships": 0,
            "import_relationships": 0,
            "inheritance_relationships": 0,
            "call_relationships": 0,
            "field_access_relationships": 0,
            "type_relationships": 0,
            "cross_file_relationships": 0
        }
    
    def _create_file_symbol_id(self, file_path: str) -> str:
        """Create a simple symbol ID for the file."""
        from pathlib import Path
        file_name = Path(file_path).stem
        return f"local {file_name}"