# Message Chain Components

AstrBot uses MessageChain to describe message structure, an ordered list composed of multiple message components.

> For message model structure, see `messages/model.md`
> For event objects and result construction, see `messages/events.md`
> For how adapters convert messages, see `platform_adapters/message_conversion.md`

## Core Components and Compatibility

| Component Type | Description | Parameter Example | Platform Compatibility |
|----------------|-------------|-------------------|----------------------|
| `Plain` | Plain text | `text="Hello"` | All platforms |
| `At` | @mention user | `user_id="xxx"` | Most platforms |
| `Image` | Image | `fromFileSystem(path)`, `fromURL(url)` | All platforms |
| `Record` | Audio | `file="path/to/wav"` | Widely supported |
| `Video` | Video | `fromFileSystem(path)`, `fromURL(url)` | Widely supported |
| `File` | File | `file="path"`, `name="a.txt"` | Some platforms |
| `Face` | Emoji | `id="123"` | Mainly OneBot v11 |
| `Node/Nodes` | Combined forward | `uin`, `name`, `content` | OneBot v11 only |
| `Poke` | Poke | - | Mainly OneBot v11 |
| `Reply` | Reply to message | `message_id="xxx"` | Widely supported |
| `Forward` | Forward | `id="forward_id"` | Some platforms |
| `Json` | JSON card | `data={"key": "value"}` | Some platforms |

## Import

```python
import astrbot.api.message_components as Comp
```

## Message Construction Examples

```python
# Method 1: Manually build a list
chain = [
    Comp.At(user_id=event.get_sender_id()),
    Comp.Plain(" 来看这张图："),
    Comp.Image.fromURL("https://example.com/image.jpg")
]
yield event.chain_result(chain)

# Method 2: Use MessageChain streaming construction
from astrbot.api.event import MessageChain
message_chain = MessageChain().message("Hello!").file_image("path/to/image.jpg")
await self.context.send_message(event.unified_msg_origin, message_chain)
```

## Image Component Details

```python
Image.fromURL("https://example.com/img.jpg")
Image.fromFileSystem("/path/to/image.jpg")
Image.fromBase64("base64_data")
Image.fromBytes(bytes_data)

# Conversion methods
img.convert_to_file_path() -> str   # Convert to local path
img.convert_to_base64() -> str      # Convert to base64
img.register_to_file_service() -> str  # Register to file service
```

## Audio/Video Components

```python
Record.fromFileSystem("/path/to/audio.wav")
Record.fromURL("https://example.com/audio.wav")
Record.fromBase64("base64_data")

Video.fromFileSystem("/path/to/video.mp4")
Video.fromURL("https://example.com/video.mp4")
```

## File Component

```python
File(name="文件名", file="/path/to/file", url="https://...")
# Async fetch
path = await file.get_file(allow_return_url=True)
```
