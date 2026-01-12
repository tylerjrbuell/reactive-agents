"""
Playground - Real-world framework tests for developers.

This module provides organized, runnable tests for each framework feature.
Use these to explore, tinker, and validate the reactive-agents framework.

Usage:
    python main.py                    # Interactive menu
    python main.py streaming          # Run specific test
    python main.py --list             # List all available tests
"""

# Import test modules for easy access
from . import test_streaming
from . import test_agents
from . import test_strategies
from . import test_workflows
from . import tools

__all__ = [
    "test_streaming",
    "test_agents",
    "test_strategies",
    "test_workflows",
    "tools",
]
