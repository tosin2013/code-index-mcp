# SCIP 關係圖實施計畫

**版本**: 1.0  
**日期**: 2025-01-14  
**狀態**: 規劃階段  

## 📋 問題分析

### 當前狀況
- ✅ SCIP Protocol Buffer 結構完整實現
- ✅ 符號定義和出現位置正確處理
- ❌ **關鍵缺失**: SCIP Relationship 功能完全未實現
- ❌ 內部 `CallRelationships` 與標準 SCIP `Relationship` 完全分離

### 影響評估
- **合規性**: 目前僅 60-70% 符合 SCIP 標準
- **功能性**: 關係圖和跨符號導航功能不可用
- **兼容性**: 無法與標準 SCIP 工具鏈集成

## 🎯 目標

### 主要目標
1. **100% SCIP 標準合規性**: 完整實現 `scip_pb2.Relationship` 支援
2. **關係圖功能**: 啟用函數調用、繼承、實現等關係追蹤
3. **多語言支援**: 6 種程式語言的關係提取
4. **向後兼容**: 不破壞現有功能

### 成功指標
- ✅ 所有符號包含正確的 SCIP Relationship 信息
- ✅ 通過官方 SCIP 驗證工具檢查
- ✅ 關係查詢 API 正常運作
- ✅ 性能影響 < 20%

## 🏗️ 技術架構

### 當前架構問題
```
[CallRelationships (內部格式)] ❌ 斷層 ❌ [SCIP Relationship (標準格式)]
```

### 目標架構
```
[程式碼分析] → [關係提取] → [關係管理器] → [SCIP Relationship] → [SymbolInformation]
```

### 核心組件

#### 1. 關係管理器 (`relationship_manager.py`)
```python
class SCIPRelationshipManager:
    """SCIP 關係轉換和管理核心"""
    
    def create_relationship(self, target_symbol: str, relationship_type: RelationshipType) -> scip_pb2.Relationship
    def add_relationships_to_symbol(self, symbol_info: scip_pb2.SymbolInformation, relationships: List[Relationship])
    def convert_call_relationships(self, call_rels: CallRelationships) -> List[scip_pb2.Relationship]
```

#### 2. 關係類型定義 (`relationship_types.py`)
```python
class RelationshipType(Enum):
    CALLS = "calls"                    # 函數調用關係
    INHERITS = "inherits"              # 繼承關係  
    IMPLEMENTS = "implements"          # 實現關係
    REFERENCES = "references"          # 引用關係
    TYPE_DEFINITION = "type_definition" # 類型定義關係
```

## 📁 檔案修改計畫

### 🆕 新增檔案 (4個)

#### 核心組件
```
src/code_index_mcp/scip/core/
├── relationship_manager.py      # 關係轉換核心 (優先級 1)
└── relationship_types.py        # 關係類型定義 (優先級 1)
```

#### 測試檔案
```
tests/
├── scip/test_relationship_manager.py        # 單元測試 (優先級 3)
└── integration/test_scip_relationships.py   # 整合測試 (優先級 3)
```

### 🔄 修改現有檔案 (9個)

#### 核心系統
```
src/code_index_mcp/scip/core/
└── local_reference_resolver.py  # 關係存儲和查詢 (優先級 1)
```

#### 策略層
```
src/code_index_mcp/scip/strategies/
├── base_strategy.py             # 基礎關係處理 (優先級 1)
├── python_strategy.py           # Python 關係提取 (優先級 2)  
├── javascript_strategy.py       # JavaScript 關係提取 (優先級 2)
├── java_strategy.py             # Java 關係提取 (優先級 2)
├── objective_c_strategy.py      # Objective-C 關係提取 (優先級 2)
├── zig_strategy.py              # Zig 關係提取 (優先級 2)
└── fallback_strategy.py         # 後備關係處理 (優先級 2)
```

#### 分析工具
```
src/code_index_mcp/tools/scip/
├── symbol_definitions.py        # 關係數據結構增強 (優先級 2)
└── scip_symbol_analyzer.py      # 關係分析整合 (優先級 2)
```

## 🗓️ 實施時程

### 階段 1：核心基礎 (第1-2週) - 優先級 1
- [ ] **Week 1.1**: 創建 `relationship_manager.py`
  - SCIP Relationship 創建和轉換邏輯
  - 關係類型映射功能
  - 基礎 API 設計

- [ ] **Week 1.2**: 創建 `relationship_types.py`
  - 內部關係類型枚舉定義
  - SCIP 標準關係映射
  - 關係驗證邏輯

- [ ] **Week 2.1**: 修改 `base_strategy.py`
  - 新增 `_create_scip_relationships` 方法
  - 修改 `_create_scip_symbol_information` 加入關係處理
  - 新增抽象方法 `_build_symbol_relationships`

