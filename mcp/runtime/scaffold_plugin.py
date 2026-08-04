# [RUNTIME S1–S3] Deterministic scaffold (contracts-backed, multi-type + adapter frame).
"""
Generate a minimal plugin/adapter tree that must pass the matching reviewer
with severity error=0.

Star plugins: review_plugin_directory
Adapter frame: review_adapter_directory (FIX-06 oriented; full smoke later with user plugin)

Does not call AstrBot OpenAPI. Smoke only after user Dashboard config.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from .contracts import (
    SCAFFOLD_TYPES,
    STAR_PLUGIN_TYPES,
    TYPE_REQUIREMENTS,
    command_default_from_name,
    slug_to_adapter_class_name,
    slug_to_class_name,
    validate_adapter_id,
    validate_plugin_name,
)
from .review_static import review_adapter_directory, review_plugin_directory


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def default_workspace_dir() -> str:
    """Staging dir for scaffolds. Env ASTRBOT_DEV_WORKSPACE overrides; otherwise ~/.astrbot_skill_workspace.

    NEVER default to cwd: when the MCP runs inside AstrBot the cwd may be
    /AstrBot (container root), which produced confusing staging paths like
    /AstrBot/<plugin_name>/. The staging dir is irrelevant to where the plugin
    actually installs — install_path uploads it into <data>/plugins/<name>/.
    """
    env = (os.environ.get("ASTRBOT_DEV_WORKSPACE") or "").strip()
    if env:
        return env
    return str(Path.home() / ".astrbot_skill_workspace")


# Files agents may deliver directly via extra_files_json (whitelist, no traversal)
_EXTRA_FILE_ALLOW = frozenset(
    {"main.py", "metadata.yaml", "requirements.txt", "_conf_schema.json", "README.md"}
)


def _safe_cmd_token(command: str, plugin_name: str) -> str:
    c = (command or "").strip().lstrip("/")
    c = re.sub(r"[^a-z0-9_]", "_", c.lower())
    if not c:
        c = command_default_from_name(plugin_name)
    if c[0].isdigit():
        c = "cmd_" + c
    return c


def _render_metadata(name: str, author: str, desc: str, display: str) -> str:
    return (
        f"name: {name}\n"
        f"display_name: {display}\n"
        f"desc: {desc}\n"
        f"version: 0.1.0\n"
        f"author: {author}\n"
        f"repo: \n"
        f'astrbot_version: ">=4.26.8"\n'
    )


def _render_requirements(plugin_type: str) -> str:
    lines = TYPE_REQUIREMENTS.get(plugin_type) or []
    if not lines:
        return "# No third-party deps (stdlib + AstrBot only)\n"
    return "\n".join(lines) + "\n"


def _render_command_main(class_name: str, command: str, hello_text: str) -> str:
    return f'''from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class {class_name}(Star):
    """Scaffolded command plugin — fill BUSINESS sections only."""

    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        logger.info("{class_name} loaded")

    @filter.command("{command}")
    async def cmd_{command}(self, event: AstrMessageEvent):
        """{hello_text}"""
        # === BUSINESS START ===
        text = event.message_str.strip()
        user = event.get_sender_name()
        if not text:
            yield event.plain_result("Usage: /{command} <text>")
            return
        yield event.plain_result(f"Hello, {{user}}: {{text}}")
        # === BUSINESS END ===

    async def terminate(self):
        logger.info("{class_name} unloaded")
'''


def _render_llm_tool_main(
    class_name: str, command: str, tool_name: str, tool_desc: str
) -> str:
    return f'''import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext


@dataclass
class ScaffoldTool(FunctionTool[AstrAgentContext]):
    """LLM tool scaffold — replace URL/business in call()."""

    name: str = "{tool_name}"
    description: str = "{tool_desc}"
    parameters: dict = Field(
        default_factory=lambda: {{
            "type": "object",
            "properties": {{
                "query": {{
                    "type": "string",
                    "description": "User query string",
                }}
            }},
            "required": ["query"],
        }}
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> str:
        query = kwargs.get("query", "")
        if not query:
            return "Error: Missing 'query' parameter"
        # === BUSINESS START ===
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://httpbin.org/get"
                async with session.get(
                    url,
                    params={{"q": query}},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return f"Error: HTTP {{resp.status}}"
                    data = await resp.json()
                    return str(data.get("args", data))[:500]
        except aiohttp.ClientError as e:
            logger.error(f"ScaffoldTool network error: {{e}}")
            return f"Error: Network request failed: {{e}}"
        except Exception as e:
            logger.error(f"ScaffoldTool error: {{e}}")
            return f"Error: Query failed: {{e}}"
        # === BUSINESS END ===


class {class_name}(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(ScaffoldTool())

    async def initialize(self):
        logger.info("{class_name} loaded, ScaffoldTool registered")

    @filter.command("{command}")
    async def cmd_{command}(self, event: AstrMessageEvent):
        """Manual invoke scaffold tool. Usage: /{command} <query>"""
        query = event.message_str.strip()
        if not query:
            yield event.plain_result("Usage: /{command} <query>")
            return
        tool = ScaffoldTool()
        result = await tool.call(ContextWrapper(None), query=query)
        yield event.plain_result(result)

    async def terminate(self):
        logger.info("{class_name} unloaded")
'''


def _render_session_main(class_name: str, command: str) -> str:
    return f'''from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.utils.session_waiter import session_waiter, SessionController


class {class_name}(Star):
    """Session waiter scaffold — multi-turn; smoke hard-pass = first packet only."""

    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("{command}")
    async def cmd_{command}(self, event: AstrMessageEvent):
        """Start multi-turn session. Follow-up messages handled by waiter."""
        # === BUSINESS START ===
        yield event.plain_result(
            "Session started. Type your reply (or 'quit' to exit)."
        )

        @session_waiter(timeout=60)
        async def waiter(controller: SessionController, event: AstrMessageEvent):
            text = event.message_str.strip()
            if text.lower() == "quit":
                await event.send(event.plain_result("Session ended."))
                controller.stop()
                return
            # Replace with real multi-turn logic
            await event.send(event.plain_result(f"Got: {{text}} (type quit to exit)"))
            controller.keep(timeout=60, reset_timeout=True)

        try:
            await waiter(event)
        except TimeoutError:
            yield event.plain_result("Session timed out.")
        # === BUSINESS END ===

    async def terminate(self):
        logger.info("{class_name} unloaded")
'''


def _render_cron_main(class_name: str, command: str) -> str:
    job = "scaffold_job"
    return f'''import datetime
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class {class_name}(Star):
    """Cron scaffold — idempotent register (delete by job_id, not name alone)."""

    JOB_NAME = "{job}"

    def __init__(self, context: Context):
        super().__init__(context)
        self.cron_mgr = context.cron_manager

    async def initialize(self):
        try:
            await self._delete_jobs_by_name(self.JOB_NAME)
            await self.cron_mgr.add_basic_job(
                name=self.JOB_NAME,
                cron_expression="0 9 * * *",
                handler=self._cron_handler,
                persistent=True,
                description="Scaffold daily job 09:00",
                enabled=True,
            )
            logger.info("{class_name} cron registered (idempotent)")
        except Exception as e:
            logger.error(f"Cron register failed: {{e}}")

    async def _cron_handler(self, payload: dict = None):
        # === BUSINESS START ===
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        logger.info(f"Scaffold cron tick: {{now}}")
        # === BUSINESS END ===

    @staticmethod
    def _job_attr(job, *names, default=""):
        for n in names:
            if hasattr(job, n):
                return getattr(job, n)
            if isinstance(job, dict) and n in job:
                return job[n]
        return default

    async def _list_jobs_safe(self):
        result = self.cron_mgr.list_jobs()
        if hasattr(result, "__await__"):
            result = await result
        return result or []

    async def _delete_job_by_id(self, job_id: str):
        result = self.cron_mgr.delete_job(job_id)
        if hasattr(result, "__await__"):
            await result

    async def _delete_jobs_by_name(self, name: str) -> int:
        jobs = await self._list_jobs_safe()
        n = 0
        for job in jobs:
            jname = self._job_attr(job, "name", default="")
            jid = self._job_attr(job, "job_id", "id", default="")
            if jname == name and jid:
                try:
                    await self._delete_job_by_id(str(jid))
                    n += 1
                except Exception as e:
                    logger.warning(f"delete cron {{jid}}: {{e}}")
        return n

    @filter.command("{command}")
    async def cmd_{command}(self, event: AstrMessageEvent):
        """List cron jobs (shows job_id)."""
        try:
            jobs = await self._list_jobs_safe()
        except Exception as e:
            yield event.plain_result(f"List failed: {{e}}")
            return
        if not jobs:
            yield event.plain_result("No scheduled tasks")
            return
        lines = ["Scheduled tasks:"]
        for job in jobs:
            name = self._job_attr(job, "name", default="?")
            jid = self._job_attr(job, "job_id", "id", default="?")
            expr = self._job_attr(job, "cron_expression", "cron", default="?")
            lines.append(f"- {{name}} | id={{jid}} | {{expr}}")
        yield event.plain_result("\\n".join(lines))

    async def terminate(self):
        try:
            await self._delete_jobs_by_name(self.JOB_NAME)
        except Exception as e:
            logger.warning(f"cron cleanup: {{e}}")
'''


def _render_hook_main(class_name: str, command: str) -> str:
    return f'''from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest, LLMResponse
from astrbot.api.star import Context, Star


class {class_name}(Star):
    """LLM hook scaffold — no yield in on_llm_* hooks."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.enabled = True

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        if not self.enabled:
            return
        # === BUSINESS START ===
        injection = "Please answer concisely."
        if req.system_prompt:
            req.system_prompt += f"\\n{{injection}}"
        else:
            req.system_prompt = injection
        # === BUSINESS END ===

    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        if resp.completion_text:
            logger.debug(f"LLM response chars: {{len(resp.completion_text)}}")

    @filter.command("{command}")
    async def cmd_{command}(self, event: AstrMessageEvent):
        """Toggle hook on/off."""
        self.enabled = not self.enabled
        status = "enabled" if self.enabled else "disabled"
        yield event.plain_result(f"LLM hook {{status}}")

    async def terminate(self):
        logger.info("{class_name} unloaded")
