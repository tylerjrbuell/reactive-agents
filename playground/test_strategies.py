"""
Strategy Tests - Test different reasoning strategies.

Tests REACTIVE, REFLECT_DECIDE_ACT, PLAN_EXECUTE_REFLECT, and ADAPTIVE strategies.
"""

import asyncio
from typing import Optional

from reactive_agents import ReactiveAgentBuilder, Provider, ReasoningStrategies
from .tools import get_weather, get_crypto_price


async def test_reactive_strategy(model: str = "cogito:14b") -> bool:
    """Test the REACTIVE strategy for quick responses."""
    print("\n--- REACTIVE Strategy ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("ReactiveAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Quick Response Assistant")
            .with_instructions("Provide quick, reactive responses.")
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_custom_tools([get_crypto_price])
            .with_max_iterations(5)
            .with_log_level("warning")
            .with_dynamic_strategy_switching(False)
            .build()
        )

        result = await agent.run("What is the price of Bitcoin?")

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(
            f"Answer: {result.final_answer[:150] if result.final_answer else 'None'}..."
        )

        await agent.close()
        return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        return False


async def test_reflect_decide_act_strategy(model: str = "cogito:14b") -> bool:
    """Test the REFLECT_DECIDE_ACT strategy."""
    print("\n--- REFLECT_DECIDE_ACT Strategy ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("RDAAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Thoughtful Assistant")
            .with_instructions(
                "Reflect before acting. Consider your approach carefully."
            )
            .with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)
            .with_custom_tools([get_weather])
            .with_max_iterations(5)
            .with_log_level("warning")
            .build()
        )

        result = await agent.run(
            "What's the weather in London? Think about how to answer this."
        )

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(
            f"Answer: {result.final_answer[:150] if result.final_answer else 'None'}..."
        )

        await agent.close()
        return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        return False


async def test_plan_execute_reflect_strategy(model: str = "cogito:14b") -> bool:
    """Test the PLAN_EXECUTE_REFLECT strategy."""
    print("\n--- PLAN_EXECUTE_REFLECT Strategy ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("PlannerAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Strategic Planner")
            .with_instructions(
                "Plan your approach, execute steps, and reflect on results."
            )
            .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
            .with_custom_tools([get_weather, get_crypto_price])
            .with_max_iterations(8)
            .with_log_level("warning")
            .build()
        )

        result = await agent.run(
            "Get the weather in Tokyo and the price of Ethereum, then summarize both."
        )

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(
            f"Answer: {result.final_answer[:200] if result.final_answer else 'None'}..."
        )

        await agent.close()
        return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        return False


async def test_adaptive_strategy(model: str = "cogito:14b") -> bool:
    """Test the ADAPTIVE strategy that switches based on task complexity."""
    print("\n--- ADAPTIVE Strategy ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("AdaptiveAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Adaptive Assistant")
            .with_instructions("Adapt your reasoning based on task complexity.")
            .with_reasoning_strategy(ReasoningStrategies.ADAPTIVE)
            .with_custom_tools([get_weather, get_crypto_price])
            .with_max_iterations(10)
            .with_log_level("warning")
            .with_dynamic_strategy_switching(True)
            .build()
        )

        result = await agent.run("What is 2 + 2?")

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(
            f"Answer: {result.final_answer[:100] if result.final_answer else 'None'}..."
        )

        await agent.close()
        return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        return False


async def run(strategy: Optional[str] = None, model: str = "cogito:14b") -> dict:
    """
    Run strategy tests.

    Args:
        strategy: Specific strategy to test (reactive, rda, per, adaptive)
                  or None to run all.
        model: Model to use for tests.

    Returns:
        Dict with test results.
    """
    print("=" * 60)
    print("STRATEGY TESTS")
    print("=" * 60)

    results = {}

    tests = {
        "reactive": test_reactive_strategy,
        "rda": test_reflect_decide_act_strategy,
        "per": test_plan_execute_reflect_strategy,
        "adaptive": test_adaptive_strategy,
    }

    if strategy and strategy in tests:
        results[strategy] = await tests[strategy](model)
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
