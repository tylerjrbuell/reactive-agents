# Loop Intervention Architecture - Proper System Integration

**Date:** January 15, 2026
**Status:** Design Proposal
**Goal:** Implement graduated loop intervention that fits existing architecture

---

## Problem Analysis

### Current Issue
Loop detection identifies loops but **interventions are ineffective**:
1. Loop detected → flag set → handler called
2. Handler adds nudge OR switches strategy
3. **Flag immediately reset** → no persistent memory
4. **Nudges are suggestions** → LLM can ignore
5. **No hard constraints** → same tool can be called again
6. Loop continues indefinitely

### Root Cause
**Soft interventions without enforcement mechanisms**

---

## Architectural Principles

Following the existing framework patterns:

1. **SOLID Design**
   - Single Responsibility Principle
   - Dependency Injection
   - Interface Segregation

2. **Policy-Based Configuration**
   - Strategy Pattern for intervention policies
   - Builder API for user configuration
   - Sensible defaults

3. **Event-Driven Communication**
   - Events for state changes
   - Observable for monitoring
   - Decoupled components

4. **State Machine Pattern**
   - Well-defined states
   - Clear transitions
   - Predictable behavior

---

## Solution Architecture

### 1. InterventionPolicy System (Strategy Pattern)

**Location:** `reactive_agents/core/engine/intervention_policy.py`

**Purpose:** Defines **what** happens at each escalation level

```python
from typing import Protocol, Dict, Any
from dataclasses import dataclass
from enum import Enum


class InterventionLevel(Enum):
    """Escalation levels for loop intervention."""
    NONE = 0          # No intervention yet
    WARNING = 1       # First detection - soft guidance
    RESTRICTION = 2   # Second detection - enforce constraints
    TERMINATION = 3   # Third detection - hard stop


@dataclass
class InterventionAction:
    """Action to take when intervening on a loop."""
    level: InterventionLevel
    add_nudge: bool = False
    nudge_message: str = ""
    switch_strategy: bool = False
    target_strategy: str = ""
    restrict_tool: bool = False
    tool_name: str = ""
    restriction_iterations: int = 0
    terminate: bool = False
    termination_status: str = ""


class InterventionPolicyProtocol(Protocol):
    """Protocol for intervention policy implementations."""

    def determine_action(
        self,
        current_level: InterventionLevel,
        loop_details: Dict[str, Any],
        current_strategy: str,
    ) -> InterventionAction:
        """Determine what action to take for this intervention."""
        ...


class GraduatedInterventionPolicy:
    """Default graduated intervention policy - escalates over 3 levels.

    Level 1 (WARNING): Add guidance nudge
    Level 2 (RESTRICTION): Switch strategy + restrict tool
    Level 3 (TERMINATION): Hard stop with failure status
    """

    def __init__(
        self,
        warning_iterations: int = 2,  # How long to restrict tool
        target_strategy: str = "plan_execute_reflect",  # Strategy for level 2
    ):
        self.warning_iterations = warning_iterations
        self.target_strategy = target_strategy

    def determine_action(
        self,
        current_level: InterventionLevel,
        loop_details: Dict[str, Any],
        current_strategy: str,
    ) -> InterventionAction:
        """Determine intervention based on escalation level."""
        tool_name = loop_details.get("tool_name", "unknown")
        loop_type = loop_details.get("type", "unknown")
        loop_length = loop_details.get("length", 0)

        if current_level == InterventionLevel.NONE:
            # First detection - WARNING level
            return InterventionAction(
                level=InterventionLevel.WARNING,
                add_nudge=True,
                nudge_message=(
                    f"⚠️ Loop pattern detected: You've called {tool_name} "
                    f"{loop_length} times with the same parameters. "
                    f"This approach may not be working. Try a different tool or approach."
                ),
            )

        elif current_level == InterventionLevel.WARNING:
            # Second detection - RESTRICTION level
            return InterventionAction(
                level=InterventionLevel.RESTRICTION,
                add_nudge=True,
                nudge_message=(
                    f"🚨 LOOP DETECTED ({loop_type}): {tool_name} has been "
                    f"called {loop_length} times. Switching to structured planning "
                    f"and temporarily restricting this tool to force exploration "
                    f"of alternatives."
                ),
                switch_strategy=True if current_strategy != self.target_strategy else False,
                target_strategy=self.target_strategy,
                restrict_tool=True,
                tool_name=tool_name,
                restriction_iterations=self.warning_iterations,
            )

        else:  # RESTRICTION or higher
            # Third detection - TERMINATION
            return InterventionAction(
                level=InterventionLevel.TERMINATION,
                terminate=True,
                termination_status="LOOP_FAILURE",
                add_nudge=True,
                nudge_message=(
                    f"❌ TERMINAL LOOP: Despite multiple interventions, "
                    f"you continue to call {tool_name} repeatedly. "
                    f"Task cannot be completed with current approach."
                ),
            )


class AggressiveInterventionPolicy(GraduatedInterventionPolicy):
    """More aggressive - skips warning, goes straight to restriction."""

    def determine_action(
        self,
        current_level: InterventionLevel,
        loop_details: Dict[str, Any],
        current_strategy: str,
    ) -> InterventionAction:
        """Skip warning level for high-confidence loops."""
        if current_level == InterventionLevel.NONE:
            # Go straight to restriction if confidence is high
            confidence = loop_details.get("confidence", 0.0)
            if confidence >= 0.95:
                # Treat as second-level intervention
                return super().determine_action(
                    InterventionLevel.WARNING,  # Escalate immediately
                    loop_details,
                    current_strategy,
                )

        return super().determine_action(current_level, loop_details, current_strategy)


class PermissiveInterventionPolicy(GraduatedInterventionPolicy):
    """More permissive - allows more retries before restricting."""

    def __init__(self):
        super().__init__(warning_iterations=4)  # Longer restriction time

    def determine_action(
        self,
        current_level: InterventionLevel,
        loop_details: Dict[str, Any],
        current_strategy: str,
    ) -> InterventionAction:
        """Add extra warning level before restriction."""
        if current_level == InterventionLevel.WARNING:
            # Check if this is first or second warning
            loop_count = loop_details.get("loop_length", 0)
            if loop_count < 5:  # Allow up to 5 repetitions before restricting
                # Stay at warning level
                return InterventionAction(
                    level=InterventionLevel.WARNING,
                    add_nudge=True,
                    nudge_message=(
                        f"⚠️ Repeated action detected. Consider trying "
                        f"a different approach if current one isn't working."
                    ),
                )

        return super().determine_action(current_level, loop_details, current_strategy)
```

