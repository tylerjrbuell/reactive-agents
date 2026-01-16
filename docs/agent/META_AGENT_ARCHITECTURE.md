# Meta-Agent / Conductor Pattern Architecture

**Date:** January 15, 2026
**Status:** Design Proposal
**Pattern:** Conductor-Worker (Microservices for Agents)

---

## Core Insight

> **Instead of building complex safety mechanisms into monolithic agents,
> use composition and delegation with specialized sub-agents.**

**Current Problem:** Single agent trying to do everything → loops, gets stuck, needs complex intervention

**Solution:** Conductor agent delegates to specialized, lightweight sub-agents → isolation, resilience, simplicity

---

## Architectural Comparison

### Monolithic Agent (Current)
```
┌─────────────────────────────────────┐
│     Single Agent                    │
│  - All tools                        │
│  - All strategies                   │
│  - Loop detection                   │
│  - Intervention policies            │
│  - Memory management                │
│  - Context management               │
│  - Error recovery                   │
│                                     │
│  Gets overwhelmed → loops → stuck   │
└─────────────────────────────────────┘
```

### Conductor Pattern (Proposed)
```
┌─────────────────────────────────────┐
│   Conductor Agent (Root)            │
│  - Meta-tools (spawn/monitor)       │
│  - Orchestration logic              │
│  - Memory (shared context)          │
│  - Result aggregation               │
│                                     │
│  Delegates work ↓                   │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┬─────────┬─────────┐
    │             │         │         │
┌───▼────┐  ┌────▼───┐ ┌──▼────┐ ┌──▼────┐
│ Search │  │ Analyze│ │ Write │ │ Calc  │
│ Agent  │  │ Agent  │ │ Agent │ │ Agent │
│        │  │        │ │       │ │       │
│ 3 iter │  │ 5 iter │ │ 2 iter│ │ 1 iter│
│ Simple │  │ Focused│ │ Fast  │ │ Pure  │
└────────┘  └────────┘ └───────┘ └───────┘
  Loops?      Fails?     Done✓    Done✓
  Kill it!    Try new    Return   Return
```

**Benefits:**
- ✅ **Isolation**: Loop in sub-agent doesn't affect conductor
- ✅ **Specialization**: Each sub-agent focused on one thing
- ✅ **Resilience**: Failed sub-agent = terminate and retry
- ✅ **Simplicity**: Sub-agents don't need complex systems
- ✅ **Composability**: Conductor tries different combinations
- ✅ **Scalability**: Can run sub-agents in parallel
- ✅ **Natural Fit**: Reactive agents already async, already have lifecycle

---

## Pattern: Unix Philosophy for Agents

### Unix Philosophy
1. Do one thing well
2. Compose small programs
3. Text streams for communication

### Meta-Agent Philosophy
1. **Specialized sub-agents** - each does one thing well
2. **Conductor orchestrates** - compose agents for complex tasks
3. **Structured results** - agents return typed data

**Example:**
```bash
# Unix
cat file.txt | grep "error" | wc -l

# Meta-Agent
conductor.run("Count errors in logs")
  → spawn search_agent(task="find error logs")
  → spawn count_agent(task="count entries", data=search_results)
  → return count
```

---

## Design: Meta-Tools System

### 1. Meta-Tool: spawn_sub_agent

**Purpose:** Create and run a specialized sub-agent

```python
@tool(category="meta")
async def spawn_sub_agent(
    task: str,
    tools: List[str],
    max_iterations: int = 3,
    timeout: int = 30,
    agent_type: str = "reactive",
) -> Dict[str, Any]:
    """Spawn a lightweight sub-agent to handle a focused task.

    Use this when you need to delegate a specific, well-defined subtask
    to a specialized agent. Sub-agents are isolated and resource-limited.

    Args:
        task: Clear, specific task for the sub-agent
        tools: List of tool names to give the sub-agent (keep minimal)
        max_iterations: Maximum iterations (default: 3, keep low)
        timeout: Timeout in seconds (default: 30)
        agent_type: Type of agent ("reactive", "plan" - reactive is default)

    Returns:
        {
            "agent_id": "unique_id",
            "status": "running",
            "task": "the task",
        }

    Examples:
        - Search task: spawn_sub_agent(task="Find all Python files", tools=["search_files"])
        - Analysis: spawn_sub_agent(task="Analyze sales data", tools=["read_csv", "calculate"])
        - Writing: spawn_sub_agent(task="Write summary", tools=["write_file"])
    """
```

