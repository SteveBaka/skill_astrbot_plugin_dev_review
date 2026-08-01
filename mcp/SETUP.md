# MCP Server Setup

## Authority

| Source | Role |
|--------|------|
| **This file (`mcp/SETUP.md`)** | MCP install & client config **source of truth** |
| `README.md` § MCP | Chinese quick start only; must match this file |
| Working client config | Runtime proof (e.g. `~/.config/kilo/kilo.jsonc`) |

**Required launch shape (all stdio clients):**

1. **Absolute** path to venv `python3`
2. **Absolute** path to `mcp/server.py` (do **not** use bare `server.py`)
3. **Absolute** `cwd` pointing at the `mcp/` directory

Why: some hosts (notably Kilo) spawn the process from the **workspace / project root** and resolve the script argument relative to that root, **not** relative to `cwd`. Relative `server.py` then becomes `<project>/server.py` (missing) → process exits → `MCP error -32000: Connection closed`.

## 1. Create venv and install dependencies

```bash
cd skill_astrbot_plugin_dev_review/mcp
python3 -m venv .venv
.venv/bin/pip install mcp pyyaml uvicorn starlette
```

> Requires Python 3.10+. If your system Python is older, use the Python from another 3.12 venv:
> ```bash
> /path/to/python3.12 -m venv .venv
> ```

## 2. Add to your MCP client config

Replace `/your/actual/path/skill_astrbot_plugin_dev_review` with the real absolute skill root.

### Kilo CLI / global (`~/.config/kilo/kilo.jsonc`)

`command` is a single array: `[python, server.py]`.

```json
{
  "mcp": {
    "skill-astrbot-plugin": {
      "type": "local",
      "command": [
        "/your/actual/path/skill_astrbot_plugin_dev_review/mcp/.venv/bin/python3",
        "/your/actual/path/skill_astrbot_plugin_dev_review/mcp/server.py"
      ],
      "cwd": "/your/actual/path/skill_astrbot_plugin_dev_review/mcp",
      "enabled": true
    }
  }
}
```

### Kilo / VS Code extension (`mcp_settings.json`)

Uses `command` + `args` (not a single array):

```json
{
  "mcpServers": {
    "skill-astrbot-plugin": {
      "command": "/your/actual/path/skill_astrbot_plugin_dev_review/mcp/.venv/bin/python3",
      "args": [
        "/your/actual/path/skill_astrbot_plugin_dev_review/mcp/server.py"
      ],
      "cwd": "/your/actual/path/skill_astrbot_plugin_dev_review/mcp",
      "disabled": false
    }
  }
}
```

Typical path:  
`~/Library/Application Support/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json`  
(or the equivalent Cursor/globalStorage path for your editor).

### Other clients (Claude Desktop / Cursor / Windsurf)

Prefer the same **absolute python + absolute server.py + cwd**. Map fields to that client’s schema (`command`/`args` vs array). Do not rely on relative `server.py` + `cwd` alone unless you have verified that client resolves scripts against `cwd`.

Config file locations:

| Client | Path |
|--------|------|
| Kilo CLI | `~/.config/kilo/kilo.jsonc` |
| Kilo extension | `.../globalStorage/kilocode.kilo-code/settings/mcp_settings.json` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| VS Code user MCP | `~/.vscode/mcp.json` or Code `User/mcp.json` (may be separate from Kilo extension settings) |

## 3. Verify

Restart your MCP client (or Reload Window). You should see **6 docs tools** always, plus **runtime tools** when the server starts (runtime needs env for live calls):

