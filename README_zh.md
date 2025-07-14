# 程式碼索引 MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

一個用於程式碼索引、搜尋和分析的模型上下文協定(Model Context Protocol)伺服器。

</div>

## 什麼是程式碼索引 MCP？

程式碼索引 MCP 是一個專門的 MCP 伺服器，提供智慧程式碼索引和分析功能。它使大型語言模型能夠與您的程式碼儲存庫互動，提供對複雜程式碼庫的即時洞察和導航。

此伺服器基於[模型上下文協定](https://modelcontextprotocol.io) (MCP) 建構，該協定標準化了 AI 模型與外部工具和資料來源的互動方式。

## 主要特性

- **專案索引**：遞迴掃描目錄以建構可搜尋的程式碼檔案索引
- **進階搜尋**：智慧搜尋，自動偵測 ugrep、ripgrep、ag 或 grep 以提升效能
- **正規表達式搜尋**：完整的正規表達式模式匹配，具備安全驗證以防範 ReDoS 攻擊
- **模糊搜尋**：ugrep 的原生模糊匹配功能，或其他工具的詞邊界模式匹配
- **檔案分析**：取得有關檔案結構、匯入、類別、方法和複雜性的詳細資訊
  - **Java 支援**：全面分析包括套件、類別、介面、列舉和方法
  - **Python/JavaScript 支援**：函式、類別和匯入分析
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

## 設定與整合

您可以根據不同的需求，透過以下幾種方式來設定和使用 Code Index MCP。

### 一般用途：與宿主應用整合（建議）

這是最簡單也最常見的使用方式，專為希望在 AI 應用程式（如 Claude Desktop）中使用 Code Index MCP 的使用者設計。

1.  **先決條件**：請確保您已安裝 Python 3.10+ 和 [uv](https://github.com/astral-sh/uv)。

2.  **設定宿主應用**：將以下設定新增到您宿主應用的 MCP 設定檔中（例如，Claude Desktop 的設定檔是 `claude_desktop_config.json`）：

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

3.  **重新啟動宿主應用**：新增設定後，請重新啟動您的應用程式。`uvx` 命令會在背景自動處理 `code-index-mcp` 伺服器的安裝與執行。

### 本地開發

如果您想為這個專案的開發做出貢獻，請遵循以下步驟：

1.  **複製儲存庫**：
    ```bash
    git clone https://github.com/johnhuang316/code-index-mcp.git
    cd code-index-mcp
    ```

2.  **安裝相依套件**：使用 `uv` 安裝所需套件。
    ```bash
    uv sync
    ```

3.  **設定您的宿主應用以進行本地開發**：為了讓您的宿主應用程式（例如 Claude Desktop）使用您本地的原始碼，請更新其設定檔，讓它透過 `uv run` 來執行伺服器。這能確保您對程式碼所做的任何變更，在宿主應用啟動伺服器時能立即生效。

    ```json
    {
      "mcpServers": {
        "code-index": {
          "command": "uv",
          "args": [
            "run",
            "code_index_mcp"
          ]
        }
      }
    }
    ```

4.  **使用 MCP Inspector 進行偵錯**：要對您的本地伺服器進行偵錯，您同樣需要告訴 Inspector 使用 `uv run`。
    ```bash
    npx @modelcontextprotocol/inspector uv run code_index_mcp
    ```

### 手動安裝：使用 pip（替代方案）

如果您習慣使用 `pip` 來手動管理您的 Python 套件，可以透過以下方式安裝。

1.  **安裝套件**：
    ```bash
    pip install code-index-mcp
    ```

2.  **設定宿主應用**：您需要手動更新宿主應用的 MCP 設定，將命令從 `"command": "uvx"` 修改為 `"command": "code-index-mcp"`。

    ```json
    {
      "mcpServers": {
        "code-index": {
          "command": "code-index-mcp",
          "args": []
        }
      }
    }
    ```

## 可用工具

### 核心工具

- **set_project_path**：設定索引的基本專案路徑。
- **search_code_advanced**：使用外部工具 (ugrep/ripgrep/ag/grep) 的增強搜尋，支援正規表達式和模糊匹配。
- **find_files**：尋找專案中符合給定模式的檔案。
- **get_file_summary**：取得特定檔案的摘要，包括行數、函式、匯入等。
- **refresh_index**：重新整理專案索引。
- **get_settings_info**：取得專案設定的資訊。

### 工具程式

- **create_temp_directory**：建立用於儲存索引資料的臨時目錄。
- **check_temp_directory**：檢查用於儲存索引資料的臨時目錄。
- **clear_settings**：清除所有設定和快取資料。
- **refresh_search_tools**：手動重新偵測可用的命令列搜尋工具（例如 ripgrep）。

## 常見工作流程與範例

這是一個典型的使用場景，展示如何透過像 Claude 這樣的 AI 助理來使用 Code Index MCP。

### 1. 設定專案路徑與首次索引

這是第一步，也是最重要的一步。當您設定專案路徑時，伺服器會自動進行首次的檔案索引，或載入先前快取的索引。

**範例提示：**
```
請將專案路徑設定為 C:\Users\username\projects\my-react-app
```

### 2. 更新索引（需要時）

如果您在初次設定後對專案檔案做了較大的變更，可以手動重新整理索引，以確保所有工具都能基於最新的資訊運作。

**範例提示：**
```
我剛新增了幾個新的元件，請幫我重新整理專案索引。
```
*（AI 助理會使用 `refresh_index` 工具）*

### 3. 探索專案結構

索引準備就緒後，您可以使用模式（glob）來尋找檔案，以了解程式碼庫的結構並找到相關檔案。

**範例提示：**
```
尋找 'src/components' 目錄中所有的 TypeScript 元件檔案。
```
*（AI 助理會使用 `find_files` 工具，並搭配像 `src/components/**/*.tsx` 這樣的模式）*

### 4. 分析特定檔案

在深入研究一個檔案的完整內容之前，您可以先取得該檔案結構的快速摘要，包括函式、類別和匯入的模組。

**範例提示：**
```
可以給我 'src/api/userService.ts' 這個檔案的摘要嗎？
```
*（AI 助理會使用 `get_file_summary` 工具）*

### 5. 搜尋程式碼

有了最新的索引，您就可以搜尋程式碼片段、函式名稱或任何文字模式，以找到特定邏輯的實作位置。

**範例：簡單搜尋**
```
搜尋 "processData" 函式所有出現過的地方。
```

**範例：模糊匹配搜尋**
```
我正在尋找一個與使用者驗證相關的函式，它可能叫做 'authUser'、'authenticateUser' 或類似的名稱。你可以對 'authUser' 進行模糊搜尋嗎？
```

**範例：正規表達式搜尋**
```
使用正規表達式搜尋所有符合模式 "get.*Data" 的函式呼叫。
```

**範例：在特定檔案中搜尋**
```
只在 Python 檔案中搜尋字串 "API_ENDPOINT"。
```
*（AI 助理會使用 `search_code_advanced` 工具，並將 `file_pattern` 參數設定為 `*.py`）*

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
