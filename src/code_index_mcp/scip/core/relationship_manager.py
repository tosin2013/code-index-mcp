"""SCIP 關係管理器 - 負責將內部關係轉換為標準 SCIP Relationship"""

import logging
from typing import List, Dict, Optional, Any, Set
from enum import Enum

from ..proto import scip_pb2

logger = logging.getLogger(__name__)


class RelationshipType(Enum):
    """內部關係類型定義"""
    CALLS = "calls"                    # 函數調用關係
    CALLED_BY = "called_by"            # 被調用關係
    INHERITS = "inherits"              # 繼承關係  
    IMPLEMENTS = "implements"          # 實現關係
    REFERENCES = "references"          # 引用關係
    TYPE_DEFINITION = "type_definition" # 類型定義關係
    DEFINITION = "definition"          # 定義關係


class SCIPRelationshipManager:
    """
    SCIP 關係轉換和管理核心
    
    負責將內部關係格式轉換為標準 SCIP Relationship 對象，
    並管理符號間的各種關係類型。
    """
    
    def __init__(self):
        """初始化關係管理器"""
        self.relationship_cache: Dict[str, List[scip_pb2.Relationship]] = {}
        self.symbol_relationships: Dict[str, Set[str]] = {}
        
        logger.debug("SCIPRelationshipManager initialized")
    
    def create_relationship(self, 
                          target_symbol: str, 
                          relationship_type: RelationshipType) -> scip_pb2.Relationship:
        """
        創建標準 SCIP Relationship 對象
        
        Args:
            target_symbol: 目標符號的 SCIP 符號 ID
            relationship_type: 關係類型
            
        Returns:
            SCIP Relationship 對象
        """
        relationship = scip_pb2.Relationship()
        relationship.symbol = target_symbol
        
        # 根據關係類型設置相應的布爾標誌
        if relationship_type == RelationshipType.REFERENCES:
            relationship.is_reference = True
        elif relationship_type == RelationshipType.IMPLEMENTS:
            relationship.is_implementation = True
        elif relationship_type == RelationshipType.TYPE_DEFINITION:
            relationship.is_type_definition = True
        elif relationship_type == RelationshipType.DEFINITION:
            relationship.is_definition = True
        else:
            # 對於 CALLS, CALLED_BY, INHERITS 等關係，使用 is_reference
            # 這些關係在 SCIP 標準中主要通過 is_reference 表示
            relationship.is_reference = True
        
        logger.debug(f"Created SCIP relationship: {target_symbol} ({relationship_type.value})")
        return relationship
    
    def add_relationships_to_symbol(self, 
                                  symbol_info: scip_pb2.SymbolInformation, 
                                  relationships: List[scip_pb2.Relationship]) -> None:
        """
        將關係列表添加到 SCIP 符號信息中
        
        Args:
            symbol_info: SCIP 符號信息對象
            relationships: 要添加的關係列表
        """
        if not relationships:
            return
            
        # 清除現有關係（如果有的話）
        del symbol_info.relationships[:]
        
        # 添加新關係
        symbol_info.relationships.extend(relationships)
        
        logger.debug(f"Added {len(relationships)} relationships to symbol {symbol_info.symbol}")
    
    def convert_call_relationships(self, 
                                 call_relationships: Any, 
                                 symbol_manager: Any) -> List[scip_pb2.Relationship]:
        """
        將內部 CallRelationships 轉換為 SCIP Relationship 列表
        
        Args:
            call_relationships: 內部 CallRelationships 對象
            symbol_manager: 符號管理器，用於生成符號 ID
            
        Returns:
            SCIP Relationship 對象列表
        """
        relationships = []
        
        # 處理本地調用關係
        if hasattr(call_relationships, 'local') and call_relationships.local:
            for function_name in call_relationships.local:
                # 嘗試生成目標符號 ID
                target_symbol_id = self._generate_local_symbol_id(
                    function_name, symbol_manager
                )
                if target_symbol_id:
                    relationship = self.create_relationship(
                        target_symbol_id, RelationshipType.CALLS
                    )
                    relationships.append(relationship)
        
        # 處理外部調用關係
        if hasattr(call_relationships, 'external') and call_relationships.external:
            for call_info in call_relationships.external:
                if isinstance(call_info, dict) and 'name' in call_info:
                    # 為外部調用生成符號 ID
                    target_symbol_id = self._generate_external_symbol_id(
                        call_info, symbol_manager
                    )
                    if target_symbol_id:
                        relationship = self.create_relationship(
                            target_symbol_id, RelationshipType.CALLS
                        )
                        relationships.append(relationship)
        
        logger.debug(f"Converted call relationships: {len(relationships)} relationships")
        return relationships
    
    def add_inheritance_relationship(self, 
                                   child_symbol_id: str, 
                                   parent_symbol_id: str) -> scip_pb2.Relationship:
        """
        添加繼承關係
        
        Args:
            child_symbol_id: 子類符號 ID
            parent_symbol_id: 父類符號 ID
            
        Returns:
            SCIP Relationship 對象
        """
        relationship = self.create_relationship(parent_symbol_id, RelationshipType.INHERITS)
        
        # 記錄關係到緩存
        if child_symbol_id not in self.symbol_relationships:
            self.symbol_relationships[child_symbol_id] = set()
        self.symbol_relationships[child_symbol_id].add(parent_symbol_id)
        
        logger.debug(f"Added inheritance: {child_symbol_id} -> {parent_symbol_id}")
        return relationship
    
    def add_implementation_relationship(self, 
                                      implementer_symbol_id: str, 
                                      interface_symbol_id: str) -> scip_pb2.Relationship:
        """
        添加實現關係（介面實現）
        
        Args:
            implementer_symbol_id: 實現者符號 ID
            interface_symbol_id: 介面符號 ID
            
        Returns:
            SCIP Relationship 對象
        """
        relationship = self.create_relationship(interface_symbol_id, RelationshipType.IMPLEMENTS)
        
        # 記錄關係到緩存
        if implementer_symbol_id not in self.symbol_relationships:
            self.symbol_relationships[implementer_symbol_id] = set()
        self.symbol_relationships[implementer_symbol_id].add(interface_symbol_id)
        
        logger.debug(f"Added implementation: {implementer_symbol_id} -> {interface_symbol_id}")
        return relationship
    
    def get_symbol_relationships(self, symbol_id: str) -> List[scip_pb2.Relationship]:
        """
        獲取符號的所有關係
        
        Args:
            symbol_id: 符號 ID
            
        Returns:
            關係列表
        """
        if symbol_id in self.relationship_cache:
            return self.relationship_cache[symbol_id]
        return []
    
    def cache_relationships(self, symbol_id: str, relationships: List[scip_pb2.Relationship]) -> None:
        """
        緩存符號的關係
        
        Args:
            symbol_id: 符號 ID
            relationships: 關係列表
        """
        self.relationship_cache[symbol_id] = relationships
        logger.debug(f"Cached {len(relationships)} relationships for {symbol_id}")
    
    def clear_cache(self) -> None:
        """清除關係緩存"""
        self.relationship_cache.clear()
        self.symbol_relationships.clear()
        logger.debug("Relationship cache cleared")
    
    def get_statistics(self) -> Dict[str, int]:
        """
        獲取關係統計信息
        
        Returns:
            統計信息字典
        """
        total_relationships = sum(len(rels) for rels in self.relationship_cache.values())
        return {
            'symbols_with_relationships': len(self.relationship_cache),
            'total_relationships': total_relationships,
            'cached_symbol_connections': len(self.symbol_relationships)
        }
    
    def _generate_local_symbol_id(self, function_name: str, symbol_manager: Any) -> Optional[str]:
        """
        為本地函數生成符號 ID
        
        Args:
            function_name: 函數名稱
            symbol_manager: 符號管理器
            
        Returns:
            符號 ID 或 None
        """
        try:
            if hasattr(symbol_manager, 'create_local_symbol'):
                # 假設這是一個本地符號，使用基本路徑
                return symbol_manager.create_local_symbol(
                    language="unknown",  # 將在具體策略中設置正確的語言
                    file_path="",        # 將在具體策略中設置正確的文件路徑
                    symbol_path=[function_name],
                    descriptor="()."     # 函數描述符
                )
        except Exception as e:
            logger.warning(f"Failed to generate local symbol ID for {function_name}: {e}")
        return None
    
    def _generate_external_symbol_id(self, call_info: Dict[str, Any], symbol_manager: Any) -> Optional[str]:
        """
        為外部調用生成符號 ID
        
        Args:
            call_info: 外部調用信息
            symbol_manager: 符號管理器
            
        Returns:
            符號 ID 或 None
        """
        try:
            function_name = call_info.get('name', '')
            file_path = call_info.get('file', '')
            
            if function_name and hasattr(symbol_manager, 'create_local_symbol'):
                return symbol_manager.create_local_symbol(
                    language="unknown",  # 將在具體策略中設置正確的語言
                    file_path=file_path,
                    symbol_path=[function_name],
                    descriptor="()."     # 函數描述符
                )
        except Exception as e:
            logger.warning(f"Failed to generate external symbol ID for {call_info}: {e}")
        return None


class RelationshipError(Exception):
    """關係處理相關錯誤"""
    pass


class RelationshipConversionError(RelationshipError):
    """關係轉換錯誤"""
    pass