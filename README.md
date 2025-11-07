# Code Index MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**Intelligent code indexing and analysis for Large Language Models**

Transform how AI understands your codebase with advanced search, analysis, and navigation capabilities.

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## Overview

Code Index MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that bridges the gap between AI models and complex codebases. It provides intelligent indexing, advanced search capabilities, and detailed code analysis to help AI assistants understand and navigate your projects effectively.

**Perfect for:** Code review, refactoring, documentation generation, debugging assistance, and architectural analysis.

## Quick Start

### 🚀 **Recommended Setup (Most Users)**

The easiest way to get started with any MCP-compatible application:

**Prerequisites:** Python 3.10+ and [uv](https://github.com/astral-sh/uv)

1. **Add to your MCP configuration** (e.g., `claude_desktop_config.json` or `~/.claude.json`):
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

2. **Restart your application** – `uvx` automatically handles installation and execution

3. **Start using** (give these prompts to your AI assistant):
   ```
   Set the project path to /Users/dev/my-react-app
   Find all TypeScript files in this project
   Search for "authentication" functions
   Analyze the main App.tsx file
   ```

## 🔒 Security & Contributing

**CRITICAL for contributors:** This repository uses **pre-commit hooks** to prevent credential leaks and ensure code quality before commits.

### Pre-commit Setup (Required for Contributors)

```bash
# 1. Install pre-commit
pip install pre-commit

# 2. Install the hooks
pre-commit install

# 3. Test the hooks
pre-commit run --all-files
```

**What's protected:**
- ✅ MCP API keys (ci_* prefix)
- ✅ Database connection strings
- ✅ GCP service account keys
- ✅ Webhook secrets (GitHub, GitLab, Gitea)
- ✅ Private keys and credentials

**Configuration files:**
- `.pre-commit-config.yaml` - Pre-commit hook configuration
- `.gitleaks.toml` - Secret detection rules
- `.gitignore` - Credential exclusions

See [Deployment Lifecycle Guide](DEPLOYMENT_LIFECYCLE.md#security-setup-pre-commit-hooks) for detailed setup instructions.

## ☁️ Cloud Deployment

Code Index MCP supports **two deployment modes**:

### Local Mode (Default)
Perfect for individual developers - runs directly on your machine with zero deployment complexity.

### Cloud Mode (Teams & Organizations)
Deploy to cloud infrastructure for team collaboration with multi-user support, auto-scaling, and semantic code search capabilities.

**🚀 NEW: Git-Sync Feature**
- Ingest code directly from Git repositories (GitHub, GitLab, Bitbucket, Gitea)
- Auto-sync on every push via webhooks
- 99% token savings, 95% faster incremental updates
- See [Git-Sync Deployment Guide](deployment/gcp/GIT_SYNC_DEPLOYMENT_GUIDE.md)

**Supported Platforms:**
- **Google Cloud** - Cloud Run + AlloyDB + Vertex AI (~$6-25/month with Git-sync)
  - **🚀 Deployment Lifecycle**: [Complete repeatable workflow guide](DEPLOYMENT_LIFECYCLE.md) (NEW!)
  - **Quick Deploy**: [5-minute setup guide](deployment/gcp/QUICK_DEPLOY.md)
  - **Full Guide**: [GCP deployment with Git-sync](deployment/gcp/GIT_SYNC_DEPLOYMENT_GUIDE.md)
- **AWS** - Lambda/ECS + Aurora PostgreSQL + Amazon Bedrock (~$2.50-65/month)
- **OpenShift** - Kubernetes pods + Milvus + vLLM + ODF (on-premise ready)

**Features:**
- ✅ HTTP/SSE transport for cloud endpoints
- ✅ Multi-user authentication with API keys
- ✅ Automatic resource cleanup (no manual maintenance)
- ✅ Vector embeddings for semantic code search
- ✅ **Git-sync auto-update** (NEW!)
- ✅ Platform-native integrations

**Get Started:** See [Cloud Deployment Guide](docs/DEPLOYMENT.md) for platform-specific setup instructions.

### 📤 Code Ingestion for Cloud Mode

#### 🚀 **Recommended: Git-Sync (99% Token Savings)**

**NEW!** The best way to ingest code is directly from your Git repository - no file uploads needed!

**Benefits:**
- ✅ **99% token savings** vs file upload (no need to send files through AI)
- ✅ **95% faster** incremental updates (pulls only changes)
- ✅ **Auto-sync** via webhooks on every git push
- ✅ **Supports** GitHub, GitLab, Bitbucket, Gitea

**Usage:**
```
# Public repository
ingest_code_from_git(git_url="https://github.com/user/repo")

# Private repository
ingest_code_from_git(
    git_url="https://github.com/user/private-repo",
    auth_token="ghp_xxxxxxxxxxxx"
)

# Gitea custom domain
ingest_code_from_git(
    git_url="https://gitea.example.com/user/app",
    auth_token="your_token"
)
```

**Setup Webhooks (Optional):**
Configure webhooks in your Git platform to auto-sync on push:
- **GitHub**: `https://your-service.run.app/webhook/github`
- **GitLab**: `https://your-service.run.app/webhook/gitlab`
- **Gitea**: `https://your-service.run.app/webhook/gitea`

**Deployment Guide:** See [Git-Sync Deployment Guide](deployment/gcp/GIT_SYNC_DEPLOYMENT_GUIDE.md) for full setup instructions.

**Quick Deploy:** See [Quick Deploy Guide](deployment/gcp/QUICK_DEPLOY.md) for 5-minute setup.

#### 📦 **Legacy: File Upload (Deprecated)**

<details>
<summary>Click to expand legacy file upload method (not recommended)</summary>

**Note:** This method is deprecated. Use Git-sync instead for better performance.

1. **Get the upload script via MCP:**
   ```
   Ask your AI assistant: "Get me the cloud upload script"
   ```

2. **Or download manually:**
   ```bash
   curl -O https://raw.githubusercontent.com/YOUR-REPO/main/upload_code_for_ingestion.py
   python upload_code_for_ingestion.py /path/to/your/project --project-name my-app
   ```

**See:** [Cloud Ingestion Guide](CLOUD_INGESTION_GUIDE.md) for legacy upload details.

</details>

### 🔗 Connecting to Cloud Deployment

Once you've deployed Code Index MCP to the cloud, configure your MCP client to connect via HTTP/SSE:

#### Google Cloud Run

1. **Get your API key** from your administrator or generate one:
   ```bash
   cd deployment/gcp
   ./setup-secrets.sh YOUR_NAME read,write
   ```

2. **Add to your MCP configuration** (e.g., `claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "code-index-cloud": {
         "url": "https://code-index-mcp-dev-XXXX.run.app/sse",
         "transport": "sse",
         "headers": {
           "X-API-Key": "ci_your_api_key_here"
         }
       }
     }
   }
   ```

3. **Restart your MCP client** - The server is now ready for team collaboration!

**Note:** Replace `XXXX` with your Cloud Run service identifier and `ci_your_api_key_here` with your actual API key.

#### AWS Lambda / OpenShift

Configuration is similar - see the [Cloud Deployment Guide](docs/DEPLOYMENT.md#configuring-mcp-clients) for platform-specific URLs and authentication details.

**Benefits of Cloud Mode:**
- 🌐 Access from anywhere (no local installation needed)
- 👥 Share with your team (multi-user support)
- 🔍 Semantic code search (with vector embeddings)
- 💰 Pay per use (scales to $0 when idle)
- 🔐 API key authentication (secure team access)

## Typical Use Cases

**Code Review**: "Find all places using the old API"
**Refactoring Help**: "Where is this function called?"
**Learning Projects**: "Show me the main components of this React project"
**Debugging**: "Search for all error handling related code"

## Key Features

### 🔍 **Intelligent Search & Analysis**
- **Dual-Strategy Architecture**: Specialized tree-sitter parsing for 7 core languages, fallback strategy for 50+ file types
- **Direct Tree-sitter Integration**: No regex fallbacks for specialized languages - fail fast with clear errors
- **Advanced Search**: Auto-detects and uses the best available tool (ugrep, ripgrep, ag, or grep)
- **Universal File Support**: Comprehensive coverage from advanced AST parsing to basic file indexing
- **File Analysis**: Deep insights into structure, imports, classes, methods, and complexity metrics after running `build_deep_index`

### 🗂️ **Multi-Language Support**
- **7 Languages with Tree-sitter AST Parsing**: Python, JavaScript, TypeScript, Java, Go, Objective-C, Zig
- **50+ File Types with Fallback Strategy**: C/C++, Rust, Ruby, PHP, and all other programming languages
- **Document & Config Files**: Markdown, JSON, YAML, XML with appropriate handling
- **Web Frontend**: Vue, React, Svelte, HTML, CSS, SCSS
- **Database**: SQL variants, NoSQL, stored procedures, migrations
- **Configuration**: JSON, YAML, XML, Markdown
- **[View complete list](#supported-file-types)**

### ⚡ **Real-time Monitoring & Auto-refresh**
- **File Watcher**: Automatic index updates when files change
- **Cross-platform**: Native OS file system monitoring
- **Smart Processing**: Batches rapid changes to prevent excessive rebuilds
- **Shallow Index Refresh**: Watches file changes and keeps the file list current; run a deep rebuild when you need symbol metadata

### ⚡ **Performance & Efficiency**
- **Tree-sitter AST Parsing**: Native syntax parsing for accurate symbol extraction
- **Persistent Caching**: Stores indexes for lightning-fast subsequent access
- **Smart Filtering**: Intelligent exclusion of build directories and temporary files
- **Memory Efficient**: Optimized for large codebases
- **Direct Dependencies**: No fallback mechanisms - fail fast with clear error messages

## Supported File Types

<details>
<summary><strong>📁 Programming Languages (Click to expand)</strong></summary>

**Languages with Specialized Tree-sitter Strategies:**
- **Python** (`.py`, `.pyw`) - Full AST analysis with class/method extraction and call tracking
- **JavaScript** (`.js`, `.jsx`, `.mjs`, `.cjs`) - ES6+ class and function parsing with tree-sitter
- **TypeScript** (`.ts`, `.tsx`) - Complete type-aware symbol extraction with interfaces
- **Java** (`.java`) - Full class hierarchy, method signatures, and call relationships
- **Go** (`.go`) - Struct methods, receiver types, and function analysis
- **Objective-C** (`.m`, `.mm`) - Class/instance method distinction with +/- notation
- **Zig** (`.zig`, `.zon`) - Function and struct parsing with tree-sitter AST

**All Other Programming Languages:**
All other programming languages use the **FallbackParsingStrategy** which provides basic file indexing and metadata extraction. This includes:
- **System & Low-Level:** C/C++ (`.c`, `.cpp`, `.h`, `.hpp`), Rust (`.rs`)
- **Object-Oriented:** C# (`.cs`), Kotlin (`.kt`), Scala (`.scala`), Swift (`.swift`)
- **Scripting & Dynamic:** Ruby (`.rb`), PHP (`.php`), Shell (`.sh`, `.bash`)
- **And 40+ more file types** - All handled through the fallback strategy for basic indexing

</details>

<details>
<summary><strong>🌐 Web & Frontend (Click to expand)</strong></summary>

**Frameworks & Libraries:**
- Vue (`.vue`)
- Svelte (`.svelte`)
- Astro (`.astro`)

**Styling:**
- CSS (`.css`, `.scss`, `.less`, `.sass`, `.stylus`, `.styl`)
- HTML (`.html`)

**Templates:**
- Handlebars (`.hbs`, `.handlebars`)
- EJS (`.ejs`)
- Pug (`.pug`)

</details>

<details>
<summary><strong>🗄️ Database & SQL (Click to expand)</strong></summary>

**SQL Variants:**
- Standard SQL (`.sql`, `.ddl`, `.dml`)
- Database-specific (`.mysql`, `.postgresql`, `.psql`, `.sqlite`, `.mssql`, `.oracle`, `.ora`, `.db2`)

**Database Objects:**
- Procedures & Functions (`.proc`, `.procedure`, `.func`, `.function`)
- Views & Triggers (`.view`, `.trigger`, `.index`)

**Migration & Tools:**
- Migration files (`.migration`, `.seed`, `.fixture`, `.schema`)
- Tool-specific (`.liquibase`, `.flyway`)

**NoSQL & Modern:**
- Graph & Query (`.cql`, `.cypher`, `.sparql`, `.gql`)

</details>

<details>
<summary><strong>📄 Documentation & Config (Click to expand)</strong></summary>

- Markdown (`.md`, `.mdx`)
- Configuration (`.json`, `.xml`, `.yml`, `.yaml`)

</details>

### 🛠️ **Development Setup**

For contributing or local development:

1. **Clone and install:**
   ```bash
   git clone https://github.com/johnhuang316/code-index-mcp.git
   cd code-index-mcp
   uv sync
   ```

2. **Configure for local development:**
   ```json
   {
     "mcpServers": {
       "code-index": {
         "command": "uv",
         "args": ["run", "code-index-mcp"]
       }
     }
   }
   ```

3. **Debug with MCP Inspector:**
   ```bash
   npx @modelcontextprotocol/inspector uv run code-index-mcp
   ```

<details>
<summary><strong>Alternative: Manual pip Installation</strong></summary>

If you prefer traditional pip management:

```bash
pip install code-index-mcp
```

Then configure:
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


## Available Tools

### 🏗️ **Project Management**
| Tool | Description |
|------|-------------|
| **`set_project_path`** | Initialize indexing for a project directory |
| **`refresh_index`** | Rebuild the shallow file index after file changes |
| **`build_deep_index`** | Generate the full symbol index used by deep analysis |
| **`get_settings_info`** | View current project configuration and status |

*Run `build_deep_index` when you need symbol-level data; the default shallow index powers quick file discovery.*

### 🔍 **Search & Discovery**
| Tool | Description |
|------|-------------|
| **`search_code_advanced`** | Smart search with regex, fuzzy matching, and file filtering |
| **`find_files`** | Locate files using glob patterns (e.g., `**/*.py`) |
| **`get_file_summary`** | Analyze file structure, functions, imports, and complexity (requires deep index) |

### 🔄 **Monitoring & Auto-refresh**
| Tool | Description |
|------|-------------|
| **`get_file_watcher_status`** | Check file watcher status and configuration |
| **`configure_file_watcher`** | Enable/disable auto-refresh and configure settings |

### 🛠️ **System & Maintenance**
| Tool | Description |
|------|-------------|
| **`create_temp_directory`** | Set up storage directory for index data |
| **`check_temp_directory`** | Verify index storage location and permissions |
| **`clear_settings`** | Reset all cached data and configurations |
| **`refresh_search_tools`** | Re-detect available search tools (ugrep, ripgrep, etc.) |

## Usage Examples

### 🎯 **Quick Start Workflow**

**1. Initialize Your Project**
```
Set the project path to /Users/dev/my-react-app
```
*Automatically indexes your codebase and creates searchable cache*

**2. Explore Project Structure**
```
Find all TypeScript component files in src/components
```
*Uses: `find_files` with pattern `src/components/**/*.tsx`*

**3. Analyze Key Files**
```
Give me a summary of src/api/userService.ts
```
*Uses: `get_file_summary` to show functions, imports, and complexity*
*Tip: run `build_deep_index` first if you get a `needs_deep_index` response.*

### 🔍 **Advanced Search Examples**

<details>
<summary><strong>Code Pattern Search</strong></summary>

```
Search for all function calls matching "get.*Data" using regex
```
*Finds: `getData()`, `getUserData()`, `getFormData()`, etc.*

</details>

<details>
<summary><strong>Fuzzy Function Search</strong></summary>

```
Find authentication-related functions with fuzzy search for 'authUser'
```
*Matches: `authenticateUser`, `authUserToken`, `userAuthCheck`, etc.*

</details>

<details>
<summary><strong>Language-Specific Search</strong></summary>

```
Search for "API_ENDPOINT" only in Python files
```
*Uses: `search_code_advanced` with `file_pattern: "*.py"`*

</details>

<details>
<summary><strong>Auto-refresh Configuration</strong></summary>

```
Configure automatic index updates when files change
```
*Uses: `configure_file_watcher` to enable/disable monitoring and set debounce timing*

</details>

<details>
<summary><strong>Project Maintenance</strong></summary>

```
I added new components, please refresh the project index
```
*Uses: `refresh_index` to update the searchable cache*

</details>

## Troubleshooting

### 🔄 **Auto-refresh Not Working**

If automatic index updates aren't working when files change, try:
- `pip install watchdog` (may resolve environment isolation issues)
- Use manual refresh: Call the `refresh_index` tool after making file changes
- Check file watcher status: Use `get_file_watcher_status` to verify monitoring is active

## Development & Contributing

### 🔧 **Building from Source**
```bash
git clone https://github.com/johnhuang316/code-index-mcp.git
cd code-index-mcp
uv sync
uv run code-index-mcp
```

### 🐛 **Debugging**
```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

### 🤝 **Contributing**

Contributions are welcome! Please feel free to submit a Pull Request.

**For Contributors**:
- See [AGENTS.md](AGENTS.md) for repository guidelines and coding standards
- Review [CLAUDE.md](CLAUDE.md) for comprehensive architecture documentation
- Check [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for planned features and roadmap

**Want to Implement Cloud Features?**
- Start with [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) for detailed task breakdowns
- Choose a platform: [Google Cloud](docs/adrs/0002-cloud-run-http-deployment-with-auto-cleanup.md), [AWS](docs/adrs/0006-aws-http-deployment-with-auto-cleanup.md), or [OpenShift](docs/adrs/0007-openshift-http-deployment-with-auto-cleanup.md)
- Follow the week-by-week implementation sequence
- All ADRs are documented in [docs/adrs/](docs/adrs/)

---

### 📜 **License**
[MIT License](LICENSE)

### 🌐 **Translations**
- [繁體中文](README_zh.md)
- [日本語](README_ja.md)
