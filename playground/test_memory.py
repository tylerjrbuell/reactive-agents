"""
Memory System Playground Tests

These tests focus on validating the memory system capabilities:
- Memory persistence across sessions
- Memory retrieval and semantic search
- Cross-session learning
- Tool preference tracking
- Vector memory functionality

Note: These tests are designed to test the FRAMEWORK's memory capabilities,
not model performance. All tools use clear docstrings to minimize model confusion.
"""

import asyncio
from typing import Dict, Any, List
from reactive_agents import ReactiveAgentBuilder, Provider, ReasoningStrategies
from reactive_agents.core.tools.decorators import tool


# ============================================================================
# Well-Designed Tools with Clear Docstrings
# ============================================================================


@tool()
def save_user_preference(key: str, value: str) -> Dict[str, Any]:
    """
    Save a user preference to memory.

    This tool is used to store user preferences that should be remembered across sessions.

    Args:
        key: The preference name (e.g., 'favorite_color', 'preferred_language')
        value: The preference value (e.g., 'blue', 'python')

    Returns:
        Confirmation with the saved preference

    Examples:
        - To save favorite color: key='favorite_color', value='blue'
        - To save preferred language: key='preferred_language', value='python'
    """
    return {
        "success": True,
        "message": f"Saved preference: {key} = {value}",
        "key": key,
        "value": value
    }


@tool()
def recall_user_preference(key: str) -> Dict[str, Any]:
    """
    Recall a previously saved user preference from memory.

    Use this tool to retrieve preferences that were saved in previous sessions.
    The agent's memory system will automatically retrieve the value if it exists.

    Args:
        key: The preference name to recall (e.g., 'favorite_color')

    Returns:
        The saved preference value or indication if not found

    Examples:
        - To recall favorite color: key='favorite_color'
        - To recall preferred language: key='preferred_language'
    """
    # Simulated retrieval - actual implementation would query agent memory
    return {
        "success": True,
        "message": f"Attempting to recall preference: {key}",
        "key": key,
        "note": "Check agent memory for the actual value"
    }


@tool()
def log_task_completion(task_name: str, success: bool, notes: str = "") -> Dict[str, Any]:
    """
    Log that a task was completed for future reference.

    This helps the agent remember what tasks it has accomplished, which can
    inform future decision-making and avoid repeating work.

    Args:
        task_name: Name of the completed task (e.g., 'data_analysis_Q4_sales')
        success: Whether the task completed successfully (True/False)
        notes: Optional notes about the task completion

    Returns:
        Confirmation of task logging

    Examples:
        - Log successful analysis: task_name='analyze_sales_data', success=True, notes='Found key insights'
        - Log failed attempt: task_name='database_query', success=False, notes='Connection timeout'
    """
    return {
        "logged": True,
        "task": task_name,
        "success": success,
        "notes": notes,
        "message": f"Task '{task_name}' logged as {'successful' if success else 'failed'}"
    }


@tool()
def get_task_history(limit: int = 5) -> Dict[str, Any]:
    """
    Retrieve history of previously completed tasks.

    This allows the agent to see what tasks have been done before, which helps with:
    - Avoiding duplicate work
    - Learning from past successes/failures
    - Providing continuity across sessions

    Args:
        limit: Maximum number of historical tasks to return (default: 5)

    Returns:
        Dictionary with list of previously completed tasks and metadata

    Examples:
        - Get last 5 tasks: limit=5
        - Get last 10 tasks: limit=10
    """
    # Simulated task history - actual implementation would query agent memory
    _ = limit  # Used for limiting results in actual implementation
    return {
        "tasks": [
            {"task": "analyze_sales_data", "success": True, "timestamp": "2026-01-10T10:00:00"},
            {"task": "generate_report", "success": True, "timestamp": "2026-01-10T11:30:00"},
            {"task": "database_backup", "success": False, "timestamp": "2026-01-10T14:00:00"},
        ],
        "total_returned": 3,
        "note": "Check agent memory for complete history"
    }


