"""
Tests for ToolManager.

Tests the tool management functionality including tool discovery, execution,
caching, validation, integration with SOLID components, and parallel execution.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from reactive_agents.core.tools.tool_manager import ToolManager, ParallelToolResult
from reactive_agents.core.tools.base import Tool
from reactive_agents.core.tools.abstractions import ToolProtocol, MCPToolWrapper
from reactive_agents.core.tools.tool_guard import ToolGuard
from reactive_agents.core.tools.tool_cache import ToolCache
from reactive_agents.core.tools.tool_confirmation import ToolConfirmation
from reactive_agents.core.tools.tool_validator import ToolValidator
from reactive_agents.core.tools.tool_executor import ToolExecutor
from reactive_agents.core.tools.default import FinalAnswerTool
from reactive_agents.core.types.event_types import AgentStateEvent
from reactive_agents.tests.fixtures import create_mock_context


class TestToolManager:
    """Test cases for ToolManager."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock agent context."""
        return create_mock_context(
            agent_name="TestAgent",
            enable_caching=True,
            cache_ttl=3600,
            confirmation_callback=None,
            confirmation_config=None,
            tool_use_enabled=True,
            collect_metrics_enabled=True,
            tools=[],
            mcp_client=None,
        )

    @pytest.fixture
    def mock_tool(self):
        """Create a mock tool."""
        tool = Mock(spec=ToolProtocol)
        tool.name = "test_tool"
        tool.tool_definition = {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string", "description": "First parameter"}
                    },
                    "required": ["param1"],
                },
            },
        }
        return tool

    @pytest.fixture
    def tool_manager(self, mock_context):
        """Create a tool manager instance with mocked dependencies."""
        # Mock component instances first
        mock_guard = Mock(spec=ToolGuard)
        mock_guard.add_default_guards = Mock()
        mock_guard.can_use = Mock(return_value=True)
        mock_guard.needs_confirmation = Mock(return_value=False)
        mock_guard.record_use = Mock()

        mock_cache = Mock(spec=ToolCache)
        mock_cache.enabled = True
        mock_cache.ttl = 3600
        mock_cache.hits = 0
        mock_cache.misses = 0
        mock_cache.generate_cache_key = Mock(return_value="test_key")
        mock_cache.get = Mock(return_value=None)
        mock_cache.put = Mock()

        mock_confirmation = Mock(spec=ToolConfirmation)
        mock_confirmation.tool_requires_confirmation = Mock(return_value=False)
        mock_confirmation.request_confirmation = AsyncMock(return_value=(True, None))
        mock_confirmation.inject_user_feedback = Mock()

        mock_validator = Mock(spec=ToolValidator)
        mock_validator.validate_tool_result_usage = Mock(
            return_value={"valid": True, "warnings": [], "suggestions": []}
        )
        mock_validator.store_search_data = Mock()

        mock_executor = Mock(spec=ToolExecutor)

        # Make parse_tool_arguments dynamic based on the actual call
        def parse_tool_arguments_side_effect(tool_call):
            # Check for invalid format
            if "function" not in tool_call:
                raise ValueError("Tool call missing function name")
            function = tool_call.get("function", {})
            name = function.get("name", "test_tool")
            if not name:
                raise ValueError("Tool call missing function name")
            args = function.get("arguments", {"param1": "value1"})
            return (name, args)

        mock_executor.parse_tool_arguments = Mock(
            side_effect=parse_tool_arguments_side_effect
        )
        mock_executor.execute_tool = AsyncMock(
            return_value="Tool executed successfully"
        )
        mock_executor.add_reasoning_to_context = Mock()
        mock_executor._generate_tool_summary = AsyncMock(return_value="Tool summary")

        # Create ToolManager normally, then replace components after initialization
        manager = ToolManager(context=mock_context)

        # Replace the actual components with our mocks
        manager.guard = mock_guard
        manager.cache = mock_cache
        manager.confirmation = mock_confirmation
        manager.validator = mock_validator
        manager.executor = mock_executor

        # Store mocks for test access
        manager._mock_guard = mock_guard
        manager._mock_cache = mock_cache
        manager._mock_confirmation = mock_confirmation
        manager._mock_validator = mock_validator
        manager._mock_executor = mock_executor

        return manager

    def test_initialization(self, tool_manager, mock_context):
        """Test tool manager initialization."""
        assert tool_manager.context == mock_context
        assert tool_manager.tools == []
        assert tool_manager.tool_signatures == []
        assert tool_manager.tool_history == []

        # Verify components were initialized
        assert tool_manager.guard is not None
        assert tool_manager.cache is not None
        assert tool_manager.confirmation is not None
        assert tool_manager.validator is not None
        assert tool_manager.executor is not None

        # Verify that our mocks are properly set up
        assert hasattr(tool_manager.guard, "add_default_guards")
        assert hasattr(tool_manager.guard, "can_use")
        assert hasattr(tool_manager.guard, "needs_confirmation")
        assert hasattr(tool_manager.guard, "record_use")

    def test_properties(self, tool_manager, mock_context):
        """Test tool manager properties."""
        assert tool_manager.agent_logger == mock_context.agent_logger
        assert tool_manager.tool_logger == mock_context.tool_logger
        assert tool_manager.model_provider == mock_context.model_provider

        # Test cache properties
        assert tool_manager.cache_hits == 0
        assert tool_manager.cache_misses == 0
        assert tool_manager.enable_caching is True
        assert tool_manager.cache_ttl == 3600

    @pytest.mark.asyncio
    async def test_initialize_tools_empty(self, tool_manager):
        """Test tool initialization with no tools."""
        from reactive_agents.core.tools.system_tools_registry import SystemToolConfig

        with patch.object(tool_manager, "_generate_tool_signatures"), patch(
            "reactive_agents.core.tools.default.FinalAnswerTool"
        ) as mock_final_answer, patch(
            "reactive_agents.core.tools.tool_manager.get_enabled_system_tools"
        ) as mock_get_system_tools:

            mock_tool = Mock()
            mock_tool.name = "final_answer"
            mock_final_answer.return_value = mock_tool

            # Mock system tools registry to return only final_answer
            mock_config = SystemToolConfig(
                tool_class=mock_final_answer,
                name="final_answer",
                enabled_by_default=True,
                description="Provides final answer",
                category="core",
            )
            mock_get_system_tools.return_value = [mock_config]

            await tool_manager._initialize_tools()

            # Should have injected final_answer tool
            assert len(tool_manager.tools) == 1
            assert tool_manager.tools[0].name == "final_answer"

    @pytest.mark.asyncio
    async def test_initialize_tools_with_mcp(self, tool_manager, mock_context):
        """Test tool initialization with MCP tools."""
        # Mock MCP client with tools
        mock_mcp_client = Mock()
        mock_tool1 = Mock()
        mock_tool1.name = "mcp_tool1"
        mock_tool2 = Mock()
        mock_tool2.name = "mcp_tool2"
        mock_mcp_tools = [mock_tool1, mock_tool2]
        mock_mcp_client.tools = mock_mcp_tools
        mock_mcp_client.tool_signatures = [
            {"type": "function", "function": {"name": "mcp_tool1"}}
        ]
        mock_mcp_client.server_tools = {"server1": mock_mcp_tools}
        # get_tools is an async method, so use AsyncMock
        mock_mcp_client.get_tools = AsyncMock(return_value=None)
        mock_context.mcp_client = mock_mcp_client

        with patch.object(tool_manager, "_generate_tool_signatures"), patch(
            "reactive_agents.core.tools.tool_manager.MCPToolWrapper"
        ) as mock_wrapper, patch(
            "reactive_agents.core.tools.default.FinalAnswerTool"
        ) as mock_final_answer, patch(
            "reactive_agents.core.tools.tool_manager.get_enabled_system_tools"
        ) as mock_get_system_tools:

            def wrapper_side_effect(tool, client):
                wrapped = Mock()
                wrapped.name = f"wrapped_{tool.name}"
                return wrapped

            mock_wrapper.side_effect = wrapper_side_effect

            mock_final_tool = Mock()
            mock_final_tool.name = "final_answer"
            mock_final_answer.return_value = mock_final_tool

            # Mock system tools registry to return only final_answer
            from reactive_agents.core.tools.system_tools_registry import (
                SystemToolConfig,
            )

            mock_config = SystemToolConfig(
                tool_class=mock_final_answer,
                name="final_answer",
                enabled_by_default=True,
                description="Provides final answer",
                category="core",
            )
            mock_get_system_tools.return_value = [mock_config]

            await tool_manager._initialize_tools()

            # Should have MCP tools + final_answer tool
            assert len(tool_manager.tools) == 3
            assert len(tool_manager.tool_signatures) == 1

    @pytest.mark.asyncio
    async def test_initialize_tools_with_custom_tools(
        self, tool_manager, mock_context, mock_tool
    ):
        """Test tool initialization with custom tools."""
        mock_context.tools = [mock_tool]

        with patch.object(tool_manager, "_generate_tool_signatures"), patch(
            "reactive_agents.core.tools.default.FinalAnswerTool"
        ) as mock_final_answer, patch(
            "reactive_agents.core.tools.tool_manager.get_enabled_system_tools"
        ) as mock_get_system_tools:

            mock_final_tool = Mock()
            mock_final_tool.name = "final_answer"
            mock_final_answer.return_value = mock_final_tool

            # Mock system tools registry to return only final_answer
            from reactive_agents.core.tools.system_tools_registry import (
                SystemToolConfig,
            )

            mock_config = SystemToolConfig(
                tool_class=mock_final_answer,
                name="final_answer",
                enabled_by_default=True,
                description="Provides final answer",
                category="core",
            )
            mock_get_system_tools.return_value = [mock_config]

            await tool_manager._initialize_tools()

            # Should have custom tool + final_answer tool
            assert len(tool_manager.tools) == 2
            assert mock_tool in tool_manager.tools

    def test_get_tool(self, tool_manager, mock_tool):
        """Test getting a tool by name."""
        tool_manager.tools = [mock_tool]

        # Test finding existing tool
        found_tool = tool_manager.get_tool("test_tool")
        assert found_tool == mock_tool

        # Test tool not found
        not_found = tool_manager.get_tool("nonexistent_tool")
        assert not_found is None

    @pytest.mark.asyncio
    async def test_use_tool_success(self, tool_manager, mock_tool):
        """Test successful tool execution."""
        tool_manager.tools = [mock_tool]

        tool_call = {
            "function": {"name": "test_tool", "arguments": {"param1": "value1"}}
        }

        with patch.object(
            tool_manager, "_actually_call_tool", return_value="Success"
        ) as mock_call:
            result = await tool_manager.use_tool(tool_call)

            assert result == "Success"
            mock_call.assert_called_once_with(tool_call)
            tool_manager._mock_guard.record_use.assert_called_once_with("test_tool")

    @pytest.mark.asyncio
    async def test_use_tool_rate_limited(self, tool_manager):
        """Test tool execution when rate limited."""
        tool_call = {"function": {"name": "test_tool", "arguments": {}}}

        # Mock guard to deny usage
        tool_manager._mock_guard.can_use.return_value = False

        result = await tool_manager.use_tool(tool_call)

        assert "rate-limited" in result
        tool_manager._mock_guard.record_use.assert_not_called()

    @pytest.mark.asyncio
    async def test_use_tool_confirmation_required(self, tool_manager, mock_tool):
        """Test tool execution with confirmation required."""
        tool_manager.tools = [mock_tool]

        tool_call = {
            "function": {"name": "test_tool", "arguments": {"param1": "value1"}}
        }

        # Mock guard to require confirmation
        tool_manager._mock_guard.needs_confirmation.return_value = True

        with patch.object(
            tool_manager, "_actually_call_tool", return_value="Success"
        ) as mock_call:
            result = await tool_manager.use_tool(tool_call)

            assert result == "Success"
            tool_manager._mock_confirmation.request_confirmation.assert_called_once()

    @pytest.mark.asyncio
    async def test_use_tool_confirmation_denied(self, tool_manager):
        """Test tool execution when confirmation is denied."""
        tool_call = {
            "function": {"name": "test_tool", "arguments": {"param1": "value1"}}
        }

        # Mock guard to require confirmation and confirmation to be denied
        tool_manager._mock_guard.needs_confirmation.return_value = True
        tool_manager._mock_confirmation.request_confirmation.return_value = (
            False,
            "User declined",
        )

        result = await tool_manager.use_tool(tool_call)

        assert "cancelled" in result
        assert "User declined" in result

    @pytest.mark.asyncio
    async def test_actually_call_tool_success(
        self, tool_manager, mock_tool, mock_context
    ):
        """Test successful tool execution through _actually_call_tool."""
        tool_manager.tools = [mock_tool]

        tool_call = {
            "function": {"name": "test_tool", "arguments": {"param1": "value1"}}
        }

        result = await tool_manager._actually_call_tool(tool_call)

        assert result == "Tool executed successfully"

        # Verify events were emitted
        mock_context.emit_event.assert_any_call(
            AgentStateEvent.TOOL_CALLED,
            {"tool_name": "test_tool", "parameters": {"param1": "value1"}},
        )

    @pytest.mark.asyncio
    async def test_actually_call_tool_not_found(self, tool_manager, mock_context):
        """Test tool execution when tool is not found."""
        tool_call = {"function": {"name": "nonexistent_tool", "arguments": {}}}

        result = await tool_manager._actually_call_tool(tool_call)

        assert "not found" in result

        # Verify TOOL_FAILED event was emitted
        mock_context.emit_event.assert_any_call(
            AgentStateEvent.TOOL_FAILED,
            {"tool_name": "nonexistent_tool", "parameters": {}, "error": result},
        )

    @pytest.mark.asyncio
    async def test_actually_call_tool_cached_result(self, tool_manager, mock_tool):
        """Test tool execution with cached result."""
        tool_manager.tools = [mock_tool]

        # Mock cache to return cached result
        tool_manager._mock_cache.get.return_value = "Cached result"

        tool_call = {
            "function": {"name": "test_tool", "arguments": {"param1": "value1"}}
        }

        result = await tool_manager._actually_call_tool(tool_call)

        assert result == "Cached result"
        tool_manager._mock_executor.execute_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_actually_call_tool_with_confirmation(self, tool_manager, mock_tool):
        """Test tool execution with confirmation flow."""
        tool_manager.tools = [mock_tool]

        # Mock confirmation to be required
        tool_manager._mock_confirmation.tool_requires_confirmation.return_value = True

        tool_call = {
            "function": {"name": "test_tool", "arguments": {"param1": "value1"}}
        }

        result = await tool_manager._actually_call_tool(tool_call)

        assert result == "Tool executed successfully"
        tool_manager._mock_confirmation.request_confirmation.assert_called_once()

    @pytest.mark.asyncio
    async def test_actually_call_tool_confirmation_denied(
        self, tool_manager, mock_tool
    ):
        """Test tool execution when confirmation is denied."""
        tool_manager.tools = [mock_tool]

        # Mock confirmation to be required and denied
        tool_manager._mock_confirmation.tool_requires_confirmation.return_value = True
        tool_manager._mock_confirmation.request_confirmation.return_value = (
            False,
            "User feedback",
        )

        tool_call = {
            "function": {"name": "test_tool", "arguments": {"param1": "value1"}}
        }

        result = await tool_manager._actually_call_tool(tool_call)

        assert "cancelled" in result
        assert "User feedback" in result
        tool_manager._mock_confirmation.inject_user_feedback.assert_called_once()

    def test_get_tool_description(self, tool_manager, mock_tool):
        """Test getting tool description."""
        description = tool_manager._get_tool_description(mock_tool)
        assert description == "A test tool"

    def test_emit_tool_completion_events(self, tool_manager, mock_context):
        """Test emitting tool completion events."""
        tool_manager._emit_tool_completion_events(
            "test_tool", {"param1": "value1"}, "result", 0.1
        )

        # Verify TOOL_COMPLETED event was emitted
        mock_context.emit_event.assert_any_call(
            AgentStateEvent.TOOL_COMPLETED,
            {
                "tool_name": "test_tool",
                "parameters": {"param1": "value1"},
                "result": "result",
                "execution_time": 0.1,
            },
        )

    def test_emit_tool_completion_events_final_answer(self, tool_manager, mock_context):
        """Test emitting events for final_answer tool."""
        tool_manager._emit_tool_completion_events(
            "final_answer", {"answer": "Final answer"}, "Final answer", 0.1
        )

        # Verify FINAL_ANSWER_SET event was emitted
        mock_context.emit_event.assert_any_call(
            AgentStateEvent.FINAL_ANSWER_SET,
            {
                "tool_name": "final_answer",
                "answer": "Final answer",
                "parameters": {"answer": "Final answer"},
            },
        )

    @pytest.mark.asyncio
    async def test_generate_and_log_summary(self, tool_manager):
        """Test generating tool summary."""
        summary = await tool_manager._generate_and_log_summary(
            "test_tool", {"param1": "value1"}, "result"
        )

        assert summary == "Tool summary"
        tool_manager._mock_executor._generate_tool_summary.assert_called_once_with(
            "test_tool", {"param1": "value1"}, "result"
        )

    def test_add_to_history_success(self, tool_manager, mock_context):
        """Test adding successful tool execution to history."""
        tool_manager._add_to_history(
            "test_tool", {"param1": "value1"}, "result", "summary", 0.1
        )

        assert len(tool_manager.tool_history) == 1
        entry = tool_manager.tool_history[0]
        assert entry["name"] == "test_tool"
        assert entry["params"] == {"param1": "value1"}
        assert entry["result"] == "result"
        assert entry["summary"] == "summary"
        assert entry["execution_time"] == 0.1
        assert entry["cached"] is False
        assert entry["cancelled"] is False
        assert entry["error"] is False

        # Verify tool was added to successful tools
        assert "test_tool" in mock_context.session.successful_tools

    def test_add_to_history_error(self, tool_manager, mock_context):
        """Test adding failed tool execution to history."""
        tool_manager._add_to_history("test_tool", {}, "Error occurred", error=True)

        assert len(tool_manager.tool_history) == 1
        entry = tool_manager.tool_history[0]
        assert entry["error"] is True

        # Verify tool was NOT added to successful tools
        assert "test_tool" not in mock_context.session.successful_tools

    def test_add_to_history_with_metrics(self, tool_manager, mock_context):
        """Test adding to history updates metrics."""
        tool_manager._add_to_history("test_tool", {}, "result", execution_time=0.1)

        # Verify metrics were updated
        mock_context.metrics_manager.update_tool_metrics.assert_called_once()
        mock_context.emit_event.assert_any_call(
            AgentStateEvent.METRICS_UPDATED, {"metrics": {}}
        )

    def test_generate_tool_signatures(self, tool_manager, mock_tool):
        """Test generating tool signatures."""
        tool_manager.tools = [mock_tool]

        tool_manager._generate_tool_signatures()

        assert len(tool_manager.tool_signatures) == 1
        assert mock_tool.tool_definition in tool_manager.tool_signatures

    def test_get_available_tools(self, tool_manager, mock_tool):
        """Test getting available tools."""
        tool_manager.tools = [mock_tool]

        tools = tool_manager.get_available_tools()
        assert tools == [mock_tool]

    def test_get_available_tool_names(self, tool_manager, mock_tool):
        """Test getting available tool names."""
        tool_manager.tools = [mock_tool]

        names = tool_manager.get_available_tool_names()
        assert names == {"test_tool"}

    def test_get_last_tool_action(self, tool_manager):
        """Test getting last tool action."""
        # Test with empty history
        assert tool_manager.get_last_tool_action() is None

        # Add entry to history
        tool_manager._add_to_history("test_tool", {}, "result")

        last_action = tool_manager.get_last_tool_action()
        assert last_action is not None
        assert last_action["name"] == "test_tool"

    def test_register_tools(self, tool_manager, mock_context, mock_tool):
        """Test registering tools."""
        # Add tool to context
        mock_context.tools = [mock_tool]

        with patch.object(tool_manager, "_generate_tool_signatures") as mock_gen:
            tool_manager.register_tools()

            assert mock_tool in tool_manager.tools
            mock_gen.assert_called_once()

    def test_register_tools_deduplication(self, tool_manager, mock_context):
        """Test tool registration deduplicates by name."""
        # Create two tools with same name
        tool1 = Mock()
        tool1.name = "duplicate_tool"
        tool2 = Mock()
        tool2.name = "duplicate_tool"

        tool_manager.tools = [tool1]
        mock_context.tools = [tool2]

        with patch.object(tool_manager, "_generate_tool_signatures"):
            tool_manager.register_tools()

            # Should only have one tool with that name
            names = [t.name for t in tool_manager.tools]
            assert names.count("duplicate_tool") == 1

    @pytest.mark.asyncio
    async def test_use_tool_invalid_format(self, tool_manager):
        """Test tool execution with invalid tool call format."""
        invalid_tool_call = {"invalid": "format"}

        result = await tool_manager.use_tool(invalid_tool_call)

        assert result.startswith("Error:")

    def test_load_plugin_tools_success(self, tool_manager):
        """Test loading tools from plugin system."""
        mock_plugin_manager = Mock()
        mock_tool_plugin = Mock()
        mock_plugin_tool = Mock()
        mock_plugin_tool.name = "plugin_tool"
        mock_plugin_tool.use = Mock()
        mock_tool_plugin.get_tools.return_value = {"plugin_tool": mock_plugin_tool}
        mock_plugin_manager.get_plugins_by_type.return_value = {
            "test_plugin": mock_tool_plugin
        }

        with patch(
            "reactive_agents.plugins.plugin_manager.get_plugin_manager",
            return_value=mock_plugin_manager,
        ), patch(
            "reactive_agents.plugins.plugin_manager.PluginType"
        ) as mock_plugin_type, patch(
            "reactive_agents.plugins.plugin_manager.ToolPlugin",
            mock_tool_plugin.__class__,
        ):

            mock_plugin_type.TOOL = "tool"  # Set the enum value

            tool_manager._load_plugin_tools()

            # Verify plugin tools were loaded
            plugin_tool_names = [
                t.name for t in tool_manager.tools if hasattr(t, "name")
            ]
            assert "plugin_tool" in plugin_tool_names

    def test_load_plugin_tools_import_error(self, tool_manager):
        """Test loading plugin tools when plugin system is not available."""
        with patch(
            "reactive_agents.plugins.plugin_manager.get_plugin_manager",
            side_effect=ImportError,
        ):
            # Should not raise exception
            tool_manager._load_plugin_tools()

            # Should log debug message about plugin system not being available
            if tool_manager.tool_logger:
                tool_manager.tool_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_tool_execution_flow_integration(
        self, tool_manager, mock_tool, mock_context
    ):
        """Test complete tool execution flow integration."""
        tool_manager.tools = [mock_tool]

        tool_call = {
            "function": {"name": "test_tool", "arguments": {"param1": "value1"}}
        }

        # Execute tool
        result = await tool_manager.use_tool(tool_call)

        # Verify complete flow
        assert result == "Tool executed successfully"

        # Verify all components were called
        tool_manager._mock_guard.can_use.assert_called_with("test_tool")
        tool_manager._mock_executor.parse_tool_arguments.assert_called()
        tool_manager._mock_executor.execute_tool.assert_called()
        tool_manager._mock_cache.generate_cache_key.assert_called()
        tool_manager._mock_validator.validate_tool_result_usage.assert_called()

        # Verify history was updated
        assert len(tool_manager.tool_history) == 1

        # Verify events were emitted
        mock_context.emit_event.assert_called()


