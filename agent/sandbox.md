# Sandbox (Computer Use Runtime)

Sandbox provides an isolated execution environment for code and shell commands.

## Access in Plugin

```python
booter = self.context.get_booter()        # sandbox booter
local = self.context.get_local_booter()   # local booter
```

## Shell Execution

```python
result = await booter.shell.exec("ls -la")
# result.stdout, result.stderr, result.exit_code
```

## Python Execution

```python
result = await booter.python.exec("print(1+1)")
```

## File Transfer

```python
# Upload host file to sandbox
await booter.upload_file("/host/path.txt", "/sandbox/path.txt")

# Download sandbox file to host
await booter.download_file("/sandbox/output.txt", "/host/output.txt")
```

## Availability Check

```python
if booter.available:
    # sandbox is ready
    pass
```

## UMO Binding

Each sandbox is bound to a UMO (Unified Message Origin). The same UMO always gets the same sandbox instance.

## Configuration Keys

| Key | Description |
|-----|-------------|
| `computer_use_runtime` | `sandbox` or `local` |
| `sandbox.booter` | Boot type |
| `shipyard_endpoint` | Shipyard endpoint (if applicable) |
