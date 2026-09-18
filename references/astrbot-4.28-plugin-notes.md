# AstrBot 4.28 Plugin Development Notes

Authoritative target for **skill-generated plugins** remains `astrbot_version: ">=4.27,<5"`
(`contracts.SCAFFOLD_ASTRBOT_VERSION`). Production cores validated: **4.27.4 / 4.28.1**.

This file records **4.28.0–4.28.1** facts that plugin authors and this skill’s MCP
tooling must respect. Official docs/source win on conflict.

## OpenAPI extras + graceful degradation (skill MCP)

| Tool | Endpoint | Older core behavior |
|------|----------|---------------------|
| `astrbot_openapi_capabilities` | report matrix | Always safe (read-only) |
| `astrbot_plugin_install_url` | `POST /plugins/install/url` | **Degrade** → `install_path` |
| `astrbot_plugin_install_git` | `POST /plugins/install/git` | **Degrade** → `install_path` |
| `astrbot_plugin_update` | `POST /plugins/{id}/update` | **Degrade** → `install_path` |
| `astrbot_plugin_changelog` | `GET /plugins/.../changelog` | **Degrade** → README/releases |
| `astrbot_plugin_validate_repo` | `POST /plugins/validate/repo` | **Degrade** → manual metadata review |

**Policy** (`contracts.OPENAPI_DEGRADATION_POLICY` / `runtime/openapi_caps.py`):

1. Resolve capability via live `openapi.json` (if any) → local snapshot → core `min_core` version hint  
2. If `unsupported` / `core_version_too_old` → structured payload (`degraded=true`), **do not** treat as agent bug  
3. HTTP 404/405/501 on optional paths → `error_kind=openapi_unsupported` + fallback tool name  
4. **Portable baseline** on every core: `astrbot_plugin_pack_preview` + `astrbot_plugin_install_path` (Scheme A)

## Install staleness (Scheme A) — tiered contract

On **4.28.x**, `install/upload` updates `metadata.version` in the plugin list after a successful re-upload. Skill MCP `install_path` therefore **does not** mark `possible_stale_install` when version changed:

| install_status | Meaning | Agent |
|----------------|---------|-------|
| `install_ok_version_bumped` | version before→after changed; components same | Success; smoke only if handler internals must be proven |
| `pack_changed_components_same` | same version/components; pack main.py hash changed | Prefer smoke |
| `possible_stale_install` (low/high) | same version + same components | low → smoke first; high (same pack hash) → bump / force_refresh |

Details: `mcp/SETUP.md` Result analysis · implementation `runtime/tools_install.py` (`_classify_install_staleness`).

## What did NOT break (re-verified on 4.28.1)

| Surface | Status |
|---------|--------|
| `astrbot.api.event.filter` (`command`, `command_group`, `event_message_type`, `regex`, hooks) | Unchanged vs skill `FILTER_ATTR_KNOWN` |
| `from astrbot.api.platform import register_platform_adapter` | Unchanged public re-export |
| `astrbot.api.web` (`json_response`, `request`, `stream_response`, …) | Still the official plugin-pages recommendation |
| H1-B command args (typed ints / str / command_group) | Smoke-OK on 4.27.4 **and** 4.28.1 |
| Plugin manage OpenAPI (list/get/reload/enabled/config/log-level/install/upload) | Used by skill MCP; no drift vs live OpenAPI (ETag 304) |
| Extension Web routes | Still `/api/v1/plugins/extensions/<plugin_name>/...` |

## OpenAPI (plugin-relevant) — snapshot 163 paths on 4.28.1

Public OpenAPI still **does not** expose API-key-accessible `/logs/*` (dashboard `system`
scope only). Skill log access remains via **`astrbot_plugin_mcp_logs_bridge`**.

Paths present in snapshot that **plugin / MCP authors** may care about (not all used by this skill yet):

