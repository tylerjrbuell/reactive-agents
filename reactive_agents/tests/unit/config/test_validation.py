"""Tests for configuration validation utilities."""

import pytest
from reactive_agents.config.validation import (
    ConfigurationValidationError,
    validate_provider,
    validate_reasoning_strategy,
    validate_log_level,
    validate_model_format,
    validate_context_pruning_strategy,
    validate_tool_use_policy,
)


class TestValidateProvider:
    """Tests for provider validation."""

    def test_valid_providers(self):
        """Test that valid providers are accepted."""
        valid_providers = ["anthropic", "openai", "ollama", "groq", "google"]
        for provider in valid_providers:
            result = validate_provider(provider)
            assert result == provider.lower()

    def test_case_insensitive(self):
        """Test that provider validation is case-insensitive."""
        assert validate_provider("ANTHROPIC") == "anthropic"
        assert validate_provider("OpenAI") == "openai"

    def test_invalid_provider_raises_error(self):
        """Test that invalid providers raise ConfigurationValidationError."""
        with pytest.raises(ConfigurationValidationError) as exc_info:
            validate_provider("invalid_provider")

        error = exc_info.value
        assert error.field == "provider"
        assert error.invalid_value == "invalid_provider"
        assert "anthropic" in error.valid_options


class TestValidateReasoningStrategy:
    """Tests for reasoning strategy validation."""

    def test_valid_strategies(self):
        """Test that valid strategies are accepted."""
        valid_strategies = [
            "reactive",
            "reflect_decide_act",
            "plan_execute_reflect",
            "self_ask",
            "goal_action_feedback",
            "adaptive",
        ]
        for strategy in valid_strategies:
            result = validate_reasoning_strategy(strategy)
            assert result == strategy.lower()

    def test_case_insensitive(self):
        """Test that strategy validation is case-insensitive."""
        assert validate_reasoning_strategy("REACTIVE") == "reactive"
        assert validate_reasoning_strategy("Adaptive") == "adaptive"

    def test_invalid_strategy_raises_error(self):
        """Test that invalid strategies raise ConfigurationValidationError."""
        with pytest.raises(ConfigurationValidationError) as exc_info:
            validate_reasoning_strategy("invalid_strategy")

        error = exc_info.value
        assert error.field == "reasoning_strategy"
        assert "reactive" in error.valid_options


class TestValidateLogLevel:
    """Tests for log level validation."""

    def test_valid_log_levels(self):
        """Test that valid log levels are accepted."""
        valid_levels = ["debug", "info", "warning", "error", "critical"]
        for level in valid_levels:
            result = validate_log_level(level)
            assert result == level.lower()

    def test_case_insensitive(self):
        """Test that log level validation is case-insensitive."""
        assert validate_log_level("DEBUG") == "debug"
        assert validate_log_level("Info") == "info"

    def test_invalid_level_raises_error(self):
        """Test that invalid log levels raise ConfigurationValidationError."""
        with pytest.raises(ConfigurationValidationError) as exc_info:
            validate_log_level("verbose")

        error = exc_info.value
        assert error.field == "log_level"


class TestValidateModelFormat:
    """Tests for model format validation."""

    def test_valid_model_formats(self):
        """Test that valid model formats are accepted."""
        valid_formats = [
            "anthropic:claude-3-sonnet",
            "openai:gpt-4",
            "ollama:llama3:8b",  # Model names can have colons
            "groq:mixtral-8x7b-32768",
            "google:gemini-pro",
        ]
        for fmt in valid_formats:
            result = validate_model_format(fmt)
            assert result == fmt

    def test_missing_colon_raises_error(self):
        """Test that models without provider:model format raise error."""
        with pytest.raises(ConfigurationValidationError) as exc_info:
            validate_model_format("gpt-4")

        error = exc_info.value
        assert "provider:model" in str(error)

    def test_invalid_provider_raises_error(self):
        """Test that unknown providers raise error."""
        with pytest.raises(ConfigurationValidationError) as exc_info:
            validate_model_format("unknown:model")

        error = exc_info.value
        assert "unknown" in error.invalid_value


class TestValidateContextPruningStrategy:
    """Tests for context pruning strategy validation."""

    def test_valid_strategies(self):
        """Test that valid context pruning strategies are accepted."""
        for strategy in ["conservative", "balanced", "aggressive"]:
            result = validate_context_pruning_strategy(strategy)
            assert result == strategy

    def test_invalid_strategy_raises_error(self):
        """Test that invalid strategies raise error."""
        with pytest.raises(ConfigurationValidationError):
            validate_context_pruning_strategy("invalid")


class TestValidateToolUsePolicy:
    """Tests for tool use policy validation."""

    def test_valid_policies(self):
        """Test that valid tool use policies are accepted."""
        for policy in ["always", "required_only", "adaptive", "never"]:
            result = validate_tool_use_policy(policy)
            assert result == policy

    def test_invalid_policy_raises_error(self):
        """Test that invalid policies raise error."""
        with pytest.raises(ConfigurationValidationError):
            validate_tool_use_policy("sometimes")


class TestConfigurationValidationError:
    """Tests for the ConfigurationValidationError class."""

    def test_error_message_format(self):
        """Test that error messages are properly formatted."""
        error = ConfigurationValidationError(
            message="Unknown value",
            field="test_field",
            invalid_value="bad_value",
            valid_options=["option1", "option2"],
        )

        error_str = str(error)
        assert "test_field" in error_str
        assert "Unknown value" in error_str
        assert "bad_value" in error_str
        assert "option1" in error_str
        assert "option2" in error_str

    def test_error_without_valid_options(self):
        """Test error message when valid_options is not provided."""
        error = ConfigurationValidationError(
            message="Something went wrong",
            field="test_field",
            invalid_value="bad_value",
        )

        error_str = str(error)
        assert "test_field" in error_str
        assert "Something went wrong" in error_str
