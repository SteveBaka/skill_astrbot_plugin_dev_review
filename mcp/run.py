#!/usr/bin/env python3
# [RUNTIME] Self-bootstrapping MCP launcher for AstrBot.
"""
Zero-manual-setup entry point for AstrBot MCP.

Register the MCP server in AstrBot WebUI as:

    command: python3
    args:    ["<skill>/mcp/run.py"]
    env:     ASTRBOT_* (optional; docs tools work without)

Bootstrap order (fastest first):
  1. The current interpreter (`sys.executable`) can already import
     `mcp.server.fastmcp` — use it directly. This covers the AstrBot Docker
     container whose system Python already bundles the MCP SDK, so no venv and
     no pip are needed at all.
  2. An existing `.venv` that can import it — reuse it.
  3. Create `.venv` + install requirements.txt, verify import, then use it.
  4. Last resort: fall back to `sys.executable` (server.py will surface the
     real missing-module error in AstrBot logs).

Failures are printed to stderr (not swallowed) so AstrBot's log pipe shows the
actual cause on a failed test-connection.

Why not a shell script: AstrBot's MCP stdio allowlist blocks bash/sh and any
`-c` inline python — `python3 <file>` is the sanctioned shape.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE / "server.py"
REQS = HERE / "requirements.txt"
REQUIRED_MODULE = "mcp.server.fastmcp"

if sys.platform == "win32":
    _VENV_PY = HERE / ".venv" / "Scripts" / "python.exe"
else:
    _VENV_PY = HERE / ".venv" / "bin" / "python3"


def _log(msg: str) -> None:
    print(f"[run.py] {msg}", file=sys.stderr, flush=True)


def _import_ok(python: str, module: str = REQUIRED_MODULE, timeout: int = 60) -> bool:
    """True if `python` can import `module`."""
    try:
        subprocess.run(
            [python, "-c", f"import {module}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return True
    except Exception:
        return False


def _create_venv() -> Path:
    """Create .venv and install deps; raise with stderr on failure."""
    _log(f"creating venv at {HERE / '.venv'}")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(HERE / ".venv")],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "venv failed")
    _log("installing requirements.txt into venv")
    result = subprocess.run(
        [
            str(_VENV_PY),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-q",
            "-r",
            str(REQS),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "pip failed")
    return _VENV_PY


def _bootstrap() -> str:
    """Return the python executable that should run server.py."""
    # 1) current interpreter already has the SDK (AstrBot container)
    if _import_ok(sys.executable):
        _log("using current interpreter (deps already present)")
        return sys.executable

    # 2) existing venv works
    if _VENV_PY.is_file() and _import_ok(str(_VENV_PY)):
        _log("using existing venv")
        return str(_VENV_PY)

    # 3) (re)create venv
    try:
        _create_venv()
        if _import_ok(str(_VENV_PY)):
            _log("using freshly-created venv")
            return str(_VENV_PY)
        _log("venv created but import check failed")
    except Exception as exc:  # noqa: BLE001
        _log(f"venv bootstrap failed: {exc}")

    # 4) last resort — server.py will surface the real error in logs
    _log(f"falling back to {sys.executable}")
    return sys.executable


if __name__ == "__main__":
    python = _bootstrap()
    args = [python, str(SERVER), *sys.argv[1:]]
    if os.name == "nt":
        os.execv(sys.executable, args)
    else:
        os.execv(python, args)
