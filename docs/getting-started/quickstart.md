# Quick Start

Build your first AI agent in under 5 minutes.

## Basic Agent

```python
import asyncio
from reactive_agents import ReactiveAgentBuilder, ReasoningStrategies

async def main():
    # Build the agent
    agent = await (
        ReactiveAgentBuilder()
        .with_name("QuickStartAgent")
        .with_model("ollama:llama3")
        .with_role("Helpful Assistant")
        .with_instructions("Help users with their questions")
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_max_iterations(10)
        .build()
    )

    # Run a task
    result = await agent.run("What is the capital of France?")

    # Check the result
    print(f"Status: {result.status}")
    print(f"Answer: {result.final_answer}")

    # Clean up
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Agent with Custom Tools

```python
import asyncio
from reactive_agents import ReactiveAgentBuilder, tool, ReasoningStrategies

@tool()
async def calculate(expression: str) -> str:
    """Evaluate a mathematical expression.

    Args:
        expression: A mathematical expression like "2 + 2"
    """
    try:
        result = eval(expression)
        return f"The result is: {result}"
    except Exception as e:
        return f"Error: {e}"

@tool()
async def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: Name of the city
    """
    # In a real app, call a weather API
    return f"The weather in {city} is sunny, 72°F"

async def main():
    agent = await (
        ReactiveAgentBuilder()
        .with_name("ToolAgent")
        .with_model("ollama:llama3")
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_custom_tools([calculate, get_weather])
        .build()
    )

    result = await agent.run("What is 15 * 7 and what's the weather in Paris?")
    print(result.final_answer)

    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Using Events

Monitor agent execution in real-time:

```python
async def main():
    agent = await (
        ReactiveAgentBuilder()
        .with_name("EventAgent")
        .with_model("ollama:llama3")
        .build()
    )

    # Subscribe to events
    agent.on_session_started(lambda e: print(f"Started: {e['agent_name']}"))
    agent.on_tool_called(lambda e: print(f"Tool called: {e['tool_name']}"))
    agent.on_iteration_completed(lambda e: print(f"Iteration {e['iteration']} complete"))
    agent.on_session_ended(lambda e: print(f"Session ended"))

    result = await agent.run("Tell me a joke")
    print(result.final_answer)

    await agent.close()
```

## Using Context Manager

For automatic cleanup:

```python
async def main():
    agent = await (
        ReactiveAgentBuilder()
        .with_name("ContextAgent")
        .with_model("ollama:llama3")
        .build()
    )

    async with agent:
        result = await agent.run("What is 2 + 2?")
        print(result.final_answer)
    # Agent is automatically closed
```

## Next Steps

- [Building Agents](../user-guide/building-agents.md) - Deep dive into agent configuration
- [Custom Tools](../user-guide/custom-tools.md) - Create powerful custom tools
- [Reasoning Strategies](../user-guide/reasoning-strategies.md) - Choose the right strategy
