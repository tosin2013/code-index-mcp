"""Base classes for SCIP framework components."""

from .index_factory import SCIPIndexFactory
from .relationship_extractor import BaseRelationshipExtractor
from .enum_mapper import BaseEnumMapper
from .language_analyzer import BaseLanguageAnalyzer

__all__ = [
    'SCIPIndexFactory',
    'BaseRelationshipExtractor', 
    'BaseEnumMapper',
    'BaseLanguageAnalyzer',
]