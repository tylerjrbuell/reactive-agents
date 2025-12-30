"""
Context Protocol

Defines the interface contract that both AgentContext and ComponentContext
must implement. This allows components to accept either type without losing
type safety.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from reactive_agents.core.config.agent_config import AgentConfig
    from reactive_agents.utils.logging import Logger
    from reactive_agents.providers.llm.base import BaseModelProvider
    from reactive_agents.core.events.event_bus import EventBus
    from reactive_agents.providers.external.client import MCPClient


@runtime_checkable
class ContextProtocol(Protocol):
    """
    Protocol defining the minimal interface that component initialization contexts must provide.

    Both AgentContext and ComponentContext implement this protocol, allowing
    components to accept either type while maintaining type safety.
    """

    # Configuration
    config: "AgentConfig"

    # Core components
    agent_logger: "Logger"
    tool_logger: "Logger"
    result_logger: "Logger"
    model_provider: "BaseModelProvider"
    event_bus: Optional["EventBus"]
    mcp_client: Optional["MCPClient"]

    # Configuration properties (delegated to config)
    @property
    def agent_name(self) -> str: ...

    @property
    def use_memory_enabled(self) -> bool: ...

    @property
    def collect_metrics_enabled(self) -> bool: ...

    @property
    def enable_state_observation(self) -> bool: ...

    def emit_event(self, event_type: Any, data: dict) -> None: ...
