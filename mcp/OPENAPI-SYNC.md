# OpenAPI local snapshot

| Field | Value |
|-------|--------|
| Live URL | https://docs.astrbot.app/openapi.json |
| UI | https://docs.astrbot.app/scalar.html |
| Last skill sync | 2026-07-30 (AstrBot **v4.26.8** release window) |
| Paths in snapshot | **145** (no path/method drift vs prior for runtime-used routes) |
| `info.version` | `0.1.0` (pinned by upstream — **not** a core version marker) |
| Snapshot file | `AstrBot OpenAPI v1.json` (gitignored local asset) |
| Refresh | `python3 mcp/scripts/check_openapi_drift.py --update` |

## Known core API not yet in public OpenAPI (v4.26.8 source)

| Method | Path | Scope | Body | Notes |
|--------|------|-------|------|--------|
| PUT | `/api/v1/plugins/{plugin_id}/log-level` | `plugin` | `{"level": "DEBUG"\|"INFO"\|"WARNING"\|"ERROR"\|"CRITICAL"\|null}` | null = follow global; also `log_level` on plugin config GET |

Do **not** register MCP tools for routes missing from the published spec unless the user pins an instance version and accepts drift risk.

## Runtime-used routes (18)

Still fully present in the 145-path public contract (chat / plugins / config-profiles / providers). See `check_openapi_drift.py` extraction from `mcp/runtime/*.py`.