'''


def _render_web_main(class_name: str, command: str, plugin_name: str) -> str:
    return f'''import time
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from quart import jsonify


PLUGIN_NAME = "{plugin_name}"


class {class_name}(Star):
    """Web API scaffold — StarTools.get_data_dir only on Star subclass."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.start_time = time.time()
        self.data_dir = None
        context.register_web_api(
            f"/{{PLUGIN_NAME}}/status",
            self.api_status,
            ["GET"],
            "Plugin status",
        )

    async def initialize(self):
        self.data_dir = StarTools.get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"{{PLUGIN_NAME}} data_dir={{self.data_dir}}")

    async def api_status(self):
        uptime = int(time.time() - self.start_time)
        return jsonify({{"status": "running", "uptime_seconds": uptime}})

    @filter.command("{command}")
    async def cmd_{command}(self, event: AstrMessageEvent):
        """Show registered Web API path."""
        yield event.plain_result(
            f"Status API: /api/plug/{{PLUGIN_NAME}}/status"
        )

    async def terminate(self):
        logger.info("{class_name} unloaded")
'''


def _render_agent_main(class_name: str, command: str) -> str:
    # Lightweight agent-style: tool + command (full tool_loop can be filled in BUSINESS)
    return f'''import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext


@dataclass
class AgentScaffoldTool(FunctionTool[AstrAgentContext]):
    name: str = "scaffold_agent_echo"
    description: str = "Echo query for agent-style plugin scaffold"
    parameters: dict = Field(
        default_factory=lambda: {{
            "type": "object",
            "properties": {{
                "query": {{"type": "string", "description": "Query"}},
            }},
            "required": ["query"],
        }}
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> str:
        q = kwargs.get("query", "")
        return f"echo: {{q}}" if q else "Error: Missing query"


class {class_name}(Star):
    """Agent-oriented scaffold — register tool; extend with tool_loop_agent in BUSINESS."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(AgentScaffoldTool())

    async def initialize(self):
        logger.info("{class_name} loaded")

    @filter.command("{command}")
    async def cmd_{command}(self, event: AstrMessageEvent):
        """Run scaffold agent tool. Usage: /{command} <query>"""
        query = event.message_str.strip()
        if not query:
            yield event.plain_result("Usage: /{command} <query>")
            return
        # === BUSINESS START ===
        tool = AgentScaffoldTool()
        result = await tool.call(ContextWrapper(None), query=query)
        yield event.plain_result(result)
        # === BUSINESS END ===

    async def terminate(self):
        logger.info("{class_name} unloaded")