| Tool | Description |
|------|-------------|
| `get_skill_info` | Get skill overview (categories, doc count, quick start) |
| `list_docs` | List all categories and documents |
| `get_doc(category, doc_name)` | Fetch a specific document |
| `search_docs(query)` | Search all documents by keyword |
| `validate_import(symbol)` | Check if an AstrBot import path is correct |
| `get_review_checklist(file_type)` | Get review checklist (main/general/metadata/adapter) |
| `astrbot_runtime_info` | **[P0]** Config + optional OpenAPI probe (no token leak) |
| `astrbot_plugin_list` | **[P0]** GET `/api/v1/plugins` (read-only) |
| `astrbot_plugin_failed` | **[P0]** GET `/api/v1/plugins/failed` (read-only) |
| `astrbot_plugin_get` | **[P0]** GET `/api/v1/plugins/{plugin_id}` (read-only) |
| `astrbot_plugin_config_get` | **[P1]** GET plugin config — **`redact=true` default**; `redact=false` **only** when about to `config_set` (not casual read/log/chat) |
| `astrbot_plugin_config_schema` | **[P1]** GET plugin config schema (read) |
| `astrbot_plugin_config_set` | **[P1]** PUT plugin config (**mutations**) |
| `astrbot_plugin_set_enabled` | **[P1]** PATCH enable/disable (**mutations**) |
| `astrbot_plugin_reload` | **[P1]** POST reload (+ failed endpoint) (**mutations**) |
| `astrbot_plugin_uninstall` | **[P2]** DELETE uninstall (**mutations** + confirm; **default keep config/data**) |
| `astrbot_plugin_pack_preview` | **[P2]** Dry-run local ZIP pack (gitignore; **no upload**) |
| `astrbot_plugin_install_path` | **[P2]** Scheme A: pack → upload → enable → reload → failed (**mutations**; optional `force_refresh`) |
| `astrbot_providers_brief` | **[P2.5]** Provider id/name list (no secrets) |
| `astrbot_config_profiles_brief` | **[P2.5]** Profile names/ids only |
| `astrbot_post_install_hints` | **[P2.5]** Dashboard checklist (no config reads) |
| `astrbot_ensure_plugin_dev_skill` | **[P2.5]** Create `plugin_dev_skill` from default (**mutations** + confirms) |
| `astrbot_chat_sessions_brief` | **[P3]** List WebChat sessions metadata (chat scope) |
| `astrbot_chat_probe` | **[P3]** Opt-in SSE smoke via `POST /chat` (**confirm_probe**; fixed reusable smoke session) |
| `astrbot_chat_sessions_cleanup` | **[P3]** Delete **webchat-only** sessions (**mutations** + confirm; cannot delete Dashboard-user sessions) |
| `astrbot_scaffold_plugin` | **[P2+]** Scaffold `command\|llm_tool\|session\|cron\|hook\|web\|agent\|adapter` from contracts; review error=0 invariant |
| `astrbot_review_path` | **[P2+]** AST review `profile=plugin\|adapter` (FIX-mapped; contracts single source) |
| `astrbot_smoke_suite` | **[P3+]** Composite smoke after **user** Dashboard config (enable / plugin_set / schema) |

CLI check (if `kilo` is installed):

```bash
kilo mcp list
```

Expect `skill-astrbot-plugin` **connected**. Server stderr may show `ListToolsRequest`.

## 3.1 Runtime env (optional — LAN AstrBot)

> **Docs MCP does not need these.** Empty `ASTRBOT_BASE_URL` ⇒ runtime tools return `not_configured`; docs tools stay healthy.

Configure on the **MCP host** (`env` next to the server entry in `kilo.jsonc` / `mcp_settings.json`), never commit secrets into this repo.

| Env | Required | Meaning |
|-----|----------|---------|
| `ASTRBOT_BASE_URL` | for runtime | e.g. `http://192.168.1.50:6185` (AstrBot on **another LAN device** — do not use that device's `localhost` from Kilo's machine) |
| `ASTRBOT_TOKEN` | if instance requires auth | Dashboard API key / token (sent as `X-API-Key` by default; **chat** scope needed for chat_probe) |
| `ASTRBOT_AUTH_MODE` | no | `api_key` (default) \| `bearer` \| `auto` |
| `ASTRBOT_HTTP_TIMEOUT` | no | seconds, default `15` (raise on slow NAS/VPN; upload/chat may need more) |
| `ASTRBOT_ALLOW_MUTATIONS` | no | default off; `true` enables reload / set_enabled / config_set / install / uninstall / ensure_plugin_dev_skill |
| `ASTRBOT_ALLOW_CHAT_PROBE` | no | default off; allows chat_probe without per-call `confirm_probe` |
| `ASTRBOT_CHAT_USERNAME` | for chat_probe | default WebChat username |
| `ASTRBOT_CHAT_CONFIG_NAME` | no | default `plugin_dev_skill` |
| `ASTRBOT_CHAT_SMOKE_SESSION_ID` | no | fixed smoke session id (default `mcp-smoke-<username>`) |