**Benefits:**
- ✅ **Policy Pattern**: Easy to swap policies (Graduated, Aggressive, Permissive)
- ✅ **Configurable**: Users can create custom policies
- ✅ **Testable**: Each policy can be unit tested independently
- ✅ **Clear Intent**: Each intervention level has defined actions

---

### 2. Tool Restriction System (Extends ToolGuard)

**Location:** `reactive_agents/core/tools/tool_guard.py` (extend existing)

**Purpose:** **Enforces** restrictions decided by intervention policy

```python
# Add to existing ToolGuard class:

class ToolGuard:
    """Middleware for enforcing tool usage policies."""

    def __init__(self):
        self.usage_log: Dict[str, List[float]] = {}
        self.rate_limits: Dict[str, Tuple[int, int]] = {}
        self.confirmation_required: Set[str] = set()
        self.admin_required: Set[str] = set()
        self.cooldowns: Dict[str, int] = {}

        # NEW: Temporary restrictions from loop intervention
        self.temporary_restrictions: Dict[str, int] = {}  # {tool_name: iterations_remaining}

    def add_temporary_restriction(
        self,
        tool_name: str,
        iterations: int,
        reason: str = "Loop intervention"
    ):
        """Temporarily restrict a tool for N iterations.

        Args:
            tool_name: Tool to restrict
            iterations: Number of iterations to restrict for
            reason: Reason for restriction (for logging)
        """
        self.temporary_restrictions[tool_name] = iterations
        # Log restriction
        print(f"🚫 Tool '{tool_name}' restricted for {iterations} iterations: {reason}")

    def decrement_restrictions(self):
        """Decrement all temporary restrictions by 1 iteration.

        Called at the end of each iteration by ExecutionEngine.
        """
        expired = []
        for tool_name, remaining in self.temporary_restrictions.items():
            if remaining <= 1:
                expired.append(tool_name)
            else:
                self.temporary_restrictions[tool_name] = remaining - 1

        # Remove expired restrictions
        for tool_name in expired:
            del self.temporary_restrictions[tool_name]
            print(f"✅ Tool '{tool_name}' restriction expired")

    def is_tool_restricted(self, tool_name: str) -> Tuple[bool, str]:
        """Check if tool is currently restricted.

        Returns:
            Tuple of (is_restricted, reason)
        """
        if tool_name in self.temporary_restrictions:
            remaining = self.temporary_restrictions[tool_name]
            return (
                True,
                f"Tool temporarily restricted due to loop detection "
                f"({remaining} iterations remaining)"
            )

        return (False, "")

    # Modify existing validate() method:
    def validate(self, tool_name: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate if a tool can be used with given parameters."""

        # NEW: Check temporary restrictions first
        is_restricted, restriction_reason = self.is_tool_restricted(tool_name)
        if is_restricted:
            return (False, restriction_reason)

        # ... existing validation logic (rate limits, cooldowns, etc.) ...
```