**Implementation:**
```python
class SpawnSubAgentTool(Tool):
    """Meta-tool for spawning sub-agents."""

    def __init__(self, context: ContextProtocol):
        super().__init__(
            name="spawn_sub_agent",
            description="Spawn a specialized sub-agent for a focused task",
            input_schema=SpawnSubAgentInput,
            category="meta",
        )
        self.context = context
        self.sub_agents: Dict[str, SubAgentHandle] = {}

    async def use(self, params: Dict[str, Any]) -> ToolResult:
        """Spawn and run a sub-agent."""
        task = params["task"]
        tool_names = params["tools"]
        max_iterations = params.get("max_iterations", 3)
        timeout = params.get("timeout", 30)
        agent_type = params.get("agent_type", "reactive")

        # Get tool objects from names
        available_tools = {t.name: t for t in self.context.tool_manager.tools}
        sub_agent_tools = [
            available_tools[name] for name in tool_names
            if name in available_tools
        ]

        # Create lightweight sub-agent
        from reactive_agents import ReactiveAgentBuilder, ReasoningStrategies

        strategy = ReasoningStrategies.REACTIVE  # Simple by default
        if agent_type == "plan":
            strategy = ReasoningStrategies.PLAN_EXECUTE_REFLECT

        sub_agent = await (
            ReactiveAgentBuilder()
            .with_model(
                self.context.model_provider.provider,
                self.context.model_provider.model_name
            )
            .with_tools(sub_agent_tools)
            .with_reasoning_strategy(strategy)
            .with_max_iterations(max_iterations)
            .with_memory_enabled(False)  # No memory for sub-agents
            .build()
        )

        # Generate unique ID
        agent_id = f"sub_{int(time.time() * 1000)}"

        # Create handle for tracking
        handle = SubAgentHandle(
            agent_id=agent_id,
            agent=sub_agent,
            task=task,
            status="running",
            started_at=time.time(),
            timeout=timeout,
        )

        self.sub_agents[agent_id] = handle

        # Run sub-agent in background with timeout
        asyncio.create_task(
            self._run_sub_agent_with_timeout(handle)
        )

        return ToolResult.ok(
            value={
                "agent_id": agent_id,
                "status": "running",
                "task": task,
                "max_iterations": max_iterations,
                "timeout": timeout,
            },
            tool_name=self.name,
        )

    async def _run_sub_agent_with_timeout(self, handle: SubAgentHandle):
        """Run sub-agent with timeout protection."""
        try:
            result = await asyncio.wait_for(
                handle.agent.run(handle.task),
                timeout=handle.timeout
            )

            handle.status = "completed"
            handle.result = result
            handle.completed_at = time.time()

        except asyncio.TimeoutError:
            handle.status = "timeout"
            handle.error = f"Sub-agent exceeded {handle.timeout}s timeout"
            await handle.agent.close()

        except Exception as e:
            handle.status = "failed"
            handle.error = str(e)
            await handle.agent.close()
```

### 2. Meta-Tool: get_sub_agent_result

**Purpose:** Retrieve result from a completed sub-agent

```python
@tool(category="meta")
async def get_sub_agent_result(
    agent_id: str,
    wait: bool = True,
    wait_timeout: int = 10,
) -> Dict[str, Any]:
    """Get the result from a sub-agent.

    Args:
        agent_id: ID of the sub-agent (from spawn_sub_agent)
        wait: Whether to wait for completion (default: True)
        wait_timeout: Max seconds to wait if wait=True (default: 10)

    Returns:
        {
            "status": "completed" | "running" | "failed" | "timeout",
            "result": {...},  # If completed
            "error": "...",   # If failed/timeout
        }
    """
```

### 3. Meta-Tool: check_sub_agent_status

**Purpose:** Check status without retrieving full result

```python
@tool(category="meta")
async def check_sub_agent_status(agent_id: str) -> Dict[str, Any]:
    """Check the status of a running sub-agent.

    Returns:
        {
            "status": "running" | "completed" | "failed" | "timeout",
            "iterations": 2,
            "elapsed_seconds": 5.3,
        }
    """
```

