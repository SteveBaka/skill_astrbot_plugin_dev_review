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

import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))

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


DOCS_INDEX = discover_docs(SKILL_ROOT)
ALL_CATEGORIES = sorted(DOCS_INDEX.keys())
TOTAL_DOCS = sum(len(v) for v in DOCS_INDEX.values())

# Import reference table (from review/main-file-checklist.md §1)
IMPORT_TABLE = {
    "logger": ("from astrbot.api import logger", "from astrbot.api.logger import logger"),
    "filter": ("from astrbot.api.event import filter", "from astrbot.api import filter"),
    "AstrMessageEvent": ("from astrbot.api.event import AstrMessageEvent", "from astrbot.api import AstrMessageEvent"),
    "Star": ("from astrbot.api.star import Star", "from astrbot.api import Star"),
    "Context": ("from astrbot.api.star import Context", "from astrbot.api import Context"),
    "StarTools": ("from astrbot.api.star import StarTools", "from astrbot.api import StarTools"),
    "AstrBotConfig": ("from astrbot.api import AstrBotConfig", None),
    "ProviderRequest": ("from astrbot.api.provider import ProviderRequest", "from astrbot.api import ProviderRequest"),
    "LLMResponse": ("from astrbot.api.provider import LLMResponse", "from astrbot.api import LLMResponse"),
    "Comp": ("from astrbot.api.message_components import Comp", "from astrbot.api import Comp"),
    "Plain": ("from astrbot.api.message_components import Plain", "from astrbot.api import Plain"),
    "Image": ("from astrbot.api.message_components import Image", "from astrbot.api import Image"),
    "MessageChain": ("from astrbot.api.event import MessageChain", "from astrbot.api import MessageChain"),
    "session_waiter": ("from astrbot.core.utils.session_waiter import session_waiter", "from astrbot.api import session_waiter"),
    "SessionController": ("from astrbot.core.utils.session_waiter import SessionController", None),
    "FunctionTool": ("from astrbot.core.agent.tool import FunctionTool", "from astrbot.api import FunctionTool"),
    "ToolExecResult": ("from astrbot.core.agent.tool import ToolExecResult", None),
    "ToolSet": ("from astrbot.core.agent.tool import ToolSet", None),
    "ContextWrapper": ("from astrbot.core.agent.run_context import ContextWrapper", None),
    "AstrAgentContext": ("from astrbot.core.astr_agent_context import AstrAgentContext", None),
    "BaseAgentRunHooks": ("from astrbot.core.agent.hooks import BaseAgentRunHooks", None),
    "Platform": ("from astrbot.api.platform import Platform", "from astrbot.api import Platform"),
    "PlatformMetadata": ("from astrbot.api.platform import PlatformMetadata", None),
    "AstrBotMessage": ("from astrbot.api.platform import AstrBotMessage", None),
    "MessageMember": ("from astrbot.api.platform import MessageMember", None),
    "MessageType": ("from astrbot.api.platform import MessageType", None),
    "register_platform_adapter": ("from astrbot.core.platform.register import register_platform_adapter", None),
    "At": ("from astrbot.api.message_components import At", None),
    "Record": ("from astrbot.api.message_components import Record", None),
    "Video": ("from astrbot.api.message_components import Video", None),
    "html_renderer": ("from astrbot.api import html_renderer", None),
}


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
        f"**Categories**: {len(ALL_CATEGORIES)} | **Documents**: {TOTAL_DOCS} | **Root**: `{SKILL_ROOT}`",
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
    for cat in ALL_CATEGORIES:
        count = len(DOCS_INDEX[cat])
        lines.append(f"- **{cat}** ({count} docs)")
    lines.append("")
    lines.append("Use `list_docs` to see all documents, `get_doc` to read one, `search_docs` to search.")
    return "\n".join(lines)


@mcp.tool()
def list_docs(category: str = "") -> str:
    """List all available document categories and their documents. Pass a category name to filter."""
    if category:
        if category not in DOCS_INDEX:
            return f"Unknown category: {category}. Available: {', '.join(ALL_CATEGORIES)}"
        lines = [f"## {category}\n"]
        for doc_id, desc in DOCS_INDEX[category].items():
            lines.append(f"- `{doc_id}`: {desc}")
        return "\n".join(lines)
    else:
        lines = [f"# AstrBot Skill Docs ({len(ALL_CATEGORIES)} categories, {TOTAL_DOCS} docs)\n"]
        for c in ALL_CATEGORIES:
            lines.append(f"## {c}")
            for doc_id, desc in DOCS_INDEX[c].items():
                lines.append(f"- `{doc_id}`: {desc}")
            lines.append("")
        return "\n".join(lines)


@mcp.tool()
def get_doc(category: str, doc_name: str) -> str:
    """Fetch a specific document by category and name. Use list_docs to discover available categories and documents."""
    fpath = _resolve_path(category, doc_name)
    if not os.path.exists(fpath):
        avail = ", ".join(DOCS_INDEX.get(category, {}).keys()) if category in DOCS_INDEX else "N/A"
        return f"Not found: {category}/{doc_name}.md\nAvailable in '{category}': {avail}"
    with open(fpath, "r", encoding="utf-8") as f:
        return f.read()


@mcp.tool()
def search_docs(query: str) -> str:
    """Search all documents for a keyword and return matching context with surrounding lines."""
    q = query.lower()
    results: List[str] = []
    for cat in ALL_CATEGORIES:
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
    if symbol in IMPORT_TABLE:
        correct, wrong = IMPORT_TABLE[symbol]
        result = f"**{symbol}**\n\n✅ Correct: `{correct}`"
        if wrong:
            result += f"\n❌ Common WRONG: `{wrong}`"
        return result

    # Fuzzy match
    matches = [k for k in IMPORT_TABLE if symbol.lower() in k.lower()]
    if matches:
        lines = [f"Symbol '{symbol}' not found exactly. Did you mean:"]
        for m in matches[:5]:
            correct, wrong = IMPORT_TABLE[m]
            lines.append(f"- `{m}` → `{correct}`")
        return "\n".join(lines)

    return f"Symbol '{symbol}' not in the reference table. Available: {', '.join(sorted(IMPORT_TABLE.keys()))}"


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
