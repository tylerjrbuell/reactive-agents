"""
Root-level pytest configuration.

This file must be at the repository root for pytest_plugins to work correctly.
"""

import pytest

# Configure asyncio plugin for all tests
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Register custom marks to avoid warnings."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "providers: mark test as provider test")
    config.addinivalue_line("markers", "slow: mark test as slow running test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
