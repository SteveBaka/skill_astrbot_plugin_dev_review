# Plugin Dashboard Pages (AstrBot 4.25.3 – 4.28.x)

> ## ⚠️ Version scope — read before using this file
>
> | Core version | Use |
> |---|---|
> | **`4.25.3 – 4.28.x`** | **this file** (Pages surface: `pages/`, `window.AstrBotPluginPage`) |
> | **`>=4.29`** | [`plugin-views.md`](./plugin-views.md) — Pages were renamed to **Views** (`views/`, `window.AstrBotPluginView`) |
>
> Sections marked `[version-independent]` are accurate on **both** ranges and are mirrored
> in `plugin-views.md`; keep them in sync when editing.
>
> Renamed in **4.29.0** by PR #10307 (`4b049d1e`), with path-token assets + the finished
> rename in PR #10415 (`8831d950`). Everything listed here is still **accepted** on 4.29
> as a deprecated alias — but new plugins should target `plugin-views.md`.
> Migration: [§11](#11-migration-to-views-429).

> **Primary reference**: https://docs.astrbot.app/dev/star/guides/plugin-pages.html
> (the URL is unchanged, but since 4.29.0 its **content** is "Plugin Views" — for 4.28-era
> wording this file is the accurate one, not that page.)

AstrBot supports plugins exposing Dashboard pages through the `pages/` directory. AstrBot scans `pages/<page_name>/index.html`; directories without `index.html` are ignored.

> For simple configuration items, prefer `_conf_schema.json`. Plugin Pages are more suitable for complex forms, dashboards, logs, file upload/download, SSE, and custom interactions.

> **v4.25.3+**: Plugin pages appear in the Dashboard sidebar (MDI icons) and sync Dashboard theme.
> **v4.26.0+**: Plugin page asset token fallback improved — prefer relative static paths as documented.

## Directory Structure

```text
my_plugin/
├── main.py
├── metadata.yaml
├── pages/
│   └── studio/
│       ├── index.html      # Entry point
│       ├── app.js          # Vue SPA (router + components + API client)
│       └── style.css       # Styles
└── .astrbot-plugin/
    └── i18n/
        ├── zh-CN.json      # Page title/description + strings (key prefix: pages.<page_name>)
        └── en-US.json
```

> **No `_page.json`.** Page/View metadata is **not** declared in a per-directory JSON file —
> it lives in `.astrbot-plugin/i18n/<locale>.json` under the `pages.<page_name>` key
> (see § Page Internationalization). Exceptions: `metadata.yaml` only.

## Recommended Tech Stack `[version-independent]`

| Approach | Use Case |
|----------|----------|
| Vue 3 CDN + SPA | Medium complexity, no build step needed |
| Vanilla HTML + JS | Simple pages |
| Vue + Vite build | Complex apps — **not supported** (AstrBot has no Node build) |

Vue 3 CDN: `vue.global.prod.js` (~33KB gzip) + `vue-router.global.prod.js`, runs directly in browser.

## Bridge SDK (window.AstrBotPluginPage)

> **4.25.3 – 4.28.x**: the global is `window.AstrBotPluginPage`.
> **4.29+**: canonical name is `window.AstrBotPluginView`; `AstrBotPluginPage` stays as an
> alias. For a plugin that must run on both, see [§11](#11-migration-to-views-429).
> See [`plugin-views.md`](./plugin-views.md) for the 4.29 surface.

AstrBot automatically inserts the bridge SDK into the iframe. **No manual import needed.**

### Bridge is Injected Asynchronously

The bridge SDK is injected **after** the iframe loads. If `app.js` accesses `bridge` before injection, it will be `undefined`.

```js
// ❌ WRONG — static reference, bridge may not exist yet
const bridge = window.AstrBotPluginPage;

// ✅ CORRECT — lazy getter
function getBridge() {
  return window.AstrBotPluginPage;
}

// ✅ CORRECT — poll and wait in init
async function init() {
  let retries = 0;
  while (!window.AstrBotPluginPage && retries < 50) {
    await new Promise(r => setTimeout(r, 100));
    retries++;
  }
  const br = window.AstrBotPluginPage;
  if (br && typeof br.ready === 'function') {
    await br.ready();
  }
  // Mount Vue app...
}
```

### Core Methods

<!-- Source: https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/star/guides/plugin-pages.md §Bridge API -->

- `ready()`: Wait for bridge ready, return initial context (`Promise<context>`)
- `getContext()`: Read current context synchronously (use after `ready()` or in `onContext()` callback)
- `getLocale()`: Get current WebUI language (e.g., `"zh-CN"`, defaults to `"zh-CN"`)
- `getI18n()`: Get full i18n resource object for the plugin
- `t(key, fallback)`: Get translated text by dot-notation key, returns `fallback` if missing
- `onContext(handler)`: Listen for context changes (e.g., language switch), returns unsubscribe function

### HTTP Methods

- `apiGet(endpoint, params)`: GET request, returns `Promise<data>`
- `apiPost(endpoint, body)`: POST request, body sent as JSON, returns `Promise<data>`
- `upload(endpoint, file)`: Upload single File object via `multipart/form-data`, field name is `file`, returns `Promise<data>`
- `download(endpoint, params, filename)`: Trigger browser download from backend
- `subscribeSSE(endpoint, handlers, params)`: Subscribe to SSE, returns `Promise<subscriptionId>`
- `unsubscribeSSE(subscriptionId)`: Cancel SSE subscription

### Endpoint Rules

- Must be a relative path within the plugin
- Allowed: `"stats"`, `"settings/save"`, `"files/export"`
- **NOT allowed**: empty string, `"/stats"`, `"../stats"`, `"https://..."`, `"stats?x=1"`, `"stats#top"`
- Query params go through `params` argument, not in the endpoint string

### Context Object

```json
{
  "pluginName": "astrbot_plugin_xxx",
  "displayName": "My Plugin",
  "pageName": "bridge-demo",
  "pageTitle": "Bridge Demo",
  "locale": "zh-CN",
  "i18n": {}
}
```

## Backend API Registration

Official `guides/plugin-pages.md` **recommends** `astrbot.api.web` helpers for new plugins.
Quart (`jsonify` / `request`) still works for **legacy** handlers — do not mix both proxies in one handler.

```python
from astrbot.api.star import Context, Star
from astrbot.api.web import json_response, request

PLUGIN_NAME = "astrbot_plugin_xxx"

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        context.register_web_api(
            f"/{PLUGIN_NAME}/config",
            self.api_get_config,
            ["GET"],
            "Get config",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/save",
            self.api_save_config,
            ["POST"],
            "Save config",
        )

    async def api_get_config(self):
        return json_response({"key": "value"})

    async def api_save_config(self):
        body = await request.json(default={})
        return json_response({"status": "ok", "echo": body})
```

**Legacy Quart** (existing plugins only):

```python
from quart import jsonify, request
# return jsonify({...}); body = await request.json
```

### Route Format

```python
# ✅ CORRECT — prefixed with plugin name
context.register_web_api(f"/{PLUGIN_NAME}/config", handler, ["GET"], "desc")

# ❌ WRONG — missing plugin name prefix
context.register_web_api("/config", handler, ["GET"], "desc")
```

### Config Read/Write

```python
# Read
config_value = self.config._cfg

# Write (whitelist keys only)
allowed_keys = set(self.config._SCHEMA_DEFAULTS.keys())
for k, v in body.items():
    if k in allowed_keys:
        self.config.set(k, v)
# AstrBot auto-persists; no save_config() needed
```

## Common Pitfalls

### 1. API Route Double Prefix

`bridge.apiGet` automatically prepends the plugin name. Do NOT add it manually.

```js
// ❌ WRONG — bridge forwards to /api/plug/xxx/xxx/voices (double prefix)
await getBridge().apiGet('astrbot_plugin_xxx/voices');

// ✅ CORRECT — bridge forwards to /api/plug/xxx/voices
await getBridge().apiGet('voices');
```

### 2. bridge.upload Only Accepts Single File

`bridge.upload(endpoint, file)` accepts **one File object** only, not FormData. Field name is fixed as `file`.

```js
// ❌ WRONG — FormData not supported
const fd = new FormData();
fd.append('voice_id', id);
fd.append('audio', file);
await bridge.upload('voices/clone', fd);

// ✅ CORRECT — split into init + upload
await apiPost('voices/clone-init', { voice_id: id });
await bridge.upload('voices/clone-file', file);

// ✅ BETTER — use base64 JSON, avoids bridge.upload entirely
const b64 = btoa(String.fromCharCode(...new Uint8Array(await file.arrayBuffer())));
await apiPost('voices/clone-file', { file_b64: b64, filename: file.name });
```

### 3. OpaqueResponseBlocking on Audio

Cross-origin audio requests are blocked in the sandboxed iframe. Use base64 instead.

```python
# Backend: return base64-encoded audio
import base64
audio_bytes = audio_path.read_bytes()
b64 = base64.b64encode(audio_bytes).decode()
return jsonify({"audio_b64": b64, "format": "wav", "mime": "audio/wav"})
```

```js
// Frontend: play via data URI
const result = await apiPost('tts', body);
audioSrc.value = `data:${result.mime};base64,${result.audio_b64}`;
```

### 4. localStorage Not Available

iframe sandbox may restrict localStorage. Use in-memory variables instead.

```js
// ❌ Unreliable
localStorage.setItem('theme', 'dark');

// ✅ In-memory
const isDark = ref(true);
```

### 5. CDN MIME Type Blocked

CDN may return wrong MIME type. Use inline SVG icons instead (~4KB total, zero network dependency).

```js
const ICONS = {
  settings: '<path d="M10.325 4.317..."/>',
  // ...
};
function icon(name) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" 
    viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${ICONS[name] || ''}</svg>`;
}
```

## Security Checklist

| Check | Measure |
|-------|---------|
| Path traversal | Filter `voice_id`: `re.sub(r"[^a-zA-Z0-9_-\u4e00-\u9fff]", "", id)` |
| File size | base64 limit: `len(file_b64) > 20 * 1024 * 1024` |
| Config injection | Key whitelist: `allowed_keys = set(self.config._SCHEMA_DEFAULTS.keys())` |
| File suffix | Whitelist: `suffix not in (".mp3", ".wav")` |
| Error messages | Never expose internal paths, return `str(e)` only |

## Static Resources — 4.28 and below only

> **This whole section is 4.28-specific and does NOT describe 4.29+.**
> 4.29 replaced server-side rewriting with a **path token**
> (`/api/v1/plugins/<plugin>/views/<view>/_t/<token>/`) and **removed** the legacy
> `/api/plugin/page/content/...?asset_token=...` route (PR #10415).
> The one rule that survives both versions: **use plain relative paths**
> (`./style.css`, `./assets/logo.svg`) and never hardcode an asset URL or `asset_token`.

AstrBot automatically rewrites relative paths and appends `asset_token`. Use relative paths (`./style.css`, `./assets/logo.svg`). Do NOT manually concatenate `/api/plugin/page/content/...`.

AstrBot rewrites:
- HTML `src` and `href`
- CSS `url(...)`
- JavaScript `import`, `export ... from`, dynamic `import()`

SPA should use hash routing (history routing needs real files at each path).

## Security Constraints `[version-independent]`

Plugin Pages run in a sandboxed iframe:

```
allow-scripts allow-forms allow-downloads
```

Pages cannot access Dashboard cookies, LocalStorage, or same-origin DOM. Security headers applied:

```
X-Frame-Options: SAMEORIGIN
Content-Security-Policy: frame-ancestors 'self'; object-src 'none'; base-uri 'self'
Cache-Control: no-store
```

## SSE Subscription

```js
const subscriptionId = await bridge.subscribeSSE(
  "events",
  {
    onOpen() { console.log("SSE opened"); },
    onMessage(event) {
      console.log(event.raw, event.parsed, event.lastEventId);
      // event.parsed auto-parses JSON strings
    },
    onError(err) { console.warn("SSE error", err); },
  },
  { topic: "logs" }
);

// Clean up on page unload
window.addEventListener("beforeunload", () => {
  bridge.unsubscribeSSE(subscriptionId);
});
```

## Debugging

| Error | Cause |
|-------|-------|
| `未找到该路由` | API path double-prefix or not registered |
| `Missing uploaded file payload` | bridge.upload passed FormData instead of File |
| `无响应` | bridge.apiPost expected JSON but received binary |
| `OpaqueResponseBlocking` | Cross-origin audio blocked → use base64 |
| `MIME type 不匹配` | CDN issue → switch CDN or inline resource |
| `frame-ancestors` warning | Normal CSP behavior, ignore |

### Testing Workflow

1. Modify `pages/` files → refresh page (no plugin reload needed)
2. Modify `main.py` API → reload plugin
3. Add/delete Page directories → reload plugin
4. Edit `.astrbot-plugin/i18n/<locale>.json` → **reload plugin** (metadata is read at load time)

## Page Internationalization `[version-independent]`

> **Corrected 2026-10-16.** Earlier revisions of this file documented a per-directory
> `_page.json` with `{"title": {"i18n_key": ...}}`. **That file does not exist in
> AstrBot** — `git log --all -S "_page.json"` across `docs/` and `astrbot/` returns
> nothing, and the official guide has always pointed at
> `.astrbot-plugin/i18n/<locale>.json`. Do not create `_page.json`.

Declare page metadata in `.astrbot-plugin/i18n/<locale>.json`, under the
`pages.<page_name>` key (`<page_name>` must match the directory name):

```json
{
  "pages": {
    "studio": {
      "title": "Studio",
      "description": "Plugin management page.",
      "heading": "Plugin Page",
      "refresh": "Refresh"
    }
  }
}
```

`title` becomes the WebUI shell title and the page component name on the plugin detail
page; `description` becomes the component description. Other keys are free-form page
strings read via `bridge.t()`.

- Prefer the older `pages.<page_name>` key when the plugin must also run on `>=4.29`
  (4.29 reads it as an alias of `views.<view_name>`, so one key serves both).
- **Reload the plugin after editing locale files** so the WebUI receives new metadata.
- `4.29+` only: if the current locale has no `title`, the ungrouped sidebar falls back to
  the plugin name and grouped mode to the View directory name.

Use `bridge.t()` in page scripts and `bridge.onContext()` to respond to language switches:

```js
function render() {
  document.title = bridge.t("pages.studio.title", "Studio");
  document.getElementById("heading").textContent = bridge.t("pages.studio.heading", "Plugin Page");
}

await bridge.ready();
render();
bridge.onContext(render);  // Re-render on language switch
```

## 11. Migration to Views (4.29+)

Maps every surface this file documents onto its 4.29 counterpart. Alias column = still
accepted on 4.29, but deprecated; prefer the canonical column for new work.

| Do now (works on **both**) | 4.29 canonical | Notes |
|---|---|---|
| keep `pages/<page_name>/index.html` | `views/<view_name>/index.html` | `pages/` is accepted on 4.29; if both exist, `views/` wins |
| `window.AstrBotPluginView ?? window.AstrBotPluginPage` | `window.AstrBotPluginView` | dual-read makes one build work on both |
| i18n key `pages.<page_name>` | `views.<view_name>` | 4.29 reads `pages` as an alias → `pages` key alone is dual-compatible |
| `metadata.yaml` without a views field | `views:` list (`pages:` alias) | optional; only needed if you declare views explicitly |
| **relative** asset paths (`./app.js`) | same | 4.28 rewrites them; 4.29 resolves them under the `_t/<token>/` prefix |
| read `context.pageName` | `context.pageName` | field name kept for wire compatibility on 4.29 |

**Do NOT do** (breaks on 4.29):

- hardcode `/api/plugin/page/content/...` or append `asset_token` yourself — the route was
  removed (PR #10415);
- depend on server-side HTML/CSS/JS URL rewriting — gone in 4.29;
- create `_page.json` — never existed;
- call `/(pages)/{id}/assets/...` — those endpoints were removed.

**Recommended dual-version plugin** — one build, 4.28 and 4.29:

```text
my_plugin/
├─ pages/studio/index.html      # 4.28 reads it; 4.29 reads it as an alias
├─ views/studio/index.html      # optional: 4.29 prefers it if present
├─ .astrbot-plugin/i18n/zh-CN.json   # key: "pages": { "studio": {...} }
└─ metadata.yaml
```

```js
const bridge = window.AstrBotPluginView ?? window.AstrBotPluginPage;
```

Full 4.29 surface: [`plugin-views.md`](./plugin-views.md).
