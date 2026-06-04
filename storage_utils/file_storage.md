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

## Notes

- `StarTools.get_data_dir()` returns a `Path` object, not a string
- Do not store large files in the plugin root directory
- It is recommended to periodically clean up unused temporary files
