# Escape Hatches & Loop Detection Design

**Date:** January 13, 2026
**Pattern:** Following `final_answer` built-in tool approach
**Philosophy:** Strategic self-correction without excessive agent control

---

## Overview

Following the pattern of `FinalAnswerTool` (category="system", auto-injected, direct context access), we'll add **escape hatch tools** that allow agents to signal when they're stuck or need help, plus **automatic loop detection** that triggers interventions.

### Key Principle

> **Balance**: Give agents enough control to self-correct, but maintain framework guardrails to prevent counterproductive behavior.

---

## 1. Built-In Escape Hatch Tools

Following the `FinalAnswerTool` pattern, create system-category tools that agents can invoke.

### 1.1 `signal_stuck` Tool

**Purpose**: Agent acknowledges it's stuck and requests framework intervention

```python
# reactive_agents/core/tools/meta_actions.py

class SignalStuckInput(ToolInput):
    """Input schema for signal_stuck tool."""

    reason: str = Field(
        ...,
        description="Why the agent believes it's stuck (e.g., 'repeated same action', 'no progress', 'missing information')"
    )
    attempted_approaches: Optional[List[str]] = Field(
        default=None,
        description="Approaches already tried that didn't work"
    )


class SignalStuckTool(Tool):
    """Tool for agent to signal it's stuck and needs help.

    When invoked:
    1. Logs the stuck signal
    2. Sets a flag in session for framework to handle
    3. Can trigger strategy switch or escalation

    This is a "graceful stuck" signal vs. hitting max_iterations.
    """

    name: str = Field(default="signal_stuck")
    description: str = Field(
        default="Signal that you're stuck and need framework intervention. "
                "Use when: repeated attempts fail, no progress is being made, "
                "or you lack necessary information to proceed."
    )
    category: str = Field(default="system")

    context: Optional["ContextProtocol"] = Field(default=None, exclude=True)

    def __init__(self, context: "ContextProtocol", **data):
        super().__init__(
            name="signal_stuck",
            description=self.description,
            function=None,
            input_schema=SignalStuckInput,
            category="system",
            **data
        )
        self.context = context

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the signal_stuck tool."""
        reason = params.get("reason")
        attempted = params.get("attempted_approaches", [])

        if not reason:
            return ToolResult.fail(
                error="Missing required parameter 'reason'",
                tool_name=self.name
            )

        # Set stuck flag in session
        if self.context.session:
            self.context.session.agent_signaled_stuck = True
            self.context.session.stuck_reason = reason
            self.context.session.attempted_approaches = attempted

        # Log for visibility
        if self.context.agent_logger:
            self.context.agent_logger.warning(
                f"🚨 Agent signaled stuck: {reason}"
            )

        # Emit event for observers
        self.context.emit_event(
            "AGENT_STUCK_SIGNAL",
            {
                "reason": reason,
                "attempted_approaches": attempted,
                "iteration": self.context.session.iterations
            }
        )

        return ToolResult.ok(
            value="Framework notified. Will attempt intervention.",
            tool_name=self.name
        )
```

### 1.2 `request_strategy_switch` Tool

**Purpose**: Agent explicitly requests a strategy change

```python
class RequestStrategySwitchInput(ToolInput):
    """Input schema for request_strategy_switch tool."""

    reason: str = Field(
        ...,
        description="Why a strategy switch is needed"
    )
    preferred_strategy: Optional[str] = Field(
        default=None,
        description="Preferred new strategy (e.g., 'plan_execute_reflect', 'reactive'). If not specified, framework decides."
    )


class RequestStrategySwitchTool(Tool):
    """Tool for agent to request a strategy change.

    When invoked:
    1. Validates the request
    2. Sets a flag for execution engine to handle
    3. Framework decides whether to honor the request

    Note: Framework has final say - agent makes a request, not a command.
    """

    name: str = Field(default="request_strategy_switch")
    description: str = Field(
        default="Request a switch to a different reasoning strategy. "
                "Use when current approach isn't working well for the task."
    )
    category: str = Field(default="system")

    context: Optional["ContextProtocol"] = Field(default=None, exclude=True)

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the request_strategy_switch tool."""
        reason = params.get("reason")
        preferred = params.get("preferred_strategy")

        if not reason:
            return ToolResult.fail(
                error="Missing required parameter 'reason'",
                tool_name=self.name
            )

        # Set strategy switch request in session
        if self.context.session:
            self.context.session.strategy_switch_requested = True
            self.context.session.strategy_switch_reason = reason
            self.context.session.preferred_strategy = preferred

        # Log for visibility
        if self.context.agent_logger:
            target = preferred or "framework-decided"
            self.context.agent_logger.info(
                f"🔄 Agent requested strategy switch: {reason} (target: {target})"
            )

        # Emit event
        self.context.emit_event(
            "STRATEGY_SWITCH_REQUESTED",
            {
                "reason": reason,
                "preferred_strategy": preferred,
                "current_strategy": self.context.reasoning_strategy,
                "iteration": self.context.session.iterations
            }
        )

        return ToolResult.ok(
            value=f"Strategy switch requested. Framework will evaluate at next iteration.",
            tool_name=self.name
        )
```

