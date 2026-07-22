# Key-Value Storage (KV Storage)

AstrBot provides plugins with a simple and easy-to-use KV storage interface (>= v4.9.2).

## Core Interface

Call directly from within the plugin class (inheriting from `Star`):

```python
await self.put_kv_data(key: str, value: Any)       # Store
data = await self.get_kv_data(key: str, default=None)  # Retrieve
await self.delete_kv_data(key: str)                 # Delete
```

## Features

- **Isolation**: Data is isolated by plugin ID; keys from different plugins do not conflict
- **Persistence**: Automatically persisted to `data/metadata/kv_storage.db`
- **Async**: All interfaces are async methods

## Lifecycle (≥ v4.26.2)

- **On plugin uninstall**, AstrBot **clears this plugin's KV data** (framework behavior).
- Do **not** assume scores, sessions, or caches in KV survive uninstall/reinstall.
- For data that must survive reinstall, store under plugin data dir via `StarTools.get_data_dir()` (files you control), document the path for users, or use external storage.

## Usage Example

```python
# Call only from Star plugin methods (self is Star)
await self.put_kv_data("user_scores", {"alice": 100, "bob": 85})
scores = await self.get_kv_data("user_scores", default={})
await self.delete_kv_data("user_scores")
```
