# Advanced Features

Advanced capabilities for production use cases.

## Tool Confirmation System

Control which tools require user confirmation before execution.

### Basic Configuration

```python
from reactive_agents import ConfirmationConfig

# Create default confirmation config
config = ConfirmationConfig.create_default()

# Customize as needed
config["always_confirm"].append("delete_file")
config["never_confirm"].append("read_file")

agent = await (
    ReactiveAgentBuilder()
    .with_confirmation_config(config)
    .build()
)
```

### Configuration Options

```python
{
    # Tools that always require confirmation
    "always_confirm": ["delete_file", "send_email"],

    # Tools that never require confirmation
    "never_confirm": ["final_answer", "read_file"],

    # Pattern matching for tool names/descriptions
    "patterns": {
        "write": "confirm",
        "delete": "confirm",
        "update": "confirm",
        "create": "confirm",
    },

    # Default action if no rules match: "confirm" or "proceed"
    "default_action": "proceed"
}
```

### Custom Confirmation Callback

```python
from reactive_agents import ConfirmationCallbackProtocol

async def my_confirmation(
    action_description: str,
    details: dict
) -> bool:
    """
    Args:
        action_description: Description of the action
        details: Contains "tool" (name) and "params" (arguments)

    Returns:
        True to proceed, False to cancel
    """
    tool_name = details.get("tool", "unknown")
    print(f"Tool: {tool_name}")
    print(f"Action: {action_description}")
    response = input("Proceed? (y/n): ").lower()
    return response.startswith("y")

agent = await (
    ReactiveAgentBuilder()
    .with_confirmation_callback(my_confirmation)
    .build()
)
```

### Confirmation with Feedback

Provide feedback to guide agent behavior:

```python
async def confirmation_with_feedback(
    description: str,
    details: dict
) -> tuple[bool, str]:
    """Return (proceed, feedback) to guide the agent."""
    print(f"Action: {description}")
    response = input("Proceed? (y/n/f for feedback): ").lower()

    if response.startswith("f"):
        feedback = input("Your feedback: ")
        proceed = input("Now proceed? (y/n): ").lower().startswith("y")
        return (proceed, feedback)

    return (response.startswith("y"), "")
```

## Context Management

Intelligent context management optimizes memory usage and preserves important information.

### Strategy-Aware Context

Context management adapts to the active reasoning strategy:

- **Reactive**: Minimal context, focus on recent messages
- **Plan-Execute-Reflect**: Preserves planning context and summaries
- **Reflect-Decide-Act**: Prioritizes reflection and system guidance

### Configuration

```python
agent = await (
    ReactiveAgentBuilder()
    # Context limits
    .with_context_config(
        max_context_messages=20,
        max_context_tokens=4000
    )

    # Pruning behavior
    .with_enable_context_pruning(True)
    .with_enable_context_summarization(True)
    .with_context_pruning_strategy("balanced")  # conservative, balanced, aggressive

    # Summarization frequency (iterations between summarizations)
    .with_context_summarization_frequency(3)

    .build()
)
```

### Pruning Strategies

| Strategy | Behavior |
|----------|----------|
| conservative | Preserves more context, slower pruning |
| balanced | Default, moderate pruning |
| aggressive | Aggressive pruning for limited contexts |

### Context Windows

The system automatically:

- Groups related messages into logical windows
- Tracks importance of each window
- Preserves high-importance windows during pruning
- Summarizes pruned content to maintain continuity

## Vector Memory

Semantic search and persistent memory using ChromaDB.

### Enable Vector Memory

```python
agent = await (
    ReactiveAgentBuilder()
    .with_name("ResearchAgent")
    .with_model("ollama:llama3")
    .with_vector_memory_enabled(True)
    .with_vector_memory_collection("my_research")
    .build()
)
```

### Memory Operations

```python
# Search for relevant memories
results = await agent.search_memory(
    "AI ethics frameworks",
    n_results=5,
    memory_types=["session", "reflection"]
)

# Get context memories for a task
context_memories = await agent.get_context_memories(
    "Research task about machine learning",
    max_items=10
)

# Get memory statistics
stats = agent.get_memory_stats()
print(f"Total memories: {stats.get('total_memories', 0)}")
```

### Memory Types

- **session**: Complete session records
- **reflection**: Agent reflections and insights
- **tool_result**: Tool execution results
- **context**: Contextual information

### Storage

Vector memories are stored in `storage/vector_memory/` by default:

- Each collection is persisted independently
- Memories persist across agent sessions
- Automatic cleanup of old memories

### Multi-Agent Memory Sharing

```python
# Multiple agents can share a collection
agent1 = await (
    ReactiveAgentBuilder()
    .with_vector_memory_collection("shared_research")
    .build()
)

agent2 = await (
    ReactiveAgentBuilder()
    .with_vector_memory_collection("shared_research")
    .build()
)

# Agent 1 does research
await agent1.run("Research machine learning algorithms")

# Agent 2 can access the same memories
memories = await agent2.search_memory("machine learning")
```

## Tool Use Policy

Control how and when tools are used:

```python
agent = await (
    ReactiveAgentBuilder()
    # Policy: always, required_only, adaptive, never
    .with_tool_use_policy("adaptive")

    # Limit consecutive tool calls
    .with_tool_use_max_consecutive_calls(3)

    .build()
)
```

### Policies

| Policy | Behavior |
|--------|----------|
| always | Always attempt to use tools |
| required_only | Only use tools when necessary |
| adaptive | Dynamically decide based on context |
| never | Disable tool use entirely |

## Execution Control

Control agent execution in real-time:

```python
agent = await builder.build()

# Start task
import asyncio
task = asyncio.create_task(agent.run("Long running task"))

# Pause execution
await agent.pause()

# Resume execution
await agent.resume()

# Stop gracefully
await agent.stop()

# Force terminate
await agent.terminate()
```

### Control Events

Monitor control state changes:

```python
agent.on_pause_requested(lambda e: print("Pause requested"))
agent.on_paused(lambda e: print("Execution paused"))
agent.on_resume_requested(lambda e: print("Resume requested"))
agent.on_resumed(lambda e: print("Execution resumed"))
agent.on_stop_requested(lambda e: print("Stop requested"))
agent.on_stopped(lambda e: print("Execution stopped"))
```

## Caching

Enable response caching for improved performance:

```python
agent = await (
    ReactiveAgentBuilder()
    .with_enable_caching(True)
    .build()
)
```

Tool-level caching:

```python
@tool(cacheable=True, cache_ttl=3600)  # Cache for 1 hour
async def expensive_api_call(query: str) -> str:
    """Results will be cached."""
    return await call_expensive_api(query)
```
