# Sandbox (Computer Use Runtime)

Sandbox provides an isolated execution environment for code and shell commands.

## Detecting the Runtime (v4.29.0+ #9472)

`GET /api/v1/stats/version` now returns a `runtime` snapshot alongside the version, so a
plugin can adapt **before** calling a tool instead of failing at execution time:

```json
{"runtime": {
  "os": "darwin",            // platform.system().lower()
  "arch": "arm64",           // platform.machine(), unmodified
  "sandbox": {
    "backend": "seatbelt",   // bubblewrap | seatbelt | null
    "status": "detected",    // detected | missing | unavailable | unsupported
    "error": "..."           // only when status == unavailable
  }
}}
```

`status` semantics: `detected` = executable found and a minimal workspace sandbox launched;
`missing` = executable not found; `unavailable` = found but startup failed; `unsupported` =
this platform has no Local process sandbox backend (`backend: null`).

**Values are captured once at application startup** — after installing sandbox
dependencies the operator must restart AstrBot to refresh them. Do not cache across
restarts, and do not treat this as a live probe (it does not verify DNS or every
permitted operation).

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
