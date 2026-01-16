"""
ComponentFactory: Creates and wires agent components in dependency order.

This module provides a factory that creates all components needed by an agent,
ensuring they are initialized in the correct order to avoid circular dependencies.

The factory follows a tiered approach:
1. Tier 1: Loggers (no dependencies)
2. Tier 2: EventBus, ModelProvider (depend on agent_name/loggers)
3. Tier 3: ToolManager, MemoryManager, MetricsManager (depend on loggers, event_bus)
4. Tier 4: WorkflowManager, ContextManager (depend on model_provider)
5. Tier 5: TaskClassifier (needs full AgentContext - created separately)
"""

from __future__ import annotations

from typing import Optional, List, Any, TYPE_CHECKING

from reactive_agents.core.factory.component_set import ComponentSet

if TYPE_CHECKING:
    from reactive_agents.core.config.agent_config import AgentConfig
    from reactive_agents.providers.external.client import MCPClient
    from reactive_agents.core.tools.base import Tool


class ComponentFactory:
    """
    Factory for creating and wiring agent components in dependency order.

    This factory extracts component creation logic from AgentContext into a
    dedicated class with explicit dependency ordering. Components are created
    in tiers to ensure dependencies are satisfied before dependent components
    are initialized.

    Usage:
        config = AgentConfig(agent_name="MyAgent", provider_model_name="openai:gpt-4")
        components = await ComponentFactory.create_components(config)
    """

    @staticmethod
    async def create_components(
        config: "AgentConfig",
        mcp_client: Optional["MCPClient"] = None,
        custom_tools: Optional[List["Tool"]] = None,
    ) -> ComponentSet:
        """
        Create all components based on configuration.

        This method creates components in explicit dependency order to avoid
        circular dependencies and ensure proper initialization.

        Dependency order:
        1. Loggers (no dependencies)
        2. EventBus (depends on agent_name only)
        3. ModelProvider (external dependency)
        4. MemoryManager (depends on loggers)
        5. ToolManager (depends on loggers, event_bus)
        6. MetricsManager (depends on loggers, event_bus)
        7. WorkflowManager (optional)
        8. ContextManager (depends on model_provider)
        9. TaskClassifier (may depend on context - NOT created here)

        Args:
            config: The AgentConfig with all configuration settings
            mcp_client: Optional MCP client for tool discovery
            custom_tools: Optional list of custom tools to register

        Returns:
            ComponentSet with all initialized components
        """
        # =========================================================================
        # Tier 1: Loggers (no dependencies)
        # =========================================================================
        agent_logger, tool_logger, result_logger = ComponentFactory._create_loggers(
            config
        )
        agent_logger.info(f"Creating components for agent: {config.agent_name}")

        # =========================================================================
        # Tier 2: EventBus and ModelProvider
        # =========================================================================
        event_bus = ComponentFactory._create_event_bus(config)
        if event_bus:
            agent_logger.info("Event bus initialized.")

        model_provider = ComponentFactory._create_model_provider(config, agent_logger)
        agent_logger.info(f"Initialized model provider: {config.provider_model_name}")

        # =========================================================================
        # Tier 3: MemoryManager, ToolManager, MetricsManager
        # These need a minimal context-like object for initialization
        # =========================================================================

        # Create a minimal context holder for components that need it
        # This will be replaced with the full AgentContext later
        from reactive_agents.core.factory._component_context import ComponentContext

        component_context = ComponentContext(
            config=config,
            agent_logger=agent_logger,
            tool_logger=tool_logger,
            result_logger=result_logger,
            model_provider=model_provider,
            event_bus=event_bus,
            mcp_client=mcp_client,
            custom_tools=custom_tools or [],
        )

        # Create memory manager
        memory_manager = await ComponentFactory._create_memory_manager(
            config, component_context, agent_logger
        )

        # Create metrics manager
        metrics_manager = ComponentFactory._create_metrics_manager(
            config, component_context
        )

        # Create tool manager
        tool_manager = ComponentFactory._create_tool_manager(
            component_context
        )

        # =========================================================================
        # Tier 4: WorkflowManager, ContextManager
        # =========================================================================
        workflow_manager = ComponentFactory._create_workflow_manager(
            config, component_context
        )

        context_manager = ComponentFactory._create_context_manager(component_context)
        agent_logger.info("Context manager initialized.")

        # =========================================================================
        # Build and return ComponentSet
        # TaskClassifier is NOT created here - it needs full AgentContext
        # =========================================================================
        components = ComponentSet(
            agent_logger=agent_logger,
            tool_logger=tool_logger,
            result_logger=result_logger,
            model_provider=model_provider,
            event_bus=event_bus,
            tool_manager=tool_manager,
            memory_manager=memory_manager,
            metrics_manager=metrics_manager,
            workflow_manager=workflow_manager,
            context_manager=context_manager,
            task_classifier=None,  # Created later with full AgentContext
        )

        agent_logger.info(f"ComponentSet created: {components}")
        return components

    @staticmethod
    def _create_loggers(config: "AgentConfig"):
        """Create the three loggers needed by the agent."""
        from reactive_agents.utils.logging import Logger

        agent_logger = Logger(
            name=config.agent_name,
            type="agent",
            level=config.log_level,
        )

        tool_logger = Logger(
            name=f"{config.agent_name} Tool",
            type="tool",
            level=config.log_level,
        )

        result_logger = Logger(
            name=f"{config.agent_name} Result",
            type="agent_response",
            level=config.log_level,
        )

        return agent_logger, tool_logger, result_logger

    @staticmethod
    def _create_event_bus(config: "AgentConfig"):
        """Create the event bus if state observation is enabled."""
        if not config.enable_state_observation:
            return None

        from reactive_agents.core.events.event_bus import EventBus

        return EventBus(config.agent_name)

    @staticmethod
    def _create_model_provider(config: "AgentConfig", agent_logger: Any):
        """Create the model provider."""
        try:
            from reactive_agents.providers.llm.factory import ModelProviderFactory

            # Create model provider with options
            # Note: We pass None for context here since we don't have full AgentContext yet
            # The model provider will work without it for basic operations
            return ModelProviderFactory.get_model_provider(
                config.provider_model_name,
                options=config.model_provider_options or {},
                context=None,  # Will be set later when AgentContext is created
            )

        except Exception as e:
            agent_logger.error(f"Failed to initialize model provider: {e}")
            raise RuntimeError(f"Model provider initialization failed: {e}")

    @staticmethod
    async def _create_memory_manager(
        config: "AgentConfig",
        component_context: Any,
        agent_logger: Any,
    ):
        """Create the appropriate memory manager based on configuration."""
        if not config.use_memory_enabled:
            agent_logger.info(f"Memory manager disabled for {config.agent_name}")
            return None

        if config.vector_memory_enabled:
            agent_logger.info(
                f"Initializing memory manager for {config.agent_name} with vector memory enabled"
            )

            from reactive_agents.core.memory.vector_memory import (
                VectorMemoryManager,
                VectorMemoryConfig,
            )
            from reactive_agents.config.settings import get_settings

            settings = get_settings()
            vector_persist_dir = str(settings.get_vector_memory_path())

            # Create vector memory configuration
            vector_config = VectorMemoryConfig(
                collection_name=config.vector_memory_collection
                or config.agent_name.replace(" ", "_").lower(),
                persist_directory=vector_persist_dir,
            )

            memory_manager = VectorMemoryManager(
                context=component_context,
                config=vector_config,
            )

            agent_logger.info(
                f"Initialized vector memory with collection: {vector_config.collection_name}"
            )
            return memory_manager

        else:
            agent_logger.info(
                f"Initializing memory manager for {config.agent_name} with json memory enabled"
            )

            from reactive_agents.core.memory.memory_manager import MemoryManager

            return MemoryManager(context=component_context)

    @staticmethod
    def _create_metrics_manager(config: "AgentConfig", component_context: Any):
        """Create the metrics manager if metrics collection is enabled."""
        if not config.collect_metrics_enabled:
            return None

        from reactive_agents.core.metrics.metrics_manager import MetricsManager

        return MetricsManager(context=component_context)

    @staticmethod
    def _create_tool_manager(component_context: Any):
        """Create the tool manager."""
        from reactive_agents.core.tools.tool_manager import ToolManager

        return ToolManager(context=component_context)

    @staticmethod
    def _create_workflow_manager(config: "AgentConfig", component_context: Any):
        """Create the workflow manager."""
        from reactive_agents.core.workflows.workflow_manager import WorkflowManager

        return WorkflowManager(
            context=component_context,
            workflow_context=None,  # Will be set when agent joins a workflow
            workflow_dependencies=[],  # Will be set when agent joins a workflow
        )

    @staticmethod
    def _create_context_manager(component_context: Any):
        """Create the context manager."""
        from reactive_agents.core.context.context_manager import ContextManager

        return ContextManager(agent_context=component_context)
