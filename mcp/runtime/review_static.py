# [RUNTIME] AST-based static reviewer: deterministic checks mapped to FIX rules.
"""
Codified reviewer for AstrBot plugins (review/auto-fix-guide.md as executable
checks). Pure logic — no HTTP, no AstrBot instance — so it runs anywhere and
is fully unit-testable.

Scope: only checks that are *statically decidable* are implemented; judgment
calls (architecture, naming quality, business logic) stay with the LLM review
workflow (Phase A/B). Each finding links a FIX rule id so agents can jump to
review/auto-fix-guide.md for the fix pattern.

Severity:
  error   — will break at import/load/runtime (blocks install)
  warning — violates a mandatory skill rule; likely broken behavior
  info    — hygiene (unused imports, style-level rules)
"""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ── shared knowledge (kept in sync with server.py IMPORT_TABLE) ─

# wrong-import module paths that do not exist / must not be used
WRONG_IMPORT_MODULES = {
    "astrbot.api.logger": "from astrbot.api import logger  # FIX-00",
}

# symbols importable from astrbot.api directly is WRONG for these:
WRONG_FROM_API = {
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

DEPRECATED_FILTER_ATTRS = {"on_keyword", "on_full_match", "on_regex"}

GENERIC_PKG_NAMES = {"services", "handlers", "utils", "models", "core", "api", "common"}

# stdlib top-level modules we should not demand in requirements.txt
_STDLIB_HINT = {
    "os", "sys", "re", "io", "json", "time", "datetime", "asyncio", "typing",
    "pathlib", "collections", "functools", "itertools", "math", "random",
    "uuid", "hashlib", "base64", "urllib", "http", "logging", "traceback",
    "dataclasses", "enum", "abc", "contextlib", "tempfile", "shutil",
    "subprocess", "socket", "struct", "copy", "string", "textwrap", "types",
    "inspect", "importlib", "warnings", "unicodedata", "zoneinfo", "sqlite3",
    "csv", "html", "xml", "zipfile", "tarfile", "gzip", "secrets", "signal",
    "threading", "queue", "weakref", "numbers", "decimal", "fractions",
}


# packages bundled with AstrBot core — plugins may use them without declaring
# (verified against AstrBot requirements; keep conservative)
_ASTRBOT_BUNDLED = {
    "aiohttp", "pydantic", "quart", "yaml", "pyyaml", "loguru", "httpx",
    "aiosqlite", "PIL", "pillow", "apscheduler", "fastapi", "uvicorn",
    "starlette", "openai", "anthropic",
}


@dataclass
class Finding:
    rule: str            # FIX-xx or META-xx / REQ-xx
    severity: str        # error | warning | info
    file: str
    line: int
    message: str
    hint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewReport:
    ok: bool = True
    plugin_dir: str = ""
    files_checked: int = 0
    findings: List[Finding] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    def finalize(self) -> "ReviewReport":
        self.counts = {"error": 0, "warning": 0, "info": 0}
        for f in self.findings:
            self.counts[f.severity] = self.counts.get(f.severity, 0) + 1
        self.ok = self.counts["error"] == 0
        # stable order: severity then file/line
        sev_rank = {"error": 0, "warning": 1, "info": 2}
        self.findings.sort(key=lambda f: (sev_rank.get(f.severity, 9), f.file, f.line))
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "plugin_dir": self.plugin_dir,
            "files_checked": self.files_checked,
            "counts": self.counts,
            "findings": [f.to_dict() for f in self.findings],
            "error": self.error,
        }


# ── per-file AST checks ────────────────────────────────────────


