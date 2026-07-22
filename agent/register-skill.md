# Register Skill (AstrBot Native Skill System)

AstrBot has a native Skill system where plugins can bundle AI capabilities (Skills) that get auto-registered by AstrBot's SkillManager.

> This is AstrBot's own Skill concept — different from Kilo Skills or other AI tool Skill systems.

## Bundling Skills with a Plugin

Plugins can provide a `skills/` directory. After AstrBot loads the plugin, valid Skills inside are automatically included in the Skill Manager, with their source shown as the plugin.

### Multiple Skills

```text
your_plugin/
  metadata.yaml
  main.py
  skills/
    web-search-helper/
      SKILL.md
    report-writer/
      SKILL.md
```

### Single Skill

If `skills/` itself is one Skill, place `SKILL.md` directly under it:

```text
your_plugin/
  skills/
    SKILL.md
```

In this case, the Skill name uses the plugin directory name.

## Behavior

- Plugin-provided Skills appear as **read-only** sources in the WebUI Skills page
- They can be enabled or disabled, but cannot be deleted or edited from Local Skills
- When the plugin is uninstalled or updated, its bundled Skills change with the plugin files
- Skills can execute in Local or Sandbox environments

## SKILL.md Format

Each Skill's `SKILL.md` should contain:

```markdown
---
name: my-skill-name
description: What this skill does and when to use it
---

# Skill Content

Instructions, context, and references for the AI agent.
```

## Registration Flow

1. Plugin is loaded by AstrBot's PluginManager
2. PluginManager scans `skills/` directory in the plugin
3. Valid `SKILL.md` files are registered with SkillManager
4. Skills appear in WebUI and become available to the agent system
5. On plugin uninstall/update, Skills are removed/refreshed

## Plugin `skills/` vs Workspace Skills

| Source | Where | Typical use |
|--------|--------|-------------|
| **Plugin-bundled** | `your_plugin/skills/` | Ships with plugin; read-only in WebUI; removed/updated with plugin |
| **Workspace skills** | Session / project workspace (runtime, ≥4.26.0) | Loaded into requests when configured; discovery hardened by core |

Do not confuse AstrBot native Skills with this Kilo skill repo. For plugin authors, prefer documenting both if your product relies on either.

Backups may include the skills directory (≥4.26.0). Versioned skill download archive names are handled by core (≥4.26.7).

## Usage in Agent System

Registered Skills appear in the skill manager and can be used by the agent system. The agent reads each Skill's `SKILL.md` for instructions.

Official plugin overview: `docs/en/dev/star/plugin-new.md` (not legacy `docs/en/dev/plugin.md`).
