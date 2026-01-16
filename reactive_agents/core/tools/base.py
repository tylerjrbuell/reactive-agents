"""
Pydantic-based Tool class with validation and schema generation.

This module provides the core Tool class and related base classes for
defining tools with input/output validation and auto-generated JSON schemas
for LLM function calling.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, Optional, Type, Union
from pydantic import BaseModel, Field, ConfigDict
import asyncio
import inspect


class ToolInput(BaseModel):
    """Base class for tool input schemas.

    Subclass this to define strict input validation for tools.
    The extra="forbid" config means unknown fields will be rejected.

    Example:
        class MyToolInput(ToolInput):
            query: str = Field(..., description="Search query")
            limit: int = Field(default=10, description="Max results")
    """
    model_config = ConfigDict(extra="forbid")  # Strict: reject unknown fields


class ToolOutput(BaseModel):
    """Base class for tool output schemas.

    Provides a standardized output format with success status and optional error.

    Example:
        class SearchOutput(ToolOutput):
            results: List[str] = Field(default_factory=list)
    """
    success: bool = True
    result: Any = None
    error: Optional[str] = None


class Tool(BaseModel):
    """Pydantic-based tool with validation and schema generation.

    Provides:
    - Input validation via Pydantic schemas
    - Auto-generated JSON schemas for LLM function calling
    - Consistent error handling
    - Backward compatibility with existing @tool decorator
    - Support for both sync and async functions

    Attributes:
        name: Unique tool identifier
        description: What the tool does (used in LLM prompts)
        function: The callable to execute (excluded from serialization)
        input_schema: Optional Pydantic model for input validation
        output_schema: Optional Pydantic model for output wrapping
        category: Tool category for organization
        requires_confirmation: Whether to prompt user before execution
        cacheable: Whether results can be cached
        cache_ttl: Cache time-to-live in seconds

    Example:
        # From a decorated function
        @tool(description="Search the web")
        async def web_search(query: str) -> str:
            return f"Results for {query}"

        tool_instance = Tool(function=web_search)

        # With explicit schema
        class SearchInput(ToolInput):
            query: str

        tool_instance = Tool(
            name="web_search",
            description="Search the web",
            function=web_search,
            input_schema=SearchInput
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="", description="Unique tool identifier")
    description: str = Field(default="", description="What the tool does")
    function: Optional[Callable] = Field(default=None, exclude=True)
    input_schema: Optional[Type[ToolInput]] = Field(default=None, exclude=True)
    output_schema: Optional[Type[ToolOutput]] = Field(default=None, exclude=True)

    # Metadata
    category: str = Field(default="general")
    requires_confirmation: bool = Field(default=False)
    cacheable: bool = Field(default=False)
    cache_ttl: int = Field(default=300)

    # Internal storage for tool_definition from decorated functions
    _tool_definition_cache: Optional[Dict[str, Any]] = None

    def __init__(self, function: Optional[Callable] = None, **data):
        """Initialize a Tool instance.

        Can be initialized either with just a function (backward compatible)
        or with explicit parameters.

        Args:
            function: The function to wrap as a tool. If provided as positional arg,
                     enables backward compatibility with old Tool(function) pattern.
            **data: Additional tool configuration (name, description, etc.)
        """
        # Handle backward-compatible initialization: Tool(function)
        if function is not None and "function" not in data:
            data["function"] = function

        # Extract metadata from function if not provided
        func = data.get("function")
        if func is not None:
            # Get name from function if not provided
            if not data.get("name"):
                data["name"] = getattr(func, "__name__", "unnamed_tool")

            # Get description from function docstring or decorator if not provided
            if not data.get("description"):
                # First try to get from tool_definition (set by @tool decorator)
                if hasattr(func, "tool_definition"):
                    func_def = func.tool_definition
                    if isinstance(func_def, dict) and "function" in func_def:
                        data["description"] = func_def["function"].get("description", "")

                # Fallback to docstring
                if not data.get("description"):
                    data["description"] = getattr(func, "__doc__", "") or ""

        super().__init__(**data)

    @property
    def tool_definition(self) -> Dict[str, Any]:
        """Generate OpenAI-compatible function schema for LLM tool calling.

        Returns a schema in the format expected by OpenAI's function calling API:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "What the tool does",
                "parameters": { ... JSON Schema ... }
            }
        }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description or f"Execute {self.name}",
                "parameters": self._get_parameters_schema()
            }
        }

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Extract JSON schema from input_schema or function signature.

        Priority:
        1. Explicit input_schema if provided
        2. Parameters from @tool decorator's tool_definition
        3. Empty schema as fallback
        """
        # Use explicit input_schema if provided
        if self.input_schema:
            schema = self.input_schema.model_json_schema()
            # Remove title and $defs that Pydantic adds (not needed for LLM)
            schema.pop("title", None)
            schema.pop("$defs", None)
            return schema

        # Fallback: Check if function has tool_definition attribute (from @tool decorator)
        if self.function and hasattr(self.function, "tool_definition"):
            func_def = self.function.tool_definition
            if isinstance(func_def, dict) and "function" in func_def:
                return func_def["function"].get("parameters", {"type": "object", "properties": {}})

        # Ultimate fallback: empty schema
        return {"type": "object", "properties": {}}

    async def use(self, params: Dict[str, Any]) -> Any:
        """Execute tool with input validation.

        Args:
            params: Parameters to pass to the tool function

        Returns:
            Tool execution result, or ToolOutput with error on failure
        """
        if self.function is None:
            return ToolOutput(success=False, error="Tool function not defined")

        # Validate input if schema exists
        if self.input_schema:
            try:
                validated = self.input_schema.model_validate(params)
                params = validated.model_dump()
            except Exception as e:
                return ToolOutput(success=False, error=f"Input validation failed: {e}")

        # Execute the function
        try:
            if asyncio.iscoroutinefunction(self.function):
                result = await self.function(**params)
            else:
                # Support sync functions too
                result = self.function(**params)

            # Wrap in ToolOutput if output_schema specified and result isn't already that type
            if self.output_schema and not isinstance(result, self.output_schema):
                return self.output_schema(result=result)

            return result

        except Exception as e:
            error_msg = f"Tool Execution Error: {e}"
            if self.output_schema:
                return self.output_schema(success=False, error=error_msg)
            return error_msg

    @classmethod
    def from_function(
        cls,
        function: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        input_schema: Optional[Type[ToolInput]] = None,
        output_schema: Optional[Type[ToolOutput]] = None,
        **kwargs
    ) -> "Tool":
        """Create a Tool from a function.

        Factory method that extracts name and description from function metadata
        if not provided explicitly.

        Args:
            function: The callable to wrap
            name: Override the tool name (defaults to function.__name__)
            description: Override the description (defaults to docstring)
            input_schema: Optional Pydantic model for input validation
            output_schema: Optional Pydantic model for output wrapping
            **kwargs: Additional tool configuration

        Returns:
            A configured Tool instance

        Example:
            async def my_tool(query: str) -> str:
                '''Search for something.'''
                return f"Results for {query}"

            tool = Tool.from_function(my_tool)
            # name="my_tool", description="Search for something."
        """
        # Extract description from decorator or docstring if not provided
        final_description = description
        if not final_description:
            if hasattr(function, "tool_definition"):
                func_def = function.tool_definition
                if isinstance(func_def, dict) and "function" in func_def:
                    final_description = func_def["function"].get("description", "")
            if not final_description:
                final_description = getattr(function, "__doc__", "") or ""

        return cls(
            name=name or getattr(function, "__name__", "unnamed_tool"),
            description=final_description,
            function=function,
            input_schema=input_schema,
            output_schema=output_schema,
            **kwargs
        )

    def __hash__(self) -> int:
        """Make Tool hashable for use in sets."""
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        """Check equality based on name."""
        if isinstance(other, Tool):
            return self.name == other.name
        return False