@tool()
def execute_calculation(expression: str) -> Dict[str, Any]:
    """
    Execute a mathematical calculation.

    This tool safely evaluates mathematical expressions. Results are logged
    so the agent can remember previous calculations.

    Args:
        expression: Math expression to evaluate (e.g., '2 + 2', '10 * 5')

    Returns:
        Calculation result

    Examples:
        - Simple addition: expression='2 + 2'
        - Multiplication: expression='10 * 5'
        - Complex: expression='(100 - 25) * 2'

    Safety:
        Only basic arithmetic operators (+, -, *, /, **, %) are allowed.
        Variable names and imports are not permitted for security.
    """
    try:
        # Safe evaluation - only allow basic math operations
        allowed_chars = set('0123456789+-*/()%. ')
        if not all(c in allowed_chars for c in expression):
            return {
                "success": False,
                "error": "Invalid characters in expression. Only numbers and basic operators allowed."
            }

        result = eval(expression, {"__builtins__": {}}, {})
        return {
            "success": True,
            "expression": expression,
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "expression": expression,
            "error": str(e)
        }


# ============================================================================
# Memory Test Scenarios
# ============================================================================


async def test_memory_persistence():
    """
    Test 1: Memory Persistence Across Sessions

    Validates that:
    - Agent can save information to memory
    - Memory persists after agent shutdown
    - Agent can recall information from previous session
    """
    print("\n" + "=" * 60)
    print("TEST 1: Memory Persistence Across Sessions")
    print("=" * 60)

    # Session 1: Save preferences
    print("\n📝 Session 1: Saving user preferences...")
    agent = await (
        ReactiveAgentBuilder()
        .with_model(Provider.OLLAMA, "cogito:14b")
        .with_tools([save_user_preference, log_task_completion])
        # Memory is enabled by default - no need to explicitly enable
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_max_iterations(5)
        .build()
    )

    result = await agent.run("""
        Save these preferences for me:
        1. My favorite color is azure blue
        2. My preferred programming language is Python
        3. My timezone is UTC-5

        Use the save_user_preference tool for each preference.
        Then log that you completed this task using log_task_completion.
    """)

    print(f"✅ Session 1 Result: {result.final_answer}")
    print(f"   Iterations: {result.session.iterations}")
    print(f"   Tools Used: {result.session.successful_tools}")

    # Close agent to save memory
    await agent.close()
    print("💾 Agent closed, memory saved")

    # Session 2: Recall preferences (simulating new session)
    print("\n🔍 Session 2: Recalling preferences (new agent instance)...")
    agent2 = await (
        ReactiveAgentBuilder()
        .with_model(Provider.OLLAMA, "cogito:14b")
        .with_tools([recall_user_preference, get_task_history])
        # Memory is enabled by default and will load existing memory
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_max_iterations(5)
        .build()
    )

    result2 = await agent2.run("""
        What preferences did I save in the previous session?
        Use recall_user_preference to check for:
        - favorite_color
        - preferred_language
        - timezone

        Also use get_task_history to see what tasks were completed before.
    """)

    print(f"✅ Session 2 Result: {result2.final_answer}")
    print(f"   Iterations: {result2.session.iterations}")

    # Validation
    memory_persisted = "azure blue" in str(result2.final_answer).lower() or "Python" in str(result2.final_answer)

    await agent2.close()

    return {
        "test": "memory_persistence",
        "passed": memory_persisted,
        "session1_iterations": result.session.iterations,
        "session2_iterations": result2.session.iterations,
        "memory_persisted": memory_persisted
    }


