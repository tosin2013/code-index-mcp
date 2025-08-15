"""SCIP 關係類型定義和映射

這個模組定義了內部關係類型到 SCIP 標準關係的映射，
並提供關係驗證和規範化功能。
"""

import logging
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from dataclasses import dataclass

from ..proto import scip_pb2

logger = logging.getLogger(__name__)


class InternalRelationshipType(Enum):
    """內部關係類型定義 - 擴展版本支援更多關係類型"""
    
    # 函數調用關係
    CALLS = "calls"                    # A 調用 B
    CALLED_BY = "called_by"           # A 被 B 調用
    
    # 類型關係
    INHERITS = "inherits"             # A 繼承 B
    INHERITED_BY = "inherited_by"     # A 被 B 繼承
    IMPLEMENTS = "implements"         # A 實現 B (介面)
    IMPLEMENTED_BY = "implemented_by" # A 被 B 實現
    
    # 定義和引用關係
    DEFINES = "defines"               # A 定義 B
    DEFINED_BY = "defined_by"         # A 被 B 定義
    REFERENCES = "references"         # A 引用 B
    REFERENCED_BY = "referenced_by"   # A 被 B 引用
    
    # 類型相關關係
    TYPE_OF = "type_of"              # A 是 B 的類型
    HAS_TYPE = "has_type"            # A 有類型 B
    
    # 模組和包關係
    IMPORTS = "imports"              # A 導入 B
    IMPORTED_BY = "imported_by"      # A 被 B 導入
    EXPORTS = "exports"              # A 導出 B
    EXPORTED_BY = "exported_by"      # A 被 B 導出
    
    # 組合關係
    CONTAINS = "contains"            # A 包含 B (類包含方法)
    CONTAINED_BY = "contained_by"    # A 被 B 包含
    
    # 重寫關係
    OVERRIDES = "overrides"          # A 重寫 B
    OVERRIDDEN_BY = "overridden_by"  # A 被 B 重寫


@dataclass
class RelationshipMapping:
    """關係映射配置"""
    scip_is_reference: bool = False
    scip_is_implementation: bool = False
    scip_is_type_definition: bool = False
    scip_is_definition: bool = False
    description: str = ""