### Example `kilo.jsonc` fragment (paths absolute; env for LAN)

```jsonc
"skill-astrbot-plugin": {
  "type": "local",
  "command": [
    "/your/actual/path/skill_astrbot_plugin_dev_review/mcp/.venv/bin/python3",
    "/your/actual/path/skill_astrbot_plugin_dev_review/mcp/server.py"
  ],
  "cwd": "/your/actual/path/skill_astrbot_plugin_dev_review/mcp",
  "enabled": true,
  "env": {
    // 局域网 AstrBot 根地址（跨设备写主机 IP:端口）
    "ASTRBOT_BASE_URL": "http://192.168.x.x:6185",
    // Dashboard API Key（chat_probe 需含 chat 权限；勿提交仓库）
    "ASTRBOT_TOKEN": "your-api-key",
    // 鉴权方式：api_key（默认）| bearer | auto
    "ASTRBOT_AUTH_MODE": "api_key",
    // HTTP 超时秒数（上传/对话可调高）
    "ASTRBOT_HTTP_TIMEOUT": "20",
    // 允许写操作：reload/启停/配置/安装/卸载/建 plugin_dev_skill
    "ASTRBOT_ALLOW_MUTATIONS": "true",
    // 允许不经 confirm_probe 调 chat_probe（默认建议 false）
    "ASTRBOT_ALLOW_CHAT_PROBE": "false",
    // WebChat 发送者用户名（chat_probe）
    "ASTRBOT_CHAT_USERNAME": "your_webchat_user",
    // chat_probe 默认配置档案名
    "ASTRBOT_CHAT_CONFIG_NAME": "plugin_dev_skill"
  }
}
```

### Connectivity check order

1. Restart MCP client after env change.
2. Call `astrbot_runtime_info` → expect `connection: "ok"` and `probe.summary.plugin_count`.
3. If `error_kind=connect|timeout`: fix IP/port/firewall/AstrBot process (LAN).
4. If `error_kind=auth`: set/fix `ASTRBOT_TOKEN` / try `bearer`.
5. Then `astrbot_plugin_list` / `astrbot_plugin_failed`.

### Plugin manage flow (P1)

```
list/get → config_get → (optional config_set) → set_enabled → reload → failed probe
```

| Result | Meaning |
|--------|---------|
| `mutations_disabled` | Gate closed; OpenAPI write **not** called. Set `ASTRBOT_ALLOW_MUTATIONS=true` + restart MCP. |
| reload `ok` + empty failed | Plugin reloaded cleanly |
| reload `ok` + still in failed | Load error — fix code, reload again |
| `http_status` 4xx/5xx | Auth/body/id wrong — see response `data` |

### Local install / update — Scheme A (recommended)

```
edit source on MCP host machine
  → astrbot_plugin_pack_preview(path)   # optional
  → astrbot_plugin_install_path(path)   # zip + upload + enable + reload + failed
```