async def test_tool_preference_tracking():
    """
    Test 2: Tool Preference Tracking

    Validates that:
    - Agent tracks which tools succeed/fail
    - Tool success rates are calculated
    - Agent can optimize tool selection based on history
    """
    print("\n" + "=" * 60)
    print("TEST 2: Tool Preference Tracking")
    print("=" * 60)

    agent = await (
        ReactiveAgentBuilder()
        .with_model(Provider.OLLAMA, "cogito:14b")
        .with_tools([execute_calculation, log_task_completion])
        # Memory enabled by default
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_max_iterations(10)
        .build()
    )

    # Execute multiple calculations to build tool usage history
    result = await agent.run("""
        Perform these calculations in sequence:
        1. Calculate 15 + 27
        2. Calculate 100 * 3
        3. Calculate 500 / 25
        4. Calculate 2 ** 8 (2 to the power of 8)
        5. Try to calculate 'invalid$expression' (this should fail)
        6. Calculate 75 - 30

        Use the execute_calculation tool for each one.
        After all calculations, log task completion.
    """)

    print(f"✅ Result: {result.final_answer}")
    print(f"   Iterations: {result.session.iterations}")
    print(f"   Tools Used: {result.session.successful_tools}")

    # Check memory for tool preferences
    memory_manager = agent.context.memory_manager
    tool_prefs = {}

    if memory_manager:
        tool_prefs = memory_manager.get_tool_preferences()

        print(f"\n📊 Tool Preferences Tracked:")
        for tool_name, prefs in tool_prefs.items():
            print(f"   {tool_name}:")
            print(f"      Success Rate: {prefs.get('success_rate', 0):.2%}")
            print(f"      Total Usage: {prefs.get('total_usage', 0)}")
            print(f"      Successes: {prefs.get('success_count', 0)}")
            print(f"      Failures: {prefs.get('failure_count', 0)}")
    else:
        print("\n⚠️  Memory manager not available")

    await agent.close()

    tracking_works = len(tool_prefs) > 0 and 'execute_calculation' in tool_prefs

    return {
        "test": "tool_preference_tracking",
        "passed": tracking_works,
        "iterations": result.session.iterations,
        "tool_preferences_tracked": list(tool_prefs.keys()),
        "execute_calculation_tracked": 'execute_calculation' in tool_prefs
    }


async def test_vector_memory_search():
    """
    Test 3: Vector Memory Semantic Search

    Validates that:
    - Vector memory can be enabled
    - Semantic search works across stored memories
    - Similar queries retrieve relevant past context
    """
    print("\n" + "=" * 60)
    print("TEST 3: Vector Memory Semantic Search")
    print("=" * 60)

    try:
        from reactive_agents.core.memory.vector_memory import CHROMADB_AVAILABLE

        if not CHROMADB_AVAILABLE:
            print("⚠️  ChromaDB not available - skipping vector memory test")
            return {
                "test": "vector_memory_search",
                "passed": False,
                "skipped": True,
                "reason": "ChromaDB not installed"
            }

        agent = await (
            ReactiveAgentBuilder()
            .with_model(Provider.OLLAMA, "cogito:14b")
            .with_tools([log_task_completion, execute_calculation])
            .with_vector_memory()  # Use vector memory for semantic search
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_max_iterations(8)
            .build()
        )

        # Store various types of information
        result = await agent.run("""
            Perform these tasks and log each one:

            1. Calculate 25 * 4 and log completion
            2. Calculate 100 + 50 and log completion
            3. Calculate 1000 / 10 and log completion

            Make sure to use execute_calculation for math and log_task_completion after each.
        """)

        print(f"✅ Tasks Completed: {result.final_answer}")
        print(f"   Iterations: {result.session.iterations}")

        # Test semantic search on vector memory
        search_results = []
        if hasattr(agent.context.memory_manager, 'search_memory'):
            print("\n🔍 Testing semantic search...")

            # Wait for vector memory to be ready
            if hasattr(agent.context.memory_manager, 'await_ready'):
                ready = await agent.context.memory_manager.await_ready(timeout=10.0)  # type: ignore[attr-defined]
                if ready:
                    print("   Vector memory is ready")
                else:
                    print("   ⚠️ Vector memory initialization timed out")
                    await agent.close()
                    return {
                        "test": "vector_memory_search",
                        "passed": False,
                        "error": "Vector memory initialization timeout"
                    }

            # Search for calculation-related memories
            search_results = await agent.context.memory_manager.search_memory(  # type: ignore[attr-defined]
                "multiplication calculations",
                n_results=5
            )

            print(f"   Found {len(search_results)} relevant memories")
            for i, memory in enumerate(search_results[:3]):
                print(f"   Memory {i+1}:")
                print(f"      Content: {memory['content'][:100]}...")
                print(f"      Relevance: {memory.get('relevance_score', 0):.3f}")
                print(f"      Type: {memory.get('metadata', {}).get('memory_type', 'unknown')}")

            search_works = len(search_results) > 0
        else:
            print("⚠️  Vector memory search not available")
            search_works = False

        await agent.close()

        return {
            "test": "vector_memory_search",
            "passed": search_works,
            "iterations": result.session.iterations,
            "memories_found": len(search_results)
        }

    except ImportError as e:
        print(f"⚠️  Vector memory dependencies not available: {e}")
        return {
            "test": "vector_memory_search",
            "passed": False,
            "skipped": True,
            "reason": "Missing dependencies (chromadb or sentence-transformers)"
        }


