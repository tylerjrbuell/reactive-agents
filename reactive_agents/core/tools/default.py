"""Final answer tool implementation.

This module provides the FinalAnswerTool which is automatically injected
into agents to allow them to provide final answers and conclude tasks.
"""

from typing import Any, Dict
from pydantic import Field

from reactive_agents.core.tools.system_tool import SystemTool
from reactive_agents.core.tools.base import ToolInput
from reactive_agents.core.tools.abstractions import ToolResult


class FinalAnswerInput(ToolInput):
    """Input schema for the final_answer tool."""

    answer: str = Field(
        ...,
        description="The final textual answer to the user's query as a complete response to the original task.",
    )


class FinalAnswerTool(SystemTool):
    """Tool for providing the final answer to the user's query.

    This tool is automatically injected into agents by the ToolManager
    to provide a standardized way for agents to conclude their tasks.

    When invoked, it sets the final answer in the agent context's session,
    signaling that the task is complete.

    Example:
        # Agent calls this when ready to provide final answer
        await final_answer_tool.use({"answer": "The result is 42"})
        # Sets context.session.final_answer = "The result is 42"
    """

    # Tool metadata
    name: str = Field(default="final_answer")
    description: str = Field(
        default="Provides the final answer to the user's query and concludes the task."
    )
    input_schema: type[ToolInput] | None = FinalAnswerInput

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

        # Set the final answer in the context
        if self.context.session:
            self.context.session.final_answer = answer

        # Log final answer setting
        if hasattr(self.context, "agent_logger") and self.context.agent_logger:
            self.context.agent_logger.info(
                f"✅ Final answer set: {answer[:50] if answer else 'None'}..."
            )

        return ToolResult.ok(value=answer, tool_name=self.name)
