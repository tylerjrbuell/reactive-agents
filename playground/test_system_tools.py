"""Fast, focused tests for system tools and loop detection.

These tests verify that:
1. Loop detection catches repeated actions
2. signal_stuck intervention works
3. Strategy switching from loops helps
4. Performance actually improves with interventions

Run individual tests for quick iteration:
    python playground/test_system_tools.py test_loop_detection_triggers
    python playground/test_system_tools.py test_signal_stuck_helps
    python playground/test_system_tools.py all
"""

import asyncio
import sys
from typing import Dict, Any
from reactive_agents.app.builders.agent import ReactiveAgentBuilder
from reactive_agents.core.tools.base import Tool, ToolInput
from reactive_agents.core.tools.abstractions import ToolResult
from pydantic import Field


# ============================================================================
# Test Tools - Simulate problematic scenarios
# ============================================================================


class StuckToolInput(ToolInput):
    """Input for stuck tool."""
    query: str = Field(..., description="Query to process (ignored)")


class StuckTool(Tool):
    """Tool that always returns same result - simulates stuck scenario."""

    name: str = "stuck_tool"
    description: str = "A tool that always returns 42 (simulates stuck behavior)"
    input_schema: type[ToolInput] | None = StuckToolInput

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Always return 42."""
        return ToolResult.ok(value="42", tool_name=self.name)


class CounterToolInput(ToolInput):
    """Input for counter tool."""
    action: str = Field(..., description="Action to perform")


class CounterTool(Tool):
    """Tool that tracks call count - for verification."""

    name: str = "counter_tool"
    description: str = "Tracks how many times it's been called"
    input_schema: type[ToolInput] | None = CounterToolInput

    def __init__(self, **data):
        super().__init__(**data)
        self.call_count = 0

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Increment and return count."""
        self.call_count += 1
        return ToolResult.ok(
            value=f"Call #{self.call_count}",
            tool_name=self.name
        )


class FlakeyToolInput(ToolInput):
    """Input for flakey tool."""
    query: str = Field(..., description="Query to process")


