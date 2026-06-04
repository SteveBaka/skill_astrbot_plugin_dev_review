# Visual Utilities (HTML Rendering & Text-to-Image)

> **Playground**: Use [AstrBot Text2Image Playground](https://t2i-playground.astrbot.app/) to visually edit and test HTML templates online.

## text_to_image (Star method)

```python
async def text_to_image(self, text: str, return_url: bool = True) -> str
```

Converts plain text to image using the active template. **This is a `Star` class method** — call with `self.text_to_image()`.

```python
@filter.command("image")
async def on_image(self, event: AstrMessageEvent, text: str):
    url = await self.text_to_image(text)
    # path = await self.text_to_image(text, return_url=False)  # save to local file
    yield event.image_result(url)
```

## html_render (Star method)

```python
async def html_render(self, tmpl: str, data: dict, return_url: bool = True, options: dict | None = None) -> str
```

Renders Jinja2 HTML template to image. **This is a `Star` class method** — call with `self.html_render()`. Uses Playwright under the hood.

```python
TMPL = '''
<div style="font-size: 32px;">
<h1>Todo List</h1>
<ul>
{% for item in items %}
    <li>{{ item }}</li>
{% endfor %}
</ul>
</div>
'''

@filter.command("todo")
async def custom_t2i(self, event: AstrMessageEvent):
    url = await self.html_render(TMPL, {"items": ["Eat", "Sleep", "Play"]})
    yield event.image_result(url)
```

## Render Options (Playwright screenshot API)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `timeout` | float | — | Screenshot timeout (ms) |
| `type` | `"jpeg"` / `"png"` | `"jpeg"` | Image format |
| `quality` | int | 40 | JPEG quality (1-100), PNG only |
| `omit_background` | bool | — | Transparent background (PNG only) |
| `full_page` | bool | True | Capture full scrollable page |
| `clip` | dict | — | Clip region `{x, y, width, height}` |
| `animations` | `"allow"` / `"disabled"` | — | CSS animations |
| `caret` | `"hide"` / `"initial"` | `"hide"` | Text caret visibility |
| `scale` | `"css"` / `"device"` | — | `"css"` = CSS pixels, `"device"` = device scale |

## SDK Methods (advanced)

```python
from astrbot.api import html_renderer

await html_renderer.initialize()

# Default text-to-image
await html_renderer.render_t2i(text="...", use_network=True, return_url=False, template_name=None)

# Custom template
await html_renderer.render_custom_template(tmpl_str="...", tmpl_data={}, return_url=False, options=None)
```

## Template Management

```python
TemplateManager:
    list_templates()
    get_template(name)
    create_template(name, content)
    update_template(name, content)
    delete_template(name)
    reset_default_template()
```
