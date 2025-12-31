"""
AgentConfig: Immutable configuration dataclass for reactive agents.

This module provides a frozen dataclass that holds all configuration fields
for an agent. By separating configuration from runtime state, we achieve:
- Clear separation of concerns
- Immutability guarantees for configuration
- Easier testing and serialization
- Better documentation of available options
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, Literal, Callable, Awaitable, Union, Tuple, List

from reactive_agents.config.validation import (
    validate_model_format,
    validate_reasoning_strategy,
    ConfigurationValidationError,
)


@dataclass(frozen=True)
class AgentConfig:
    """
    Immutable configuration for a reactive agent.

    This frozen dataclass holds all configuration parameters that define
    an agent's behavior. Once created, the configuration cannot be modified,
    ensuring consistent behavior throughout the agent's lifecycle.

    Attributes are organized into logical groups:
    - Core Identity: Agent name, model, instructions
    - Feature Flags: Enable/disable various capabilities
    - Execution Parameters: Iteration limits, retries, logging
    - Context Management: Message limits, pruning, summarization
    - Tool Configuration: Tool policies and limits
    """

    # =========================================================================
    # Core Identity (5 fields)
    # These fields define the fundamental identity and behavior of the agent
    # =========================================================================
    agent_name: str
    """Unique name identifying this agent instance."""

    provider_model_name: str
    """The LLM provider and model name (e.g., 'openai/gpt-4', 'anthropic/claude-3')."""

    instructions: str = ""
    """High-level instructions that guide the agent's behavior."""

    role: str = ""
    """The role this agent plays (e.g., 'Task Executor', 'Code Reviewer')."""

    role_instructions: Dict[str, Any] = field(default_factory=dict)
    """Role-specific instructions and configurations."""

    # =========================================================================
    # Feature Flags (11 boolean fields)
    # These flags enable or disable various agent capabilities
    # =========================================================================
    tool_use_enabled: bool = True
    """Whether the agent can use tools to accomplish tasks."""

    reflect_enabled: bool = False
    """Whether the agent performs self-reflection on its actions."""

    use_memory_enabled: bool = True
    """Whether the agent uses long-term memory for context."""

    collect_metrics_enabled: bool = True
    """Whether to collect performance and usage metrics."""

    vector_memory_enabled: bool = False
    """Whether to use ChromaDB vector memory for semantic search."""

    enable_state_observation: bool = True
    """Whether to emit state observation events via the event bus."""

    enable_reactive_execution: bool = True
    """Whether to enable the reactive execution engine."""

    enable_dynamic_strategy_switching: bool = False
    """Whether to enable dynamic strategy switching based on task classification."""

    enable_context_pruning: bool = True
    """Whether to enable automatic context pruning to manage token limits."""

    enable_context_summarization: bool = True
    """Whether to enable automatic context summarization."""

    enable_caching: bool = True
    """Whether to enable LLM response caching for efficiency."""

    # =========================================================================
    # Execution Parameters (6 fields)
    # These parameters control the execution behavior of the agent
    # =========================================================================
    max_iterations: Optional[int] = None
    """Maximum number of iterations allowed per task. None means unlimited."""

    max_task_retries: int = 3
    """Maximum number of retries for failed tasks."""

    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    """Logging level for agent operations."""

    min_completion_score: float = 1.0
    """Minimum score (0.0-1.0) required for task completion evaluation."""

    cache_ttl: int = 3600
    """Time-to-live in seconds for cached LLM responses."""

    offline_mode: bool = False
    """Whether to run in offline mode (no external API calls)."""

    # =========================================================================
    # Context Management (8 fields)
    # These parameters control how the agent manages conversation context
    # =========================================================================
    max_context_messages: int = 20
    """Maximum number of context messages to retain in the conversation."""

    max_context_tokens: Optional[int] = None
    """Maximum number of tokens to retain in context. None means unlimited."""

    context_pruning_strategy: Literal["conservative", "balanced", "aggressive"] = "balanced"
    """Strategy for pruning context when limits are reached."""

    context_token_budget: Optional[int] = None
    """Token budget for context management. None uses model defaults."""

    context_pruning_aggressiveness: float = 0.5
    """Aggressiveness level (0.0-1.0) for context pruning."""

    context_summarization_frequency: int = 10
    """Number of iterations between automatic context summarizations."""

    response_format: Optional[str] = None
    """Format specification for the agent's final response (e.g., 'json', 'markdown')."""

    reasoning_strategy: str = "adaptive"
    """The reasoning strategy to use (e.g., 'reactive', 'deliberative', 'adaptive')."""

    # =========================================================================
    # Tool Configuration (3 fields)
    # These parameters control tool usage behavior
    # =========================================================================
    tool_use_policy: Literal["always", "required_only", "adaptive", "never"] = "always"
    """Policy controlling when tools are allowed in the agent loop."""

    tool_use_max_consecutive_calls: int = 5
    """Maximum consecutive tool calls before forcing reflection/summary."""

    check_tool_feasibility: bool = False
    """Whether to check tool feasibility before starting task execution."""

    # =========================================================================
    # Vector Memory Configuration (1 field)
    # Configuration specific to vector memory functionality
    # =========================================================================
    vector_memory_collection: Optional[str] = None
    """Name of the ChromaDB collection for vector memory storage."""

    # =========================================================================
    # Retry Configuration (1 field)
    # Configuration for retry behavior on failures
    # =========================================================================
    retry_config: Dict[str, Any] = field(default_factory=lambda: {
        "max_retries": 3,
        "base_delay": 1.0,
        "max_delay": 10.0,
        "retry_network_errors": True,
    })
    """Configuration for retry behavior on failures."""

    # =========================================================================
    # Model Provider Configuration (1 field)
    # Options passed to the model provider
    # =========================================================================
    model_provider_options: Dict[str, Any] = field(default_factory=dict)
    """Options passed to the LLM model provider."""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], warn_unknown: bool = True) -> "AgentConfig":
        """
        Create an AgentConfig instance from a dictionary.

        This factory method validates configuration values and warns about
        unknown keys before creating a new AgentConfig.

        Args:
            data: Dictionary containing configuration values.
            warn_unknown: If True (default), emit warnings for unknown keys.

        Returns:
            A new AgentConfig instance with the provided configuration.

        Raises:
            ConfigurationValidationError: If any configuration value is invalid.

        Example:
            >>> config = AgentConfig.from_dict({
            ...     "agent_name": "MyAgent",
            ...     "provider_model_name": "openai/gpt-4",
            ...     "max_iterations": 10,
            ... })
        """
        # Get the set of valid field names from the dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}

        # Warn about unknown keys
        unknown_keys = set(data.keys()) - valid_fields
        if unknown_keys and warn_unknown:
            warnings.warn(
                f"AgentConfig: Unknown configuration keys will be ignored: "
                f"{', '.join(sorted(unknown_keys))}. "
                f"Valid keys: {', '.join(sorted(valid_fields))}",
                UserWarning,
                stacklevel=2,
            )

        # Filter to valid keys
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        # Validate provider_model_name if present
        if "provider_model_name" in filtered_data:
            validate_model_format(
                filtered_data["provider_model_name"],
                field="provider_model_name",
            )

        # Validate reasoning_strategy if present
        if "reasoning_strategy" in filtered_data:
            filtered_data["reasoning_strategy"] = validate_reasoning_strategy(
                filtered_data["reasoning_strategy"],
                field="reasoning_strategy",
            )

        return cls(**filtered_data)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this AgentConfig to a dictionary.

        This method serializes all configuration fields to a dictionary
        that can be used for persistence, logging, or recreating the config.

        Returns:
            A dictionary containing all configuration values.

        Example:
            >>> config = AgentConfig(
            ...     agent_name="MyAgent",
            ...     provider_model_name="openai/gpt-4"
            ... )
            >>> data = config.to_dict()
            >>> data["agent_name"]
            'MyAgent'
        """
        return asdict(self)

    def with_updates(self, **kwargs: Any) -> "AgentConfig":
        """
        Create a new AgentConfig with updated values.

        Since AgentConfig is frozen (immutable), this method creates
        a new instance with the specified fields updated.

        Args:
            **kwargs: Field names and their new values.

        Returns:
            A new AgentConfig instance with the updated values.

        Raises:
            TypeError: If an unknown field name is provided.

        Example:
            >>> config = AgentConfig(
            ...     agent_name="MyAgent",
            ...     provider_model_name="openai/gpt-4"
            ... )
            >>> updated = config.with_updates(max_iterations=20)
            >>> updated.max_iterations
            20
        """
        current = self.to_dict()
        current.update(kwargs)
        return AgentConfig.from_dict(current)

    def __repr__(self) -> str:
        """Return a detailed string representation of the config."""
        return (
            f"AgentConfig("
            f"agent_name={self.agent_name!r}, "
            f"provider_model_name={self.provider_model_name!r}, "
            f"tool_use_enabled={self.tool_use_enabled}, "
            f"max_iterations={self.max_iterations}, "
            f"reasoning_strategy={self.reasoning_strategy!r}"
            f")"
        )
