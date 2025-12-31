"""
Configuration validation utilities.

This module provides validation functions for configuration values,
with helpful error messages that list valid options.
"""

from typing import List, Optional, Set


class ConfigurationValidationError(ValueError):
    """
    Exception raised when a configuration value is invalid.

    Provides detailed error messages with suggestions for valid values.
    """

    def __init__(
        self,
        message: str,
        field: str,
        invalid_value: str,
        valid_options: Optional[List[str]] = None,
    ):
        self.field = field
        self.invalid_value = invalid_value
        self.valid_options = valid_options

        full_message = f"Configuration error for '{field}': {message}"
        if valid_options:
            full_message += f"\n  Received: '{invalid_value}'"
            full_message += f"\n  Valid options: {', '.join(sorted(valid_options))}"
        super().__init__(full_message)


# Known valid providers (must match the actual provider implementations)
VALID_PROVIDERS: Set[str] = {
    "anthropic",
    "openai",
    "ollama",
    "groq",
    "google",
    "mock",  # Used for testing
}

# Known valid reasoning strategies (must match ReasoningStrategies enum)
VALID_REASONING_STRATEGIES: Set[str] = {
    "reactive",
    "reflect_decide_act",
    "plan_execute_reflect",
    "self_ask",
    "goal_action_feedback",
    "adaptive",
}

# Known valid log levels
VALID_LOG_LEVELS: Set[str] = {
    "debug",
    "info",
    "warning",
    "error",
    "critical",
}

# Known valid context pruning strategies
VALID_CONTEXT_PRUNING_STRATEGIES: Set[str] = {
    "conservative",
    "balanced",
    "aggressive",
}

# Known valid tool use policies
VALID_TOOL_USE_POLICIES: Set[str] = {
    "always",
    "required_only",
    "adaptive",
    "never",
}


def validate_provider(provider: str, field: str = "provider") -> str:
    """
    Validate a provider name.

    Args:
        provider: The provider name to validate
        field: Field name for error messages

    Returns:
        The validated provider name (lowercased)

    Raises:
        ConfigurationValidationError: If provider is invalid
    """
    provider_lower = provider.lower()
    if provider_lower not in VALID_PROVIDERS:
        raise ConfigurationValidationError(
            f"Unknown provider '{provider}'",
            field=field,
            invalid_value=provider,
            valid_options=list(VALID_PROVIDERS),
        )
    return provider_lower


def validate_reasoning_strategy(strategy: str, field: str = "reasoning_strategy") -> str:
    """
    Validate a reasoning strategy name.

    Args:
        strategy: The strategy name to validate
        field: Field name for error messages

    Returns:
        The validated strategy name (lowercased)

    Raises:
        ConfigurationValidationError: If strategy is invalid
    """
    strategy_lower = strategy.lower()
    if strategy_lower not in VALID_REASONING_STRATEGIES:
        raise ConfigurationValidationError(
            f"Unknown reasoning strategy '{strategy}'",
            field=field,
            invalid_value=strategy,
            valid_options=list(VALID_REASONING_STRATEGIES),
        )
    return strategy_lower


def validate_log_level(level: str, field: str = "log_level") -> str:
    """
    Validate a log level.

    Args:
        level: The log level to validate
        field: Field name for error messages

    Returns:
        The validated log level (lowercased)

    Raises:
        ConfigurationValidationError: If log level is invalid
    """
    level_lower = level.lower()
    if level_lower not in VALID_LOG_LEVELS:
        raise ConfigurationValidationError(
            f"Unknown log level '{level}'",
            field=field,
            invalid_value=level,
            valid_options=list(VALID_LOG_LEVELS),
        )
    return level_lower


def validate_model_format(model_spec: str, field: str = "provider_model_name") -> str:
    """
    Validate a model specification format (provider:model).

    Args:
        model_spec: The model specification to validate (e.g., "anthropic:claude-3-sonnet")
        field: Field name for error messages

    Returns:
        The validated model specification

    Raises:
        ConfigurationValidationError: If format is invalid or provider is unknown
    """
    if ":" not in model_spec:
        raise ConfigurationValidationError(
            f"Invalid model format. Expected 'provider:model' format "
            f"(e.g., 'anthropic:claude-3-sonnet', 'ollama:llama3:8b')",
            field=field,
            invalid_value=model_spec,
            valid_options=[f"{p}:<model_name>" for p in sorted(VALID_PROVIDERS)],
        )

    provider = model_spec.split(":")[0].lower()
    if provider not in VALID_PROVIDERS:
        raise ConfigurationValidationError(
            f"Unknown provider '{provider}' in model specification",
            field=field,
            invalid_value=model_spec,
            valid_options=list(VALID_PROVIDERS),
        )

    return model_spec


def validate_context_pruning_strategy(
    strategy: str, field: str = "context_pruning_strategy"
) -> str:
    """
    Validate a context pruning strategy.

    Args:
        strategy: The strategy to validate
        field: Field name for error messages

    Returns:
        The validated strategy (lowercased)

    Raises:
        ConfigurationValidationError: If strategy is invalid
    """
    strategy_lower = strategy.lower()
    if strategy_lower not in VALID_CONTEXT_PRUNING_STRATEGIES:
        raise ConfigurationValidationError(
            f"Unknown context pruning strategy '{strategy}'",
            field=field,
            invalid_value=strategy,
            valid_options=list(VALID_CONTEXT_PRUNING_STRATEGIES),
        )
    return strategy_lower


def validate_tool_use_policy(policy: str, field: str = "tool_use_policy") -> str:
    """
    Validate a tool use policy.

    Args:
        policy: The policy to validate
        field: Field name for error messages

    Returns:
        The validated policy (lowercased)

    Raises:
        ConfigurationValidationError: If policy is invalid
    """
    policy_lower = policy.lower()
    if policy_lower not in VALID_TOOL_USE_POLICIES:
        raise ConfigurationValidationError(
            f"Unknown tool use policy '{policy}'",
            field=field,
            invalid_value=policy,
            valid_options=list(VALID_TOOL_USE_POLICIES),
        )
    return policy_lower
