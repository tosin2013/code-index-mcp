# 程式碼索引 MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.8%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

一個用於程式碼索引、搜尋和分析的模型上下文協定(Model Context Protocol)伺服器。

</div>

## 什麼是程式碼索引 MCP？

程式碼索引 MCP 是一個專門的 MCP 伺服器，提供智慧程式碼索引和分析功能。它使大型語言模型能夠與您的程式碼儲存庫互動，提供對複雜程式碼庫的即時洞察和導航。

此伺服器基於[模型上下文協定](https://modelcontextprotocol.io) (MCP) 建構，該協定標準化了 AI 模型與外部工具和資料來源的互動方式。

## 主要特性

- **專案索引**：遞迴掃描目錄以建構可搜尋的程式碼檔案索引
- **進階搜尋**：智慧搜尋，自動偵測 ugrep、ripgrep、ag 或 grep 以提升效能
- **模糊搜尋**：ugrep 的原生模糊匹配功能提供卓越的搜尋結果，或其他工具的安全模糊模式
- **檔案分析**：取得有關檔案結構、匯入和複雜性的詳細資訊
- **智慧篩選**：自動忽略建構目錄、相依套件和非程式碼檔案
- **持久儲存**：快取索引以提高跨工作階段的效能
- **延遲載入**：僅在需要時偵測搜尋工具，優化啟動效能

## 支援的檔案類型

伺服器支援多種程式語言和檔案副檔名，包括：

- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx, .mjs, .cjs)
- 前端框架 (.vue, .svelte, .astro)
- Java (.java)
- C/C++ (.c, .cpp, .h, .hpp)
- C# (.cs)
- Go (.go)
- Ruby (.rb)
- PHP (.php)
- Swift (.swift)
- Kotlin (.kt)
- Rust (.rs)
- Scala (.scala)
- Shell 指令碼 (.sh, .bash)
- Zig (.zig)
- Web 檔案 (.html, .css, .scss, .less, .sass, .stylus, .styl)
- 模板引擎 (.hbs, .handlebars, .ejs, .pug)
- **資料庫與 SQL**：
  - SQL 檔案 (.sql, .ddl, .dml)
  - 資料庫特定格式 (.mysql, .postgresql, .psql, .sqlite, .mssql, .oracle, .ora, .db2)
  - 資料庫物件 (.proc, .procedure, .func, .function, .view, .trigger, .index)
  - 遷移與工具 (.migration, .seed, .fixture, .schema, .liquibase, .flyway)
  - NoSQL 與現代資料庫 (.cql, .cypher, .sparql, .gql)
- 文件/配置 (.md, .mdx, .json, .xml, .yml, .yaml)

## 安裝

### 先決條件

- Python 3.8 或更高版本
- [uv](https://github.com/astral-sh/uv) 套件管理器（建議）

### 使用 uvx（建議）

使用 uvx 安裝和使用 code-index-mcp 是最簡單的方法：

```bash
uvx code-index-mcp
```

### 使用 pip

或者，您可以透過 pip 安裝：

```bash
pip install code-index-mcp
```

安裝後，您可以以模組方式執行：

```bash
python -m code_index_mcp
```

## 與 Claude Desktop 整合

將以下內容新增到您的 Claude 設定（`~/Library/Application Support/Claude/claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "code-index": {
      "command": "uvx",
      "args": [
        "code-index-mcp"
      ]
    }
  }
}
```

新增設定後，重新啟動 Claude Desktop，程式碼索引 MCP 工具將可使用。

## 可用工具

### 核心工具

- **set_project_path**：設定索引的基本專案路徑。
- **search_code**：在已索引檔案中進行基本程式碼搜尋。
- **search_code_advanced**：使用外部工具 (ugrep/ripgrep/ag/grep) 的增強搜尋，支援模糊匹配。
- **find_files**：尋找專案中符合給定模式的檔案。
- **get_file_summary**：取得特定檔案的摘要，包括行數、函式、匯入等。
- **refresh_index**：重新整理專案索引。
- **get_settings_info**：取得專案設定的資訊。

### 工具程式

- **create_temp_directory**：建立用於儲存索引資料的臨時目錄。
- **check_temp_directory**：檢查用於儲存索引資料的臨時目錄。
- **clear_settings**：清除所有設定和快取資料。

## Claude 使用範例

以下是如何與 Claude 一起使用 Code Index MCP 的一些範例：

### 設定專案路徑

```
請將專案路徑設定為 C:\Users\username\projects\my-python-project
```

### 搜尋程式碼模式

```
在 Python 檔案中搜尋所有出現 "def process_data" 的地方
```

### 進階搜尋與模糊匹配

```
使用進階搜尋並啟用模糊匹配來尋找 "process"
```

### 取得檔案摘要

```
給我專案中 main.py 檔案的摘要
```

### 尋找特定類型的所有檔案

```
尋找專案中所有的 JavaScript 檔案
```

## 開發

### 從原始碼建構

1. 複製儲存庫：

```bash
git clone https://github.com/username/code-index-mcp.git
cd code-index-mcp
```

2. 安裝相依套件：

```bash
uv sync
```

3. 在本地執行伺服器：

```bash
uv run code_index_mcp
```

## 偵錯

您可以使用 MCP inspector 來偵錯伺服器：

```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

## 授權條款

[MIT 授權條款](LICENSE)

## 貢獻

歡迎貢獻！請隨時提交拉取請求。

## 語言

- [English](README.md)