class TestParallelToolExecution:
    """Test cases for parallel tool execution functionality."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock agent context."""
        return create_mock_context(
            agent_name="TestAgent",
            enable_caching=True,
            cache_ttl=3600,
            confirmation_callback=None,
            confirmation_config=None,
            tool_use_enabled=True,
            collect_metrics_enabled=True,
            tools=[],
            mcp_client=None,
        )

    @pytest.fixture
    def mock_tools(self):
        """Create multiple mock tools for parallel testing."""
        tools = []
        for i in range(3):
            tool = Mock(spec=ToolProtocol)
            tool.name = f"tool_{i}"
            tool.tool_definition = {
                "type": "function",
                "function": {
                    "name": f"tool_{i}",
                    "description": f"Test tool {i}",
                    "parameters": {
                        "type": "object",
                        "properties": {"param": {"type": "string"}},
                    },
                },
            }
            tools.append(tool)
        return tools

    @pytest.fixture
    def tool_manager_for_parallel(self, mock_context, mock_tools):
        """Create a tool manager configured for parallel execution tests."""
        # Create mocked components
        mock_guard = Mock(spec=ToolGuard)
        mock_guard.add_default_guards = Mock()
        mock_guard.can_use = Mock(return_value=True)
        mock_guard.needs_confirmation = Mock(return_value=False)
        mock_guard.record_use = Mock()

        mock_cache = Mock(spec=ToolCache)
        mock_cache.enabled = True
        mock_cache.ttl = 3600
        mock_cache.hits = 0
        mock_cache.misses = 0
        mock_cache.generate_cache_key = Mock(
            return_value=None
        )  # Disable caching for tests
        mock_cache.get = Mock(return_value=None)
        mock_cache.put = Mock()

        mock_confirmation = Mock(spec=ToolConfirmation)
        mock_confirmation.tool_requires_confirmation = Mock(return_value=False)
        mock_confirmation.request_confirmation = AsyncMock(return_value=(True, None))

        mock_validator = Mock(spec=ToolValidator)
        mock_validator.validate_tool_result_usage = Mock(
            return_value={"valid": True, "warnings": [], "suggestions": []}
        )
        mock_validator.store_search_data = Mock()

        mock_executor = Mock(spec=ToolExecutor)

        # Dynamic tool execution based on tool name
        async def execute_tool_side_effect(tool, tool_name, params):
            # Simulate some work
            await asyncio.sleep(0.01)
            return f"Result from {tool_name}"

        mock_executor.execute_tool = AsyncMock(side_effect=execute_tool_side_effect)

        def parse_tool_arguments_side_effect(tool_call):
            function = tool_call.get("function", {})
            name = function.get("name", "unknown")
            args = function.get("arguments", {})
            return (name, args)

        mock_executor.parse_tool_arguments = Mock(
            side_effect=parse_tool_arguments_side_effect
        )
        mock_executor.add_reasoning_to_context = Mock()
        mock_executor._generate_tool_summary = AsyncMock(return_value="Tool summary")

        # Create manager
        manager = ToolManager(context=mock_context)
        manager.tools = mock_tools.copy()
        manager.guard = mock_guard
        manager.cache = mock_cache
        manager.confirmation = mock_confirmation
        manager.validator = mock_validator
        manager.executor = mock_executor

        return manager

    def test_parallel_tool_result_dataclass(self):
        """Test ParallelToolResult dataclass creation and attributes."""
        result = ParallelToolResult(
            tool_name="test_tool",
            tool_call_id="call_123",
            result="Success",
            success=True,
            error=None,
            execution_time=0.5,
        )

        assert result.tool_name == "test_tool"
        assert result.tool_call_id == "call_123"
        assert result.result == "Success"
        assert result.success is True
        assert result.error is None
        assert result.execution_time == 0.5

    def test_parallel_tool_result_with_error(self):
        """Test ParallelToolResult with error state."""
        result = ParallelToolResult(
            tool_name="failed_tool",
            tool_call_id="call_456",
            result=None,
            success=False,
            error="Connection timeout",
            execution_time=1.0,
        )

        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.result is None

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_empty_list(self, tool_manager_for_parallel):
        """Test parallel execution with empty tool list."""
        results = await tool_manager_for_parallel.execute_tools_parallel([])

        assert results == []

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_single_tool(self, tool_manager_for_parallel):
        """Test parallel execution with a single tool."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {"name": "tool_0", "arguments": {"param": "value1"}},
            }
        ]

        results = await tool_manager_for_parallel.execute_tools_parallel(tool_calls)

        assert len(results) == 1
        assert results[0].tool_name == "tool_0"
        assert results[0].tool_call_id == "call_1"
        assert results[0].success is True
        assert results[0].execution_time > 0

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_multiple_tools(
        self, tool_manager_for_parallel
    ):
        """Test parallel execution with multiple tools."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {"name": "tool_0", "arguments": {"param": "a"}},
            },
            {
                "id": "call_2",
                "function": {"name": "tool_1", "arguments": {"param": "b"}},
            },
            {
                "id": "call_3",
                "function": {"name": "tool_2", "arguments": {"param": "c"}},
            },
        ]

        results = await tool_manager_for_parallel.execute_tools_parallel(tool_calls)

        assert len(results) == 3
        # Verify order is preserved
        assert results[0].tool_call_id == "call_1"
        assert results[1].tool_call_id == "call_2"
        assert results[2].tool_call_id == "call_3"
        # Verify all succeeded
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_order_preserved(
        self, tool_manager_for_parallel
    ):
        """Test that result order matches input order."""
        tool_calls = [
            {"id": "first", "function": {"name": "tool_2", "arguments": {}}},
            {"id": "second", "function": {"name": "tool_0", "arguments": {}}},
            {"id": "third", "function": {"name": "tool_1", "arguments": {}}},
        ]

        results = await tool_manager_for_parallel.execute_tools_parallel(tool_calls)

        assert results[0].tool_call_id == "first"
        assert results[0].tool_name == "tool_2"
        assert results[1].tool_call_id == "second"
        assert results[1].tool_name == "tool_0"
        assert results[2].tool_call_id == "third"
        assert results[2].tool_name == "tool_1"

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_one_failure_others_continue(
        self, tool_manager_for_parallel, mock_context
    ):
        """Test that one tool failure doesn't affect others."""
        call_count = 0

        async def use_tool_with_failure(self_arg, tool_call):
            nonlocal call_count
            call_count += 1
            tool_name = tool_call.get("function", {}).get("name")
            if tool_name == "tool_1":
                return "Error: Simulated failure"
            return f"Success: {tool_name}"

        tool_calls = [
            {"id": "call_1", "function": {"name": "tool_0", "arguments": {}}},
            {
                "id": "call_2",
                "function": {"name": "tool_1", "arguments": {}},
            },  # This will fail
            {"id": "call_3", "function": {"name": "tool_2", "arguments": {}}},
        ]

        with patch.object(
            type(tool_manager_for_parallel), "use_tool", new=use_tool_with_failure
        ):
            results = await tool_manager_for_parallel.execute_tools_parallel(tool_calls)

        assert len(results) == 3
        assert call_count == 3  # All tools were attempted

        # First tool succeeded
        assert results[0].success is True
        assert "Success" in str(results[0].result)

        # Second tool failed
        assert results[1].success is False
        assert "Error" in str(results[1].error) or "Error" in str(results[1].result)

        # Third tool succeeded despite second failing
        assert results[2].success is True
        assert "Success" in str(results[2].result)

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_exception_handling(
        self, tool_manager_for_parallel, mock_context
    ):
        """Test that exceptions in one tool don't crash others."""

        async def use_tool_with_exception(self_arg, tool_call):
            tool_name = tool_call.get("function", {}).get("name")
            if tool_name == "tool_1":
                raise RuntimeError("Unexpected error")
            return f"Success: {tool_name}"

        tool_calls = [
            {"id": "call_1", "function": {"name": "tool_0", "arguments": {}}},
            {
                "id": "call_2",
                "function": {"name": "tool_1", "arguments": {}},
            },  # Raises exception
            {"id": "call_3", "function": {"name": "tool_2", "arguments": {}}},
        ]

        with patch.object(
            type(tool_manager_for_parallel), "use_tool", new=use_tool_with_exception
        ):
            results = await tool_manager_for_parallel.execute_tools_parallel(tool_calls)

        assert len(results) == 3

        # First tool succeeded
        assert results[0].success is True

        # Second tool failed with exception
        assert results[1].success is False
        assert "Unexpected error" in results[1].error

        # Third tool succeeded
        assert results[2].success is True

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_without_tool_call_id(
        self, tool_manager_for_parallel
    ):
        """Test parallel execution when tool calls don't have IDs."""
        tool_calls = [
            {"function": {"name": "tool_0", "arguments": {"param": "value"}}},
            {"function": {"name": "tool_1", "arguments": {"param": "value"}}},
        ]

        results = await tool_manager_for_parallel.execute_tools_parallel(tool_calls)

        assert len(results) == 2
        assert results[0].tool_call_id is None
        assert results[1].tool_call_id is None
        # Tool names should still be correct
        assert results[0].tool_name == "tool_0"
        assert results[1].tool_name == "tool_1"

    @pytest.mark.asyncio
    async def test_execute_tools_parallel_logs_summary(
        self, tool_manager_for_parallel, mock_context
    ):
        """Test that parallel execution logs summary information."""
        tool_calls = [
            {"id": "call_1", "function": {"name": "tool_0", "arguments": {}}},
            {"id": "call_2", "function": {"name": "tool_1", "arguments": {}}},
        ]

        await tool_manager_for_parallel.execute_tools_parallel(tool_calls)

        # Verify logging was called with summary
        mock_context.tool_logger.info.assert_called()
        calls = [str(call) for call in mock_context.tool_logger.info.call_args_list]
        # Should have start and completion logs
        assert any("parallel" in call.lower() or "Starting" in call for call in calls)

    @pytest.mark.asyncio
    async def test_execute_tool_safe_success(self, tool_manager_for_parallel):
        """Test execute_tool_safe with successful execution."""
        tool_call = {
            "id": "call_1",
            "function": {"name": "tool_0", "arguments": {"param": "test"}},
        }

        result = await tool_manager_for_parallel.execute_tool_safe(tool_call)

        assert isinstance(result, ParallelToolResult)
        assert result.success is True
        assert result.tool_name == "tool_0"
        assert result.tool_call_id == "call_1"
        assert result.execution_time > 0

    @pytest.mark.asyncio
    async def test_execute_tool_safe_failure(self, tool_manager_for_parallel):
        """Test execute_tool_safe with failed execution."""

        async def failing_use_tool(self_arg, tool_call):
            return "Error: Tool failed"

        tool_call = {"id": "call_1", "function": {"name": "tool_0", "arguments": {}}}

        with patch.object(
            type(tool_manager_for_parallel), "use_tool", new=failing_use_tool
        ):
            result = await tool_manager_for_parallel.execute_tool_safe(tool_call)

        assert isinstance(result, ParallelToolResult)
        assert result.success is False
        assert "Error" in str(result.error) or "Error" in str(result.result)

    @pytest.mark.asyncio
    async def test_execute_tool_safe_exception(self, tool_manager_for_parallel):
        """Test execute_tool_safe handles exceptions gracefully."""

        async def exception_use_tool(self_arg, tool_call):
            raise ValueError("Something went wrong")

        tool_call = {"id": "call_1", "function": {"name": "tool_0", "arguments": {}}}

        with patch.object(
            type(tool_manager_for_parallel), "use_tool", new=exception_use_tool
        ):
            result = await tool_manager_for_parallel.execute_tool_safe(tool_call)

        assert isinstance(result, ParallelToolResult)
        assert result.success is False
        assert result.error is not None and "Something went wrong" in result.error

    @pytest.mark.asyncio
    async def test_parallel_execution_respects_guards(
        self, tool_manager_for_parallel, mock_context
    ):
        """Test that parallel execution respects tool guards."""
        # Configure guard to block tool_1
        tool_manager_for_parallel.guard.can_use = Mock(
            side_effect=lambda name: name != "tool_1"
        )

        tool_calls = [
            {"id": "call_1", "function": {"name": "tool_0", "arguments": {}}},
            {
                "id": "call_2",
                "function": {"name": "tool_1", "arguments": {}},
            },  # Should be blocked
            {"id": "call_3", "function": {"name": "tool_2", "arguments": {}}},
        ]

        results = await tool_manager_for_parallel.execute_tools_parallel(tool_calls)

        assert len(results) == 3
        # tool_0 should succeed
        assert results[0].success is True
        # tool_1 should be rate-limited
        assert results[1].success is False
        assert (
            "rate-limited" in str(results[1].result).lower()
            or "rate-limited" in str(results[1].error or "").lower()
        )
        # tool_2 should succeed
        assert results[2].success is True

    @pytest.mark.asyncio
    async def test_parallel_execution_concurrent_timing(
        self, tool_manager_for_parallel
    ):
        """Test that parallel execution actually runs concurrently."""
        execution_times = []

        async def timed_use_tool(self_arg, tool_call):
            start = time.time()
            await asyncio.sleep(0.1)  # Simulate 100ms of work
            execution_times.append(time.time() - start)
            return "Result"

        tool_calls = [
            {"function": {"name": "tool_0", "arguments": {}}},
            {"function": {"name": "tool_1", "arguments": {}}},
            {"function": {"name": "tool_2", "arguments": {}}},
        ]

        start_time = time.time()
        with patch.object(
            type(tool_manager_for_parallel), "use_tool", new=timed_use_tool
        ):
            results = await tool_manager_for_parallel.execute_tools_parallel(tool_calls)
        total_time = time.time() - start_time

        assert len(results) == 3
        # If run sequentially, this would take ~300ms
        # If run in parallel, it should take ~100ms (plus overhead)
        # We allow up to 250ms to account for test environment variability
        assert (
            total_time < 0.25
        ), f"Parallel execution took {total_time}s, expected < 0.25s"
