"""
ComponentContext: Minimal context interface for component initialization.

This module provides a lightweight context object that components can use
during initialization, before the full AgentContext is available.

This is an internal implementation detail of the factory module and should
not be used directly by external code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from reactive_agents.core.config.agent_config import AgentConfig
    from reactive_agents.utils.logging import Logger
    from reactive_agents.providers.llm.base import BaseModelProvider
    from reactive_agents.core.events.event_bus import EventBus
    from reactive_agents.providers.external.client import MCPClient
    from reactive_agents.core.tools.base import Tool
    from reactive_agents.core.types.session_types import AgentSession


@dataclass
class ComponentContext:
    """
    Minimal context interface for component initialization.

    This class provides the minimum interface that components need during
    their initialization phase. It wraps an AgentConfig and provides
    attribute access to configuration values as well as the essential
    runtime components (loggers, model_provider, event_bus).

    After the full AgentContext is created, components should use that
    instead of this minimal context.

    Note: This class uses __getattr__ to delegate most attribute access
    to the underlying config, making it compatible with existing component
    code that expects an AgentContext-like interface.
    """

    config: "AgentConfig"
    agent_logger: "Logger"
    tool_logger: "Logger"
    result_logger: "Logger"
    model_provider: "BaseModelProvider"
    event_bus: Optional["EventBus"] = None
    mcp_client: Optional["MCPClient"] = None
    custom_tools: List["Tool"] = field(default_factory=list)

    # These will be set by the factory as components are created
    memory_manager: Optional[Any] = None
    metrics_manager: Optional[Any] = None
    tool_manager: Optional[Any] = None
    workflow_manager: Optional[Any] = None
    context_manager: Optional[Any] = None
    task_classifier: Optional[Any] = None
    reflection_manager: Optional[Any] = None  # For compatibility

    # Session placeholder - will be properly initialized later
    _session: Optional["AgentSession"] = field(default=None, repr=False)

    @property
    def session(self) -> "AgentSession":
        """Get or create a default session for component initialization."""
        if self._session is None:
            from reactive_agents.core.types.session_types import AgentSession
            from reactive_agents.core.types.status_types import TaskStatus
            import time

            self._session = AgentSession(
                initial_task="",
                current_task="",
                start_time=time.time(),
                task_status=TaskStatus.INITIALIZED,
                reasoning_log=[],
                task_progress=[],
                task_nudges=[],
                successful_tools=set(),
                metrics={},
                completion_score=0.0,
                tool_usage_score=0.0,
                progress_score=0.0,
                answer_quality_score=0.0,
                llm_evaluation_score=0.0,
                instruction_adherence_score=0.0,
            )
        return self._session

    @property
    def tools(self) -> List["Tool"]:
        """Get custom tools for tool manager initialization."""
        return self.custom_tools

    @property
    def agent_name(self) -> str:
        """Get agent name from config."""
        return self.config.agent_name

    @property
    def use_memory_enabled(self) -> bool:
        """Get memory enabled flag from config."""
        return self.config.use_memory_enabled

    @property
    def collect_metrics_enabled(self) -> bool:
        """Get metrics collection flag from config."""
        return self.config.collect_metrics_enabled

    @property
    def enable_state_observation(self) -> bool:
        """Get state observation flag from config."""
        return self.config.enable_state_observation

    def __getattr__(self, name: str) -> Any:
        """
        Delegate attribute access to the underlying config.

        This allows components to access config values directly from
        this context object, maintaining compatibility with code that
        expects an AgentContext-like interface.
        """
        # First check if it's a config attribute
        if hasattr(self.config, name):
            return getattr(self.config, name)

        # Raise AttributeError for unknown attributes
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def emit_event(self, event_type: Any, data: Dict[str, Any]) -> None:
        """
        Emit an event to the event bus if available.

        This method provides compatibility with components that emit events
        during initialization.
        """
        if self.event_bus and self.config.enable_state_observation:
            event_data = {
                "agent_name": self.config.agent_name,
                **data,
            }
            self.event_bus.emit(event_type, event_data)

    async def emit_event_async(self, event_type: Any, data: Dict[str, Any]) -> None:
        """
        Emit an async event to the event bus if available.
        """
        if self.event_bus and self.config.enable_state_observation:
            event_data = {
                "agent_name": self.config.agent_name,
                **data,
            }
            await self.event_bus.emit_async(event_type, event_data)
