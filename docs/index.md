# Reactive Agents

A powerful, intuitive framework for building AI agents with multiple reasoning strategies.

## Features

- **Builder Pattern API** - Clean, fluent interface for agent creation
- **Multiple Reasoning Strategies** - Reactive, Plan-Execute-Reflect, Reflect-Decide-Act, and more
- **Easy Tool Creation** - Simple `@tool` decorator for custom tools
- **MCP Integration** - Built-in support for Model Context Protocol
- **Event System** - Rich lifecycle events for monitoring and debugging
- **Multi-Provider Support** - Ollama, OpenAI, Anthropic, Google, Groq

## Quick Start

```python
from reactive_agents import ReactiveAgentBuilder, tool, ReasoningStrategies

@tool()
async def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

async def main():
    agent = await (
        ReactiveAgentBuilder()
        .with_name("SearchAgent")
        .with_model("ollama:llama3")
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_custom_tools([search])
        .build()
    )

    result = await agent.run("Find information about Python")
    print(result.final_answer)

    await agent.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Installation

```bash
pip install reactive-agents
```

Or with Poetry:

```bash
poetry add reactive-agents
```

## Why Reactive Agents?

| Feature | Reactive Agents | LangChain | CrewAI |
|---------|-----------------|-----------|--------|
| Builder API | Excellent | Verbose | Medium |
| Tool Creation | Simple `@tool` | Boilerplate | Medium |
| Error Messages | Outstanding | Cryptic | Medium |
| Type Safety | Strong | Weak | Weak |
| Learning Curve | Medium | Steep | Medium |

## Next Steps

- [Installation Guide](getting-started/installation.md) - Detailed installation instructions
- [Quick Start Tutorial](getting-started/quickstart.md) - Build your first agent
- [Reasoning Strategies](user-guide/reasoning-strategies.md) - Choose the right strategy
- [API Reference](reference/) - Complete API documentation
