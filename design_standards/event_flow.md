# Message Flow Model

AstrBot message processing follows a clear flow process.

## Core Flow

```
1. Receive → Platform adapter receives raw message
2. Convert → Call convert_message to wrap as AstrBotMessage (see platform_adapters/message_conversion.md)
3. Commit → Wrap as AstrMessageEvent and submit to event queue via commit_event
4. Dispatch → PlatformManager dispatches events to all plugin Handlers by priority
5. Process → Plugin executes business logic (if stop_event() is called, flow terminates)
6. LLM  → If not intercepted and trigger conditions are met, call the configured LLM (see agent/invoke-llm.md)
7. Decorate → Call on_decorating_result hook before sending (see agent/hooks.md)
8. Reply → Call event.send() or yield, triggering adapter send method
9. Send → Adapter calls platform SDK to send the message
```

## Key Objects

| Step | Object | Reference |
|------|--------|-----------|
| Convert | `AstrBotMessage` | `messages/model.md` |
| Commit/Dispatch | `AstrMessageEvent` | `messages/events.md` |
| Process | `filter` decorators | `references/core-concepts.md` |
| Reply | `MessageChain` / `MessageEventResult` | `messages/components.md` |
