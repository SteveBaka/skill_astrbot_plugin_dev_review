# Telegram Media Group Handling

Telegram splits multi-image/video "albums" into separate Updates. AstrBot's Telegram adapter merges them using a debounce mechanism.

## Core Logic

### Debounce Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `telegram_media_group_timeout` | 2.5s | Debounce delay, resets on each new message in the group |
| `telegram_media_group_max_wait` | 10.0s | Hard timeout, forces merge even if messages keep arriving |

### Merge Strategy

1. **Base metadata**: Uses the first message's `message_str` (caption), reply chain, and session context
2. **Component aggregation**: Extracts media components (Image, Video) from all subsequent messages and appends to the base message's `message` list
3. **Event dispatch**: Submits a single `AstrMessageEvent` with the complete merged `MessageChain`

## Key Methods

- `handle_media_group_message(update, context)`: Intercepts messages with `media_group_id`, manages cache and scheduling
- `process_media_group(media_group_id)`: Core merge function, extracts from cache, reassembles `AstrBotMessage`, triggers `handle_msg`

## Impact on Plugin Developers

- **Event density**: For Telegram albums, the plugin receives only ONE `AstrMessageEvent`. `event.message` may contain multiple `Image` or `Video` components.
- **Response delay**: Telegram album messages have an inherent ~2.5s delay for media collection. This is expected behavior.

## Edge Cases

- Different captions on different images: only the first message's text is preserved
- Messages arriving after `max_wait` are treated as separate events
