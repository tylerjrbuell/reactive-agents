# Building Agents

Learn how to create and configure agents using the builder pattern.

## The Builder Pattern

Reactive Agents uses a fluent builder pattern for agent creation:

```python
from reactive_agents import ReactiveAgentBuilder

agent = await (
    ReactiveAgentBuilder()
    .with_name("MyAgent")
    .with_model("ollama:llama3")
    .with_role("Assistant")
    .build()
)
```

Each `.with_*()` method returns the builder, allowing method chaining.

## Builder Methods

### Identity Configuration

```python
.with_name("AgentName")     # Required: Unique identifier
.with_role("Role")          # Agent's persona/role
.with_instructions("...")   # Behavioral guidelines
```

### Model Configuration

```python
.with_model("provider:model")  # LLM provider and model

# Examples:
.with_model("ollama:llama3")
.with_model("openai:gpt-4")
.with_model("anthropic:claude-3-sonnet")
```

### Reasoning Configuration

```python
from reactive_agents import ReasoningStrategies

.with_reasoning_strategy(ReasoningStrategies.REACTIVE)
.with_max_iterations(10)
.with_min_completion_score(0.8)
```

### Tool Configuration

```python
.with_custom_tools([tool1, tool2])    # Python function tools
.with_mcp_tools(["server1", "server2"])  # MCP servers
.with_tools(                          # Combined
    custom_tools=[...],
    mcp_tools=[...]
)
```

## Agent Lifecycle

### 1. Build Phase

```python
agent = await builder.build()
```

During build:

- Configuration is validated
- MCP connections are established
- Tools are registered
- Context is initialized

### 2. Execution Phase

```python
result = await agent.run("Your task here")
```

During execution:

- Session is started
- Strategy executes iterations
- Tools are called as needed
- Result is generated

### 3. Cleanup Phase

```python
await agent.close()
```

Or use context manager:

```python
async with agent:
    result = await agent.run("Task")
```

## Accessing Agent State

### Session Information

```python
# During or after execution
session = agent.context.session

print(session.session_id)
print(session.iterations)
print(session.final_answer)
print(session.task_status)
```

### Execution Result

```python
result = await agent.run("Task")

print(result.status)            # TaskStatus enum
print(result.final_answer)      # The answer
print(result.was_successful())  # bool
print(result.strategy_used)     # Strategy name
print(result.task_metrics)      # Performance metrics
```

## Multiple Runs

An agent can execute multiple tasks:

```python
agent = await builder.build()

result1 = await agent.run("First task")
result2 = await agent.run("Second task")

await agent.close()
```

Each run starts a fresh session while preserving agent configuration.

## Error Handling

```python
try:
    result = await agent.run("Task")
    if result.was_successful():
        print(result.final_answer)
    else:
        print(f"Task failed: {result.status}")
        for error in result.session.errors:
            print(f"  - {error}")
finally:
    await agent.close()
```

## Best Practices

1. **Always close agents** - Use context managers or explicit `.close()`
2. **Set appropriate iterations** - Too few may not complete, too many waste resources
3. **Use specific instructions** - Clear guidelines improve agent behavior
4. **Choose the right strategy** - Match the strategy to your task type
