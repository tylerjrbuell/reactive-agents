"""SystemTool - Lightweight base class for framework system tools.

This module provides a minimal extension of Tool for framework-provided
system tools that require direct context access (like final_answer,
signal_stuck, etc.)
"""

from __future__ import annotations
from typing import Any
from pydantic import Field

from reactive_agents.core.tools.base import Tool

# Import ContextProtocol directly to avoid Pydantic forward reference issues
# This is safe because Tool base class already has the same pattern
try:
    from reactive_agents.core.context.context_protocol import ContextProtocol
except ImportError:
    # Fallback for edge cases during module loading
    ContextProtocol = Any  # type: ignore


class SystemTool(Tool):
    """Lightweight extension for framework system tools.

    SystemTool enforces:
    - Context reference is required (not optional)
    - Category is always "system" (immutable)

    Use this for framework-provided tools like:
    - final_answer
    - signal_stuck
    - request_strategy_switch
    - request_clarification

    User-provided tools should continue using Tool directly.

    Example:
        class FinalAnswerTool(SystemTool):
            name: str = Field(default="final_answer")
            description: str = Field(default="Provides final answer")

            async def use(self, params: Dict[str, Any]) -> ToolResult:
                self.context.session.final_answer = params.get("answer")
                return ToolResult.ok(value=answer, tool_name=self.name)
    """

    # Force category to always be "system"
    category: str = Field(default="system", frozen=True)

    # Context is required (not optional) and excluded from serialization
    context: "ContextProtocol" = Field(..., exclude=True)  # type: ignore

    def __init__(self, context: ContextProtocol, **data):  # type: ignore
        """Initialize a system tool with required context.

        Args:
            context: The agent context (required)
            **data: Additional tool configuration

        Raises:
            ValueError: If context is None
        """
        if context is None:
            raise ValueError(f"{self.__class__.__name__} requires a context")

        # Ensure category stays "system"
        if "category" in data and data["category"] != "system":
            raise ValueError(
                f"SystemTool category must be 'system', got '{data['category']}'"
            )

        super().__init__(context=context, category="system", **data)

    def __hash__(self) -> int:
        """Make SystemTool hashable based on name."""
        return hash(f"system:{self.name}")

    def __eq__(self, other: object) -> bool:
        """Check equality based on name and system category."""
        if isinstance(other, SystemTool):
            return self.name == other.name
        if isinstance(other, Tool):
            return self.name == other.name and other.category == "system"
        return False

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"SystemTool(name='{self.name}', category='system')"


# Rebuild the model to resolve forward references after imports are complete
SystemTool.model_rebuild()
