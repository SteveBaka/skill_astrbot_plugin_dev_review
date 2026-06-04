# Persona Control

PersonaManager manages persona presets (system prompts + tool configurations).

## Access

```python
pm = self.context.persona_manager
```

## CRUD Methods

```python
# Get
persona = await pm.get_persona(persona_id)
all_personas = await pm.get_all_personas()

# Create
await pm.create_persona(persona_id="my_persona", system_prompt="You are...", tools=["tool1"])

# Update
await pm.update_persona(persona_id="my_persona", system_prompt="New prompt")

# Delete
await pm.delete_persona(persona_id="my_persona")
```

## Persona Resolution Priority

```
session-level > conversation-level > global default
```

1. **Session-level**: Set per-session persona via conversation manager
2. **Conversation-level**: Set per-conversation persona
3. **Global default**: System-wide default persona

## Setting Persona

```python
# At conversation level
await conv_mgr.update_conversation(umo, conversation_id=cid, persona_id="my_persona")

# Disable persona with [%None]
```

## Folder Management

Personas can be organized into folders for better management via the WebUI.
