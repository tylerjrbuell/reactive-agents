# MCP Integration

Use Model Context Protocol (MCP) tools with Reactive Agents.

## What is MCP?

MCP (Model Context Protocol) is a standard for connecting AI models to external tools and data sources. Reactive Agents has built-in support for MCP servers.

## Using MCP Tools

### By Server Name

```python
agent = await (
    ReactiveAgentBuilder()
    .with_name("MCPAgent")
    .with_model("ollama:llama3")
    .with_mcp_tools(["brave-search", "filesystem"])
    .build()
)
```

### With Full Configuration

```python
agent = await (
    ReactiveAgentBuilder()
    .with_mcp_config({
        "servers": {
            "brave-search": {
                "command": "npx",
                "args": ["-y", "@anthropic-ai/brave-search-mcp"],
                "env": {
                    "BRAVE_API_KEY": "your-api-key"
                }
            },
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@anthropic-ai/filesystem-mcp"],
                "env": {
                    "ALLOWED_PATHS": "/tmp,/home/user/data"
                }
            }
        }
    })
    .with_mcp_tools(["brave-search", "filesystem"])
    .build()
)
```

## MCP Configuration Options

### Server Definition

```python
{
    "servers": {
        "server-name": {
            "command": "...",      # Command to run
            "args": ["..."],       # Command arguments
            "env": {               # Environment variables
                "KEY": "value"
            },
            "cwd": "/path/to/dir"  # Working directory (optional)
        }
    }
}
```

### Configuration File

You can also use a configuration file:

```python
.with_mcp_config("/path/to/mcp_config.json")
```

**mcp_config.json:**
```json
{
  "servers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/brave-search-mcp"]
    }
  }
}
```

## Combining MCP and Custom Tools

```python
from reactive_agents import tool

@tool()
async def my_tool(param: str) -> str:
    """Custom tool."""
    return f"Result: {param}"

agent = await (
    ReactiveAgentBuilder()
    .with_tools(
        custom_tools=[my_tool],
        mcp_tools=["brave-search"]
    )
    .build()
)
```

## Filtering MCP Servers

Use only specific servers from a configuration:

```python
# Full config has many servers, but only use these two
.with_mcp_config(full_config)
.with_mcp_server_filter(["brave-search", "time"])
```

## Pre-initialized MCP Client

If you have an existing MCPClient:

```python
from reactive_agents.providers.external.client import MCPClient

mcp_client = MCPClient(config)
await mcp_client.connect()

agent = await (
    ReactiveAgentBuilder()
    .with_mcp_client(mcp_client)
    .build()
)
```

## Popular MCP Servers

### Brave Search

Web search functionality:

```python
{
    "brave-search": {
        "command": "npx",
        "args": ["-y", "@anthropic-ai/brave-search-mcp"],
        "env": {"BRAVE_API_KEY": "your-key"}
    }
}
```

### Filesystem

File system operations:

```python
{
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@anthropic-ai/filesystem-mcp"],
        "env": {"ALLOWED_PATHS": "/path/to/allowed"}
    }
}
```

### Time

Time and timezone operations:

```python
{
    "time": {
        "command": "npx",
        "args": ["-y", "@anthropic-ai/time-mcp"]
    }
}
```

### SQLite

Database operations:

```python
{
    "sqlite": {
        "command": "npx",
        "args": ["-y", "@anthropic-ai/sqlite-mcp"],
        "env": {"DATABASE_PATH": "/path/to/db.sqlite"}
    }
}
```

## Error Handling

MCP connection errors are handled gracefully:

```python
try:
    agent = await (
        ReactiveAgentBuilder()
        .with_mcp_tools(["nonexistent-server"])
        .build()
    )
except Exception as e:
    print(f"MCP connection failed: {e}")
```

The framework provides helpful error messages when MCP servers fail to connect.

## MCP Tool Discovery

Tools from MCP servers are automatically discovered:

```python
agent = await builder.build()

# Access discovered tools through the tool manager
tools = agent.context.tool_manager.get_available_tools()
for tool in tools:
    print(f"- {tool.name}: {tool.description}")
```

## Best Practices

1. **Validate server availability** - MCP servers must be installed/accessible
2. **Set environment variables** - Many servers need API keys
3. **Use filters** - Only include servers you need
4. **Handle errors** - MCP connections can fail
5. **Combine strategically** - Mix MCP and custom tools for flexibility
