# Reactive Agents: Reasoning Improvements & Next-Gen Architecture Plan

**Date:** January 13, 2026
**Status:** ACTIVE DEVELOPMENT PLAN
**Priority:** HIGH - Foundation for Next-Gen Agent Reasoning

---

## Executive Summary

Based on test results from `playground/test_reasoning_edge_cases.py` and codebase analysis, this document outlines a comprehensive plan to:

1. **Fix critical reasoning gaps** identified in testing
2. **Enable composable reasoning primitives** for novel agent architectures
3. **Support next-generation reasoning paradigms** through extensible building blocks

### Key Philosophy

> **The framework should provide flexible, composable primitives that enable experimentation with novel reasoning approaches - not just implement current state-of-the-art patterns.**

---

## Test Results Analysis

### ✅ What's Working Well

1. **Completion Detection**: PASS (unexpected!)
   - Correctly distinguishes conversational from action-based tasks
   - Efficient iteration counts (1 iter for conversational, 2 for action tasks)

2. **Component Architecture**: Solid foundation
   - Clean separation of concerns
   - Dependency injection working well
   - Event bus providing good observability

3. **Strategy System**: Good structure but underutilized
   - Multiple strategies implemented (Reactive, PlanExecuteReflect, ReflectDecideAct)
   - Strategy switching method exists but is never invoked

### ❌ Critical Gaps Identified

1. **Loop Detection**: FAIL
   - No tracking of repeated tool calls with identical parameters
   - Agent can repeat same action 10+ times without detecting futility
   - **Root cause**: No action history tracking in execution loop

2. **Strategy Switching**: FAIL
   - Dynamic switching enabled but never triggers mid-execution
   - Strategy selected at START but never re-evaluated DURING execution
   - **Root cause**: `execution_engine.py:_execute_loop()` never checks if strategy should switch

3. **Memory-Guided Reasoning**: Marginal improvement (25% vs 30% target)
   - Memory stores session history but is never consulted during reasoning
   - No `get_similar_sessions()` or `get_relevant_reflections()` APIs
   - **Root cause**: Memory manager lacks query methods, strategies don't call them

4. **Progress Stagnation**: Not implemented
   - No tracking of `iterations_without_progress`
   - No detection of when agent is stuck without making progress
   - **Root cause**: No progress measurement beyond iteration count

5. **Tool Redundancy**: Not implemented
   - Same tool called multiple times with identical params
   - No detection or prevention mechanism
   - **Root cause**: No tool call history tracker

6. **Context Summarization**: Naive implementation
   - Line 544 of `context_manager.py` uses placeholder summarization
   - Loses semantic content during pruning
   - **Root cause**: No LLM-powered summarization

---

## Architecture Analysis

### Current Execution Flow

```
ExecutionEngine.execute()
  ├─ _setup_session()
  ├─ _select_strategy() [ONLY AT START]
  │    └─ Checks dynamic_switching config
  │    └─ But only selects initial strategy
  │
  └─ _execute_loop()
       └─ while _should_continue():
            ├─ strategy_manager.execute_iteration() [No switching check]
            ├─ Check if final_answer exists
            ├─ context_manager.summarize_and_prune()
            └─ Continue... [No loop detection, no progress tracking]
```

### Critical Missing Components

1. **ReasoningMonitor**: Should track and analyze reasoning quality in real-time
2. **LoopDetector**: Should detect repeated patterns
3. **ProgressTracker**: Should measure actual progress vs iteration count
4. **MemoryQueryService**: Should provide semantic memory retrieval
5. **StrategyOrchestrator**: Should decide when to switch strategies
6. **ToolRedundancyChecker**: Should prevent duplicate tool calls

---

## 🚀 Proposed Architecture: Composable Reasoning Primitives

### Vision: Building Blocks for Next-Gen Agents

Instead of hardcoding specific reasoning patterns, provide **composable primitives** that developers can mix and match to create novel reasoning approaches:

