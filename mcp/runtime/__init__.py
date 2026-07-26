# [RUNTIME] Optional AstrBot OpenAPI control plane for plugin test/debug.
# Docs MCP tools live in server.py and must keep working if this package is absent
# or if ASTRBOT_* env is unset. Do not import this package from docs tool bodies.
"""
AstrBot runtime extension for skill-astrbot-plugin MCP.

P0: stable LAN connectivity + read-only plugin observation.
P1: plugin manage (config get/set, enable, reload) behind ASTRBOT_ALLOW_MUTATIONS.
P2: install_path (Scheme A zip+upload) + uninstall (keep config/data by default).
P2.5: plugin_dev_skill profile ensure + providers brief + post-install hints.
P3: chat_probe (SSE, opt-in) + chat_sessions_brief.
Later: local logs (P4).
"""

from .register import register_runtime_tools

__all__ = ["register_runtime_tools"]
