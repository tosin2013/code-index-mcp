# Code Index MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

コードのインデックス作成、検索、解析のためのModel Context Protocol（MCP）サーバー。

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## Code Index MCPとは？

Code Index MCPは、インテリジェントなコードインデックス作成と解析機能を提供する専用のMCPサーバーです。大規模言語モデルがあなたのコードリポジトリと対話し、複雑なコードベースに対するリアルタイムの洞察とナビゲーションを提供することを可能にします。

このサーバーは、AIモデルが外部ツールやデータソースと対話するための標準化された方法である[Model Context Protocol](https://modelcontextprotocol.io)（MCP）と統合されています。

## 主な機能

- **プロジェクトインデックス作成**: ディレクトリを再帰的にスキャンして、検索可能なコードファイルのインデックスを構築
- **高度な検索**: ugrep、ripgrep、ag、grepの自動検出による高性能なインテリジェント検索
- **正規表現検索**: ReDoS攻撃を防ぐための安全性検証を備えた完全な正規表現パターンマッチング
- **ファジー検索**: ugrepのネイティブファジーマッチング、または他のツールでの単語境界パターンマッチング
- **ファイル解析**: ファイル構造、インポート、クラス、メソッド、複雑さに関する詳細な洞察を取得
  - **Javaサポート**: パッケージ、クラス、インターフェース、列挙型、メソッドを含む包括的な解析
  - **Python/JavaScriptサポート**: 関数、クラス、インポートの解析
- **スマートフィルタリング**: ビルドディレクトリ、依存関係、非コードファイルを自動的に無視
- **永続ストレージ**: セッション間でのパフォーマンス向上のためにインデックスをキャッシュ
- **遅延ロード**: 最適な起動パフォーマンスのために、必要な時のみ検索ツールを検出

## サポートされているファイルタイプ

サーバーは複数のプログラミング言語とファイル拡張子をサポートしています：

- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx, .mjs, .cjs)
- フロントエンドフレームワーク (.vue, .svelte, .astro)
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
- シェルスクリプト (.sh, .bash)
- Zig (.zig)
- Webファイル (.html, .css, .scss, .less, .sass, .stylus, .styl)
- テンプレートエンジン (.hbs, .handlebars, .ejs, .pug)
- **データベース & SQL**:
  - SQLファイル (.sql, .ddl, .dml)
  - データベース固有 (.mysql, .postgresql, .psql, .sqlite, .mssql, .oracle, .ora, .db2)
  - データベースオブジェクト (.proc, .procedure, .func, .function, .view, .trigger, .index)
  - マイグレーション & ツール (.migration, .seed, .fixture, .schema, .liquibase, .flyway)
  - NoSQL & モダン (.cql, .cypher, .sparql, .gql)
- ドキュメント/設定 (.md, .mdx, .json, .xml, .yml, .yaml)

## セットアップと統合

ニーズに応じて、Code Index MCPをセットアップして使用する方法がいくつかあります。

### ホストアプリケーションでの一般使用（推奨）

これは最も簡単で一般的な使用方法です。Claude DesktopなどのAIアプリケーション内でCode Index MCPを使用したいユーザー向けに設計されています。