```
┌─────────────────────────────────────────────────────────────┐
│                   REASONING ORCHESTRATOR                     │
│  (Coordinates reasoning components based on agent config)    │
└────────────────┬────────────────────────────────────────────┘
                 │
    ┌────────────┴───────────────────────────────┐
    │                                             │
┌───▼────┐  ┌──────────┐  ┌──────────┐  ┌──────▼────┐
│ Observe│  │  Think   │  │   Act    │  │  Reflect  │
│ Module │  │  Module  │  │  Module  │  │   Module  │
└────────┘  └──────────┘  └──────────┘  └───────────┘
    │            │             │               │
    └────────────┴─────────────┴───────────────┘
                      │
          ┌───────────▼────────────┐
          │  REASONING MONITORS     │
          │  - Loop Detector        │
          │  - Progress Tracker     │
          │  - Memory Query         │
          │  - Tool Redundancy      │
          │  - Context Analyzer     │
          └─────────────────────────┘
```

### Core Primitives

1. **Observation Primitives**
   - `observe_context()`: Analyze current state
   - `observe_progress()`: Measure task advancement
   - `observe_patterns()`: Detect loops and repetitions

2. **Thinking Primitives**
   - `think_plan()`: Generate action plans
   - `think_evaluate()`: Assess current approach
   - `think_alternatives()`: Consider different strategies

3. **Action Primitives**
   - `act_use_tool()`: Execute tool with validation
   - `act_switch_strategy()`: Change reasoning approach
   - `act_request_info()`: Ask for clarification

4. **Reflection Primitives**
   - `reflect_outcome()`: Analyze action results
   - `reflect_approach()`: Evaluate strategy effectiveness
   - `reflect_memory()`: Learn from similar past experiences

5. **Memory Primitives**
   - `query_similar_tasks()`: Find relevant past experiences
   - `query_successful_patterns()`: Retrieve what worked before
   - `query_tool_preferences()`: Get recommended tools

---

## Phase 1: Critical Fixes (Week 1-2)

### 1.1 Loop Detection System

**File**: `reactive_agents/core/reasoning/monitors/loop_detector.py` (NEW)

```python
class LoopDetector:
    """Detects when agent repeats same actions without progress."""

    def __init__(self, window_size: int = 3):
        self.action_history: List[ActionSignature] = []
        self.window_size = window_size

    def record_action(self, tool_name: str, parameters: Dict[str, Any]):
        """Record a tool call for loop detection."""
        signature = self._hash_action(tool_name, parameters)
        self.action_history.append(signature)

    def check_for_loop(self) -> Optional[LoopDetection]:
        """Check if recent actions form a loop."""
        if len(self.action_history) < self.window_size:
            return None

        recent = self.action_history[-self.window_size:]

        # Check if all recent actions are identical
        if len(set(recent)) == 1:
            return LoopDetection(
                detected=True,
                repeated_action=recent[0],
                repetition_count=self.window_size,
                recommendation="switch_strategy"
            )

        return None
```

**Integration**: Add to `execution_engine.py:_execute_loop()` after each iteration

```python
# In _execute_loop(), after strategy execution
if hasattr(strategy_result, 'tool_calls'):
    for tool_call in strategy_result.tool_calls:
        self.loop_detector.record_action(
            tool_call.tool_name,
            tool_call.parameters
        )

    loop_check = self.loop_detector.check_for_loop()
    if loop_check and loop_check.detected:
        self.agent_logger.warning(
            f"🔁 Loop detected: {loop_check.repeated_action} "
            f"repeated {loop_check.repetition_count} times"
        )

        # Add nudge or switch strategy
        if loop_check.recommendation == "switch_strategy":
            await self._trigger_strategy_switch(
                reason="loop_detected",
                context=reasoning_context
            )
```

### 1.2 Mid-Execution Strategy Switching

**File**: `reactive_agents/core/reasoning/orchestrator.py` (NEW)

