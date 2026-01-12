from __future__ import annotations
import time
from typing import Optional, TYPE_CHECKING, cast

from reactive_agents.core.reasoning.steps.base import BaseReasoningStep
from reactive_agents.core.types.reasoning_types import (
    ContinueThinkingPayload,
    FinishTaskPayload,
    EvaluationPayload,
    StrategyAction,
)
from reactive_agents.core.types.session_types import BaseStrategyState
from reactive_agents.core.reasoning.strategies.base import StrategyResult
from reactive_agents.core.reasoning.strategies.states import (
    PlanExecuteReflectState,
    ReactiveState,
)

if TYPE_CHECKING:
    from reactive_agents.core.types.reasoning_types import ReasoningContext


class EvaluateTaskCompletionStep(BaseReasoningStep):
    """
    A reasoning step that evaluates the completion of the task.
    """

    async def execute(
        self,
        state: "BaseStrategyState",
        task: str,
        reasoning_context: "ReasoningContext",
    ) -> Optional["StrategyResult"]:

        if self.agent_logger:
            self.agent_logger.info("🔎 Evaluating task completion...")

        if not self.strategy:
            raise ValueError("Strategy not set on step")

        # Extract comprehensive execution context from state
        exec_summary = state.get_execution_summary()
        progress_summary = ""
        latest_output = ""
        execution_log = ""

        if isinstance(state, PlanExecuteReflectState):
            progress_summary = state.current_plan.get_summary()
        elif isinstance(state, ReactiveState):
            progress_summary = f"Total: {exec_summary.get('total_responses', 0)}, Success: {exec_summary.get('successful_responses', 0)}"
            latest_output = exec_summary.get("last_response", "")

        # Build execution log from session messages
        if self.context and self.context.session:
            messages = self.context.session.messages[-5:]  # Last 5 messages for context
            execution_log = "\n".join(
                [
                    f"{m.get('role', 'unknown')}: {str(m.get('content', ''))[:100]}"
                    for m in messages
                ]
            )

        # Use the evaluation component with all context
        evaluation_result = await self.strategy.evaluate(
            task,
            progress_summary=progress_summary,
            latest_output=latest_output,
            execution_log=execution_log,
        )

        if evaluation_result.is_complete:
            if self.agent_logger:
                self.agent_logger.info("Evaluation confirms task is complete.")

            completion = await self.strategy.complete_task(task, progress_summary)
            return StrategyResult.create(
                payload=FinishTaskPayload(
                    action=StrategyAction.FINISH_TASK,
                    final_answer=completion.final_answer or "Task completed.",
                    evaluation=EvaluationPayload(
                        action=StrategyAction.EVALUATE_COMPLETION,
                        is_complete=True,
                        reasoning=completion.reasoning,
                        confidence=completion.confidence,
                    ),
                ),
                should_continue=False,
            )

        if self.agent_logger:
            self.agent_logger.info("Task not yet complete. Continuing iteration.")

        # If not complete, continue the loop
        return StrategyResult.create(
            payload=ContinueThinkingPayload(
                action=StrategyAction.CONTINUE_THINKING,
                reasoning=evaluation_result.reasoning,
            ),
            should_continue=True,
        )
