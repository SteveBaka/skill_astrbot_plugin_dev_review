# Plugin Views (AstrBot 4.29+)

> **Primary reference**: https://docs.astrbot.app/dev/star/guides/plugin-pages.html
> (the page keeps the `plugin-pages` URL; its **content** is "Plugin Views" since 4.29.0)

> **Applies to**: AstrBot `>=4.29,<5`.
> For `4.25.3 – 4.28.x` use [`plugin-pages.md`](./plugin-pages.md) — that file documents the
> pre-rename surface. **Sections marked `[version-independent]` are safe on both.**
>
> **Evidence base** (do not "improve" these claims from memory):
> `docs/en/dev/star/guides/plugin-pages.md` at tag **v4.29.0** (byte-identical to master),
> plus commit `4b049d1e` (PR #10307, the rename) and `8831d950` (PR #10415, path-token
> assets + completing the rename). Where this file disagrees with a core release note,
> the release note wins.

## 1. Terminology and the rename

"Plugin Pages" became "Plugin Views" in **4.29.0** (PR #10307). The rename is
**alias-compatible everywhere** — the commit message lists the guarantees:

> Views preferred, **Pages kept as a compatible alias everywhere**:
> `StarMetadata.pages → views`; `metadata.yaml` accepts `views:` (`pages:` alias);
> `views/` preferred, `pages/` still accepted; v1 API gains `/plugins/view(s)` alongside
> `/plugins/page(s)`; `window.AstrBotPluginView` with `AstrBotPluginPage` as alias;
> i18n `views.<name>.*` preferred with `pages.<name>.*` alias; frontend
> `/plugin-view/...` with `/plugin-page/...` redirecting.

| Surface | 4.29 canonical | 4.29 alias | 4.28 and below |
|---------|----------------|------------|----------------|
| Directory | `views/` | `pages/` | `pages/` only |
| Bridge global | `window.AstrBotPluginView` | `window.AstrBotPluginPage` | `AstrBotPluginPage` only |
| i18n key prefix | `views.<view_name>` | `pages.<page_name>` | `pages.<page_name>` only |
| `metadata.yaml` | `views:` | `pages:` | `pages:` (or neither) |
| v1 API | `/plugins/view(s)`, `/plugins/{id}/views` | `/plugins/page(s)`, `/plugins/{id}/pages` (**deprecated**) | `/plugins/page(s)` only |
| Static asset auth | path token `.../views/<view>/_t/<token>/` | — | server-side URL rewriting + `asset_token` query |
| v1 tag name | `Plugin Views` | — | `Plugin Pages` |

**If both `views/` and `pages/` exist, `views/` wins**
(`PLUGIN_PAGE_ROOT_DIR_NAMES = ("views", "pages")`,
`astrbot/dashboard/services/plugin_page_service.py:29`).

Full migration checklist: [`plugin-pages.md` § Migration](./plugin-pages.md#11-migration-to-views-429).

## 2. Directory layout `[version-independent]`

Each direct child directory under `views/` is one View. AstrBot only discovers
`views/<view_name>/index.html`; directories without `index.html` are ignored.

```text
astrbot_plugin_view_demo/
├─ main.py
├─ metadata.yaml
└─ views/
   ├─ bridge-demo/
   │  ├─ index.html
   │  ├─ app.js
   │  ├─ style.css
   │  └─ assets/
   │     └─ logo.svg
   └─ settings/
      └─ index.html
```

- `view_name` rules: non-empty, not `.` / `..`, no leading `.`, no `/` or `\`.
- Users open views from the **plugin detail page** in the WebUI. Since 4.29 they are also
  listed in the sidebar's **Extensions** group, optionally grouped per plugin.

## 3. Development flow `[version-independent]`

1. Create `views/<view_name>/index.html`.
2. Talk to the Dashboard through `window.AstrBotPluginView`.
3. Register backend APIs with `context.register_web_api()` in `main.py`.
4. Read the request and return a response using `astrbot.api.web`.
5. Reload the plugin after **adding or removing View directories**, and after **editing
   locale files**. Static asset edits only need a View refresh.

## 4. Backend Web APIs `[version-independent]`

Plugin backend code should use `astrbot.api.web`. Do **not** expose raw FastAPI,
Starlette, or Quart request objects as your public business API.

### 4.1 Route registration

```python
from astrbot.api.star import Context, Star
from astrbot.api.web import error_response, json_response, request

PLUGIN_NAME = "astrbot_plugin_view_demo"

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        context.register_web_api(
            f"/{PLUGIN_NAME}/ping", self.page_ping, ["GET"], "View ping"
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/settings/save", self.save_settings, ["POST"], "Save View settings"
        )

    async def page_ping(self):
        limit = request.query.get("limit", 20, type=int)
        return json_response({"message": "pong", "limit": limit, "username": request.username})
```

The registered route **must include the plugin name prefix**; the bridge endpoint used
by the View **must not**. The Dashboard forwards `bridge.apiGet("items/123")` to
`/api/v1/plugins/extensions/<plugin_name>/items/123`, so `/<plugin_name>/items/<item_id>`
matches and `item_id` arrives as a keyword argument:

```python
async def get_item(self, item_id: str):
    return json_response({"item_id": item_id})
```

Dynamic segments: `<name>` matches one path segment; `<path:name>` matches the rest.

### 4.2 Request object

```python
from astrbot.api.web import request
```

`request` is a context proxy, valid only while a plugin Web API handler runs.

| API | Description |
| --- | --- |
| `request.method` | HTTP method |
| `request.path` | Current Dashboard API path |
| `request.plugin_name` | Plugin name parsed from the extension path |
| `request.username` | Current Dashboard username, possibly `None` |
| `request.headers` / `request.cookies` | Headers / cookies |
| `request.content_type` | Request Content-Type |
| `request.client_host` | Client address |
| `request.path_params` | Dynamic route parameters |
| `request.query` | Query params — `.get(key, default, type=int)`, `.getlist(key)` |
| `await request.body()` | Raw body bytes |
| `await request.json(default={})` | JSON body, `default` on parse failure |
| `await request.form()` | Form fields **without** uploaded files |
| `await request.files()` | Uploaded files |

`request.form()` and `request.files()` cache the parsed multipart data, so calling both
in one handler is fine.

### 4.3 Responses

```python
from astrbot.api.web import (
    error_response, file_response, json_response, stream_response, PluginUploadFile,
)
```

- `json_response({...})`
- `error_response("invalid threshold", status_code=400)`
- `file_response(path, filename="export.json", content_type="application/json")`
- `stream_response(async_gen())` — for SSE; must yield `data: ...\n\n`

Returning a `dict`, `list`, `(body, status_code)`, or a lower-level Response still works.
Returning `{"status": "ok", "data": value}` is unwrapped by the bridge (see §5.3).

### 4.4 Uploads

```python
from pathlib import Path
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path
from astrbot.api.web import PluginUploadFile, error_response, json_response, request

async def import_file(self):
    form = await request.form()
    files = await request.files()
    upload: PluginUploadFile | None = files.get("file")
    if not isinstance(upload, PluginUploadFile):
        return error_response("missing file")

    target_dir = (
        Path(get_astrbot_plugin_data_path())
        / (request.plugin_name or "unknown_plugin") / "imports"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / Path(upload.filename).name
    await upload.save(target)
    return json_response({"filename": upload.filename, "content_type": upload.content_type,
                          "tag": form.get("tag")})
```

### 4.5 Quart compatibility

Handlers registered through `register_web_api()` still run in a Quart-compatible request
context, so legacy `from quart import jsonify, request` keeps working. **Do not mix the
two `request` proxies in one handler** — migrate one handler at a time.

## 5. Bridge API

The View iframe cannot access Dashboard cookies, LocalStorage, or the parent DOM.
Everything that needs Dashboard identity goes through the bridge.

```js
const bridge = window.AstrBotPluginView;   // 4.29+; alias: window.AstrBotPluginPage
```

AstrBot injects `/api/plugin/page/bridge-sdk.js` into returned HTML (the path stays
`page` — it is a wire-compatible surface). **Do not import it manually.**

> **Injection is asynchronous.** A static top-level `const bridge = window.AstrBotPluginView;`
> may be `undefined` if the inline script runs before injection. Use an external
> `type="module"` script (recommended), or poll/wait for `bridge.ready()`.

### 5.1 Context

`ready()` waits for the parent page to send the initial context.

```json
{
  "pluginName": "astrbot_plugin_view_demo",
  "displayName": "Plugin View Demo",
  "pageName": "bridge-demo",
  "pageTitle": "Bridge Demo",
  "locale": "en-US",
  "i18n": {},
  "isDark": false
}
```

`pageName` / `pageTitle` keep their historical names on 4.29 (wire compatibility) — read
them as-is, do not expect `viewName`.

| API | Returns | Description |
| --- | --- | --- |
| `ready()` | `Promise<context>` | Waits for the bridge, returns initial context |
| `getContext()` | `context \| null` | Latest context, synchronously |
| `getLocale()` | `string` | WebUI locale, default `zh-CN` |
| `getI18n()` | `object` | Plugin i18n resources |
| `t(key, fallback)` | `string` | Dot-notation lookup, `fallback` when missing |
| `onContext(handler)` | `() => void` | Listen for context changes, returns unsubscribe |

There is **no** `onContextChange()`. Use `onContext()`.

### 5.2 HTTP methods

- `apiGet(endpoint, params)` — GET, `params` become query parameters
- `apiPost(endpoint, body)` — POST JSON
- `upload(endpoint, file)` — one `File`, `multipart/form-data`, field name always `file`
- `download(endpoint, params, filename)` — triggers a browser download; resolves to
  `{"filename": "..."}`
- `subscribeSSE(endpoint, handlers, params)` — returns `Promise<subscriptionId>`;
  handlers: `onOpen`, `onMessage`, `onError`
- `unsubscribeSSE(subscriptionId)`

### 5.3 JSON result contract

- backend returns `{"status": "ok", "data": value}` → Promise resolves to **`value`**
- backend returns plain JSON, e.g. `{"message": "pong"}` → resolves to that **full body**
- backend returns `{"status": "error", "message": "..."}`, or the HTTP call fails →
  Promise **rejects** with `Error`

For View-only APIs prefer plain business JSON; use `error_response()` for failures and
`try/catch` on the View.

### 5.4 Endpoint rules

`endpoint` is a **plugin-local relative path**: `stats`, `settings/save`, `files/export`.

Rejected: empty string, `\`, a URL scheme, query strings, fragments, and empty / `.` /
`..` segments. Prefer **no leading `/`** — the bridge strips it for compatibility.

Query data goes in `params`, never in the endpoint string:

```js
await bridge.apiGet("stats", { limit: 20 });   // ✅
await bridge.apiGet("stats?limit=20");         // ❌
```

`bridge.apiGet` prepends the plugin name itself — adding it again double-prefixes.

### 5.5 SSE

```js
const id = await bridge.subscribeSSE(
  "events",
  {
    onOpen() { /* ... */ },
    onMessage(ev) { /* ev.raw, ev.parsed (auto-JSON), ev.lastEventId, ev.eventType */ },
    onError(err) { /* ... */ },
  },
  { topic: "logs" },
);
window.addEventListener("beforeunload", () => { bridge.unsubscribeSSE(id); });
```

Backend must return `text/event-stream` and end every message with a blank line.
**Never** open a native `EventSource("/api/v1/...")` from the View — it cannot send
`Authorization`, so you get 401. Use `bridge.subscribeSSE()`.

## 6. Static assets — path token (4.29+)

Use **plain relative paths**:

```html
<link rel="stylesheet" href="./style.css" />
<script type="module" src="./app.js"></script>
<img src="./assets/logo.svg" alt="" />
```

AstrBot authenticates view assets with a **path token**: the `content_path` returned by
the entry config endpoint looks like `/api/v1/plugins/<plugin>/views/<view>/_t/<token>/`.
Relative URLs inside the page resolve under that prefix and inherit the token by normal
URL resolution. **Content is served as-is — no server-side rewriting.** The token lives
as long as the dashboard session and is scoped to exactly that plugin and view.

- Do **not** hardcode content URLs.
- Do **not** append `asset_token` yourself.
- Do **not** rely on `..` to escape the View root.
- The legacy `/api/plugin/page/content/...?asset_token=...` form is **removed** (PR #10415);
  so are `/api/v1/plugins/page/assets` and `.../{id}/pages/{name}/assets/...`.

A SPA should use **hash routing** (history routing needs a real file at every path).

## 7. Light / dark theme `[version-independent]`

The bridge keeps `data-theme` on `<html>`: `<html data-theme="light">` /
`<html data-theme="dark">`. "Follow System" still resolves to one of the two.

```css
:root { --bg: #ffffff; --text: #1a1a1a; }
[data-theme="dark"] { --bg: #1a1a1a; --text: #e0e0e0; }
body { background: var(--bg); color: var(--text); }
```

The server injects `data-theme` into returned HTML to avoid a flash. For runtime
reactions read `bridge.getContext()?.isDark` and subscribe with `onContext()`.

## 8. View metadata and internationalization (4.29+)

Put View metadata in `.astrbot-plugin/i18n/<locale>.json`, nested under
**`views.<view_name>`**. `views` is a top-level field alongside `metadata` and `config`;
`<view_name>` must exactly match the directory name under `views/`.

```text
astrbot_plugin_view_demo/
├─ views/bridge-demo/index.html
└─ .astrbot-plugin/i18n/{zh-CN,en-US}.json
```

```json
{
  "views": {
    "bridge-demo": {
      "title": "Bridge Demo",
      "description": "Shows how a view reads the WebUI locale and translations.",
      "heading": "Plugin View"
    }
  }
}
```

| Field | Required | Purpose |
| --- | --- | --- |
| `title` | No | View name in the sidebar, WebUI shell, and plugin detail page |
| `description` | No | View description on the plugin detail page |
| other keys | No | View-specific strings, read with `bridge.t()` |

- Use `views` for new plugins; `pages` remains only a compatibility alias.
- **Reload the plugin after editing locale files** so the WebUI picks up new metadata.
- If the current locale has no `title`: the **ungrouped** sidebar shows the plugin name;
  **grouped** mode shows the View directory name (the group already shows the plugin).

> **There is no `_page.json`.** A per-directory `_page.json` with `{title: {i18n_key: ...}}`
> does not exist in AstrBot — not in 4.28, not in 4.29
> (`git log --all -S "_page.json"` over `docs/` + `astrbot/` is empty). Locale metadata
> lives only in `.astrbot-plugin/i18n/<locale>.json`.

## 9. Security constraints `[version-independent]`

Views run in a restricted iframe: `allow-scripts allow-forms allow-downloads`.

They cannot access Dashboard cookies, LocalStorage, or the parent DOM, and cannot bypass
the bridge to reuse Dashboard auth. Asset responses carry:

- `X-Frame-Options: SAMEORIGIN`
- `Content-Security-Policy: frame-ancestors 'self'; object-src 'none'; base-uri 'self'`
- `Cache-Control: no-store`
- `X-Content-Type-Options: nosniff`

Backend handlers must still validate input — never trust paths, filenames, formats, or
numeric ranges sent by a View.

| Check | Measure |
|-------|---------|
| Path traversal | Whitelist/regex the id: `re.sub(r"[^a-zA-Z0-9_-\u4e00-\u9fff]", "", id)` |
| File size | e.g. base64 limit `len(file_b64) > 20 * 1024 * 1024` |
| Config injection | Key whitelist: `allowed_keys = set(self.config._SCHEMA_DEFAULTS.keys())` |
| File suffix | Whitelist: `suffix not in (".mp3", ".wav")` |
| Error messages | Never expose internal paths; return `str(e)` only |

## 10. Practical guidance (skill value-add) `[version-independent]`

**Tech stack**

| Approach | Use case |
|----------|----------|
| Vue 3 CDN + SPA | Medium complexity, no build step |
| Vanilla HTML + JS | Simple views |
| Vue + Vite build | **Not supported** — AstrBot has no Node build step |

Vue 3 CDN: `vue.global.prod.js` (~33KB gzip) + `vue-router.global.prod.js`.

**Known pitfalls**

1. `bridge.upload(endpoint, file)` takes **one `File`**, not `FormData`. Need extra fields?
   Do a separate `apiPost` first, or send base64 JSON.
2. Cross-origin audio is blocked in the sandbox (`OpaqueResponseBlocking`) — return base64
   and play it from a `data:` URI.
3. `localStorage` may be unavailable in the iframe — keep state in memory.
4. CDN responses can carry a wrong MIME type — prefer inline SVG over icon-font CDNs.

## 11. Debugging

| Symptom | Cause |
|---------|-------|
| View missing | no `views/<view_name>/index.html`, plugin disabled, or detail page not refreshed |
| Bridge undefined | script ran before injection → use an external `type="module"` script |
| Route not matched | registered route lacks `/{PLUGIN_NAME}` prefix, or the endpoint includes it |
| Empty query/JSON | GET values must go through `apiGet(endpoint, params)`; POST through `apiPost` |
| Empty upload | `upload()` always uses field name `file`; read `(await request.files()).get("file")` |
| SSE silent | response not `text/event-stream`, or messages lack the trailing blank line |
| SSE 401 | native `EventSource` used instead of `bridge.subscribeSSE()` |
| `未找到该路由` | double plugin-name prefix, or the handler was never registered |
