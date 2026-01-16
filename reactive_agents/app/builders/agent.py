"""
Builder module for creating agent instances with a fluent interface.

This module provides builder classes and utility functions to simplify
the creation and configuration of agents.
"""

import json
from typing import (
    Any,
    Dict,
    Awaitable,
    Callable,
    Optional,
    List,
    Tuple,
    Union,
    TypeVar,
    Set,
    Literal,
    TYPE_CHECKING,
)
import asyncio
from enum import Enum
from typing_extensions import Literal
from pydantic import BaseModel, Field, ConfigDict

from reactive_agents.core.types.execution_types import ExecutionResult
from reactive_agents.providers.external.client import MCPClient
from reactive_agents.core.types.confirmation_types import ConfirmationCallbackProtocol
from reactive_agents.config.logging import LogLevel, formatter
from reactive_agents.utils.logging import Logger
from reactive_agents.config.mcp_config import MCPConfig
from reactive_agents.app.agents.reactive_agent import ReactiveAgent
from reactive_agents.core.tools.base import Tool
from reactive_agents.core.types.event_types import AgentStateEvent

# Import new architecture components
from reactive_agents.core.config.agent_config import AgentConfig
from reactive_agents.core.factory.component_factory import ComponentFactory
from reactive_agents.core.context.agent_context import AgentContext
from reactive_agents.core.types.event_types import (
    SessionStartedEventData,
    SessionEndedEventData,
    TaskStatusChangedEventData,
    IterationStartedEventData,
    IterationCompletedEventData,
    ToolCalledEventData,
    ToolCompletedEventData,
    ToolFailedEventData,
    ReflectionGeneratedEventData,
    FinalAnswerSetEventData,
    MetricsUpdatedEventData,
    ErrorOccurredEventData,
)
from reactive_agents.core.events.event_bus import EventCallback, AsyncEventCallback
from reactive_agents.core.types.agent_types import ReactiveAgentConfig
from reactive_agents.core.types.reasoning_types import ReasoningStrategies
from reactive_agents.config.natural_language_config import create_agent_from_nl


# Define type variables for better type hinting
T = TypeVar("T")
ReactiveAgentBuilderT = TypeVar("ReactiveAgentBuilderT", bound="ReactiveAgentBuilder")

# Import the reusable ReasoningStrategies type
from reactive_agents.core.types.reasoning_types import ReasoningStrategies

ReasoningStrategyType = ReasoningStrategies


class Provider(str, Enum):
    """Supported LLM providers for the agent framework.

    Use these enum values with `with_model()` for type-safe configuration:

    Example:
        builder.with_model(Provider.ANTHROPIC, "claude-3-sonnet-20240229")
        - Or with string format:
        builder.with_model("anthropic:claude-3-sonnet-20240229")
    """

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    GROQ = "groq"
    GOOGLE = "google"

    @classmethod
    def values(cls) -> List[str]:
        """Get all supported provider names."""
        return [p.value for p in cls]

    @classmethod
    def is_valid(cls, provider: str) -> bool:
        """Check if a provider name is valid."""
        return provider.lower() in cls.values()


class ContextPruningStrategy(str, Enum):
    """Strategies for context pruning during agent execution.

    Use these enum values with `with_context_pruning_strategy()` for type-safe configuration:

    Example:
        builder.with_context_pruning_strategy(ContextPruningStrategy.BALANCED)
    """

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"

    @classmethod
    def values(cls) -> List[str]:
        """Get all supported strategy names."""
        return [s.value for s in cls]

    @classmethod
    def is_valid(cls, strategy: str) -> bool:
        """Check if a strategy name is valid."""
        return strategy.lower() in cls.values()


class ToolUsePolicy(str, Enum):
    """Policies controlling when and how tools are used.

    Use these enum values with `with_tool_use_policy()` for type-safe configuration:

    Example:
        builder.with_tool_use_policy(ToolUsePolicy.ADAPTIVE)
    """

    ALWAYS = "always"
    REQUIRED_ONLY = "required_only"
    ADAPTIVE = "adaptive"
    NEVER = "never"

    @classmethod
    def values(cls) -> List[str]:
        """Get all supported policy names."""
        return [p.value for p in cls]

    @classmethod
    def is_valid(cls, policy: str) -> bool:
        """Check if a policy name is valid."""
        return policy.lower() in cls.values()


class BuilderValidationError(ValueError):
    """Exception raised when builder configuration is invalid.

    Provides detailed error messages with suggestions for valid values.
    """

    def __init__(
        self, message: str, field: str, valid_options: Optional[List[str]] = None
    ):
        self.field = field
        self.valid_options = valid_options
        full_message = f"Builder validation error for '{field}': {message}"
        if valid_options:
            full_message += f"\n  Valid options: {', '.join(valid_options)}"
        super().__init__(full_message)


class ToolConfig(BaseModel):
    """Configuration for a tool"""

    name: str
    is_custom: bool = False
    description: Optional[str] = None
    source: str = "unknown"


class ConfirmationConfig(BaseModel):
    """Configuration for the confirmation system"""

    enabled: bool = True
    strategy: str = "always"
    excluded_tools: List[str] = Field(default_factory=list)
    included_tools: Optional[List[str]] = None
    allowed_silent_tools: List[str] = Field(default_factory=list)
    timeout: Optional[float] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


# Convenience function for the absolute simplest agent creation
async def quick_create_agent(
    task: str,
    model: str = "ollama:cogito:14b",
    tools: List[str] = ["brave-search", "time"],
    interactive: bool = False,
) -> ExecutionResult:
    """
    Create and run a ReactiveAgent with minimal configuration

    This is the simplest possible way to create and run an agent.

    Args:
        task: The task for the agent to perform
        model: The model to use
        tools: List of tool names to include
        interactive: Whether to require confirmation for tool usage
        use_reactive_v2: Whether to use ReactiveAgentV2 (default: True)

    Returns:
        The result dictionary from the agent run
    """
    # Create simple confirmation callback if interactive is True
    confirmation_callback = None
    if interactive:

        async def simple_callback(
            action_description: str, details: Dict[str, Any]
        ) -> bool:
            print(f"\nTool: {details.get('tool', 'unknown')}")
            user_input = input("Proceed? (y/n) [y]: ").lower().strip()
            return user_input == "y" or user_input == ""

        confirmation_callback = simple_callback

    # Create and run the agent (default to ReactiveAgent)
    agent = await ReactiveAgentBuilder().with_model(model).with_mcp_tools(tools).build()

    if confirmation_callback:
        agent.context.confirmation_callback = confirmation_callback

    try:
        return await agent.run(initial_task=task)
    finally:
        await agent.close()


