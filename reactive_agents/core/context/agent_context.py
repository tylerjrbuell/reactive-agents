"""
AgentContext: Runtime state container for reactive agents.

This module provides a slim runtime state container that holds:
- An AgentConfig reference (immutable configuration)
- Pre-built component references (injected via factory)
- Session state (mutable runtime data)
- Delegation properties for backward compatibility

By separating configuration (AgentConfig) from runtime state (AgentContext),
we achieve cleaner architecture and better separation of concerns.
"""

from __future__ import annotations

from typing import (
    List,
    Dict,
    Any,
    Literal,
    Optional,
    Union,
    Tuple,
)

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reactive_agents.core.reasoning.engine import ReasoningEngine
    from reactive_agents.app.agents.reactive_agent import ReactiveAgent
    from reactive_agents.app.agents.base import Agent
    from reactive_agents.core.factory.component_set import ComponentSet
    from reactive_agents.core.context.context_protocol import ContextProtocol

from reactive_agents.config.mcp_config import MCPConfig
from reactive_agents.utils.logging import Logger
from reactive_agents.providers.llm.base import BaseModelProvider
from reactive_agents.providers.external.client import MCPClient
from reactive_agents.core.types.status_types import TaskStatus

# --- Import Manager Classes ---
from reactive_agents.core.metrics.metrics_manager import MetricsManager
from reactive_agents.core.memory.memory_manager import MemoryManager
from reactive_agents.core.memory.vector_memory import VectorMemoryManager

from reactive_agents.core.workflows.workflow_manager import WorkflowManager
from reactive_agents.core.tools.tool_manager import ToolManager

# --- Import AgentSession from its new location ---
from reactive_agents.core.types.session_types import AgentSession

# --- Import EventBus ---
from reactive_agents.core.events.event_bus import EventBus
from reactive_agents.core.types.event_types import AgentStateEvent

# Add imports for new components
from reactive_agents.core.reasoning.task_classifier import TaskClassifier
from reactive_agents.core.context.context_manager import ContextManager

# Import AgentConfig
from reactive_agents.core.config.agent_config import AgentConfig

# Import confirmation types
from reactive_agents.core.types.confirmation_types import ConfirmationCallbackProtocol