| Area | Examples |
|------|----------|
| Plugin lifecycle | `POST /plugins/install/upload`, `install/url`, `install/git`, `install/github`, `POST /plugins/update`, `POST /plugins/{id}/update` |
| Plugin config | `GET/PUT /plugins/{id}/config`, `.../config/schema`, config-files |
| Plugin pages | `GET /plugins/{id}/pages`, page assets, `page-bridge-sdk.js` |
| Extension (your Web APIs) | `/plugins/extensions/{plugin_path}` |
| Log level | `PUT /plugins/{id}/log-level` |
| Version gate | `POST /plugins/version-support/check` |
| Failed list | `/plugins/failed`, `DELETE /plugins/failed/{id}`, reload |
| Market / sources | `/plugins/market*`, `/plugin-sources*` |
| Skills | `/skills*` (incl. neo evaluate/promote/rollback) |
| Conversations / sessions | `/conversations*`, `/sessions*`, UMO filter-options |

**Skill MCP runtime-used endpoints (21)** all still match live spec on 4.28.1.

## Log-reading companion plugin

| Item | Value |
|------|--------|
| Plugin id | `astrbot_plugin_mcp_logs_bridge` |
| Local version | **v0.1.6** (metadata `>=4.27,<5`) |
| Why it exists | No public API-key `/logs/*` on 4.28.1 |
| Data source | In-process `LogBroker` (same as Dashboard `/logs/history`); file+rotation fallback |
| Web API style | `register_web_api` + **`astrbot.api.web`** |
| Auth | Plugin-scope `X-API-Key` + optional shared `X-MCP-Token` (`auth_token` is `secret: true`) |
| 4.28.1 runtime | `logs_history` / `logs_tail` / `logs_search` returned `source=broker` ✅ |
| Skill MCP env | `ASTRBOT_LOG_MCP_URL` required to register relay tools; optional `ASTRBOT_LOG_MCP_TOKEN` |

## 4.28 features plugin authors should adapt to

| Change | Plugin-dev impact |
|--------|-------------------|
| **Config / profile secret masking (#9824)** | Set `"secret": true` on tokens; do not log config secrets |
| **Agent Runner in profiles (#9821)** | Coach users to profile UI; plugin `context.get_using_agent_runner(umo)` unchanged |
| **`max_agent_step` on cron/background agents (#9801)** | Active cron jobs can stop earlier; document budgets |
| **Cron runner failure recording (#9987)** | Expect failure logs on ERROR end states |
| **`/reset` ≡ `/new` (#10004, 4.28.1)** | Session/conversation tools; third-party agent backends may reset session ids |
| **Image attachment paths preserved (#10042)** | Safer to keep attachment paths for the event/agent lifetime |
| **OpenAI tool schema sorted by name (#9798)** | Registration order ≠ schema order; names must stay unique |
| **Anthropic base URL needs `/v1` (#9802)** | Document when plugins/READMEs mention provider URLs |
| **AnySearch web search (#9767)** | Built-in search provider; tool names remain profile-dependent |
| **Plugin update via URL/file fixed (#10053 / 4.28.1)** | Aligns with skill Scheme A notes; still bump version / force_refresh for stale installs |
| **UMO readable names (#9909)** | WebUI easier debugging; UMO string format still `platform:type:session` |
| **Group metadata enrichment (#9851)** | Adapters may expose richer group info — optional for custom adapters |
| **dict config user content preserved (#9958)** | Safer to ship `dict` / `template_list` schemas |

## Version policy (do not loosen casually)

```text
Skill scaffold default:  ">=4.27,<5"     # hard load gate for generated plugins
Official teaching example: ">=4.16,<5"  # only for ancient-surface demos
Bump to ">=4.28,<5" only when templates depend on 4.28-only APIs
```

Raise the floor **after** codegen actually requires 4.28-only behavior + re-smoke.

## Verification commands

```bash
# version gate against live core
astrbot_version_check(spec=">=4.27,<5", include_probe_version=true)

# OpenAPI drift (ETag 304 = no change)
python3 mcp/scripts/check_openapi_drift.py
python3 mcp/scripts/check_openapi_drift.py --update   # refresh snapshot when needed

# log relay (needs ASTRBOT_LOG_MCP_URL on MCP host)
astrbot_logs_tail(lines=20)
```