### 1.3 `request_clarification` Tool

**Purpose**: Agent asks for clarification or additional information

```python
class RequestClarificationInput(ToolInput):
    """Input schema for request_clarification tool."""

    question: str = Field(
        ...,
        description="What clarification or additional information is needed"
    )
    blocking: bool = Field(
        default=False,
        description="Whether this blocks progress (true) or is just helpful (false)"
    )


class RequestClarificationTool(Tool):
    """Tool for agent to request clarification from user or system.

    When invoked:
    1. Records the clarification request
    2. Can pause execution if blocking
    3. Provides a way for agent to ask for help
    """

    name: str = Field(default="request_clarification")
    description: str = Field(
        default="Request clarification or additional information needed to proceed. "
                "Use when task requirements are ambiguous or missing key details."
    )
    category: str = Field(default="system")

    context: Optional["ContextProtocol"] = Field(default=None, exclude=True)

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the request_clarification tool."""
        question = params.get("question")
        blocking = params.get("blocking", False)

        if not question:
            return ToolResult.fail(
                error="Missing required parameter 'question'",
                tool_name=self.name
            )

        # Add to session clarification requests
        if self.context.session:
            if not hasattr(self.context.session, 'clarification_requests'):
                self.context.session.clarification_requests = []

            self.context.session.clarification_requests.append({
                "question": question,
                "blocking": blocking,
                "iteration": self.context.session.iterations,
                "timestamp": time.time()
            })

        # Log
        if self.context.agent_logger:
            priority = "BLOCKING" if blocking else "non-blocking"
            self.context.agent_logger.info(
                f"❓ Agent requested clarification ({priority}): {question}"
            )

        # Emit event
        self.context.emit_event(
            "CLARIFICATION_REQUESTED",
            {
                "question": question,
                "blocking": blocking,
                "iteration": self.context.session.iterations
            }
        )

        # If blocking, could pause or add nudge
        if blocking and self.context.context_manager:
            self.context.context_manager.add_nudge(
                f"Clarification needed: {question}. "
                f"Proceed with best available information or signal stuck."
            )

        return ToolResult.ok(
            value="Clarification request recorded. Proceeding with available information.",
            tool_name=self.name
        )
```

---

## 2. Loop Detection System

### 2.1 Session-Based Tool Call Tracking

**Add to `AgentSession` in `session_types.py`:**

```python
class ToolCallRecord(BaseModel):
    """Record of a tool call for loop detection."""
    tool_name: str
    parameters: Dict[str, Any]
    iteration: int
    timestamp: float
    result_success: bool


class AgentSession(BaseModel):
    """Session data for a single agent run."""

    # ... existing fields ...

    # Tool call tracking for loop detection
    tool_call_history: List[ToolCallRecord] = Field(default_factory=list)

    # Agent self-correction signals
    agent_signaled_stuck: bool = False
    stuck_reason: Optional[str] = None
    attempted_approaches: List[str] = Field(default_factory=list)

    # Strategy switch requests
    strategy_switch_requested: bool = False
    strategy_switch_reason: Optional[str] = None
    preferred_strategy: Optional[str] = None

    # Clarification requests
    clarification_requests: List[Dict[str, Any]] = Field(default_factory=list)
```

### 2.2 Loop Detector Component