### 4. Meta-Tool: terminate_sub_agent

**Purpose:** Kill a sub-agent (if stuck/looping)

```python
@tool(category="meta")
async def terminate_sub_agent(agent_id: str, reason: str) -> Dict[str, Any]:
    """Terminate a running sub-agent.

    Use when:
    - Sub-agent is taking too long
    - Sub-agent is likely stuck/looping
    - Need to try a different approach

    Args:
        agent_id: ID of sub-agent to terminate
        reason: Why you're terminating it

    Returns:
        {"terminated": True, "agent_id": "...", "reason": "..."}
    """
```

---

## Sub-Agent Design Principles

### Lightweight Configuration

**Sub-agents should be:**
1. **Focused** - Small tool set (1-5 tools)
2. **Fast** - Low max_iterations (2-5)
3. **Simple** - Reactive strategy (no complex planning)
4. **Stateless** - No memory (conductor manages state)
5. **Time-bounded** - Short timeout (30-60s)
6. **Isolated** - Failures don't affect conductor

**Example Sub-Agent Types:**

```python
# File searcher - just finds files
FileSearchAgent(
    tools=["search_files", "list_directory"],
    max_iterations=3,
    timeout=30,
)

# Data analyzer - just analyzes
DataAnalyzerAgent(
    tools=["read_csv", "calculate_stats", "create_chart"],
    max_iterations=5,
    timeout=60,
)

# File writer - just writes
FileWriterAgent(
    tools=["write_file", "append_to_file"],
    max_iterations=2,
    timeout=20,
)

# Pure calculator - single shot
CalculatorAgent(
    tools=["calculate"],
    max_iterations=1,
    timeout=10,
)
```

---

## Conductor Agent Pattern

### Conductor Responsibilities

1. **Task Decomposition**
   - Break complex task into subtasks
   - Determine which sub-agents to spawn
   - Sequence or parallelize work

2. **Orchestration**
   - Spawn sub-agents with right tools
   - Monitor progress
   - Handle failures gracefully

3. **Result Aggregation**
   - Collect sub-agent results
   - Combine/synthesize
   - Produce final answer

4. **Memory Management**
   - Conductor has memory (learns over time)
   - Sub-agents stateless (no memory overhead)
   - Shared context via conductor

5. **Error Handling**
   - Sub-agent loops → terminate, try different approach
   - Sub-agent fails → spawn replacement with different tools
   - Sub-agent timeout → kill and retry with shorter task

### Conductor Tools

**Conductor has:**
- Meta-tools (spawn, monitor, terminate sub-agents)
- High-level domain tools (if needed)
- Memory (to learn patterns)
- Higher max_iterations (15-20)
- More sophisticated strategy (plan_execute_reflect)

**Conductor does NOT have:**
- Low-level tools (those go to sub-agents)
- Every possible tool (delegates to specialists)

---

## Example Workflows

### Example 1: Data Analysis Task

**Task:** "Analyze sales data and create a report"

**Monolithic Agent:**
```
Agent tries to do everything:
1. Find sales data
2. Read it
3. Calculate stats
4. Create visualizations
5. Write report
→ Gets overwhelmed, loops, retries same approach 10 times
```

**Conductor Agent:**
```python
Conductor receives task

# Step 1: Find data
search_agent = spawn_sub_agent(
    task="Find sales data files in /data/sales",
    tools=["search_files", "list_directory"],
    max_iterations=3,
)
files = get_sub_agent_result(search_agent.agent_id)

if files.status == "failed":
    # Try different approach
    search_agent2 = spawn_sub_agent(
        task="Search for CSV files with 'sales' in name",
        tools=["find_files_by_pattern"],
        max_iterations=2,
    )
    files = get_sub_agent_result(search_agent2.agent_id)

# Step 2: Analyze data
analyzer = spawn_sub_agent(
    task=f"Calculate total sales, average, trends from {files.result}",
    tools=["read_csv", "calculate_stats"],
    max_iterations=5,
)
stats = get_sub_agent_result(analyzer.agent_id)

# Step 3: Write report
writer = spawn_sub_agent(
    task=f"Write sales report with these stats: {stats.result}",
    tools=["write_file"],
    max_iterations=2,
)
report = get_sub_agent_result(writer.agent_id)

final_answer(f"Report created: {report.result}")
```

