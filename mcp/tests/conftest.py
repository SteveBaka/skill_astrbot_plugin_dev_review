"""Shared fixtures for mcp/runtime unit tests.

Run from mcp/:  .venv/bin/pytest tests/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `import runtime` work regardless of pytest invocation cwd
MCP_DIR = Path(__file__).resolve().parent.parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

REPO_ROOT = MCP_DIR.parent
# Real example plugin used as a packing fixture (fast + precise, per project owner)
FIXTURE_PLUGIN = REPO_ROOT / "plugin-types" / "type2-session-waiter"

ASTRBOT_ENV_KEYS = (
    "ASTRBOT_BASE_URL",
    "ASTRBOT_TOKEN",
    "ASTRBOT_AUTH_MODE",
    "ASTRBOT_HTTP_TIMEOUT",
    "ASTRBOT_ALLOW_MUTATIONS",
    "ASTRBOT_ALLOW_CHAT_PROBE",
    "ASTRBOT_CHAT_USERNAME",
    "ASTRBOT_CHAT_CONFIG_NAME",
    "ASTRBOT_CHAT_SMOKE_SESSION_ID",
)


@pytest.fixture(autouse=True)
def clean_astrbot_env(monkeypatch):
    """Tests must never see (or touch) a real AstrBot instance by accident."""
    for key in ASTRBOT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture
def fixture_plugin_dir() -> Path:
    assert FIXTURE_PLUGIN.is_dir(), f"fixture plugin missing: {FIXTURE_PLUGIN}"
    return FIXTURE_PLUGIN
