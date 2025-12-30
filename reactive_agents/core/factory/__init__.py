"""
Factory module for creating agent components.

This module provides the ComponentFactory and ComponentSet for creating
and bundling agent components with proper dependency ordering.

Usage:
    from reactive_agents.core.factory import ComponentFactory, ComponentSet
    from reactive_agents.core.config.agent_config import AgentConfig

    config = AgentConfig(
        agent_name="MyAgent",
        provider_model_name="openai:gpt-4"
    )
    components: ComponentSet = await ComponentFactory.create_components(config)
"""

from reactive_agents.core.factory.component_set import ComponentSet
from reactive_agents.core.factory.component_factory import ComponentFactory

__all__ = [
    "ComponentSet",
    "ComponentFactory",
]
