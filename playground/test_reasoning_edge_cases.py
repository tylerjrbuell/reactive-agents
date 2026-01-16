"""
Reasoning Edge Case Tests - Expose Critical Framework Gaps

These tests are designed to FAIL until reasoning improvements are implemented.
They validate loop detection, strategy switching, completion detection, memory
integration, and context management - all areas identified as critical gaps.

EXPECTED RESULTS (before fixes):
- Loop detection tests: FAIL (no loop detection exists)
- Strategy switching tests: FAIL (switching never triggers)
- Completion detection tests: FAIL (conversational tasks timeout)
- Memory-guided tests: FAIL (memory never consulted)
- Context fidelity tests: FAIL (naive summarization)

After implementing fixes from REASONING_ANALYSIS.md, these should pass.
"""

import asyncio
from typing import Dict, Any, List
import time

from reactive_agents import ReactiveAgentBuilder, Provider, ReasoningStrategies
from reactive_agents.core.tools.decorators import tool


# ============================================================================
# Test 1: Loop Detection
# ============================================================================


async def test_infinite_loop_detection(model: str = "cogito:14b") -> Dict[str, Any]:
    """
    Test: Agent gets stuck in infinite loop repeating same actions.

    EXPECTED TO PASS: Loop detection is now implemented.

    Current behavior: Loop detector triggers within 4-6 iterations and:
    - Detects similar tool call patterns
    - Switches strategy automatically
    - Provides guidance nudges
    - Agent can use signal_stuck to self-report

    Success criteria: Loop detection triggers and intervenes appropriately.
    """
    print("\n" + "=" * 70)
    print("TEST: Infinite Loop Detection")
    print("=" * 70)
    print("EXPECTED: PASS - Loop detection implemented")
    print()

    @tool()
    def stuck_tool(query: str) -> str:
        """A tool that always returns the same result, creating potential loops."""
        return "Result: 42 (this won't change no matter how many times you call it)"

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("LoopTestAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Test Subject")
            .with_instructions(
                "Try to get different results by calling tools multiple times if needed."
            )
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_custom_tools([stuck_tool])
            .with_max_iterations(10)
            .with_log_level("warning")
            .build()
        )

        task = "Use stuck_tool to find the answer. If it doesn't work, try again with different queries."

        start_time = time.time()
        result = await agent.run(task)
        duration = time.time() - start_time

        # Analyze loop behavior
        tool_calls = (
            result.session.tool_call_history
            if hasattr(result.session, "tool_call_history")
            else []
        )

        # Count how many times stuck_tool was called
        stuck_tool_calls = [
            call for call in tool_calls if call.get("tool_name") == "stuck_tool"
        ]

        print(f"\n📊 Results:")
        print(f"   Status: {result.status.value}")
        print(f"   Iterations: {result.session.iterations}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   stuck_tool called: {len(stuck_tool_calls)} times")

        # Check for loop indicators
        has_loop = len(stuck_tool_calls) >= 3
        hit_max_iterations = result.session.iterations >= 10

        # Check if loop was detected (check cumulative history)
        loop_detections = getattr(result.session, "loop_detections", [])
        loop_detected = len(loop_detections) > 0

        print(f"\n🔍 Analysis:")
        print(f"   Loop suspected: {has_loop}")
        print(f"   Hit max iterations: {hit_max_iterations}")
        print(f"   Loop detected by framework: {loop_detected}")

        if loop_detected:
            print(f"   Loop detection count: {len(loop_detections)}")
            for i, detection in enumerate(loop_detections, 1):
                print(
                    f"      {i}. Iteration {detection.get('iteration')}: {detection.get('tool_name')} "
                    f"({detection.get('length')} reps, {detection.get('confidence'):.0%} confidence)"
                )

        await agent.close()

        # Test passes if loop was detected, fails if it wasn't
        test_passed = loop_detected

        print(
            f"\n{'✅ PASS' if test_passed else '❌ FAIL'}: Loop detection {'worked' if test_passed else 'not implemented'}"
        )

        return {
            "test": "infinite_loop_detection",
            "passed": test_passed,
            "iterations": result.session.iterations,
            "tool_calls": len(stuck_tool_calls),
            "loop_detected": loop_detected,
            "loop_detection_count": len(loop_detections),
            "expected_failure": False,  # Loop detection is now implemented
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return {"test": "infinite_loop_detection", "passed": False, "error": str(e)}


# ============================================================================
# Test 2: Strategy Switching Validation
# ============================================================================


async def test_strategy_switching_actually_happens(
    model: str = "cogito:14b",
) -> Dict[str, Any]:
    """
    Test: Dynamic strategy switching is enabled but never triggers.

    EXPECTED TO FAIL: Strategy switching logic doesn't check during iteration loop.

    Current behavior: Agent starts with REACTIVE, struggles with complex task,
    but never switches to PLAN_EXECUTE_REFLECT despite dynamic switching enabled.

    After fix: Should detect task complexity mismatch and switch strategies
    with session.strategy_changes metadata showing when/why switch occurred.
    """
    print("\n" + "=" * 70)
    print("TEST: Strategy Switching Actually Happens")
    print("=" * 70)
    print("EXPECTED: FAIL - Dynamic switching never triggers")
    print()

    @tool()
    def step_one() -> str:
        """Complete step one of multi-step task."""
        return "Step 1 complete"

    @tool()
    def step_two() -> str:
        """Complete step two of multi-step task."""
        return "Step 2 complete"

    @tool()
    def step_three() -> str:
        """Complete step three of multi-step task."""
        return "Step 3 complete"

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("StrategySwitchTest")
            .with_model(Provider.OLLAMA, model)
            .with_role("Adaptive Problem Solver")
            .with_instructions("Complete complex multi-step tasks efficiently.")
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)  # Start simple
            .with_dynamic_strategy_switching(True)  # Enable switching
            .with_custom_tools([step_one, step_two, step_three])
            .with_max_iterations(10)
            .with_log_level("warning")
            .build()
        )

        task = """
        Complete this multi-step project in order:
        1. Call step_one
        2. Call step_two  
        3. Call step_three
        4. Summarize all results
        
        This requires careful planning and organization.
        """

        initial_strategy = "reactive"

        start_time = time.time()
        result = await agent.run(task)
        duration = time.time() - start_time

        # Check if strategy changed
        final_strategy = (
            result.session.final_strategy
            if hasattr(result.session, "final_strategy")
            else initial_strategy
        )
        strategy_changes = (
            result.session.strategy_changes
            if hasattr(result.session, "strategy_changes")
            else []
        )

        print(f"\n📊 Results:")
        print(f"   Initial strategy: {initial_strategy}")
        print(f"   Final strategy: {final_strategy}")
        print(f"   Strategy changes: {len(strategy_changes)}")
        print(f"   Iterations: {result.session.iterations}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Success: {result.was_successful()}")

        if strategy_changes:
            print(f"\n   Strategy change details:")
            for change in strategy_changes:
                print(
                    f"      - Iteration {change.get('iteration')}: {change.get('from')} → {change.get('to')}"
                )
                print(f"        Reason: {change.get('reason')}")

        await agent.close()

        # Test passes if strategy actually switched
        switched = final_strategy != initial_strategy or len(strategy_changes) > 0

        print(
            f"\n{'✅ PASS' if switched else '❌ FAIL'}: Strategy switching {'worked' if switched else 'never triggered'}"
        )

        return {
            "test": "strategy_switching_validation",
            "passed": switched,
            "initial_strategy": initial_strategy,
            "final_strategy": final_strategy,
            "changes": len(strategy_changes),
            "expected_failure": True,
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {
            "test": "strategy_switching_validation",
            "passed": False,
            "error": str(e),
        }


# ============================================================================
# Test 3: Task Completion Detection
# ============================================================================


async def test_conversational_vs_action_task_completion(
    model: str = "cogito:14b",
) -> Dict[str, Any]:
    """
    Test: Agent can't distinguish conversational from action-based tasks.

    EXPECTED TO FAIL: Conversational tasks timeout instead of completing in 1 iteration.

    Current behavior:
    - "Remember X" runs 3+ iterations without calling final_answer
    - "Calculate X" correctly uses tools and final_answer in ~2 iterations

    After fix: Completion detector should recognize conversational tasks
    need only acknowledgment, not tool usage.
    """
    print("\n" + "=" * 70)
    print("TEST: Conversational vs Action Task Completion")
    print("=" * 70)
    print("EXPECTED: Conversational task FAILS (takes 3+ iterations instead of 1)")
    print()

    @tool()
    def calculate(expression: str) -> float:
        """Calculate a mathematical expression."""
        return eval(expression)

    try:
        # Test 1: Conversational task (should be 1 iteration)
        print("Test 1a: Conversational task")
        agent1 = await (
            ReactiveAgentBuilder()
            .with_name("ConversationalTest")
            .with_model(Provider.OLLAMA, model)
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_max_iterations(5)
            .with_log_level("warning")
            .build()
        )

        conversational_task = (
            "Remember this: my favorite number is 42. Just acknowledge you've noted it."
        )

        start1 = time.time()
        result1 = await agent1.run(conversational_task)
        duration1 = time.time() - start1

        print(f"   Iterations: {result1.session.iterations} (expected: 1)")
        print(f"   Duration: {duration1:.2f}s")
        print(f"   Success: {result1.was_successful()}")

        await agent1.close()

        # Test 1b: Action task (should use tools, ~2 iterations)
        print("\nTest 1b: Action task")
        agent2 = await (
            ReactiveAgentBuilder()
            .with_name("ActionTest")
            .with_model(Provider.OLLAMA, model)
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_custom_tools([calculate])
            .with_max_iterations(5)
            .with_log_level("warning")
            .build()
        )

        action_task = "Calculate 15 * 23 and give me the result."

        start2 = time.time()
        result2 = await agent2.run(action_task)
        duration2 = time.time() - start2

        print(f"   Iterations: {result2.session.iterations} (expected: 2-3)")
        print(f"   Duration: {duration2:.2f}s")
        print(f"   Success: {result2.was_successful()}")
        print(f"   Used calculate: {'calculate' in result2.session.successful_tools}")

        await agent2.close()

        # Analysis
        conversational_efficient = result1.session.iterations <= 1
        action_used_tools = "calculate" in result2.session.successful_tools

        print(f"\n🔍 Analysis:")
        print(f"   Conversational task efficient: {conversational_efficient}")
        print(f"   Action task used tools: {action_used_tools}")

        test_passed = conversational_efficient and action_used_tools

        print(
            f"\n{'✅ PASS' if test_passed else '❌ FAIL'}: Completion detection {'works' if test_passed else 'needs improvement'}"
        )

        return {
            "test": "completion_detection",
            "passed": test_passed,
            "conversational_iterations": result1.session.iterations,
            "action_iterations": result2.session.iterations,
            "conversational_efficient": conversational_efficient,
            "expected_failure": True,
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {"test": "completion_detection", "passed": False, "error": str(e)}


# ============================================================================
# Test 4: Memory-Guided Efficiency
# ============================================================================


async def test_memory_improves_efficiency_over_sessions(
    model: str = "cogito:14b",
) -> Dict[str, Any]:
    """
    Test: Memory exists but is never consulted during reasoning.

    EXPECTED TO FAIL: Second session takes same iterations as first (no learning).

    Current behavior: Agent stores memory after session 1, but doesn't
    consult get_similar_sessions() or get_relevant_reflections() in session 2.

    After fix: Session 2 should complete in 50% fewer iterations by
    consulting memory and learning from session 1's successful approach.
    """
    print("\n" + "=" * 70)
    print("TEST: Memory-Guided Efficiency Improvement")
    print("=" * 70)
    print("EXPECTED: FAIL - Memory not consulted, no improvement")
    print()

    @tool()
    def analyze_data(data_type: str) -> Dict[str, Any]:
        """Analyze a dataset."""
        return {
            "type": data_type,
            "records": 1000,
            "avg": 42.5,
            "summary": f"Analysis of {data_type} complete",
        }

    @tool()
    def generate_report(analysis: str) -> str:
        """Generate report from analysis."""
        return f"Report generated based on: {analysis}"

    try:
        # Session 1: Baseline
        print("Session 1: Baseline (no prior memory)")
        agent1 = await (
            ReactiveAgentBuilder()
            .with_name("MemoryTestAgent")
            .with_model(Provider.OLLAMA, model)
            .with_role("Data Analyst")
            .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
            .with_custom_tools([analyze_data, generate_report])
            .with_max_iterations(10)
            .with_log_level("warning")
            .build()
        )

        task1 = "Analyze sales data and generate a comprehensive report."

        start1 = time.time()
        result1 = await agent1.run(task1)
        duration1 = time.time() - start1

        print(f"   Iterations: {result1.session.iterations}")
        print(f"   Duration: {duration1:.2f}s")
        print(f"   Tools: {result1.session.successful_tools}")

        await agent1.close()

        # Small delay to ensure memory is saved
        await asyncio.sleep(1)

        # Session 2: Should benefit from memory
        print("\nSession 2: With memory from session 1")
        agent2 = await (
            ReactiveAgentBuilder()
            .with_name("MemoryTestAgent")  # Same name to load memory
            .with_model(Provider.OLLAMA, model)
            .with_role("Data Analyst")
            .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
            .with_custom_tools([analyze_data, generate_report])
            .with_max_iterations(10)
            .with_log_level("warning")
            .build()
        )

        # Similar task (should trigger get_similar_sessions)
        task2 = "Analyze customer data and generate a comprehensive report."

        start2 = time.time()
        result2 = await agent2.run(task2)
        duration2 = time.time() - start2

        print(f"   Iterations: {result2.session.iterations}")
        print(f"   Duration: {duration2:.2f}s")
        print(f"   Tools: {result2.session.successful_tools}")

        await agent2.close()

        # Analysis
        iteration_improvement = (
            (result1.session.iterations - result2.session.iterations)
            / result1.session.iterations
        ) * 100

        print(f"\n🔍 Analysis:")
        print(f"   Session 1 iterations: {result1.session.iterations}")
        print(f"   Session 2 iterations: {result2.session.iterations}")
        print(f"   Improvement: {iteration_improvement:.1f}%")
        print(f"   Target improvement: >30%")

        # Memory was consulted if session 2 is significantly faster
        memory_helped = iteration_improvement >= 30

        print(
            f"\n{'✅ PASS' if memory_helped else '❌ FAIL'}: Memory {'helped' if memory_helped else 'not consulted'}"
        )

        return {
            "test": "memory_guided_efficiency",
            "passed": memory_helped,
            "session1_iterations": result1.session.iterations,
            "session2_iterations": result2.session.iterations,
            "improvement_percent": iteration_improvement,
            "expected_failure": True,
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {"test": "memory_guided_efficiency", "passed": False, "error": str(e)}


# ============================================================================
# Test 5: Context Summarization Fidelity
# ============================================================================


async def test_context_summarization_preserves_critical_info(
    model: str = "cogito:14b",
) -> Dict[str, Any]:
    """
    Test: Context summarization uses naive placeholder instead of LLM.

    EXPECTED TO FAIL: Critical information lost during context pruning.

    Current behavior: Line 544 of context_manager.py generates useless
    summaries like "[Summary of 10 messages: 5 user, 5 assistant]" which
    loses all semantic content.

    After fix: LLM-powered summarization should preserve key facts even
    after aggressive pruning.
    """
    print("\n" + "=" * 70)
    print("TEST: Context Summarization Fidelity")
    print("=" * 70)
    print("EXPECTED: FAIL - Naive summarization loses information")
    print()

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("ContextTest")
            .with_model(Provider.OLLAMA, model)
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_max_context_messages(15)  # Force aggressive pruning
            .with_context_pruning(True)
            .with_max_iterations(20)
            .with_log_level("warning")
            .build()
        )

        # Series of interactions with critical fact in middle
        tasks = [
            "Hello, I'm starting a conversation.",
            "Let me tell you about my preferences.",
            "I really enjoy outdoor activities.",
            "My favorite sport is rock climbing.",
            "I also like hiking on weekends.",
            "CRITICAL FACT: My emergency contact is Dr. Sarah Chen at 555-0123.",  # This must be remembered
            "I've been climbing for 5 years.",
            "Last month I climbed El Capitan.",
            "It was an amazing experience.",
            "I'm planning another trip soon.",
            "Maybe to Yosemite again.",
            "Or perhaps somewhere new.",
            "I'm also interested in bouldering.",
            "It's a different challenge.",
            "Now, what was my emergency contact information?",  # Test if it remembers
        ]

        print("Running 15 conversation turns to force context pruning...")

        for i, task in enumerate(tasks, 1):
            result = await agent.run(task)
            if i == 6:
                print(f"   Turn {i}: CRITICAL FACT provided")
            elif i == 15:
                print(f"   Turn {i}: Asking for critical fact recall")

                # Check if emergency contact info is in response
                response = result.final_answer or ""
                has_contact_name = (
                    "sarah" in response.lower() or "chen" in response.lower()
                )
                has_contact_number = "555" in response or "0123" in response

                print(f"\n🔍 Analysis:")
                print(f"   Mentioned contact name: {has_contact_name}")
                print(f"   Mentioned contact number: {has_contact_number}")

            # Small delay between turns
            await asyncio.sleep(0.3)

        await agent.close()

        # Test passes if both name and number were recalled
        info_preserved = has_contact_name and has_contact_number

        print(
            f"\n{'✅ PASS' if info_preserved else '❌ FAIL'}: Critical info {'preserved' if info_preserved else 'lost in summarization'}"
        )

        return {
            "test": "context_summarization_fidelity",
            "passed": info_preserved,
            "contact_name_preserved": has_contact_name,
            "contact_number_preserved": has_contact_number,
            "expected_failure": True,
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {
            "test": "context_summarization_fidelity",
            "passed": False,
            "error": str(e),
        }


# ============================================================================
# Test 6: Progress Tracking and Stagnation
# ============================================================================


async def test_progress_stagnation_detection(
    model: str = "cogito:14b",
) -> Dict[str, Any]:
    """
    Test: No tracking of iterations_without_progress metric.

    EXPECTED TO FAIL: Agent makes no progress but framework doesn't detect it.

    Current behavior: Agent can run multiple iterations making no new
    progress (no new tool results, no new information) but framework
    doesn't track or react to this stagnation.

    After fix: session.iterations_without_progress should increment,
    and after 3 stagnant iterations, trigger intervention (strategy switch
    or graceful termination with explanation).
    """
    print("\n" + "=" * 70)
    print("TEST: Progress Stagnation Detection")
    print("=" * 70)
    print("EXPECTED: FAIL - No stagnation tracking exists")
    print()

    @tool()
    def unhelpful_tool(query: str) -> str:
        """A tool that doesn't actually help solve the task."""
        return "This doesn't really answer your question. Try something else?"

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("StagnationTest")
            .with_model(Provider.OLLAMA, model)
            .with_role("Problem Solver")
            .with_instructions(
                "Solve tasks efficiently. If stuck, try different approaches."
            )
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_custom_tools([unhelpful_tool])
            .with_max_iterations(8)
            .with_log_level("warning")
            .build()
        )

        task = "Find the answer using available tools. The answer should be a specific number."

        start_time = time.time()
        result = await agent.run(task)
        duration = time.time() - start_time

        # Check if stagnation was detected
        stagnation_detected = hasattr(result.session, "iterations_without_progress")

        if stagnation_detected:
            stagnant_iterations = result.session.iterations_without_progress
            print(f"\n📊 Stagnation Metrics:")
            print(f"   Iterations without progress: {stagnant_iterations}")
            print(f"   Stagnation threshold: 3")
            print(f"   Intervention triggered: {stagnant_iterations >= 3}")
        else:
            print(f"\n📊 No stagnation tracking found")
            print(f"   Total iterations: {result.session.iterations}")

        await agent.close()

        # Test passes if stagnation was tracked and detected
        test_passed = stagnation_detected

        print(
            f"\n{'✅ PASS' if test_passed else '❌ FAIL'}: Stagnation detection {'implemented' if test_passed else 'missing'}"
        )

        return {
            "test": "progress_stagnation_detection",
            "passed": test_passed,
            "stagnation_tracking_exists": stagnation_detected,
            "expected_failure": True,
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {
            "test": "progress_stagnation_detection",
            "passed": False,
            "error": str(e),
        }


# ============================================================================
# Test 7: Tool Redundancy Detection
# ============================================================================


async def test_tool_redundancy_prevention(model: str = "cogito:14b") -> Dict[str, Any]:
    """
    Test: Same tool called multiple times with identical parameters.

    EXPECTED TO FAIL: No redundancy detection exists.

    Evidence from real-world tests: Code Reviewer called check_security
    twice with same code, wasting an iteration.

    After fix: RecentToolTracker should detect duplicate calls within
    last 3-5 calls and either skip or warn about redundancy.
    """
    print("\n" + "=" * 70)
    print("TEST: Tool Redundancy Prevention")
    print("=" * 70)
    print("EXPECTED: FAIL - No redundancy detection")
    print()

    @tool()
    def check_status(item_id: str) -> Dict[str, str]:
        """Check the status of an item."""
        return {"item_id": item_id, "status": "active"}

    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("RedundancyTest")
            .with_model(Provider.OLLAMA, model)
            .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
            .with_custom_tools([check_status])
            .with_max_iterations(5)
            .with_log_level("warning")
            .build()
        )

        task = "Check the status of item ABC-123 thoroughly. Verify the result multiple times if needed."

        result = await agent.run(task)

        # Analyze tool calls
        tool_calls = (
            result.session.tool_call_history
            if hasattr(result.session, "tool_call_history")
            else []
        )

        # Count duplicate check_status calls with same parameters
        check_status_calls = [
            c for c in tool_calls if c.get("tool_name") == "check_status"
        ]

        # Check for exact duplicates (same parameters)
        duplicates = 0
        seen = set()
        for call in check_status_calls:
            params_str = str(call.get("parameters", {}))
            if params_str in seen:
                duplicates += 1
            seen.add(params_str)

        # Check if redundancy was detected/prevented
        redundancy_detected = hasattr(result.session, "redundant_tool_calls_detected")

        print(f"\n📊 Results:")
        print(f"   Total check_status calls: {len(check_status_calls)}")
        print(f"   Duplicate calls: {duplicates}")
        print(f"   Redundancy detected by framework: {redundancy_detected}")

        await agent.close()

        # Test passes if redundancy detection exists OR no duplicates occurred
        test_passed = redundancy_detected or duplicates == 0

        print(
            f"\n{'✅ PASS' if test_passed else '❌ FAIL'}: Redundancy {'prevented' if test_passed else 'not detected'}"
        )

        return {
            "test": "tool_redundancy_prevention",
            "passed": test_passed,
            "duplicate_calls": duplicates,
            "redundancy_tracking_exists": redundancy_detected,
            "expected_failure": True,
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {"test": "tool_redundancy_prevention", "passed": False, "error": str(e)}


# ============================================================================
# Test Runner
# ============================================================================


async def run_all_edge_case_tests(model: str = "cogito:14b"):
    """Run all reasoning edge case tests."""
    print("\n" + "=" * 70)
    print("REASONING EDGE CASE TESTS")
    print("Exposing Critical Framework Gaps")
    print("=" * 70)
    print(
        "\n⚠️  These tests are EXPECTED TO FAIL until reasoning fixes are implemented."
    )
    print(
        "See REASONING_ANALYSIS.md and ROADMAP.md Phase 1.5 for implementation plan.\n"
    )

    tests = [
        ("Loop Detection", test_infinite_loop_detection),
        ("Strategy Switching Validation", test_strategy_switching_actually_happens),
        ("Completion Detection", test_conversational_vs_action_task_completion),
        ("Memory-Guided Efficiency", test_memory_improves_efficiency_over_sessions),
        (
            "Context Summarization Fidelity",
            test_context_summarization_preserves_critical_info,
        ),
        ("Progress Stagnation Detection", test_progress_stagnation_detection),
        ("Tool Redundancy Prevention", test_tool_redundancy_prevention),
    ]

    results = {}
    start_time = time.time()

    for name, test_func in tests:
        try:
            result = await test_func(model)
            results[name] = result
        except Exception as e:
            print(f"\n{name} - EXCEPTION: {e}")
            results[name] = {"test": name, "passed": False, "error": str(e)}

    total_duration = time.time() - start_time

    # Summary
    print("\n" + "=" * 70)
    print("EDGE CASE TEST RESULTS")
    print("=" * 70)

    passed = 0
    failed = 0
    expected_failures = 0

    for name, result in results.items():
        status = "PASS" if result.get("passed") else "FAIL"
        emoji = "✅" if result.get("passed") else "❌"
        expected = " (expected)" if result.get("expected_failure") else ""

        print(f"{emoji} {name}: {status}{expected}")

        if result.get("passed"):
            passed += 1
        else:
            failed += 1
            if result.get("expected_failure"):
                expected_failures += 1

    print(f"\n📊 Summary:")
    print(f"   Passed: {passed}/{len(tests)}")
    print(f"   Failed: {failed}/{len(tests)}")
    print(f"   Expected failures: {expected_failures}/{failed}")
    print(f"   Duration: {total_duration:.2f}s")

    if expected_failures == failed:
        print(f"\n✅ All failures are expected - baseline established")
        print(f"   Implement fixes from REASONING_ANALYSIS.md to make these pass")

    return results


async def run(model: str = "cogito:14b", **kwargs):
    """Entry point for test runner."""
    return await run_all_edge_case_tests(model)


if __name__ == "__main__":
    asyncio.run(run())
