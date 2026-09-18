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

# ── plugin identity ────────────────────────────────────────────

PLUGIN_NAME_RE = re.compile(r"^astrbot_plugin_[a-z0-9_]+$")

# Skill-generated plugin metadata default (NOT the official docs teaching example).
# Official plugin-new.md examples use ">=4.16,<5"; this skill encodes 4.27+ contracts
# (H1-B command args smoke, astrbot.api.web scaffold, log-level notes).
# Validated on production cores **4.27.4 and 4.28.1** (typed args / command_group /
# message_str remainder; no Star filter/API break in v4.28.1 tag surface).
# Raise to ">=4.28,<5" only when templates actually depend on 4.28-only APIs.
SCAFFOLD_ASTRBOT_VERSION = ">=4.27,<5"
OFFICIAL_TEACHING_ASTRBOT_VERSION = ">=4.16,<5"
# Production cores where skill contracts were smoke-tested
SKILL_VALIDATED_CORES = ("4.27.4", "4.28.1")

# ── FIX-00 import contracts ────────────────────────────────────

WRONG_IMPORT_MODULES: dict[str, str] = {
    "astrbot.api.logger": "from astrbot.api import logger  # FIX-00",
}

WRONG_FROM_API: dict[str, str] = {
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

DEPRECATED_FILTER_ATTRS: frozenset[str] = frozenset()

# Official @filter.<attr> surface, verified against tag/master source of
# astrbot/api/event/filter/__init__.py (provenance: repo tags, not changelogs —
# API-surface changes do not reliably appear in changelogs).
#   v3.4.0: command, command_group, event_message_type, regex,
#           platform_adapter_type, permission_type
#   v4.0.0: + custom_filter, on_astrbot_loaded, on_llm_request, on_llm_response,
#           llm_tool, on_decorating_result, after_message_sent
#   master: + on_agent_begin, on_agent_done, on_llm_tool_respond,
#           on_plugin_error, on_plugin_loaded, on_plugin_unloaded,
#           on_platform_loaded, on_using_llm_tool, on_waiting_llm_request,
#           EventMessageType(-Filter), PermissionType(-Filter),
#           PlatformAdapterType(-Filter), CustomFilter, EventType, MessageType
FILTER_ATTR_KNOWN: frozenset[str] = frozenset(
    {
        # v3.4.0 era
        "command",
        "command_group",
        "event_message_type",
        "regex",
        "platform_adapter_type",
        "permission_type",
        # v4.0.0 additions
        "custom_filter",
        "on_astrbot_loaded",
        "on_llm_request",
        "on_llm_response",
        "llm_tool",
        "on_decorating_result",
        "after_message_sent",
        # master additions
        "on_agent_begin",
        "on_agent_done",
        "on_llm_tool_respond",
        "on_plugin_error",
        "on_plugin_loaded",
        "on_plugin_unloaded",
        "on_platform_loaded",
        "on_using_llm_tool",
        "on_waiting_llm_request",
        # constants / filter classes re-exported for isinstance use
        "EventMessageType",
        "EventMessageTypeFilter",
        "PermissionType",
        "PermissionTypeFilter",
        "PlatformAdapterType",
        "PlatformAdapterTypeFilter",
        "CustomFilter",
    }
)

# [PROVENANCE] Version-sensitive contract entries carry their source so the
# drift checker (mcp/scripts/check_contract_drift.py) can re-verify each
# against the AstrBot repo, and entries without provenance cannot be enforced
# at error severity (lesson: FIX-21 once asserted an API that never existed).
#   source_type: "tag" (verified in tag source) | "changelog" | "pr"
CONTRACT_PROVENANCE: dict[str, dict[str, str]] = {
    "FIX-21": {
        "source_type": "tag",
        "ref": "astrbot/api/event/filter/__init__.py (v3.4.0..master)",
        "note": "on_keyword/on_full_match/on_regex never existed; rule now "
        "flags unknown filter attrs, not a removal claim.",
    },
    "FIX-13": {
        "source_type": "changelog+pr",
        "ref": "changelogs/v4.25.0.md, PR #8178",
        "note": "context.register_llm_tool() deprecated (decorator remains).",
    },
    "FIX-07": {
        "source_type": "pr",
        "ref": "docs/en/dev/star/guides/ai.md (llm tool return)",
        "note": "Tool.call() must return str on Python 3.12.",
    },
    "FIX-00": {
        "source_type": "tag",
        "ref": "astrbot/api/{__init__,event/__init__,star/__init__,provider/__init__,message_components/__init__}.py",
        "note": "Import surface verified against tag sources.",
    },
    "FIX-02": {
        "source_type": "tag+smoke",
        "ref": "docs/en/dev/star/guides/listen-message-event.md + "
        "AstrBot smoke astrbot_plugin_skill_probe v0.2.0 on **4.27.4 and 4.28.1**",
        "note": "Typed command params are official; work on 4.27.4 **and 4.28.1**. "
        "H1-B constrains models to annotated structured params or message_str "
        "remainder — not a blanket ban on function parameters.",
    },
    "public-api-web": {
        "source_type": "tag",
        "ref": "docs/en/dev/star/guides/plugin-pages.md + astrbot/api/web.py "
        "(still recommended on v4.28.1 tag)",
        "note": "New plugins use astrbot.api.web helpers; Quart remains a legacy load path.",
    },
    "public-api-adapter": {
        "source_type": "tag",
        "ref": "docs/en/dev/plugin-platform-adapter.md + astrbot/api/platform/__init__.py "
        "(v4.28.1 re-export unchanged)",
        "note": "register_platform_adapter public path is astrbot.api.platform; "
        "MessageSesion lives in core.platform.message_session (official docs).",
    },
}

# H1-B command arg policy (codegen / review contracts — single source for models)
COMMAND_ARG_POLICY = {
    "structured_types": frozenset({"int", "float", "bool"}),
    "free_text_types": frozenset({"str"}),
    "rule": (
        "structured → annotated typed params; free-text → event.message_str "
        "remainder after stripping command prefix; untyped extras forbidden"
    ),
    "message_str_includes_command": True,
    "runtime_smoke": (
        "AstrBot 4.27.4 and **4.28.1**: typed binding OK; missing/type → framework error"
    ),
}

# OpenAPI optional features — degrade on older cores instead of hard-fail.
# Source of truth for paths: mcp/runtime/openapi_caps.py OPENAPI_FEATURES.
# install_path (Scheme A) is the portable baseline on all cores.
OPENAPI_DEGRADATION_POLICY = (
    "newer endpoints (install/url, install/git, plugin update, changelog, "
    "validate/repo) are optional; tools return error_kind=openapi_unsupported|"
    "core_version_too_old with fallback=install_path when absent"
)

GENERIC_PKG_NAMES: frozenset[str] = frozenset(
    {"services", "handlers", "utils", "models", "core", "api", "common"}
)

# ── requirements / stdlib / bundled ────────────────────────────

STDLIB_TOP_LEVEL: frozenset[str] = frozenset(
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
        "glob",
        "fnmatch",
        "mimetypes",
        "wave",
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

ASTRBOT_BUNDLED: frozenset[str] = frozenset(
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

SCAFFOLD_TYPES: tuple[str, ...] = (
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
STAR_PLUGIN_TYPES: frozenset[str] = frozenset(
    {"command", "llm_tool", "session", "cron", "hook", "web", "agent"}
)

TYPE_REQUIREMENTS: dict[str, list[str]] = {
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
IMPORT_TABLE: dict[str, tuple[str, str | None]] = {
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
        # Official style is module alias, not a class export (components.py has no Comp class).
        "import astrbot.api.message_components as Comp",
        "from astrbot.api.message_components import Comp",
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
        # Official public API (plugin-platform-adapter.md + astrbot/api/platform/__init__.py).
        # Prefer public re-exports for next-core compatibility; core path also works.
        "from astrbot.api.platform import register_platform_adapter",
        "from astrbot.api import register_platform_adapter",
    ),
    "MessageSession": (
        "from astrbot.core.platform.message_session import MessageSession",
        None,
    ),
    "MessageSesion": (
        # Official docs use the historical typo alias MessageSesion.
        "from astrbot.core.platform.message_session import MessageSesion",
        "from astrbot.core.platform.astr_message_event import MessageSesion",
    ),
    "At": ("from astrbot.api.message_components import At", None),
    "Record": ("from astrbot.api.message_components import Record", None),
    "Video": ("from astrbot.api.message_components import Video", None),
    "html_renderer": ("from astrbot.api import html_renderer", None),
    # Official plugin-pages.md: prefer astrbot.api.web over raw Quart for new plugins.
    "request": (
        "from astrbot.api.web import request",
        "from quart import request",
    ),
    "json_response": (
        "from astrbot.api.web import json_response",
        "from quart import jsonify",
    ),
    "error_response": (
        "from astrbot.api.web import error_response",
        None,
    ),
    "file_response": (
        "from astrbot.api.web import file_response",
        None,
    ),
    "stream_response": (
        "from astrbot.api.web import stream_response",
        None,
    ),
    "PluginUploadFile": (
        "from astrbot.api.web import PluginUploadFile",
        None,
    ),
}


def lookup_import(symbol: str) -> tuple[str, str | None] | None:
    """Return (correct, wrong_or_none) for exact symbol, or None."""
    return IMPORT_TABLE.get((symbol or "").strip())


def fuzzy_import_symbols(symbol: str, limit: int = 5) -> list[str]:
    s = (symbol or "").strip().lower()
    if not s:
        return []
    return [k for k in IMPORT_TABLE if s in k.lower()][:limit]


SCAFFOLD_IMPORT_LINES: dict[str, list[str]] = {
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
        # Official guides/plugin-pages.md — prefer astrbot.api.web (quart still bundled for legacy)
        "from astrbot.api.web import json_response, request",
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
        # Official plugin-platform-adapter.md public surface
        "from astrbot.api.platform import (",
        "    Platform,",
        "    AstrBotMessage,",
        "    MessageMember,",
        "    MessageType,",
        "    PlatformMetadata,",
        "    register_platform_adapter,",
        ")",
        "from astrbot.core.platform.message_session import MessageSesion",
    ],
}

# FIX-06 oriented: attribute names that commonly collide with Platform base.
# Heuristic for adapter profile review — not exhaustive of core source.
ADAPTER_PLATFORM_RESERVED_ATTRS: frozenset[str] = frozenset(
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
ADAPTER_CONFIG_CORE_INJECTED_KEYS: frozenset[str] = frozenset({"id", "enable", "type"})

# Core SHARED platform metadata field names (astrbot/core/config/default.py
# platform_group.metadata.platform.items + register.py injects). config_service
# merges every adapter's config_metadata into this ONE dict by field name via
# items.update(...) — redefining these names overwrites the built-in entry
# (and its condition) for ALL adapters' forms. Prefix custom fields instead.
ADAPTER_CONFIG_CORE_BUILTIN_KEYS: frozenset[str] = frozenset(
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

ADAPTER_REQUIRED_METHODS: frozenset[str] = frozenset({"run", "meta", "send_by_session"})


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
        return f"invalid adapter id {n!r}: use lowercase [a-z][a-z0-9_]*, length 2-64"
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