'''


def _render_adapter_main(adapter_id: str, class_name: str) -> str:
    """Framework-only adapter: required methods + no reserved attr shadowing."""
    return f'''import asyncio
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain
from astrbot.api.platform import Platform, PlatformMetadata
from astrbot.api.star import Context, Star
from astrbot.core.platform.register import register_platform_adapter


@register_platform_adapter(
    "{adapter_id}",
    "Scaffold adapter framework — complete run/send before production use",
    # Official style: custom fields only. register.py injects type/enable/id if absent.
    # Do NOT add _conf_schema.json (Star plugin channel). See FIX-06 / register.py.
    default_config_tmpl={{"{adapter_id}_token": "", "{adapter_id}_base_url": ""}},
    config_metadata={{
        "{adapter_id}_token": {{
            "description": "Bot / API token",
            "type": "string",
            "hint": "Platform credential",
            "secret": True,
        }},
        "{adapter_id}_base_url": {{
            "description": "Service base URL",
            "type": "string",
            "hint": "https://…",
        }},
    }},
    adapter_display_name="{adapter_id}",
)
class {class_name}(Platform):
    """
    Adapter FRAME only (not a full working bridge).

    Implement BUSINESS: connect client, convert platform messages to AstrBotMessage,
    commit_event, and send_by_session. Smoke with a real adapter plugin when ready.
    """

    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: asyncio.Queue,
    ):
        super().__init__(platform_config, event_queue)
        self._settings = platform_settings
        self._running = False
        # Do NOT assign self.client / self.config / self.event_queue (FIX-06)

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="{adapter_id}",
            description="Scaffold platform adapter frame",
            id="{adapter_id}",
        )

    async def run(self):
        self._running = True
        logger.info("{class_name} run() started — replace with real client loop")
        # === BUSINESS START ===
        while self._running:
            await asyncio.sleep(3600)
        # === BUSINESS END ===

    async def send_by_session(self, session, message_chain: MessageChain):
        # === BUSINESS START ===
        logger.info(f"send_by_session stub session={{session}} chain={{message_chain}}")
        # === BUSINESS END ===

    async def terminate(self):
        self._running = False
        logger.info("{class_name} terminated")


