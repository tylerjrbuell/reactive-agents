"""
Tool abstractions and protocols.

This module provides the ToolProtocol interface, ToolResult wrapper,
and MCPToolWrapper for adapting MCP tools to the framework's interface.
"""

from typing import Any, Awaitable, Dict, List, Optional, Protocol, TYPE_CHECKING
from pydantic import Field

from mcp import Tool as MCPTool
from mcp.types import TextContent
from reactive_agents.core.tools.base import Tool
from reactive_agents.providers.external.client import MCPClient


class ToolProtocol(Protocol):
    """Protocol defining the interface that all tools must implement.

    This protocol ensures compatibility between different tool implementations
    (custom tools, MCP tools, etc.) and the ToolManager.

    Attributes:
        name: Unique identifier for the tool
        tool_definition: OpenAI-compatible function schema for LLM tool calling
    """

    name: str
    tool_definition: Dict[str, Any]

    async def use(self, params: dict) -> Any:
        """Execute the tool with the given parameters.

        Args:
            params: Dictionary of parameters to pass to the tool

        Returns:
            The result of tool execution
        """
        ...


class ToolResult:
    """Standardized tool result wrapper.

    Provides consistent interface for handling tool results regardless
    of the underlying result type.

    Attributes:
        raw_result: The original unmodified result from the tool
    """

    def __init__(self, result: Any):
        """Initialize with a raw result.

        Args:
            result: The raw result from tool execution
        """
        self.raw_result = result

    def to_list(self) -> List[str]:
        """Convert the result to a list format.

        Returns:
            List of string representations of the result
        """
        if isinstance(self.raw_result, list):
            return [str(item) for item in self.raw_result]
        return [str(self.raw_result)]

    def to_string(self) -> str:
        """Convert the result to a string format.

        Returns:
            String representation of the result
        """
        if isinstance(self.raw_result, list):
            return (
                str(self.raw_result[0])
                if len(self.raw_result) == 1
                else str(self.raw_result)
            )
        return str(self.raw_result)

    @classmethod
    def wrap(cls, result: Any) -> "ToolResult":
        """Wrap any result in a ToolResult.

        Args:
            result: Any result to wrap

        Returns:
            A ToolResult instance containing the result
        """
        return cls(result)

    def __str__(self) -> str:
        """String representation of the result."""
        return self.to_string()

    def __repr__(self) -> str:
        """Debug representation of the result."""
        return f"ToolResult({self.raw_result!r})"


class MCPToolWrapper(Tool):
    """Wrapper to adapt MCP tools to match our Tool/ToolProtocol interface.

    This class bridges the MCP tool system with our internal tool framework,
    allowing MCP tools to be used seamlessly alongside custom tools.

    Note: This class inherits from the Pydantic-based Tool class but overrides
    the constructor and methods to handle MCP-specific behavior.
    """

    # Additional attributes for MCP
    mcp_tool: Optional[MCPTool] = Field(default=None, exclude=True)
    mcp_client: Optional[MCPClient] = Field(default=None, exclude=True)

    def __init__(self, mcp_tool: MCPTool, client: MCPClient, **data):
        """Initialize the MCP tool wrapper.

        Args:
            mcp_tool: The MCP tool definition
            client: The MCP client for executing the tool
            **data: Additional configuration
        """
        # Build tool_definition from MCP tool
        tool_def = {
            "type": "function",
            "function": {
                "name": mcp_tool.name,
                "description": mcp_tool.description or f"Execute {mcp_tool.name}",
                "parameters": mcp_tool.inputSchema,
            },
        }

        # Initialize the base Tool with extracted info
        super().__init__(
            name=mcp_tool.name,
            description=mcp_tool.description or "",
            function=None,  # MCP tools don't use a local function
            **data
        )

        # Store MCP-specific references
        self.mcp_tool = mcp_tool
        self.mcp_client = client

        # Cache the tool definition
        self._mcp_tool_definition = tool_def

    @property
    def tool_definition(self) -> Dict[str, Any]:
        """Get the OpenAI-compatible function schema.

        Returns:
            The tool definition schema for LLM function calling
        """
        return self._mcp_tool_definition

    async def use(self, params: dict) -> ToolResult:
        """Execute the MCP tool through its client.

        Args:
            params: Parameters to pass to the MCP tool

        Returns:
            ToolResult containing the execution result or error
        """
        if self.mcp_client is None:
            return ToolResult("Error: MCP client not configured")

        try:
            result = await self.mcp_client.call_tool(
                tool_name=self.name,
                params=params,
            )
            # Convert MCP result content to strings
            return ToolResult(
                [r.text if type(r) is TextContent else r for r in result.content]
            )
        except Exception as e:
            return ToolResult(f"Tool Error: {e}")

    def __hash__(self) -> int:
        """Make MCPToolWrapper hashable."""
        return hash(f"mcp:{self.name}")

    def __eq__(self, other: object) -> bool:
        """Check equality based on name."""
        if isinstance(other, MCPToolWrapper):
            return self.name == other.name
        if isinstance(other, Tool):
            return self.name == other.name
        return False