class SCIPRelationshipMapper:
    """
    SCIP 關係映射器
    
    負責將內部關係類型映射到標準 SCIP Relationship 格式，
    並提供關係驗證和查詢功能。
    """
    
    # 內部關係類型到 SCIP 標準的映射表
    RELATIONSHIP_MAPPINGS: Dict[InternalRelationshipType, RelationshipMapping] = {
        # 函數調用關係 - 使用 is_reference
        InternalRelationshipType.CALLS: RelationshipMapping(
            scip_is_reference=True,
            description="Function call relationship"
        ),
        InternalRelationshipType.CALLED_BY: RelationshipMapping(
            scip_is_reference=True,
            description="Reverse function call relationship"
        ),
        
        # 繼承關係 - 使用 is_reference
        InternalRelationshipType.INHERITS: RelationshipMapping(
            scip_is_reference=True,
            description="Class inheritance relationship"
        ),
        InternalRelationshipType.INHERITED_BY: RelationshipMapping(
            scip_is_reference=True,
            description="Reverse inheritance relationship"
        ),
        
        # 實現關係 - 使用 is_implementation
        InternalRelationshipType.IMPLEMENTS: RelationshipMapping(
            scip_is_implementation=True,
            description="Interface implementation relationship"
        ),
        InternalRelationshipType.IMPLEMENTED_BY: RelationshipMapping(
            scip_is_implementation=True,
            description="Reverse implementation relationship"
        ),
        
        # 定義關係 - 使用 is_definition
        InternalRelationshipType.DEFINES: RelationshipMapping(
            scip_is_definition=True,
            description="Symbol definition relationship"
        ),
        InternalRelationshipType.DEFINED_BY: RelationshipMapping(
            scip_is_definition=True,
            description="Reverse definition relationship"
        ),
        
        # 引用關係 - 使用 is_reference
        InternalRelationshipType.REFERENCES: RelationshipMapping(
            scip_is_reference=True,
            description="Symbol reference relationship"
        ),
        InternalRelationshipType.REFERENCED_BY: RelationshipMapping(
            scip_is_reference=True,
            description="Reverse reference relationship"
        ),
        
        # 類型關係 - 使用 is_type_definition
        InternalRelationshipType.TYPE_OF: RelationshipMapping(
            scip_is_type_definition=True,
            description="Type definition relationship"
        ),
        InternalRelationshipType.HAS_TYPE: RelationshipMapping(
            scip_is_type_definition=True,
            description="Has type relationship"
        ),
        
        # 導入/導出關係 - 使用 is_reference
        InternalRelationshipType.IMPORTS: RelationshipMapping(
            scip_is_reference=True,
            description="Module import relationship"
        ),
        InternalRelationshipType.IMPORTED_BY: RelationshipMapping(
            scip_is_reference=True,
            description="Reverse import relationship"
        ),
        InternalRelationshipType.EXPORTS: RelationshipMapping(
            scip_is_reference=True,
            description="Module export relationship"
        ),
        InternalRelationshipType.EXPORTED_BY: RelationshipMapping(
            scip_is_reference=True,
            description="Reverse export relationship"
        ),
        
        # 包含關係 - 使用 is_reference
        InternalRelationshipType.CONTAINS: RelationshipMapping(
            scip_is_reference=True,
            description="Containment relationship"
        ),
        InternalRelationshipType.CONTAINED_BY: RelationshipMapping(
            scip_is_reference=True,
            description="Reverse containment relationship"
        ),
        
        # 重寫關係 - 使用 is_implementation
        InternalRelationshipType.OVERRIDES: RelationshipMapping(
            scip_is_implementation=True,
            description="Method override relationship"
        ),
        InternalRelationshipType.OVERRIDDEN_BY: RelationshipMapping(
            scip_is_implementation=True,
            description="Reverse override relationship"
        ),
    }
    
    def __init__(self):
        """初始化關係映射器"""
        self.custom_mappings: Dict[str, RelationshipMapping] = {}
        logger.debug("SCIPRelationshipMapper initialized")
    
    def map_to_scip_relationship(self, 
                                target_symbol: str, 
                                relationship_type: InternalRelationshipType) -> scip_pb2.Relationship:
        """
        將內部關係類型映射為 SCIP Relationship 對象
        
        Args:
            target_symbol: 目標符號 ID
            relationship_type: 內部關係類型
            
        Returns:
            SCIP Relationship 對象
            
        Raises:
            ValueError: 如果關係類型不支援
        """
        if relationship_type not in self.RELATIONSHIP_MAPPINGS:
            raise ValueError(f"Unsupported relationship type: {relationship_type}")
        
        mapping = self.RELATIONSHIP_MAPPINGS[relationship_type]
        
        relationship = scip_pb2.Relationship()
        relationship.symbol = target_symbol
        relationship.is_reference = mapping.scip_is_reference
        relationship.is_implementation = mapping.scip_is_implementation
        relationship.is_type_definition = mapping.scip_is_type_definition
        relationship.is_definition = mapping.scip_is_definition
        
        logger.debug(f"Mapped {relationship_type.value} -> SCIP relationship for {target_symbol}")
        return relationship
    
    def batch_map_relationships(self, 
                              relationships: List[tuple]) -> List[scip_pb2.Relationship]:
        """
        批量映射關係
        
        Args:
            relationships: (target_symbol, relationship_type) 元組列表
            
        Returns:
            SCIP Relationship 對象列表
        """
        scip_relationships = []
        
        for target_symbol, relationship_type in relationships:
            try:
                scip_rel = self.map_to_scip_relationship(target_symbol, relationship_type)
                scip_relationships.append(scip_rel)
            except ValueError as e:
                logger.warning(f"Failed to map relationship: {e}")
                continue
        
        logger.debug(f"Batch mapped {len(scip_relationships)} relationships")
        return scip_relationships
    
    def validate_relationship_type(self, relationship_type: str) -> bool:
        """
        驗證關係類型是否支援
        
        Args:
            relationship_type: 關係類型字符串
            
        Returns:
            是否支援
        """
        try:
            InternalRelationshipType(relationship_type)
            return True
        except ValueError:
            return relationship_type in self.custom_mappings
    
    def get_supported_relationship_types(self) -> List[str]:
        """
        獲取所有支援的關係類型
        
        Returns:
            關係類型字符串列表
        """
        builtin_types = [rt.value for rt in InternalRelationshipType]
        custom_types = list(self.custom_mappings.keys())
        return builtin_types + custom_types
    
    def get_relationship_description(self, relationship_type: InternalRelationshipType) -> str:
        """
        獲取關係類型的描述
        
        Args:
            relationship_type: 關係類型
            
        Returns:
            描述字符串
        """
        mapping = self.RELATIONSHIP_MAPPINGS.get(relationship_type)
        return mapping.description if mapping else "Unknown relationship"
    
    def add_custom_mapping(self, 
                          relationship_type: str, 
                          mapping: RelationshipMapping) -> None:
        """
        添加自定義關係映射
        
        Args:
            relationship_type: 自定義關係類型名稱
            mapping: 關係映射配置
        """
        self.custom_mappings[relationship_type] = mapping
        logger.debug(f"Added custom relationship mapping: {relationship_type}")
    
    def get_reverse_relationship(self, relationship_type: InternalRelationshipType) -> Optional[InternalRelationshipType]:
        """
        獲取關係的反向關係
        
        Args:
            relationship_type: 關係類型
            
        Returns:
            反向關係類型或 None
        """
        reverse_mappings = {
            InternalRelationshipType.CALLS: InternalRelationshipType.CALLED_BY,
            InternalRelationshipType.CALLED_BY: InternalRelationshipType.CALLS,
            InternalRelationshipType.INHERITS: InternalRelationshipType.INHERITED_BY,
            InternalRelationshipType.INHERITED_BY: InternalRelationshipType.INHERITS,
            InternalRelationshipType.IMPLEMENTS: InternalRelationshipType.IMPLEMENTED_BY,
            InternalRelationshipType.IMPLEMENTED_BY: InternalRelationshipType.IMPLEMENTS,
            InternalRelationshipType.DEFINES: InternalRelationshipType.DEFINED_BY,
            InternalRelationshipType.DEFINED_BY: InternalRelationshipType.DEFINES,
            InternalRelationshipType.REFERENCES: InternalRelationshipType.REFERENCED_BY,
            InternalRelationshipType.REFERENCED_BY: InternalRelationshipType.REFERENCES,
            InternalRelationshipType.TYPE_OF: InternalRelationshipType.HAS_TYPE,
            InternalRelationshipType.HAS_TYPE: InternalRelationshipType.TYPE_OF,
            InternalRelationshipType.IMPORTS: InternalRelationshipType.IMPORTED_BY,
            InternalRelationshipType.IMPORTED_BY: InternalRelationshipType.IMPORTS,
            InternalRelationshipType.EXPORTS: InternalRelationshipType.EXPORTED_BY,
            InternalRelationshipType.EXPORTED_BY: InternalRelationshipType.EXPORTS,
            InternalRelationshipType.CONTAINS: InternalRelationshipType.CONTAINED_BY,
            InternalRelationshipType.CONTAINED_BY: InternalRelationshipType.CONTAINS,
            InternalRelationshipType.OVERRIDES: InternalRelationshipType.OVERRIDDEN_BY,
            InternalRelationshipType.OVERRIDDEN_BY: InternalRelationshipType.OVERRIDES,
        }
        
        return reverse_mappings.get(relationship_type)
    
    def is_directional_relationship(self, relationship_type: InternalRelationshipType) -> bool:
        """
        檢查關係是否是有向的
        
        Args:
            relationship_type: 關係類型
            
        Returns:
            是否有向
        """
        # 大多數關係都是有向的
        non_directional = {
            # 可以在這裡添加非有向關係類型
        }
        return relationship_type not in non_directional
    
    def group_relationships_by_type(self, 
                                  relationships: List[scip_pb2.Relationship]) -> Dict[str, List[scip_pb2.Relationship]]:
        """
        按關係的 SCIP 標誌分組
        
        Args:
            relationships: SCIP 關係列表
            
        Returns:
            按類型分組的關係字典
        """
        groups = {
            'references': [],
            'implementations': [],
            'type_definitions': [],
            'definitions': []
        }
        
        for rel in relationships:
            if rel.is_reference:
                groups['references'].append(rel)
            if rel.is_implementation:
                groups['implementations'].append(rel)
            if rel.is_type_definition:
                groups['type_definitions'].append(rel)
            if rel.is_definition:
                groups['definitions'].append(rel)
        
        return groups
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        獲取映射器統計信息
        
        Returns:
            統計信息字典
        """
        return {
            'builtin_relationship_types': len(InternalRelationshipType),
            'custom_relationship_types': len(self.custom_mappings),
            'total_supported_types': len(InternalRelationshipType) + len(self.custom_mappings)
        }


class RelationshipTypeError(Exception):
    """關係類型相關錯誤"""
    pass


class UnsupportedRelationshipError(RelationshipTypeError):
    """不支援的關係類型錯誤"""
    pass