```python
# reactive_agents/core/reasoning/monitors/loop_detector.py

import hashlib
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class LoopDetectionResult:
    """Result of loop detection analysis."""
    loop_detected: bool
    loop_type: Optional[str] = None  # 'exact_repeat', 'parameter_cycle', 'tool_sequence'
    repeated_action: Optional[str] = None
    repetition_count: int = 0
    recommendation: Optional[str] = None  # 'switch_strategy', 'add_nudge', 'escalate'
    confidence: float = 0.0


class LoopDetector:
    """Detects loops in agent tool usage patterns.

    Integrates with existing session tool_call_history to detect:
    1. Exact repeated tool calls (same tool + same params)
    2. Cyclic parameter patterns (tool cycling through same param sets)
    3. Tool sequence loops (A->B->C->A->B->C pattern)
    """

    def __init__(self, exact_repeat_window: int = 3, cycle_window: int = 6):
        """Initialize loop detector.

        Args:
            exact_repeat_window: How many identical calls in a row = loop
            cycle_window: Window size for detecting cyclic patterns
        """
        self.exact_repeat_window = exact_repeat_window
        self.cycle_window = cycle_window

    def check_for_loops(
        self,
        tool_call_history: List[Dict[str, Any]]
    ) -> LoopDetectionResult:
        """Check if recent tool calls indicate a loop.

        Args:
            tool_call_history: List of tool call records from session

        Returns:
            LoopDetectionResult with findings
        """
        if len(tool_call_history) < self.exact_repeat_window:
            return LoopDetectionResult(loop_detected=False)

        # Check 1: Exact repeated calls
        exact_result = self._check_exact_repeats(tool_call_history)
        if exact_result.loop_detected:
            return exact_result

        # Check 2: Cyclic patterns
        if len(tool_call_history) >= self.cycle_window:
            cycle_result = self._check_cyclic_patterns(tool_call_history)
            if cycle_result.loop_detected:
                return cycle_result

        return LoopDetectionResult(loop_detected=False)

    def _check_exact_repeats(
        self,
        tool_call_history: List[Dict[str, Any]]
    ) -> LoopDetectionResult:
        """Check for exact repeated tool calls."""
        recent = tool_call_history[-self.exact_repeat_window:]

        # Create signatures for each call
        signatures = [self._tool_call_signature(call) for call in recent]

        # Check if all recent signatures are identical
        if len(set(signatures)) == 1:
            repeated_call = recent[0]
            return LoopDetectionResult(
                loop_detected=True,
                loop_type='exact_repeat',
                repeated_action=f"{repeated_call['tool_name']}({self._simplify_params(repeated_call['parameters'])})",
                repetition_count=self.exact_repeat_window,
                recommendation='switch_strategy',
                confidence=0.95
            )

        return LoopDetectionResult(loop_detected=False)

    def _check_cyclic_patterns(
        self,
        tool_call_history: List[Dict[str, Any]]
    ) -> LoopDetectionResult:
        """Check for cyclic patterns (A->B->C->A->B->C)."""
        recent = tool_call_history[-self.cycle_window:]
        signatures = [self._tool_call_signature(call) for call in recent]

        # Check if second half matches first half (indicating cycle)
        mid = len(signatures) // 2
        first_half = signatures[:mid]
        second_half = signatures[mid:mid+len(first_half)]

        if first_half == second_half and len(first_half) >= 2:
            return LoopDetectionResult(
                loop_detected=True,
                loop_type='parameter_cycle',
                repeated_action=f"Cycle: {' -> '.join([s[:20] for s in first_half])}",
                repetition_count=2,
                recommendation='add_nudge',
                confidence=0.85
            )

        return LoopDetectionResult(loop_detected=False)

    def _tool_call_signature(self, tool_call: Dict[str, Any]) -> str:
        """Create a signature for a tool call.

        Signature includes tool name + parameters for exact matching.
        """
        tool_name = tool_call.get('tool_name', '')
        parameters = tool_call.get('parameters', {})

        # Create deterministic string representation
        param_str = json.dumps(parameters, sort_keys=True)
        signature = f"{tool_name}::{param_str}"

        return hashlib.md5(signature.encode()).hexdigest()

    def _simplify_params(self, params: Dict[str, Any]) -> str:
        """Simplify parameters for display."""
        if not params:
            return ""

        # Show first 2 params or truncate
        items = list(params.items())[:2]
        return ", ".join([f"{k}={v}" for k, v in items])
```

---

## 3. Integration with Execution Engine

### 3.1 ToolManager Integration

**Modify `tool_manager.py` to inject escape hatch tools:**

