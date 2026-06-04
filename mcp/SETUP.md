# MCP Server Setup

## 1. Create venv and install dependencies

```bash
cd skill_astrbot_plugin_dev_review/mcp
python3 -m venv .venv
.venv/bin/pip install mcp pyyaml uvicorn starlette
```

> Requires Python 3.10+. If your system Python is older, use the Python from astrbot-mcp's venv:
> ```bash
> /path/to/astrbot-mcp/.venv/bin/python3.12 -m venv .venv
> ```

## 2. Add to your MCP client config

```json
{
  "mcp": {
    "skill-astrbot-plugin": {
      "type": "local",
      "command": [
        "/your/actual/path/skill_astrbot_plugin_dev_review/mcp/.venv/bin/python3",
        "server.py"
      ],
      "cwd": "/your/actual/path/skill_astrbot_plugin_dev_review/mcp",
      "enabled": true
    }
  }
}
```

Config file locations:

| Client | Path |
|--------|------|
| Kilo | `~/.config/kilo/kilo.jsonc` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| VS Code | `~/.vscode/mcp.json` |

## 3. Verify

Restart your MCP client. You should see 6 tools:

| Tool | Description |
|------|-------------|
| `get_skill_info` | Get skill overview (categories, doc count, quick start) |
| `list_docs` | List all categories and documents |
| `get_doc(category, doc_name)` | Fetch a specific document |
| `search_docs(query)` | Search all documents by keyword |
| `validate_import(symbol)` | Check if an AstrBot import path is correct |
| `get_review_checklist(file_type)` | Get review checklist (main/general/metadata/adapter) |

## 4. SSE Mode (optional)

For MCP clients that don't support stdio, run in SSE mode:

```bash
MCP_TRANSPORT=sse MCP_PORT=3000 .venv/bin/python3 server.py
```

Then configure your client to connect to `http://localhost:3000/sse`.

## Troubleshooting

**"Executable not found: python3"**: Use the full absolute path to `.venv/bin/python3`.

**"ModuleNotFoundError: mcp"**: Make sure you're using the venv Python, not system Python.

**Tools not appearing**: Check that `cwd` points to the `mcp/` directory.
