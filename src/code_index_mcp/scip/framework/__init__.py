"""SCIP Framework Infrastructure - Complete framework for SCIP standard compliance."""

# Core framework components
from .types import SCIPSymbolDescriptor, SCIPPositionInfo, SCIPSymbolContext, SCIPSymbolExtractor
from .standard_framework import SCIPStandardFramework
from .symbol_generator import SCIPSymbolGenerator
from .position_calculator import SCIPPositionCalculator
from .compliance_validator import SCIPComplianceValidator
from .relationship_manager import SCIPRelationshipManager, RelationshipType, SymbolRelationship

# Language-specific implementations (legacy - being phased out)
# NOTE: Old java_factory.py has been removed and replaced with java/ module

# Base abstract classes for all language implementations
from .base import (
    SCIPIndexFactory as BaseSCIPIndexFactory,
    BaseRelationshipExtractor,
    BaseEnumMapper,
    BaseLanguageAnalyzer
)

# New modular Python framework components
from .python import (
    PythonSCIPIndexFactory as ModularPythonSCIPIndexFactory,
    create_python_scip_factory,
    PythonRelationshipExtractor as ModularPythonRelationshipExtractor,
    PythonEnumMapper as ModularPythonEnumMapper,
    PythonASTAnalyzer
)

# New modular JavaScript framework components
from .javascript import (
    JavaScriptSCIPIndexFactory as ModularJavaScriptSCIPIndexFactory,
    create_javascript_scip_factory,
    JavaScriptRelationshipExtractor as ModularJavaScriptRelationshipExtractor,
    JavaScriptEnumMapper as ModularJavaScriptEnumMapper,
    JavaScriptSyntaxAnalyzer
)

# New modular Java framework components
from .java import (
    JavaSCIPIndexFactory as ModularJavaSCIPIndexFactory,
    create_java_scip_factory,
    JavaRelationshipExtractor as ModularJavaRelationshipExtractor,
    JavaEnumMapper as ModularJavaEnumMapper,
    JavaTreeSitterAnalyzer
)

# New modular Objective-C framework components
from .objective_c import (
    ObjectiveCSCIPIndexFactory as ModularObjectiveCSCIPIndexFactory,
    create_objective_c_scip_factory,
    ObjectiveCRelationshipExtractor as ModularObjectiveCRelationshipExtractor,
    ObjectiveCEnumMapper as ModularObjectiveCEnumMapper,
    ObjectiveCClangAnalyzer
)

# New modular Zig framework components
from .zig import (
    ZigSCIPIndexFactory as ModularZigSCIPIndexFactory,
    create_zig_scip_factory,
    ZigRelationshipExtractor as ModularZigRelationshipExtractor,
    ZigEnumMapper as ModularZigEnumMapper,
    ZigTreeSitterAnalyzer
)

# New modular Fallback framework components
from .fallback import (
    FallbackSCIPIndexFactory as ModularFallbackSCIPIndexFactory,
    create_fallback_scip_factory,
    FallbackRelationshipExtractor as ModularFallbackRelationshipExtractor,
    FallbackEnumMapper as ModularFallbackEnumMapper,
    FallbackBasicAnalyzer
)

# Advanced features
from .caching_system import SCIPCacheManager, BatchProcessor, CacheEntry
from .streaming_indexer import StreamingIndexer, IndexingProgress, IndexMerger
from .unified_api import SCIPFrameworkAPI, SCIPConfig, create_scip_framework

__all__ = [
    # Core framework
    'SCIPSymbolDescriptor',
    'SCIPPositionInfo', 
    'SCIPSymbolContext',
    'SCIPSymbolExtractor',
    'SCIPStandardFramework',
    'SCIPSymbolGenerator',
    'SCIPPositionCalculator', 
    'SCIPComplianceValidator',
    'SCIPRelationshipManager',
    'RelationshipType',
    'SymbolRelationship',
    
    # Language implementations (legacy - removed)
    # 'JavaSCIPIndexFactory', - moved to java/ module
    # 'JavaSCIPEnumMapper', - moved to java/ module
    
    # Base abstract classes
    'BaseSCIPIndexFactory',
    'BaseRelationshipExtractor',
    'BaseEnumMapper',
    'BaseLanguageAnalyzer',
    
    # New modular Python components
    'ModularPythonSCIPIndexFactory',
    'create_python_scip_factory',
    'ModularPythonRelationshipExtractor',
    'ModularPythonEnumMapper',
    'PythonASTAnalyzer',
    
    # New modular JavaScript components
    'ModularJavaScriptSCIPIndexFactory',
    'create_javascript_scip_factory',
    'ModularJavaScriptRelationshipExtractor',
    'ModularJavaScriptEnumMapper',
    'JavaScriptSyntaxAnalyzer',
    
    # New modular Java components
    'ModularJavaSCIPIndexFactory',
    'create_java_scip_factory',
    'ModularJavaRelationshipExtractor',
    'ModularJavaEnumMapper',
    'JavaTreeSitterAnalyzer',
    
    # New modular Objective-C components
    'ModularObjectiveCSCIPIndexFactory',
    'create_objective_c_scip_factory',
    'ModularObjectiveCRelationshipExtractor',
    'ModularObjectiveCEnumMapper',
    'ObjectiveCClangAnalyzer',
    
    # New modular Zig components
    'ModularZigSCIPIndexFactory',
    'create_zig_scip_factory',
    'ModularZigRelationshipExtractor',
    'ModularZigEnumMapper',
    'ZigTreeSitterAnalyzer',
    
    # New modular Fallback components
    'ModularFallbackSCIPIndexFactory',
    'create_fallback_scip_factory',
    'ModularFallbackRelationshipExtractor',
    'ModularFallbackEnumMapper',
    'FallbackBasicAnalyzer',
    
    # Advanced features
    'SCIPCacheManager',
    'BatchProcessor',
    'CacheEntry',
    'StreamingIndexer',
    'IndexingProgress',
    'IndexMerger',
    'SCIPFrameworkAPI',
    'SCIPConfig',
    'create_scip_framework'
]