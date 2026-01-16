# Tool Usage Example

Create and use custom tools with your agents.

## Complete Code

```python
import asyncio
from reactive_agents import ReactiveAgentBuilder, tool, ReasoningStrategies

# Define custom tools
@tool()
async def calculate(expression: str) -> str:
    """Evaluate a mathematical expression.

    Args:
        expression: A mathematical expression like "2 + 2" or "15 * 7"
    """
    try:
        # Note: In production, use a safer evaluation method
        result = eval(expression)
        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Error evaluating expression: {e}"


@tool()
async def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The name of the city
    """
    # Simulated weather data
    weather_data = {
        "paris": "Sunny, 72°F (22°C)",
        "london": "Cloudy, 59°F (15°C)",
        "tokyo": "Rainy, 68°F (20°C)",
        "new york": "Clear, 75°F (24°C)",
    }

    city_lower = city.lower()
    if city_lower in weather_data:
        return f"The weather in {city} is: {weather_data[city_lower]}"
    return f"Weather data not available for {city}"


@tool()
async def search_database(query: str, limit: int = 5) -> str:
    """Search a database for records.

    Args:
        query: The search query
        limit: Maximum number of results to return
    """
    # Simulated database search
    results = [f"Result {i}: {query} match {i}" for i in range(1, min(limit, 5) + 1)]
    return f"Found {len(results)} results:\n" + "\n".join(results)


async def main():
    # Create agent with custom tools
    agent = await (
        ReactiveAgentBuilder()
        .with_name("ToolAgent")
        .with_model("ollama:llama3")
        .with_role("Assistant with Tools")
        .with_instructions(
            "You are a helpful assistant with access to calculation, "
            "weather, and search tools. Use them when appropriate."
        )
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_custom_tools([calculate, get_weather, search_database])
        .with_max_iterations(10)
        .build()
    )

    # Monitor tool calls
    agent.on_tool_called(lambda e: print(f"  [Tool] {e['tool_name']}"))

    async with agent:
        # Test the calculation tool
        print("\n--- Test 1: Calculation ---")
        result = await agent.run("What is 15 * 7 + 23?")
        print(f"Answer: {result.final_answer}")

        # Test the weather tool
        print("\n--- Test 2: Weather ---")
        result = await agent.run("What's the weather like in Paris?")
        print(f"Answer: {result.final_answer}")

        # Test multiple tools
        print("\n--- Test 3: Multiple Tools ---")
        result = await agent.run(
            "Calculate 100 / 4 and tell me the weather in Tokyo"
        )
        print(f"Answer: {result.final_answer}")


if __name__ == "__main__":
    asyncio.run(main())
```

## Creating Tools

### Basic Tool

```python
@tool()
async def my_tool(param: str) -> str:
    """Tool description here.

    Args:
        param: Description of the parameter
    """
    return f"Result: {param}"
```

### Tool with Multiple Parameters

```python
@tool()
async def advanced_tool(
    query: str,
    limit: int = 10,
    sort: str = "relevance"
) -> str:
    """Search with advanced options.

    Args:
        query: The search query
        limit: Maximum results (default: 10)
        sort: Sort order (default: relevance)
    """
    return f"Searching '{query}' with limit={limit}, sort={sort}"
```

### Synchronous Tool

```python
@tool()
def sync_tool(value: int) -> str:
    """A synchronous tool."""
    return str(value * 2)
```

### Tool with Decorator Options

```python
@tool(
    description="Custom description override",
    category="math",
    requires_confirmation=True,
    cacheable=True,
    cache_ttl=300
)
async def special_tool(x: int) -> str:
    """This docstring is overridden."""
    return str(x)
```

## Tool Best Practices

### 1. Clear Descriptions

The docstring becomes the tool description for the LLM:

```python
@tool()
async def web_search(query: str) -> str:
    """Search the web for current information about a topic.

    Use this tool when you need up-to-date information that may not
    be in your training data.

    Args:
        query: A specific search query (be as specific as possible)
    """
    pass
```

### 2. Error Handling

Return error messages instead of raising exceptions:

```python
@tool()
async def safe_tool(param: str) -> str:
    """A tool with error handling."""
    try:
        result = do_something(param)
        return f"Success: {result}"
    except ValueError as e:
        return f"Invalid input: {e}"
    except Exception as e:
        return f"Error: {e}"
```

### 3. Type Hints

Always include type hints:

```python
@tool()
async def typed_tool(
    name: str,
    count: int,
    value: float,
    enabled: bool,
    tags: list,
    options: dict
) -> str:
    """Tool with all common types."""
    pass
```

### 4. Specific Names

Use descriptive function names:

```python
# Good
@tool()
async def search_products(query: str) -> str: ...

@tool()
async def get_user_profile(user_id: str) -> str: ...

# Less clear
@tool()
async def search(q: str) -> str: ...

@tool()
async def get(id: str) -> str: ...
```

## Expected Output

```
--- Test 1: Calculation ---
  [Tool] calculate
Answer: 15 * 7 + 23 equals 128.

--- Test 2: Weather ---
  [Tool] get_weather
Answer: The weather in Paris is sunny at 72°F (22°C).

--- Test 3: Multiple Tools ---
  [Tool] calculate
  [Tool] get_weather
Answer: 100 / 4 = 25, and the weather in Tokyo is rainy at 68°F (20°C).
```
