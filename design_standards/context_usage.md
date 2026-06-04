# Context Object Usage Guide

`Context` is AstrBot's capability hub, injected during plugin `__init__`, and is the only bridge for plugins to interact with the system core.

## Important Properties

Access managers via `self.context`:

- `self.context.conversation_manager`: Conversation manager
- `self.context.persona_manager`: Persona manager
- `self.context.platform_manager`: Platform manager
- `self.context.provider_manager`: Provider manager
- `self.context.cron_manager`: Cron manager

## Core Methods

### Messaging and Platform

- `send_message(umo: str, message_chain: MessageChain)`: Proactively send a message to a specified source
- `get_platform(platform_type)`: **DEPRECATED** — use `get_platform_inst(platform_id)` (v4.0.0+) <!-- Source: guides/other.md §获取消息平台实例 -->
- `get_platform_inst(platform_id)`: Get platform instance by ID (v4.0.0+)
- `get_all_stars() -> list[StarMetadata]`: Get metadata of all loaded plugins (includes plugin class instance, config, etc.)

### AI and Tools

- `add_llm_tools(*tools)`: Dynamically register function tools
- `get_using_provider(umo)`: Get the current LLM provider
- `get_current_chat_provider_id(umo) -> str`: Get current chat provider ID (v4.5.7+)
- `llm_generate(...)`: Simplified LLM call (v4.5.7+)
- `tool_loop_agent(...)`: Tool loop Agent (v4.5.7+)

### Configuration

- `get_config(umo=None)`: Get current configuration
- `register_web_api(path, handler, methods, desc)`: Register Web API
