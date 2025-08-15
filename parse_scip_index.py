#!/usr/bin/env python3
"""解析 SCIP 索引文件"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def parse_scip_index():
    """解析 SCIP 索引文件"""
    
    scip_file_path = r"C:\Users\P10362~1\AppData\Local\Temp\code_indexer\22bf459212636f4b8ae327f69d901283\index.scip"
    
    try:
        from code_index_mcp.scip.proto import scip_pb2
        
        print(f"🔍 解析 SCIP 文件: {scip_file_path}")
        
        # 檢查文件是否存在
        if not os.path.exists(scip_file_path):
            print("❌ SCIP 文件不存在")
            return
        
        # 獲取文件大小
        file_size = os.path.getsize(scip_file_path)
        print(f"📊 文件大小: {file_size} bytes")
        
        # 讀取並解析 SCIP 文件
        with open(scip_file_path, 'rb') as f:
            scip_data = f.read()
        
        print(f"✅ 讀取了 {len(scip_data)} bytes 的數據")
        
        # 解析 protobuf
        scip_index = scip_pb2.Index()
        scip_index.ParseFromString(scip_data)
        
        print(f"✅ SCIP 索引解析成功")
        print(f"📄 文檔數量: {len(scip_index.documents)}")
        
        # 檢查元數據
        if scip_index.metadata:
            print(f"📋 元數據:")
            print(f"   版本: {scip_index.metadata.version}")
            print(f"   項目根目錄: {scip_index.metadata.project_root}")
            print(f"   工具信息: {scip_index.metadata.tool_info}")
        
        # 檢查前幾個文檔
        for i, doc in enumerate(scip_index.documents[:5]):
            print(f"\n📄 文檔 {i+1}: {doc.relative_path}")
            print(f"   語言: {doc.language}")
            print(f"   符號數量: {len(doc.symbols)}")
            print(f"   出現次數: {len(doc.occurrences)}")
            
            # 檢查符號
            for j, symbol in enumerate(doc.symbols[:3]):
                print(f"   🔍 符號 {j+1}: {symbol.display_name}")
                print(f"      符號 ID: {symbol.symbol}")
                print(f"      類型: {symbol.kind}")
                print(f"      關係數量: {len(symbol.relationships)}")
                
                # 檢查關係
                if symbol.relationships:
                    for k, rel in enumerate(symbol.relationships[:2]):
                        print(f"      🔗 關係 {k+1}: -> {rel.symbol}")
                        print(f"         is_reference: {rel.is_reference}")
                        print(f"         is_implementation: {rel.is_implementation}")
                        print(f"         is_type_definition: {rel.is_type_definition}")
        
        # 統計信息
        total_symbols = sum(len(doc.symbols) for doc in scip_index.documents)
        total_occurrences = sum(len(doc.occurrences) for doc in scip_index.documents)
        total_relationships = sum(len(symbol.relationships) for doc in scip_index.documents for symbol in doc.symbols)
        
        print(f"\n📊 統計信息:")
        print(f"   總文檔數: {len(scip_index.documents)}")
        print(f"   總符號數: {total_symbols}")
        print(f"   總出現次數: {total_occurrences}")
        print(f"   總關係數: {total_relationships}")
        
        return True
        
    except Exception as e:
        print(f"❌ 解析失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 開始解析 SCIP 索引文件...")
    success = parse_scip_index()
    
    if success:
        print("\n✅ SCIP 索引解析完成！")
    else:
        print("\n❌ SCIP 索引解析失敗")