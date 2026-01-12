"""
Strategy State Classes

This module contains all strategy-specific state classes.
Separated into its own module to avoid circular import issues with steps.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional

from pydantic import Field

from reactive_agents.core.types.session_types import (
    BaseStrategyState,
    register_strategy,
)
from reactive_agents.core.types.reasoning_component_types import Plan, ReflectionResult


class ReactiveState(BaseStrategyState):
    """State tracking specific to Reactive strategy."""

    # Execution state
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)
    error_count: int = 0
    max_errors: int = 3
    last_response: str = ""
    tool_responses: List[str] = Field(default_factory=list)

    # Metrics
    tool_success_rate: float = 0.0
    response_quality_score: float = 0.0

    def reset(self) -> None:
        """Reset the state of the strategy."""
        self.execution_history.clear()
        self.error_count = 0
        self.max_errors = 3
        self.last_response = ""
        self.tool_responses.clear()
        self.tool_success_rate = 0.0
        self.response_quality_score = 0.0

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a structured summary of execution progress."""
        successful_responses = [
            r for r in self.execution_history if r.get("success", False)
        ]
        failed_responses = [
            r for r in self.execution_history if not r.get("success", False)
        ]

        return {
            "total_responses": len(self.execution_history),
            "successful_responses": len(successful_responses),
            "failed_responses": len(failed_responses),
            "error_count": self.error_count,
            "tool_success_rate": self.tool_success_rate,
            "response_quality_score": self.response_quality_score,
            "last_response": self.last_response,
            "tool_responses": self.tool_responses,
            "execution_history": self.execution_history,
        }

    def record_response_result(self, response_result: Dict[str, Any]) -> None:
        """Record a response result and update metrics."""
        self.execution_history.append(response_result)
        self.last_response = response_result.get("content", "")

        # Update success rates
        total_responses = len(self.execution_history)
        successful_responses = len(
            [r for r in self.execution_history if r.get("success", False)]
        )
        self.tool_success_rate = (
            successful_responses / total_responses if total_responses > 0 else 0.0
        )

        # Track tool responses
        if "tool_calls" in response_result:
            for call in response_result["tool_calls"]:
                if isinstance(call, dict) and "result" in call:
                    self.tool_responses.append(str(call["result"]))


class PlanExecuteReflectState(BaseStrategyState):
    """State tracking specific to Plan-Execute-Reflect strategy."""

    # Plan state
    current_plan: Plan = Field(default_factory=Plan)
    current_step: int = 0
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)
    error_count: int = 0
    completed_actions: List[str] = Field(default_factory=list)
    max_errors: int = 3
    max_retries_per_step: int = 3
    last_step_output: str = ""
    tool_responses: List[str] = Field(default_factory=list)

    # Reflection state
    reflection_count: int = 0
    last_reflection_result: Optional[ReflectionResult] = None
    reflection_history: List[ReflectionResult] = Field(default_factory=list)

    # Strategy metrics
    plan_success_rate: float = 0.0
    step_success_rate: float = 0.0
    recovery_success_rate: float = 0.0

    def reset(self) -> None:
        """Reset the state of the strategy."""
        self.current_plan = Plan()
        self.current_step = 0
        self.execution_history.clear()
        self.error_count = 0
        self.completed_actions.clear()
        self.reflection_count = 0
        self.reflection_history.clear()

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a structured summary of execution progress."""
        successful_steps = [
            s for s in self.execution_history if s.get("success", False)
        ]
        failed_steps = [
            s for s in self.execution_history if not s.get("success", False)
        ]

        return {
            "total_steps": len(self.execution_history),
            "successful_steps": len(successful_steps),
            "failed_steps": len(failed_steps),
            "error_count": self.error_count,
            "reflection_count": self.reflection_count,
            "current_step": self.current_step,
            "plan_success_rate": self.plan_success_rate,
            "step_success_rate": self.step_success_rate,
            "recovery_success_rate": self.recovery_success_rate,
        }

    def record_step_result(self, step_result: Dict[str, Any]) -> None:
        """Record a step execution result and update metrics."""
        self.execution_history.append(step_result)
        self.last_step_output = step_result.get("result", "")

        # Update success rates
        total_steps = len(self.execution_history)
        successful_steps = len(
            [s for s in self.execution_history if s.get("success", False)]
        )
        self.step_success_rate = (
            successful_steps / total_steps if total_steps > 0 else 0.0
        )

        # Track tool responses
        if "tool_calls" in step_result:
            for call in step_result["tool_calls"]:
                if isinstance(call, dict) and "result" in call:
                    self.tool_responses.append(str(call["result"]))

    def record_reflection_result(self, reflection_result: ReflectionResult) -> None:
        """Record a reflection result and update metrics."""
        self.reflection_count += 1
        self.last_reflection_result = reflection_result
        self.reflection_history.append(reflection_result)


class ReflectDecideActState(BaseStrategyState):
    """State tracking specific to Reflect-Decide-Act strategy."""

    cycle_count: int = Field(default=0, description="Number of RDA cycles completed")
    reflection_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of reflection results"
    )
    decision_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of decisions made"
    )
    action_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of actions taken"
    )
    current_action: Dict[str, Any] = Field(
        default_factory=dict, description="Current action being executed"
    )
    error_count: int = Field(default=0, description="Number of errors encountered")
    max_errors: int = Field(
        default=3, description="Maximum allowed errors before strategy switch"
    )
    last_goal_evaluation: Optional[Dict[str, Any]] = Field(
        default=None, description="Last goal evaluation result"
    )

    def reset(self) -> None:
        """Reset all fields to their declared defaults."""
        self.cycle_count = 0
        self.reflection_history.clear()
        self.decision_history.clear()
        self.action_history.clear()
        self.current_action = {}
        self.error_count = 0
        self.max_errors = 3
        self.last_goal_evaluation = None

    def record_reflection_result(self, result: Dict[str, Any]) -> None:
        self.reflection_history.append(result)

    def record_decision_result(self, result: Dict[str, Any]) -> None:
        self.decision_history.append(result)

    def record_action_result(self, result: Dict[str, Any]) -> None:
        self.action_history.append(result)

    def get_execution_summary(self) -> Dict[str, Any]:
        return {
            "cycle_count": self.cycle_count,
            "reflection_count": len(self.reflection_history),
            "decision_count": len(self.decision_history),
            "action_count": len(self.action_history),
            "error_count": self.error_count,
        }