class ReactiveAgentBuilder:
    """
    Unified builder class for creating ReactiveAgent instances with full framework integration.

    This class provides comprehensive support for:
    - Dynamic reasoning strategies (reflect_decide_act, plan_execute_reflect, reactive, adaptive)
    - Task classification and adaptive strategy switching
    - Natural language configuration
    - Vector memory integration
    - Enhanced event system with dynamic event handlers
    - Advanced tool management (MCP + custom tools)
    - Real-time control operations (pause, resume, stop, terminate)
    - Comprehensive context management

    Examples:
        Basic reactive agent:
        ```python
        agent = await (ReactiveAgentBuilder()
                .with_name("Reactive Agent")
                .with_model("ollama:qwen3:4b")
                .with_reasoning_strategy("reflect_decide_act")
                .with_mcp_tools(["brave-search", "sqlite"])
                .build())
        ```

        Adaptive agent with strategy switching:
        ```python
        agent = await (ReactiveAgentBuilder()
                .with_name("Adaptive Agent")
                .with_reasoning_strategy("adaptive")
                .with_dynamic_strategy_switching(True)
                .with_mcp_tools(["brave-search", "time"])
                .build())
        ```

        Natural language configuration:
        ```python
        agent = await (ReactiveAgentBuilder()
                .with_config_prompt(
                    "Create an agent that can research topics and analyze data"
                )
                .build())
        ```

        With vector memory:
        ```python
        agent = await (ReactiveAgentBuilder()
                .with_name("Memory Agent")
                .with_vector_memory("research_memories")
                .with_reasoning_strategy("plan_execute_reflect")
                .build())
        ```

        Event-driven agent:
        ```python
        agent = await (ReactiveAgentBuilder()
                .with_name("Event Agent")
                .with_reasoning_strategy("reflect_decide_act")
                .on_tool_called(lambda event: print(f"Tool: {event['tool_name']}"))
                .on_session_started(lambda event: print("Session started"))
                .build())
        ```
    """

    def __init__(self):
        # Initialize with comprehensive defaults
        self._config = {
            "agent_name": "ReactiveAgent",
            "role": "Enhanced Task Executor",
            "provider_model_name": "ollama:cogito:14b",
            "model_provider_options": {},
            "mcp_client": None,
            "min_completion_score": 1.0,
            "builder_prompt": None,
            "instructions": "Solve tasks efficiently using dynamic reasoning strategies.",
            "max_iterations": 10,
            "reflect_enabled": True,
            "log_level": "info",
            "quiet_mode": False,
            "initial_task": None,
            "tool_use_enabled": True,
            "use_memory_enabled": True,
            "collect_metrics_enabled": True,
            "check_tool_feasibility": True,
            "enable_caching": True,
            "confirmation_callback": None,
            "confirmation_config": {},
            "max_context_messages": 20,
            "max_context_tokens": None,
            "enable_context_pruning": True,
            "enable_context_summarization": True,
            "context_pruning_strategy": "balanced",
            "context_token_budget": 4000,
            "context_pruning_aggressiveness": "balanced",
            "context_summarization_frequency": 3,
            "tool_use_policy": "adaptive",
            "tool_use_max_consecutive_calls": 3,
            # Advanced configuration
            "reasoning_strategy": "adaptive",
            "enable_reactive_execution": True,
            "enable_dynamic_strategy_switching": True,
            "kwargs": {},
        }
        self._mcp_client: Optional[MCPClient] = None
        self._mcp_config: Optional[MCPConfig] = None
        self._mcp_server_filter: Optional[List[str]] = None
        self._custom_tools: List[Any] = []
        self._registered_tools: Set[str] = set()
        self._logger = Logger(
            "ReactiveAgentBuilder", "builder", self._config.get("log_level", "info")
        )
        self._logger.formatter = formatter

        # Advanced features
        self._vector_memory_enabled: bool = False
        self._vector_memory_collection: Optional[str] = None

    def from_prompt(self, agent_description: str, task: str) -> "ReactiveAgentBuilder":
        """
        Create an agent from a prompt.
        """
        self._config["builder_prompt"] = agent_description
        self._config["initial_task"] = task
        return self

    # Basic configuration methods
    def with_name(self, name: str) -> "ReactiveAgentBuilder":
        """Set the agent's name"""
        self._config["agent_name"] = name
        return self

    def with_role(self, role: str) -> "ReactiveAgentBuilder":
        """Set the agent's role"""
        self._config["role"] = role
        return self

    def with_model(
        self,
        model_name_or_provider: Union[str, Provider],
        model: Optional[str] = None,
    ) -> "ReactiveAgentBuilder":
        """Set the model to use for the agent.

        Args:
            model_name_or_provider: Either:
                - Full model spec string: "provider:model" (e.g., "anthropic:claude-3-sonnet")
                - Provider enum: Provider.ANTHROPIC, Provider.OPENAI, etc.
            model: Model name when using Provider enum (required if using enum)

        Returns:
            self for method chaining

        Raises:
            BuilderValidationError: If provider or model format is invalid

        Examples:
            # String format (existing pattern)
            builder.with_model("anthropic:claude-3-sonnet")

            # Type-safe enum format
            builder.with_model(Provider.ANTHROPIC, "claude-3-sonnet")
        """
        # Handle Provider enum
        if isinstance(model_name_or_provider, Provider):
            if model is None:
                raise BuilderValidationError(
                    "Model name is required when using Provider enum",
                    field="model",
                )
            full_model_name = f"{model_name_or_provider.value}:{model}"
        else:
            full_model_name = model_name_or_provider

        # Validate format
        if ":" not in full_model_name:
            raise BuilderValidationError(
                f"Invalid model format '{full_model_name}'. Expected 'provider:model' format "
                f"(e.g., 'anthropic:claude-3-sonnet', 'ollama:llama3:8b')",
                field="model",
                valid_options=[f"{p}:<model_name>" for p in Provider.values()],
            )

        # Extract and validate provider
        provider = full_model_name.split(":")[0].lower()
        if not Provider.is_valid(provider):
            raise BuilderValidationError(
                f"Unknown provider '{provider}'",
                field="model",
                valid_options=Provider.values(),
            )

        self._config["provider_model_name"] = full_model_name
        return self

    def with_model_provider_options(
        self, options: Dict[str, Any]
    ) -> "ReactiveAgentBuilder":
        """Set the model provider options for the agent"""
        self._config["model_provider_options"] = options
        return self

    def with_instructions(self, instructions: str) -> "ReactiveAgentBuilder":
        """Set the agent's instructions"""
        self._config["instructions"] = instructions
        return self

    def with_max_iterations(self, max_iterations: int) -> "ReactiveAgentBuilder":
        """Set the maximum number of iterations for the agent"""
        self._config["max_iterations"] = max_iterations
        return self

    def with_reflection(self, enabled: bool = True) -> "ReactiveAgentBuilder":
        """Enable or disable reflection"""
        self._config["reflect_enabled"] = enabled
        return self

    def with_log_level(self, level: Union[LogLevel, str]) -> "ReactiveAgentBuilder":
        """Set the log level (debug, info, warning, error, critical)"""
        if isinstance(level, LogLevel):
            level = level.value
        self._config["log_level"] = level
        return self

    def with_quiet_mode(self, enabled: bool = True) -> "ReactiveAgentBuilder":
        """
        Enable quiet mode to suppress all logging except critical errors.

        Args:
            enabled: If True, suppress all output except CRITICAL level logs

        Returns:
            Self for method chaining
        """
        self._config["quiet_mode"] = enabled
        if enabled:
            self._config["log_level"] = LogLevel.CRITICAL.value
        return self

    # Advanced reasoning strategy methods
    def with_reasoning_strategy(
        self,
        strategy: Union[ReasoningStrategies, str] = ReasoningStrategies.ADAPTIVE,
    ) -> "ReactiveAgentBuilder":
        """
        Set the initial reasoning strategy for the agent.

        Args:
            strategy: Either a ReasoningStrategies enum or a string strategy name.
                      Default: ReasoningStrategies.ADAPTIVE

        Available strategies:
        - REACTIVE: Quick reactive responses (fastest)
        - REFLECT_DECIDE_ACT: Reflect, decide, then act (most robust)
        - PLAN_EXECUTE_REFLECT: Plan first, execute, then reflect
        - SELF_ASK: Question decomposition approach
        - GOAL_ACTION_FEEDBACK: GAF pattern
        - ADAPTIVE: Switch strategies based on task complexity

        Raises:
            BuilderValidationError: If strategy is invalid

        Examples:
            # Using enum (recommended)
            builder.with_reasoning_strategy(ReasoningStrategies.REACTIVE)

            # Using string (still supported)
            builder.with_reasoning_strategy("reactive")
        """
        # Convert string to enum if needed
        if isinstance(strategy, str):
            strategy_lower = strategy.lower()
            valid_strategies = [s.value for s in ReasoningStrategies]
            if strategy_lower not in valid_strategies:
                raise BuilderValidationError(
                    f"Unknown reasoning strategy '{strategy}'",
                    field="reasoning_strategy",
                    valid_options=valid_strategies,
                )
            strategy = ReasoningStrategies(strategy_lower)

        self._config["reasoning_strategy"] = strategy
        return self

    @staticmethod
    def get_available_strategies() -> List[str]:
        """
        Get a list of all available reasoning strategies.

        Returns:
            List[str]: List of available strategy names

        Example:
            ```python
            strategies = ReactiveAgentBuilder.get_available_strategies()
            print(f"Available strategies: {strategies}")
            ```
        """
        from reactive_agents.core.types.reasoning_types import ReasoningStrategies

        return [strategy.value for strategy in ReasoningStrategies]

    @staticmethod
    def get_strategy_descriptions() -> Dict[str, str]:
        """
        Get descriptions of all available reasoning strategies.

        Returns:
            Dict[str, str]: Dictionary mapping strategy names to descriptions

        Example:
            ```python
            descriptions = ReactiveAgentBuilder.get_strategy_descriptions()
            for strategy, desc in descriptions.items():
                print(f"{strategy}: {desc}")
            ```
        """
        return {
            "reflect_decide_act": "Reflect, decide, then act (most robust, good for complex tasks)",
            "plan_execute_reflect": "Plan first, execute, then reflect (good for structured tasks)",
            "reactive": "Quick reactive responses (fastest, good for simple queries)",
            "adaptive": "Switch strategies based on task complexity (most flexible)",
            "memory_enhanced": "Enhanced with memory capabilities (good for context-heavy tasks)",
        }

    class Strategies:
        """Static class providing autocomplete for available reasoning strategies."""

        @staticmethod
        def get_all() -> List[str]:
            """Get all available strategy names."""
            from reactive_agents.core.types.reasoning_types import ReasoningStrategies

            return [strategy.value for strategy in ReasoningStrategies]

        # Static attributes for autocomplete
        REFLECT_DECIDE_ACT = "reflect_decide_act"
        PLAN_EXECUTE_REFLECT = "plan_execute_reflect"
        REACTIVE = "reactive"
        ADAPTIVE = "adaptive"
        MEMORY_ENHANCED = "memory_enhanced"
        SELF_ASK = "self_ask"
        GOAL_ACTION_FEEDBACK = "goal_action_feedback"

    def with_dynamic_strategy_switching(
        self, enabled: bool = True
    ) -> "ReactiveAgentBuilder":
        """Enable or disable dynamic reasoning strategy switching during execution"""
        self._config["enable_dynamic_strategy_switching"] = enabled
        return self

    def with_reactive_execution(self, enabled: bool = True) -> "ReactiveAgentBuilder":
        """Enable or disable reactive execution engine"""
        self._config["enable_reactive_execution"] = enabled
        return self

    # vector memory configuration

    def with_vector_memory(
        self, collection_name: Optional[str] = None
    ) -> "ReactiveAgentBuilder":
        """
        Enable ChromaDB vector memory for semantic memory search.

        Args:
            collection_name: Name of the ChromaDB collection (defaults to agent_name)
        """
        self._vector_memory_enabled = True
        self._vector_memory_collection = collection_name
        return self

    # Tool configuration methods
    def with_mcp_tools(self, server_filter: List[str]) -> "ReactiveAgentBuilder":
        """
        Configure the MCP client with specific server-side tools

        Args:
            server_filter: List of MCP tool names to include
        """
        self._mcp_server_filter = server_filter
        self._config["mcp_server_filter"] = server_filter
        # warn of servers not found
        if self._mcp_config:
            for server_name in server_filter:
                if server_name not in self._mcp_config.mcpServers.keys():
                    self._logger.warning(
                        f"Server {server_name} not found in MCP config skipping..."
                    )

        # Track MCP tools for debugging
        for tool_name in server_filter:
            self._registered_tools.add(f"mcp:{tool_name}")
        return self

    def with_custom_tools(self, tools: List[Any]) -> "ReactiveAgentBuilder":
        """
        Add custom tools to the agent

        These tools should be decorated with the @tool() decorator from tools.decorators

        Args:
            tools: List of custom tool functions or objects
        """
        for tool in tools:
            # If it's already a Tool instance, add it directly
            if hasattr(tool, "name") and hasattr(tool, "tool_definition"):
                self._custom_tools.append(tool)
                self._registered_tools.add(
                    f"custom:{getattr(tool, 'name', str(id(tool)))}"
                )
            # If it's a function decorated with @tool(), wrap it in a Tool class
            elif hasattr(tool, "tool_definition"):
                wrapped_tool = Tool(tool)
                # Ensure the name is preserved from the function
                if not hasattr(wrapped_tool, "name") and hasattr(tool, "__name__"):
                    wrapped_tool.name = tool.__name__
                self._custom_tools.append(wrapped_tool)
                self._registered_tools.add(f"custom:{wrapped_tool.name}")
            else:
                raise ValueError(
                    f"Custom tool {tool.__name__ if hasattr(tool, '__name__') else tool} "
                    f"is not properly decorated with @tool()"
                )

        # Track tool registrations for debugging
        if not hasattr(self, "_debug_registered_tools"):
            self._debug_registered_tools = []
        for tool in self._custom_tools:
            tool_name = getattr(tool, "name", getattr(tool, "__name__", str(id(tool))))
            self._debug_registered_tools.append(f"Custom: {tool_name}")

        return self

    def with_tool_use(self, tool_use: bool = True) -> "ReactiveAgentBuilder":
        self._config["tool_use_enabled"] = tool_use
        return self

    def with_tools(
        self,
        tools: Optional[List[Any]] = None,
        *,
        mcp_tools: Optional[List[str]] = None,
        custom_tools: Optional[List[Any]] = None,
    ) -> "ReactiveAgentBuilder":
        """
        Configure tools for the agent with automatic type detection.

        This method intelligently detects tool types:
        - Strings are treated as MCP server names (e.g., "brave-search", "time")
        - Functions/objects with `tool_definition` are treated as custom tools

        Args:
            tools: Mixed list of tools - strings for MCP servers, decorated functions for custom tools
            mcp_tools: (Deprecated) Explicit list of MCP tool names
            custom_tools: (Deprecated) Explicit list of custom tool functions

        Examples:
            # Auto-detection (recommended):
            .with_tools([my_custom_tool, "brave-search", another_tool, "time"])

            # Explicit separation (legacy, still supported):
            .with_tools(mcp_tools=["brave-search"], custom_tools=[my_tool])
        """
        detected_mcp_tools: List[str] = []
        detected_custom_tools: List[Any] = []

        # Process the unified tools list with auto-detection
        if tools:
            for tool in tools:
                if isinstance(tool, str):
                    # String = MCP server name
                    detected_mcp_tools.append(tool)
                elif hasattr(tool, "tool_definition") or (
                    hasattr(tool, "name") and callable(getattr(tool, "execute", None))
                ):
                    # Has tool_definition or is a Tool instance = custom tool
                    detected_custom_tools.append(tool)
                else:
                    # Unknown type - try to provide helpful error
                    tool_repr = getattr(tool, "__name__", repr(tool))
                    raise ValueError(
                        f"Unknown tool type: {tool_repr}. "
                        f"Tools must be either strings (MCP server names) or "
                        f"functions decorated with @tool()."
                    )

        # Also handle explicit mcp_tools/custom_tools params for backward compatibility
        if mcp_tools:
            detected_mcp_tools.extend(mcp_tools)
        if custom_tools:
            detected_custom_tools.extend(custom_tools)

        # Register the detected tools
        if detected_mcp_tools:
            self.with_mcp_tools(detected_mcp_tools)
        if detected_custom_tools:
            self.with_custom_tools(detected_custom_tools)

        # Add metadata to help track tool sources
        self._config["hybrid_tools_config"] = {
            "mcp_tools": detected_mcp_tools,
            "custom_tools_count": len(detected_custom_tools),
        }

        return self

    def with_tool_caching(self, enabled: bool = True) -> "ReactiveAgentBuilder":
        """Enable or disable tool caching"""
        self._config["enable_caching"] = enabled
        return self

    def with_mcp_client(self, mcp_client: MCPClient) -> "ReactiveAgentBuilder":
        """
        Use a pre-configured MCP client

        This allows using an MCP client that has already been initialized
        with specific configurations.

        Args:
            mcp_client: An initialized MCPClient instance
        """
        self._mcp_client = mcp_client
        self._config["mcp_client"] = mcp_client
        return self

    def with_mcp_config(self, mcp_config: MCPConfig) -> "ReactiveAgentBuilder":
        """
        Use an MCP server configuration

        This allows using an MCP client that has already been initialized
        with specific configurations.

        Args:
            mcp_config: An initialized MCPConfig instance
        """
        self._mcp_config = mcp_config
        self._config["mcp_config"] = mcp_config
        return self

    def with_confirmation(
        self,
        callback: ConfirmationCallbackProtocol,
        config: Optional[Union[Dict[str, Any], ConfirmationConfig]] = None,
    ) -> "ReactiveAgentBuilder":
        """
        Configure the confirmation system

        Args:
            callback: The confirmation callback function
            config: Optional configuration for the confirmation system
        """
        self._config["confirmation_callback"] = callback

        if config:
            # Convert Pydantic model to dict if needed
            if isinstance(config, ConfirmationConfig):
                config = config.model_dump()
            self._config["confirmation_config"] = config

        return self

    def with_advanced_config(self, **kwargs) -> "ReactiveAgentBuilder":
        """
        Set any configuration options directly

        This allows setting any configuration options that don't have specific methods
        """
        self._config.update(kwargs)
        return self

    def with_workflow_context(self, context: Dict[str, Any]) -> "ReactiveAgentBuilder":
        """Set shared workflow context data"""
        self._config["workflow_context_shared"] = context
        return self

    def with_response_format(self, format_spec: str) -> "ReactiveAgentBuilder":
        """Set the response format specification for the agent's final answer"""
        self._config["response_format"] = format_spec
        return self

    def with_max_context_messages(self, value: int) -> "ReactiveAgentBuilder":
        """Set the maximum number of context messages to retain."""
        self._config["max_context_messages"] = value
        return self

    def with_max_context_tokens(self, value: int) -> "ReactiveAgentBuilder":
        """Set the maximum number of context tokens to retain."""
        self._config["max_context_tokens"] = value
        return self

    def with_context_pruning(self, value: bool = True) -> "ReactiveAgentBuilder":
        """Enable or disable context pruning."""
        self._config["enable_context_pruning"] = value
        return self

    def with_context_summarization(self, value: bool = True) -> "ReactiveAgentBuilder":
        """Enable or disable context summarization."""
        self._config["enable_context_summarization"] = value
        return self

    def with_context_pruning_strategy(
        self, strategy: Union[ContextPruningStrategy, str]
    ) -> "ReactiveAgentBuilder":
        """Set the context pruning strategy.

        Args:
            strategy: Either a ContextPruningStrategy enum or a string strategy name.

        Available strategies:
        - CONSERVATIVE: Minimal pruning, keeps more context
        - BALANCED: Moderate pruning (default)
        - AGGRESSIVE: Maximum pruning for token efficiency

        Raises:
            BuilderValidationError: If strategy is invalid

        Examples:
            # Using enum (recommended)
            builder.with_context_pruning_strategy(ContextPruningStrategy.BALANCED)

            # Using string (still supported)
            builder.with_context_pruning_strategy("balanced")
        """
        # Convert string to enum if needed
        if isinstance(strategy, str):
            strategy_lower = strategy.lower()
            if not ContextPruningStrategy.is_valid(strategy_lower):
                raise BuilderValidationError(
                    f"Unknown context pruning strategy '{strategy}'",
                    field="context_pruning_strategy",
                    valid_options=ContextPruningStrategy.values(),
                )
            strategy = ContextPruningStrategy(strategy_lower)

        self._config["context_pruning_strategy"] = strategy.value
        return self

    def with_context_token_budget(self, value: int) -> "ReactiveAgentBuilder":
        """Set the token budget for context management."""
        self._config["context_token_budget"] = value
        return self

    def with_context_pruning_aggressiveness(
        self, aggressiveness: Union[ContextPruningStrategy, str]
    ) -> "ReactiveAgentBuilder":
        """Set the aggressiveness of context pruning.

        Args:
            aggressiveness: Either a ContextPruningStrategy enum or a string value.

        Available levels:
        - CONSERVATIVE: Minimal pruning (keeps more context)
        - BALANCED: Moderate pruning (default)
        - AGGRESSIVE: Maximum pruning (prioritizes token efficiency)

        Raises:
            BuilderValidationError: If aggressiveness level is invalid

        Examples:
            # Using enum (recommended)
            builder.with_context_pruning_aggressiveness(ContextPruningStrategy.AGGRESSIVE)

            # Using string (still supported)
            builder.with_context_pruning_aggressiveness("aggressive")
        """
        # Convert string to enum if needed
        if isinstance(aggressiveness, str):
            aggressiveness_lower = aggressiveness.lower()
            if not ContextPruningStrategy.is_valid(aggressiveness_lower):
                raise BuilderValidationError(
                    f"Unknown context pruning aggressiveness '{aggressiveness}'",
                    field="context_pruning_aggressiveness",
                    valid_options=ContextPruningStrategy.values(),
                )
            aggressiveness = ContextPruningStrategy(aggressiveness_lower)

        self._config["context_pruning_aggressiveness"] = aggressiveness.value
        return self

    def with_context_summarization_frequency(
        self, value: int
    ) -> "ReactiveAgentBuilder":
        """Set the number of iterations between context summarizations."""
        self._config["context_summarization_frequency"] = value
        return self

    def with_tool_use_policy(
        self, policy: Union[ToolUsePolicy, str]
    ) -> "ReactiveAgentBuilder":
        """Set the tool use policy.

        Args:
            policy: Either a ToolUsePolicy enum or a string policy name.

        Available policies:
        - ALWAYS: Always attempt to use tools when available
        - REQUIRED_ONLY: Only use tools when explicitly required
        - ADAPTIVE: Dynamically decide based on task requirements (default)
        - NEVER: Never use tools

        Raises:
            BuilderValidationError: If policy is invalid

        Examples:
            # Using enum (recommended)
            builder.with_tool_use_policy(ToolUsePolicy.ADAPTIVE)

            # Using string (still supported)
            builder.with_tool_use_policy("adaptive")
        """
        # Convert string to enum if needed
        if isinstance(policy, str):
            policy_lower = policy.lower()
            if not ToolUsePolicy.is_valid(policy_lower):
                raise BuilderValidationError(
                    f"Unknown tool use policy '{policy}'",
                    field="tool_use_policy",
                    valid_options=ToolUsePolicy.values(),
                )
            policy = ToolUsePolicy(policy_lower)

        self._config["tool_use_policy"] = policy.value
        return self

    def with_tool_use_max_consecutive_calls(self, value: int) -> "ReactiveAgentBuilder":
        """Set the maximum consecutive tool calls before forcing reflection/summarization."""
        self._config["tool_use_max_consecutive_calls"] = value
        return self

    # Factory methods for common agent types
    @classmethod
    async def research_agent(
        cls,
        model: Optional[str] = None,
    ) -> ReactiveAgent:
        """
        Create a pre-configured research agent optimized for information gathering

        Args:
            model: Optional model name to use (default: ollama:cogito:14b)
        """
        builder = cls()
        if model:
            builder.with_model(model)

        return await (
            builder.with_name("Research Agent")
            .with_role("Research Assistant")
            .with_instructions(
                "Research information thoroughly and provide accurate results."
            )
            .with_mcp_tools(["brave-search", "time"])
            .with_reflection(True)
            .with_max_iterations(15)
            .build()
        )

    @classmethod
    async def database_agent(cls, model: Optional[str] = None) -> ReactiveAgent:
        """
        Create a pre-configured database agent optimized for database operations

        Args:
            model: Optional model name to use (default: ollama:cogito:14b)
        """
        builder = cls()
        if model:
            builder.with_model(model)

        return await (
            builder.with_name("Database Agent")
            .with_role("Database Assistant")
            .with_instructions(
                "Perform database operations accurately and efficiently."
            )
            .with_mcp_tools(["sqlite"])
            .with_reflection(True)
            .build()
        )

    @classmethod
    async def crypto_research_agent(
        cls,
        model: Optional[str] = None,
        confirmation_callback: Optional[Callable] = None,
        cryptocurrencies: Optional[List[str]] = None,
    ) -> ReactiveAgent:
        """
        Create a specialized agent for cryptocurrency research and data collection

        Args:
            model: Optional model name to use (default: ollama:cogito:14b)
            confirmation_callback: Optional callback for confirming sensitive operations
            cryptocurrencies: List of cryptocurrencies to track (default: ["Bitcoin", "Ethereum"])
        """
        builder = cls()
        if model:
            builder.with_model(model)

        # Use default list if none provided
        cryptocurrencies = cryptocurrencies or ["Bitcoin", "Ethereum"]

        # Build specialized instructions for crypto research
        crypto_instructions = (
            f"Research current prices for cryptocurrencies and maintain accurate records in a database. "
            f"Focus on these cryptocurrencies: {', '.join(cryptocurrencies)}. "
            f"When researching prices, ensure you get the most current data and properly format the date. "
            f"Always verify data before adding it to the database. Create any necessary tables if they don't exist."
        )

        # Configure the builder
        builder = (
            builder.with_name("Crypto Research Agent")
            .with_role("Financial Data Analyst")
            .with_instructions(crypto_instructions)
            .with_mcp_tools(["brave-search", "sqlite", "time"])
            .with_reflection(True)
            .with_max_iterations(15)
        )

        # Add confirmation callback if provided
        if confirmation_callback:
            builder.with_confirmation(confirmation_callback)

        return await builder.build()

    @classmethod
    async def reactive_research_agent(
        cls, model: Optional[str] = None
    ) -> ReactiveAgent:
        """Create a pre-configured reactive research agent optimized for information gathering"""
        builder = cls()
        if model:
            builder.with_model(model)

        return await (
            builder.with_name("Reactive Research Agent")
            .with_role("Advanced Research Assistant")
            .with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)
            .with_instructions(
                "Research information thoroughly using dynamic reasoning strategies."
            )
            .with_mcp_tools(["brave-search", "time"])
            .with_reflection(True)
            .with_max_iterations(15)
            .with_dynamic_strategy_switching(True)
            .build()
        )

    @classmethod
    async def adaptive_agent(cls, model: Optional[str] = None) -> ReactiveAgent:
        """Create a pre-configured adaptive agent that switches strategies based on task complexity"""
        builder = cls()
        if model:
            builder.with_model(model)

        return await (
            builder.with_name("Adaptive Agent")
            .with_role("Adaptive Task Executor")
            .with_reasoning_strategy(ReasoningStrategies.ADAPTIVE)
            .with_instructions(
                "Adapt reasoning strategy based on task complexity and requirements."
            )
            .with_mcp_tools(["brave-search", "time", "sqlite"])
            .with_reflection(True)
            .with_max_iterations(20)
            .with_dynamic_strategy_switching(True)
            .build()
        )

    @classmethod
    async def add_custom_tools_to_agent(
        cls, agent: ReactiveAgent, custom_tools: List[Any]
    ) -> ReactiveAgent:
        """
        Add custom tools to an existing agent instance

        This utility method provides a clean way to add custom tools to an agent
        that has already been created, such as one from a factory method.

        Args:
            agent: An existing ReactiveAgent instance
            custom_tools: List of custom tool functions or objects

        Returns:
            The updated agent with the new tools added

        Example:
            ```python
            agent = await ReactiveAgentBuilder.research_agent()
            updated_agent = await ReactiveAgentBuilder.add_custom_tools_to_agent(
                agent, [my_custom_tool]
            )
            ```
        """
        if not agent or not hasattr(agent, "context"):
            raise ValueError("Invalid agent provided")

        # Process and wrap the custom tools if needed
        processed_tools = []
        for tool in custom_tools:
            if hasattr(tool, "name") and hasattr(tool, "tool_definition"):
                processed_tools.append(tool)
            elif hasattr(tool, "tool_definition"):
                processed_tools.append(Tool(tool))
            else:
                raise ValueError(
                    f"Custom tool {tool.__name__ if hasattr(tool, '__name__') else tool} "
                    f"is not properly decorated with @tool()"
                )

        # Check for the tools attribute and add tools
        if hasattr(agent.context, "tools"):
            for tool in processed_tools:
                agent.context.tools.append(tool)

        # Update the tool manager if it exists
        tool_manager = getattr(agent.context, "tool_manager", None)
        if tool_manager is not None:
            # Give a small delay to ensure setup is complete
            await asyncio.sleep(0.1)

            # Add tools to the manager
            for tool in processed_tools:
                tool_manager.tools.append(tool)

            # Update tool signatures if possible
            generate_signatures = getattr(
                tool_manager, "_generate_tool_signatures", None
            )
            if callable(generate_signatures):
                generate_signatures()

        return agent

    # Diagnostic methods
    def debug_tools(self) -> Dict[str, Any]:
        """
        Get diagnostic information about the tools configured for this agent

        This method helps with debugging tool registration issues by providing
        information about which tools are registered and their sources.

        Returns:
            Dict[str, Any]: Diagnostic information about registered tools

        Example:
            ```python
            builder = ReactiveAgentBuilder()
                .with_mcp_tools(["brave-search", "time"])
                .with_custom_tools([my_custom_tool])

            # Debug before building
            tool_info = builder.debug_tools()
            print(f"MCP Tools: {tool_info['mcp_tools']}")
            print(f"Custom Tools: {tool_info['custom_tools']}")
            ```
        """
        mcp_tools = []
        custom_tools = []

        # Extract tool info from registered tools
        for tool_id in self._registered_tools:
            if tool_id.startswith("mcp:"):
                mcp_tools.append(tool_id.split(":", 1)[1])
            elif tool_id.startswith("custom:"):
                custom_tools.append(tool_id.split(":", 1)[1])

        # Get tool info from custom tools list
        custom_tool_details = []
        for tool in self._custom_tools:
            tool_name = getattr(tool, "name", getattr(tool, "__name__", str(id(tool))))
            tool_details = {
                "name": tool_name,
                "has_name_attr": hasattr(tool, "name"),
                "has_tool_definition": hasattr(tool, "tool_definition"),
                "type": type(tool).__name__,
            }
            custom_tool_details.append(tool_details)

        return {
            "mcp_tools": mcp_tools,
            "custom_tools": custom_tools,
            "custom_tool_details": custom_tool_details,
            "mcp_client_initialized": self._mcp_client is not None,
            "server_filter": self._mcp_server_filter,
            "total_tools": len(self._registered_tools),
        }

    @staticmethod
    async def diagnose_agent_tools(agent: ReactiveAgent) -> Dict[str, Any]:
        """
        Diagnose tool registration issues in an existing agent

        This static method examines an agent that has already been created
        to check for tool registration issues and provides detailed diagnostics.

        Args:
            agent: The ReactiveAgent instance to diagnose

        Returns:
            Dict[str, Any]: Diagnostic information about the agent's tools

        Example:
            ```python
            agent = await ReactiveAgentBuilder().with_mcp_tools(["brave-search"]).build()

            # Diagnose after building
            diagnosis = await ReactiveAgentBuilder.diagnose_agent_tools(agent)
            if diagnosis["has_tool_mismatch"]:
                print("Warning: Tool registration mismatch detected!")
                print(f"Tools in context: {diagnosis['context_tools']}")
                print(f"Tools in manager: {diagnosis['manager_tools']}")
            ```
        """
        if not agent or not hasattr(agent, "context"):
            return {"error": "Invalid agent or no context attribute"}

        context = agent.context
        tool_manager = getattr(context, "tool_manager", None)
        context_tools = getattr(context, "tools", [])

        # Get tools from context
        context_tool_names = []
        for tool in context_tools:
            tool_name = getattr(tool, "name", str(id(tool)))
            context_tool_names.append(tool_name)

        # Get tools from tool manager
        manager_tool_names = []
        if tool_manager:
            for tool in getattr(tool_manager, "tools", []):
                tool_name = getattr(tool, "name", str(id(tool)))
                manager_tool_names.append(tool_name)

        # Check for mismatches
        context_set = set(context_tool_names)
        manager_set = set(manager_tool_names)

        missing_in_context = manager_set - context_set
        missing_in_manager = context_set - manager_set

        has_mismatch = len(missing_in_context) > 0 or len(missing_in_manager) > 0

        return {
            "context_tools": context_tool_names,
            "manager_tools": manager_tool_names,
            "has_tool_mismatch": has_mismatch,
            "missing_in_context": list(missing_in_context),
            "missing_in_manager": list(missing_in_manager),
            "has_mcp_client": hasattr(context, "mcp_client")
            and context.mcp_client is not None,
            "has_custom_tools": hasattr(agent, "_has_custom_tools"),
        }

    # Event subscription methods
    def with_subscription(
        self, event_type: AgentStateEvent, callback: EventCallback[Any]
    ) -> "ReactiveAgentBuilder":
        """
        Register a callback function for any event type using a more generic interface.

        This provides a more dynamic way to subscribe to events without using specific helper methods.

        Args:
            event_type: The type of event to observe (from AgentStateEvent enum)
            callback: The callback function to invoke when the event occurs

        Returns:
            self for method chaining

        Example:
            ```python
            builder = (ReactiveAgentBuilder()
                .with_subscription(
                    AgentStateEvent.TOOL_CALLED,
                    lambda event: print(f"Tool called: {event['tool_name']}")
                )
                .build())
            ```
        """
        return self.with_event_callback(event_type, callback)

    def with_async_subscription(
        self, event_type: AgentStateEvent, callback: AsyncEventCallback[Any]
    ) -> "ReactiveAgentBuilder":
        """
        Register an async callback function for any event type using a more generic interface.

        This provides a more dynamic way to subscribe to async events without using specific helper methods.

        Args:
            event_type: The type of event to observe (from AgentStateEvent enum)
            callback: The async callback function to invoke when the event occurs

        Returns:
            self for method chaining

        Example:
            ```python
            async def log_tool_call(event):
                await db.log_event(event['tool_name'], event['parameters'])

            builder = (ReactiveAgentBuilder()
                .with_async_subscription(
                    AgentStateEvent.TOOL_CALLED,
                    log_tool_call
                )
                .build())
            ```
        """
        return self.with_async_event_callback(event_type, callback)

    def with_event_callback(
        self, event_type: AgentStateEvent, callback: EventCallback
    ) -> "ReactiveAgentBuilder":
        """
        Register a callback function for a specific event type.

        This allows setting up event observers before the agent is built.

        Args:
            event_type: The type of event to observe
            callback: The callback function to invoke when the event occurs

        Returns:
            self for method chaining

        Example:
            ```python
            builder = (ReactiveAgentBuilder()
                .with_event_callback(
                    AgentStateEvent.TOOL_CALLED,
                    lambda event: print(f"Tool called: {event['tool_name']}")
                )
                .build())
            ```
        """
        if not hasattr(self, "_event_callbacks"):
            self._event_callbacks = {}

        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []

        self._event_callbacks[event_type].append(callback)
        return self

    def with_async_event_callback(
        self, event_type: AgentStateEvent, callback: AsyncEventCallback
    ) -> "ReactiveAgentBuilder":
        """
        Register an async callback function for a specific event type.

        This allows setting up async event observers before the agent is built.

        Args:
            event_type: The type of event to observe
            callback: The async callback function to invoke when the event occurs

        Returns:
            self for method chaining

        Example:
            ```python
            async def log_tool_call(event):
                await db.log_event(event['tool_name'], event['parameters'])

            builder = (ReactiveAgentBuilder()
                .with_async_event_callback(
                    AgentStateEvent.TOOL_CALLED,
                    log_tool_call
                )
                .build())
            ```
        """
        if not hasattr(self, "_async_event_callbacks"):
            self._async_event_callbacks = {}

        if event_type not in self._async_event_callbacks:
            self._async_event_callbacks[event_type] = []

        self._async_event_callbacks[event_type].append(callback)
        return self

    # Convenience methods for specific event types
    def on_session_started(
        self, callback: EventCallback[SessionStartedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for session started events"""
        return self.with_event_callback(AgentStateEvent.SESSION_STARTED, callback)

    def on_session_ended(
        self, callback: EventCallback[SessionEndedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for session ended events"""
        return self.with_event_callback(AgentStateEvent.SESSION_ENDED, callback)

    def on_task_status_changed(
        self, callback: EventCallback[TaskStatusChangedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for task status changed events"""
        return self.with_event_callback(AgentStateEvent.TASK_STATUS_CHANGED, callback)

    def on_iteration_started(
        self, callback: EventCallback[IterationStartedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for iteration started events"""
        return self.with_event_callback(AgentStateEvent.ITERATION_STARTED, callback)

    def on_iteration_completed(
        self, callback: EventCallback[IterationCompletedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for iteration completed events"""
        return self.with_event_callback(AgentStateEvent.ITERATION_COMPLETED, callback)

    def on_tool_called(
        self, callback: EventCallback[ToolCalledEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for tool called events"""
        return self.with_event_callback(AgentStateEvent.TOOL_CALLED, callback)

    def on_tool_completed(
        self, callback: EventCallback[ToolCompletedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for tool completed events"""
        return self.with_event_callback(AgentStateEvent.TOOL_COMPLETED, callback)

    def on_tool_failed(
        self, callback: EventCallback[ToolFailedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for tool failed events"""
        return self.with_event_callback(AgentStateEvent.TOOL_FAILED, callback)

    def on_reflection_generated(
        self, callback: EventCallback[ReflectionGeneratedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for reflection generated events"""
        return self.with_event_callback(AgentStateEvent.REFLECTION_GENERATED, callback)

    def on_final_answer_set(
        self, callback: EventCallback[FinalAnswerSetEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for final answer set events"""
        return self.with_event_callback(AgentStateEvent.FINAL_ANSWER_SET, callback)

    def on_metrics_updated(
        self, callback: EventCallback[MetricsUpdatedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for metrics updated events"""
        return self.with_event_callback(AgentStateEvent.METRICS_UPDATED, callback)

    def on_error_occurred(
        self, callback: EventCallback[ErrorOccurredEventData]
    ) -> "ReactiveAgentBuilder":
        """Register a callback for error occurred events"""
        return self.with_event_callback(AgentStateEvent.ERROR_OCCURRED, callback)

    def on_session_started_async(
        self, callback: AsyncEventCallback[SessionStartedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register an async callback for session started events"""
        return self.with_async_event_callback(AgentStateEvent.SESSION_STARTED, callback)

    def on_session_ended_async(
        self, callback: AsyncEventCallback[SessionEndedEventData]
    ) -> "ReactiveAgentBuilder":
        """Register an async callback for session ended events"""
        return self.with_async_event_callback(AgentStateEvent.SESSION_ENDED, callback)

    # Build method
    async def build(self) -> ReactiveAgent:
        """
        Build and return a configured ReactiveAgent instance.

        This method:
        1. Handles optional builder prompt for dynamic configuration
        2. Creates an AgentConfig from builder fields
        3. Creates an AgentContext with the config
        4. Uses ComponentFactory to create and wire all components
        5. Injects components into the context
        6. Creates and initializes the ReactiveAgent

        Returns:
            ReactiveAgent: A fully configured agent ready to use
        """
        # Handle builder prompt for dynamic configuration (kept for backward compatibility)
        if self._config["builder_prompt"]:
            valid_dynamic_config_keys = [
                "agent_name",
                "role",
                "initial_task",
                "instructions",
                "reasoning_strategy",
                "max_iterations",
                "enable_caching",
                "use_memory_enabled",
            ]
            self._logger.info("Building agent from prompt...")
            from reactive_agents.providers.llm.factory import ModelProviderFactory

            model_provider = ModelProviderFactory.get_model_provider(
                self._config["provider_model_name"]
            )

            config = {key: self._config[key] for key in valid_dynamic_config_keys}

            completion_result = await model_provider.get_completion(
                system="""
                Role: You are an agent configuration builder. You are given a description of the agent and you need to build an agent configuration based on the description and the initial config. Do not stray from the initial config keys. Respond in only valid json.
                Instructions:
                - Create ideal config values to build the most accurate and effective agent for the given task and agent description.
                - You must respond in valid json matching the schema of the initial config.
                - You must not stray from the initial config keys.
                - You must not add any new keys to the config.
                - You must not remove any keys from the config.
                """,
                prompt=f"""
                Task: {self._config["initial_task"]}
                AgentDescription: {self._config["builder_prompt"]}
                Initial config: {json.dumps(config, indent=4)}
                """,
                format="json",
            )

            # Parse the JSON response with error handling
            # get_completion without response_model returns CompletionResponse
            from reactive_agents.providers.llm.base import CompletionResponse
            if not isinstance(completion_result, CompletionResponse):
                self._logger.warning("Unexpected response type, using default config")
                content = None
            else:
                content = completion_result.message.content
            if not content:
                self._logger.warning("Empty response from model, using default config")
            else:
                # Clean potential markdown code blocks
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                try:
                    config = json.loads(content)
                except json.JSONDecodeError as e:
                    self._logger.warning(f"Failed to parse config JSON: {e}, using default config")
            self._logger.info(f"Agent config: {json.dumps(config, indent=4)}")
            self._config.update(config)

        # Configure vector memory if enabled
        if self._vector_memory_enabled:
            collection_name = (
                self._vector_memory_collection or self._config["agent_name"]
            )
            self._config["vector_memory_enabled"] = True
            self._config["vector_memory_collection"] = collection_name
            self._config["use_memory_enabled"] = True
            self._logger.info(
                f"Vector memory enabled with collection: {collection_name}"
            )

        # Configure logging based on builder settings
        from reactive_agents.config.logging import configure_logging
        log_level_str = self._config.get("log_level", "info")
        quiet_mode = self._config.get("quiet_mode", False)

        # Convert string to LogLevel enum if needed
        if isinstance(log_level_str, str):
            log_level = LogLevel(log_level_str.lower())
        else:
            log_level = log_level_str

        configure_logging(level=log_level, quiet=quiet_mode)

        try:
            # =========================================================================
            # Step 1: Create AgentConfig from builder fields
            # =========================================================================
            agent_config = self._create_agent_config()
            self._logger.info(
                f"Created AgentConfig for agent: {agent_config.agent_name}"
            )

            # =========================================================================
            # Step 2: Initialize MCP client if needed (before component creation)
            # =========================================================================
            mcp_client = await self._initialize_mcp_client()

            # =========================================================================
            # Step 3: Create AgentContext with config
            # =========================================================================
            context = AgentContext(config=agent_config)

            # Set MCP client and config on context
            if mcp_client:
                context.mcp_client = mcp_client
            if self._mcp_config:
                context.mcp_config = self._mcp_config

            # Set confirmation callback and config if provided
            if self._config.get("confirmation_callback"):
                context.confirmation_callback = self._config["confirmation_callback"]
            if self._config.get("confirmation_config"):
                context.confirmation_config = self._config["confirmation_config"]

            # Set custom tools on context for tool manager to pick up
            if self._custom_tools:
                context.tools = self._custom_tools

            # =========================================================================
            # Step 4: Use ComponentFactory to create all components
            # =========================================================================
            components = await ComponentFactory.create_components(
                config=agent_config,
                mcp_client=mcp_client,
                custom_tools=self._custom_tools if self._custom_tools else None,
            )
            self._logger.info(f"Created components: {components}")

            # =========================================================================
            # Step 5: Inject components into context
            # =========================================================================
            context.inject_components(components)
            self._logger.info("Injected components into AgentContext")

            # =========================================================================
            # Step 6: Create ReactiveAgent with the configured context
            # =========================================================================
            # We still need ReactiveAgentConfig for ReactiveAgent constructor compatibility
            # but we pass the pre-configured context so it won't recreate components
            reactive_config = ReactiveAgentConfig(**self._config)
            agent = ReactiveAgent(config=reactive_config, context=context)

            # Initialize the agent (this will skip component creation since context is provided)
            await agent.initialize()

            # =========================================================================
            # Step 7: Set up event callbacks if any were registered
            # =========================================================================
            if hasattr(self, "_event_callbacks"):
                for event_type, callbacks in self._event_callbacks.items():
                    for callback in callbacks:
                        if hasattr(agent, "_event_bus") and agent._event_bus:
                            agent._event_bus.register_callback(event_type, callback)

            if hasattr(self, "_async_event_callbacks"):
                for event_type, callbacks in self._async_event_callbacks.items():
                    for callback in callbacks:
                        if hasattr(agent, "_event_bus") and agent._event_bus:
                            agent._event_bus.register_async_callback(
                                event_type, callback
                            )

            self._logger.info(
                f"Successfully built ReactiveAgent: {agent_config.agent_name}"
            )
            return agent

        except Exception as e:
            # Clean up MCP client if agent creation fails
            if self._mcp_client is not None:
                try:
                    await self._mcp_client.close()
                except Exception as cleanup_error:
                    self._logger.error(
                        f"Error closing MCP client during error handling: {cleanup_error}"
                    )

            raise RuntimeError(f"Failed to create ReactiveAgent: {e}") from e

    def _create_agent_config(self) -> AgentConfig:
        """
        Create an AgentConfig from the builder's configuration dictionary.

        This method maps builder fields to AgentConfig fields, handling
        any necessary transformations.

        Returns:
            AgentConfig: The immutable configuration object
        """
        # Map builder config keys to AgentConfig fields
        # Note: AgentConfig has specific field names that may differ from builder config
        config_mapping = {
            # Core Identity
            "agent_name": self._config.get("agent_name", "ReactiveAgent"),
            "provider_model_name": self._config.get(
                "provider_model_name", "ollama:cogito:14b"
            ),
            "instructions": self._config.get("instructions", ""),
            "role": self._config.get("role", ""),
            "role_instructions": self._config.get("role_instructions", {}),
            # Feature Flags
            "tool_use_enabled": self._config.get("tool_use_enabled", True),
            "reflect_enabled": self._config.get("reflect_enabled", False),
            "use_memory_enabled": self._config.get("use_memory_enabled", True),
            "collect_metrics_enabled": self._config.get(
                "collect_metrics_enabled", True
            ),
            "vector_memory_enabled": self._config.get("vector_memory_enabled", False),
            "enable_state_observation": self._config.get(
                "enable_state_observation", True
            ),
            "enable_reactive_execution": self._config.get(
                "enable_reactive_execution", True
            ),
            "enable_dynamic_strategy_switching": self._config.get(
                "enable_dynamic_strategy_switching", False
            ),
            "enable_context_pruning": self._config.get("enable_context_pruning", True),
            "enable_context_summarization": self._config.get(
                "enable_context_summarization", True
            ),
            "enable_caching": self._config.get("enable_caching", True),
            # Execution Parameters
            "max_iterations": self._config.get("max_iterations"),
            "max_task_retries": self._config.get("max_task_retries", 3),
            "log_level": self._config.get("log_level", "info"),
            "min_completion_score": self._config.get("min_completion_score", 1.0),
            "cache_ttl": self._config.get("cache_ttl", 3600),
            "offline_mode": self._config.get("offline_mode", False),
            # Context Management
            "max_context_messages": self._config.get("max_context_messages", 20),
            "max_context_tokens": self._config.get("max_context_tokens"),
            "context_pruning_strategy": self._config.get(
                "context_pruning_strategy", "balanced"
            ),
            "context_token_budget": self._config.get("context_token_budget"),
            "context_pruning_aggressiveness": self._config.get(
                "context_pruning_aggressiveness", 0.5
            ),
            "context_summarization_frequency": self._config.get(
                "context_summarization_frequency", 10
            ),
            "response_format": self._config.get("response_format"),
            "reasoning_strategy": self._config.get("reasoning_strategy", "adaptive"),
            # Tool Configuration
            "tool_use_policy": self._config.get("tool_use_policy", "always"),
            "tool_use_max_consecutive_calls": self._config.get(
                "tool_use_max_consecutive_calls", 5
            ),
            "check_tool_feasibility": self._config.get("check_tool_feasibility", False),
            # Vector Memory Configuration
            "vector_memory_collection": self._config.get("vector_memory_collection"),
            # Model Provider Options
            "model_provider_options": self._config.get("model_provider_options", {}),
        }

        # Handle context_pruning_aggressiveness which might be a string in builder
        aggressiveness = config_mapping["context_pruning_aggressiveness"]
        if isinstance(aggressiveness, str):
            # Convert string aggressiveness to float
            aggressiveness_map = {
                "conservative": 0.3,
                "balanced": 0.5,
                "aggressive": 0.7,
            }
            config_mapping["context_pruning_aggressiveness"] = aggressiveness_map.get(
                aggressiveness, 0.5
            )

        # Filter out None values for optional fields
        filtered_config = {k: v for k, v in config_mapping.items() if v is not None}

        return AgentConfig(**filtered_config)

    async def _initialize_mcp_client(self) -> Optional[MCPClient]:
        """
        Initialize MCP client if configured.

        Returns:
            Optional[MCPClient]: The initialized MCP client, or None if not configured
        """
        # Return existing client if already set
        if self._mcp_client is not None:
            return self._mcp_client

        # Check if MCP is configured
        mcp_server_filter = self._mcp_server_filter or self._config.get(
            "mcp_server_filter"
        )
        mcp_config = self._mcp_config or self._config.get("mcp_config")

        if not mcp_server_filter and not mcp_config:
            return None

        try:
            from reactive_agents.config.mcp_config import MCPConfig

            # Load or validate MCP config
            if mcp_config and not isinstance(mcp_config, MCPConfig):
                mcp_config = MCPConfig.model_validate(mcp_config, strict=False)
            # Don't create empty MCPConfig - let MCPClient load from file if needed

            self._mcp_config = mcp_config

            # Create and initialize MCP client
            # Only pass server_config if we have an actual config, otherwise let client load from file
            mcp_client = MCPClient(
                server_config=mcp_config if mcp_config else None,
                server_filter=mcp_server_filter,
            )
            self._mcp_client = await mcp_client.initialize()

            self._logger.info(
                f"MCP client initialized with servers: {mcp_server_filter}"
            )
            return self._mcp_client

        except Exception as e:
            self._logger.error(f"Failed to initialize MCP client: {e}")
            raise