```python
class StrategyOrchestrator:
    """Decides when and how to switch strategies during execution."""

    def should_switch_strategy(
        self,
        current_strategy: str,
        session: AgentSession,
        loop_detected: bool = False,
        progress_stagnant: bool = False
    ) -> Optional[StrategySwitchRecommendation]:
        """Evaluate if strategy switch is needed."""

        # Trigger 1: Loop detected
        if loop_detected:
            return StrategySwitchRecommendation(
                from_strategy=current_strategy,
                to_strategy="plan_execute_reflect",
                reason="loop_detected",
                priority="high"
            )

        # Trigger 2: Progress stagnation
        if progress_stagnant and session.iterations >= 3:
            return StrategySwitchRecommendation(
                from_strategy=current_strategy,
                to_strategy="plan_execute_reflect",
                reason="progress_stagnation",
                priority="medium"
            )

        # Trigger 3: Strategy performing poorly (from metrics)
        if self.context.metrics_manager:
            strategy_score = self.context.metrics_manager.get_strategy_performance(
                current_strategy
            )
            if strategy_score < 0.4:  # Poor performance threshold
                best_strategy = self.context.metrics_manager.get_best_strategy()
                if best_strategy and best_strategy != current_strategy:
                    return StrategySwitchRecommendation(
                        from_strategy=current_strategy,
                        to_strategy=best_strategy,
                        reason="poor_performance",
                        priority="medium"
                    )

        return None
```

**Integration**: Add check in `execution_engine.py:_execute_loop()`

```python
# In _execute_loop(), after each iteration
if self.context.enable_dynamic_strategy_switching:
    switch_rec = self.strategy_orchestrator.should_switch_strategy(
        current_strategy=self.strategy_manager.get_current_strategy_name(),
        session=self.context.session,
        loop_detected=bool(loop_check and loop_check.detected),
        progress_stagnant=self.progress_tracker.is_stagnant()
    )

    if switch_rec:
        self.agent_logger.info(
            f"🔄 Switching strategy: {switch_rec.from_strategy} → "
            f"{switch_rec.to_strategy} (reason: {switch_rec.reason})"
        )
        await self.strategy_manager.switch_strategy(
            switch_rec.to_strategy,
            task,
            reasoning_context
        )
```

### 1.3 Progress Stagnation Detection

**File**: `reactive_agents/core/reasoning/monitors/progress_tracker.py` (NEW)

```python
class ProgressTracker:
    """Tracks actual progress beyond iteration count."""

    def __init__(self):
        self.iteration_snapshots: List[ProgressSnapshot] = []
        self.last_progress_iteration: int = 0

    def record_iteration(
        self,
        iteration: int,
        tool_results: List[ToolResult],
        context_changes: int,
        session: AgentSession
    ) -> ProgressSnapshot:
        """Record iteration state for progress analysis."""
        snapshot = ProgressSnapshot(
            iteration=iteration,
            new_tool_results=len([r for r in tool_results if r.success]),
            context_size_change=context_changes,
            has_final_answer=bool(session.final_answer),
            timestamp=time.time()
        )

        # Check if this iteration made progress
        if self._made_progress(snapshot):
            self.last_progress_iteration = iteration

        self.iteration_snapshots.append(snapshot)
        return snapshot

    def is_stagnant(self, threshold: int = 3) -> bool:
        """Check if agent is stagnant (no progress for N iterations)."""
        if not self.iteration_snapshots:
            return False

        current_iteration = self.iteration_snapshots[-1].iteration
        iterations_since_progress = current_iteration - self.last_progress_iteration

        return iterations_since_progress >= threshold

    def _made_progress(self, snapshot: ProgressSnapshot) -> bool:
        """Determine if this iteration made meaningful progress."""
        # Progress indicators:
        # 1. New successful tool results
        # 2. Significant context growth (new information)
        # 3. Final answer provided
        return (
            snapshot.new_tool_results > 0
            or snapshot.context_size_change > 100  # Arbitrary threshold
            or snapshot.has_final_answer
        )
```

### 1.4 Memory-Guided Reasoning

**File**: `reactive_agents/core/memory/memory_manager.py` (ENHANCE)

Add new query methods:

```python
class MemoryManager(BaseModel):
    # ... existing code ...

    def get_similar_sessions(
        self,
        task: str,
        similarity_threshold: float = 0.7,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find similar past sessions to guide current execution.

        This uses simple keyword matching for now. In Phase 3, we'll
        integrate vector search for semantic similarity.
        """
        if not self.agent_memory or not self.agent_memory.session_history:
            return []

        # Simple keyword-based similarity for Phase 1
        task_keywords = set(task.lower().split())

        similar_sessions = []
        for session_data in self.agent_memory.session_history:
            session_task = session_data.get("initial_task", "").lower()
            session_keywords = set(session_task.split())

            # Jaccard similarity
            intersection = len(task_keywords & session_keywords)
            union = len(task_keywords | session_keywords)
            similarity = intersection / union if union > 0 else 0

            if similarity >= similarity_threshold:
                similar_sessions.append({
                    **session_data,
                    "similarity": similarity
                })

        # Sort by similarity and return top N
        similar_sessions.sort(key=lambda x: x["similarity"], reverse=True)
        return similar_sessions[:limit]

    def get_relevant_reflections(
        self,
        context: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get reflections relevant to current context."""
        if not self.agent_memory or not self.agent_memory.reflections:
            return []

        # Simple relevance scoring based on keyword overlap
        context_keywords = set(context.lower().split())

        scored_reflections = []
        for reflection in self.agent_memory.reflections:
            reflection_text = reflection.get("content", "").lower()
            reflection_keywords = set(reflection_text.split())

            relevance = len(context_keywords & reflection_keywords) / len(context_keywords)

            scored_reflections.append({
                **reflection,
                "relevance": relevance
            })

        scored_reflections.sort(key=lambda x: x["relevance"], reverse=True)
        return scored_reflections[:limit]

    def recommend_tools_for_task(self, task: str) -> List[str]:
        """Recommend tools based on past successful usage."""
        similar_sessions = self.get_similar_sessions(task, similarity_threshold=0.6)

        # Aggregate successful tools from similar sessions
        tool_usage = {}
        for session in similar_sessions:
            if session.get("was_successful"):
                tools = session.get("successful_tools", [])
                for tool in tools:
                    tool_usage[tool] = tool_usage.get(tool, 0) + 1

        # Sort by frequency
        recommended = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)
        return [tool for tool, _ in recommended]
```

**Integration**: Add memory consultation to strategies

```python
# In BaseReasoningStrategy.initialize()
async def initialize(self, task: str, reasoning_context: ReasoningContext):
    """Initialize strategy with memory-guided insights."""
    # Query memory for similar tasks
    similar_sessions = self.context.memory_manager.get_similar_sessions(task)

    if similar_sessions:
        self.logger.info(
            f"💡 Found {len(similar_sessions)} similar past sessions"
        )

        # Extract insights
        avg_iterations = sum(s.get("iterations", 0) for s in similar_sessions) / len(similar_sessions)
        successful_strategies = [
            s.get("strategy") for s in similar_sessions
            if s.get("was_successful")
        ]

        # Store insights in reasoning context for strategy use
        reasoning_context.memory_insights = {
            "expected_iterations": int(avg_iterations),
            "successful_strategies": successful_strategies,
            "recommended_tools": self.context.memory_manager.recommend_tools_for_task(task)
        }

        self.logger.debug(f"Memory insights: {reasoning_context.memory_insights}")
```

### 1.5 Tool Redundancy Detection

**File**: `reactive_agents/core/reasoning/monitors/tool_redundancy_checker.py` (NEW)

```python
class ToolRedundancyChecker:
    """Detects and prevents redundant tool calls."""

    def __init__(self, window_size: int = 5):
        self.recent_calls: List[ToolCallSignature] = []
        self.window_size = window_size

    def is_redundant(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> bool:
        """Check if this tool call is redundant."""
        signature = ToolCallSignature(
            tool_name=tool_name,
            param_hash=self._hash_params(parameters)
        )

        # Check if this exact call was made recently
        for recent_call in self.recent_calls[-3:]:  # Last 3 calls
            if recent_call == signature:
                return True

        return False

    def record_call(self, tool_name: str, parameters: Dict[str, Any]):
        """Record a tool call."""
        signature = ToolCallSignature(
            tool_name=tool_name,
            param_hash=self._hash_params(parameters)
        )
        self.recent_calls.append(signature)

        # Keep only recent window
        if len(self.recent_calls) > self.window_size:
            self.recent_calls = self.recent_calls[-self.window_size:]

    def _hash_params(self, parameters: Dict[str, Any]) -> str:
        """Create a hash of parameters for comparison."""
        import hashlib
        import json
        param_str = json.dumps(parameters, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()
```

