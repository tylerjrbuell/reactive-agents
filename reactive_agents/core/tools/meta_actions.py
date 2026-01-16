"""Meta-action system tools for self-correction and framework communication.

This module provides escape hatch tools that allow agents to signal when
they're stuck, request strategy changes, or ask for clarification. These
tools use the SystemTool base class for type safety and framework integration.
"""

import time
from typing import Any, Dict, List
from pydantic import Field

from reactive_agents.core.tools.system_tool import SystemTool
from reactive_agents.core.tools.base import ToolInput
from reactive_agents.core.tools.abstractions import ToolResult
from reactive_agents.core.types.event_types import AgentStateEvent


# ============================================================================
# Input Schemas
# ============================================================================


class SignalStuckInput(ToolInput):
    """Input schema for signal_stuck tool."""

    reason: str = Field(
        ...,
        description="Why the agent believes it's stuck (e.g., 'repeated same action', 'no progress', 'missing information')",
    )
    attempted_approaches: List[str] | None = Field(
        default=None, description="Approaches already tried that didn't work"
    )


class RequestStrategySwitchInput(ToolInput):
    """Input schema for request_strategy_switch tool."""

    reason: str = Field(..., description="Why a strategy switch is needed")
    preferred_strategy: str | None = Field(
        default=None,
        description="Preferred new strategy (e.g., 'plan_execute_reflect', 'reactive'). If not specified, framework decides.",
    )


class RequestClarificationInput(ToolInput):
    """Input schema for request_clarification tool."""

    question: str = Field(
        ..., description="What clarification or additional information is needed"
    )
    blocking: bool = Field(
        default=False,
        description="Whether this blocks progress (true) or is just helpful (false)",
    )


# ============================================================================
# System Tools
# ============================================================================


class SignalStuckTool(SystemTool):
    """System tool to signal being stuck and request framework intervention.

    When an agent invokes this tool:
    1. Sets a flag in the session indicating stuck state
    2. Records the reason and attempted approaches
    3. Emits an event for observers
    4. Triggers framework intervention (e.g., strategy switch)

    This is a "graceful stuck" signal vs. hitting max_iterations, allowing
    the framework to help before complete failure.

    Example:
        # Agent calls when it detects a problem
        await signal_stuck_tool.use({
            "reason": "I've tried the same approach 3 times with no progress",
            "attempted_approaches": ["direct API call", "cached lookup", "estimation"]
        })
        # Framework response: Switches strategy or adds strong nudge
    """

    name: str = Field(default="signal_stuck")
    description: str = Field(
        default=(
            "Signal that you're stuck and need framework intervention. "
            "Use when: repeated attempts fail, no progress is being made, "
            "or you lack necessary information to proceed."
        )
    )
    input_schema: type[ToolInput] | None = SignalStuckInput

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the signal_stuck tool.

        Args:
            params: Validated parameters containing 'reason' and optionally 'attempted_approaches'

        Returns:
            ToolResult indicating the framework was notified
        """
        reason = params.get("reason", "Unknown reason")
        attempted = params.get("attempted_approaches", [])

        # Update session state
        if self.context.session:
            self.context.session.agent_signaled_stuck = True
            self.context.session.stuck_reason = reason
            self.context.session.attempted_approaches = attempted

        # Log the signal
        if self.context.agent_logger:
            self.context.agent_logger.warning(f"🚨 Agent signaled stuck: {reason}")
            if attempted:
                self.context.agent_logger.info(f"   Attempted: {', '.join(attempted)}")

        # Emit event for observers
        if hasattr(self.context, "emit_event"):
            event_data = {"reason": reason, "attempted_approaches": attempted}
            if self.context.session:
                event_data["iteration"] = self.context.session.iterations
            self.context.emit_event(AgentStateEvent.STUCK_SIGNALED, event_data)

        return ToolResult.ok(
            value="Framework notified. Will attempt intervention.", tool_name=self.name
        )


class RequestStrategySwitchTool(SystemTool):
    """System tool to request a reasoning strategy change.

    When an agent invokes this tool:
    1. Records the switch request and reason
    2. Optionally specifies preferred strategy
    3. Emits an event for tracking
    4. Framework evaluates and may honor the request

    Note: The framework has final say - the agent makes a request, not a command.
    This provides balanced control where agents can advocate for change but
    framework maintains safety guardrails.

    Example:
        # Agent requests different approach
        await request_strategy_switch_tool.use({
            "reason": "This task requires careful multi-step planning",
            "preferred_strategy": "plan_execute_reflect"
        })
        # Framework evaluates and switches if reasonable
    """

    name: str = Field(default="request_strategy_switch")
    description: str = Field(
        default=(
            "Request a switch to a different reasoning strategy. "
            "Use when current approach isn't working well for the task."
        )
    )
    input_schema: type[ToolInput] | None = RequestStrategySwitchInput

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the request_strategy_switch tool.

        Args:
            params: Validated parameters containing 'reason' and optionally 'preferred_strategy'

        Returns:
            ToolResult indicating the request was recorded
        """
        reason = params.get("reason", "Strategy not suitable for task")
        preferred = params.get("preferred_strategy")

        # Update session state
        if self.context.session:
            self.context.session.strategy_switch_requested = True
            self.context.session.strategy_switch_reason = reason
            self.context.session.preferred_strategy = preferred

        # Log the request
        target = preferred or "framework-decided"
        if self.context.agent_logger:
            self.context.agent_logger.info(
                f"🔄 Agent requested strategy switch: {reason} (target: {target})"
            )

        # Emit event for observers
        if hasattr(self.context, "emit_event"):
            event_data = {
                "reason": reason,
                "preferred_strategy": preferred,
                "current_strategy": getattr(
                    self.context, "reasoning_strategy", "unknown"
                ),
            }
            if self.context.session:
                event_data["iteration"] = self.context.session.iterations
            self.context.emit_event(
                AgentStateEvent.STRATEGY_SWITCH_REQUESTED, event_data
            )

        return ToolResult.ok(
            value="Strategy switch requested. Framework will evaluate at next iteration.",
            tool_name=self.name,
        )


