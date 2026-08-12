# OpenAPI local snapshot

| Field | Value |
|-------|--------|
| Live URL | https://docs.astrbot.app/openapi.json |
| UI | https://docs.astrbot.app/scalar.html |
| Last skill sync | 2026-08-13 (AstrBot **v4.27.0** snapshot; **v4.27.2 / v4.27.3** checked — 162 paths, no delta) |
| Paths in snapshot | **162** (no path/method drift for runtime-used routes) |
| `info.version` | `0.1.0` (pinned by upstream — **not** a core version marker) |
| Snapshot file | `AstrBot OpenAPI v1.json` (gitignored local asset) |
| Refresh | `python3 mcp/scripts/check_openapi_drift.py --update` |

## v4.27.0 delta (2026-08-02)

- **Runtime-used routes: 18/18 present, methods & scopes unchanged** — no impact on the MCP control plane.
- `PUT /api/v1/plugins/{plugin_id}/log-level` (scope `plugin`) is **now in the public spec** — previously only in core source. Implementing a log-level MCP tool is now spec-backed.
- **New endpoints** (not used by runtime):
  - `/api/v1/plugins/install/git` — install/update from HTTP(S)/SSH/SCP Git repos (#9493)
  - `/api/v1/conversations*`, `/api/v1/sessions*`, `/api/v1/session-groups*` — group message history (#9465) / session management (#9499)
  - `/api/v1/chat/projects/{project_id}/workspace/file*` — project workspace files (#9505)
- **Removed**: `/api/v1/files/tokens/{id}` — not used by runtime.
- **Scope metadata**: plugin config endpoints (`/api/v1/plugins/{id}/config*`) are scope **`plugin`** (not `config`); `config` covers config-profiles; `provider` covers providers; `chat` covers WebChat. See `mcp/SETUP.md` API Key scopes.

## v4.27.2 check (2026-08-05)

Pure maintenance/fix patch (#9525/#9539/#9532/…). Live spec verified: **162 paths
identical to snapshot**, runtime-used routes + scopes unchanged → **no skill/MCP
update required**.

## v4.27.3 check (2026-08-13)

Feature/performance patch (async SharedPreferences #9582/#9584/#9649, cron
timezone #9579/#9581, plugin config default reset #9599, MCP tool-name sanitize
#9534, empty-config-schema #9619, …). Live spec verified: **162 paths identical
to snapshot**, runtime-used routes + scopes unchanged → **no MCP/OpenAPI update
required**. Doc-only notes added: KV storage async API reaffirmed, cron timezone.

## Runtime-used routes (20)

All present in the 162-path contract (chat / plugins / config-profiles / providers). See `check_openapi_drift.py` extraction from `mcp/runtime/*.py`.