```python
# In ToolManager.__init__, after injecting FinalAnswerTool:

def __init__(self, context: "AgentContext", tools: Optional[List[ToolProtocol]] = None):
    # ... existing code ...

    # Inject built-in system tools
    if self.tool_logger:
        self.tool_logger.info("Injecting internal 'final_answer' tool.")
    internal_final_answer_tool = FinalAnswerTool(context=self.context)
    self.tools.append(internal_final_answer_tool)

    # Inject escape hatch tools (if enabled in config)
    if getattr(self.context, 'enable_escape_hatches', True):
        if self.tool_logger:
            self.tool_logger.info("Injecting escape hatch tools (signal_stuck, request_strategy_switch, request_clarification)")

        from reactive_agents.core.tools.meta_actions import (
            SignalStuckTool,
            RequestStrategySwitchTool,
            RequestClarificationTool
        )

        self.tools.extend([
            SignalStuckTool(context=self.context),
            RequestStrategySwitchTool(context=self.context),
            RequestClarificationTool(context=self.context)
        ])

    self.register_tools()
```

### 3.2 Execution Engine Integration

**Modify `execution_engine.py:_execute_loop()` to check for loops and handle escape hatches:**

```python
# In ExecutionEngine.__init__, add loop detector:
def __init__(self, agent: "Agent"):
    # ... existing code ...

    # Initialize loop detector
    from reactive_agents.core.reasoning.monitors.loop_detector import LoopDetector
    self.loop_detector = LoopDetector(
        exact_repeat_window=3,
        cycle_window=6
    )

# In _execute_loop(), after each iteration:
async def _execute_loop(self, task: str, cancellation_event, reasoning_context) -> Dict[str, Any]:
    # ... existing loop setup ...

    while self._should_continue():
        # ... existing iteration code ...

        # Execute one iteration
        strategy_result = await self.strategy_manager.execute_iteration(
            task, reasoning_context
        )

        # === NEW: Loop Detection ===
        loop_check = self.loop_detector.check_for_loops(
            self.context.session.tool_call_history
        )

        if loop_check.loop_detected:
            self.agent_logger.warning(
                f"🔁 Loop detected ({loop_check.loop_type}): "
                f"{loop_check.repeated_action} "
                f"({loop_check.repetition_count}x)"
            )

            # Handle based on recommendation
            if loop_check.recommendation == 'switch_strategy':
                # Auto-trigger strategy switch
                await self._handle_loop_detected(loop_check, task, reasoning_context)
            elif loop_check.recommendation == 'add_nudge':
                # Add nudge to agent
                self.context_manager.add_nudge(
                    f"You appear to be in a loop: {loop_check.repeated_action}. "
                    f"Try a different approach or use signal_stuck if you need help."
                )

        # === NEW: Check Agent Signals ===
        if self.context.session.agent_signaled_stuck:
            self.agent_logger.warning(
                f"🚨 Agent signaled stuck: {self.context.session.stuck_reason}"
            )
            await self._handle_agent_stuck(task, reasoning_context)

        if self.context.session.strategy_switch_requested:
            self.agent_logger.info(
                f"🔄 Agent requested strategy switch: {self.context.session.strategy_switch_reason}"
            )
            await self._handle_strategy_switch_request(task, reasoning_context)

        # ... rest of iteration handling ...

async def _handle_loop_detected(
    self,
    loop_check: LoopDetectionResult,
    task: str,
    reasoning_context: ReasoningContext
):
    """Handle detected loop by switching strategy or escalating."""
    current_strategy = self.strategy_manager.get_current_strategy_name()

    # If we're in reactive and loop detected, switch to plan_execute_reflect
    if current_strategy == "reactive":
        self.agent_logger.info(
            "🔄 Loop detected in REACTIVE strategy. Switching to PLAN_EXECUTE_REFLECT."
        )
        await self.strategy_manager.switch_strategy(
            "plan_execute_reflect",
            task,
            reasoning_context
        )

        # Add nudge explaining the switch
        self.context_manager.add_nudge(
            f"Framework switched to planning strategy due to detected loop. "
            f"Previous approach: {loop_check.repeated_action} was repeated {loop_check.repetition_count} times."
        )
    else:
        # Already in a complex strategy, add strong nudge
        self.context_manager.add_nudge(
            f"CRITICAL: Loop detected - {loop_check.repeated_action} repeated {loop_check.repetition_count} times. "
            f"You MUST try a completely different approach or use signal_stuck if unable to proceed."
        )

async def _handle_agent_stuck(
    self,
    task: str,
    reasoning_context: ReasoningContext
):
    """Handle agent's stuck signal."""
    # Log attempted approaches
    if self.context.session.attempted_approaches:
        self.agent_logger.info(
            f"Agent tried: {', '.join(self.context.session.attempted_approaches)}"
        )

    # Strategy: Switch to most robust strategy
    current_strategy = self.strategy_manager.get_current_strategy_name()
    if current_strategy != "plan_execute_reflect":
        self.agent_logger.info(
            "Agent stuck. Escalating to PLAN_EXECUTE_REFLECT strategy."
        )
        await self.strategy_manager.switch_strategy(
            "plan_execute_reflect",
            task,
            reasoning_context
        )
    else:
        # Already in best strategy, provide strong nudge
        self.context_manager.add_nudge(
            f"Framework acknowledged your stuck signal. Reason: {self.context.session.stuck_reason}. "
            f"Decompose the problem into smaller steps or request clarification if needed."
        )

    # Reset the stuck flag for next iteration
    self.context.session.agent_signaled_stuck = False

async def _handle_strategy_switch_request(
    self,
    task: str,
    reasoning_context: ReasoningContext
):
    """Handle agent's strategy switch request."""
    preferred = self.context.session.preferred_strategy
    reason = self.context.session.strategy_switch_reason

    # Evaluate if request is reasonable
    if preferred and preferred in self.strategy_manager.strategies:
        self.agent_logger.info(
            f"Honoring agent's strategy switch request to {preferred}"
        )
        await self.strategy_manager.switch_strategy(
            preferred,
            task,
            reasoning_context
        )
    else:
        # Agent didn't specify or invalid, framework decides
        current = self.strategy_manager.get_current_strategy_name()
        if current == "reactive":
            target = "plan_execute_reflect"
        else:
            target = "reflect_decide_act"  # Try different approach

        self.agent_logger.info(
            f"Agent requested switch (reason: {reason}). "
            f"Framework selecting {target}."
        )
        await self.strategy_manager.switch_strategy(
            target,
            task,
            reasoning_context
        )

    # Reset flag
    self.context.session.strategy_switch_requested = False
```

