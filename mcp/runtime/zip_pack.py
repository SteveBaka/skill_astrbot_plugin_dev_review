# [RUNTIME P2] Build market/GitHub-like plugin ZIPs for install/upload.
"""
Pack a local plugin directory into a ZIP suitable for:
  POST /api/v1/plugins/install/upload

Goal: contents ≈ GitHub "Download ZIP" / marketplace package:
  - Top-level folder = plugin directory name (usually astrbot_plugin_*)
  - Exclude files matching .gitignore (plugin root, then walk up to git root)
  - Always exclude common junk even if not listed in .gitignore

Exclusion priority:
  1. Hard denylist (safety; matches typical release hygiene)
  2. Aggregated .gitignore rules (pathspec if available, else stdlib fallback)
  3. Never pack outside plugin_dir
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# [RUNTIME] Always skip — even if .gitignore is missing/incomplete.
# Aligns with clean market/GitHub source trees (no venv, no pyc, no IDE).
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
}

HARD_EXCLUDE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dylib",
    ".egg",
)


@dataclass
class PackResult:
    """In-memory ZIP + diagnostics for agent debugging."""

    ok: bool
    zip_bytes: bytes = b""
    root_name: str = ""
    # [RUNTIME] Multipart filename from metadata.yaml (not directory basename alone)
    zip_filename: str = ""
    metadata_name: str = ""
    metadata_version: str = ""
    file_count: int = 0
    total_bytes_uncompressed: int = 0
    zip_bytes_size: int = 0
    included_sample: List[str] = field(default_factory=list)
    excluded_sample: List[str] = field(default_factory=list)
    gitignore_files: List[str] = field(default_factory=list)
    pathspec_engine: str = "none"
    error: Optional[str] = None
    error_kind: Optional[str] = None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _yaml_scalar_fields(text: str, keys: Sequence[str]) -> Dict[str, str]:
    """
    Best-effort metadata.yaml scalar parse (no full YAML required for name/version).

    Supports: name: foo / name: "foo" / name: 'foo'
    """
    out: Dict[str, str] = {}
    for key in keys:
        m = re.search(
            rf"(?m)^\s*{re.escape(key)}\s*:\s*[\"']?([^\s\"'#]+(?:[^\n\"'#]*?)?)[\"']?\s*(?:#.*)?$",
            text,
        )
        if m:
            val = m.group(1).strip().strip("\"'")
            if val:
                out[key] = val
    return out


def _safe_zip_token(s: str, *, max_len: int = 80) -> str:
    """Sanitize a metadata field for use in a .zip filename."""
    s = (s or "").strip()
    # common version prefixes
    if s.lower().startswith("v") and len(s) > 1 and s[1].isdigit():
        s = s[1:]
    s = re.sub(r"[^\w.\-]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("._-")
    if not s:
        return "plugin"
    return s[:max_len]


def zip_filename_from_metadata(
    *,
    metadata_name: str,
    metadata_version: str = "",
    fallback_root: str = "plugin",
) -> str:
    """
    Build upload filename from metadata.yaml fields.

    Preferred: {name}-{version}.zip  e.g. astrbot_plugin_mimo_tts-2.1.1.zip
    Fallback:  {name}.zip or {folder}.zip
    """
    name = _safe_zip_token(metadata_name) if metadata_name else _safe_zip_token(fallback_root)
    ver = _safe_zip_token(metadata_version) if metadata_version else ""
    if ver:
        return f"{name}-{ver}.zip"
    return f"{name}.zip"


def _collect_gitignore_paths(plugin_dir: Path) -> List[Path]:
    """
    Collect .gitignore from plugin_dir upward until filesystem root or .git.

    Later files in the list are closer to root; matching uses all patterns
    (pathspec: concatenated; fallback: any match excludes).
    """
    found: List[Path] = []
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


def _build_pathspec(gitignore_files: Sequence[Path]):
    """
    Prefer pathspec (gitignore semantics). Fallback: simple glob matcher.
    Returns (matcher, engine_name) where matcher.match_file(rel_posix) -> ignored?
    """
    patterns: List[str] = []
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
            # pathspec >=1.x prefers "gitignore"; older only has "gitwildmatch"
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

    # [RUNTIME] Minimal fallback — common gitignore patterns only
    compiled: List[Tuple[re.Pattern[str], bool]] = []
    for raw in patterns:
        neg = raw.startswith("!")
        body = raw[1:] if neg else raw
        # directory-only trailing /
        body = body.rstrip("/")
        # rough: ** and * 
        esc = re.escape(body).replace(r"\*\*", "<<<DD>>>").replace(r"\*", "[^/]*")
        esc = esc.replace("<<<DD>>>", ".*")
        if not body.startswith("/"):
            # match anywhere
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


def _hard_excluded(rel_parts: Sequence[str], name: str, is_dir: bool) -> bool:
    for part in rel_parts:
        if part in HARD_EXCLUDE_DIR_NAMES:
            return True
        if part.endswith(".egg-info"):
            return True
    if name in HARD_EXCLUDE_FILE_NAMES:
        return True
    if not is_dir:
        lower = name.lower()
        if any(lower.endswith(suf) for suf in HARD_EXCLUDE_SUFFIXES):
            return True
    return False


def pack_plugin_directory(plugin_path: str | Path) -> PackResult:
    """
    Walk plugin_path and produce an in-memory ZIP.

    Archive layout:
      <root_name>/metadata.yaml
      <root_name>/main.py
      ...
    where root_name = plugin directory basename (not parent).
    """
    try:
        root = Path(plugin_path).expanduser().resolve()
    except Exception as exc:  # noqa: BLE001
        return PackResult(
            ok=False,
            error=f"Invalid path: {exc}",
            error_kind="bad_path",
        )

    if not root.is_dir():
        return PackResult(
            ok=False,
            error=f"Not a directory: {root}",
            error_kind="bad_path",
        )

    # [RUNTIME] Minimal plugin shape (market-compatible)
    meta = root / "metadata.yaml"
    main_py = root / "main.py"
    if not meta.is_file():
        return PackResult(
            ok=False,
            error="metadata.yaml missing — not a plugin root",
            error_kind="not_a_plugin",
        )
    if not main_py.is_file():
        return PackResult(
            ok=False,
            error="main.py missing — not a plugin root",
            error_kind="not_a_plugin",
        )

    root_name = root.name
    if not root_name or root_name in (".", ".."):
        return PackResult(ok=False, error="Invalid plugin folder name", error_kind="bad_path")

    # [RUNTIME] ZIP download/upload name from metadata.yaml (name + version)
    try:
        meta_fields = _yaml_scalar_fields(_read_text(meta), ("name", "version"))
    except Exception:
        meta_fields = {}
    metadata_name = meta_fields.get("name", "")
    metadata_version = meta_fields.get("version", "")
    # Archive top-level folder: prefer metadata name (matches market/GitHub style)
    # when it looks like a plugin id; else keep directory basename.
    if metadata_name and re.match(r"^[A-Za-z0-9_.-]+$", metadata_name):
        archive_root = metadata_name
    else:
        archive_root = root_name
    zip_filename = zip_filename_from_metadata(
        metadata_name=metadata_name or archive_root,
        metadata_version=metadata_version,
        fallback_root=archive_root,
    )

    gi_files = _collect_gitignore_paths(root)
    matcher, engine = _build_pathspec(gi_files)

    included: List[Tuple[Path, str]] = []  # (abs, arcname)
    excluded_sample: List[str] = []
    unc_total = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dpath = Path(dirpath)
        rel_dir = dpath.relative_to(root)

        # prune dirs in-place
        keep_dirs: List[str] = []
        for dn in list(dirnames):
            sub_parts = (rel_dir.parts if str(rel_dir) != "." else ()) + (dn,)
            rel_sub = "/".join(sub_parts)
            if _hard_excluded(sub_parts, dn, True):
                if len(excluded_sample) < 40:
                    excluded_sample.append(f"{rel_sub}/ [hard]")
                continue
            # gitignore directory paths often listed with trailing /
            if matcher.match_file(rel_sub) or matcher.match_file(rel_sub + "/"):
                if len(excluded_sample) < 40:
                    excluded_sample.append(f"{rel_sub}/ [gitignore]")
                continue
            keep_dirs.append(dn)
        dirnames[:] = keep_dirs

        for fn in filenames:
            abs_f = dpath / fn
            if not abs_f.is_file():
                continue
            parts = (rel_dir.parts if str(rel_dir) != "." else ()) + (fn,)
            rel_posix = "/".join(parts)
            if _hard_excluded(parts, fn, False):
                if len(excluded_sample) < 40:
                    excluded_sample.append(f"{rel_posix} [hard]")
                continue
            if matcher.match_file(rel_posix):
                if len(excluded_sample) < 40:
                    excluded_sample.append(f"{rel_posix} [gitignore]")
                continue
            try:
                size = abs_f.stat().st_size
            except OSError:
                continue
            # Use archive_root (metadata name preferred) as ZIP top-level folder
            arc = f"{archive_root}/{rel_posix}"
            included.append((abs_f, arc))
            unc_total += size

    if not included:
        return PackResult(
            ok=False,
            error="No files to pack after exclusions",
            error_kind="empty_pack",
            root_name=archive_root,
            zip_filename=zip_filename,
            metadata_name=metadata_name,
            metadata_version=metadata_version,
            gitignore_files=[str(p) for p in gi_files],
            pathspec_engine=engine,
            excluded_sample=excluded_sample,
        )

    # Stable order for reproducible zips
    included.sort(key=lambda x: x[1])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_f, arc in included:
            # ZIP_DEFLATED; use fixed date optional — skip for simplicity
            zf.write(abs_f, arcname=arc)

    data = buf.getvalue()
    sample = [arc for _, arc in included[:25]]

    return PackResult(
        ok=True,
        zip_bytes=data,
        root_name=archive_root,
        zip_filename=zip_filename,
        metadata_name=metadata_name,
        metadata_version=metadata_version,
        file_count=len(included),
        total_bytes_uncompressed=unc_total,
        zip_bytes_size=len(data),
        included_sample=sample,
        excluded_sample=excluded_sample,
        gitignore_files=[str(p) for p in gi_files],
        pathspec_engine=engine,
    )
