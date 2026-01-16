"""
Context Protocol

Defines the interface contract that both AgentContext and ComponentContext
must implement. This allows components to accept either type without losing
type safety.
"""

from __future__ import annotations
from typing import (
    Protocol,
    runtime_checkable,
    Any,
    Optional,
    List,
    Union,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from reactive_agents.core.config.agent_config import AgentConfig
    from reactive_agents.utils.logging import Logger
    from reactive_agents.providers.llm.base import BaseModelProvider
    from reactive_agents.core.events.event_bus import EventBus
    from reactive_agents.providers.external.client import MCPClient
    from reactive_agents.core.tools.base import Tool
    from reactive_agents.core.types.session_types import AgentSession
    from reactive_agents.core.metrics.metrics_manager import MetricsManager
    from reactive_agents.core.tools.tool_manager import ToolManager
    from reactive_agents.core.memory.memory_manager import MemoryManager
    from reactive_agents.core.memory.vector_memory import VectorMemoryManager
    from reactive_agents.core.context.context_manager import ContextManager


@runtime_checkable
class ContextProtocol(Protocol):
    """
    Protocol defining the interface that component initialization contexts must provide.

    Both AgentContext and ComponentContext implement this protocol, allowing
    components to accept either type while maintaining type safety.

    This protocol includes both required and optional attributes. Required attributes
    are available during initial component creation, while optional attributes become
    available after full context initialization.

    Note: Loggers are Optional because AgentContext may not have them initialized
    until after components are injected. Components should check before using.
    """

    # =========================================================================
    # Required: Configuration
    # =========================================================================
    config: "AgentConfig"

    # =========================================================================
    # Core Loggers (Optional - may not be initialized until after injection)
    # =========================================================================
    agent_logger: Optional["Logger"]
    tool_logger: Optional["Logger"]
    result_logger: Optional["Logger"]

    # =========================================================================
    # Required: Core Components
    # =========================================================================
    model_provider: Optional["BaseModelProvider"]
    event_bus: Optional["EventBus"]
    mcp_client: Optional["MCPClient"]

    # =========================================================================
    # Optional: Manager Components (available after full initialization)
    # =========================================================================
    metrics_manager: Optional["MetricsManager"]
    tool_manager: Optional["ToolManager"]
    memory_manager: Optional[Union["MemoryManager", "VectorMemoryManager"]]
    context_manager: Optional["ContextManager"]

    # =========================================================================
    # Optional: Runtime State (available after full initialization)
    # =========================================================================
    session: Optional["AgentSession"]
    tools: Optional[List[Any]]

    # =========================================================================
    # Configuration Properties (delegated to config)
    # =========================================================================
    @property
    def agent_name(self) -> str: ...

    @property
    def use_memory_enabled(self) -> bool: ...

    @property
    def collect_metrics_enabled(self) -> bool: ...

    @property
    def enable_state_observation(self) -> bool: ...

    # =========================================================================
    # Methods
    # =========================================================================
    def emit_event(self, event_type: Any, data: dict) -> None: ...