class _FileChecker(ast.NodeVisitor):
    def __init__(self, rel_path: str, tree: ast.AST, source: str) -> None:
        self.rel = rel_path
        self.tree = tree
        self.source = source
        self.findings: List[Finding] = []
        self.imported_names: Dict[str, int] = {}      # name -> lineno
        self.used_names: Set[str] = set()
        self.top_level_modules: Set[str] = set()      # for requirements cross-check
        self.star_class_stack: List[bool] = []        # inside Star subclass?
        self.has_sys_path_insert = "sys.path.insert" in source

    def out(self, rule: str, sev: str, line: int, msg: str, hint: str = "") -> None:
        self.findings.append(Finding(rule, sev, self.rel, line, msg, hint))

    # -- imports --------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            self.top_level_modules.add(top)
            self.imported_names[alias.asname or top] = node.lineno
            if alias.name == "requests":
                self.out(
                    "FIX-04", "error", node.lineno,
                    "sync `requests` library imported",
                    "Use aiohttp or httpx (async) — requests blocks the event loop.",
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if node.level == 0:
            self.top_level_modules.add(mod.split(".")[0])
        if mod in WRONG_IMPORT_MODULES:
            self.out(
                "FIX-00", "error", node.lineno,
                f"import from non-existent module `{mod}`",
                f"Correct: {WRONG_IMPORT_MODULES[mod]}",
            )
        if mod == "astrbot.api":
            for alias in node.names:
                if alias.name in WRONG_FROM_API:
                    self.out(
                        "FIX-00", "error", node.lineno,
                        f"`{alias.name}` is not importable from astrbot.api",
                        f"Correct: {WRONG_FROM_API[alias.name]}",
                    )
        if mod == "requests" or mod.startswith("requests."):
            self.out(
                "FIX-04", "error", node.lineno,
                "sync `requests` library imported",
                "Use aiohttp or httpx (async).",
            )
        for alias in node.names:
            if alias.name != "*":
                self.imported_names[alias.asname or alias.name] = node.lineno
        self.generic_visit(node)

    # -- name usage (for unused-import) ---------------------------

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # deprecated filter APIs: filter.on_keyword etc.
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "filter"
            and node.attr in DEPRECATED_FILTER_ATTRS
        ):
            self.out(
                "FIX-21", "error", node.lineno,
                f"deprecated decorator filter.{node.attr} (removed in v4.x)",
                "Use @filter.event_message_type(...) + Python-side matching.",
            )
        # StarTools.get_data_dir outside Star subclass
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "StarTools"
            and node.attr == "get_data_dir"
            and not (self.star_class_stack and self.star_class_stack[-1])
        ):
            self.out(
                "FIX-27", "warning", node.lineno,
                "StarTools.get_data_dir() called outside a Star subclass",
                "Call it in the plugin's Star __init__ and pass data_dir to services.",
            )
        # register_llm_tool deprecated
        if node.attr == "register_llm_tool":
            self.out(
                "FIX-13", "warning", node.lineno,
                "register_llm_tool() is deprecated",
                "Use the @filter.llm_tool decorator.",
            )
        self.generic_visit(node)

    # -- classes / functions --------------------------------------

    def _is_star_subclass(self, node: ast.ClassDef) -> bool:
        for base in node.bases:
            name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
            if name == "Star":
                return True
        return False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        is_star = self._is_star_subclass(node)
        self.star_class_stack.append(is_star)

        if is_star:
            self._check_star_init(node)

        # FIX-20: dataclass mutable defaults
        if any(
            (isinstance(d, ast.Name) and d.id == "dataclass")
            or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
            or (isinstance(d, ast.Call) and (
                (isinstance(d.func, ast.Name) and d.func.id == "dataclass")
                or (isinstance(d.func, ast.Attribute) and d.func.attr == "dataclass")
            ))
            for d in node.decorator_list
        ):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(
                    stmt.value, (ast.Dict, ast.List, ast.Set)
                ):
                    self.out(
                        "FIX-20", "error", stmt.lineno,
                        "dataclass field with mutable literal default",
                        "Use field(default_factory=lambda: {...}) / field(default_factory=list).",
                    )

        self.generic_visit(node)
        self.star_class_stack.pop()

    def _check_star_init(self, node: ast.ClassDef) -> None:
        init = next(
            (s for s in node.body
             if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and s.name == "__init__"),
            None,
        )
        if init is None:
            return
        args = [a.arg for a in init.args.args]  # includes self
        has_super = any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "__init__"
            and isinstance(n.func.value, ast.Call)
            and isinstance(n.func.value.func, ast.Name)
            and n.func.value.func.id == "super"
            for n in ast.walk(init)
        )
        if not has_super:
            self.out(
                "FIX-01", "error", init.lineno,
                "Star subclass __init__ missing super().__init__(context)",
                "First line should be super().__init__(context).",
            )
        if "config" not in args:
            self.out(
                "FIX-22", "info", init.lineno,
                "__init__ does not accept `config: AstrBotConfig`",
                "Needed only if the plugin has _conf_schema.json; "
                "then also set self.config = config.",
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_handler(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_handler(node)
        self.generic_visit(node)

    def _handler_decorators(self, node) -> List[str]:
        found = []
        for d in node.decorator_list:
            target = d.func if isinstance(d, ast.Call) else d
            if isinstance(target, ast.Attribute):
                found.append(target.attr)
        return found

    def _check_handler(self, node) -> None:
        decs = self._handler_decorators(node)
        if "command" in decs or "command_group" in decs:
            if not (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                self.out(
                    "FIX-17", "warning", node.lineno,
                    f"@filter.command handler `{node.name}` missing docstring",
                    "Every @filter.command must have a docstring (shown in help).",
                )
            args = [a.arg for a in node.args.args]
            extra = [a for a in args if a not in ("self", "event")]
            if "command" in decs and extra:
                self.out(
                    "FIX-02", "warning", node.lineno,
                    f"command handler `{node.name}` has extra parameters {extra}",
                    "Prefer parsing event.message_str; extra params can raise "
                    "`got multiple values for argument`.",
                )
            if "command" in decs and not isinstance(node, ast.AsyncFunctionDef):
                self.out(
                    "FIX-29", "warning", node.lineno,
                    f"command handler `{node.name}` is not async",
                    "Handlers should be `async def`.",
                )

    # -- return-type check for Tool.call --------------------------

    def check_tool_exec_result(self) -> None:
        if "ToolExecResult" in self.source:
            # find the usage line
            for i, ln in enumerate(self.source.splitlines(), 1):
                if "ToolExecResult" in ln and not ln.strip().startswith("#"):
                    self.out(
                        "FIX-07", "warning", i,
                        "ToolExecResult referenced",
                        "Tool.call() should return str on Python 3.12.",
                    )
                    break

    def check_unused_imports(self) -> None:
        # attribute roots count as usage: handled via visit_Name(Load)
        for name, lineno in self.imported_names.items():
            if name == "*":
                continue
            if name not in self.used_names and f"{name}." not in self.source:
                self.out(
                    "FIX-23", "info", lineno,
                    f"unused import `{name}`",
                    "Remove unused imports before review.",
                )

    def run(self) -> "_FileChecker":
        self.visit(self.tree)
        self.check_tool_exec_result()
        self.check_unused_imports()
        return self


# ── metadata / requirements checks ─────────────────────────────

_META_REQUIRED = ("name", "desc", "version", "author")


def check_metadata(meta_path: Path, report: ReviewReport) -> Dict[str, str]:
    rel = meta_path.name
    fields: Dict[str, str] = {}
    if not meta_path.is_file():
        report.add(Finding("META-01", "error", rel, 0, "metadata.yaml missing"))
        return fields
    text = meta_path.read_text(encoding="utf-8", errors="replace")
    for key in (*_META_REQUIRED, "repo", "astrbot_version"):
        m = re.search(rf"(?m)^\s*{key}\s*:\s*[\"']?([^\n\"'#]+)", text)
        if m:
            fields[key] = m.group(1).strip()
    for key in _META_REQUIRED:
        if not fields.get(key):
            report.add(Finding(
                "META-02", "error", rel, 0, f"metadata.yaml missing required field `{key}`",
            ))
    name = fields.get("name", "")
    if name and not name.startswith("astrbot_plugin_"):
        report.add(Finding(
            "META-03", "warning", rel, 0,
            f"plugin name `{name}` missing astrbot_plugin_ prefix",
            "Naming rule: astrbot_plugin_*, lowercase, no spaces.",
        ))
    if name and re.search(r"[A-Z\s]", name):
        report.add(Finding(
            "META-03", "warning", rel, 0,
            f"plugin name `{name}` must be lowercase without spaces",
        ))
    av = fields.get("astrbot_version", "")
    # strip comparators to inspect the version literal itself (>=v4.16 → v4.16)
    av_literal = re.sub(r"^[<>=!~\s,]+", "", av)
    if av_literal.startswith("v"):
        report.add(Finding(
            "META-04", "warning", rel, 0,
            f"astrbot_version `{av}` must be PEP 440 (no v prefix)",
            'e.g. ">=4.16" not ">=v4.16".',
        ))
    return fields


def check_requirements(
    plugin_dir: Path, all_modules: Set[str], report: ReviewReport
) -> None:
    req = plugin_dir / "requirements.txt"
    declared: Set[str] = set()
    if req.is_file():
        for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s and not s.startswith(("#", "-")):
                pkg = re.split(r"[<>=!~\[;]", s)[0].strip().lower()
                if pkg:
                    declared.add(pkg.replace("-", "_"))
    local_names = {p.stem for p in plugin_dir.glob("*.py")} | {
        p.name for p in plugin_dir.iterdir() if p.is_dir()
    }
    third_party = {
        m for m in all_modules
        if m and m not in _STDLIB_HINT
        and not m.startswith("astrbot")
        and m not in local_names
        and m.lower() not in _ASTRBOT_BUNDLED
    }
    missing = sorted(
        m for m in third_party if m.lower().replace("-", "_") not in declared
    )
    for m in missing:
        report.add(Finding(
            "REQ-01", "warning", "requirements.txt", 0,
            f"third-party module `{m}` imported but not declared",
            "Add it to requirements.txt (AstrBot installs it on plugin install).",
        ))


def check_namespace(plugin_dir: Path, main_source: str, report: ReviewReport) -> None:
    generic = [
        p.name for p in plugin_dir.iterdir()
        if p.is_dir() and p.name in GENERIC_PKG_NAMES and (p / "__init__.py").exists()
    ]
    if generic and "sys.path.insert" not in main_source:
        report.add(Finding(
            "FIX-26", "warning", "main.py", 1,
            f"generic package dirs {generic} without sys.path.insert guard",
            "Add sys.path.insert(0, os.path.dirname(__file__)) at top of main.py "
            "to avoid cross-plugin namespace collisions.",
        ))


# ── entry point ────────────────────────────────────────────────


def review_plugin_directory(plugin_path: str | Path) -> ReviewReport:
    """Run all static checks against a plugin directory."""
    report = ReviewReport()
    try:
        root = Path(plugin_path).expanduser().resolve()
    except Exception as exc:  # noqa: BLE001
        report.error = f"Invalid path: {exc}"
        report.ok = False
        return report
    report.plugin_dir = str(root)

    if not root.is_dir():
        report.error = f"Not a directory: {root}"
        report.ok = False
        return report
    main_py = root / "main.py"
    if not main_py.is_file():
        report.error = "main.py missing — not a plugin root"
        report.ok = False
        return report

    check_metadata(root / "metadata.yaml", report)

    all_modules: Set[str] = set()
    main_source = ""
    py_files = sorted(
        p for p in root.rglob("*.py")
        if not any(part in ("__pycache__", ".venv", "venv", ".git") for part in p.parts)
    )
    for py in py_files:
        rel = str(py.relative_to(root))
        source = py.read_text(encoding="utf-8", errors="replace")
        if py == main_py:
            main_source = source
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            report.add(Finding(
                "SYNTAX", "error", rel, exc.lineno or 0,
                f"SyntaxError: {exc.msg}",
                "Fix before anything else — plugin cannot load.",
            ))
            continue
        checker = _FileChecker(rel, tree, source).run()
        report.findings.extend(checker.findings)
        all_modules |= checker.top_level_modules
        report.files_checked += 1

    check_requirements(root, all_modules, report)
    check_namespace(root, main_source, report)
    return report.finalize()