**Benefits:**
- ✅ **Natural Fit**: Extends existing ToolGuard pattern
- ✅ **Automatic Enforcement**: Validation happens before every tool call
- ✅ **Time-based**: Restrictions automatically expire
- ✅ **Observable**: Logs restriction lifecycle

---

### 3. Session State Enhancement

**Location:** `reactive_agents/core/types/session_types.py`

**Purpose:** Track intervention state persistently

```python
# Add to existing AgentSession class:

from reactive_agents.core.engine.intervention_policy import InterventionLevel


class AgentSession(BaseModel):
    """Session data for a single agent run."""

    # ... existing fields ...

    # Loop detection (existing)
    loop_detected: bool = False
    loop_details: Optional[Dict[str, Any]] = None
    loop_detections: List[Dict[str, Any]] = Field(default_factory=list)

    # NEW: Loop intervention tracking
    intervention_level: InterventionLevel = Field(default=InterventionLevel.NONE)
    intervention_history: List[Dict[str, Any]] = Field(default_factory=list)
    last_loop_tool: Optional[str] = None  # Track which tool caused last loop
    loop_same_tool_count: int = 0  # How many times same tool looped consecutively
```

**Benefits:**
- ✅ **Persistent Memory**: Tracks escalation across iterations
- ✅ **Type-Safe**: Uses Enum for intervention levels
- ✅ **Auditable**: Full intervention history preserved

---

### 4. TaskStatus Extension

**Location:** `reactive_agents/core/types/status_types.py`

**Purpose:** Add terminal status for loop failures

```python
class TaskStatus(Enum):
    """Standardized task status values for agent execution lifecycle."""

    INITIALIZED = "initialized"
    WAITING_DEPENDENCIES = "waiting_for_dependencies"
    RUNNING = "running"
    MISSING_TOOLS = "missing_tools"
    COMPLETE = "complete"
    RESCOPED_COMPLETE = "rescoped_complete"
    MAX_ITERATIONS = "max_iterations_reached"
    ERROR = "error"
    CANCELLED = "cancelled"

    # NEW: Loop-related failure states
    LOOP_FAILURE = "loop_failure"  # Terminal loop detected
```

**Benefits:**
- ✅ **Clear Semantics**: Distinguishes loop failures from other errors
- ✅ **Terminal State**: Properly ends execution
- ✅ **Observable**: Can filter/alert on loop failures

---

### 5. ExecutionEngine Integration

**Location:** `reactive_agents/core/engine/execution_engine.py`

**Purpose:** Orchestrate interventions using the policy

