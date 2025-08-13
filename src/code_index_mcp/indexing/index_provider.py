"""
索引提供者接口定义

定义所有索引访问的标准接口，确保不同实现的一致性。
"""

from typing import List, Optional, Dict, Any, Protocol
from dataclasses import dataclass


@dataclass
class SymbolInfo:
    """符号信息标准数据结构"""
    name: str
    kind: str  # 'class', 'function', 'method', 'variable', etc.
    location: Dict[str, int]  # {'line': int, 'column': int}
    scope: str
    documentation: List[str]


# Define FileInfo here to avoid circular imports
@dataclass
class FileInfo:
    """文件信息标准数据结构"""
    relative_path: str
    language: str
    absolute_path: str
    
    def __hash__(self):
        return hash(self.relative_path)
    
    def __eq__(self, other):
        if isinstance(other, FileInfo):
            return self.relative_path == other.relative_path
        return False


@dataclass
class IndexMetadata:
    """索引元数据标准结构"""
    version: str
    format_type: str
    created_at: float
    last_updated: float
    file_count: int
    project_root: str
    tool_version: str


class IIndexProvider(Protocol):
    """
    索引提供者标准接口
    
    所有索引实现都必须遵循这个接口，确保一致的访问方式。
    """
    
    def get_file_list(self) -> List[FileInfo]:
        """
        获取所有索引文件列表
        
        Returns:
            文件信息列表
        """
        ...
    
    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """
        获取特定文件信息
        
        Args:
            file_path: 文件相对路径
            
        Returns:
            文件信息，如果文件不在索引中则返回None
        """
        ...
    
    def query_symbols(self, file_path: str) -> List[SymbolInfo]:
        """
        查询文件中的符号信息
        
        Args:
            file_path: 文件相对路径
            
        Returns:
            符号信息列表
        """
        ...
    
    def search_files(self, pattern: str) -> List[FileInfo]:
        """
        按模式搜索文件
        
        Args:
            pattern: glob模式或正则表达式
            
        Returns:
            匹配的文件列表
        """
        ...
    
    def get_metadata(self) -> IndexMetadata:
        """
        获取索引元数据
        
        Returns:
            索引元数据信息
        """
        ...
    
    def is_available(self) -> bool:
        """
        检查索引是否可用
        
        Returns:
            True if index is available and functional
        """
        ...


class IIndexManager(Protocol):
    """
    索引管理器接口
    
    定义索引生命周期管理的标准接口。
    """
    
    def initialize(self) -> bool:
        """初始化索引管理器"""
        ...
    
    def get_provider(self) -> Optional[IIndexProvider]:
        """获取当前活跃的索引提供者"""
        ...
    
    def refresh_index(self, force: bool = False) -> bool:
        """刷新索引"""
        ...
    
    def save_index(self) -> bool:
        """保存索引状态"""
        ...
    
    def clear_index(self) -> None:
        """清理索引状态"""
        ...
    
    def get_index_status(self) -> Dict[str, Any]:
        """获取索引状态信息"""
        ...
