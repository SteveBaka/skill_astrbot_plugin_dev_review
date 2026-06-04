# Agent Runner (v4.7.0+)

Agent Runner is the runtime engine that executes tool_loop_agent calls.

## Plugin-Side Access

```python
# Get current session's agent runner
runner = self.context.get_using_agent_runner(umo)

# Get by ID
runner = self.context.get_agent_runner_by_id(runner_id)
```

## Chat Provider Interface

Agent Runner provides a `ChatProvider` interface for LLM calls. Feature availability depends on the underlying provider and AstrBot version.
