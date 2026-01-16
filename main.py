#!/usr/bin/env python3
"""
Reactive-Agents Framework - Development Playground

This is the main entry point for testing and tinkering with the framework.
Run different test suites to explore framework capabilities.

Usage:
    python main.py                     # Interactive menu
    python main.py streaming           # Run streaming tests
    python main.py agents              # Run agent tests
    python main.py strategies          # Run strategy tests
    python main.py workflows           # Run workflow tests
    python main.py all                 # Run all tests
    python main.py --list              # List available tests

Examples:
    # Test streaming with Ollama
    python main.py streaming

    # Run all agent tests
    python main.py agents

    # Interactive selection
    python main.py
"""

import warnings
import dotenv
from pydantic import PydanticDeprecatedSince211

# Suppress common warnings for cleaner output
warnings.simplefilter("ignore", ResourceWarning)
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince211)
warnings.filterwarnings("ignore", category=FutureWarning)

# Load environment variables
dotenv.load_dotenv()


def main():
    """Main entry point."""
    from playground.runner import main as run_playground
    run_playground()


if __name__ == "__main__":
    main()