# ── Star entry (REQUIRED dual registration, FIX-30) ────────────
# @register_platform_adapter only registers the platform; star_manager still
# needs a Star subclass to load this plugin dir. Missing it raises
# "未通过 Star 注册".


class {class_name}Plugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def terminate(self):
        logger.info("{class_name}Plugin unloaded")
'''


def _render_adapter_readme(adapter_id: str) -> str:
    return f"""# Adapter scaffold: `{adapter_id}`

This is a **framework-only** platform adapter (not a drop-in working bridge).

## Next steps

1. Fill `run()` with your platform client listen loop.
2. Convert inbound messages → `AstrBotMessage` and `commit_event(...)`.
3. Implement `send_by_session` for outbound `MessageChain`.
4. Read official: `docs/en/dev/plugin-platform-adapter.md` and skill `platform_adapters/adapter_interface.md`.
5. Static check: `astrbot_review_path` with adapter profile (or review after scaffold).
6. **Smoke**: provide a working adapter plugin instance — full E2E is not covered by WebChat smoke_suite.

## Config (official `astrbot/core/platform/register.py`)

1. Put **only custom** keys in `default_config_tmpl` (like FakePlatform docs).
2. Core **auto-fills** missing `type` / `enable` / `id` — prefer omit them in author tmpl.
3. **No `_conf_schema.json`** (Star plugin config only).
4. Avoid shadowing Platform `client` / event queue; use private names.
5. **Prefix custom fields** (`<adapter_id>_token` …): config_service merges every
   adapter's config_metadata into ONE shared dict by field name — redefining
   `port`/`callback_server_host`/`unified_webhook_mode`/`webhook_uuid` overwrites
   the built-in entry for ALL adapters' forms (FIX-32, real-world adapter collision).

## FIX-30 (dual registration — REQUIRED)

`@register_platform_adapter` registers the platform; the plugin dir **also** needs a
`Star` subclass (`XxxPlugin(Star)`) so star_manager loads it. This frame ships both.
Missing the Star class → "未通过 Star 注册".

Static: `astrbot_review_path(path, profile="adapter")`.
"""


def scaffold_plugin(
    name: str,
    author: str,
    *,
    plugin_type: str = "command",
    output_dir: str = "",
    command: str = "",
    display_name: str = "",
    desc: str = "",
    overwrite: bool = False,
    extra_files_json: str = "",
) -> Dict[str, Any]:
    """
    Create plugin or adapter-frame directory; run matching reviewer (error=0).

    extra_files_json: optional JSON object {relpath: content} to write on top of
    the generated skeleton (allowlist: main.py / metadata.yaml / requirements.txt
    / _conf_schema.json / README.md). This lets an agent deliver the COMPLETE
    plugin in one call (e.g. full main.py + _conf_schema.json) without needing a
    file-system tool, then upload via install_path.
    """
    ptype = (plugin_type or "command").strip().lower()
    if ptype not in SCAFFOLD_TYPES:
        return {
            "ok": False,
            "error_kind": "bad_type",
            "error": f"plugin_type must be one of {list(SCAFFOLD_TYPES)}, got {ptype!r}",
        }

    author = (author or "").strip()
    if not author:
        return {
            "ok": False,
            "error_kind": "bad_author",
            "error": "author is required (metadata.yaml author)",
        }

    # parse extra files (validate before writing anything)
    extra_files: Dict[str, str] = {}
    if (extra_files_json or "").strip():
        try:
            parsed = json.loads(extra_files_json)
            if not isinstance(parsed, dict):
                return {
                    "ok": False,
                    "error_kind": "bad_extra_files",
                    "error": "extra_files_json must be a JSON object {relpath: content}",
                }
            for rel, content in parsed.items():
                rel = str(rel).strip()
                if rel not in _EXTRA_FILE_ALLOW:
                    return {
                        "ok": False,
                        "error_kind": "bad_extra_files",
                        "error": (
                            f"disallowed file {rel!r}; allowed: "
                            f"{sorted(_EXTRA_FILE_ALLOW)}"
                        ),
                    }
                extra_files[rel] = str(content)
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "error_kind": "bad_extra_files",
                "error": f"extra_files_json is not valid JSON: {exc}",
            }

    # ── adapter frame (separate identity rules) ────────────────
    if ptype == "adapter":
        return _scaffold_adapter(
            name=name,
            author=author,
            output_dir=output_dir,
            display_name=display_name,
            desc=desc,
            overwrite=overwrite,
        )

    err = validate_plugin_name(name)
    if err:
        return {"ok": False, "error_kind": "bad_name", "error": err}

    name = name.strip()
    cmd = _safe_cmd_token(command, name)
    class_name = slug_to_class_name(name)
    display = (display_name or "").strip() or name.replace("astrbot_plugin_", "").replace(
        "_", " "
    ).title()
    description = (desc or "").strip() or f"Scaffolded {ptype} plugin ({name})"

    out_parent = (
        Path(output_dir).expanduser().resolve()
        if output_dir.strip()
        else Path(default_workspace_dir())
    )
    target = out_parent / name
    if target.exists() and any(target.iterdir()) and not overwrite:
        return {
            "ok": False,
            "error_kind": "exists",
            "error": f"directory not empty: {target} (pass overwrite=true to replace files)",
            "path": str(target),
        }

    target.mkdir(parents=True, exist_ok=True)

    if ptype == "command":
        main_py = _render_command_main(class_name, cmd, f"{display} command")
    elif ptype == "llm_tool":
        main_py = _render_llm_tool_main(
            class_name, cmd, f"scaffold_{cmd}"[:64], f"Scaffold tool for {display}"
        )
    elif ptype == "session":
        main_py = _render_session_main(class_name, cmd)
    elif ptype == "cron":
        main_py = _render_cron_main(class_name, cmd)
    elif ptype == "hook":
        main_py = _render_hook_main(class_name, cmd)
    elif ptype == "web":
        main_py = _render_web_main(class_name, cmd, name)
    elif ptype == "agent":
        main_py = _render_agent_main(class_name, cmd)
    else:
        return {"ok": False, "error_kind": "bad_type", "error": f"unhandled type {ptype}"}

    files = {
        "metadata.yaml": _render_metadata(name, author, description, display),
        "main.py": main_py,
        "requirements.txt": _render_requirements(ptype),
    }
    files.update(extra_files)  # agent-provided files win over skeleton

    written: List[str] = []
    for rel, content in files.items():
        (target / rel).write_text(content, encoding="utf-8")
        written.append(rel)

    report = review_plugin_directory(target)
    errors = [f.to_dict() for f in report.findings if f.severity == "error"]
    ok = report.ok and not errors

    result: Dict[str, Any] = {
        "ok": ok,
        "path": str(target),
        "plugin_name": name,
        "plugin_type": ptype,
        "class_name": class_name,
        "command": cmd,
        "files_written": written,
        "review": report.to_dict(),
        "review_profile": "plugin",
        "invariant": "scaffold_output_must_have_review_error_count_0",
        "smoke_note": (
            "Configure Dashboard (enable + profile plugin_set + schema) before smoke. "
            "session type: hard smoke = first packet only."
            if ptype == "session"
            else "Configure Dashboard before smoke_suite."
        ),
        "next_step": (
            "Review PASS (0 errors). Edit BUSINESS only; review_path → install_path → "
            "user Dashboard → smoke."
            if ok
            else "Scaffold invariant FAILED — fix templates/contracts."
        ),
    }
    if not ok:
        result["error_kind"] = "scaffold_review_failed"
        result["error"] = f"review reported {len(errors)} error(s) on fresh scaffold"
    return result


def _scaffold_adapter(
    *,
    name: str,
    author: str,
    output_dir: str,
    display_name: str,
    desc: str,
    overwrite: bool,
) -> Dict[str, Any]:
    """
    name is used as adapter_id (and folder astrbot_plugin_<id> or plain id folder).
    Prefer folder name astrbot_plugin_adapter_<id> if user passed full plugin-style name.
    """
    raw = (name or "").strip()
    # Allow astrbot_plugin_foo → adapter id foo, or plain myplatform
    if raw.startswith("astrbot_plugin_"):
        adapter_id = raw[len("astrbot_plugin_") :]
        folder = raw
    else:
        adapter_id = raw
        folder = f"astrbot_plugin_{adapter_id}" if not raw.startswith("astrbot_") else raw

    err = validate_adapter_id(adapter_id)
    if err:
        return {"ok": False, "error_kind": "bad_adapter_id", "error": err}

    # Still write metadata for packaging consistency when using plugin-style folder
    meta_err = validate_plugin_name(folder) if folder.startswith("astrbot_plugin_") else None
    if folder.startswith("astrbot_plugin_") and meta_err:
        # force valid folder
        folder = f"astrbot_plugin_{adapter_id}"

    class_name = slug_to_adapter_class_name(adapter_id)
    display = (display_name or "").strip() or adapter_id.replace("_", " ").title()
    description = (desc or "").strip() or f"Adapter frame for {adapter_id}"

    out_parent = (
        Path(output_dir).expanduser().resolve() if output_dir.strip() else Path.cwd()
    )
    target = out_parent / folder
    if target.exists() and any(target.iterdir()) and not overwrite:
        return {
            "ok": False,
            "error_kind": "exists",
            "error": f"directory not empty: {target}",
            "path": str(target),
        }
    target.mkdir(parents=True, exist_ok=True)

    main_py = _render_adapter_main(adapter_id, class_name)
    files = {
        "main.py": main_py,
        "metadata.yaml": _render_metadata(
            folder if folder.startswith("astrbot_plugin_") else f"astrbot_plugin_{adapter_id}",
            author,
            description,
            display,
        ),
        "requirements.txt": _render_requirements("adapter"),
        "ADAPTER_README.md": _render_adapter_readme(adapter_id),
    }
    # Fix metadata name to always be valid plugin-style for zip_pack
    meta_name = folder if folder.startswith("astrbot_plugin_") else f"astrbot_plugin_{adapter_id}"
    files["metadata.yaml"] = _render_metadata(meta_name, author, description, display)

    written: List[str] = []
    for rel, content in files.items():
        (target / rel).write_text(content, encoding="utf-8")
        written.append(rel)

    report = review_adapter_directory(target)
    errors = [f.to_dict() for f in report.findings if f.severity == "error"]
    ok = report.ok and not errors

    return {
        "ok": ok,
        "path": str(target),
        "plugin_name": meta_name,
        "adapter_id": adapter_id,
        "plugin_type": "adapter",
        "class_name": class_name,
        "files_written": written,
        "review": report.to_dict(),
        "review_profile": "adapter",
        "invariant": "adapter_scaffold_frame_review_error_count_0",
        "framework_only": True,
        "smoke_note": (
            "Adapter frame is NOT WebChat-smokeable. Provide a working adapter "
            "plugin later for E2E; static review only for now."
        ),
        "next_step": (
            "Fill BUSINESS in run/send_by_session; fetch official adapter docs; "
            "static review_path(profile=adapter). Full smoke when you supply a live adapter."
            if ok
            else "Adapter scaffold review failed — fix frame templates."
        ),
        **(
            {}
            if ok
            else {
                "error_kind": "scaffold_review_failed",
                "error": f"adapter review errors: {len(errors)}",
            }
        ),
    }


def astrbot_scaffold_plugin(
    name: str,
    author: str,
    plugin_type: str = "command",
    output_dir: str = "",
    command: str = "",
    display_name: str = "",
    desc: str = "",
    overwrite: bool = False,
    extra_files_json: str = "",
) -> str:
    """MCP entry: JSON string."""
    return _dumps(
        scaffold_plugin(
            name,
            author,
            plugin_type=plugin_type,
            output_dir=output_dir,
            command=command,
            display_name=display_name,
            desc=desc,
            overwrite=overwrite,
            extra_files_json=extra_files_json,
        )
    )
