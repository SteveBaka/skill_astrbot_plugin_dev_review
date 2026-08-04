# [RUNTIME S0] Shared contracts for review_static + scaffold (single source of truth).
"""
Machine-readable rules shared by:
  - review_static (AST checks → FIX ids)
  - scaffold_plugin (emit only compliant skeletons)
  - adapter review profile (FIX-06 oriented, separate from Star plugins)

Do not duplicate these tables in templates or checklists without updating here.
Authority for API semantics remains official AstrBot docs; this file encodes
the *statically enforceable* subset used for one-shot green generation.
"""

from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Tuple

# ── plugin identity ────────────────────────────────────────────

PLUGIN_NAME_RE = re.compile(r"^astrbot_plugin_[a-z0-9_]+$")

# ── FIX-00 import contracts ────────────────────────────────────

WRONG_IMPORT_MODULES: Dict[str, str] = {
    "astrbot.api.logger": "from astrbot.api import logger  # FIX-00",
}

WRONG_FROM_API: Dict[str, str] = {
    "filter": "from astrbot.api.event import filter",
    "AstrMessageEvent": "from astrbot.api.event import AstrMessageEvent",
    "Star": "from astrbot.api.star import Star",
    "Context": "from astrbot.api.star import Context",
    "StarTools": "from astrbot.api.star import StarTools",
    "ProviderRequest": "from astrbot.api.provider import ProviderRequest",
    "LLMResponse": "from astrbot.api.provider import LLMResponse",
    "Plain": "from astrbot.api.message_components import Plain",
    "Image": "from astrbot.api.message_components import Image",
    "MessageChain": "from astrbot.api.event import MessageChain",
    "session_waiter": "from astrbot.core.utils.session_waiter import session_waiter",
    "FunctionTool": "from astrbot.core.agent.tool import FunctionTool",
    "Platform": "from astrbot.api.platform import Platform",
}

DEPRECATED_FILTER_ATTRS: FrozenSet[str] = frozenset(
    {"on_keyword", "on_full_match", "on_regex"}
)

GENERIC_PKG_NAMES: FrozenSet[str] = frozenset(
    {"services", "handlers", "utils", "models", "core", "api", "common"}
)

# ── requirements / stdlib / bundled ────────────────────────────

STDLIB_TOP_LEVEL: FrozenSet[str] = frozenset(
    {
        "os",
        "sys",
        "re",
        "io",
        "json",
        "time",
        "datetime",
        "asyncio",
        "typing",
        "pathlib",
        "collections",
        "functools",
        "itertools",
        "math",
        "random",
        "uuid",
        "hashlib",
        "hmac",
        "base64",
        "urllib",
        "http",
        "logging",
        "traceback",
        "dataclasses",
        "enum",
        "abc",
        "contextlib",
        "tempfile",
        "shutil",
        "subprocess",
        "socket",
        "struct",
        "copy",
        "string",
        "textwrap",
        "types",
        "inspect",
        "importlib",
        "warnings",
        "unicodedata",
        "zoneinfo",
        "sqlite3",
        "csv",
        "html",
        "xml",
        "zipfile",
        "tarfile",
        "gzip",
        "secrets",
        "signal",
        "threading",
        "queue",
        "weakref",
        "numbers",
        "decimal",
        "fractions",
        "__future__",
    }
)

ASTRBOT_BUNDLED: FrozenSet[str] = frozenset(
    {
        "aiohttp",
        "pydantic",
        "quart",
        "yaml",
        "pyyaml",
        "loguru",
        "httpx",
        "aiosqlite",
        "PIL",
        "pillow",
        "apscheduler",
        "fastapi",
        "uvicorn",
        "starlette",
        "openai",
        "anthropic",
    }
)

# ── scaffold types ─────────────────────────────────────────────
# Full plugin-types set + adapter framework (S3). Adapter is not a Star plugin.

SCAFFOLD_TYPES: Tuple[str, ...] = (
    "command",
    "llm_tool",
    "session",
    "cron",
    "hook",
    "web",
    "agent",
    "adapter",
)

# Types that produce a normal Star plugin tree (metadata + main Star class)
STAR_PLUGIN_TYPES: FrozenSet[str] = frozenset(
    {"command", "llm_tool", "session", "cron", "hook", "web", "agent"}
)

TYPE_REQUIREMENTS: Dict[str, List[str]] = {
    "command": [],
    "llm_tool": ["aiohttp>=3.9.0"],
    "session": [],
    "cron": [],
    "hook": [],
    "web": [],  # quart is bundled
    "agent": ["aiohttp>=3.9.0"],
    "adapter": [],
}