| Detail | Behavior |
|--------|----------|
| ZIP file name | From `metadata.yaml`: `{name}-{version}.zip` (fallback `{name}.zip`) |
| ZIP root folder | Prefers `metadata.name`; else directory basename |
| Required files | `metadata.yaml`, `main.py` |
| Excludes | Plugin/parent `.gitignore` + hard list (`.git`, `.venv`, `__pycache__`, `node_modules`, …) |
| API | `POST /api/v1/plugins/install/upload` multipart field `file` |
| Update loop (**primary**) | Re-run `install_path` after edits — **no uninstall** |
| Same-name conflict (**fallback**) | If upload conflicts with already-installed plugin: uninstall with `keep_config=true` + `keep_data=true` (never delete config/data by default), then `install_path` again |
| **Stale same-version** | `success=true` **≠** “source replaced”. Core may keep old files when `version` unchanged — behavior/component docstrings stay old |
| **Refresh options** | (1) Bump `metadata.yaml` `version` then `install_path`; (2) `install_path(..., force_refresh=true)` → uninstall **keep config+data** then upload (`refresh_mode=reinstall_keep_config_data`); (3) manual uninstall keep_* then install |
| **Default safety** | `force_refresh` default **false** — never silent uninstall. No confirm → no wipe of config/data |
| Gate | `ASTRBOT_ALLOW_MUTATIONS=true` |
| Timeout | Upload uses ≥60s or `ASTRBOT_HTTP_TIMEOUT` if higher |

**Result analysis:**

| Field | Meaning |
|-------|---------|
| `success=true` + `plugin_in_failed=false` | Load path OK — **not** proof that every local edit is on disk |
| `pack_main_py_sha256_16` | Fingerprint of `main.py` inside the uploaded ZIP |
| `snapshot_before` / `snapshot_after` | Version + component fingerprint (type/name/command/description) |
| `warning=possible_stale_install` | Before/after component fingerprint identical after re-upload → try bump version or `force_refresh=true` |
| `refresh_mode` | `upload_only` (default) or `reinstall_keep_config_data` (when force_refresh ran) |
| `pack_failed` / `not_a_plugin` | Fix local path structure before retry |
| `same_name_conflict_suspected=true` | Fallback uninstall-keep-then-install (or `force_refresh`) only after primary re-upload fails |

**Agent rule:** After code changes, if smoke/behavior still looks old, do **not** only re-`install_path` blindly — bump version or `force_refresh=true` (still keeps config/data unless user explicitly asked to wipe).

### Dev profile `plugin_dev_skill` (P2.5)

```
astrbot_providers_brief          # user picks provider_id
astrbot_config_profiles_brief    # see if plugin_dev_skill exists
astrbot_ensure_plugin_dev_skill(plugin_id, provider_id, confirm_create=true, exist_policy=...)
→ user: Dashboard WebChat → select plugin_dev_skill
```

| Rule | Behavior |
|------|----------|
| Base | Deep copy of **default** profile config (server-side) |
| Overrides | `plugin_set=[plugin_id(+extras)]`, `default_provider_id=user choice` |
| Output | **Never** returns full config body |
| Exists | User chooses `abort` / `recreate` (+ delete confirm) / `rename_old` |
| Chat smoke | **Not** done by this tool; MCP auto-chat only if user later allows |
| Privacy | No auto `plugin_config_get`; install only attaches Dashboard hints |
| `config_get` redact | **Default true.** `redact=false` **only** when immediately editing via `config_set`; never for browse/log/chat; do not commit raw secrets |

### Chat probe (P3) — opt-in smoke

```
# After user explicitly allows MCP smoke:
# message = plugin's OWN command. "/plugin_help" is a minimal discovery probe
# when you don't know which commands the plugin supports; never hardcode
# mimo_tts-only commands like "/ttsinfo" for other plugins.
astrbot_chat_probe(
  message="/plugin_help",
  username="your_webchat_user",
  config_name="plugin_dev_skill",
  confirm_probe=true
)
```

| Rule | Behavior |
|------|----------|
| Gate | `confirm_probe=true` **or** env `ASTRBOT_ALLOW_CHAT_PROBE=true` |
| API key | Must include **chat** scope (else 403) |
| username | Required (`username` arg or `ASTRBOT_CHAT_USERNAME`) |
| config | Default `config_name=plugin_dev_skill` (or `ASTRBOT_CHAT_CONFIG_NAME` / `config_id`) |
| **message** | Fill the **plugin's actual command** (from `plugin_get` / `smoke_suite` components). Use `/plugin_help` to discover when unsure. Do **not** hardcode other plugins' commands (`/help` is Astrbot build-in command) |
| session | **Fixed reusable smoke session** (default `mcp-smoke-<username>`; override via `session_id` arg or `ASTRBOT_CHAT_SMOKE_SESSION_ID`); server auto-creates it, all probes land in one stable Dashboard WebChat entry |
| Response | SSE (`data: {...}`); tool returns truncated `plain_texts` / `records` |
| Privacy | No transcript files; main test remains Dashboard WebChat |

