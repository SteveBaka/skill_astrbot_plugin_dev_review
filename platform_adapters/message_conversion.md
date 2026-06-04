# Message Conversion Logic

`convert_message` is the most critical method in an adapter, mapping platform raw messages to AstrBot's unified model.

## Conversion Requirements

The following core fields must be populated in `convert_message`:

1. **`type`**: `GROUP_MESSAGE` or `FRIEND_MESSAGE`
2. **`session_id`**: Set session isolation (core field)
3. **`message_str`**: Extract plain text content
4. **`message`**: Map platform message segments to a `MessageComponent` list
5. **`sender`**: Extract sender ID and nickname
6. **`raw_message`**: Preserve the original object

## Submit Event

```python
async def handle_raw_message(self, data):
    bot_msg = self.convert_message(data)
    event = AstrMessageEvent(bot_msg, self)
    self.commit_event(event)
```