- [ ] **Week 2.2**: 更新 `local_reference_resolver.py`
  - 新增關係存儲功能
  - 實現 `add_symbol_relationship` 方法
  - 實現 `get_symbol_relationships` 方法

### 階段 2：語言實現 (第3-4週) - 優先級 2

#### Week 3: 主要語言策略
- [ ] **Week 3.1**: Python 策略 (`python_strategy.py`)
  - 函數調用關係提取
  - 類繼承關係檢測
  - 方法重寫關係處理

- [ ] **Week 3.2**: JavaScript 策略 (`javascript_strategy.py`)
  - 函數調用和原型鏈關係
  - ES6 類繼承關係
  - 模組導入關係

#### Week 4: 其他語言策略
- [ ] **Week 4.1**: Java 策略 (`java_strategy.py`)
  - 類繼承和介面實現關係
  - 方法調用關係
  - 包導入關係

- [ ] **Week 4.2**: Objective-C 和 Zig 策略
  - Objective-C 協議和繼承關係
  - Zig 結構體和函數關係
  - 後備策略更新

- [ ] **Week 4.3**: 工具層更新
  - 更新 `symbol_definitions.py`
  - 整合 `scip_symbol_analyzer.py`

### 階段 3：測試驗證 (第5週) - 優先級 3
- [ ] **Week 5.1**: 單元測試
  - 關係管理器測試
  - 關係類型轉換測試
  - 各語言策略關係提取測試

- [ ] **Week 5.2**: 整合測試
  - 端到端關係功能測試
  - 多語言項目關係測試
  - 性能回歸測試

- [ ] **Week 5.3**: SCIP 合規性驗證
  - 使用官方 SCIP 工具驗證
  - 關係格式正確性檢查
  - 兼容性測試

### 階段 4：優化完善 (第6週) - 優先級 4
- [ ] **Week 6.1**: 性能優化
  - 關係查詢 API 優化
  - 記憶體使用優化
  - 大型項目支援測試

- [ ] **Week 6.2**: 文檔和工具
  - 更新 ARCHITECTURE.md
  - 更新 API 文檔
  - 使用範例和指南

- [ ] **Week 6.3**: 發布準備
  - 版本號更新
  - 變更日誌準備
  - 向後兼容性最終檢查

## 🧪 測試策略

### 單元測試範圍
```python
# test_relationship_manager.py
def test_create_scip_relationship()
def test_convert_call_relationships()
def test_relationship_type_mapping()

# test_python_relationships.py  
def test_function_call_extraction()
def test_class_inheritance_detection()
def test_method_override_relationships()
```

### 整合測試範圍
```python
# test_scip_relationships.py
def test_end_to_end_relationship_flow()
def test_multi_language_relationship_support()
def test_cross_file_relationship_resolution()
def test_scip_compliance_validation()
```

### 測試數據
- 使用現有 `test/sample-projects/` 中的範例項目
- 新增特定關係測試案例
- 包含邊界情況和錯誤處理測試

## 📊 風險評估與緩解

### 高風險項目
1. **性能影響**: 關係處理可能影響索引速度
   - **緩解**: 增量關係更新、並行處理
   
2. **複雜度增加**: 多語言關係邏輯複雜
   - **緩解**: 分階段實施、詳細測試
   
3. **向後兼容**: 現有 API 可能受影響
   - **緩解**: 保持現有接口、漸進式更新

### 中風險項目
1. **SCIP 標準理解**: 關係映射可能不精確
   - **緩解**: 參考官方實現、社群驗證
   
2. **語言特性差異**: 不同語言關係模型差異大
   - **緩解**: 分語言設計、彈性架構

## 🚀 預期成果

### 功能改進
- ✅ 完整的 SCIP 關係圖支援
- ✅ 跨文件符號導航功能
- ✅ 與標準 SCIP 工具鏈兼容
- ✅ 6 種程式語言的關係分析

### 合規性提升
- **當前**: 60-70% SCIP 標準合規
- **目標**: 95%+ SCIP 標準合規
- **關鍵**: 100% Relationship 功能合規

### 性能目標
- 索引速度影響 < 15%
- 記憶體使用增長 < 20%
- 大型項目 (1000+ 檔案) 支援良好

## 📝 變更管理

### 版本控制策略
- 功能分支開發 (`feature/scip-relationships`)
- 增量 PR 提交，便於審查
- 完整功能後合併到主分支

### 文檔更新
- [ ] 更新 `ARCHITECTURE.md` 包含關係架構
- [ ] 更新 `README.md` 功能描述
- [ ] 新增關係 API 使用指南
- [ ] 更新 `SCIP_OFFICIAL_STANDARDS.md` 實現狀態

### 發布策略
- 作為主要版本發布 (v3.0.0)
- 提供升級指南和遷移文檔
- 社群通知和反饋收集

---

**負責人**: Claude Code  
**審查者**: 項目維護者  
**最後更新**: 2025-01-14