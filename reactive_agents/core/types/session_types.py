from __future__ import annotations
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
import uuid
import time

from .status_types import TaskStatus
from .agent_types import TaskSuccessCriteria


class BaseStrategyState(BaseModel):
    """Base class for all strategy-specific state models."""

    def reset(self) -> None:
        """Reset the state of the strategy."""
        pass


# --- Unified Strategy & State Registration ---
STRATEGY_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_strategy(name: str, state_cls: type, **metadata):
    """Register a strategy and its state class in the global registry."""

    def decorator(strategy_cls):
        STRATEGY_REGISTRY[name] = {
            "strategy_cls": strategy_cls,
            "state_cls": state_cls,
            "metadata": metadata,
        }
        return strategy_cls

    return decorator


class AgentSession(BaseModel):
    """Session data for a single agent run."""

    # Core session data
    agent_name: str = Field(default="Agent")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    initial_task: str
    current_task: str
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    task_status: TaskStatus = TaskStatus.INITIALIZED
    error: Optional[str] = None

    # Message history and reasoning
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning_log: List[str] = Field(default_factory=list)
    thinking_log: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # Store thinking with call context
    task_progress: List[str] = Field(default_factory=list)
    task_nudges: List[str] = Field(default_factory=list)

    # Tool usage tracking
    successful_tools: Set[str] = Field(default_factory=set)
    min_required_tools: Optional[Set[str]] = None

    # Metrics and scoring
    metrics: Dict[str, Any] = Field(default_factory=dict)
    completion_score: float = 0.0
    tool_usage_score: float = 0.0
    progress_score: float = 0.0
    answer_quality_score: float = 0.0
    llm_evaluation_score: float = 0.0
    instruction_adherence_score: float = 0.0

    # Evaluation and improvement
    evaluation: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    final_answer: Optional[str] = None
    success_criteria: Optional[TaskSuccessCriteria] = None

    # Error tracking
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    # Iteration tracking
    iterations: int = 0

    # Agent self-correction signals (for escape hatch tools)
    agent_signaled_stuck: bool = False
    stuck_reason: Optional[str] = None
    attempted_approaches: List[str] = Field(default_factory=list)

    # Strategy switch requests
    strategy_switch_requested: bool = False
    strategy_switch_reason: Optional[str] = None
    preferred_strategy: Optional[str] = None

    # Clarification requests
    clarification_requests: List[Dict[str, Any]] = Field(default_factory=list)

    # Loop detection state
    loop_detected: bool = False
    loop_details: Optional[Dict[str, Any]] = None
    loop_detections: List[Dict[str, Any]] = Field(default_factory=list)  # Cumulative history

    # Scoring weights
    tool_usage_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    progress_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    answer_quality_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    llm_evaluation_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    completion_score_weight: float = Field(default=0.4, ge=0.0, le=1.0)

    # Add next step tracking
    current_next_step: Optional[str] = None
    next_step_source: Optional[str] = None  # "reflection", "planning", "manual"
    next_step_timestamp: Optional[float] = None

    # Add last result tracking
    last_result: Optional[str] = None
    last_result_timestamp: Optional[float] = None
    last_result_iteration: Optional[int] = None

    # Strategy-specific state - updated to support multiple strategies
    strategy_state: Dict[str, BaseStrategyState] = Field(default_factory=dict)
    active_strategy: Optional[str] = None

    @property
    def duration(self) -> float:
        """Calculates the total duration of the session in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time

    @property
    def overall_score(self) -> float:
        """Calculates the final weighted score for the session."""
        score = (
            self.completion_score * self.completion_score_weight
            + self.tool_usage_score * self.tool_usage_weight
            + self.progress_score * self.progress_weight
            + self.answer_quality_score * self.answer_quality_weight
            + self.llm_evaluation_score * self.llm_evaluation_weight
        )
        total_weight = (
            self.completion_score_weight
            + self.tool_usage_weight
            + self.progress_weight
            + self.answer_quality_weight
            + self.llm_evaluation_weight
        )
        return score / total_weight if total_weight > 0 else 0.0

    @property
    def has_failed(self) -> bool:
        """Checks if the task has failed."""
        return self.task_status == TaskStatus.ERROR or any(
            e.get("is_critical") for e in self.errors
        )

    def add_message(self, role: str, content: str) -> "AgentSession":
        """Adds a message to the session and returns self for chaining."""
        message = {"role": role, "content": content}
        if message in self.messages:
            return self
        self.messages.append(message)
        return self

    def add_error(
        self, source: str, details: Dict[str, Any], is_critical: bool = False
    ) -> "AgentSession":
        """Adds a structured error to the session and returns self for chaining."""
        error_entry = {
            "source": source,
            "details": details,
            "is_critical": is_critical,
            "timestamp": time.time(),
        }
        self.errors.append(error_entry)
        if is_critical:
            self.task_status = TaskStatus.ERROR
        return self

    def get_prompt_context(self, last_n_messages: int = 10) -> List[Dict[str, Any]]:
        """Retrieves the most recent messages for use in an LLM prompt."""
        return self.messages[-last_n_messages:]

    def to_summary_dict(self) -> Dict[str, Any]:
        """Generates a dictionary summary of the session."""
        return {
            "session_id": self.session_id,
            "task": self.initial_task,
            "status": self.task_status.value,
            "duration_seconds": self.duration,
            "overall_score": self.overall_score,
            "total_errors": len(self.errors),
            "critical_errors": len([e for e in self.errors if e.get("is_critical")]),
            "iterations": self.iterations,
            "final_answer": self.final_answer,
        }

    def initialize_strategy_state(self, strategy_name: str) -> None:
        """
        Initialize state tracking for a specific strategy if not already present.
        Uses the STRATEGY_REGISTRY for dynamic state instantiation.

        Note: Strategies must be registered via @register_strategy decorator before use.
        State classes are now defined within their respective strategy files.
        """
        if strategy_name not in self.strategy_state:
            entry = STRATEGY_REGISTRY.get(strategy_name)
            if entry and "state_cls" in entry:
                self.strategy_state[strategy_name] = entry["state_cls"]()
            else:
                raise ValueError(
                    f"Unknown strategy: {strategy_name}. "
                    f"Ensure the strategy module is imported and registered via @register_strategy."
                )
        self.active_strategy = strategy_name

    def get_strategy_state(
        self, strategy_name: Optional[str] = None
    ) -> Optional[BaseStrategyState]:
        """Get the state for a specific strategy, or the active one if not specified."""
        name = strategy_name or self.active_strategy
        if name is None:
            return None
        return self.strategy_state.get(name)