**Benefits:**
- Each sub-agent simple, focused
- If analyzer loops → kill it, try with different tools
- Conductor coordinates but doesn't do low-level work
- Failures isolated

### Example 2: Research Task

**Task:** "Research React best practices and summarize"

**Conductor:**
```python
# Parallel search with multiple sub-agents
search_agents = [
    spawn_sub_agent(
        task="Search official React docs for best practices",
        tools=["web_search", "fetch_url"],
        max_iterations=3,
    ),
    spawn_sub_agent(
        task="Search GitHub for React patterns",
        tools=["github_search"],
        max_iterations=3,
    ),
    spawn_sub_agent(
        task="Search Stack Overflow for React questions",
        tools=["stackoverflow_search"],
        max_iterations=3,
    ),
]

# Wait for all (or timeout stragglers)
results = await asyncio.gather(
    *[get_sub_agent_result(a.agent_id, wait_timeout=30) for a in search_agents]
)

# Synthesize results
synthesizer = spawn_sub_agent(
    task=f"Synthesize these research results into summary: {results}",
    tools=["summarize_text"],
    max_iterations=3,
)

summary = get_sub_agent_result(synthesizer.agent_id)
final_answer(summary.result)
```

**Benefits:**
- Parallel execution (faster)
- Each searcher specialized
- Timeout protection on each
- Conductor synthesizes (high-level task)

---

## Integration with Existing Framework

### System Tools Registry Extension

**Add meta-tools to registry:**

```python
# reactive_agents/core/tools/meta_tools.py

from reactive_agents.core.tools.system_tool import SystemTool

class MetaToolsRegistry:
    """Registry for meta-tools (conductor capabilities)."""

    @staticmethod
    def get_meta_tools(context: ContextProtocol) -> List[SystemTool]:
        """Get all meta-tools for conductor agents."""
        return [
            SpawnSubAgentTool(context),
            GetSubAgentResultTool(context),
            CheckSubAgentStatusTool(context),
            TerminateSubAgentTool(context),
        ]
```

**Enable in builder:**

```python
# In ReactiveAgentBuilder

def as_conductor(self) -> "ReactiveAgentBuilder":
    """Configure this agent as a conductor (meta-agent).

    Adds meta-tools for spawning and managing sub-agents.
    Recommended settings:
    - Higher max_iterations (15-20)
    - More sophisticated strategy (plan_execute_reflect)
    - Memory enabled (to learn orchestration patterns)
    """
    self.config.is_conductor = True
    self.config.enable_meta_tools = True

    # Recommended defaults for conductors
    if not hasattr(self.config, 'max_iterations'):
        self.config.max_iterations = 20

    if not hasattr(self.config, 'reasoning_strategy'):
        from reactive_agents.core.reasoning.strategies import ReasoningStrategies
        self.config.reasoning_strategy = ReasoningStrategies.PLAN_EXECUTE_REFLECT

    return self
```

### Usage

```python
# Create conductor agent
conductor = await (
    ReactiveAgentBuilder()
    .with_model(Provider.OLLAMA, "cogito:14b")
    .as_conductor()  # Adds meta-tools, better defaults
    .with_tools([high_level_tools])  # Optional domain tools
    .build()
)

# Run complex task
result = await conductor.run(
    "Analyze sales data, identify trends, and create executive summary"
)

# Conductor will:
# 1. Decompose task
# 2. Spawn specialized sub-agents
# 3. Monitor their progress
# 4. Aggregate results
# 5. Produce final answer
```

---

## Advantages Over Intervention System

### Intervention System (Complex)
- ❌ Adds policies, restrictions, escalation to monolithic agent
- ❌ Still single point of failure
- ❌ Complex state management
- ❌ Hard to debug when agent doing too much

### Conductor Pattern (Simple)
- ✅ **Composition over configuration**
- ✅ **Isolation**: Sub-agent loops → just kill it
- ✅ **Specialization**: Each agent focused
- ✅ **Resilience**: Failure = swap sub-agent
- ✅ **Simplicity**: Sub-agents need minimal safety
- ✅ **Scalability**: Parallel sub-agents
- ✅ **Testability**: Test sub-agents independently
- ✅ **Debuggability**: Clear separation of concerns