async def test_cross_session_learning():
    """
    Test 4: Cross-Session Learning

    Validates that:
    - Agent remembers successful approaches from past sessions
    - Agent can build on previous knowledge
    - Efficiency improves with repeated similar tasks
    """
    print("\n" + "=" * 60)
    print("TEST 4: Cross-Session Learning")
    print("=" * 60)

    # Session 1: Establish baseline
    print("\n📝 Session 1: Establishing baseline performance...")
    agent1 = await (
        ReactiveAgentBuilder()
        .with_model(Provider.OLLAMA, "cogito:14b")
        .with_tools([execute_calculation, log_task_completion])
        # Memory enabled by default
        .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
        .with_max_iterations(10)
        .build()
    )

    result1 = await agent1.run("""
        Calculate the total cost for this order:
        - 5 items at $12.50 each
        - 3 items at $8.75 each
        - 2 items at $15.00 each

        Calculate subtotal, then add 8% tax, then add $5 shipping.
        Log your completion when done.
    """)

    print(f"✅ Session 1 Result: {result1.final_answer}")
    print(f"   Iterations: {result1.session.iterations}")
    print(f"   Efficiency: {result1.session.metrics.get('efficiency_score', 0):.2f}")

    session1_iterations = result1.session.iterations

    await agent1.close()

    # Session 2: Repeat similar task (should be faster with memory)
    print("\n🔍 Session 2: Repeating similar task (should leverage memory)...")
    agent2 = await (
        ReactiveAgentBuilder()
        .with_model(Provider.OLLAMA, "cogito:14b")
        .with_tools([execute_calculation, log_task_completion])
        # Memory enabled by default
        .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
        .with_max_iterations(10)
        .build()
    )

    result2 = await agent2.run("""
        Calculate the total cost for this order:
        - 4 items at $9.99 each
        - 6 items at $5.50 each
        - 1 item at $25.00

        Calculate subtotal, then add 8% tax, then add $5 shipping.
        Log your completion when done.
    """)

    print(f"✅ Session 2 Result: {result2.final_answer}")
    print(f"   Iterations: {result2.session.iterations}")
    print(f"   Efficiency: {result2.session.metrics.get('efficiency_score', 0):.2f}")

    session2_iterations = result2.session.iterations

    await agent2.close()

    # Improved performance would mean fewer iterations in session 2
    # (though this depends on memory being consulted - which is the gap we identified)
    iterations_reduced = session2_iterations <= session1_iterations

    print(f"\n📊 Learning Assessment:")
    print(f"   Session 1 Iterations: {session1_iterations}")
    print(f"   Session 2 Iterations: {session2_iterations}")
    print(f"   Improved: {iterations_reduced}")
    print(f"   Note: Improvement requires memory consultation to be implemented")

    return {
        "test": "cross_session_learning",
        "passed": iterations_reduced,  # Will fail until memory consultation implemented
        "session1_iterations": session1_iterations,
        "session2_iterations": session2_iterations,
        "learning_demonstrated": iterations_reduced,
        "note": "May fail until memory consultation is integrated into strategies"
    }


