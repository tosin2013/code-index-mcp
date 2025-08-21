"""Fallback SCIP Framework Module - For unsupported languages and files."""

from .factory import FallbackSCIPIndexFactory, create_fallback_scip_factory
from .relationship_extractor import FallbackRelationshipExtractor
from .enum_mapper import FallbackEnumMapper
from .basic_analyzer import FallbackBasicAnalyzer

__all__ = [
    'FallbackSCIPIndexFactory',
    'create_fallback_scip_factory',
    'FallbackRelationshipExtractor', 
    'FallbackEnumMapper',
    'FallbackBasicAnalyzer'
]