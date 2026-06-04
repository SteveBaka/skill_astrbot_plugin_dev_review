# Configuration Schema (`_conf_schema.json`)

AstrBot uses schemas for automatic configuration parsing and WebUI visualization.

## Basic Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | **Required** | `string`, `text`, `int`, `float`, `bool`, `object`, `list`, `dict`, `template_list`, `file` |
| `description` | string | Configuration description |
| `hint` | string | Hover tooltip |
| `obvious_hint` | bool | Whether to display prominently |
| `default` | any | Default value |
| `options` | list | Dropdown options |
| `invisible` | bool | Whether hidden |

## Type Examples

### string / int / float / bool

```json
{
  "api_key": {
    "type": "string",
    "description": "API 密钥",
    "default": ""
  },
  "max_retry": {
    "type": "int",
    "description": "最大重试次数",
    "default": 3,
    "hint": "建议 1-5"
  },
  "enable_feature": {
    "type": "bool",
    "description": "启用功能",
    "default": true
  }
}
```

### text (multi-line text)

```json
{
  "system_prompt": {
    "type": "text",
    "description": "系统提示词",
    "default": "你是一个助手"
  }
}
```

### dict (key-value pairs, supports template_schema)

```json
{
  "custom_params": {
    "type": "dict",
    "description": "自定义参数",
    "template_schema": {
      "temperature": {
        "type": "float",
        "default": 0.6,
        "slider": {"min": 0, "max": 2, "step": 0.1}
      }
    }
  }
}
```

### template_list (repeated configuration groups, v4.10.4+)

```json
{
  "providers": {
    "type": "template_list",
    "description": "API 供应商列表",
    "templates": {
      "openai": {
        "name": "OpenAI",
        "items": {
          "api_key": {"type": "string", "default": "sk-xxxx"},
          "model": {"type": "string", "default": "gpt-4"}
        }
      }
    }
  }
}
```

### file (file upload, v4.13.0+)

```json
{
  "uploads": {
    "type": "file",
    "description": "上传文件",
    "file_types": [".pdf", ".docx"],
    "default": []
  }
}
```

File storage location: `data/plugins/<plugin_name>/files/<config_key>/`

## Built-in Selectors (_special)

| Value | Return Type | Description |
|-------|-------------|-------------|
| `select_provider` | string | Select model provider |
| `select_provider_tts` | string | Select TTS provider |
| `select_provider_stt` | string | Select STT provider |
| `select_persona` | string | Select persona |
| `select_knowledgebase` | list | Select knowledge base (multi-select) |

```json
{
  "model": {
    "type": "string",
    "description": "默认模型",
    "_special": "select_provider"
  }
}
```

## Usage in Code

```python
from astrbot.api import AstrBotConfig

class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        api_key = self.config.get("api_key")
        
        # Save configuration (call after modification)
        # self.config.save_config()
```

## Configuration Update Mechanism

- Automatically adds missing default values
- Automatically removes configuration items not present in the schema
- Reload the plugin after updating `_conf_schema.json` for changes to take effect
