"""
Tool abstractions and protocols.

This module provides the ToolProtocol interface, ToolResult wrapper,
and MCPToolWrapper for adapting MCP tools to the framework's interface.
"""

from typing import Any, Dict, List, Optional, Protocol
from enum import Enum
import time

from pydantic import BaseModel, Field, ConfigDict

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

    @property
    def tool_definition(self) -> Dict[str, Any]:
        """Get the OpenAI-compatible function schema for LLM tool calling."""
        ...

    async def use(self, params: dict) -> Any:
        """Execute the tool with the given parameters.

        Args:
            params: Dictionary of parameters to pass to the tool

        Returns:
            The result of tool execution
        """
        ...


class ToolErrorType(str, Enum):
    """Types of errors that can occur during tool execution."""

    VALIDATION_ERROR = "validation_error"  # Input validation failed
    EXECUTION_ERROR = "execution_error"  # Tool function raised exception
    TIMEOUT_ERROR = "timeout_error"  # Tool execution timed out
    PERMISSION_ERROR = "permission_error"  # Tool execution not permitted
    NOT_FOUND_ERROR = "not_found_error"  # Tool not found
    CLIENT_ERROR = "client_error"  # MCP/external client error
    UNKNOWN_ERROR = "unknown_error"  # Unclassified error


class ToolResult(BaseModel):
    """Standardized tool result with explicit success/failure tracking.

    This Pydantic model provides a consistent interface for handling tool results
    regardless of the underlying tool type (custom, MCP, etc.).

    Attributes:
        success: Whether the tool execution succeeded
        value: The result value (None if failed)
        error: Error message if failed (None if succeeded)
        error_type: Classification of the error type
        tool_name: Name of the tool that was executed
        execution_time_ms: Time taken to execute in milliseconds
        metadata: Additional metadata about the execution

    Example:
        # Successful result
        result = ToolResult.ok(value="Search completed", tool_name="web_search")

        # Failed result
        result = ToolResult.fail(
            error="Connection timeout",
            error_type=ToolErrorType.TIMEOUT_ERROR,
            tool_name="web_search"
        )

        # Check result
        if result.success:
            print(result.value)
        else:
            print(f"Error: {result.error}")
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool = Field(default=True, description="Whether execution succeeded")
    value: Any = Field(default=None, description="The result value")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_type: Optional[ToolErrorType] = Field(
        default=None, description="Classification of error type"
    )
    tool_name: Optional[str] = Field(default=None, description="Name of the executed tool")
    execution_time_ms: Optional[float] = Field(
        default=None, description="Execution time in milliseconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional execution metadata"
    )

    # Backward compatibility: store raw_result for legacy code
    @property
    def raw_result(self) -> Any:
        """Backward compatible access to the result value."""
        return self.value

    def to_list(self) -> List[str]:
        """Convert the result to a list format.

        Returns:
            List of string representations of the result
        """
        if not self.success:
            return [f"Error: {self.error}"]
        if isinstance(self.value, list):
            return [str(item) for item in self.value]
        return [str(self.value)]

    def to_string(self) -> str:
        """Convert the result to a string format.

        Returns:
            String representation of the result
        """
        if not self.success:
            return f"Error: {self.error}"
        if isinstance(self.value, list):
            return (
                str(self.value[0])
                if len(self.value) == 1
                else str(self.value)
            )
        return str(self.value)

    @classmethod
    def ok(
        cls,
        value: Any,
        tool_name: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        """Create a successful result.

        Args:
            value: The result value
            tool_name: Name of the tool that was executed
            execution_time_ms: Execution time in milliseconds
            metadata: Additional metadata

        Returns:
            A successful ToolResult instance
        """
        return cls(
            success=True,
            value=value,
            tool_name=tool_name,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )

    @classmethod
    def fail(
        cls,
        error: str,
        error_type: ToolErrorType = ToolErrorType.UNKNOWN_ERROR,
        tool_name: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        """Create a failed result.

        Args:
            error: Error message describing what went wrong
            error_type: Classification of the error
            tool_name: Name of the tool that was executed
            execution_time_ms: Execution time in milliseconds
            metadata: Additional metadata (e.g., stack trace, context)

        Returns:
            A failed ToolResult instance
        """
        return cls(
            success=False,
            error=error,
            error_type=error_type,
            tool_name=tool_name,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )

    @classmethod
    def wrap(cls, result: Any, tool_name: Optional[str] = None) -> "ToolResult":
        """Wrap any result in a ToolResult, detecting success/failure.

        This method provides backward compatibility by detecting if the result
        is already a ToolResult, an error string, or a normal value.

        Args:
            result: Any result to wrap
            tool_name: Name of the tool

        Returns:
            A ToolResult instance
        """
        # Already a ToolResult
        if isinstance(result, ToolResult):
            return result

        # Legacy error detection: string starting with "Error"
        if isinstance(result, str) and (
            result.startswith("Error:") or
            result.startswith("Tool Error:") or
            result.startswith("Tool Execution Error:")
        ):
            return cls.fail(
                error=result,
                error_type=ToolErrorType.EXECUTION_ERROR,
                tool_name=tool_name,
            )

        # Normal successful result
        return cls.ok(value=result, tool_name=tool_name)

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        tool_name: Optional[str] = None,
        error_type: Optional[ToolErrorType] = None,
    ) -> "ToolResult":
        """Create a failed result from an exception.

        Args:
            exception: The exception that occurred
            tool_name: Name of the tool that was executed
            error_type: Classification of the error (auto-detected if not provided)

        Returns:
            A failed ToolResult instance
        """
        # Auto-detect error type if not provided
        if error_type is None:
            exc_type = type(exception).__name__
            if "Timeout" in exc_type:
                error_type = ToolErrorType.TIMEOUT_ERROR
            elif "Permission" in exc_type or "Access" in exc_type:
                error_type = ToolErrorType.PERMISSION_ERROR
            elif "Validation" in exc_type:
                error_type = ToolErrorType.VALIDATION_ERROR
            elif "NotFound" in exc_type or "KeyError" in exc_type:
                error_type = ToolErrorType.NOT_FOUND_ERROR
            else:
                error_type = ToolErrorType.EXECUTION_ERROR

        return cls.fail(
            error=f"{type(exception).__name__}: {str(exception)}",
            error_type=error_type,
            tool_name=tool_name,
            metadata={"exception_type": type(exception).__name__},
        )

    def __str__(self) -> str:
        """String representation of the result."""
        return self.to_string()

    def __repr__(self) -> str:
        """Debug representation of the result."""
        if self.success:
            return f"ToolResult.ok({self.value!r})"
        return f"ToolResult.fail({self.error!r})"

    def __bool__(self) -> bool:
        """Allow using ToolResult in boolean context (True if successful)."""
        return self.success


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
        start_time = time.time()

        if self.mcp_client is None:
            return ToolResult.fail(
                error="MCP client not configured",
                error_type=ToolErrorType.CLIENT_ERROR,
                tool_name=self.name,
            )

        try:
            result = await self.mcp_client.call_tool(
                tool_name=self.name,
                params=params,
            )
            # Convert MCP result content to strings
            content = [
                r.text if isinstance(r, TextContent) else str(r)
                for r in result.content
            ]
            execution_time_ms = (time.time() - start_time) * 1000

            return ToolResult.ok(
                value=content,
                tool_name=self.name,
                execution_time_ms=execution_time_ms,
                metadata={"source": "mcp"},
            )
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return ToolResult.from_exception(
                exception=e,
                tool_name=self.name,
                error_type=ToolErrorType.CLIENT_ERROR,
            )

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
