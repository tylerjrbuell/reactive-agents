"""
Stress Tests - Push the framework to its limits.

These tests are designed to expose issues, bottlenecks, and edge cases
through complex real-world scenarios.
"""

import asyncio
from typing import Optional, List, Dict, Any
import time

from reactive_agents import ReactiveAgentBuilder, Provider, ReasoningStrategies
from .tools import get_weather, get_crypto_price, calculate


async def test_complex_multi_step_reasoning(model: str = "cogito:14b") -> bool:
    """
    Test complex multi-step task requiring:
    - Multiple tool calls in sequence
    - Context retention across steps
    - Proper dependency management
    """
    print("\n--- Complex Multi-Step Reasoning Test ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("ComplexReasoningAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Financial Analyst")
            .with_instructions(
                "You are a financial analyst. Break down complex questions into steps, "
                "use tools systematically, and provide comprehensive answers."
            )
            .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
            .with_custom_tools([get_weather, get_crypto_price, calculate])
            .with_max_iterations(10)
            .with_log_level("info")
            .build()
        )

        # Complex task requiring multiple steps
        task = """
        I need a comprehensive analysis:
        1. Get the current Bitcoin price
        2. Calculate what 5 Bitcoin would cost
        3. Get the weather in Tokyo
        4. Based on the weather, recommend if it's a good day for outdoor activities
        
        Provide all findings in a structured summary.
        """

        start_time = time.time()
        result = await agent.run(task)
        duration = time.time() - start_time

        print(f"Status: {result.status.value}")
        print(f"Duration: {duration:.2f}s")
        print(f"Iterations: {result.session.iterations}")
        print(f"Tools Used: {len(result.session.successful_tools)}")
        print(f"Success: {result.was_successful()}")

        # Validate that multiple tools were actually used
        expected_tools = {"get_crypto_price", "calculate", "get_weather"}
        tools_used = result.session.successful_tools
        tools_found = expected_tools & tools_used

        print(f"Expected tools used: {len(tools_found)}/{len(expected_tools)}")

        await agent.close()
        return result.was_successful() and len(tools_found) >= 2

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_error_recovery(model: str = "cogito:14b") -> bool:
    """
    Test error recovery mechanisms:
    - Handling invalid tool inputs
    - Recovering from failed operations
    - Retrying with different approaches
    """
    print("\n--- Error Recovery Test ---")

    try:
        # Tool that will fail initially
        def failing_tool(attempt: int = 1) -> str:
            """A tool that fails on first attempts."""
            if attempt < 2:
                raise ValueError("Simulated failure - try again with attempt=2")
            return f"Success on attempt {attempt}"

        agent = await (
            ReactiveAgentBuilder()
            .with_name("ErrorRecoveryAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Resilient Assistant")
            .with_instructions(
                "When tools fail, analyze the error and try different approaches. "
                "Read error messages carefully and adjust parameters."
            )
            .with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)
            .with_custom_tools([failing_tool])
            .with_max_iterations(8)
            .with_log_level("info")
            .build()
        )

        result = await agent.run(
            "Use the failing_tool. If it fails, try again with different parameters."
        )

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(
            f"Error Count: {result.session.error_count if hasattr(result.session, 'error_count') else 'N/A'}"
        )
        print(f"Success: {result.was_successful()}")

        await agent.close()
        return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_strategy_switching(model: str = "cogito:14b") -> bool:
    """
    Test dynamic strategy switching:
    - Start with one strategy
    - Detect when it's not working well
    - Switch to a more appropriate strategy
    """
    print("\n--- Strategy Switching Test ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("AdaptiveAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Adaptive Problem Solver")
            .with_instructions("Adapt your approach based on task complexity.")
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)  # Start simple
            .with_dynamic_strategy_switching(True)  # Enable switching
            .with_custom_tools([get_weather, calculate])
            .with_max_iterations(10)
            .with_log_level("info")
            .build()
        )

        # Task that benefits from planning
        task = """
        I need you to:
        1. Calculate 15 * 23
        2. Get weather for 3 different cities (Tokyo, New York, London)
        3. Compare the temperatures
        4. Identify which city has the best weather
        
        This requires careful planning and organization.
        """

        result = await agent.run(task)

        print(f"Status: {result.status.value}")
        print(
            f"Final Strategy: {result.session.final_strategy if hasattr(result.session, 'final_strategy') else 'Unknown'}"
        )
        print(f"Iterations: {result.session.iterations}")
        print(f"Success: {result.was_successful()}")

        await agent.close()
        return result.was_successful()

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_context_management(model: str = "cogito:14b") -> bool:
    """
    Test context management under load:
    - Long conversation history
    - Context pruning behavior
    - Memory retention
    """
    print("\n--- Context Management Test ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("ContextAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Conversational Assistant")
            .with_instructions("Maintain context across multiple interactions.")
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_max_iterations(3)
            .with_max_context_messages(10)  # Force context pruning
            .with_context_pruning(True)
            .with_log_level("info")
            .build()
        )

        # Series of related tasks
        tasks = [
            "Remember this: my favorite number is 42",
            "What was my favorite number?",
            "Calculate my favorite number times 2",
        ]

        results = []
        for i, task in enumerate(tasks, 1):
            print(f"\nStep {i}: {task}")
            result = await agent.run(task)
            results.append(result)
            print(
                f"  Answer: {result.final_answer[:100] if result.final_answer else 'None'}..."
            )

            # Small delay between tasks
            await asyncio.sleep(0.5)

        # Check if context was maintained
        final_result = results[-1]
        success = final_result.was_successful() and "84" in (
            final_result.final_answer or ""
        )  # 42 * 2 = 84

        print(f"\nOverall Success: {success}")

        await agent.close()
        return success

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_concurrent_agents(model: str = "cogito:14b") -> bool:
    """
    Test multiple agents running concurrently:
    - Resource contention
    - Independence of agent contexts
    - Parallel execution performance
    """
    print("\n--- Concurrent Agents Test ---")

    try:

        async def run_agent(name: str, task: str, strategy: str) -> Dict[str, Any]:
            """Run a single agent and return results."""
            agent = await (
                ReactiveAgentBuilder()
                .with_name(name)
                .with_model(Provider.OLLAMA, model)
                .with_role("Concurrent Worker")
                .with_instructions(f"Work on your assigned task independently.")
                .with_reasoning_strategy(strategy)
                .with_custom_tools([get_weather, calculate])
                .with_max_iterations(5)
                .with_log_level("warning")
                .build()
            )

            start = time.time()
            result = await agent.run(task)
            duration = time.time() - start

            await agent.close()

            return {
                "name": name,
                "success": result.was_successful(),
                "duration": duration,
                "iterations": result.session.iterations,
            }

        # Run 3 agents concurrently
        agents = [
            ("Agent1", "Calculate 100 * 5", ReasoningStrategies.REACTIVE),
            ("Agent2", "What's the weather in Tokyo?", ReasoningStrategies.REACTIVE),
            ("Agent3", "Calculate 50 + 75", ReasoningStrategies.REACTIVE),
        ]

        start_time = time.time()
        results = await asyncio.gather(
            *[run_agent(name, task, strat) for name, task, strat in agents]
        )
        total_duration = time.time() - start_time

        print(f"\nTotal Duration: {total_duration:.2f}s")
        for r in results:
            print(
                f"  {r['name']}: {'✓' if r['success'] else '✗'} ({r['duration']:.2f}s, {r['iterations']} iters)"
            )

        all_success = all(r["success"] for r in results)
        print(f"\nAll Agents Successful: {all_success}")

        return all_success

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_max_iterations_behavior(model: str = "cogito:14b") -> bool:
    """
    Test behavior when hitting max iterations:
    - Graceful degradation
    - Partial progress tracking
    - Meaningful failure messages
    """
    print("\n--- Max Iterations Behavior Test ---")

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("LimitedAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Constrained Assistant")
            .with_instructions("Work within iteration limits.")
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_max_iterations(2)  # Very low limit
            .with_log_level("info")
            .build()
        )

        # Task that would normally take more iterations
        task = "Solve a complex problem requiring multiple steps and tools"

        result = await agent.run(task)

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(f"Max Iterations: 2")
        print(f"Reached Limit: {result.session.iterations >= 2}")
        print(f"Has Final Answer: {result.final_answer is not None}")

        await agent.close()

        # Success if it handles limit gracefully
        return result.session.iterations <= 2 and result.final_answer is not None

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_tool_chaining_complexity(model: str = "cogito:14b") -> bool:
    """
    Test complex tool chaining:
    - Output of one tool as input to another
    - Multiple dependent operations
    - Proper data flow
    """
    print("\n--- Tool Chaining Complexity Test ---")

    try:

        def get_number() -> int:
            """Get a number."""
            return 10

        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        def format_result(value: int) -> str:
            """Format a result."""
            return f"The final result is: {value}"

        agent = await (
            ReactiveAgentBuilder()
            .with_name("ChainingAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Tool Chain Specialist")
            .with_instructions(
                "Chain tool calls together. Use output from one tool as input to the next."
            )
            .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
            .with_custom_tools([get_number, multiply, format_result])
            .with_max_iterations(8)
            .with_log_level("info")
            .build()
        )

        task = """
        Execute these steps in order:
        1. Call get_number to get a number
        2. Call multiply with that number and 5
        3. Call format_result with the multiplication result
        
        Provide the formatted output.
        """

        result = await agent.run(task)

        print(f"Status: {result.status.value}")
        print(f"Iterations: {result.session.iterations}")
        print(f"Tools Used: {result.session.successful_tools}")
        print(f"Success: {result.was_successful()}")

        # Check if result contains expected value (10 * 5 = 50)
        contains_result = "50" in (result.final_answer or "")
        print(f"Contains Expected Result: {contains_result}")

        await agent.close()
        return result.was_successful() and contains_result

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def run_all_stress_tests(model: str = "cogito:14b"):
    """Run all stress tests and report results."""
    print("=" * 60)
    print("STRESS TESTS - Framework Limits & Edge Cases")
    print("=" * 60)

    tests = [
        ("Complex Multi-Step Reasoning", test_complex_multi_step_reasoning),
        ("Error Recovery", test_error_recovery),
        ("Strategy Switching", test_strategy_switching),
        ("Context Management", test_context_management),
        ("Concurrent Agents", test_concurrent_agents),
        ("Max Iterations Behavior", test_max_iterations_behavior),
        ("Tool Chaining Complexity", test_tool_chaining_complexity),
    ]

    results = {}
    start_time = time.time()

    for name, test_func in tests:
        try:
            result = await test_func(model)
            results[name] = "PASS" if result else "FAIL"
        except Exception as e:
            print(f"\n{name} - EXCEPTION: {e}")
            results[name] = "ERROR"

    total_duration = time.time() - start_time

    print("\n" + "=" * 60)
    print("STRESS TEST RESULTS")
    print("=" * 60)

    for name, status in results.items():
        emoji = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
        print(f"  {emoji} {name}: {status}")

    print(f"\nTotal Duration: {total_duration:.2f}s")

    passed = sum(1 for s in results.values() if s == "PASS")
    total = len(results)
    print(f"Success Rate: {passed}/{total} ({100*passed//total}%)")

    return results


async def run(model: str = "cogito:14b", **kwargs):
    """Entry point for runner."""
    return await run_all_stress_tests(model)
