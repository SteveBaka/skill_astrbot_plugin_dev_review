# Plugin Dashboard Pages

> **Primary reference**: https://docs.astrbot.app/dev/star/guides/plugin-pages.html

AstrBot supports plugins exposing Dashboard pages through the `pages/` directory. AstrBot scans `pages/<page_name>/index.html`; directories without `index.html` are ignored.

> For simple configuration items, prefer `_conf_schema.json`. Plugin Pages are more suitable for complex forms, dashboards, logs, file upload/download, SSE, and custom interactions.

> **v4.25.3+**: Plugin pages now automatically appear in the Dashboard sidebar with MDI icon support. Pages also sync with the Dashboard theme (dark/light mode) automatically.

## Directory Structure

```text
my_plugin/
├── main.py
└── pages/
    └── studio/
        ├── index.html      # Entry point
        ├── app.js          # Vue SPA (router + components + API client)
        ├── style.css       # Styles
        └── _page.json      # Page metadata (i18n)
```

## Recommended Tech Stack

| Approach | Use Case |
|----------|----------|
| Vue 3 CDN + SPA | Medium complexity, no build step needed |
| Vanilla HTML + JS | Simple pages |
| Vue + Vite build | Complex apps — **not supported** (AstrBot has no Node build) |

Vue 3 CDN: `vue.global.prod.js` (~33KB gzip) + `vue-router.global.prod.js`, runs directly in browser.

## Bridge SDK (window.AstrBotPluginPage)

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

```python
from quart import jsonify, request
from astrbot.api.star import Context, Star

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
        return jsonify({"key": "value"})

    async def api_save_config(self):
        body = await request.json
        return jsonify({"status": "ok"})
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

## Static Resources

AstrBot automatically rewrites relative paths and appends `asset_token`. Use relative paths (`./style.css`, `./assets/logo.svg`). Do NOT manually concatenate `/api/plugin/page/content/...`.

AstrBot rewrites:
- HTML `src` and `href`
- CSS `url(...)`
- JavaScript `import`, `export ... from`, dynamic `import()`

SPA should use hash routing (history routing needs real files at each path).

## Security Constraints

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

## Page Internationalization

`_page.json` in page directory defines the page title and description shown in WebUI:

```json
{
  "title": { "i18n_key": "pages.studio.title" },
  "description": { "i18n_key": "pages.studio.desc" }
}
```

The `i18n_key` values map to entries in `.astrbot-plugin/i18n/<locale>.json`. The `title` is used as the WebUI shell title and the page component name in the plugin detail page. The `description` is used as the page component description.

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
