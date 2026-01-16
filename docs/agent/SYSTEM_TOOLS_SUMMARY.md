# System Tools Implementation Summary

**Date:** January 13, 2026
**Status:** ✅ Core implementation complete

---

## What We Built

### 1. **SystemTool Base Class** - Minimal & Clean

**File:** `reactive_agents/core/tools/system_tool.py`

A lightweight extension of `Tool` that enforces:
- ✅ Context is **required** (not optional)
- ✅ Category is always **"system"** (immutable)
- ✅ Type safety through constructor validation

**That's it.** No abstractions, no complexity, no helper methods.

```python
class SystemTool(Tool):
    """Lightweight extension for framework system tools."""

    category: str = Field(default="system", frozen=True)
    context: "ContextProtocol" = Field(..., exclude=True)  # Required!

    def __init__(self, context: "ContextProtocol", **data):
        if context is None:
            raise ValueError(f"{self.__class__.__name__} requires context")
        super().__init__(context=context, category="system", **data)
```

**Just ~30 lines total.** Simple, clear, effective.

---

### 2. **Refactored FinalAnswerTool**

**File:** `reactive_agents/core/tools/default.py`

Updated to use `SystemTool` base class. No other changes.

```python
class FinalAnswerTool(SystemTool):
    name: str = Field(default="final_answer")
    description: str = Field(default="Provides final answer...")
    input_schema: type[ToolInput] | None = FinalAnswerInput

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        # Same as before - just extends SystemTool now
        self.context.session.final_answer = params.get("answer")
        return ToolResult.ok(value=answer, tool_name=self.name)
```

---

### 3. **Three Escape Hatch Tools**

**File:** `reactive_agents/core/tools/meta_actions.py`

All follow the same `SystemTool` pattern as `FinalAnswerTool`.

#### **A) SignalStuckTool**
Agent signals it's stuck and needs help.

```python
class SignalStuckTool(SystemTool):
    name: str = Field(default="signal_stuck")
    input_schema: type[ToolInput] | None = SignalStuckInput

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        # Set session flags
        self.context.session.agent_signaled_stuck = True
        self.context.session.stuck_reason = params.get("reason")

        # Log & emit event
        self.context.agent_logger.warning(f"🚨 Agent signaled stuck")
        self.context.emit_event("AGENT_STUCK_SIGNAL", {...})

        return ToolResult.ok(...)
```

**Agent usage:**
```python
await signal_stuck(
    reason="I've tried the same approach 3 times with no progress",
    attempted_approaches=["API call", "cache lookup", "estimation"]
)
```

#### **B) RequestStrategySwitchTool**
Agent requests a different reasoning strategy.

```python
class RequestStrategySwitchTool(SystemTool):
    name: str = Field(default="request_strategy_switch")
    input_schema: type[ToolInput] | None = RequestStrategySwitchInput

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        # Record the request
        self.context.session.strategy_switch_requested = True
        self.context.session.strategy_switch_reason = params.get("reason")
        self.context.session.preferred_strategy = params.get("preferred_strategy")

        # Log & emit
        self.context.agent_logger.info(f"🔄 Agent requested strategy switch")
        self.context.emit_event("STRATEGY_SWITCH_REQUESTED", {...})

        return ToolResult.ok(...)
```

**Agent usage:**
```python
await request_strategy_switch(
    reason="This task requires careful multi-step planning",
    preferred_strategy="plan_execute_reflect"
)
```

#### **C) RequestClarificationTool**
Agent asks for more information.

```python
class RequestClarificationTool(SystemTool):
    name: str = Field(default="request_clarification")
    input_schema: type[ToolInput] | None = RequestClarificationInput

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        # Record the clarification request
        question = params.get("question")
        blocking = params.get("blocking", False)

        # Add to session
        if not hasattr(self.context.session, "clarification_requests"):
            setattr(self.context.session, "clarification_requests", [])

        clarification_requests = getattr(self.context.session, "clarification_requests")
        clarification_requests.append({
            "question": question,
            "blocking": blocking,
            "iteration": self.context.session.iterations,
            "timestamp": time.time()
        })

        # Log & emit
        self.context.agent_logger.info(f"❓ Agent requested clarification")
        self.context.emit_event("CLARIFICATION_REQUESTED", {...})

        # Add nudge if blocking
        if blocking:
            self.context.context_manager.add_nudge(
                f"Clarification needed: {question}. Proceed with best info."
            )

        return ToolResult.ok(...)
```

**Agent usage:**
```python
await request_clarification(
    question="What time period should the analysis cover?",
    blocking=False
)
```

---

## Architecture Benefits

### ✅ Simple Pattern
- Follows existing `FinalAnswerTool` approach exactly
- No over-engineering, no abstractions
- Just `SystemTool` base class for type safety

### ✅ Type Safe
- Context cannot be None (enforced at construction)
- Category cannot be changed (frozen field)
- Clear contract through Python types

### ✅ Consistent
- All system tools follow same pattern
- Easy to add new system tools
- Familiar to developers

