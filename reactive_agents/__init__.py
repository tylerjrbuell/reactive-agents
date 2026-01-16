"""
Reactive Agents Framework

A powerful, intuitive framework for building AI agents with multiple reasoning strategies.

Quick Start:
    from reactive_agents import ReactiveAgentBuilder, Provider, ReasoningStrategies, tool

    @tool()
    async def my_tool(query: str) -> str:
        '''My custom tool.'''
        return f"Result for {query}"

    agent = await (
        ReactiveAgentBuilder()
        .with_name("MyAgent")
        .with_model(Provider.OLLAMA, "llama3")
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_custom_tools([my_tool])
        .build()
    )

    result = await agent.run("Do something")
    print(result.final_answer)
"""

# Suppress FutureWarning from instructor's internal google.generativeai import
# The instructor package hasn't fully migrated to google-genai yet
# This is a known issue tracked at: https://github.com/instructor-ai/instructor/issues
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="instructor.providers.gemini.client")

# Core agent classes
from reactive_agents.app.agents.base import Agent
from reactive_agents.app.agents.reactive_agent import ReactiveAgent
from reactive_agents.app.builders.agent import ReactiveAgentBuilder

# Tool creation
from reactive_agents.core.tools.decorators import tool, create_tool_from_function

# Builder enums for type-safe configuration
from reactive_agents.app.builders.agent import (
    Provider,
    ContextPruningStrategy,
    ToolUsePolicy,
)

# Types and enums
from reactive_agents.core.types.reasoning_types import ReasoningStrategies
from reactive_agents.core.types.execution_types import ExecutionResult, AgentResult
from reactive_agents.core.types.agent_types import ReactiveAgentConfig
from reactive_agents.core.types.confirmation_types import (
    ConfirmationConfig,
    ConfirmationCallbackProtocol,
)
from reactive_agents.core.types.status_types import TaskStatus
from reactive_agents.core.types.session_types import AgentSession
from reactive_agents.core.types.event_types import AgentStateEvent
from reactive_agents.config.logging import LogLevel

__all__ = [
    # Core classes
    "Agent",
    "ReactiveAgent",
    "ReactiveAgentBuilder",
    # Tool creation
    "tool",
    "create_tool_from_function",
    # Builder enums for type-safe configuration
    "Provider",
    "ContextPruningStrategy",
    "ToolUsePolicy",
    # Types and enums
    "ReasoningStrategies",
    "ExecutionResult",
    "AgentResult",  # Alias for ExecutionResult - return type of agent.run()
    "ReactiveAgentConfig",
    "ConfirmationConfig",
    "ConfirmationCallbackProtocol",
    "TaskStatus",
    "AgentSession",
    "AgentStateEvent",
    "LogLevel",  # Logging configuration
]

__version__ = "0.2.0"
