from __future__ import annotations
import time
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from collections import deque

from pydantic import BaseModel, Field, ConfigDict

# Import ContextProtocol at runtime so Pydantic can resolve the forward reference
from reactive_agents.core.context.context_protocol import ContextProtocol

if TYPE_CHECKING:
    from reactive_agents.utils.logging import Logger


class ToolMetrics(BaseModel):
    """Metrics for a single tool."""
    calls: int = 0
    errors: int = 0
    total_time: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate tool success rate."""
        if self.calls == 0:
            return 0.0
        return (self.calls - self.errors) / self.calls

    @property
    def avg_time(self) -> float:
        """Calculate average execution time."""
        successful_calls = self.calls - self.errors
        if successful_calls == 0:
            return 0.0
        return self.total_time / successful_calls


class StrategyExecutionRecord(BaseModel):
    """Record of a single strategy execution for performance tracking."""

    strategy_name: str
    success: bool
    iterations: int
    completion_score: float = 0.0
    execution_time_ms: float = 0.0
    error_count: int = 0
    tool_calls: int = 0
    timestamp: float = Field(default_factory=time.time)

    @property
    def efficiency_score(self) -> float:
        """Calculate execution efficiency (higher = better)."""
        if self.iterations == 0:
            return 0.0
        base_efficiency = self.completion_score / max(1, self.iterations)
        error_penalty = self.error_count * 0.1
        return max(0.0, min(1.0, base_efficiency - error_penalty))


class StrategyPerformance(BaseModel):
    """Aggregated performance metrics for a strategy."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    strategy_name: str
    total_executions: int = 0
    successful_executions: int = 0
    total_iterations: int = 0
    total_execution_time_ms: float = 0.0
    total_errors: int = 0
    completion_scores: List[float] = Field(default_factory=list)
    efficiency_scores: List[float] = Field(default_factory=list)
    recent_window: deque = Field(default_factory=lambda: deque(maxlen=20), exclude=True)

    @property
    def success_rate(self) -> float:
        """Calculate strategy success rate."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    @property
    def avg_iterations(self) -> float:
        """Calculate average iterations per execution."""
        if self.total_executions == 0:
            return 0.0
        return self.total_iterations / self.total_executions

    @property
    def avg_completion_score(self) -> float:
        """Calculate average completion score."""
        if not self.completion_scores:
            return 0.0
        return sum(self.completion_scores) / len(self.completion_scores)

    @property
    def avg_efficiency(self) -> float:
        """Calculate average efficiency score."""
        if not self.efficiency_scores:
            return 0.0
        return sum(self.efficiency_scores) / len(self.efficiency_scores)

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_iterations == 0:
            return 0.0
        return self.total_errors / self.total_iterations

    @property
    def overall_score(self) -> float:
        """Calculate weighted overall performance score."""
        if self.total_executions == 0:
            return 0.0
        return (
            self.success_rate * 0.35 +
            self.avg_completion_score * 0.30 +
            self.avg_efficiency * 0.25 +
            (1.0 - self.error_rate) * 0.10
        )

    def record_execution(self, record: StrategyExecutionRecord) -> None:
        """Record an execution and update aggregated metrics."""
        self.total_executions += 1
        if record.success:
            self.successful_executions += 1
        self.total_iterations += record.iterations
        self.total_execution_time_ms += record.execution_time_ms
        self.total_errors += record.error_count
        self.completion_scores.append(record.completion_score)
        self.efficiency_scores.append(record.efficiency_score)
        self.recent_window.append(record)


class MetricsManager(BaseModel):
    """
    Unified metrics system for agent execution, tool performance, and strategy analysis.

    This class serves as the single source of truth for all metrics in the framework:
    - Execution-level metrics (tool usage, model calls, tokens, cache performance)
    - Strategy-level performance tracking for strategy selection decisions
    - Session scoring and completion tracking

    Attributes:
        context: Reference to the agent context
        start_time: When the current execution started
        end_time: When execution completed (None if still running)
        status: Current execution status
        tool_calls: Total number of tool calls made
        tool_errors: Number of tool calls that resulted in errors
        iterations: Number of reasoning iterations
        model_calls: Number of LLM calls made
        prompt_tokens: Total prompt tokens used
        completion_tokens: Total completion tokens used
        tools: Per-tool metrics dictionary
        cache_hits/cache_misses: Cache performance
        tool_latency/model_latency: Time spent in tools vs model calls
        strategy_performance: Per-strategy aggregated metrics
    """

    context: "ContextProtocol" = Field(exclude=True)

    # Core Execution Metrics
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "initialized"
    tool_calls: int = 0
    tool_errors: int = 0
    iterations: int = 0
    model_calls: int = 0

    # Token Usage Metrics
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Tool Performance Metrics
    tools: Dict[str, ToolMetrics] = Field(default_factory=dict)
    cache_hits: int = 0
    cache_misses: int = 0
    tool_latency: float = 0.0
    model_latency: float = 0.0

    # Strategy Performance Metrics (unified from StrategyPerformanceMonitor)
    strategy_performance: Dict[str, StrategyPerformance] = Field(default_factory=dict)
    current_strategy: Optional[str] = None
    current_execution_start: Optional[float] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def agent_logger(self) -> Logger:
        assert self.context.agent_logger is not None
        return self.context.agent_logger

    @property
    def total_time(self) -> float:
        """Calculates the total execution time."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time

    @property
    def total_tokens(self) -> int:
        """Calculates the total tokens used."""
        return self.prompt_tokens + self.completion_tokens

    @property
    def cache_ratio(self) -> float:
        """Calculates the cache hit ratio."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    def reset(self):
        """Resets metrics for a new run."""
        self.agent_logger.debug("Resetting metrics.")
        self.start_time = time.time()
        self.end_time = None
        if self.context.session is not None:
            self.status = str(self.context.session.task_status)
            self.iterations = self.context.session.iterations
        else:
            self.status = "initialized"
            self.iterations = 0
        self.tool_calls = 0
        self.tool_errors = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.model_calls = 0
        self.tools = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.tool_latency = 0.0
        self.model_latency = 0.0

    def update_tool_metrics(self, tool_history_entry: Dict[str, Any]):
        """Updates metrics based on a tool execution entry from ToolManager history."""
        if not self.context.collect_metrics_enabled:
            return

        self.tool_calls += 1
        tool_name = tool_history_entry.get("name", "unknown")
        is_error = tool_history_entry.get("error", False)
        execution_time = tool_history_entry.get("execution_time")

        if is_error:
            self.tool_errors += 1

        if tool_name not in self.tools:
            self.tools[tool_name] = ToolMetrics()

        self.tools[tool_name].calls += 1
        if is_error:
            self.tools[tool_name].errors += 1

        if execution_time is not None and not tool_history_entry.get("cached") and not is_error:
            self.tools[tool_name].total_time += execution_time
            self.tool_latency += execution_time

    def update_model_metrics(self, model_call_data: Dict[str, Any]):
        """Updates metrics after a model call."""
        if not self.context.collect_metrics_enabled:
            return

        self.model_calls += 1
        self.prompt_tokens += model_call_data.get("prompt_tokens", 0) or 0
        self.completion_tokens += model_call_data.get("completion_tokens", 0) or 0
        self.model_latency += model_call_data.get("time", 0) or 0

    def finalize_run_metrics(self):
        """Updates final metrics like end_time, total_time, and status."""
        if not self.context.collect_metrics_enabled:
            return

        self.end_time = time.time()
        if self.context.session is not None:
            self.status = str(self.context.session.task_status)
            self.iterations = self.context.session.iterations

        if self.context.tool_manager:
            self.cache_hits = self.context.tool_manager.cache_hits
            self.cache_misses = self.context.tool_manager.cache_misses

        self.agent_logger.debug("📊📈 Finalized run metrics.")

    def get_metrics(self) -> Dict[str, Any]:
        """Returns a comprehensive dictionary report of all metrics."""
        if not self.context.collect_metrics_enabled:
            return {}

        # Ensure dynamic properties are calculated for the report
        report = self.model_dump(exclude={"context"})
        report["total_time"] = self.total_time
        report["total_tokens"] = self.total_tokens
        report["cache_ratio"] = self.cache_ratio
        return report

    # =========================================================================
    # Strategy Performance Tracking Methods
    # =========================================================================

    def start_strategy_execution(self, strategy_name: str) -> None:
        """Begin tracking a strategy execution.

        Call this when starting to execute a strategy. Pair with
        complete_strategy_execution() when the strategy finishes.

        Args:
            strategy_name: Name of the strategy being executed
        """
        if not self.context.collect_metrics_enabled:
            return

        self.current_strategy = strategy_name
        self.current_execution_start = time.time()
        self.agent_logger.debug(f"Started tracking strategy: {strategy_name}")

    def complete_strategy_execution(
        self,
        success: bool,
        completion_score: float = 0.0,
        iterations: Optional[int] = None,
        error_count: Optional[int] = None,
    ) -> None:
        """Complete tracking of current strategy execution.

        Records the execution metrics and updates aggregated performance data.

        Args:
            success: Whether the strategy execution succeeded
            completion_score: Task completion score (0.0 to 1.0)
            iterations: Number of iterations (defaults to current session iterations)
            error_count: Number of errors (defaults to current tool_errors)
        """
        if not self.context.collect_metrics_enabled:
            return

        if self.current_strategy is None or self.current_execution_start is None:
            self.agent_logger.warning(
                "complete_strategy_execution called without start_strategy_execution"
            )
            return

        # Calculate execution time
        execution_time_ms = (time.time() - self.current_execution_start) * 1000

        # Use provided values or defaults from current metrics
        actual_iterations = iterations if iterations is not None else self.iterations
        actual_errors = error_count if error_count is not None else self.tool_errors

        # Create execution record
        record = StrategyExecutionRecord(
            strategy_name=self.current_strategy,
            success=success,
            iterations=actual_iterations,
            completion_score=completion_score,
            execution_time_ms=execution_time_ms,
            error_count=actual_errors,
            tool_calls=self.tool_calls,
        )

        # Get or create strategy performance tracker
        if self.current_strategy not in self.strategy_performance:
            self.strategy_performance[self.current_strategy] = StrategyPerformance(
                strategy_name=self.current_strategy
            )

        # Record the execution
        self.strategy_performance[self.current_strategy].record_execution(record)

        self.agent_logger.debug(
            f"Recorded strategy execution: {self.current_strategy} "
            f"(success={success}, score={completion_score:.2f}, "
            f"efficiency={record.efficiency_score:.2f})"
        )

        # Reset current tracking
        self.current_strategy = None
        self.current_execution_start = None

    def get_strategy_rankings(self) -> List[tuple[str, float]]:
        """Get strategies ranked by overall performance score.

        Returns:
            List of (strategy_name, overall_score) tuples, sorted by score descending
        """
        rankings = [
            (name, perf.overall_score)
            for name, perf in self.strategy_performance.items()
            if perf.total_executions > 0
        ]
        return sorted(rankings, key=lambda x: x[1], reverse=True)

    def get_best_strategy(self, min_executions: int = 3) -> Optional[str]:
        """Get the best performing strategy with sufficient execution history.

        Args:
            min_executions: Minimum number of executions required for consideration

        Returns:
            Name of best strategy, or None if no strategy has enough history
        """
        candidates = [
            (name, perf.overall_score)
            for name, perf in self.strategy_performance.items()
            if perf.total_executions >= min_executions
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[1])[0]

    def should_switch_strategy(
        self,
        current_strategy: str,
        performance_threshold: float = 0.3,
        min_executions: int = 3,
    ) -> Optional[str]:
        """Determine if switching to a better strategy is recommended.

        Args:
            current_strategy: Name of the currently active strategy
            performance_threshold: Minimum score difference to recommend switch
            min_executions: Minimum executions before recommending switch

        Returns:
            Name of recommended strategy to switch to, or None to stay
        """
        current_perf = self.strategy_performance.get(current_strategy)
        if current_perf is None or current_perf.total_executions < min_executions:
            return None  # Not enough data to recommend switch

        current_score = current_perf.overall_score
        best_strategy = self.get_best_strategy(min_executions)

        if best_strategy is None or best_strategy == current_strategy:
            return None

        best_score = self.strategy_performance[best_strategy].overall_score

        if best_score - current_score >= performance_threshold:
            self.agent_logger.info(
                f"Recommending strategy switch: {current_strategy} "
                f"(score={current_score:.2f}) -> {best_strategy} "
                f"(score={best_score:.2f})"
            )
            return best_strategy

        return None

    def get_strategy_summary(self, strategy_name: str) -> Dict[str, Any]:
        """Get a summary of performance metrics for a specific strategy.

        Args:
            strategy_name: Name of the strategy

        Returns:
            Dictionary with performance metrics, or empty dict if not found
        """
        perf = self.strategy_performance.get(strategy_name)
        if perf is None:
            return {}

        return {
            "strategy_name": strategy_name,
            "total_executions": perf.total_executions,
            "success_rate": perf.success_rate,
            "avg_iterations": perf.avg_iterations,
            "avg_completion_score": perf.avg_completion_score,
            "avg_efficiency": perf.avg_efficiency,
            "error_rate": perf.error_rate,
            "overall_score": perf.overall_score,
        }