Env extras: `ASTRBOT_ALLOW_CHAT_PROBE`, `ASTRBOT_CHAT_USERNAME`, `ASTRBOT_CHAT_CONFIG_NAME`, `ASTRBOT_CHAT_SMOKE_SESSION_ID`.

### Session cleanup (P3) — webchat-only, verified limits

`astrbot_chat_sessions_cleanup` deletes WebChat sessions with a hard privacy gate: every id must verify as a **webchat-platform** session of the given username (other platforms → `scope_violation`, whole call refused). Requires `ASTRBOT_ALLOW_MUTATIONS=true` + `confirm_cleanup=true`, hard cap `max_delete`.

**Known limit (source-verified 2026-07):** AstrBot checks `session.creator == auth identity`, and API-key identity is `api_key:<key_id>` — so sessions created by Dashboard users always return `Permission denied` via API key; delete those in Dashboard WebChat. Do **not** work around this by granting system scope; the fixed-session probe design makes cleanup mostly unnecessary.

### Uninstall safety (P2) — keep by default

OpenAPI body: `{ "delete_config": bool, "delete_data": bool }`.

| Rule | Behavior |
|------|----------|
| Ask user | Keep config? Keep persistent data? |
| No answer | **Keep both** (`keep_config=true`, `keep_data=true` → API `delete_*=false`) |
| Never silent wipe | `delete_config`/`delete_data` true only after explicit user OK |
| Tool gates | `confirm_uninstall=true` required for any uninstall; if deleting config/data, also `confirm_delete_config` / `confirm_delete_data` |
| Soft refuse | `error_kind=confirm_required` / `delete_*_confirm_required` → **API not called** |

Agent must not uninstall production plugins during routine tests; use a dedicated sandbox only with user permission.

### Scaffold (P2+) — contracts + review invariant

`astrbot_scaffold_plugin(name, author, plugin_type=..., output_dir=...)`:

**Types:** `command` | `llm_tool` | `session` | `cron` | `hook` | `web` | `agent` | `adapter`

1. Validates name/author (adapter: id slug)  
2. Writes tree from **`runtime/contracts.py`**  
3. Review: Star → `profile=plugin` (+ FIX-03); **adapter** → `profile=adapter` (FIX-06)  
4. **Invariant:** fresh scaffold **0 review errors**

**adapter** = framework only (not WebChat-smokeable). Full adapter E2E when you provide a working adapter.

Confirm name/author first. Star: BUSINESS → review → install → **user Dashboard** → smoke.

### Static review (P2+) — codified FIX rules

`astrbot_review_path(path, profile=plugin|adapter)` — **no AstrBot instance needed**. Import/FIX tables in `runtime/contracts.py`. Adapter profile adds FIX-06 / ADAPT-*. Findings link `review/auto-fix-guide.md`:

| Severity | Meaning | Examples |
|----------|---------|----------|
| error | breaks at import/load | FIX-00 wrong imports, FIX-04 sync requests, FIX-20 dataclass mutable defaults, FIX-21 deprecated filter APIs, FIX-01 missing super().__init__, SYNTAX |
| warning | mandatory-rule violation | FIX-02 handler params, FIX-17 missing docstring, FIX-26 namespace, FIX-27 StarTools context, META-03/04 naming/PEP440, REQ-01 undeclared deps |
| info | hygiene | FIX-23 unused imports, FIX-22 config-injection hint |

Recommended order: `astrbot_review_path` → fix errors → `astrbot_plugin_install_path` → `astrbot_smoke_suite`. Judgment-level review (architecture, logic) stays with the Phase A/B LLM workflow — this tool only automates the statically decidable subset.

