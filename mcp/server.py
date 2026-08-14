#!/usr/bin/env python3
"""
AstrBot Skill MCP Server
Self-contained MCP server embedded in the skill directory.
Auto-discovers all .md documentation from the skill root.

Usage:
    # stdio mode (default, for Kilo/Claude/Cursor)
    python mcp/server.py

    # SSE mode (for tools that don't support stdio)
    MCP_TRANSPORT=sse MCP_PORT=3000 python mcp/server.py
"""

import json
import os
import sys
from typing import Dict, List

from mcp.server.fastmcp import FastMCP

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))

# Ensure `import runtime` works for contracts / optional runtime tools
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Transport config from env
TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
SSE_HOST = os.environ.get("MCP_HOST", "localhost")
SSE_PORT = int(os.environ.get("MCP_PORT", "3000"))

mcp = FastMCP("skill-astrbot-plugin")


# ── Doc Discovery ──────────────────────────────────────────────

def discover_docs(root_path: str) -> Dict[str, Dict[str, str]]:
    """Auto-discover .md docs organized by subdirectory (category)."""
    index: Dict[str, Dict[str, str]] = {}
    skip = {"mcp", ".git", "__pycache__", "node_modules", ".DS_Store", ".venv"}

    for entry in sorted(os.listdir(root_path)):
        if entry in skip or entry.startswith("."):
            continue
        full = os.path.join(root_path, entry)
        if not os.path.isdir(full):
            continue

        docs: Dict[str, str] = {}
        for fname in sorted(os.listdir(full)):
            if not fname.endswith(".md"):
                continue
            doc_id = fname[:-3]
            fpath = os.path.join(full, fname)
            desc = f"{entry}/{doc_id}"
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        s = line.strip()
                        if s.startswith("# "):
                            desc = s[2:].strip()
                            break
                        elif s and s != "---":
                            break
            except Exception:
                pass
            docs[doc_id] = desc

        if docs:
            index[entry] = docs

    # Root-level .md files
    root_docs: Dict[str, str] = {}
    for fname in sorted(os.listdir(root_path)):
        if fname.endswith(".md") and os.path.isfile(os.path.join(root_path, fname)):
            doc_id = fname[:-3]
            root_docs[doc_id] = doc_id
    if root_docs:
        index["__root__"] = root_docs

    return index


# Docs index: prefer the PRECOMPUTED mcp/docs_index.json (millisecond load).
# Scanning + reading every .md takes ~30s on some volumes (SynologyDrive) and
# must NEVER run inside the MCP client's request window (30s timeout). Fall back
# to a live scan only if the json is missing (then cache in memory).
_DOCS_INDEX_JSON = os.path.join(SCRIPT_DIR, "docs_index.json")
_docs_cache: Dict[str, Dict[str, str]] | None = None