async def test_reflection_memory():
    """
    Test 5: Reflection Memory Storage and Retrieval

    Validates that:
    - Agent stores reflections about its performance
    - Reflections can be retrieved and referenced
    - Reflections inform future decision-making
    """
    print("\n" + "=" * 60)
    print("TEST 5: Reflection Memory Storage")
    print("=" * 60)

    agent = await (
        ReactiveAgentBuilder()
        .with_model(Provider.OLLAMA, "cogito:14b")
        .with_tools([execute_calculation, log_task_completion])
        # Memory enabled by default
        .with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)  # Uses reflection
        .with_max_iterations(10)
        .build()
    )

    result = await agent.run("""
        Try these calculations and learn from any errors:
        1. Calculate 50 + 75
        2. Calculate 'bad expression' (this will fail - learn from it)
        3. Calculate 200 - 125
        4. Calculate 10 ** 2

        Reflect on what works and what doesn't.
        Log task completion when done.
    """)

    print(f"✅ Result: {result.final_answer}")
    print(f"   Iterations: {result.session.iterations}")

    # Check for stored reflections
    memory_manager = agent.context.memory_manager
    reflections = []

    if memory_manager:
        reflections = memory_manager.get_reflections()

        print(f"\n💭 Reflections Stored: {len(reflections)}")
        for i, reflection in enumerate(reflections[-3:]):  # Show last 3
            print(f"   Reflection {i+1}:")
            print(f"      Content: {str(reflection.get('content', ''))[:150]}...")
            print(f"      Timestamp: {reflection.get('timestamp', 'unknown')}")
    else:
        print("\n⚠️  Memory manager not available")

    reflections_stored = len(reflections) > 0

    await agent.close()

    return {
        "test": "reflection_memory",
        "passed": reflections_stored,
        "iterations": result.session.iterations,
        "reflections_count": len(reflections),
        "reflections_stored": reflections_stored
    }


# ============================================================================
# Test Runner
# ============================================================================


async def run_memory_tests():
    """Run all memory-focused playground tests"""
    print("\n" + "=" * 60)
    print("MEMORY SYSTEM PLAYGROUND TESTS")
    print("=" * 60)
    print("\nThese tests validate the framework's memory capabilities,")
    print("not model performance. Tools are designed with clear interfaces")
    print("to minimize model confusion and test the framework itself.")
    print("=" * 60)

    results = []

    # Run each test
    tests = [
        ("Memory Persistence", test_memory_persistence),
        ("Tool Preference Tracking", test_tool_preference_tracking),
        ("Vector Memory Search", test_vector_memory_search),
        ("Cross-Session Learning", test_cross_session_learning),
        ("Reflection Memory", test_reflection_memory),
    ]

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "test": test_name.lower().replace(" ", "_"),
                "passed": False,
                "error": str(e)
            })

    # Summary
    print("\n" + "=" * 60)
    print("MEMORY TEST RESULTS SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.get("passed", False))
    skipped = sum(1 for r in results if r.get("skipped", False))
    failed = len(results) - passed - skipped

    for result in results:
        status = "✓ PASS" if result.get("passed") else ("⊘ SKIP" if result.get("skipped") else "✗ FAIL")
        test_name = result["test"].replace("_", " ").title()
        print(f"  {status}: {test_name}")
        if result.get("error"):
            print(f"         Error: {result['error']}")
        if result.get("note"):
            print(f"         Note: {result['note']}")
        if result.get("skipped"):
            print(f"         Reason: {result.get('reason', 'Unknown')}")

    print(f"\nTotal Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Success Rate: {(passed / (len(results) - skipped) * 100) if (len(results) - skipped) > 0 else 0:.1f}%")

    return results


async def run(**kwargs):
    """Entry point for playground runner integration."""
    _ = kwargs  # Reserved for future use (model selection, etc.)
    return await run_memory_tests()


if __name__ == "__main__":
    asyncio.run(run_memory_tests())