### Smoke suite (P3+) — composite pipeline

**Dashboard-first gate (product rule):** After installing a **new** plugin, or after adding/changing **`_conf_schema.json`**, profile **`plugin_set`**, per-tool enable, or other UI-only settings, the agent must **remind the user** to configure them in **AstrBot Dashboard** (plugin config + WebChat profile such as `plugin_dev_skill`). Run `astrbot_smoke_suite` / `chat_probe` **only after** the user confirms those settings (or explicitly asks to smoke without waiting). Do not silently mutate live `plugin_set` just to pass smoke.

`astrbot_smoke_suite(plugin_id, confirm=true, username=...)` codifies the proven manual loop:

1. Plugin status check — not loaded → failed-list diagnosis with FIX links; disabled → enable hint
2. Case derivation from components: non-admin commands (info/help-like first), command groups, one hook probe, one llm_tool soft probe; `extra_messages="a||b"` appends custom cases; `max_cases` cap (default 8)
3. Sequential `chat_probe` runs into the ONE fixed smoke session
4. Post-run failed re-check — catches plugins that crash *during* the run
5. Aggregated verdict: `pass` / `soft_pass` (llm_tool declined) / `error` / `no_content`

Same gates as chat_probe: `confirm=true` (or `ASTRBOT_ALLOW_CHAT_PROBE`), chat-scoped key, username. Admin commands skipped unless `include_admin=true`.

**Not done yet:** local log tail (P4).

**Result analysis (P0):** success only means OpenAPI control plane is reachable and auth works.  
**Result analysis (P1):** manage tools change live AstrBot state; use deliberately on LAN instances.  
**Result analysis (P2 uninstall):** soft refuse means safety gate worked; hard `ok` means plugin removed with the `kept` flags in the response.

## 3.2 Maintenance (dev)

- **Unit tests** (`mcp/tests/`, no AstrBot needed; env auto-cleared):
  `.venv/bin/pytest tests/` — covers zip_pack exclusions/naming, config gates,
  chat SSE/session policy, client auth/errors. Fixture plugin:
  `plugin-types/type2-session-waiter`.
- **OpenAPI drift check** (`mcp/scripts/check_openapi_drift.py`):
  live source `https://docs.astrbot.app/openapi.json` (the scalar.html data URL;
  `info.version` is pinned 0.1.0 — drift is by ETag/content, never version).
  `python3 mcp/scripts/check_openapi_drift.py` → exit 0 no drift / 1 runtime
  endpoints affected (fix `mcp/runtime` first) / 2 drift elsewhere only.
  `--update` refreshes the local snapshot (`AstrBot OpenAPI v1.json`, gitignored);
  `--offline` validates runtime paths against the snapshot without network.
  Run after each AstrBot release.
  **v4.26.8 note (2026-07-30):** 145 paths, no delta vs prior snapshot for
  runtime-used routes. Core also has `PUT /api/v1/plugins/{plugin_id}/log-level`
  (`plugin` scope, body `{"level": "DEBUG"|…|null}`) — **not yet listed** in
  public openapi.json; do not invent MCP tools against undocumented-only
  routes until the published spec includes them (or pin instance version).