```python
class ExecutionEngine:
    """Core execution loop with loop intervention."""

    def __init__(self, agent: "Agent"):
        # ... existing initialization ...

        # NEW: Intervention policy (injected via config)
        from reactive_agents.core.engine.intervention_policy import (
            GraduatedInterventionPolicy
        )
        self.intervention_policy = getattr(
            agent.context,
            'intervention_policy',
            GraduatedInterventionPolicy()  # Default
        )

    async def _execute_loop(self, task: str, cancellation_event, reasoning_context):
        """Main execution loop with intervention."""

        # ... existing loop setup ...

        while self._should_continue():
            try:
                # ... iteration execution ...

                # Check for detected loops (EXISTING)
                if self.context.session.loop_detected:
                    # NEW: Use policy to determine action
                    action = await self._handle_loop_with_policy(
                        task,
                        reasoning_context
                    )

                    # If action requires termination, break immediately
                    if action.terminate:
                        break

                # NEW: Decrement tool restrictions at end of iteration
                if hasattr(self.context.tool_manager, 'guard'):
                    self.context.tool_manager.guard.decrement_restrictions()

            except Exception as e:
                # ... error handling ...

        # ... return results ...

    async def _handle_loop_with_policy(
        self,
        task: str,
        reasoning_context: ReasoningContext,
    ) -> InterventionAction:
        """Handle loop using intervention policy.

        This replaces the existing _handle_loop_detected method.
        """
        loop_details = self.context.session.loop_details or {}
        tool_name = loop_details.get("tool_name", "unknown")

        # Track if same tool is looping repeatedly
        if tool_name == self.context.session.last_loop_tool:
            self.context.session.loop_same_tool_count += 1
        else:
            self.context.session.last_loop_tool = tool_name
            self.context.session.loop_same_tool_count = 1

        # Get current intervention level
        current_level = self.context.session.intervention_level

        # Ask policy what to do
        action = self.intervention_policy.determine_action(
            current_level=current_level,
            loop_details=loop_details,
            current_strategy=self.strategy_manager.get_current_strategy_name(),
        )

        # Log intervention
        if self.agent_logger:
            self.agent_logger.warning(
                f"🔁 Loop intervention (Level {action.level.value}): "
                f"{tool_name} - {loop_details.get('type', 'unknown')} loop"
            )

        # Execute policy actions
        if action.add_nudge:
            self.context_manager.add_nudge(action.nudge_message)

        if action.switch_strategy:
            await self.strategy_manager.switch_strategy(
                action.target_strategy,
                task,
                reasoning_context
            )

        if action.restrict_tool:
            self.context.tool_manager.guard.add_temporary_restriction(
                tool_name=action.tool_name,
                iterations=action.restriction_iterations,
                reason=f"Loop intervention (level {action.level.value})"
            )

        if action.terminate:
            self.context.session.task_status = TaskStatus.LOOP_FAILURE
            self.context.session.has_failed = True
            self.context.session.final_answer = (
                f"Task failed due to irrecoverable loop: {action.nudge_message}"
            )

            if self.agent_logger:
                self.agent_logger.error(
                    f"❌ Task terminated due to loop failure: {tool_name}"
                )

        # Update intervention level and history
        self.context.session.intervention_level = action.level
        self.context.session.intervention_history.append({
            "iteration": self.context.session.iterations,
            "level": action.level.value,
            "tool_name": tool_name,
            "action": action.__dict__,
            "timestamp": time.time(),
        })

        # Emit intervention event
        self.context.emit_event(
            AgentStateEvent.LOOP_INTERVENTION,  # NEW event type
            {
                "level": action.level.value,
                "tool_name": tool_name,
                "loop_details": loop_details,
                "actions_taken": {
                    "nudge": action.add_nudge,
                    "strategy_switch": action.switch_strategy,
                    "tool_restriction": action.restrict_tool,
                    "termination": action.terminate,
                },
                "iteration": self.context.session.iterations,
            }
        )

        # Reset loop flag for next iteration
        self.context.session.loop_detected = False
        self.context.session.loop_details = None

        return action
```

**Benefits:**
- ✅ **Policy-Driven**: Uses injected policy for decisions
- ✅ **Comprehensive**: Executes all policy-specified actions
- ✅ **Observable**: Emits events and logs
- ✅ **Auditable**: Tracks full intervention history

---

### 6. Event System Extension

**Location:** `reactive_agents/core/types/event_types.py`

**Purpose:** Add event type for interventions

```python
class AgentStateEvent(Enum):
    """Event types for agent state changes."""

    # ... existing events ...

    # NEW: Loop intervention event
    LOOP_INTERVENTION = "loop_intervention"
```

---

### 7. Builder API Configuration

**Location:** `reactive_agents/app/builders/reactive_agent_builder.py`

**Purpose:** Allow users to configure intervention policy

```python
class ReactiveAgentBuilder:
    """Builder for creating reactive agents."""

    def with_intervention_policy(
        self,
        policy: InterventionPolicyProtocol,
    ) -> "ReactiveAgentBuilder":
        """Configure loop intervention policy.

        Args:
            policy: Intervention policy to use (Graduated, Aggressive, Permissive, or custom)

        Example:
            ```python
            from reactive_agents.core.engine.intervention_policy import (
                AggressiveInterventionPolicy
            )

            agent = await (
                ReactiveAgentBuilder()
                .with_intervention_policy(AggressiveInterventionPolicy())
                .build()
            )
            ```
        """
        self.config.intervention_policy = policy
        return self

    def with_default_intervention(
        self,
        level: str = "graduated"  # "graduated", "aggressive", "permissive"
    ) -> "ReactiveAgentBuilder":
        """Configure intervention using preset policy.

        Args:
            level: Preset policy level
        """
        from reactive_agents.core.engine.intervention_policy import (
            GraduatedInterventionPolicy,
            AggressiveInterventionPolicy,
            PermissiveInterventionPolicy,
        )

        policies = {
            "graduated": GraduatedInterventionPolicy(),
            "aggressive": AggressiveInterventionPolicy(),
            "permissive": PermissiveInterventionPolicy(),
        }

        self.config.intervention_policy = policies.get(
            level,
            GraduatedInterventionPolicy()
        )
        return self
```

