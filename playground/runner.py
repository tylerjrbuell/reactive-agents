"""
Playground Runner - Execute playground tests from command line.

Usage:
    python main.py                     # Interactive menu
    python main.py streaming           # Run streaming tests
    python main.py agents              # Run agent tests
    python main.py strategies          # Run strategy tests
    python main.py workflows           # Run workflow tests
    python main.py all                 # Run all tests
    python main.py --list              # List available tests
"""

import asyncio
import sys
from typing import Dict, Any

from scipy import signal

# Test modules - use relative imports
from . import test_streaming
from . import test_agents
from . import test_strategies
from . import test_workflows
from . import test_stress
from . import test_real_world
from . import test_memory
from . import test_reasoning_edge_cases
from . import test_system_tools


# Registry of available test suites
TEST_SUITES = {
    "streaming": {
        "module": test_streaming,
        "description": "Test streaming responses from all providers",
    },
    "agents": {
        "module": test_agents,
        "description": "Test agent creation, tools, and events",
    },
    "strategies": {
        "module": test_strategies,
        "description": "Test reasoning strategies (reactive, RDA, PER, adaptive)",
    },
    "workflows": {
        "module": test_workflows,
        "description": "Test multi-agent workflow orchestration",
    },
    "stress": {
        "module": test_stress,
        "description": "Stress tests - complex scenarios, edge cases, limits",
    },
    "real-world": {
        "module": test_real_world,
        "description": "Real-world scenarios - customer support, data analysis, etc.",
    },
    "memory": {
        "module": test_memory,
        "description": "Memory system tests - persistence, retrieval, learning",
    },
    "reasoning-edge-cases": {
        "module": test_reasoning_edge_cases,
        "description": "Reasoning edge cases - loop detection, strategy switching, completion, memory integration (EXPECTED FAILURES)",
    },
    "system-tools": {
        "module": test_system_tools,
        "description": "System tools tests - final answer, request clarification,stuck signaling",
    },
}


def list_tests():
    """List all available test suites."""
    print("\n" + "=" * 60)
    print("AVAILABLE TEST SUITES")
    print("=" * 60)

    for name, info in TEST_SUITES.items():
        print(f"\n  {name}")
        print(f"    {info['description']}")

    print("\n" + "-" * 60)
    print("Usage:")
    print("  python main.py <test_name>    Run specific test suite")
    print("  python main.py all            Run all test suites")
    print("  python main.py --list         Show this list")
    print("=" * 60 + "\n")


async def run_test(test_name: str, **kwargs) -> Dict[str, Any]:
    """
    Run a specific test suite.

    Args:
        test_name: Name of test suite to run
        **kwargs: Additional arguments passed to test

    Returns:
        Test results dict
    """
    if test_name not in TEST_SUITES:
        print(f"Unknown test suite: {test_name}")
        list_tests()
        return {}

    module = TEST_SUITES[test_name]["module"]
    return await module.run(**kwargs)


async def run_all(**kwargs) -> Dict[str, Dict[str, Any]]:
    """Run all test suites."""
    print("\n" + "=" * 60)
    print("RUNNING ALL TEST SUITES")
    print("=" * 60)

    all_results = {}

    for name in TEST_SUITES:
        print(f"\n>>> Running {name} tests...")
        all_results[name] = await run_test(name, **kwargs)

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)

    total_pass = 0
    total_fail = 0

    for suite_name, results in all_results.items():
        suite_pass = sum(1 for v in results.values() if v)
        suite_fail = sum(1 for v in results.values() if not v)
        total_pass += suite_pass
        total_fail += suite_fail
        print(f"  {suite_name}: {suite_pass} passed, {suite_fail} failed")

    print("-" * 60)
    print(f"  TOTAL: {total_pass} passed, {total_fail} failed")
    print("=" * 60)

    return all_results


def run_interactive():
    """Run interactive menu for selecting tests."""
    print("\n" + "=" * 60)
    print("REACTIVE-AGENTS PLAYGROUND")
    print("=" * 60)
    print("\nSelect a test suite to run:\n")

    options = list(TEST_SUITES.keys()) + ["all", "quit"]

    for i, name in enumerate(options, 1):
        if name in TEST_SUITES:
            print(f"  {i}. {name} - {TEST_SUITES[name]['description']}")
        elif name == "all":
            print(f"  {i}. all - Run all test suites")
        else:
            print(f"  {i}. quit - Exit")

    print()

    while True:
        try:
            choice = input("Enter choice (number or name): ").strip().lower()

            # Handle numeric input
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    choice = options[idx]
                else:
                    print("Invalid choice. Try again.")
                    continue

            if choice == "quit" or choice == "q":
                print("Goodbye!")
                return

            if choice == "all":
                asyncio.run(run_all())
                return

            if choice in TEST_SUITES:
                asyncio.run(run_test(choice))
                return

            print(f"Unknown option: {choice}. Try again.")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            return
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point for playground runner."""
    args = sys.argv[1:]

    if not args:
        # Interactive mode
        run_interactive()
        return

    if args[0] == "--list" or args[0] == "-l":
        list_tests()
        return

    if args[0] == "all":
        asyncio.run(run_all())
        return

    # Run specific test
    test_name = args[0]
    asyncio.run(run_test(test_name))


if __name__ == "__main__":
    main()