- **Error-fingerprint KB → auto-fix-guide** (`mcp/runtime/error_fingerprint.py` + `mcp/scripts/error_kb.py`):
  captures **desensitized** error shapes (paths/UUID/token/plugin-id/line numbers
  stripped) during regression/smoke; proposes new `auto-fix-guide.md` FIX entries
  for recurring unclassified errors.
  ```bash
  # opt-in: record install/smoke diagnoses automatically
  export ASTRBOT_ERROR_KB="$PWD/.error_kb.json"   # gitignored
  # CLI (record one / report / propose new FIX entries)
  python3 scripts/error_kb.py --store /tmp/kb.json record --error "No module named 'x'" --rule FIX-00 --source plugin
  python3 scripts/error_kb.py --store /tmp/kb.json report
  python3 scripts/error_kb.py --store /tmp/kb.json propose --guide ../review/auto-fix-guide.md --min 2
  ```
  Recorded samples never contain secrets/paths.

  **Regression feedback loop (plugin-types + adapters):**
  1. `export ASTRBOT_ERROR_KB="$PWD/.error_kb.json"`
  2. Run `astrbot_smoke_suite` / `install_path` on `plugin-types/type*` and the
     adapter under test; errors auto-record into the KB.
  3. `report` → review desensitized samples + counts + source plugins.
  4. `propose --min 2` → **only entries passing `validate_fix_entry` are printed
     as writable drafts** (exit 0); rejected ones (placeholder-only / too-generic /
     duplicate pattern/title / invalid regex) are listed as *skipped* and must
     **not** be appended to `auto-fix-guide.md` as-is (exit 1 when none pass).
  5. For accepted drafts: verify the root cause in a real traceback, add the FIX
     section to `review/auto-fix-guide.md`, and (optionally) fold the fingerprint
     regex into `failure_analysis._SIGNATURES` so it classifies automatically next run.

## 4. SSE Mode (optional)

For MCP clients that don't support stdio:

```bash
MCP_TRANSPORT=sse MCP_PORT=3000 .venv/bin/python3 server.py
```

Client URL: `http://localhost:3000/sse`.

> **推荐用法**：当本 Skill 以插件形式**上传并安装到 AstrBot 内**时，直接用 AstrBot 自带 MCP 客户端注册本服务器（stdio），无需 SSE——见下一节「在 AstrBot 内注册」。

## 4b. Register inside AstrBot (recommended)

AstrBot ships an **MCP client** (v3.5.0+): the WebUI lets you add an MCP server by
giving a `command` + `args` (+ optional `env`), and AstrBot spawns it as a local
stdio process. Because this Skill is **installed into AstrBot as a plugin**, its
`mcp/` folder is already on the same host — point the MCP client at the local
files instead of remote SSE.

**Assumed install path (Docker/source data dir):**

```
/AstrBot/data/skills/skill_astrbot_plugin_dev_review/
├── SKILL.md
└── mcp/
    ├── run.py        ← self-bootstrap launcher (recommended entry)
    ├── server.py
    └── ...
```

### 1) Zero-setup: register via `run.py` (recommended, no manual venv)

`mcp/run.py` is a **self-bootstrapping launcher**: the first time AstrBot spawns
it, it creates `.venv` + installs `requirements.txt` automatically (falling back
to the container's system Python if `venv` is unavailable), then execs
`server.py`. Later spawns skip straight to `server.py`.

AstrBot's MCP stdio allowlist already permits `python3` (and blocks `bash`/`sh`
and `-c`), so this is the sanctioned shape:

```json
{
  "command": "python3",
  "args": [
    "/AstrBot/data/skills/skill_astrbot_plugin_dev_review/mcp/run.py"
  ],
  "env": {
    "ASTRBOT_BASE_URL": "http://127.0.0.1:6185",
    "ASTRBOT_TOKEN": "your-dashboard-api-key",
    "ASTRBOT_AUTH_MODE": "api_key",
    "ASTRBOT_HTTP_TIMEOUT": "15",
    "ASTRBOT_ALLOW_MUTATIONS": "false",
    "ASTRBOT_ALLOW_CHAT_PROBE": "false",
    "ASTRBOT_CHAT_USERNAME": "your_webchat_user",
    "ASTRBOT_CHAT_CONFIG_NAME": "plugin_dev_skill"
  }
}
```

> First "test connection" may take 30–60 s while it builds the venv and installs
> deps; subsequent tests are instant. No `docker exec` needed.

### 1b) Manual venv (alternative, only if you prefer)

```bash
docker exec astrbot bash -c "cd /AstrBot/data/skills/skill_astrbot_plugin_dev_review/mcp && \
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
# then register with command = ".../.venv/bin/python3", args = [ ".../server.py" ]
```

> **`.venv` is gitignored** — a GitHub-downloaded skill zip will **not** contain it.
> The `run.py` launcher (step 1) handles this automatically; the manual path only
> matters if you skip the launcher.