1.  **前提条件**: Python 3.10+と[uv](https://github.com/astral-sh/uv)がインストールされていることを確認してください。

2.  **ホストアプリの設定**: ホストアプリケーションのMCP設定ファイルに以下を追加してください。
    
    *Claude Desktop* -> `claude_desktop_config.json`
    
    *Claude Code* -> `~/.claude.json`。プロジェクトごとに1つの`mcpServers`とグローバルに1つがあります

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

3.  **ホストアプリの再起動**: 設定を追加した後、アプリケーションを再起動してください。`uvx`コマンドがバックグラウンドで`code-index-mcp`サーバーのインストールと実行を自動的に処理します。

### ローカル開発用

このプロジェクトの開発に貢献したい場合は、以下の手順に従ってください：

1.  **リポジトリをクローン**:
    ```bash
    git clone https://github.com/johnhuang316/code-index-mcp.git
    cd code-index-mcp
    ```

2.  **依存関係をインストール** `uv`を使用:
    ```bash
    uv sync
    ```

3.  **ローカル開発用にホストアプリを設定**: ホストアプリケーション（例：Claude Desktop）がローカルのソースコードを使用するように、設定ファイルを更新して`uv run`経由でサーバーを実行します。これにより、コードに加えた変更がホストアプリがサーバーを起動する際に即座に反映されます。

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

4.  **MCP Inspectorでデバッグ**: ローカルサーバーをデバッグするには、インスペクターにも`uv run`を使用するよう指示する必要があります。
    ```bash
    npx @modelcontextprotocol/inspector uv run code_index_mcp
    ```

### pipによる手動インストール（代替方法）

`pip`でPythonパッケージを手動管理したい場合は、サーバーを直接インストールできます。

1.  **パッケージをインストール**:
    ```bash
    pip install code-index-mcp
    ```

2.  **ホストアプリを設定**: ホストアプリケーションのMCP設定を手動で更新して、インストールされたスクリプトを指すようにする必要があります。`"command": "uvx"`を`"command": "code-index-mcp"`に置き換えてください。

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

## 利用可能なツール

### コアツール

- **set_project_path**: インデックス作成用のベースプロジェクトパスを設定します。
- **search_code_advanced**: 外部ツール（ugrep/ripgrep/ag/grep）を使用した拡張検索で、正規表現とファジーマッチングをサポート。
- **find_files**: プロジェクト内で指定されたパターンにマッチするファイルを検索します。
- **get_file_summary**: 行数、関数、インポートなどを含む特定ファイルの要約を取得します。
- **refresh_index**: プロジェクトインデックスを更新します。
- **get_settings_info**: プロジェクト設定に関する情報を取得します。

### ユーティリティツール

- **create_temp_directory**: インデックスデータの保存に使用される一時ディレクトリを作成します。
- **check_temp_directory**: インデックスデータの保存に使用される一時ディレクトリをチェックします。
- **clear_settings**: すべての設定とキャッシュデータをクリアします。
- **refresh_search_tools**: 利用可能なコマンドライン検索ツール（ripgrepなど）を手動で再検出します。

## 一般的なワークフローと例

ClaudeなどのAIアシスタントでCode Index MCPを使用する典型的なワークフローです。

### 1. プロジェクトパスの設定と初期インデックス作成

これは最初の最も重要なステップです。プロジェクトパスを設定すると、サーバーは初回のファイルインデックスを自動的に作成するか、以前にキャッシュされたものを読み込みます。

**プロンプト例:**
```
プロジェクトパスを C:\Users\username\projects\my-react-app に設定してください
```

### 2. インデックスの更新（必要に応じて）

初期設定後にプロジェクトファイルに大幅な変更を加えた場合、手動でインデックスを更新して、すべてのツールが最新の情報で動作するようにできます。

**プロンプト例:**
```
いくつかの新しいコンポーネントを追加したので、プロジェクトインデックスを更新してください。
```
*（アシスタントは`refresh_index`ツールを使用します）*

### 3. プロジェクト構造の探索

インデックスの準備ができたら、パターン（グロブ）を使用してファイルを検索し、コードベースを理解して関連ファイルを見つけることができます。

**プロンプト例:**
```
'src/components'ディレクトリ内のすべてのTypeScriptコンポーネントファイルを検索してください。
```
*（アシスタントは`src/components/**/*.tsx`のようなパターンで`find_files`ツールを使用します）*

### 4. 特定ファイルの解析

ファイルの完全な内容に詳しく入る前に、関数、クラス、インポートを含む構造の簡単な要約を取得できます。

**プロンプト例:**
```
'src/api/userService.ts'ファイルの要約を教えてください。
```
*（アシスタントは`get_file_summary`ツールを使用します）*

### 5. コードの検索

最新のインデックスがあれば、コードスニペット、関数名、または任意のテキストパターンを検索して、特定のロジックが実装されている場所を見つけることができます。

**例: シンプル検索**
```
"processData"関数のすべての出現箇所を検索してください。
```

**例: ファジーマッチング検索**
```
ユーザー認証に関連する関数を探しています。'authUser'、'authenticateUser'、または類似の名前かもしれません。'authUser'でファジー検索できますか？
```

**例: 正規表現検索**
```
正規表現を使用して、パターン"get.*Data"にマッチするすべての関数呼び出しを検索してください。
```

**例: 特定ファイル内の検索**
```
Pythonファイル内のみで文字列"API_ENDPOINT"を検索してください。
```
*（アシスタントは`file_pattern`パラメータを`*.py`に設定して`search_code_advanced`ツールを使用します）*

## 開発

### ソースからのビルド

1. リポジトリをクローン:

```bash
git clone https://github.com/username/code-index-mcp.git
cd code-index-mcp
```

2. 依存関係をインストール:

```bash
uv sync
```

3. サーバーをローカルで実行:

```bash
uv run code_index_mcp
```

## デバッグ

MCP inspectorを使用してサーバーをデバッグできます：

```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

## ライセンス

[MIT License](LICENSE)

## 貢献

貢献を歓迎します！プルリクエストをお気軽に提出してください。

## 言語

- [English](README.md)
- [繁體中文](README_zh.md)

---

*この日本語READMEは[Claude Code](https://claude.ai/code)で作成されました 🤖*