class RequestClarificationTool(SystemTool):
    """System tool to request clarification or additional information.

    When an agent invokes this tool:
    1. Records the clarification request
    2. Marks whether it's blocking progress
    3. Can pause execution if blocking
    4. Provides visibility into what agent needs

    This allows agents to explicitly communicate missing information rather
    than making assumptions or proceeding blindly.

    Example:
        # Agent identifies missing information
        await request_clarification_tool.use({
            "question": "What time period should the analysis cover?",
            "blocking": False
        })
        # Framework logs request, agent proceeds with best available information
    """

    name: str = Field(default="request_clarification")
    description: str = Field(
        default=(
            "Request clarification or additional information needed to proceed. "
            "Use when task requirements are ambiguous or missing key details."
        )
    )
    input_schema: type[ToolInput] | None = RequestClarificationInput

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the request_clarification tool.

        Args:
            params: Validated parameters containing 'question' and 'blocking' flag

        Returns:
            ToolResult indicating the request was recorded
        """
        question = params.get("question", "")
        blocking = params.get("blocking", False)

        # Add to session clarification requests
        if self.context.session:
            request_record = {
                "question": question,
                "blocking": blocking,
                "iteration": self.context.session.iterations,
                "timestamp": time.time(),
            }

            # Safely append to clarification_requests list
            if not hasattr(self.context.session, "clarification_requests"):
                setattr(self.context.session, "clarification_requests", [])

            clarification_requests = getattr(
                self.context.session, "clarification_requests", []
            )
            clarification_requests.append(request_record)

        # Log the request
        priority = "BLOCKING" if blocking else "non-blocking"
        if self.context.agent_logger:
            self.context.agent_logger.info(
                f"❓ Agent requested clarification ({priority}): {question}"
            )

        # Emit event for observers
        if hasattr(self.context, "emit_event"):
            event_data = {"question": question, "blocking": blocking}
            if self.context.session:
                event_data["iteration"] = self.context.session.iterations
            self.context.emit_event(AgentStateEvent.CLARIFICATION_REQUESTED, event_data)

        # If blocking, add nudge to context
        if (
            blocking
            and hasattr(self.context, "context_manager")
            and self.context.context_manager
        ):
            self.context.context_manager.add_nudge(
                f"Clarification needed: {question}. "
                f"Proceed with best available information or signal stuck."
            )

        return ToolResult.ok(
            value="Clarification request recorded. Proceeding with available information.",
            tool_name=self.name,
        )


# ============================================================================
# Export all tools
# ============================================================================

__all__ = [
    "SignalStuckTool",
    "SignalStuckInput",
    "RequestStrategySwitchTool",
    "RequestStrategySwitchInput",
    "RequestClarificationTool",
    "RequestClarificationInput",
]


# Rebuild models to resolve forward references
SignalStuckTool.model_rebuild()
RequestStrategySwitchTool.model_rebuild()
RequestClarificationTool.model_rebuild()
