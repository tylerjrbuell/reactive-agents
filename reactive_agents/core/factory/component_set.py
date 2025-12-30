"""
ComponentSet: Immutable bundle of initialized agent components.

This module provides a dataclass that holds all initialized components
for an agent. By bundling components together, we achieve:
- Clear ownership of component lifecycle
- Explicit dependency relationships
- Easier testing and mocking
- Type-safe component access
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from reactive_agents.utils.logging import Logger
    from reactive_agents.providers.llm.base import BaseModelProvider
    from reactive_agents.core.events.event_bus import EventBus
    from reactive_agents.core.tools.tool_manager import ToolManager
    from reactive_agents.core.memory.memory_manager import MemoryManager
    from reactive_agents.core.memory.vector_memory import VectorMemoryManager
    from reactive_agents.core.metrics.metrics_manager import MetricsManager
    from reactive_agents.core.workflows.workflow_manager import WorkflowManager
    from reactive_agents.core.context.context_manager import ContextManager
    from reactive_agents.core.reasoning.task_classifier import TaskClassifier


@dataclass
class ComponentSet:
    """
    Bundle of initialized components for an agent.

    This dataclass holds all the components that an agent needs to function.
    Components are created in a specific dependency order by the ComponentFactory
    to avoid circular dependencies.

    Note: This is NOT frozen because some components may need to be updated
    after creation (e.g., TaskClassifier needs full AgentContext).

    Attributes:
        agent_logger: Primary logger for agent operations
        tool_logger: Logger for tool execution
        result_logger: Logger for agent results/responses
        model_provider: LLM provider for generating responses
        event_bus: Event system for state observation (optional)
        tool_manager: Manages tool discovery and execution
        memory_manager: Manages agent memory (JSON or Vector based)
        metrics_manager: Collects execution metrics (optional)
        workflow_manager: Manages workflow dependencies (optional)
        context_manager: Manages conversation context
        task_classifier: Classifies tasks for strategy selection (optional)
    """

    # Loggers (Tier 1 - no dependencies)
    agent_logger: "Logger"
    tool_logger: "Logger"
    result_logger: "Logger"

    # Model Provider (Tier 2 - depends on loggers for error reporting)
    model_provider: "BaseModelProvider"

    # Event Bus (Tier 2 - depends on agent_name only)
    event_bus: Optional["EventBus"]

    # Tool Manager (Tier 3 - depends on loggers, event_bus)
    tool_manager: "ToolManager"

    # Memory Manager (Tier 3 - depends on loggers)
    memory_manager: Optional[Union["MemoryManager", "VectorMemoryManager"]]

    # Metrics Manager (Tier 3 - depends on loggers, event_bus)
    metrics_manager: Optional["MetricsManager"]

    # Workflow Manager (Tier 4 - depends on loggers)
    workflow_manager: Optional["WorkflowManager"]

    # Context Manager (Tier 4 - depends on model_provider)
    context_manager: "ContextManager"

    # Task Classifier (Tier 5 - may depend on full context, created later)
    task_classifier: Optional["TaskClassifier"] = None

    def __repr__(self) -> str:
        """Return a concise string representation of the component set."""
        components = []
        if self.agent_logger:
            components.append("agent_logger")
        if self.tool_logger:
            components.append("tool_logger")
        if self.result_logger:
            components.append("result_logger")
        if self.model_provider:
            components.append("model_provider")
        if self.event_bus:
            components.append("event_bus")
        if self.tool_manager:
            components.append("tool_manager")
        if self.memory_manager:
            components.append("memory_manager")
        if self.metrics_manager:
            components.append("metrics_manager")
        if self.workflow_manager:
            components.append("workflow_manager")
        if self.context_manager:
            components.append("context_manager")
        if self.task_classifier:
            components.append("task_classifier")

        return f"ComponentSet({', '.join(components)})"
