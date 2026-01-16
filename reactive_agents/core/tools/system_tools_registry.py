"""System tools registry for framework-provided tools.

This module provides a centralized registry of all system tools that are
automatically injected into agents. Framework users can customize which
system tools are enabled by configuring the registry.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Type, Dict, List
from dataclasses import dataclass

# Import SystemTool for type hints (not TYPE_CHECKING since we use it at runtime)
from reactive_agents.core.tools.system_tool import SystemTool

if TYPE_CHECKING:
    pass


@dataclass
class SystemToolConfig:
    """Configuration for a system tool.

    Attributes:
        tool_class: The SystemTool class to instantiate
        name: Tool name for identification
        enabled_by_default: Whether this tool is enabled by default
        description: Short description of the tool's purpose
        category: Category for grouping (e.g., 'core', 'meta', 'debug')
    """
    tool_class: Type["SystemTool"]
    name: str
    enabled_by_default: bool = True
    description: str = ""
    category: str = "system"


# Global system tools registry
# Framework users can modify this before agent initialization
SYSTEM_TOOLS_REGISTRY: Dict[str, SystemToolConfig] = {}


def register_system_tool(
    name: str,
    tool_class: Type["SystemTool"],
    enabled_by_default: bool = True,
    description: str = "",
    category: str = "system",
) -> None:
    """Register a system tool in the global registry.

    Args:
        name: Unique tool name
        tool_class: SystemTool class to register
        enabled_by_default: Whether enabled by default
        description: Tool description
        category: Tool category for grouping
    """
    SYSTEM_TOOLS_REGISTRY[name] = SystemToolConfig(
        tool_class=tool_class,
        name=name,
        enabled_by_default=enabled_by_default,
        description=description,
        category=category,
    )


def get_enabled_system_tools() -> List[SystemToolConfig]:
    """Get all system tools that are enabled by default.

    Returns:
        List of SystemToolConfig for enabled tools
    """
    return [
        config for config in SYSTEM_TOOLS_REGISTRY.values()
        if config.enabled_by_default
    ]


def get_system_tool_config(name: str) -> SystemToolConfig | None:
    """Get configuration for a specific system tool.

    Args:
        name: Tool name

    Returns:
        SystemToolConfig if found, None otherwise
    """
    return SYSTEM_TOOLS_REGISTRY.get(name)


def get_system_tools_by_category(category: str) -> List[SystemToolConfig]:
    """Get all system tools in a specific category.

    Args:
        category: Category name (e.g., 'core', 'meta', 'debug')

    Returns:
        List of SystemToolConfig in the category
    """
    return [
        config for config in SYSTEM_TOOLS_REGISTRY.values()
        if config.category == category
    ]


# ============================================================================
# Register Core System Tools
# ============================================================================

def _register_core_tools() -> None:
    """Register all core system tools in the registry."""
    from reactive_agents.core.tools.default import FinalAnswerTool
    from reactive_agents.core.tools.meta_actions import (
        SignalStuckTool,
        RequestStrategySwitchTool,
        RequestClarificationTool,
    )

    # Core tool - required for task completion
    register_system_tool(
        name="final_answer",
        tool_class=FinalAnswerTool,
        enabled_by_default=True,
        description="Provides final answer and concludes task",
        category="core",
    )

    # Meta-action tools - agent self-correction
    register_system_tool(
        name="signal_stuck",
        tool_class=SignalStuckTool,
        enabled_by_default=True,
        description="Signal being stuck and request framework intervention",
        category="meta",
    )

    register_system_tool(
        name="request_strategy_switch",
        tool_class=RequestStrategySwitchTool,
        enabled_by_default=True,
        description="Request a different reasoning strategy",
        category="meta",
    )

    register_system_tool(
        name="request_clarification",
        tool_class=RequestClarificationTool,
        enabled_by_default=True,
        description="Request clarification or additional information",
        category="meta",
    )


# Auto-register core tools on module import
_register_core_tools()


__all__ = [
    "SystemToolConfig",
    "SYSTEM_TOOLS_REGISTRY",
    "register_system_tool",
    "get_enabled_system_tools",
    "get_system_tool_config",
    "get_system_tools_by_category",
]