### ✅ Observable
- All actions logged via `agent_logger`
- All actions emit events via `emit_event()`
- Session state tracks everything

### ✅ Minimal Surface Area
- `SystemTool` is ~30 lines
- No helper methods, no abstractions
- Just type enforcement

---

## Next Steps - Integration

### 1. Add Fields to AgentSession

**File:** `reactive_agents/core/types/session_types.py`

Add these fields to `AgentSession`:

```python
class AgentSession(BaseModel):
    # ... existing fields ...

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

### 2. Inject Escape Hatch Tools

**File:** `reactive_agents/core/tools/tool_manager.py`

After injecting `FinalAnswerTool`, also inject escape hatches:

```python
# In ToolManager.__init__, after FinalAnswerTool injection:

if getattr(self.context, 'enable_escape_hatches', True):
    if self.tool_logger:
        self.tool_logger.info("Injecting escape hatch tools")

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
```

### 3. Handle Signals in Execution Engine

**File:** `reactive_agents/core/engine/execution_engine.py`

In `_execute_loop()`, after each iteration check for signals:

```python
# After strategy_result = await self.strategy_manager.execute_iteration(...)

# Check if agent signaled stuck
if self.context.session.agent_signaled_stuck:
    await self._handle_agent_stuck(task, reasoning_context)

# Check if agent requested strategy switch
if self.context.session.strategy_switch_requested:
    await self._handle_strategy_switch_request(task, reasoning_context)
```

Add handler methods:

```python
async def _handle_agent_stuck(self, task: str, reasoning_context: ReasoningContext):
    """Handle agent's stuck signal."""
    reason = self.context.session.stuck_reason
    self.agent_logger.warning(f"Handling stuck signal: {reason}")

    # Switch to most robust strategy
    if self.strategy_manager.get_current_strategy_name() != "plan_execute_reflect":
        await self.strategy_manager.switch_strategy(
            "plan_execute_reflect", task, reasoning_context
        )
    else:
        # Already in best strategy, add strong nudge
        self.context_manager.add_nudge(
            f"Framework acknowledged stuck signal: {reason}. "
            f"Break problem into smaller steps or request clarification."
        )

    # Reset flag
    self.context.session.agent_signaled_stuck = False

async def _handle_strategy_switch_request(self, task: str, reasoning_context: ReasoningContext):
    """Handle agent's strategy switch request."""
    preferred = self.context.session.preferred_strategy
    reason = self.context.session.strategy_switch_reason

    if preferred and preferred in self.strategy_manager.strategies:
        self.agent_logger.info(f"Honoring strategy switch to {preferred}")
        await self.strategy_manager.switch_strategy(preferred, task, reasoning_context)
    else:
        # Framework decides
        current = self.strategy_manager.get_current_strategy_name()
        target = "plan_execute_reflect" if current == "reactive" else "reflect_decide_act"
        await self.strategy_manager.switch_strategy(target, task, reasoning_context)

    # Reset flag
    self.context.session.strategy_switch_requested = False
```

### 4. Add Builder Configuration

**File:** `reactive_agents/app/builders/agent.py`

Add configuration method:

```python
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
```

---

## Testing

Create tests for each tool:

```python
# tests/unit/core/tools/test_system_tools.py

async def test_signal_stuck_tool():
    """Test signal_stuck sets session flags."""
    context = create_test_context()
    tool = SignalStuckTool(context)

    result = await tool.use({"reason": "repeated failures"})

    assert context.session.agent_signaled_stuck == True
    assert "repeated failures" in context.session.stuck_reason
    assert result.success == True

async def test_request_strategy_switch_tool():
    """Test request_strategy_switch records request."""
    context = create_test_context()
    tool = RequestStrategySwitchTool(context)

    result = await tool.use({
        "reason": "Need planning",
        "preferred_strategy": "plan_execute_reflect"
    })

    assert context.session.strategy_switch_requested == True
    assert context.session.preferred_strategy == "plan_execute_reflect"
    assert result.success == True

async def test_request_clarification_tool():
    """Test request_clarification records question."""
    context = create_test_context()
    tool = RequestClarificationTool(context)

    result = await tool.use({
        "question": "What time period?",
        "blocking": False
    })

    assert len(context.session.clarification_requests) == 1
    assert context.session.clarification_requests[0]["question"] == "What time period?"
    assert result.success == True
```

---

## Summary

We created a **minimal, clean system** for escape hatch tools:

1. ✅ **SystemTool** base class (~30 lines, type safety only)
2. ✅ **FinalAnswerTool** refactored to use SystemTool
3. ✅ **Three escape hatch tools** (signal_stuck, request_strategy_switch, request_clarification)
4. ✅ All follow the same simple pattern
5. ✅ No over-engineering, no complexity

**Ready for integration** - just need to:
- Add session fields
- Inject tools in ToolManager
- Handle signals in ExecutionEngine
- Add builder configuration
- Write tests

This gives agents **strategic self-correction** capabilities without excessive control - they can signal issues, framework responds appropriately.