---

## Phase 2: Composable Reasoning Architecture (Week 3-4)

### 2.1 Reasoning Primitive Interface

**File**: `reactive_agents/core/reasoning/primitives/base.py` (NEW)

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class ReasoningPrimitive(ABC):
    """Base class for composable reasoning primitives."""

    @abstractmethod
    async def execute(
        self,
        context: AgentContext,
        inputs: Dict[str, Any]
    ) -> PrimitiveResult:
        """Execute this reasoning primitive."""
        pass

    @property
    @abstractmethod
    def primitive_type(self) -> str:
        """Type of primitive (observe, think, act, reflect)."""
        pass

    @property
    def dependencies(self) -> List[str]:
        """Other primitives this depends on."""
        return []


class ObservePrimitive(ReasoningPrimitive):
    """Base for observation primitives."""

    @property
    def primitive_type(self) -> str:
        return "observe"


class ThinkPrimitive(ReasoningPrimitive):
    """Base for thinking primitives."""

    @property
    def primitive_type(self) -> str:
        return "think"


class ActPrimitive(ReasoningPrimitive):
    """Base for action primitives."""

    @property
    def primitive_type(self) -> str:
        return "act"


class ReflectPrimitive(ReasoningPrimitive):
    """Base for reflection primitives."""

    @property
    def primitive_type(self) -> str:
        return "reflect"
```

### 2.2 Concrete Primitives

**File**: `reactive_agents/core/reasoning/primitives/observations.py` (NEW)

```python
class ObserveProgressPrimitive(ObservePrimitive):
    """Observe task progress."""

    async def execute(
        self,
        context: AgentContext,
        inputs: Dict[str, Any]
    ) -> PrimitiveResult:
        """Analyze current progress."""
        session = context.session
        progress_tracker = inputs.get("progress_tracker")

        progress_analysis = {
            "iterations": session.iterations,
            "has_answer": bool(session.final_answer),
            "is_stagnant": progress_tracker.is_stagnant() if progress_tracker else False,
            "tools_used": len(session.successful_tools),
        }

        return PrimitiveResult(
            success=True,
            data=progress_analysis,
            insights=f"Progress: {progress_analysis['iterations']} iterations, "
                    f"{'stagnant' if progress_analysis['is_stagnant'] else 'making progress'}"
        )


class ObservePatternsP rimitive(ObservePrimitive):
    """Observe patterns in agent behavior."""

    async def execute(
        self,
        context: AgentContext,
        inputs: Dict[str, Any]
    ) -> PrimitiveResult:
        """Detect loops and patterns."""
        loop_detector = inputs.get("loop_detector")

        if not loop_detector:
            return PrimitiveResult(success=False, error="No loop detector available")

        loop_check = loop_detector.check_for_loop()

        return PrimitiveResult(
            success=True,
            data={
                "loop_detected": loop_check is not None and loop_check.detected,
                "repeated_action": loop_check.repeated_action if loop_check else None,
            },
            insights="Loop detected!" if (loop_check and loop_check.detected) else "No loops"
        )
