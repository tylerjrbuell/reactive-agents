# Custom Tools

Create powerful tools for your agents using the `@tool` decorator.

## Basic Tool Creation

```python
from reactive_agents import tool

@tool()
async def search(query: str) -> str:
    """Search the web for information.

    Args:
        query: The search query
    """
    # Implementation
    return f"Results for: {query}"
```

The decorator automatically:

- Extracts parameter types from type hints
- Extracts descriptions from docstrings
- Creates the tool schema for LLM function calling

## Tool Parameters

### Type Hints

Type hints are converted to JSON schema types:

```python
@tool()
async def example(
    text: str,      # -> "string"
    count: int,     # -> "integer"
    value: float,   # -> "number"
    flag: bool,     # -> "boolean"
    items: list,    # -> "array"
    data: dict,     # -> "object"
) -> str:
    """Example with all types."""
    pass
```

### Optional Parameters

Parameters with defaults are optional:

```python
@tool()
async def search(
    query: str,          # Required
    limit: int = 10,     # Optional (default: 10)
    sort: str = "date",  # Optional (default: "date")
) -> str:
    """Search with options."""
    pass
```

### Descriptions from Docstrings

Use Google-style docstrings for parameter descriptions:

```python
@tool()
async def calculate(
    expression: str,
    precision: int = 2,
) -> str:
    """Evaluate a mathematical expression.

    Args:
        expression: The math expression to evaluate (e.g., "2 + 2")
        precision: Number of decimal places in the result
    """
    result = round(eval(expression), precision)
    return str(result)
```

## Decorator Options

```python
@tool(
    description="Override the docstring description",
    category="math",              # Tool category
    requires_confirmation=True,   # Requires user confirmation
    cacheable=True,               # Results can be cached
    cache_ttl=300,                # Cache time-to-live (seconds)
)
async def my_tool(param: str) -> str:
    """This description is overridden."""
    pass
```

## Synchronous Tools

Both sync and async functions work:

```python
@tool()
def sync_tool(param: str) -> str:
    """A synchronous tool."""
    return "result"

@tool()
async def async_tool(param: str) -> str:
    """An asynchronous tool."""
    return await some_async_operation(param)
```

## Tool Categories

Organize tools by category:

```python
@tool(category="search")
async def web_search(query: str) -> str:
    """Search the web."""
    pass

@tool(category="math")
async def calculate(expr: str) -> str:
    """Calculate math."""
    pass

@tool(category="file")
async def read_file(path: str) -> str:
    """Read a file."""
    pass
```

## Confirmation Tools

For dangerous or irreversible operations:

```python
@tool(requires_confirmation=True)
async def delete_file(path: str) -> str:
    """Delete a file (requires confirmation)."""
    import os
    os.remove(path)
    return f"Deleted: {path}"
```

When used with a confirmation callback:

```python
async def confirm(description: str, details: dict) -> bool:
    print(f"Confirm: {description}")
    return input("(y/n): ").lower() == "y"

agent = await (
    ReactiveAgentBuilder()
    .with_custom_tools([delete_file])
    .with_confirmation_callback(confirm)
    .build()
)
```

## Cacheable Tools

For expensive operations that produce deterministic results:

```python
@tool(cacheable=True, cache_ttl=3600)  # Cache for 1 hour
async def expensive_api_call(query: str) -> str:
    """Make an expensive API call."""
    # This result will be cached
    return await call_expensive_api(query)
```

## Registering Tools

### With Builder

```python
agent = await (
    ReactiveAgentBuilder()
    .with_custom_tools([tool1, tool2, tool3])
    .build()
)
```

### Programmatic Creation

```python
from reactive_agents import create_tool_from_function

async def my_function(query: str) -> str:
    return f"Result: {query}"

tool = create_tool_from_function(
    my_function,
    description="Custom description",
    category="custom"
)
```

## Error Handling in Tools

Tools should handle errors gracefully:

```python
@tool()
async def safe_divide(a: float, b: float) -> str:
    """Divide two numbers safely.

    Args:
        a: The dividend
        b: The divisor
    """
    if b == 0:
        return "Error: Cannot divide by zero"
    return str(a / b)
```

## Tool Schema Access

Access the generated schema:

```python
@tool()
async def my_tool(param: str) -> str:
    """My tool."""
    pass

print(my_tool.tool_definition)
# {
#     "type": "function",
#     "function": {
#         "name": "my_tool",
#         "description": "My tool.",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "param": {"type": "string", "description": "param"}
#             },
#             "required": ["param"]
#         }
#     }
# }
```

## Best Practices

1. **Clear descriptions** - Write descriptive docstrings for better LLM understanding
2. **Type hints** - Always include type hints for parameters
3. **Error handling** - Return error messages instead of raising exceptions
4. **Specific names** - Use descriptive function names (e.g., `search_web` not `search`)
5. **Return strings** - Tools should return string results for the LLM
