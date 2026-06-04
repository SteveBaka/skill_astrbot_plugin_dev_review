# Sandbox Storage Mounting

Sandbox mounts host directories into the sandbox environment.

## Mount Mapping

| Host Path | Sandbox Path |
|-----------|-------------|
| `data/temp` | `/AstrBot/data/temp` |

## Impact on File Operations

- Files written to the mounted host path are accessible inside the sandbox
- Files written inside the sandbox at the mounted path are accessible on the host
- Temporary files should be written to `data/temp` for cross-environment access

## Cleanup

Mounted temporary files persist across sandbox restarts. Clean up explicitly when no longer needed.
