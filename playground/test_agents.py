"""
Agent Tests - Test basic agent creation and execution.

Tests the ReactiveAgentBuilder and agent lifecycle.
"""

import asyncio
from typing import Optional

from reactive_agents import ReactiveAgentBuilder, Provider, ReasoningStrategies
from .tools import get_weather, get_crypto_price, calculate


async def test_basic_agent(model: str = "cogito:14b") -> bool:
    """Test basic agent creation and simple task execution."""
    print("\n--- Basic Agent Test ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("BasicAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Helpful Assistant")
            .with_instructions("Be concise and accurate.")
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_max_iterations(3)
            .with_log_level("debug")
            .build()
        )

        result = await agent.run("What is 2 + 2? Just the number.")

        print(f"Status: {result.status.value}")
        print(f"Success: {result.was_successful()}")
        print(f"Iterations: {result.session.iterations}")
        print(
            f"Answer: {result.final_answer[:100] if result.final_answer else 'None'}..."
        )

        await agent.close()
        return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        return False


async def test_agent_with_tools(model: str = "cogito:14b") -> bool:
    """Test agent with custom tools."""
    print("\n--- Agent with Tools Test ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("ToolAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Research Assistant")
            .with_instructions(
                "Use tools to answer questions. "
                "Use get_weather for weather, get_crypto_price for crypto prices."
            )
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_custom_tools([get_weather, get_crypto_price, calculate])
            .with_max_iterations(5)
            .with_log_level("debug")
            .build()
        )

        result = await agent.run("What's the weather in Tokyo?")

        print(f"Status: {result.status.value}")
        print(f"Success: {result.was_successful()}")
        print(
            f"Answer: {result.final_answer[:200] if result.final_answer else 'None'}..."
        )

        await agent.close()
        return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        return False


async def test_agent_events(model: str = "cogito:14b") -> bool:
    """Test agent event system."""
    print("\n--- Agent Events Test ---")

    events_received = []

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("EventAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Assistant")
            .with_instructions("Be helpful.")
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_max_iterations(2)
            .with_log_level("debug")
            .build()
        )

        # Register event handlers
        agent.on_session_started(lambda e: events_received.append("session_started"))
        agent.on_iteration_started(
            lambda e: events_received.append(f"iteration_{e.get('iteration', 0)}")
        )
        agent.on_session_ended(lambda e: events_received.append("session_ended"))

        result = await agent.run("Say hello.")

        print(f"Events received: {events_received}")
        print(f"Success: {result.was_successful()}")

        await agent.close()
        return len(events_received) >= 2  # At least session start and end

    except Exception as e:
        print(f"Error: {e}")
        return False


async def test_context_manager(model: str = "cogito:14b") -> bool:
    """Test agent with context manager for automatic cleanup."""
    print("\n--- Context Manager Test ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("ContextAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Assistant")
            .with_instructions("Be brief.")
            .with_max_iterations(2)
            .with_log_level("debug")
            .build()
        )

        async with agent:
            result = await agent.run("Say 'test passed'")
            print(
                f"Answer: {result.final_answer[:50] if result.final_answer else 'None'}..."
            )
            return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        return False


async def run(test_name: Optional[str] = None, model: str = "cogito:14b") -> dict:
    """
    Run agent tests.

    Args:
        test_name: Specific test to run (basic, tools, events, context)
                   or None to run all.
        model: Model to use for tests.

    Returns:
        Dict with test results.
    """
    print("=" * 60)
    print("AGENT TESTS")
    print("=" * 60)

    results = {}

    tests = {
        "basic": test_basic_agent,
        "tools": test_agent_with_tools,
        "events": test_agent_events,
        "context": test_context_manager,
    }

    if test_name and test_name in tests:
        results[test_name] = await tests[test_name](model)
    else:
        for name, test_fn in tests.items():
            results[name] = await test_fn(model)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    return results


if __name__ == "__main__":
    asyncio.run(run())
