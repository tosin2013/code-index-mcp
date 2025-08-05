# Code Index MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**大規模言語モデルのためのインテリジェントコードインデックス作成と解析**

高度な検索、解析、ナビゲーション機能で、AIのコードベース理解を根本的に変革します。

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## 概要

Code Index MCPは、AIモデルと複雑なコードベースの橋渡しをする[Model Context Protocol](https://modelcontextprotocol.io)サーバーです。インテリジェントなインデックス作成、高度な検索機能、詳細なコード解析を提供し、AIアシスタントがプロジェクトを効果的に理解しナビゲートできるようにします。

**最適な用途：**コードレビュー、リファクタリング、ドキュメント生成、デバッグ支援、アーキテクチャ解析。

## 主な機能

### 🔍 **インテリジェント検索・解析**
- **高度な検索**：最適なツール（ugrep、ripgrep、ag、grep）を自動検出・使用
- **正規表現サポート**：ReDoS攻撃防御付きの完全な正規表現パターンマッチング
- **ファジー検索**：真の編集距離ファジーマッチング（ugrep）または単語境界パターンマッチング
- **ファイル解析**：構造、インポート、クラス、メソッド、複雑度メトリクスへの深い洞察

### 🗂️ **多言語サポート**
- **主流言語**：Java、Python、JavaScript/TypeScript、C/C++、Go、Rust、C#
- **モバイル開発**：Swift、Kotlin、Objective-C/C++、React Native
- **Webフロントエンド**：Vue、React、Svelte、Astro、HTML、CSS、SCSS
- **データベース**：SQL (MySQL、PostgreSQL、SQLite)、NoSQL、ストアドプロシージャ、マイグレーション
- **スクリプト言語**：Ruby、PHP、Shell、PowerShell、Bash
- **システム言語**：C/C++、Rust、Go、Zig
- **JVMエコシステム**：Java、Kotlin、Scala、Groovy
- **その他の言語**：Lua、Perl、R、MATLAB、設定ファイル
- **合計50+ファイルタイプ** - [完全なリストを表示](#サポートされているファイルタイプ)

### ⚡ **リアルタイム監視・自動更新**
- **ファイルウォッチャー**：ファイル変更時の自動インデックス更新
- **クロスプラットフォーム**：ネイティブOS ファイルシステム監視 (inotify、FSEvents、ReadDirectoryChangesW)
- **スマートデバウンス**：急速な変更をバッチ処理して過度な再構築を防止（デフォルト：6秒）
- **スレッドセーフ**：ThreadPoolExecutor による非ブロッキングバックグラウンド操作

### ⚡ **パフォーマンス・効率性**
- **スマートインデックス作成**：ビルドディレクトリをインテリジェントにフィルタリングしながら再帰的スキャン
- **永続キャッシュ**：超高速な後続アクセスのためのインデックス保存
- **遅延ロード**：最適化された起動のため必要時のみツール検出
- **メモリ効率**：大規模コードベース向けのインテリジェントキャッシュ戦略

## サポートされているファイルタイプ

<details>
<summary><strong>📁 プログラミング言語（クリックで展開）</strong></summary>

**システム・低レベル言語：**
- C/C++ (`.c`, `.cpp`, `.h`, `.hpp`)
- Rust (`.rs`)
- Zig (`.zig`)
- Go (`.go`)

**オブジェクト指向言語：**
- Java (`.java`)
- C# (`.cs`)
- Kotlin (`.kt`)
- Scala (`.scala`)
- Objective-C/C++ (`.m`, `.mm`)
- Swift (`.swift`)

**スクリプト・動的言語：**
- Python (`.py`)
- JavaScript/TypeScript (`.js`, `.ts`, `.jsx`, `.tsx`, `.mjs`, `.cjs`)
- Ruby (`.rb`)
- PHP (`.php`)
- Shell (`.sh`, `.bash`)

</details>

<details>
<summary><strong>🌐 Web・フロントエンド（クリックで展開）</strong></summary>

**フレームワーク・ライブラリ：**
- Vue (`.vue`)
- Svelte (`.svelte`)
- Astro (`.astro`)

**スタイリング：**
- CSS (`.css`, `.scss`, `.less`, `.sass`, `.stylus`, `.styl`)
- HTML (`.html`)

**テンプレート：**
- Handlebars (`.hbs`, `.handlebars`)
- EJS (`.ejs`)
- Pug (`.pug`)

</details>

<details>
<summary><strong>🗄️ データベース・SQL（クリックで展開）</strong></summary>

**SQL バリアント：**
- 標準SQL (`.sql`, `.ddl`, `.dml`)
- データベース固有 (`.mysql`, `.postgresql`, `.psql`, `.sqlite`, `.mssql`, `.oracle`, `.ora`, `.db2`)

**データベースオブジェクト：**
- プロシージャ・関数 (`.proc`, `.procedure`, `.func`, `.function`)
- ビュー・トリガー (`.view`, `.trigger`, `.index`)

**マイグレーション・ツール：**
- マイグレーションファイル (`.migration`, `.seed`, `.fixture`, `.schema`)
- ツール固有 (`.liquibase`, `.flyway`)

**NoSQL・モダンDB：**
- グラフ・クエリ (`.cql`, `.cypher`, `.sparql`, `.gql`)

</details>

<details>
<summary><strong>📄 ドキュメント・設定（クリックで展開）</strong></summary>

- Markdown (`.md`, `.mdx`)
- 設定 (`.json`, `.xml`, `.yml`, `.yaml`)

</details>

## クイックスタート

### 🚀 **推奨セットアップ（ほとんどのユーザー向け）**

任意のMCP対応アプリケーションで開始する最も簡単な方法：

**前提条件：** Python 3.10+ と [uv](https://github.com/astral-sh/uv)

1. **MCP設定に追加**（例：`claude_desktop_config.json` または `~/.claude.json`）：
   ```json
   {
     "mcpServers": {
       "code-index": {
         "command": "uvx",
         "args": ["code-index-mcp"]
       }
     }
   }
   ```

2. **アプリケーションを再起動** – `uvx` が自動的にインストールと実行を処理

### 🛠️ **開発セットアップ**

貢献やローカル開発用：

1. **クローンとインストール：**
   ```bash
   git clone https://github.com/johnhuang316/code-index-mcp.git
   cd code-index-mcp
   uv sync
   ```

2. **ローカル開発用設定：**
   ```json
   {
     "mcpServers": {
       "code-index": {
         "command": "uv",
         "args": ["run", "code_index_mcp"]
       }
     }
   }
   ```

3. **MCP Inspectorでデバッグ：**
   ```bash
   npx @modelcontextprotocol/inspector uv run code_index_mcp
   ```

<details>
<summary><strong>代替案：手動pipインストール</strong></summary>

従来のpip管理を好む場合：

```bash
pip install code-index-mcp
```

そして設定：
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

</details>

## 利用可能なツール

### 🏗️ **プロジェクト管理**
| ツール | 説明 |
|--------|------|
| **`set_project_path`** | プロジェクトディレクトリのインデックス作成を初期化 |
| **`refresh_index`** | ファイル変更後にプロジェクトインデックスを再構築 |
| **`get_settings_info`** | 現在のプロジェクト設定と状態を表示 |

### 🔍 **検索・発見**
| ツール | 説明 |
|--------|------|
| **`search_code_advanced`** | 正規表現、ファジーマッチング、ファイルフィルタリング対応のスマート検索 |
| **`find_files`** | globパターンを使用したファイル検索（例：`**/*.py`） |
| **`get_file_summary`** | ファイル構造、関数、インポート、複雑度の解析 |

### 🔄 **監視・自動更新**
| ツール | 説明 |
|--------|------|
| **`get_file_watcher_status`** | ファイルウォッチャーの状態と設定を確認 |
| **`configure_file_watcher`** | 自動更新の有効化/無効化と設定の構成 |

### 🛠️ **システム・メンテナンス**
| ツール | 説明 |
|--------|------|
| **`create_temp_directory`** | インデックスデータの保存ディレクトリをセットアップ |
| **`check_temp_directory`** | インデックス保存場所と権限を確認 |
| **`clear_settings`** | すべてのキャッシュデータと設定をリセット |
| **`refresh_search_tools`** | 利用可能な検索ツール（ugrep、ripgrep等）を再検出 |

## 使用例

### 🎯 **クイックスタートワークフロー**

**1. プロジェクトの初期化**
```
プロジェクトパスを /Users/dev/my-react-app に設定してください
```
*コードベースを自動インデックス作成し、検索可能なキャッシュを構築*

**2. プロジェクト構造の探索**
```
src/components で全てのTypeScriptコンポーネントファイルを見つけてください
```
*使用ツール：`find_files`、パターン `src/components/**/*.tsx`*

**3. キーファイルの解析**
```
src/api/userService.ts の要約を教えてください
```
*使用ツール：`get_file_summary` で関数、インポート、複雑度を表示*

### 🔍 **高度な検索例**

<details>
<summary><strong>コードパターン検索</strong></summary>

```
正規表現を使って "get.*Data" にマッチする全ての関数呼び出しを検索してください
```
*発見：`getData()`、`getUserData()`、`getFormData()` など*

</details>

<details>
<summary><strong>ファジー関数検索</strong></summary>

```
'authUser' でファジー検索して認証関連の関数を見つけてください
```
*マッチ：`authenticateUser`、`authUserToken`、`userAuthCheck` など*

</details>

<details>
<summary><strong>言語固有検索</strong></summary>

```
Pythonファイルのみで "API_ENDPOINT" を検索してください
```
*使用ツール：`search_code_advanced`、`file_pattern: "*.py"`*

</details>

<details>
<summary><strong>自動更新設定</strong></summary>

```
ファイル変更時の自動インデックス更新を設定してください
```
*使用ツール：`configure_file_watcher` で監視の有効化/無効化とデバウンス時間を設定*

</details>

<details>
<summary><strong>プロジェクトメンテナンス</strong></summary>

```
新しいコンポーネントを追加したので、プロジェクトインデックスを更新してください
```
*使用ツール：`refresh_index` で検索可能なキャッシュを更新*

</details>

## トラブルシューティング

### 🔄 **自動リフレッシュが動作しない**

ファイル変更時に自動インデックス更新が動作しない場合、以下を試してください：
- `pip install watchdog`（環境分離の問題を解決する可能性があります）
- 手動リフレッシュを使用：ファイル変更後に `refresh_index` ツールを呼び出す
- ファイルウォッチャーステータスを確認：`get_file_watcher_status` を使用して監視がアクティブかどうかを確認

## 開発・貢献

### 🔧 **ソースからのビルド**
```bash
git clone https://github.com/johnhuang316/code-index-mcp.git
cd code-index-mcp
uv sync
uv run code_index_mcp
```

### 🐛 **デバッグ**
```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

### 🤝 **貢献**
貢献を歓迎します！お気軽にプルリクエストを提出してください。

---

### 📜 **ライセンス**
[MIT License](LICENSE)

### 🌐 **翻訳**
- [English](README.md)
- [繁體中文](README_zh.md)