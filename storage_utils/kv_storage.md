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

## Usage Example

```python
# Store user scores
await self.put_kv_data("user_scores", {"alice": 100, "bob": 85})

# Retrieve
scores = await self.get_kv_data("user_scores", default={})

# Delete
await self.delete_kv_data("user_scores")
```
