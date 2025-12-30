# Configuration

Configure your agent's behavior with the builder pattern.

## Core Configuration

### Model Provider

```python
# Ollama (local)
.with_model("ollama:llama3")
.with_model("ollama:mistral:7b")

# OpenAI
.with_model("openai:gpt-4")
.with_model("openai:gpt-3.5-turbo")

# Anthropic
.with_model("anthropic:claude-3-opus")
.with_model("anthropic:claude-3-sonnet")

# Google
.with_model("google:gemini-pro")

# Groq
.with_model("groq:llama3-70b")
```

### Agent Identity

```python
.with_name("MyAgent")           # Identifier for logging
.with_role("Research Assistant") # Agent's persona
.with_instructions("...")        # Behavioral guidelines
```

### Execution Limits

```python
.with_max_iterations(10)         # Maximum reasoning iterations
.with_min_completion_score(0.8)  # Task completion threshold
```

## Reasoning Strategies

```python
from reactive_agents import ReasoningStrategies

# Simple prompt-response
.with_reasoning_strategy(ReasoningStrategies.REACTIVE)

# Reflection-based approach
.with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)

# Planning upfront
.with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)

# Dynamic strategy selection
.with_reasoning_strategy(ReasoningStrategies.ADAPTIVE)
```

## Tools Configuration

### Custom Tools

```python
from reactive_agents import tool

@tool()
async def my_tool(param: str) -> str:
    """Tool description."""
    return "result"

.with_custom_tools([my_tool])
```

### MCP Tools

```python
# By server name
.with_mcp_tools(["brave-search", "filesystem"])

# Full configuration
.with_mcp_config({
    "servers": {
        "brave-search": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/brave-search-mcp"]
        }
    }
})
```

### Combined Tools

```python
.with_tools(
    custom_tools=[my_tool],
    mcp_tools=["brave-search"]
)
```

## Context Management

```python
# Message limits
.with_context_config(
    max_context_messages=20,
    max_context_tokens=4000
)

# Pruning behavior
.with_context_pruning_strategy("balanced")  # conservative, balanced, aggressive
.with_enable_context_pruning(True)
.with_enable_context_summarization(True)
```

## Tool Use Policy

```python
# Policy options: always, required_only, adaptive, never
.with_tool_use_policy("adaptive")

# Limit consecutive tool calls
.with_tool_use_max_consecutive_calls(3)
```

## Confirmation Callbacks

```python
from reactive_agents import ConfirmationConfig

# Custom confirmation callback
async def confirm_action(description: str, details: dict) -> bool:
    print(f"Confirm: {description}")
    return input("(y/n): ").lower() == "y"

.with_confirmation_callback(confirm_action)

# Configuration-based confirmation
config = ConfirmationConfig.create_default()
config["always_confirm"].append("dangerous_tool")

.with_confirmation_config(config)
```

## Memory Configuration

```python
# Enable/disable memory
.with_use_memory_enabled(True)

# Vector memory (ChromaDB)
.with_vector_memory_enabled(True)
.with_vector_memory_collection("my_agent_memory")
```

## Logging

```python
# Log levels: debug, info, warning, error, critical
.with_log_level("info")
```

## Full Example

```python
from reactive_agents import (
    ReactiveAgentBuilder,
    ReasoningStrategies,
    ConfirmationConfig,
    tool,
)

@tool()
async def search(query: str) -> str:
    """Search the web."""
    return f"Results for {query}"

async def confirm(desc: str, details: dict) -> bool:
    return True

agent = await (
    ReactiveAgentBuilder()
    # Identity
    .with_name("AdvancedAgent")
    .with_model("ollama:llama3")
    .with_role("Research Assistant")
    .with_instructions("Help users find information")

    # Strategy
    .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
    .with_max_iterations(15)
    .with_min_completion_score(0.9)

    # Tools
    .with_custom_tools([search])
    .with_tool_use_policy("adaptive")

    # Context
    .with_enable_context_pruning(True)
    .with_context_pruning_strategy("balanced")

    # Memory
    .with_use_memory_enabled(True)

    # Confirmation
    .with_confirmation_callback(confirm)

    # Logging
    .with_log_level("info")

    .build()
)
```
