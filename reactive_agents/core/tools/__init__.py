"""
Tool System

Core tool management and processing components.

This module provides:
- Tool: Pydantic-based tool class with validation and schema generation
- ToolInput: Base class for tool input validation schemas
- ToolOutput: Base class for tool output schemas
- ToolProtocol: Protocol interface for tool implementations
- ToolResult: Standardized tool result wrapper
- MCPToolWrapper: Adapter for MCP tools
- ToolManager: Orchestrates tool discovery, execution, and caching
- tool: Decorator for creating tools from functions
- create_tool_from_function: Factory for creating Tool instances

Example:
    from reactive_agents.core.tools import Tool, ToolInput, tool

    # Using the decorator
    @tool(description="Search the web")
    async def web_search(query: str) -> str:
        return f"Results for {query}"

    # Create Tool instance
    search_tool = Tool(function=web_search)

    # With explicit input validation
    class SearchInput(ToolInput):
        query: str
        limit: int = 10

    validated_tool = Tool(
        name="search",
        description="Search with validation",
        function=web_search,
        input_schema=SearchInput
    )
"""

from .base import Tool, ToolInput, ToolOutput
from .abstractions import MCPToolWrapper, ToolProtocol, ToolResult
from .tool_manager import ToolManager, ParallelToolResult
from .decorators import tool, create_tool_from_function
from .data_extractor import DataExtractor, SearchDataManager

__all__ = [
    # Core classes
    "Tool",
    "ToolInput",
    "ToolOutput",
    # Protocol and wrappers
    "MCPToolWrapper",
    "ToolProtocol",
    "ToolResult",
    # Manager
    "ToolManager",
    "ParallelToolResult",
    # Decorators and factories
    "tool",
    "create_tool_from_function",
    # Data extraction
    "DataExtractor",
    "SearchDataManager",
]