```

### 2.3 Primitive Composer

**File**: `reactive_agents/core/reasoning/primitives/composer.py` (NEW)

```python
class PrimitiveComposer:
    """Composes reasoning primitives into custom strategies."""

    def __init__(self, context: AgentContext):
        self.context = context
        self.primitives: Dict[str, ReasoningPrimitive] = {}

    def register_primitive(self, name: str, primitive: ReasoningPrimitive):
        """Register a primitive for use in compositions."""
        self.primitives[name] = primitive

    async def compose_and_execute(
        self,
        composition: List[str],  # Ordered list of primitive names
        inputs: Dict[str, Any]
    ) -> CompositionResult:
        """Execute a composition of primitives."""
        results = []
        accumulated_data = inputs.copy()

        for primitive_name in composition:
            if primitive_name not in self.primitives:
                raise ValueError(f"Unknown primitive: {primitive_name}")

            primitive = self.primitives[primitive_name]
            result = await primitive.execute(self.context, accumulated_data)

            results.append(result)

            # Accumulate data for next primitive
            if result.success and result.data:
                accumulated_data.update(result.data)

        return CompositionResult(
            primitive_results=results,
            final_data=accumulated_data,
            success=all(r.success for r in results)
        )
```

This allows users to create custom reasoning flows:

```python
# Example: Custom reasoning strategy using primitives
composer = PrimitiveComposer(context)

# Register primitives
composer.register_primitive("observe_progress", ObserveProgressPrimitive())
composer.register_primitive("observe_patterns", ObservePatternsPrimitive())
composer.register_primitive("think_plan", ThinkPlanPrimitive())
composer.register_primitive("act_use_tools", ActUseToolsPrimitive())
composer.register_primitive("reflect_outcome", ReflectOutcomePrimitive())

# Define custom reasoning flow
custom_flow = [
    "observe_progress",    # Check current state
    "observe_patterns",    # Look for loops
    "think_plan",          # Plan next action
    "act_use_tools",       # Execute tools
    "reflect_outcome",     # Analyze results
]

# Execute the composition
result = await composer.compose_and_execute(
    composition=custom_flow,
    inputs={"task": task, "loop_detector": loop_detector}
)
```

---

## Phase 3: Advanced Capabilities (Month 2)

### 3.1 Vector Memory Integration

Replace simple keyword matching with semantic search using ChromaDB or similar.

### 3.2 LLM-Powered Context Summarization

Replace placeholder in `context_manager.py:544` with actual LLM summarization.

### 3.3 Tree of Thoughts Implementation

Use primitives to build ToT as a composable strategy.

### 3.4 Meta-Learning Layer

Agent learns which primitive compositions work best for different task types.

---

## Implementation Priorities

### Critical (Start Immediately)
1. Loop Detection
2. Mid-Execution Strategy Switching
3. Progress Stagnation Detection
4. Memory Query Methods

### High (Week 2)
5. Tool Redundancy Detection
6. Primitive Interface Design
7. Basic Primitive Implementations

### Medium (Week 3-4)
8. Primitive Composer
9. Example Custom Strategies
10. LLM Context Summarization

### Low (Month 2+)
11. Vector Memory
12. Meta-Learning
13. Advanced Primitives (ToT, etc.)

---

## Expected Outcomes

After Phase 1:
- ✅ 0% loop failures (was: >50%)
- ✅ 100% strategy switching success (was: 0%)
- ✅ 40-50% fewer iterations via memory guidance (was: 25%)
- ✅ Zero tool redundancy (was: multiple duplicates)
- ✅ 90%+ test pass rate (was: 42% on stress tests)

After Phase 2:
- ✅ Developers can create custom reasoning strategies without modifying core code
- ✅ Novel reasoning paradigms can be experimented with using primitive compositions
- ✅ Framework supports unexplored reasoning approaches

After Phase 3:
- ✅ Semantic memory retrieval working
- ✅ Context fidelity maintained over 100+ turns
- ✅ Meta-learning improving agent performance over time

---

## Next Steps

1. Review and approve this plan
2. Run full test suite to establish baseline metrics
3. Begin Phase 1 implementation starting with Loop Detection
4. Create integration tests for each new component
5. Update ROADMAP.md with detailed implementation timeline

---

## Notes

- All new code should follow existing patterns (Pydantic models, dependency injection, async/await)
- Each component should be independently testable
- Maintain backwards compatibility where possible
- Document all new APIs and primitives
- Add examples for custom primitive compositions
