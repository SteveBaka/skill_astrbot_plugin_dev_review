# Core Architecture Overview

AstrBot adopts a **Plugin-based** and **Event-driven** architecture.

## Core Manager Responsibilities

| Manager | Responsibility | Detailed Documentation |
|---------|---------------|----------------------|
| **PluginManager** | Plugin loading, unloading, reloading, and metadata management | — |
| **PlatformManager** | Manages message platform adapters, dispatches events | `platform_adapters/adapter_interface.md` |
| **ProviderManager** | Manages LLM, STT, TTS, and other service providers | `agent/invoke-llm.md` |
| **ConversationManager** | Manages user conversation history, context storage, and switching | `agent/conversation.md` |
| **PersonaManager** | Manages persona settings (system prompts and tool configurations) | — |
| **CronManager** | Manages scheduled tasks | `agent/cron.md` |

## Core Design Principles

1. **Decoupling**: Core system is highly decoupled from platform adapters, AI providers, and plugins
2. **Unified Model**: All platform messages are converted into a unified `AstrBotMessage` model (see `messages/model.md`)
3. **Plugin-Based**: Functionality is implemented through plugins; the core only provides basic scheduling capabilities

## Message Flow

See `design_standards/event_flow.md` for the complete flow process.

```
Receive → Convert → Commit → Dispatch → Process → LLM → Decorate → Reply → Send
```
