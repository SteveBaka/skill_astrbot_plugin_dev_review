# Plugin Internationalization (i18n)

Plugins can provide translation files in `.astrbot-plugin/i18n/*.json` to let the WebUI display corresponding text based on language.

## Directory Structure

```text
your_plugin/
  metadata.yaml
  _conf_schema.json
  .astrbot-plugin/
    i18n/
      zh-CN.json
      en-US.json
```

Language file names use WebUI locale (e.g., `zh-CN.json`, `en-US.json`). File content must be a JSON object.

When there is no corresponding translation or a field is missing, it falls back to default text:
- Plugin name/description falls back to `metadata.yaml`
- Configuration item text falls back to `_conf_schema.json`

## Metadata Translation

```json
{
  "metadata": {
    "display_name": "天气助手",
    "short_desc": "一句话天气查询。",
    "desc": "查询天气并提供出行建议。"
  }
}
```

## Configuration Item Translation

`config` nests translations for `_conf_schema.json` text by configuration item name:

```json
{
  "config": {
    "enable": {
      "description": "启用",
      "hint": "是否启用这个插件。"
    },
    "mode": {
      "description": "模式",
      "labels": ["快速", "安全"]
    }
  }
}
```

> `options` are configuration save values and are not recommended for translation. Use `labels` for dropdown display text.

## Nested Configuration Translation

`object` type configurations use the same field structure for nesting:

```json
{
  "config": {
    "sub_config": {
      "name": {
        "description": "名称",
        "hint": "显示在消息中的名称。"
      }
    }
  }
}
```

## template_list Translation

Template names go in `templates.<template_name>.name`, and fields within templates continue nesting:

```json
{
  "config": {
    "rules": {
      "description": "规则",
      "templates": {
        "default": {
          "name": "默认模板",
          "threshold": {
            "description": "阈值",
            "hint": "达到该值后触发规则。"
          }
        }
      }
    }
  }
}
```

## Constraints

- Only reads from the `.astrbot-plugin/i18n` directory
- Must use nested JSON structure; dot-notation flat keys are not supported
