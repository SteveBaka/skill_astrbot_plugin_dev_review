# File Storage Guidelines

For large files, logs, or plugin-specific resource files, AstrBot recommends following these storage guidelines.

## Directory Convention

All plugin-specific files should be stored in: `data/plugin_data/{plugin_name}/`

## Get Storage Path

```python
from astrbot.api.star import StarTools

data_dir = StarTools.get_data_dir()  # Returns a Path object
data_dir.mkdir(parents=True, exist_ok=True)

# Or use the underlying method
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
plugin_data_path = get_astrbot_data_path() / "plugin_data" / self.name
plugin_data_path.mkdir(parents=True, exist_ok=True)
```

## Hard rule — never write plugin files to the data root

Plugin-owned **persistent** files (caches, bot IDs, session state, tokens on
disk) **must** live under `data/plugin_data/{plugin_name}/`. Writing them
directly under `get_astrbot_data_path()` is a marketplace **LLM Guard** reject
(real case: flowbot adapter wxid cache → package Rejected). See `FIX-39`.

```python
# ❌ WRONG — <data>/my_cache.json
os.path.join(get_astrbot_data_path(), "my_cache.json")

# ❌ WRONG — same, pathlib form
get_astrbot_data_path() / "my_cache.json"

# ✅ OK — <data>/plugin_data/<plugin_name>/my_cache.json
StarTools.get_data_dir() / "my_cache.json"
# or
get_astrbot_data_path() / "plugin_data" / plugin_name / "my_cache.json"
```

System dirs (`logs/`, `metadata/`, `plugins/`, `config/`) are for **reading
core state only** — do not plant plugin caches there either.

## Notes

- `StarTools.get_data_dir()` returns a `Path` object, not a string
- Do not store large files in the plugin root directory
- It is recommended to periodically clean up unused temporary files
- **Attachments / media (AstrBot ≥4.28.1 #10042)**: core **preserves original image attachment paths after event cleanup** so agents can keep accessing attachments. Prefer `Image`/`Record`/`File` component resolution (`convert_to_file_path()`) or paths obtained during the event; still avoid assuming plugin-root temp dirs survive reinstall.
- **Proactive media / adapter sends**: if the platform SDK needs a local path, use component `convert_to_file_path()` (official adapter guide) rather than hand-parsing `file://` prefixes.