**Benefits:**
- ✅ **User Choice**: Easy to select policy
- ✅ **Presets**: Common policies pre-configured
- ✅ **Extensible**: Custom policies supported
- ✅ **Discoverable**: Clear builder API

---

## Implementation Checklist

### Phase 1: Core Components
- [ ] Create `intervention_policy.py` with policy classes
- [ ] Extend `ToolGuard` with temporary restrictions
- [ ] Add fields to `AgentSession` for intervention tracking
- [ ] Add `LOOP_FAILURE` status to `TaskStatus`
- [ ] Add `LOOP_INTERVENTION` event to `AgentStateEvent`

### Phase 2: Integration
- [ ] Replace `_handle_loop_detected` with `_handle_loop_with_policy` in ExecutionEngine
- [ ] Add policy initialization to ExecutionEngine.__init__
- [ ] Add `decrement_restrictions()` call at end of each iteration
- [ ] Modify `ToolManager._actually_call_tool()` to check restrictions

### Phase 3: Builder API
- [ ] Add `with_intervention_policy()` to builder
- [ ] Add `with_default_intervention()` to builder
- [ ] Update default config to include policy

### Phase 4: Testing
- [ ] Unit tests for each policy class
- [ ] Unit tests for tool restriction system
- [ ] Integration test: warning level intervention
- [ ] Integration test: restriction level intervention
- [ ] Integration test: termination level intervention
- [ ] Integration test: policy switching

### Phase 5: Documentation
- [ ] User guide for intervention policies
- [ ] API documentation
- [ ] Migration guide for existing users

---

## Advantages of This Design

### 1. **Follows Existing Patterns**
- ✅ Uses Strategy Pattern (like existing reasoning strategies)
- ✅ Extends ToolGuard (natural fit for restrictions)
- ✅ Uses Enum for states (like StrategyState, TaskStatus)
- ✅ Event-driven (like existing event system)
- ✅ Builder API (consistent with current API)

### 2. **No Breaking Changes**
- ✅ All changes are additive
- ✅ Default behavior maintains compatibility
- ✅ Existing agents work without modification

### 3. **Highly Configurable**
- ✅ Users can choose policy (Graduated/Aggressive/Permissive)
- ✅ Users can create custom policies
- ✅ Sensible defaults for zero-config usage

### 4. **Type-Safe & Testable**
- ✅ All new types use Pydantic/dataclasses
- ✅ Protocol for custom policies
- ✅ Each component testable independently

### 5. **Observable & Debuggable**
- ✅ Events for all interventions
- ✅ Comprehensive logging
- ✅ Full history in session
- ✅ Clear terminal states

### 6. **Enforcement, Not Suggestion**
- ✅ Tool restrictions are **enforced** (not optional)
- ✅ Termination is **immediate** (no more iterations)
- ✅ Escalation is **automatic** (no manual intervention needed)

---

## Example Usage

### Basic Usage (Default Graduated Policy)

```python
# Zero configuration - uses default graduated policy
agent = await (
    ReactiveAgentBuilder()
    .with_model(Provider.OLLAMA, "cogito:14b")
    .with_tools([my_tool])
    .build()
)

# If agent loops:
# 1st loop: Warning nudge
# 2nd loop: Strategy switch + tool restricted for 2 iterations
# 3rd loop: Terminated with LOOP_FAILURE status
```

### Aggressive Mode

```python
from reactive_agents.core.engine.intervention_policy import AggressiveInterventionPolicy

agent = await (
    ReactiveAgentBuilder()
    .with_intervention_policy(AggressiveInterventionPolicy())
    .build()
)

# High-confidence loops immediately trigger restriction
# Faster termination on persistent loops
```

### Custom Policy

```python
from reactive_agents.core.engine.intervention_policy import InterventionPolicyProtocol

class CustomPolicy(InterventionPolicyProtocol):
    def determine_action(self, current_level, loop_details, current_strategy):
        # Your custom logic
        ...

agent = await (
    ReactiveAgentBuilder()
    .with_intervention_policy(CustomPolicy())
    .build()
)
```

---

## Summary

This design provides **graduated loop intervention with hard enforcement** while:

1. ✅ **Following SOLID principles** (SRP, DIP, OCP)
2. ✅ **Extending existing patterns** (ToolGuard, Strategy, Events)
3. ✅ **No breaking changes** (additive only)
4. ✅ **Highly configurable** (policies, presets, custom)
5. ✅ **Type-safe & testable** (protocols, enums, dataclasses)
6. ✅ **Observable** (events, logs, history)

**This is not duct tape - this is proper system design.** 🏗️