# Docs MCP validate_import — single source (checklist §1 + FIX-00)
# symbol → (correct_import, common_wrong_or_None)
IMPORT_TABLE: Dict[str, Tuple[str, str | None]] = {
    "logger": (
        "from astrbot.api import logger",
        "from astrbot.api.logger import logger",
    ),
    "filter": (
        "from astrbot.api.event import filter",
        "from astrbot.api import filter",
    ),
    "AstrMessageEvent": (
        "from astrbot.api.event import AstrMessageEvent",
        "from astrbot.api import AstrMessageEvent",
    ),
    "Star": (
        "from astrbot.api.star import Star",
        "from astrbot.api import Star",
    ),
    "Context": (
        "from astrbot.api.star import Context",
        "from astrbot.api import Context",
    ),
    "StarTools": (
        "from astrbot.api.star import StarTools",
        "from astrbot.api import StarTools",
    ),
    "AstrBotConfig": ("from astrbot.api import AstrBotConfig", None),
    "ProviderRequest": (
        "from astrbot.api.provider import ProviderRequest",
        "from astrbot.api import ProviderRequest",
    ),
    "LLMResponse": (
        "from astrbot.api.provider import LLMResponse",
        "from astrbot.api import LLMResponse",
    ),
    "Comp": (
        "from astrbot.api.message_components import Comp",
        "from astrbot.api import Comp",
    ),
    "Plain": (
        "from astrbot.api.message_components import Plain",
        "from astrbot.api import Plain",
    ),
    "Image": (
        "from astrbot.api.message_components import Image",
        "from astrbot.api import Image",
    ),
    "MessageChain": (
        "from astrbot.api.event import MessageChain",
        "from astrbot.api import MessageChain",
    ),
    "session_waiter": (
        "from astrbot.core.utils.session_waiter import session_waiter",
        "from astrbot.api import session_waiter",
    ),
    "SessionController": (
        "from astrbot.core.utils.session_waiter import SessionController",
        None,
    ),
    "FunctionTool": (
        "from astrbot.core.agent.tool import FunctionTool",
        "from astrbot.api import FunctionTool",
    ),
    "ToolExecResult": (
        "from astrbot.core.agent.tool import ToolExecResult",
        None,
    ),
    "ToolSet": ("from astrbot.core.agent.tool import ToolSet", None),
    "ContextWrapper": (
        "from astrbot.core.agent.run_context import ContextWrapper",
        None,
    ),
    "AstrAgentContext": (
        "from astrbot.core.astr_agent_context import AstrAgentContext",
        None,
    ),
    "BaseAgentRunHooks": (
        "from astrbot.core.agent.hooks import BaseAgentRunHooks",
        None,
    ),
    "Platform": (
        "from astrbot.api.platform import Platform",
        "from astrbot.api import Platform",
    ),
    "PlatformMetadata": (
        "from astrbot.api.platform import PlatformMetadata",
        None,
    ),
    "AstrBotMessage": (
        "from astrbot.api.platform import AstrBotMessage",
        None,
    ),
    "MessageMember": (
        "from astrbot.api.platform import MessageMember",
        None,
    ),
    "MessageType": (
        "from astrbot.api.platform import MessageType",
        None,
    ),
    "register_platform_adapter": (
        "from astrbot.core.platform.register import register_platform_adapter",
        None,
    ),
    "At": ("from astrbot.api.message_components import At", None),
    "Record": ("from astrbot.api.message_components import Record", None),
    "Video": ("from astrbot.api.message_components import Video", None),
    "html_renderer": ("from astrbot.api import html_renderer", None),
}


def lookup_import(symbol: str) -> Tuple[str, str | None] | None:
    """Return (correct, wrong_or_none) for exact symbol, or None."""
    return IMPORT_TABLE.get((symbol or "").strip())


def fuzzy_import_symbols(symbol: str, limit: int = 5) -> List[str]:
    s = (symbol or "").strip().lower()
    if not s:
        return []
    return [k for k in IMPORT_TABLE if s in k.lower()][:limit]


