"""
Mock context implementation for testing.

Provides a MockContextProtocol class that satisfies the ContextProtocol
interface while allowing full control over behavior through unittest.mock.
"""

from unittest.mock import Mock, MagicMock
from typing import Any, Optional

from reactive_agents.core.context.context_protocol import ContextProtocol


class MockContextProtocol:
    """
    A mock implementation of ContextProtocol that satisfies Pydantic's
    runtime_checkable Protocol validation while allowing test customization.

    This class implements all required attributes and methods of ContextProtocol,
    making it usable as a drop-in replacement for AgentContext in tests.
    """

    def __init__(
        self,
        agent_name: str = "TestAgent",
        use_memory_enabled: bool = True,
        collect_metrics_enabled: bool = True,
        enable_state_observation: bool = True,
        **kwargs
    ):
        # Configuration mock
        self.config = Mock()
        self.config.agent_name = agent_name
        self.config.use_memory_enabled = use_memory_enabled
        self.config.collect_metrics_enabled = collect_metrics_enabled
        self.config.enable_state_observation = enable_state_observation

        # Store direct attributes for property access
        self._agent_name = agent_name
        self._use_memory_enabled = use_memory_enabled
        self._collect_metrics_enabled = collect_metrics_enabled
        self._enable_state_observation = enable_state_observation

        # Core components - loggers
        self.agent_logger = _create_mock_logger()
        self.tool_logger = _create_mock_logger()
        self.result_logger = _create_mock_logger()

        # Model provider mock
        self.model_provider = Mock()
        self.model_provider.name = "mock_provider"
        self.model_provider.model = "mock_model"

        # Optional components
        self.event_bus = kwargs.get("event_bus", Mock())
        self.mcp_client = kwargs.get("mcp_client", None)

        # Additional context attributes commonly used in tests
        self.session = Mock()
        self.session.session_id = "test-session-123"
        self.session.successful_tools = set()
        self.session.failed_tools = set()
        self.session.tool_calls = []
        self.session.errors = []
        self.session.thinking_log = []

        self.metrics_manager = Mock()
        self.metrics_manager.update_tool_metrics = Mock()
        self.metrics_manager.get_metrics = Mock(return_value={})

        # Additional manager components (optional in ContextProtocol)
        self.tool_manager = kwargs.get("tool_manager", None)
        self.memory_manager = kwargs.get("memory_manager", None)
        self.context_manager = kwargs.get("context_manager", None)

        self.reflection_manager = kwargs.get("reflection_manager", None)

        # Tool-related attributes
        self.enable_caching = kwargs.get("enable_caching", True)
        self.cache_ttl = kwargs.get("cache_ttl", 3600)
        self.confirmation_callback = kwargs.get("confirmation_callback", None)
        self.confirmation_config = kwargs.get("confirmation_config", None)
        self.tool_use_enabled = kwargs.get("tool_use_enabled", True)
        self.tools = kwargs.get("tools", [])

        # emit_event should be a Mock for test assertions
        self.emit_event = Mock()

        # Allow setting additional arbitrary attributes
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    @property
    def agent_name(self) -> str:
        return self._agent_name

    @agent_name.setter
    def agent_name(self, value: str):
        self._agent_name = value

    @property
    def use_memory_enabled(self) -> bool:
        return self._use_memory_enabled

    @use_memory_enabled.setter
    def use_memory_enabled(self, value: bool):
        self._use_memory_enabled = value

    @property
    def collect_metrics_enabled(self) -> bool:
        return self._collect_metrics_enabled

    @property
    def enable_state_observation(self) -> bool:
        return self._enable_state_observation


def _create_mock_logger():
    """Create a mock logger with all common methods."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    logger.exception = Mock()
    return logger


def create_mock_context(**kwargs) -> MockContextProtocol:
    """
    Factory function to create a MockContextProtocol with customized settings.

    Args:
        **kwargs: Override any default MockContextProtocol settings

    Returns:
        MockContextProtocol instance configured for testing

    Example:
        context = create_mock_context(
            agent_name="CustomAgent",
            use_memory_enabled=False,
            event_bus=my_custom_event_bus
        )
    """
    return MockContextProtocol(**kwargs)


# Verify that MockContextProtocol satisfies the Protocol at module load time
assert isinstance(MockContextProtocol(), ContextProtocol), \
    "MockContextProtocol does not satisfy ContextProtocol interface"
