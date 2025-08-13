"""
统一索引管理器 - 提供项目索引的统一访问接口

这个模块实现了一个中央化的索引管理器，统一处理所有索引相关操作，
包括SCIP索引、遗留索引格式的兼容，以及内存缓存管理。
"""

import os
import logging
import time
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from .index_provider import IIndexProvider, IIndexManager, IndexMetadata, SymbolInfo, FileInfo
from ..project_settings import ProjectSettings

# Try to import SCIP proto, handle if not available
try:
    from ..scip.proto.scip_pb2 import Index as SCIPIndex, Document as SCIPDocument
    SCIP_PROTO_AVAILABLE = True
except ImportError:
    SCIPIndex = None
    SCIPDocument = None
    SCIP_PROTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class UnifiedIndexManager:
    """
    统一索引管理器
    
    负责协调不同索引格式，提供统一的访问接口，
    并处理索引的生命周期管理。
    """
    
    def __init__(self, project_path: str, settings: Optional[ProjectSettings] = None):
        self.project_path = project_path
        self.settings = settings or ProjectSettings(project_path)
        
        # 核心组件 - 延迟导入避免循环依赖
        self._scip_tool = None
        self._current_provider: Optional[IIndexProvider] = None
        self._metadata: Optional[IndexMetadata] = None
        
        # 状态管理
        self._is_initialized = False
        self._last_check_time = 0
        self._check_interval = 30  # 30秒检查间隔
    
    def _get_scip_tool(self):
        """延迟导入SCIP工具以避免循环依赖"""
        if self._scip_tool is None:
            from ..tools.scip.scip_index_tool import SCIPIndexTool
            self._scip_tool = SCIPIndexTool()
        return self._scip_tool
        
    def initialize(self) -> bool:
        """
        初始化索引管理器
        
        Returns:
            True if initialization successful
        """
        try:
            # 1. 尝试加载现有索引
            if self._load_existing_index():
                logger.info("Successfully loaded existing index")
                self._is_initialized = True
                return True
            
            # 2. 如果没有现有索引，构建新索引
            if self._build_new_index():
                logger.info("Successfully built new index")
                self._is_initialized = True
                return True
            
            logger.warning("Failed to initialize index")
            return False
            
        except Exception as e:
            logger.error(f"Index initialization failed: {e}")
            return False
    
    def get_provider(self) -> Optional[IIndexProvider]:
        """
        获取当前索引提供者
        
        Returns:
            当前活跃的索引提供者，如果索引不可用则返回None
        """
        if not self._is_initialized:
            self.initialize()
        
        # 定期检查索引状态
        current_time = time.time()
        if current_time - self._last_check_time > self._check_interval:
            self._check_index_health()
            self._last_check_time = current_time
        
        return self._current_provider
    
    def refresh_index(self, force: bool = False) -> bool:
        """
        刷新索引
        
        Args:
            force: 是否强制重建索引
            
        Returns:
            True if refresh successful
        """
        try:
            if force or self._needs_rebuild():
                return self._build_new_index()
            else:
                # 尝试增量更新
                return self._incremental_update()
        except Exception as e:
            logger.error(f"Index refresh failed: {e}")
            return False
    
    def save_index(self) -> bool:
        """
        保存当前索引状态
        
        Returns:
            True if save successful
        """
        try:
            if self._current_provider and isinstance(self._current_provider, SCIPIndexProvider):
                return self._get_scip_tool().save_index()
            return False
        except Exception as e:
            logger.error(f"Index save failed: {e}")
            return False
    
    def clear_index(self) -> None:
        """清理索引状态"""
        try:
            if self._scip_tool:
                self._scip_tool.clear_index()
            self._current_provider = None
            self._metadata = None
            self._is_initialized = False
            logger.info("Index cleared successfully")
        except Exception as e:
            logger.error(f"Index clear failed: {e}")
    
    def get_index_status(self) -> Dict[str, Any]:
        """
        获取索引状态信息
        
        Returns:
            包含索引状态的字典
        """
        status = {
            'is_initialized': self._is_initialized,
            'is_available': self._current_provider is not None,
            'provider_type': type(self._current_provider).__name__ if self._current_provider else None,
            'metadata': self._metadata.__dict__ if self._metadata else None,
            'last_check': self._last_check_time
        }
        
        if self._current_provider:
            status['file_count'] = len(self._current_provider.get_file_list())
        
        return status
    
    def _load_existing_index(self) -> bool:
        """尝试加载现有索引"""
        try:
            # 1. 尝试SCIP索引
            scip_tool = self._get_scip_tool()
            if scip_tool.load_existing_index(self.project_path):
                self._current_provider = SCIPIndexProvider(scip_tool)
                self._metadata = self._create_metadata_from_scip()
                logger.info("Loaded SCIP index")
                return True
            
            # 2. 尝试遗留索引（如果需要兼容）
            legacy_data = self.settings.load_existing_index()
            if legacy_data and self._is_valid_legacy_index(legacy_data):
                self._current_provider = LegacyIndexProvider(legacy_data)
                self._metadata = self._create_metadata_from_legacy(legacy_data)
                logger.info("Loaded legacy index")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to load existing index: {e}")
            return False
    
    def _build_new_index(self) -> bool:
        """构建新索引"""
        try:
            scip_tool = self._get_scip_tool()
            file_count = scip_tool.build_index(self.project_path)
            if file_count > 0:
                self._current_provider = SCIPIndexProvider(scip_tool)
                self._metadata = self._create_metadata_from_scip()
                
                # 保存索引
                scip_tool.save_index()
                
                logger.info(f"Built new SCIP index with {file_count} files")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to build new index: {e}")
            return False
    
    def _check_index_health(self) -> None:
        """检查索引健康状态"""
        if self._current_provider and not self._current_provider.is_available():
            logger.warning("Index provider became unavailable, attempting recovery")
            self.initialize()
    
    def _needs_rebuild(self) -> bool:
        """检查是否需要重建索引"""
        if not self._metadata:
            return True
        
        # 检查项目文件是否有更新
        try:
            latest_mtime = 0
            for root, _, files in os.walk(self.project_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    mtime = os.path.getmtime(file_path)
                    latest_mtime = max(latest_mtime, mtime)
            
            return latest_mtime > self._metadata.last_updated
            
        except Exception:
            return True  # 如果检查失败，保守地重建
    
    def _incremental_update(self) -> bool:
        """增量更新索引（如果支持）"""
        # 目前简化为完全重建
        # 在未来版本中可以实现真正的增量更新
        return self._build_new_index()
    
    def _create_metadata_from_scip(self) -> IndexMetadata:
        """从SCIP索引创建元数据"""
        scip_tool = self._get_scip_tool()
        metadata_dict = scip_tool.get_project_metadata()
        return IndexMetadata(
            version="4.0-scip",
            format_type="scip",
            created_at=time.time(),
            last_updated=time.time(),
            file_count=metadata_dict.get('total_files', 0),
            project_root=metadata_dict.get('project_root', self.project_path),
            tool_version=metadata_dict.get('tool_version', 'unknown')
        )
    
    def _create_metadata_from_legacy(self, legacy_data: Dict[str, Any]) -> IndexMetadata:
        """从遗留索引创建元数据"""
        return IndexMetadata(
            version="3.0-legacy",
            format_type="legacy",
            created_at=legacy_data.get('created_at', time.time()),
            last_updated=legacy_data.get('last_updated', time.time()),
            file_count=legacy_data.get('project_metadata', {}).get('total_files', 0),
            project_root=self.project_path,
            tool_version="legacy"
        )
    
    def _is_valid_legacy_index(self, index_data: Dict[str, Any]) -> bool:
        """验证遗留索引是否有效"""
        return (
            isinstance(index_data, dict) and
            'index_metadata' in index_data and
            index_data.get('index_metadata', {}).get('version', '') >= '3.0'
        )


class SCIPIndexProvider:
    """SCIP索引提供者实现"""
    
    def __init__(self, scip_tool):
        self._scip_tool = scip_tool
    
    def get_file_list(self) -> List[FileInfo]:
        return self._scip_tool.get_file_list()
    
    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        file_list = self.get_file_list()
        for file_info in file_list:
            if file_info.relative_path == file_path:
                return file_info
        return None
    
    def query_symbols(self, file_path: str) -> List[SymbolInfo]:
        # This method is deprecated - use CodeIntelligenceService for symbol analysis
        return []
    
    def search_files(self, pattern: str) -> List[FileInfo]:
        # 延迟导入避免循环依赖
        from ..tools.filesystem.file_matching_tool import FileMatchingTool
        matcher = FileMatchingTool()
        return matcher.match_glob_pattern(self.get_file_list(), pattern)
    
    def get_metadata(self) -> IndexMetadata:
        metadata_dict = self._scip_tool.get_project_metadata()
        return IndexMetadata(
            version="4.0-scip",
            format_type="scip",
            created_at=time.time(),
            last_updated=time.time(),
            file_count=metadata_dict.get('total_files', 0),
            project_root=metadata_dict.get('project_root', ''),
            tool_version=metadata_dict.get('tool_version', 'unknown')
        )
    
    def is_available(self) -> bool:
        return self._scip_tool.is_index_available()


class LegacyIndexProvider:
    """遗留索引提供者实现（兼容性支持）"""
    
    def __init__(self, legacy_data: Dict[str, Any]):
        self._data = legacy_data
    
    def get_file_list(self) -> List[FileInfo]:
        # 从遗留数据转换为标准格式
        files = []
        file_dict = self._data.get('files', {})
        
        for file_path, file_data in file_dict.items():
            file_info = FileInfo(
                relative_path=file_path,
                language=file_data.get('language', 'unknown'),
                absolute_path=file_data.get('absolute_path', '')
            )
            files.append(file_info)
        
        return files
    
    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        file_dict = self._data.get('files', {})
        if file_path in file_dict:
            file_data = file_dict[file_path]
            return FileInfo(
                relative_path=file_path,
                language=file_data.get('language', 'unknown'),
                absolute_path=file_data.get('absolute_path', '')
            )
        return None
    
    def query_symbols(self, file_path: str) -> List[SymbolInfo]:
        # 遗留格式的符号信息有限，转换为标准格式
        file_dict = self._data.get('files', {})
        if file_path in file_dict:
            legacy_symbols = file_dict[file_path].get('symbols', [])
            symbols = []
            for symbol_data in legacy_symbols:
                if isinstance(symbol_data, dict):
                    symbol = SymbolInfo(
                        name=symbol_data.get('name', ''),
                        kind=symbol_data.get('kind', 'unknown'),
                        location=symbol_data.get('location', {'line': 1, 'column': 1}),
                        scope=symbol_data.get('scope', 'global'),
                        documentation=symbol_data.get('documentation', [])
                    )
                    symbols.append(symbol)
            return symbols
        return []
    
    def search_files(self, pattern: str) -> List[FileInfo]:
        import fnmatch
        matched_files = []
        
        for file_info in self.get_file_list():
            if fnmatch.fnmatch(file_info.relative_path, pattern):
                matched_files.append(file_info)
        
        return matched_files
    
    def get_metadata(self) -> IndexMetadata:
        meta = self._data.get('index_metadata', {})
        return IndexMetadata(
            version=meta.get('version', '3.0-legacy'),
            format_type="legacy",
            created_at=meta.get('created_at', time.time()),
            last_updated=meta.get('last_updated', time.time()),
            file_count=len(self._data.get('files', {})),
            project_root=meta.get('project_root', ''),
            tool_version="legacy"
        )
    
    def is_available(self) -> bool:
        return bool(self._data.get('files'))


# 全局索引管理器实例
_global_index_manager: Optional[UnifiedIndexManager] = None


def get_unified_index_manager(project_path: str = None, settings: ProjectSettings = None) -> UnifiedIndexManager:
    """
    获取全局统一索引管理器实例
    
    Args:
        project_path: 项目路径（首次初始化时需要）
        settings: 项目设置（可选）
    
    Returns:
        UnifiedIndexManager实例
    """
    global _global_index_manager
    
    if _global_index_manager is None and project_path:
        _global_index_manager = UnifiedIndexManager(project_path, settings)
    
    if _global_index_manager and project_path and _global_index_manager.project_path != project_path:
        # 项目路径改变，重新创建管理器
        _global_index_manager = UnifiedIndexManager(project_path, settings)
    
    return _global_index_manager


def clear_global_index_manager() -> None:
    """清理全局索引管理器"""
    global _global_index_manager
    if _global_index_manager:
        _global_index_manager.clear_index()
        _global_index_manager = None
