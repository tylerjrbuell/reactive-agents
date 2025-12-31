"""Final answer tool implementation.

This module provides the FinalAnswerTool which is automatically injected
into agents to allow them to provide final answers and conclude tasks.
"""

from typing import Any, Dict, Optional
from pydantic import Field

from reactive_agents.core.tools.base import Tool, ToolInput
from reactive_agents.core.tools.abstractions import ToolResult

# Import ContextProtocol at runtime so Pydantic can resolve the forward reference
from reactive_agents.core.context.context_protocol import ContextProtocol


class FinalAnswerInput(ToolInput):
    """Input schema for the final_answer tool."""
    answer: str = Field(
        ...,
        description="The final textual answer to the user's query as a complete response to the original task."
    )


class FinalAnswerTool(Tool):
    """Tool for providing the final answer to the user's query.

    This tool is automatically injected into agents by the ToolManager
    to provide a standardized way for agents to conclude their tasks.

    When invoked, it sets the final answer in the agent context's session,
    signaling that the task is complete.

    Attributes:
        context: Reference to the agent context for setting the final answer
    """

    # Override class-level defaults
    name: str = Field(default="final_answer")
    description: str = Field(
        default="Provides the final answer to the user's query and concludes the task."
    )
    category: str = Field(default="system")

    # Context reference (excluded from serialization)
    context: Optional["ContextProtocol"] = Field(default=None, exclude=True)

    # Pre-defined tool definition for this tool
    _tool_def: Dict[str, Any] = {
        "type": "function",
        "function": {
            "name": "final_answer",
            "description": "Provides the final answer to the user's query and concludes the task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "The final textual answer to the user's query as a complete response to the original task.",
                    }
                },
                "required": ["answer"],
            },
        },
    }

    def __init__(self, context: "ContextProtocol", **data):
        """Initialize the FinalAnswerTool.

        Args:
            context: The agent context to set the final answer in
            **data: Additional configuration
        """
        super().__init__(
            name="final_answer",
            description="Provides the final answer to the user's query and concludes the task.",
            function=None,  # We override use() directly
            input_schema=FinalAnswerInput,
            category="system",
            **data
        )
        self.context = context

    @property
    def tool_definition(self) -> Dict[str, Any]:
        """Get the OpenAI-compatible function schema.

        Returns:
            The tool definition schema for LLM function calling
        """
        return self._tool_def

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the final answer tool.

        Sets the final answer in the agent context's session.

        Args:
            params: Dictionary containing the 'answer' key

        Returns:
            ToolResult containing the answer or an error message
        """
        answer = params.get("answer")
        if answer is None:
            return ToolResult.fail(
                error="Missing required parameter 'answer'.",
                tool_name=self.name,
            )

        if self.context is None:
            return ToolResult.fail(
                error="Context not configured.",
                tool_name=self.name,
            )

        if self.context.session is None:
            return ToolResult.fail(
                error="Session not configured.",
                tool_name=self.name,
            )

        # Set the final answer in the context
        self.context.session.final_answer = answer

        # Log final answer setting
        if hasattr(self.context, "agent_logger") and self.context.agent_logger:
            self.context.agent_logger.info(
                f"FinalAnswerTool: Set session.final_answer = {answer[:50] if answer else 'None'}..."
            )

        return ToolResult.ok(value=answer, tool_name=self.name)

    def __hash__(self) -> int:
        """Make FinalAnswerTool hashable."""
        return hash("final_answer")

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if isinstance(other, FinalAnswerTool):
            return True
        if isinstance(other, Tool) and other.name == "final_answer":
            return True
        return False
