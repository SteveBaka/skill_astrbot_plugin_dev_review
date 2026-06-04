# metadata.yaml & Project Structure Validation

## 1. Required Files

| File | Required | Notes |
|------|----------|-------|
| `main.py` | ✅ | Plugin entry point |
| `metadata.yaml` | ✅ | Plugin metadata |
| `README.md` | Recommended | Documentation |
| `_conf_schema.json` | Recommended | Config definition |
| `requirements.txt` | Recommended | Python dependencies |
| `LICENSE` | Recommended | License |
| `.gitignore` | Recommended | Git ignore rules |

## 2. metadata.yaml Field Validation

**Required fields**:

| Field | Rule |
|-------|------|
| `name` | Non-empty, `astrbot_plugin_` prefix recommended |
| `desc` or `description` | Non-empty, **cannot have both** |
| `version` | Non-empty, format like `v1.0.0` |
| `author` | Non-empty |
| `repo` | Non-empty, valid GitHub URL |

**Optional fields**: `display_name`, `short_desc`, `astrbot_version`, `support_platforms`, `tags`, `social_link`

**Optional files**:
- `logo.png` — Plugin logo (1:1 ratio, recommended 256x256)
- `skills/` — Directory containing Skill definitions (auto-registered by AstrBot)

**Optional field details** (from `star/plugin-new.md`):

| Field | Type | Description |
|-------|------|-------------|
| `short_desc` | string | One-line summary for marketplace cards; falls back to `desc` if omitted |
| `astrbot_version` | string | PEP 440 format, no `v` prefix (e.g., `>=4.16,<5`). Blocks loading if unsatisfied |
| `support_platforms` | list[str] | Platform keys: `aiocqhttp`, `telegram`, `discord`, `wecom`, `lark`, `dingtalk`, `slack`, `kook`, `misskey`, `line`, etc. |

## 3. Common metadata.yaml Errors

```
❌ desc and description both present
❌ version missing
❌ repo is not a valid URL
❌ name uses reserved words or special characters
```

## 4. _conf_schema.json Validation (if exists)

- Must be valid JSON
- Each config item must have `type` field
- `type` must be: `string`, `text`, `int`, `float`, `bool`, `object`, `list`, `dict`, `template_list`, `file`
- Recommended: `description` and `default` for each item

## 5. requirements.txt Validation (if exists)

- One package per line, valid format
- Must NOT include `astrbot` (AstrBot is the runtime, not a dependency)
- Must NOT include `quart` (already bundled with AstrBot)
- Version constraints should be reasonable (avoid over-pinning)
- Every third-party `import` in .py files must have a corresponding entry in requirements.txt
- Every entry in requirements.txt must be actually imported somewhere in the code

### Cross-Check: imports vs requirements.txt

**Audit rule**: Scan all `.py` files for `import X` / `from X import ...`. For each third-party package (not `astrbot.*`, not Python stdlib), verify it appears in `requirements.txt`.

Common third-party packages that MUST be in requirements.txt:

| Package | Import Statement |
|---------|-----------------|
| `aiohttp` | `import aiohttp` |
| `httpx` | `import httpx` |
| `aiofiles` | `import aiofiles` |
| `pydantic` | `from pydantic import ...` |
| `jinja2` | `from jinja2 import ...` |

Packages that should NOT be in requirements.txt (already provided by AstrBot or Python):

| Package | Reason |
|---------|--------|
| `astrbot` | Runtime environment |
| `quart` | Bundled with AstrBot |
| `asyncio` | Python stdlib |
| `json` | Python stdlib |
| `pathlib` | Python stdlib |

### Example (from real plugin)

`astrbot_plugin_synochat_adapter/requirements.txt`:
```
aiohttp
```

Only the third-party dependency that AstrBot doesn't provide. No version pinning needed for simple cases.

## Output Format

```markdown
### Structure Validation Result

| Check | Status | Detail |
|-------|--------|--------|
| main.py | ✅ | Exists |
| metadata.yaml | ✅ | Exists, fields complete |
| _conf_schema.json | ⚠️ | Missing, recommended |
| README.md | ✅ | Exists |
| requirements.txt | ⚠️ | Missing |
| .gitignore | ✅ | Exists |

metadata.yaml fields:
- name: astrbot_plugin_example ✅
- desc: Example plugin ✅
- version: v1.0.0 ✅
- author: Test ✅
- repo: https://github.com/... ✅
```
