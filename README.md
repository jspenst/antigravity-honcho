# Antigravity Honcho Plugin

<div align="center">
  <img src="assets/logo.svg" alt="Honcho Logo" width="120" />
  <p><strong>Persistent memory, background reasoning, and social cognition for Google Antigravity.</strong></p>
</div>

---

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Antigravity](https://img.shields.io/badge/Antigravity-2.0+-purple.svg)](https://antigravity.google)
[![Honcho](https://img.shields.io/badge/Honcho-v3-blue.svg)](https://honcho.dev)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://python.org)

This plugin integrates [Honcho](https://honcho.dev) directly into **Google Antigravity**, providing:
* **Transparent & Automatic Capture:** Every conversation turn is saved to Honcho automatically without manual tool calls, featuring secret/token redaction and long code block collapsing.
* **Session Start Context Injection:** When opening a chat, Antigravity automatically receives your Peer Card, user representation profile, and project summary.
* **Complete & Ultra-fast MCP Server:** On-demand tools to search past conversations (`search`), query the dialectic reasoning agent (`chat`, `workspace_chat`), and record durable preferences (`create_conclusions`).
* **Zero External Dependencies:** Built with pure Python using only standard library modules (`urllib`, `json`, `pathlib`), requiring no Node/Bun runtime on the client machine and eliminating boot-time failure risks.

---

## Quick Installation

### Option 1: Via Git (Recommended)

Clone the repository directly into your Antigravity plugins directory:

**Windows (PowerShell):**
```powershell
git clone https://github.com/jspenst/antigravity-honcho.git "$env:USERPROFILE\.gemini\config\plugins\honcho"
```

**Linux / macOS (Bash):**
```bash
git clone https://github.com/jspenst/antigravity-honcho.git ~/.gemini/config/plugins/honcho
```

### Option 2: 1-Line Installer

**Windows:**
```powershell
irm https://raw.githubusercontent.com/jspenst/antigravity-honcho/main/install.ps1 | iex
```

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/jspenst/antigravity-honcho/main/install.sh | bash
```

### Option 3: Per Project / Team

To share this plugin with your team via the project repository, place the folder in:
```text
your-project/
└── .agents/
    └── plugins/
        └── honcho/
```
Any developer opening the project with Antigravity will automatically have Honcho enabled.

> **Important:** Restart Antigravity after installation for the new plugin to be detected.

---

## Available MCP Tools

| Tool | Description |
| :--- | :--- |
| `get_peer_context` | Returns the Peer Card and consolidated user representation learned by Honcho |
| `chat` | Asks natural language questions about the user to Honcho's dialectic reasoning agent |
| `workspace_chat` | Cross-project query across all sessions and projects within the Honcho workspace |
| `search` | Hybrid search (semantic + BM25) across stored messages and past conversations |
| `query_conclusions` | Semantic search over facts and preferences inferred by Honcho |
| `list_conclusions` | Lists the most recent conclusions extracted by the system |
| `create_conclusions` | Immediately records a new durable preference, fact, or architectural decision |

---

## Configuration

The plugin automatically reads `~/.honcho/config.json` (shared with Claude Code, Cursor, Codex, and the Honcho CLI) or environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `HONCHO_URL` | `http://127.0.0.1:8000` | Honcho backend URL (local, Docker, or Tailscale) |
| `HONCHO_API_KEY` | *(empty)* | API key (optional for self-hosted instances with `AUTH_USE_AUTH=false`) |
| `HONCHO_WORKSPACE_ID` | `antigravity` | Honcho workspace where data is stored |
| `HONCHO_PEER_NAME` | `<OS username>` | Your human peer name |
| `HONCHO_SESSION_STRATEGY` | `project` | `project` (persistent session per repo) or `conversation` (isolated session per chat) |

### Example `~/.honcho/config.json`:
```json
{
  "schemaVersion": 1,
  "baseUrl": "http://127.0.0.1:8000",
  "workspace": "antigravity",
  "peerName": "developer",
  "enabled": true
}
```

---

## Validation and Diagnostics

To test connectivity with Honcho at any time:

```powershell
python honcho_hook.py --test
```

Expected output:
```text
=== Antigravity <-> Honcho Diagnostics ===
Active (enabled)  : True
Honcho Base URL   : http://127.0.0.1:8000
Workspace ID      : antigravity
User Peer         : developer
Agent Peer        : antigravity
Session Strategy  : project
State File        : C:\Users\...\.honcho\antigravity_state.json
Server Online     : YES
```

---

## License

Distributed under the [MIT](LICENSE) License.