SCAFFOLD_IMPORT_LINES: Dict[str, List[str]] = {
    "command": [
        "from astrbot.api import logger",
        "from astrbot.api.event import filter, AstrMessageEvent",
        "from astrbot.api.star import Context, Star",
    ],
    "llm_tool": [
        "import aiohttp",
        "from astrbot.api import logger",
        "from astrbot.api.event import filter, AstrMessageEvent",
        "from astrbot.api.star import Context, Star",
        "from pydantic import Field",
        "from pydantic.dataclasses import dataclass",
        "from astrbot.core.agent.tool import FunctionTool",
        "from astrbot.core.agent.run_context import ContextWrapper",
        "from astrbot.core.astr_agent_context import AstrAgentContext",
    ],
    "session": [
        "from astrbot.api import logger",
        "from astrbot.api.event import filter, AstrMessageEvent",
        "from astrbot.api.star import Context, Star",
        "from astrbot.core.utils.session_waiter import session_waiter, SessionController",
    ],
    "cron": [
        "import datetime",
        "from astrbot.api import logger",
        "from astrbot.api.event import filter, AstrMessageEvent",
        "from astrbot.api.star import Context, Star",
    ],
    "hook": [
        "from astrbot.api import logger",
        "from astrbot.api.event import filter, AstrMessageEvent",
        "from astrbot.api.provider import ProviderRequest, LLMResponse",
        "from astrbot.api.star import Context, Star",
    ],
    "web": [
        "import time",
        "from astrbot.api import logger",
        "from astrbot.api.event import filter, AstrMessageEvent",
        "from astrbot.api.star import Context, Star, StarTools",
        "from quart import jsonify",
    ],
    "agent": [
        "import aiohttp",
        "from astrbot.api import logger",
        "from astrbot.api.event import filter, AstrMessageEvent",
        "from astrbot.api.star import Context, Star",
        "from pydantic import Field",
        "from pydantic.dataclasses import dataclass",
        "from astrbot.core.agent.tool import FunctionTool",
        "from astrbot.core.agent.run_context import ContextWrapper",
        "from astrbot.core.astr_agent_context import AstrAgentContext",
    ],
    "adapter": [
        "import asyncio",
        "from astrbot.api import logger",
        "from astrbot.api.event import MessageChain",
        "from astrbot.api.message_components import Plain",
        "from astrbot.api.platform import Platform, PlatformMetadata",
        "from astrbot.core.platform.register import register_platform_adapter",
        "from astrbot.core.platform import AstrBotMessage, MessageMember, MessageType",
    ],
}

# FIX-06 oriented: attribute names that commonly collide with Platform base.
# Heuristic for adapter profile review — not exhaustive of core source.
ADAPTER_PLATFORM_RESERVED_ATTRS: FrozenSet[str] = frozenset(
    {
        "client",
        "config",
        "event_queue",
        "metadata",
        "platform_config",
        "platform_settings",
        "logger",
        "name",
        "id",
    }
)

# Keys that register_platform_adapter auto-fills when absent (official register.py).
# Authors should omit these from default_config_tmpl; re-listing is redundant and
# can confuse WebUI metadata — reviewer warns, does not hard-fail.
ADAPTER_CONFIG_CORE_INJECTED_KEYS: FrozenSet[str] = frozenset(
    {"id", "enable", "type"}
)

# Core SHARED platform metadata field names (astrbot/core/config/default.py
# platform_group.metadata.platform.items + register.py injects). config_service
# merges every adapter's config_metadata into this ONE dict by field name via
# items.update(...) — redefining these names overwrites the built-in entry
# (and its condition) for ALL adapters' forms. Prefix custom fields instead.
ADAPTER_CONFIG_CORE_BUILTIN_KEYS: FrozenSet[str] = frozenset(
    {
        "id",
        "enable",
        "type",
        "port",
        "callback_server_host",
        "unified_webhook_mode",
        "webhook_uuid",
    }
)

ADAPTER_REQUIRED_METHODS: FrozenSet[str] = frozenset({"run", "meta", "send_by_session"})


def validate_plugin_name(name: str) -> str | None:
    """Return error message if name invalid, else None."""
    n = (name or "").strip()
    if not n:
        return "plugin name is required (astrbot_plugin_<slug>)"
    if not PLUGIN_NAME_RE.match(n):
        return (
            f"invalid name {n!r}: must match ^astrbot_plugin_[a-z0-9_]+$ "
            "(lowercase, astrbot_plugin_ prefix)"
        )
    return None


def validate_adapter_id(adapter_id: str) -> str | None:
    """Adapter register id: lowercase slug without astrbot_plugin_ prefix requirement."""
    n = (adapter_id or "").strip()
    if not n:
        return "adapter id is required"
    if not re.match(r"^[a-z][a-z0-9_]{1,63}$", n):
        return (
            f"invalid adapter id {n!r}: use lowercase [a-z][a-z0-9_]*, length 2-64"
        )
    return None


def slug_to_class_name(plugin_name: str) -> str:
    """astrbot_plugin_foo_bar → FooBarPlugin."""
    raw = plugin_name.strip()
    if raw.startswith("astrbot_plugin_"):
        raw = raw[len("astrbot_plugin_") :]
    parts = [p for p in raw.split("_") if p]
    if not parts:
        return "MyPlugin"
    return "".join(p[:1].upper() + p[1:] for p in parts) + "Plugin"


def slug_to_adapter_class_name(adapter_id: str) -> str:
    parts = [p for p in adapter_id.strip().split("_") if p]
    if not parts:
        return "MyPlatformAdapter"
    return "".join(p[:1].upper() + p[1:] for p in parts) + "Adapter"


def command_default_from_name(plugin_name: str) -> str:
    """astrbot_plugin_foo_bar → foo_bar (command token)."""
    raw = plugin_name.strip()
    if raw.startswith("astrbot_plugin_"):
        raw = raw[len("astrbot_plugin_") :]
    return raw or "hello"