### 2) Register the MCP server in AstrBot WebUI

`AstrBot 设置 → MCP` → add server using the **step 1 (run.py)** template above
(adjust the path to your actual install).

Because it runs **inside** AstrBot, `ASTRBOT_BASE_URL` points at the same
instance (`127.0.0.1:6185`), so runtime tools talk to AstrBot's own OpenAPI —
no LAN IP, no token over the network.

### 3) Notes & safety

- **`ASTRBOT_ALLOW_MUTATIONS`**: keep `false` unless you want the LLM chat to
  install/change/remove plugins through MCP — enable only after deciding that is
  acceptable (it is AstrBot controlling itself).
- **`ASTRBOT_TOKEN`**: must be an API key with the scopes you want (read-only
  tools need at least `plugin`; chat tools need `chat`). Create it in Dashboard
  `设置 → API Key`; it stays in the AstrBot UI config, not in the skill repo.
- **`ASTRBOT_CHAT_USERNAME`**: the WebChat user used by `chat_probe`/`smoke_suite`.
- Docs tools (6) work even without any env — register the server and the agent
  gets import/checklist/search help immediately.
- Do **not** commit `ASTRBOT_TOKEN` into the skill repo; it lives only in the
  AstrBot WebUI MCP config.

### Install-path rule (do not fabricate absolute paths)

- AstrBot installs **plugins** to `<data_dir>/plugins/<root_dir_name>/`
  (Docker: `/AstrBot/data/plugins/<root_dir_name>/`).
- AstrBot installs **skills** to `<data_dir>/skills/<name>/`
  (Docker: `/AstrBot/data/skills/<name>/`).
- The OpenAPI plugin list/get **only exposes `root_dir_name` (bare name), never
  absolute filesystem paths.** Agents must **not** claim a plugin lives at
  `/AstrBot/<name>/` or any other invented absolute path — the API cannot know
  it. If a real path is needed, ask the user to check the Dashboard or run
  `docker exec astrbot ls /AstrBot/data/plugins`.
- Wrong-looking answers (e.g. `/AstrBot/astrbot_plugin_x/`) are a
  **hallucination**, not data from the API.

### Scaffold → install loop (AstrBot-internal agent)

1. `astrbot_scaffold_plugin` writes to a **staging** dir — default `ASTRBOT_DEV_WORKSPACE`
   or `~/.astrbot_skill_workspace`, **never cwd** (cwd inside AstrBot may be
   `/AstrBot`, which produced confusing paths like `/AstrBot/<name>/`).
2. Deliver the complete plugin in one call via `extra_files_json`
   (allowlist: `main.py` / `metadata.yaml` / `requirements.txt` /
   `_conf_schema.json` / `README.md`). If the plugin uses `config`, **include
   `_conf_schema.json`** or `astrbot_plugin_config_set` returns
   `400 插件 … 没有注册配置`.
3. Upload: `astrbot_plugin_install_path(path=<staging>/<name>)`. The installed
   location is always `<data>/plugins/<root_dir_name>/`; the staging path is
   irrelevant. Never ask the user to copy files into `/AstrBot/<name>/`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `MCP error -32000: Connection closed` | Almost always: process exited. Use **absolute** `server.py`. Check host logs for `can't open file '.../server.py'`. |
| `can't open file '.../server.py'` (under project root, not `mcp/`) | Relative script was resolved from workspace root; switch to absolute path to `mcp/server.py`. |
| `Executable not found: python3` | Use full absolute path to `.venv/bin/python3`. |
| `ModuleNotFoundError: mcp` | Use venv Python, not system Python; re-run step 1. |
| `No such file or directory: '.../.venv/bin/python3'` | `.venv` is gitignored and absent from a GitHub zip. Use the `run.py` launcher (auto-creates it), or create it manually (§4b step 1b). |
| Tools not appearing | Confirm `cwd` is the `mcp/` directory; restart client; confirm both paths exist. |
| Extension red / CLI green | Align **extension** `mcp_settings.json` to the same absolute python + absolute `server.py` as `kilo.jsonc`. |