---

## 4. Configuration and Control

### 4.1 Builder API

```python
# In ReactiveAgentBuilder:

def with_escape_hatches(self, enabled: bool = True) -> "ReactiveAgentBuilder":
    """Enable or disable escape hatch tools.

    When enabled, agents have access to:
    - signal_stuck: Alert framework when stuck
    - request_strategy_switch: Request strategy change
    - request_clarification: Ask for more information

    Args:
        enabled: Whether to enable escape hatches (default: True)
    """
    self.config.enable_escape_hatches = enabled
    return self

def with_loop_detection(
    self,
    enabled: bool = True,
    exact_repeat_window: int = 3,
    cycle_window: int = 6
) -> "ReactiveAgentBuilder":
    """Configure automatic loop detection.

    Args:
        enabled: Whether to enable loop detection (default: True)
        exact_repeat_window: Consecutive identical calls = loop (default: 3)
        cycle_window: Window for detecting cyclic patterns (default: 6)
    """
    self.config.enable_loop_detection = enabled
    self.config.loop_detection_exact_window = exact_repeat_window
    self.config.loop_detection_cycle_window = cycle_window
    return self
```

### 4.2 Usage Example

```python
agent = await (
    ReactiveAgentBuilder()
    .with_name("SmartAgent")
    .with_model(Provider.OLLAMA, "cogito:14b")
    .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
    .with_dynamic_strategy_switching(True)  # Existing
    .with_loop_detection(enabled=True, exact_repeat_window=3)  # NEW
    .with_escape_hatches(enabled=True)  # NEW
    .with_custom_tools([my_tool])
    .build()
)

# Agent now has access to:
# - final_answer (existing)
# - signal_stuck (new)
# - request_strategy_switch (new)
# - request_clarification (new)
# Plus automatic loop detection with interventions
```

---

## 5. Expected Behavior

### Scenario 1: Agent Detects Own Loop

```
Agent: calculate(15*23) -> 345
Agent: get_weather(Tokyo) -> Sunny
Agent: calculate(15*23) -> 345
Agent: get_weather(Tokyo) -> Sunny
Agent: [Realizes repetition] signal_stuck(reason="I'm repeating the same actions without progress")
Framework: ✅ Acknowledged stuck signal. Switching to PLAN_EXECUTE_REFLECT strategy.
Agent: [Now with planning] Creates plan with proper steps
```

