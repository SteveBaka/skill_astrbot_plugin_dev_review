# OpenAPI local snapshot

| Field | Value |
|-------|--------|
| Live URL | https://docs.astrbot.app/openapi.json |
| UI | https://docs.astrbot.app/scalar.html |
| Last skill sync | 2026-10-16 (baseline recorded; snapshot still the 4.28-era **163** paths, live **4.29.0** = **170**) |
| Paths in snapshot | **163** — deliberately behind live; accepted delta in the baseline file |
| `info.version` | `0.1.0` (pinned by upstream — **not** a core version marker) |
| Snapshot file | `AstrBot OpenAPI v1.json` (gitignored local asset) |
| Refresh | `./mcp/.venv/bin/python mcp/scripts/check_openapi_drift.py --update` |
| Accepted drift baseline | `mcp/openapi_drift_baseline.json` (snapshot stays at the **4.28** baseline on purpose) |

> **Interpreter requirement**: the script uses `zip(..., strict=...)`, which needs
> **Python ≥3.10**. On a machine whose default `python3` is older (this Mac: 3.9.6)
> it aborts with a version message (`exit 3`); `--offline` aborts too. Use the 3.12
> venv interpreter (`./mcp/.venv/bin/python`) as shown above.

## v4.29.1 check (2026-10-17) — no OpenAPI change

Range checked: `v4.29.0..dffe922` (the “bump version to 4.29.1” commit, PR #10602),
11 commits. **`openspec/` and `docs/en/dev/openapi-scopes.md` are untouched**, so the
163-path snapshot and the accepted-drift baseline need no update — the 4.29.1 release is
plugin-surface neutral on the REST side.

Plugin-author-relevant changes in that range (docs only, no API):

| Change | PR | Plugin impact |
|---|---|---|
| `labels` + **`subtitles`** documented as `_conf_schema.json` fields; both follow WebUI language via `.astrbot-plugin/i18n/<locale>.json` | #10601 | **Additive**: dropdown display text + per-option description. `options` stay stored values — translate `labels`, not `options`. Older cores ignore the keys |
| Skills fault isolation: one unreadable plugin directory no longer fails the whole agent request | #10591 | `skills/` shipping plugins: a broken sibling is skipped, not fatal; keep your own `SKILL.md` readable and valid |
| Web search providers: SerpApi (web/image/scholar/finance) + DeepSeek (search + page extraction) | #10599, #10601 | Do not hardcode provider tool names; availability stays profile-dependent |

Non-plugin: Windows workspace file access + Local permission modelling (#10584), session
isolation memory leak / ordering (#10581), Telegram hidden links (#10557), Discord
everyone mentions (#10563), Edge TTS User-Agent (#10588), mobile View popover (#10562).

## Accepted drift baseline (2026-10-16)

**Live verification (2026-10-16):** against a real AstrBot **4.29.0** deployment
(`astrbot_openapi_capabilities`, `use_live=true`) the report came back
`openapi_source: "snapshot"` with `snapshot_path_count: 163` — i.e. that instance does
**not** serve `/openapi.json`, so `openapi_caps` resolved every capability from this
snapshot. Pinning the snapshot is therefore **load-bearing**, not cosmetic: on such a
deployment it is the only spec source the skill has. (The `--update` refresh still pulls
from `docs.astrbot.app`, never from the instance.)

The snapshot deliberately stays at the 4.28-era baseline so that **older cores +
newer skill** remains a supported combination. That makes the delta against live
permanent, which previously meant every run re-reported the same entries and buried
new drift. `mcp/openapi_drift_baseline.json` lists the known delta with a per-entry
PR reference and an old-core note; the script subtracts it and reports only new
drift (`--no-baseline` shows the raw delta, stale entries are flagged for pruning).

Recorded delta at live **4.29.0** (170 paths) vs snapshot **163** — 9 added,
2 removed, 0 method changes, **no runtime impact**:

- added `/api/v1/plugins/views`, `/api/v1/plugins/view`,
  `/api/v1/plugins/{plugin_id}/views`, `/api/v1/plugins/{plugin_id}/views/{view_name}`
  — plugin Pages→Views rename, tag renamed **Plugin Pages → Plugin Views**
  (#10307 / #10415); the page-named routes stay as **deprecated** aliases.
- added `/api/v1/files/upload/{init,chunk,complete,abort,status}` — **chat
  attachment** chunked upload (#10123), scope `file`; unrelated to plugin install.
- removed `/api/v1/plugins/page/assets` and
  `/api/v1/plugins/{plugin_id}/pages/{page_name}/assets/{asset_path}` — superseded by
  the path-token view asset route (#10415).

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

## Runtime-used routes (28)

All present in the 163-path snapshot (chat / plugins / config-profiles / providers /
plugin-sources). See `check_openapi_drift.py` extraction from `mcp/runtime/*.py`.