---

## When to Use Each Pattern

### Use Conductor When:
- ✅ Task has multiple distinct phases
- ✅ Task can be decomposed naturally
- ✅ Need parallel execution
- ✅ Different phases need different tools
- ✅ Willing to pay for multiple LLM calls

### Use Single Agent When:
- ✅ Task is simple and focused
- ✅ Doesn't need decomposition
- ✅ Single tool set works
- ✅ Cost-sensitive (minimize LLM calls)

---

## Implementation Plan

### Phase 1: Core Meta-Tools
- [ ] Create `meta_tools.py` module
- [ ] Implement `SpawnSubAgentTool`
- [ ] Implement `GetSubAgentResultTool`
- [ ] Implement `CheckSubAgentStatusTool`
- [ ] Implement `TerminateSubAgentTool`
- [ ] Create `SubAgentHandle` dataclass

### Phase 2: Builder Integration
- [ ] Add `.as_conductor()` to ReactiveAgentBuilder
- [ ] Add meta-tools injection logic
- [ ] Set conductor-friendly defaults

### Phase 3: Testing
- [ ] Unit tests for each meta-tool
- [ ] Integration test: conductor + single sub-agent
- [ ] Integration test: conductor + parallel sub-agents
- [ ] Integration test: sub-agent failure handling
- [ ] Integration test: sub-agent timeout handling

### Phase 4: Examples & Docs
- [ ] Example: data analysis workflow
- [ ] Example: research and summarization
- [ ] Example: multi-step file processing
- [ ] User guide: when to use conductor
- [ ] API documentation

### Phase 5: Advanced Features
- [ ] Sub-agent pooling (reuse agents)
- [ ] Sub-agent templates (pre-configured specialists)
- [ ] Result streaming (partial results)
- [ ] Hierarchical conductors (conductor → conductor → workers)

---

## Comparison: Both Approaches

### Option A: Loop Intervention System
**When to use:**
- Single agent handling well-defined task
- Need safety nets for edge cases
- Want sophisticated error recovery

**Tradeoffs:**
- ✅ One agent, simpler deployment
- ✅ No coordination overhead
- ❌ Complex internal state
- ❌ Monolithic failure mode

### Option B: Conductor/Meta-Agent Pattern
**When to use:**
- Complex multi-phase tasks
- Natural decomposition available
- Need isolation and resilience
- Willing to pay orchestration cost

**Tradeoffs:**
- ✅ Simple, focused sub-agents
- ✅ Isolation and resilience
- ✅ Parallel execution possible
- ❌ More LLM calls (cost)
- ❌ Coordination complexity

### Recommendation: **Both**

**Why not both?**

1. **Conductor for complex tasks** (multi-phase, decomposable)
2. **Single agent for simple tasks** (focused, single-phase)
3. **Intervention system as safety net** (even conductors can loop)

**Example:**
```python
# Conductor with intervention safety
conductor = await (
    ReactiveAgentBuilder()
    .as_conductor()
    .with_default_intervention("permissive")  # Backup safety
    .build()
)
```

Sub-agents don't need intervention (they're lightweight and timeout-protected).
Conductors have intervention as last resort (shouldn't loop but just in case).

---

## Summary

The **conductor/meta-agent pattern** is a superior architectural approach for complex tasks because:

1. ✅ **Separation of Concerns**: Conductor orchestrates, sub-agents execute
2. ✅ **Isolation**: Loop in sub-agent → terminate, no impact on conductor
3. ✅ **Specialization**: Each sub-agent focused on one thing
4. ✅ **Resilience**: Failed sub-agent → spawn replacement
5. ✅ **Simplicity**: Sub-agents don't need complex safety systems
6. ✅ **Composability**: Mix and match sub-agents for different workflows
7. ✅ **Natural Fit**: Reactive agents already async, already have lifecycle
8. ✅ **Proven Pattern**: Microservices, actor model, supervision trees

**This is NOT over-engineering** - this is proper distributed system design applied to agents. 🎯

Instead of building a more complex single agent, we **compose simple agents**. This is the Unix philosophy, the microservices pattern, the actor model - all proven architectures.

**Recommendation:** Implement conductor pattern first, keep intervention system as optional safety net.
