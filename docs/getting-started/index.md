# Getting Started

Welcome to Reactive Agents! This guide will help you get up and running quickly.

## What You'll Learn

1. [Installation](installation.md) - How to install the framework
2. [Quick Start](quickstart.md) - Build your first agent in 5 minutes
3. [Configuration](configuration.md) - Customize your agent's behavior

## Prerequisites

- Python 3.10 or higher
- A compatible LLM provider (Ollama, OpenAI, Anthropic, etc.)

## Quick Overview

Reactive Agents uses a **builder pattern** for creating agents:

```python
from reactive_agents import ReactiveAgentBuilder, ReasoningStrategies

agent = await (
    ReactiveAgentBuilder()
    .with_name("MyAgent")
    .with_model("ollama:llama3")
    .with_role("Assistant")
    .with_instructions("Help users with their tasks")
    .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
    .build()
)
```

Each method configures a specific aspect of your agent:

- `.with_name()` - Agent identifier for logging
- `.with_model()` - LLM provider and model
- `.with_role()` - Agent's persona
- `.with_instructions()` - Behavioral guidelines
- `.with_reasoning_strategy()` - How the agent thinks

Ready to dive in? Start with [Installation](installation.md).