class AgentContext(BaseModel):
    """
    Runtime state container for reactive agents.

    This class holds runtime state and component references, NOT configuration.
    Configuration is stored in the immutable AgentConfig and accessed via
    delegation properties for backward compatibility.

    Attributes:
        config: Immutable configuration reference
        session: Mutable session state for the current run

        Component references (injected via factory or initialized):
        - model_provider, tool_manager, memory_manager, etc.

        Runtime state fields:
        - tools, mcp_client, mcp_config, etc.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # =========================================================================
    # Configuration (immutable reference)
    # =========================================================================
    config: AgentConfig

    # =========================================================================
    # Session State (mutable runtime)
    # =========================================================================
    session: AgentSession = Field(
        default_factory=lambda: AgentSession(
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
    )

    # =========================================================================
    # Component References (injected, not created here)
    # =========================================================================
    model_provider: Optional[BaseModelProvider] = None
    tool_manager: Optional[ToolManager] = None
    memory_manager: Optional[Union[MemoryManager, VectorMemoryManager]] = None
    metrics_manager: Optional[MetricsManager] = None
    workflow_manager: Optional[WorkflowManager] = None
    context_manager: Optional[ContextManager] = None
    event_bus: Optional[EventBus] = None
    task_classifier: Optional[TaskClassifier] = None

    # Loggers
    agent_logger: Optional[Logger] = None
    tool_logger: Optional[Logger] = None
    result_logger: Optional[Logger] = None

    # =========================================================================
    # Runtime State Fields (mutable, not in config)
    # =========================================================================
    # Workflow context (shared between agents in a workflow)
    workflow_context_shared: Optional[Dict[str, Any]] = None
    workflow_dependencies: List[str] = Field(default_factory=list)

    # MCP (Model Context Protocol) runtime state
    mcp_client: Optional[MCPClient] = None
    mcp_config: Optional[MCPConfig] = None

    # Tools list (custom tools added at runtime)
    tools: List[Any] = Field(default_factory=list)

    # Confirmation callback for tool execution
    confirmation_callback: Optional[ConfirmationCallbackProtocol] = None
    confirmation_config: Optional[Dict[str, Any]] = None

    # Observability (optional)
    observability: Optional[Any] = None

    # =========================================================================
    # Private Attributes
    # =========================================================================
    _agent: Optional["ReactiveAgent"] = PrivateAttr(default=None)
    _reasoning_engine: Optional[Any] = PrivateAttr(default=None)

    def __init__(self, **data):
        """Initialize AgentContext with config and optional components."""
        super().__init__(**data)

        # Set agent name on session
        self.session.agent_name = self.config.agent_name

        # Initialize current task from initial task if not set
        if not self.session.current_task and self.session.initial_task:
            self.session.current_task = self.session.initial_task

    def inject_components(self, components: "ComponentSet") -> None:
        """
        Inject initialized components from the ComponentFactory.

        This method is called after the context is created to inject
        pre-built components. This separates component creation from
        context initialization, enabling better testing and modularity.

        Args:
            components: A ComponentSet containing all initialized components
        """
        self.agent_logger = components.agent_logger
        self.tool_logger = components.tool_logger
        self.result_logger = components.result_logger
        self.model_provider = components.model_provider
        self.event_bus = components.event_bus
        self.tool_manager = components.tool_manager
        self.memory_manager = components.memory_manager
        self.metrics_manager = components.metrics_manager
        self.workflow_manager = components.workflow_manager
        self.context_manager = components.context_manager
        self.task_classifier = components.task_classifier

        # CRITICAL FIX: Update component context references to point to the real AgentContext
        # Components were initialized with ComponentContext during factory creation,
        # but need to use the actual AgentContext during execution.
        #
        # Type system note: We use cast() here because components were initialized with
        # ComponentContext (which has optional fields like session=None), but at this point
        # AgentContext guarantees all fields are properly initialized. The type checker
        # cannot express this guarantee due to Protocol invariance with mutable attributes,
        # but the runtime behavior is guaranteed to be correct.
        from typing import cast

        context: "ContextProtocol" = cast("ContextProtocol", self)

        if self.tool_manager:
            self.tool_manager.context = context
        if self.memory_manager:
            self.memory_manager.context = context
        if self.metrics_manager:
            self.metrics_manager.context = context
        if self.workflow_manager:
            self.workflow_manager.context = context

    def _initialize_loggers(self) -> None:
        """
        Initialize loggers if they haven't been injected.

        This method provides backward compatibility for code that creates
        AgentContext without using ComponentFactory. It creates basic loggers
        using the config values.

        Note: When using the builder pattern with ComponentFactory, loggers
        are injected via inject_components() and this method is not needed.
        """
        if self.agent_logger is None:
            self.agent_logger = Logger(
                name=self.config.agent_name,
                type="agent",
                level=self.config.log_level,
            )

        if self.tool_logger is None:
            self.tool_logger = Logger(
                name=f"{self.config.agent_name} Tool",
                type="tool",
                level=self.config.log_level,
            )

        if self.result_logger is None:
            self.result_logger = Logger(
                name=f"{self.config.agent_name} Result",
                type="agent_response",
                level=self.config.log_level,
            )

    # =========================================================================
    # Delegation Properties for Backward Compatibility
    # These allow existing code using context.agent_name to still work
    # =========================================================================

    @property
    def agent_name(self) -> str:
        """Delegate to config.agent_name."""
        return self.config.agent_name

    @property
    def provider_model_name(self) -> str:
        """Delegate to config.provider_model_name."""
        return self.config.provider_model_name

    @property
    def instructions(self) -> str:
        """Delegate to config.instructions."""
        return self.config.instructions

    @property
    def role(self) -> str:
        """Delegate to config.role."""
        return self.config.role

    @property
    def role_instructions(self) -> Dict[str, Any]:
        """Delegate to config.role_instructions."""
        return self.config.role_instructions

    @property
    def tool_use_enabled(self) -> bool:
        """Delegate to config.tool_use_enabled."""
        return self.config.tool_use_enabled

    @property
    def reflect_enabled(self) -> bool:
        """Delegate to config.reflect_enabled."""
        return self.config.reflect_enabled

    @property
    def use_memory_enabled(self) -> bool:
        """Delegate to config.use_memory_enabled."""
        return self.config.use_memory_enabled

    @property
    def collect_metrics_enabled(self) -> bool:
        """Delegate to config.collect_metrics_enabled."""
        return self.config.collect_metrics_enabled

    @property
    def vector_memory_enabled(self) -> bool:
        """Delegate to config.vector_memory_enabled."""
        return self.config.vector_memory_enabled

    @property
    def enable_state_observation(self) -> bool:
        """Delegate to config.enable_state_observation."""
        return self.config.enable_state_observation

    @property
    def enable_reactive_execution(self) -> bool:
        """Delegate to config.enable_reactive_execution."""
        return self.config.enable_reactive_execution

    @property
    def enable_dynamic_strategy_switching(self) -> bool:
        """Delegate to config.enable_dynamic_strategy_switching."""
        return self.config.enable_dynamic_strategy_switching

    @property
    def enable_context_pruning(self) -> bool:
        """Delegate to config.enable_context_pruning."""
        return self.config.enable_context_pruning

    @property
    def enable_context_summarization(self) -> bool:
        """Delegate to config.enable_context_summarization."""
        return self.config.enable_context_summarization

    @property
    def enable_caching(self) -> bool:
        """Delegate to config.enable_caching."""
        return self.config.enable_caching

    @property
    def max_iterations(self) -> Optional[int]:
        """Delegate to config.max_iterations."""
        return self.config.max_iterations

    @property
    def max_task_retries(self) -> int:
        """Delegate to config.max_task_retries."""
        return self.config.max_task_retries

    @property
    def log_level(self) -> Literal["debug", "info", "warning", "error", "critical"]:
        """Delegate to config.log_level."""
        return self.config.log_level

    @property
    def min_completion_score(self) -> float:
        """Delegate to config.min_completion_score."""
        return self.config.min_completion_score

    @property
    def cache_ttl(self) -> int:
        """Delegate to config.cache_ttl."""
        return self.config.cache_ttl

    @property
    def offline_mode(self) -> bool:
        """Delegate to config.offline_mode."""
        return self.config.offline_mode

    @property
    def max_context_messages(self) -> int:
        """Delegate to config.max_context_messages."""
        return self.config.max_context_messages

    @property
    def max_context_tokens(self) -> Optional[int]:
        """Delegate to config.max_context_tokens."""
        return self.config.max_context_tokens

    @property
    def context_pruning_strategy(
        self,
    ) -> Literal["conservative", "balanced", "aggressive"]:
        """Delegate to config.context_pruning_strategy."""
        return self.config.context_pruning_strategy

    @property
    def context_token_budget(self) -> Optional[int]:
        """Delegate to config.context_token_budget."""
        return self.config.context_token_budget

    @property
    def context_pruning_aggressiveness(self) -> float:
        """Delegate to config.context_pruning_aggressiveness."""
        return self.config.context_pruning_aggressiveness

    @property
    def context_summarization_frequency(self) -> int:
        """Delegate to config.context_summarization_frequency."""
        return self.config.context_summarization_frequency

    @property
    def response_format(self) -> Optional[str]:
        """Delegate to config.response_format."""
        return self.config.response_format

    @property
    def reasoning_strategy(self) -> str:
        """Delegate to config.reasoning_strategy."""
        return self.config.reasoning_strategy

    @property
    def tool_use_policy(
        self,
    ) -> Literal["always", "required_only", "adaptive", "never"]:
        """Delegate to config.tool_use_policy."""
        return self.config.tool_use_policy

    @property
    def tool_use_max_consecutive_calls(self) -> int:
        """Delegate to config.tool_use_max_consecutive_calls."""
        return self.config.tool_use_max_consecutive_calls

    @property
    def check_tool_feasibility(self) -> bool:
        """Delegate to config.check_tool_feasibility."""
        return self.config.check_tool_feasibility

    @property
    def vector_memory_collection(self) -> Optional[str]:
        """Delegate to config.vector_memory_collection."""
        return self.config.vector_memory_collection

    @property
    def retry_config(self) -> Dict[str, Any]:
        """Delegate to config.retry_config."""
        return self.config.retry_config

    @property
    def model_provider_options(self) -> Dict[str, Any]:
        """Delegate to config.model_provider_options."""
        return self.config.model_provider_options

    # =========================================================================
    # Event System
    # =========================================================================

    def emit_event(self, event_type: AgentStateEvent, data: Dict[str, Any]) -> None:
        """
        Emit an event to all registered callbacks.

        Args:
            event_type: The type of event being emitted
            data: The data associated with the event
        """
        if self.event_bus and self.enable_state_observation:
            # Include basic agent/session context with all events
            event_data = {
                "agent_name": self.agent_name,
                "session_id": getattr(self.session, "session_id", None),
                "task": getattr(self.session, "current_task", None),
                "task_status": str(getattr(self.session, "task_status", "unknown")),
                "iterations": getattr(self.session, "iterations", 0),
            }
            # Merge with event-specific data (event data takes precedence)
            event_data = {**event_data, **data}
            self.event_bus.emit(event_type, event_data)

    async def emit_event_async(
        self, event_type: AgentStateEvent, data: Dict[str, Any]
    ) -> None:
        """
        Emit an event to all registered async callbacks.

        Args:
            event_type: The type of event being emitted
            data: The data associated with the event
        """
        if self.event_bus and self.enable_state_observation:
            # Include basic agent/session context with all events
            context_data = {
                "agent_name": self.agent_name,
                "session_id": getattr(self.session, "session_id", None),
                "task": getattr(self.session, "current_task", None),
                "task_status": str(getattr(self.session, "task_status", "unknown")),
                "iterations": getattr(self.session, "iterations", 0),
            }
            # Merge with event-specific data (event data takes precedence)
            event_data = {**context_data, **data}
            await self.event_bus.emit_async(event_type, event_data)

    # =========================================================================
    # Accessor Methods
    # =========================================================================

    async def close(self):
        """Safely close resources like the MCP client."""
        if self.agent_logger:
            self.agent_logger.info(f"Closing context for {self.agent_name}...")
            self.agent_logger.info(f"{self.agent_name} context closed successfully.")

    def get_logger(self) -> Logger:
        """Get the agent logger."""
        if not self.agent_logger:
            raise RuntimeError("Logger is not initialized in this context.")
        return self.agent_logger

    def get_tool_logger(self) -> Logger:
        """Get the tool logger."""
        if not self.tool_logger:
            raise RuntimeError("Tool logger is not initialized in this context.")
        return self.tool_logger

    def get_result_logger(self) -> Logger:
        """Get the result logger."""
        if not self.result_logger:
            raise RuntimeError("Result logger is not initialized in this context.")
        return self.result_logger

    def get_model_provider(self) -> BaseModelProvider:
        """Get the model provider."""
        if not self.model_provider:
            raise RuntimeError("ModelProvider is not initialized in this context.")
        return self.model_provider

    def get_tool_manager(self) -> ToolManager:
        """Get the tool manager."""
        if not self.tool_manager:
            raise RuntimeError("ToolManager is not initialized in this context.")
        return self.tool_manager

    def get_memory_manager(self) -> Union[MemoryManager, VectorMemoryManager]:
        """Get the memory manager."""
        if not self.memory_manager:
            raise RuntimeError("MemoryManager is not initialized in this context.")
        return self.memory_manager

    def get_reflection_manager(self):
        """Get the reflection manager (deprecated, returns None)."""
        # Reflection is now handled by the simplified infrastructure
        return None

    def get_workflow_manager(self) -> WorkflowManager:
        """Get the workflow manager."""
        if not self.workflow_manager:
            raise RuntimeError("WorkflowManager is not initialized in this context.")
        return self.workflow_manager

    @property
    def reasoning_engine(self) -> "ReasoningEngine":
        """Get the reasoning engine with lazy initialization."""
        if self._reasoning_engine is None:
            from reactive_agents.core.reasoning.engine import get_reasoning_engine

            self._reasoning_engine = get_reasoning_engine(self)
        return self._reasoning_engine

    def get_reasoning_engine(self) -> "ReasoningEngine":
        """Get the reasoning engine (convenience method)."""
        return self.reasoning_engine

    def get_tools(self) -> List[Any]:
        """Get available tools from the tool manager."""
        return self.tool_manager.get_available_tools() if self.tool_manager else []

    def get_tool_names(self) -> List[str]:
        """Get names of available tools."""
        if self.tool_manager:
            tool_names = self.tool_manager.get_available_tool_names()
            return list(tool_names) if isinstance(tool_names, set) else tool_names
        return []

    def get_tool_signatures(self) -> List[Any]:
        """Get tool signatures."""
        return self.tool_manager.tool_signatures if self.tool_manager else []

    def get_tool_by_name(self, name: str) -> Optional[Any]:
        """Get a tool by name."""
        if not self.tool_manager:
            return None
        for tool in self.tool_manager.tools:
            if getattr(tool, "name", None) == name:
                return tool
        return None

    def get_reflections(self) -> List[Any]:
        """Get reflections (deprecated, returns empty list)."""
        # Reflection is now handled by the simplified infrastructure
        return []

    def get_session_history(self) -> List[Any]:
        """Get session history from memory manager."""
        if self.memory_manager and hasattr(self.memory_manager, "get_session_history"):
            return self.memory_manager.get_session_history()
        return []

    def get_workflow_context(self) -> Optional[Dict[str, Any]]:
        """Get workflow context from workflow manager."""
        if self.workflow_manager and hasattr(self.workflow_manager, "get_full_context"):
            return self.workflow_manager.get_full_context()
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics from metrics manager."""
        if self.metrics_manager:
            return self.metrics_manager.get_metrics()
        return {}  # Return empty if metrics disabled

    def has_completed_required_tools(self) -> Tuple[bool, set]:
        """
        Check if all required tools have been completed.

        Returns:
            A tuple of (tools_completed: bool, missing_tools: set[str])
        """
        min_required_tools = self.session.min_required_tools or set()
        successful_tools = self.session.successful_tools
        if not min_required_tools:
            return True, set()
        missing_tools = min_required_tools - successful_tools
        tools_completed = len(missing_tools) == 0
        return tools_completed, missing_tools


# Note: model_rebuild() calls are no longer needed with the new ComponentContext/ContextProtocol architecture
# Components now accept either AgentContext or ComponentContext via the ContextProtocol interface