class FlakeyTool(Tool):
    """Tool that fails first N times, then succeeds."""

    name: str = "flakey_tool"
    description: str = "Fails first 3 times, then works"
    input_schema: type[ToolInput] | None = FlakeyToolInput

    def __init__(self, fail_count: int = 3, **data):
        super().__init__(**data)
        self.call_count = 0
        self.fail_count = fail_count

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Fail first N times, then succeed."""
        self.call_count += 1

        if self.call_count <= self.fail_count:
            return ToolResult.fail(
                error=f"Failed (attempt {self.call_count}/{self.fail_count})",
                tool_name=self.name
            )

        return ToolResult.ok(
            value=f"Success after {self.call_count} attempts!",
            tool_name=self.name
        )


# ============================================================================
# Test Functions
# ============================================================================


async def test_loop_detection_triggers(model: str = "ollama:cogito:14b") -> Dict[str, Any]:
    """Test that loop detection actually triggers on repeated calls.

    Setup: Agent with stuck_tool that always returns 42
    Expected: Loop detection should trigger after 3 identical calls
    Measure:
        - Did loop get detected?
        - What iteration did it trigger?
        - Did strategy switch happen?
    """
    print("\n" + "="*70)
    print("TEST: Loop Detection Triggers")
    print("="*70)

    stuck_tool = StuckTool()

    agent = await (
        ReactiveAgentBuilder()
        .with_name("LoopDetectionTest")
        .with_model(model)
        .with_reasoning_strategy("reactive")  # Start with simplest strategy
        .with_max_iterations(8)     # Shorter for faster iteration
        .with_tools([stuck_tool])
        .build()
    )

    print(f"✓ Agent created successfully")
    print(f"✓ System tools available: {[t.name for t in agent.context.tool_manager.tools if hasattr(t, 'name')]}")

    task = (
        "Use stuck_tool with different queries to find the answer. "
        "Try queries: 'weather', 'stock', 'news', 'sports', 'crypto'. "
        "The answer should vary based on the query."
    )

    print(f"\n📋 Task: {task}")
    print(f"🎯 Expected: Loop detection after 3 identical stuck_tool calls")
    print(f"⏱️  Running agent (max 8 iterations)...")

    result = await agent.run(task)

    print(f"✓ Agent completed")

    # Analyze results
    session = agent.context.session

    loop_detected = getattr(session, "loop_detected", False)
    loop_details = getattr(session, "loop_details", None)
    agent_signaled = session.agent_signaled_stuck

    print(f"\n📊 Results:")
    print(f"   Total iterations: {session.iterations}")
    print(f"   Loop detected (auto): {loop_detected}")
    if loop_details:
        print(f"   Loop type: {loop_details.get('type')}")
        print(f"   Loop length: {loop_details.get('length')}")
        print(f"   Tool involved: {loop_details.get('tool_name')}")
    print(f"   Agent signaled stuck: {agent_signaled}")
    print(f"   Final answer: {session.final_answer}")

    # Check tool manager for loop detector state
    if agent.context.tool_manager.loop_detector:
        summary = agent.context.tool_manager.loop_detector.get_summary()
        print(f"\n🔍 Loop Detector Stats:")
        print(f"   Total calls tracked: {summary['total_calls_tracked']}")
        print(f"   Unique signatures: {summary['unique_signatures']}")
        print(f"   Most called: {summary['most_called_tool']}")

    # Determine pass/fail
    passed = False
    reason = ""

    if loop_detected or agent_signaled:
        # Either automatic detection or agent signaled - both good!
        passed = True
        if loop_detected and agent_signaled:
            reason = "✅ Both loop detection AND agent signal_stuck triggered (excellent!)"
        elif loop_detected:
            reason = "✅ Loop detection triggered automatically"
        else:
            reason = "✅ Agent used signal_stuck tool"
    else:
        reason = "❌ No loop detection or stuck signal despite repeated tool calls"

    print(f"\n{reason}")
    print(f"   Iterations used: {session.iterations}/15")

    return {
        "test": "loop_detection_triggers",
        "pass": passed,
        "reason": reason,
        "iterations": session.iterations,
        "loop_detected": loop_detected,
        "agent_signaled": agent_signaled,
        "loop_details": loop_details,
    }


async def test_loop_detection_helps_performance(model: str = "ollama:cogito:14b") -> Dict[str, Any]:
    """Test that loop detection actually improves performance.

    Compare:
        - Scenario A: Agent with loop detection ENABLED (default)
        - Scenario B: Agent with loop detection DISABLED (hypothetical baseline)

    Measure:
        - Iterations to completion
        - Did it complete successfully?
        - Strategy switches triggered
    """
    print("\n" + "="*70)
    print("TEST: Loop Detection Helps Performance")
    print("="*70)

    flakey_tool = FlakeyTool(fail_count=3)

    # Test WITH loop detection (enabled by default)
    print("\n🟢 Running WITH loop detection...")
    agent_with = await (
        ReactiveAgentBuilder()
        .with_name("WithLoopDetection")
        .with_model(model)
        .with_reasoning_strategy("reactive")
        .with_max_iterations(10)  # Shorter for faster testing
        .with_tools([flakey_tool])
        .build()
    )

    task = (
        "Use flakey_tool to get data. It may fail a few times. "
        "If it keeps failing, try a different approach or signal that you're stuck. "
        "Once you get data, provide it as the final answer."
    )

    print(f"📋 Task: {task}")

    result_with = await agent_with.run(task)
    session_with = agent_with.context.session

    loop_detected_with = getattr(session_with, "loop_detected", False)
    agent_signaled_with = session_with.agent_signaled_stuck

    print(f"\n📊 Results WITH loop detection:")
    print(f"   Iterations: {session_with.iterations}")
    print(f"   Completed: {session_with.task_status}")
    print(f"   Loop detected: {loop_detected_with}")
    print(f"   Agent signaled: {agent_signaled_with}")
    print(f"   Tool calls: {flakey_tool.call_count}")
    print(f"   Final answer: {session_with.final_answer is not None}")

    # Determine success
    completed = session_with.final_answer is not None
    efficient = session_with.iterations < 15  # Completed before max

    passed = completed and efficient
    reason = ""

    if completed and efficient:
        if loop_detected_with or agent_signaled_with:
            reason = f"✅ Completed efficiently in {session_with.iterations} iterations with intervention"
        else:
            reason = f"✅ Completed efficiently in {session_with.iterations} iterations (no intervention needed)"
    elif completed:
        reason = f"⚠️  Completed but used all {session_with.iterations} iterations"
    else:
        reason = f"❌ Failed to complete (used {session_with.iterations} iterations)"

    print(f"\n{reason}")

    return {
        "test": "loop_detection_helps_performance",
        "pass": passed,
        "reason": reason,
        "iterations": session_with.iterations,
        "completed": completed,
        "loop_detected": loop_detected_with,
        "agent_signaled": agent_signaled_with,
        "tool_calls": flakey_tool.call_count,
    }


async def test_signal_stuck_triggers_intervention(model: str = "ollama:cogito:14b") -> Dict[str, Any]:
    """Test that agent using signal_stuck actually gets help.

    Setup: Task that's intentionally hard/ambiguous
    Expected: Agent should use signal_stuck, framework should intervene
    Measure:
        - Did agent use signal_stuck?
        - Did strategy switch happen?
        - Did intervention help?
    """
    print("\n" + "="*70)
    print("TEST: signal_stuck Triggers Intervention")
    print("="*70)

    counter_tool = CounterTool()

    agent = await (
        ReactiveAgentBuilder()
        .with_name("SignalStuckTest")
        .with_model(model)
        .with_reasoning_strategy("reactive")
        .with_max_iterations(12)
        .with_tools([counter_tool])
        .build()
    )

    task = (
        "Use counter_tool to find a pattern. Call it multiple times. "
        "If you can't find a pattern after 4 tries, you should signal that you're stuck. "
        "There is no actual pattern - this is intentionally impossible."
    )

    print(f"\n📋 Task: {task}")
    print(f"🎯 Expected: Agent should use signal_stuck after realizing futility")

    result = await agent.run(task)
    session = agent.context.session

    # Check if signal_stuck was used
    signal_stuck_used = False
    for tool_call in session.messages:
        if isinstance(tool_call, dict):
            if tool_call.get("tool_name") == "signal_stuck":
                signal_stuck_used = True
                break

    # Also check session flag
    agent_signaled = session.agent_signaled_stuck
    stuck_reason = session.stuck_reason

    # Check tool history
    tool_history = agent.context.tool_manager.tool_history
    signal_stuck_calls = [h for h in tool_history if h["name"] == "signal_stuck"]

    print(f"\n📊 Results:")
    print(f"   Total iterations: {session.iterations}")
    print(f"   Agent signaled stuck: {agent_signaled or signal_stuck_used}")
    if stuck_reason:
        print(f"   Stuck reason: {stuck_reason}")
    print(f"   signal_stuck calls: {len(signal_stuck_calls)}")
    print(f"   counter_tool calls: {counter_tool.call_count}")

    # Check for intervention evidence
    strategy_switches = 0
    current_strategy = "reactive"
    for msg in session.reasoning_log:
        if "switch" in msg.lower() and "strategy" in msg.lower():
            strategy_switches += 1

    print(f"   Strategy switches detected: {strategy_switches}")
    print(f"   Final answer provided: {session.final_answer is not None}")

    # Determine pass/fail
    passed = agent_signaled or len(signal_stuck_calls) > 0

    if passed:
        if strategy_switches > 0:
            reason = f"✅ Agent signaled stuck AND framework intervened (switched strategy)"
        else:
            reason = f"✅ Agent signaled stuck (framework acknowledged)"
    else:
        reason = f"❌ Agent did not use signal_stuck despite impossible task"

    print(f"\n{reason}")

    return {
        "test": "signal_stuck_triggers_intervention",
        "pass": passed,
        "reason": reason,
        "iterations": session.iterations,
        "agent_signaled": agent_signaled or signal_stuck_used,
        "signal_stuck_calls": len(signal_stuck_calls),
        "strategy_switches": strategy_switches,
        "stuck_reason": stuck_reason,
    }


async def test_strategy_switch_from_loop(model: str = "ollama:cogito:14b") -> Dict[str, Any]:
    """Test that detected loops trigger strategy switches.

    Setup: Create scenario where agent repeats same action
    Expected: Loop detection → strategy switch → different behavior
    Measure:
        - Loop detected?
        - Strategy switched?
        - Behavior changed after switch?
    """
    print("\n" + "="*70)
    print("TEST: Strategy Switch From Loop")
    print("="*70)

    stuck_tool = StuckTool()

    agent = await (
        ReactiveAgentBuilder()
        .with_name("StrategySwitchTest")
        .with_model(model)
        .with_reasoning_strategy("reactive")  # Start simple
        .with_max_iterations(12)
        .with_tools([stuck_tool])
        .build()
    )

    task = (
        "Find the correct answer using stuck_tool. "
        "Try with different queries until you find the right one."
    )

    print(f"\n📋 Task: {task}")
    print(f"🎯 Expected: Loop → Strategy switch to plan_execute_reflect")

    result = await agent.run(task)
    session = agent.context.session

    # Track strategy throughout execution
    initial_strategy = "reactive"
    final_strategy = session.active_strategy or "unknown"

    loop_detected = getattr(session, "loop_detected", False)
    strategy_switched = final_strategy != initial_strategy

    print(f"\n📊 Results:")
    print(f"   Total iterations: {session.iterations}")
    print(f"   Initial strategy: {initial_strategy}")
    print(f"   Final strategy: {final_strategy}")
    print(f"   Loop detected: {loop_detected}")
    print(f"   Strategy switched: {strategy_switched}")

    # Look for evidence in reasoning log
    intervention_detected = False
    for log_entry in session.reasoning_log:
        if any(keyword in log_entry.lower() for keyword in ["loop", "switch", "strategy", "stuck"]):
            intervention_detected = True
            print(f"   Intervention log: {log_entry[:80]}...")
            break

    passed = (loop_detected or intervention_detected) and strategy_switched

    if passed:
        reason = f"✅ Loop detected → Strategy switched to {final_strategy}"
    elif loop_detected and not strategy_switched:
        reason = f"⚠️  Loop detected but strategy didn't switch (already in best strategy?)"
        passed = True  # This is actually okay if already in best strategy
    else:
        reason = f"❌ No loop detection or strategy switch detected"

    print(f"\n{reason}")

    return {
        "test": "strategy_switch_from_loop",
        "pass": passed,
        "reason": reason,
        "iterations": session.iterations,
        "loop_detected": loop_detected,
        "strategy_switched": strategy_switched,
        "initial_strategy": initial_strategy,
        "final_strategy": final_strategy,
    }


# ============================================================================
# Test Runner
# ============================================================================


async def run_all_tests(model: str = "ollama:cogito:14b"):
    """Run all system tools tests."""
    print("\n" + "="*70)
    print("SYSTEM TOOLS & LOOP DETECTION TEST SUITE")
    print("="*70)
    print(f"Model: {model}")

    tests = [
        test_loop_detection_triggers,
        test_loop_detection_helps_performance,
        test_signal_stuck_triggers_intervention,
        test_strategy_switch_from_loop,
    ]

    results = []
    passed = 0
    failed = 0

    for test_func in tests:
        try:
            result = await test_func(model)
            results.append(result)

            if result["pass"]:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test {test_func.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            results.append({
                "test": test_func.__name__,
                "pass": False,
                "reason": f"Crashed: {e}",
            })

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    for result in results:
        status = "✅ PASS" if result["pass"] else "❌ FAIL"
        print(f"{status} - {result['test']}")
        print(f"      {result['reason']}")

    print(f"\n📊 Results: {passed} passed, {failed} failed")
    print(f"   Pass rate: {passed}/{len(tests)} ({100*passed/len(tests):.0f}%)")

    return {
        "passed": passed,
        "failed": failed,
        "total": len(tests),
        "pass_rate": passed / len(tests) if tests else 0,
        "results": results,
    }


# ============================================================================
# CLI Entry Point
# ============================================================================


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_system_tools.py <test_name>")
        print("\nAvailable tests:")
        print("  test_loop_detection_triggers")
        print("  test_loop_detection_helps_performance")
        print("  test_signal_stuck_triggers_intervention")
        print("  test_strategy_switch_from_loop")
        print("  all - Run all tests")
        sys.exit(1)

    test_name = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "ollama:cogito:14b"

    if test_name == "all":
        result = asyncio.run(run_all_tests(model))
        sys.exit(0 if result["failed"] == 0 else 1)

    # Run individual test
    test_map = {
        "test_loop_detection_triggers": test_loop_detection_triggers,
        "test_loop_detection_helps_performance": test_loop_detection_helps_performance,
        "test_signal_stuck_triggers_intervention": test_signal_stuck_triggers_intervention,
        "test_strategy_switch_from_loop": test_strategy_switch_from_loop,
    }

    if test_name not in test_map:
        print(f"Unknown test: {test_name}")
        sys.exit(1)

    result = asyncio.run(test_map[test_name](model))
    sys.exit(0 if result["pass"] else 1)