def _load_docs_index() -> Dict[str, Dict[str, str]]:
    try:
        with open(_DOCS_INDEX_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # fallback: live scan (slow on network/cloud volumes) — happens only when the
    # precomputed index is absent.
    return discover_docs(SKILL_ROOT)


def _get_docs_index() -> Dict[str, Dict[str, str]]:
    global _docs_cache
    if _docs_cache is None:
        _docs_cache = _load_docs_index()
    return _docs_cache


def _get_categories() -> list:
    return sorted(_get_docs_index().keys())


def _get_total_docs() -> int:
    return sum(len(v) for v in _get_docs_index().values())

# Import reference: single source mcp/runtime/contracts.py (checklist §1 + FIX-00)
def _load_import_table():
    try:
        from runtime.contracts import IMPORT_TABLE, fuzzy_import_symbols, lookup_import

        return IMPORT_TABLE, lookup_import, fuzzy_import_symbols
    except Exception:
        # Fallback if runtime package path broken — minimal FIX-00 set
        t = {
            "logger": (
                "from astrbot.api import logger",
                "from astrbot.api.logger import logger",
            ),
            "filter": (
                "from astrbot.api.event import filter",
                "from astrbot.api import filter",
            ),
            "Star": (
                "from astrbot.api.star import Star",
                "from astrbot.api import Star",
            ),
        }

        def _lookup(symbol: str):
            return t.get((symbol or "").strip())

        def _fuzzy(symbol: str, limit: int = 5):
            s = (symbol or "").strip().lower()
            return [k for k in t if s in k.lower()][:limit]

        return t, _lookup, _fuzzy


IMPORT_TABLE, _lookup_import, _fuzzy_import_symbols = _load_import_table()


def _resolve_path(category: str, doc_name: str) -> str:
    if category == "__root__":
        return os.path.join(SKILL_ROOT, f"{doc_name}.md")
    return os.path.join(SKILL_ROOT, category, f"{doc_name}.md")


# ── Tools ──────────────────────────────────────────────────────

@mcp.tool()
def get_skill_info() -> str:
    """Get an overview of the AstrBot Skill: categories, doc count, available review rules, and quick-start guide."""
    lines = [
        "# AstrBot Skill Overview",
        "",
        f"**Categories**: {len(_get_categories())} | **Documents**: {_get_total_docs()} | **Root**: `{SKILL_ROOT}`",
        "",
        "## Quick Start",
        "",
        "| Task | Read This |",
        "|------|-----------|",
        "| Create a plugin | `plugin-development-workflow.md` |",
        "| Pick plugin type | `plugin-types/README.md` |",
        "| Fix import errors | `review/main-file-checklist.md` §1 |",
        "| Review code | `review/review-workflow.md` |",
        "| Add LLM tools | `agent/tools.md` |",
        "| Add cron | `agent/cron.md` |",
        "| WebUI pages | `webui/plugin-pages.md` |",
        "| Split main.py | `references/modular-split.md` |",
        "",
        "## Categories",
        "",
    ]
    for cat in _get_categories():
        count = len(_get_docs_index()[cat])
        lines.append(f"- **{cat}** ({count} docs)")
    lines.append("")
    lines.append("Use `list_docs` to see all documents, `get_doc` to read one, `search_docs` to search.")
    return "\n".join(lines)


@mcp.tool()
def list_docs(category: str = "") -> str:
    """List all available document categories and their documents. Pass a category name to filter."""
    if category:
        if category not in _get_docs_index():
            return f"Unknown category: {category}. Available: {', '.join(_get_categories())}"
        lines = [f"## {category}\n"]
        for doc_id, desc in _get_docs_index()[category].items():
            lines.append(f"- `{doc_id}`: {desc}")
        return "\n".join(lines)
    else:
        lines = [f"# AstrBot Skill Docs ({len(_get_categories())} categories, {_get_total_docs()} docs)\n"]
        for c in _get_categories():
            lines.append(f"## {c}")
            for doc_id, desc in _get_docs_index()[c].items():
                lines.append(f"- `{doc_id}`: {desc}")
            lines.append("")
        return "\n".join(lines)


@mcp.tool()
def get_doc(category: str, doc_name: str) -> str:
    """Fetch a specific document by category and name. Use list_docs to discover available categories and documents."""
    fpath = _resolve_path(category, doc_name)
    if not os.path.exists(fpath):
        avail = ", ".join(_get_docs_index().get(category, {}).keys()) if category in _get_docs_index() else "N/A"
        return f"Not found: {category}/{doc_name}.md\nAvailable in '{category}': {avail}"
    with open(fpath, "r", encoding="utf-8") as f:
        return f.read()


@mcp.tool()
def search_docs(query: str) -> str:
    """Search all documents for a keyword and return matching context with surrounding lines."""
    q = query.lower()
    results: List[str] = []
    for cat in _get_categories():
        cat_path = SKILL_ROOT if cat == "__root__" else os.path.join(SKILL_ROOT, cat)
        if not os.path.isdir(cat_path):
            continue
        for fname in os.listdir(cat_path):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(cat_path, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            if q not in content.lower():
                continue
            matched: List[str] = []
            all_lines = content.split("\n")
            for i, line in enumerate(all_lines):
                if q in line.lower():
                    start = max(0, i - 2)
                    end = min(len(all_lines), i + 3)
                    matched.extend(all_lines[start:end])
                    matched.append("---")
            if matched:
                doc_id = fname[:-3]
                prefix = f"{cat}/" if cat != "__root__" else ""
                results.append(f"### {prefix}{doc_id}\n" + "\n".join(matched[:20]))
    if not results:
        return f"No documents found matching '{query}'"
    return "\n\n".join(results[:5])


@mcp.tool()
def validate_import(symbol: str) -> str:
    """Check if an AstrBot import path is correct. Returns the correct import and warns about common mistakes.

    Args:
        symbol: The symbol name to check (e.g. 'logger', 'filter', 'Star', 'FunctionTool')
    """
    symbol = symbol.strip()
    hit = _lookup_import(symbol)
    if hit:
        correct, wrong = hit
        result = f"**{symbol}**\n\n✅ Correct: `{correct}`"
        if wrong:
            result += f"\n❌ Common WRONG: `{wrong}`"
        return result

    matches = _fuzzy_import_symbols(symbol, limit=5)
    if matches:
        lines = [f"Symbol '{symbol}' not found exactly. Did you mean:"]
        for m in matches:
            pair = _lookup_import(m)
            if pair:
                lines.append(f"- `{m}` → `{pair[0]}`")
        return "\n".join(lines)

    return (
        f"Symbol '{symbol}' not in the reference table. "
        f"Available: {', '.join(sorted(IMPORT_TABLE.keys()))}"
    )


@mcp.tool()
def get_review_checklist(file_type: str = "main") -> str:
    """Get the review checklist for a specific file type. Use 'main' for main.py, 'general' for other .py files, 'metadata' for metadata.yaml, or 'adapter' for platform adapters."""
    checklists = {
        "main": """# main.py Review Checklist

## Quick Checks
- [ ] Import paths correct (use `validate_import` tool to verify)
- [ ] Star subclass with `super().__init__(context)` called
- [ ] If config used: `__init__(self, context, config: AstrBotConfig)` + `self.config = config`
- [ ] All handlers are `async def`
- [ ] All `@filter.command` have docstrings
- [ ] `@filter.command_group` uses function pattern (`def math(): pass`), NOT class
- [ ] `filter` from `astrbot.api.event`, `logger` from `astrbot.api`
- [ ] No `yield` in `on_llm_request`/`on_llm_response`/`on_decorating_result`/`after_message_sent`
- [ ] `context.add_llm_tools()` used (NOT deprecated `register_llm_tool()`)
- [ ] `terminate()` cleans up resources
- [ ] `system_prompt += ...` only for stable settings; use `extra_user_content_parts` for dynamic

## Import Reference (most common mistakes)
| Symbol | Correct | WRONG |
|--------|---------|-------|
| logger | `from astrbot.api import logger` | `from astrbot.api.logger import logger` |
| filter | `from astrbot.api.event import filter` | `from astrbot.api import filter` |
| Star | `from astrbot.api.star import Star` | `from astrbot.api import Star` |
""",
        "general": """# General Code Review Checklist

## Quick Checks
- [ ] No `requests.get()` in async context (use `aiohttp`)
- [ ] No hardcoded secrets (use `self.config`)
- [ ] No `os.system()` / `subprocess.call(shell=True)` with untrusted input
- [ ] Resources closed (files, connections)
- [ ] `requirements.txt` has all third-party deps (no `astrbot`, no `quart`)
- [ ] No `from astrbot.api.logger import logger` (must be `from astrbot.api import logger`)
- [ ] No global variables for plugin state
""",
        "metadata": """# metadata.yaml Validation

## Required Fields
- [ ] `name`: non-empty, `astrbot_plugin_` prefix recommended
- [ ] `desc` OR `description`: non-empty, NOT both
- [ ] `version`: non-empty (e.g. `v1.0.0`)
- [ ] `author`: non-empty
- [ ] `repo`: valid GitHub URL

## Optional Fields
- `display_name`, `short_desc`, `astrbot_version`, `support_platforms`, `tags`
- `logo.png` (1:1 ratio, 256x256 recommended)
- `skills/` directory for Skill definitions
""",
        "adapter": """# Platform Adapter Review

## config_metadata Rules
- [ ] `default_config_tmpl` does NOT include `"enable"` (AstrBot manages this)
- [ ] `default_config_tmpl` does NOT include `"id"` (AstrBot manages this)
- [ ] All custom fields have matching `config_metadata` entries
- [ ] `config_metadata` entries have `description`, `type`, `hint`
- [ ] `secret: True` for API keys/tokens
- [ ] `invisible: True` only for internal fields
""",
    }
    key = file_type.lower().strip()
    if key in checklists:
        return checklists[key]
    return f"Unknown file_type: '{file_type}'. Available: {', '.join(checklists.keys())}"


# ── Optional Runtime tools (P0 OpenAPI read-only) ──────────────
# [RUNTIME] Additive only: docs tools above are unchanged.
# If runtime package or httpx fails, Docs MCP must still start (stdio handshake).
# LAN: configure ASTRBOT_BASE_URL / ASTRBOT_TOKEN on MCP host env, not here.
try:
    # Ensure `import runtime` resolves when process cwd is not mcp/ (Kilo spawn).
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)
    from runtime.register import register_runtime_tools

    register_runtime_tools(mcp)
except Exception as _runtime_exc:  # noqa: BLE001 — never block docs MCP
    # stderr only: stdout is MCP JSON-RPC in stdio mode
    print(
        f"[skill-astrbot-plugin] runtime tools not loaded (docs OK): {_runtime_exc!r}",
        file=sys.stderr,
    )


# ── Entry Point ────────────────────────────────────────────────

def main():
    if TRANSPORT == "sse":
        import uvicorn
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await mcp._mcp_server.run(streams[0], streams[1], mcp._mcp_server.create_initialization_options())

        async def handle_messages(request):
            await sse.handle_post_message(request.scope, request.receive, request._send)

        starlette_app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        print(f"MCP SSE server running on http://{SSE_HOST}:{SSE_PORT}/sse")
        uvicorn.run(starlette_app, host=SSE_HOST, port=SSE_PORT)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
