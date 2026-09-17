"""Shared file filtering: hard denylist + .gitignore, for review and zip packing.

Two-layer approach:
  1. Hard denylist (HARD_EXCLUDE_*) — always excluded, .gitignore cannot override.
  2. .gitignore rules — collected from plugin dir upward, applied via pathspec.

Exports all names needed by consumers so each can stay single-purpose.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

# ── Hard denylist (safety floor) ────────────────────────────────

HARD_EXCLUDE_DIR_NAMES = {
    ".git",
    ".svn",
    ".hg",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    ".cursor",
    ".kilo",
    ".kilocode",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
}

HARD_EXCLUDE_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    ".coverage",
    "coverage.xml",
    ".error_kb.json",
}

HARD_EXCLUDE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dylib",
    ".egg",
)

# ── Utilities ────────────────────────────────────────────────────


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def collect_gitignore_paths(plugin_dir: Path) -> list[Path]:
    """Collect .gitignore from plugin_dir upward until filesystem root or .git.

    Later files in the list are closer to root; matching uses all patterns
    (pathspec: concatenated; fallback: any match excludes).
    """
    found: list[Path] = []
    cur = plugin_dir.resolve()
    for _ in range(32):
        gi = cur / ".gitignore"
        if gi.is_file():
            found.append(gi)
        if (cur / ".git").exists():
            break
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return found


def build_pathspec(gitignore_files: Sequence[Path]):
    """Prefer pathspec (gitignore semantics). Fallback: simple glob matcher.

    Returns (matcher, engine_name) where matcher.match_file(rel_posix) -> ignored?
    """
    patterns: list[str] = []
    for gi in gitignore_files:
        text = _read_text(gi)
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            patterns.append(s)

    try:
        import pathspec  # type: ignore

        if patterns:
            try:
                spec = pathspec.PathSpec.from_lines("gitignore", patterns)
            except KeyError:
                spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        else:
            spec = None

        class _PS:
            def match_file(self, rel: str) -> bool:
                if not spec:
                    return False
                return bool(spec.match_file(rel))

        return _PS(), "pathspec"
    except Exception:
        pass

    compiled: list[tuple[re.Pattern[str], bool]] = []
    for raw in patterns:
        neg = raw.startswith("!")
        body = raw[1:] if neg else raw
        body = body.rstrip("/")
        esc = re.escape(body).replace(r"\*\*", "<<<DD>>>").replace(r"\*", "[^/]*")
        esc = esc.replace("<<<DD>>>", ".*")
        if not body.startswith("/"):
            rx = re.compile(rf"(^|/)({esc})(/|$)")
        else:
            rx = re.compile(rf"^({esc.lstrip('/')})(/|$)")
        compiled.append((rx, neg))

    class _FB:
        def match_file(self, rel: str) -> bool:
            ignored = False
            for rx, neg in compiled:
                if rx.search(rel):
                    ignored = not neg
            return ignored

    return _FB(), "fallback"


def hard_excluded(rel_parts: Sequence[str], name: str, is_dir: bool) -> bool:
    """True if the file/dir at rel_parts + name should be unconditionally excluded."""
    for part in rel_parts:
        if part in HARD_EXCLUDE_DIR_NAMES:
            return True
        if part.endswith(".egg-info"):
            return True
        if part.startswith("$"):
            return True
    if name in HARD_EXCLUDE_FILE_NAMES:
        return True
    if name.startswith("$"):
        return True
    if not is_dir:
        lower = name.lower()
        if any(lower.endswith(suf) for suf in HARD_EXCLUDE_SUFFIXES):
            return True
    return False


def iter_plugin_py_files(plugin_dir: str | Path) -> list[Path]:
    """All .py files in plugin_dir passing hard-exclude + .gitignore filters.

    Returns sorted list of paths; caller must verify they still exist."""
    root = Path(plugin_dir).resolve()
    gi_files = collect_gitignore_paths(root)
    matcher, _ = build_pathspec(gi_files)

    result: list[Path] = []
    for py in sorted(root.rglob("*.py")):
        try:
            rel = py.relative_to(root)
        except ValueError:
            continue
        rel_posix = str(rel.as_posix())
        if hard_excluded(rel.parts, py.name, False):
            continue
        if matcher.match_file(rel_posix):
            continue
        result.append(py)
    return result