### Scenario 2: Framework Detects Loop

```
Agent: call_api(endpoint="/data") -> timeout
Agent: call_api(endpoint="/data") -> timeout
Agent: call_api(endpoint="/data") -> timeout
Framework: 🔁 Loop detected (exact_repeat): call_api repeated 3x. Switching strategy.
Framework: Switched REACTIVE → PLAN_EXECUTE_REFLECT
Agent: [Receives nudge] "Framework switched strategy due to loop. Try different approach."
Agent: [Plans alternative] "Try different endpoint or add error handling"
```

### Scenario 3: Agent Requests Strategy Switch

```
Agent: [Working on complex task with REACTIVE strategy]
Agent: [After 2 iterations] "This task requires careful planning"
Agent: request_strategy_switch(reason="Task requires multi-step planning", preferred_strategy="plan_execute_reflect")
Framework: ✅ Honoring strategy switch request to plan_execute_reflect
Agent: [Now planning] Creates structured plan
```

---

## 6. Advantages of This Approach

### ✅ Follows Existing Patterns
- Uses `FinalAnswerTool` as template
- Integrates with existing ToolManager injection
- Leverages AgentSession for state

### ✅ Balanced Control
- Agents can signal issues (signal_stuck, request_switch)
- Framework has final decision authority
- Automatic safety nets (loop detection)

### ✅ Minimal Invasiveness
- No breaking changes to existing APIs
- Opt-in via builder configuration
- Degrades gracefully if disabled

### ✅ Observable & Debuggable
- All signals logged
- Events emitted for monitoring
- Clear state in session

### ✅ Extensible
- Easy to add more escape hatch tools
- Loop detection can be enhanced
- Framework can learn which interventions work

---

## 7. Implementation Checklist

- [ ] Create `meta_actions.py` with three escape hatch tools
- [ ] Create `loop_detector.py` with loop detection logic
- [ ] Add fields to `AgentSession` for tracking
- [ ] Modify `ToolManager` to inject escape hatch tools
- [ ] Modify `ExecutionEngine` to use loop detector
- [ ] Add handler methods to `ExecutionEngine`
- [ ] Add builder configuration methods
- [ ] Create tests for each escape hatch tool
- [ ] Create tests for loop detection
- [ ] Create integration tests
- [ ] Update documentation

---

## 8. Testing Strategy

### Unit Tests

```python
def test_signal_stuck_tool():
    """Test signal_stuck tool sets session flags."""
    # Arrange
    context = create_test_context()
    tool = SignalStuckTool(context)

    # Act
    result = await tool.use({"reason": "repeated failures"})

    # Assert
    assert context.session.agent_signaled_stuck == True
    assert "repeated failures" in context.session.stuck_reason
    assert result.success == True

def test_loop_detector_exact_repeats():
    """Test loop detector catches exact repeats."""
    # Arrange
    detector = LoopDetector(exact_repeat_window=3)
    history = [
        {"tool_name": "calc", "parameters": {"expr": "2+2"}},
        {"tool_name": "calc", "parameters": {"expr": "2+2"}},
        {"tool_name": "calc", "parameters": {"expr": "2+2"}},
    ]

    # Act
    result = detector.check_for_loops(history)

    # Assert
    assert result.loop_detected == True
    assert result.loop_type == "exact_repeat"
    assert result.repetition_count == 3
```

### Integration Tests

```python
async def test_loop_triggers_strategy_switch():
    """Test that detected loop triggers automatic strategy switch."""
    # Create agent with loop detection
    agent = await (
        ReactiveAgentBuilder()
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_loop_detection(enabled=True, exact_repeat_window=3)
        .with_custom_tools([repeating_tool])
        .build()
    )

    # Run task that will loop
    result = await agent.run("Use repeating_tool to solve this")

    # Assert loop was detected and handled
    assert result.session.tool_call_history.count("repeating_tool") >= 3
    assert result.final_strategy != "reactive"  # Switched away
```

---

## Summary

This design provides **strategic escape hatches** that give agents self-correction capabilities without excessive control, following the proven `final_answer` tool pattern. Combined with automatic loop detection, it creates a balanced system where:

1. **Agents can self-signal** when stuck or needing help
2. **Framework automatically detects** loops and patterns
3. **Interventions are measured** - nudges, strategy switches, escalation
4. **Control stays with framework** - agents request, framework decides

This should dramatically improve the test pass rate while maintaining a clean, extensible architecture.
