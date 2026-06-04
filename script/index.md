# Plugin Templates

This directory contains plugin scaffolding templates.

## astrbot-plugin-demo

A minimal AstrBot plugin template with:

- `main.py` — Star subclass with `@filter.command("helloworld")`
- `metadata.yaml` — Plugin metadata
- `_conf_schema.json` — Configuration schema example
- `README.md` — Template README
- `.github/workflows/release.yml` — Auto-release workflow

Use this as a starting point when creating new plugins.

### Quick Start

```bash
cp -r script/astrbot-plugin-demo my_plugin
cd my_plugin
# Edit metadata.yaml, main.py, _conf_schema.json
```
