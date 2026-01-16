# Multi-Agent Architecture - Flexible Team Composition

**Date:** January 15, 2026
**Status:** Design Proposal
**Principle:** Flexibility and DX First - Every agent composable with intuitive API

---

## Vision

> **Support multiple agent operating modes with a unified, composable API that doesn't get in your way**

### Operating Modes

1. **Solo Agent** - Lightweight, focused, single-agent tasks (current style)
2. **Team-Based** - Leader + worker pods with shared workspace
3. **Advanced Multi-Agent** - Multiple teams with cross-pod collaboration

**Guiding Principles:**
- ✅ **DX First** - API should feel natural, not bureaucratic
- ✅ **Composable** - Mix and match configurations
- ✅ **Progressive Enhancement** - Start simple, add complexity when needed
- ✅ **No Lock-in** - Solo agents can join teams, teams can go solo

---

## Design Philosophy

### Like Kubernetes, but for Agents

```
Solo Agent     = Single container (lightweight, focused)
Pod            = Agent with role in a team
Team           = Deployment (leader + workers + shared storage)
Swarm          = Cluster (multiple teams collaborating)
```

### Progressive Complexity

```python
# Level 1: Solo (simple, current style)
agent = await AgentBuilder().with_tools([...]).build()
await agent.run("task")

# Level 2: Team (leader + workers + workspace)
team = await TeamBuilder()
    .with_leader("coordinator")
    .add_worker("researcher", tools=[...])
    .add_worker("analyst", tools=[...])
    .with_shared_workspace()
    .build()
await team.run("complex task")

# Level 3: Swarm (multi-team collaboration)
swarm = await SwarmBuilder()
    .add_team("research_team", research_team)
    .add_team("analysis_team", analysis_team)
    .enable_cross_team_communication()
    .build()
await swarm.run("enterprise task")
```

---

## Core Abstractions

### 1. Solo Agent (Current)

**Purpose:** Single agent for focused tasks

```python
from reactive_agents import AgentBuilder, Provider

# Minimal configuration
agent = await (
    AgentBuilder()
    .with_model(Provider.OLLAMA, "cogito:14b")
    .with_tools([search, calculate])
    .build()
)

result = await agent.run("What is 2+2?")
```

**Characteristics:**
- Lightweight (no overhead)
- Fast (single LLM call path)
- Simple (minimal configuration)
- Isolated (no shared state)

---

### 2. Pod (Team Member)

**Purpose:** Agent with a role in a team

```python
from reactive_agents import PodConfig, PodRole

# Define a pod configuration
researcher_pod = PodConfig(
    name="researcher",
    role=PodRole.WORKER,  # LEADER, WORKER, VALIDATOR, SPECIALIST
    tools=[web_search, fetch_url, summarize],
    max_iterations=5,
    description="Searches web and gathers information",
    capabilities=["research", "web_search", "summarization"],
)

analyst_pod = PodConfig(
    name="analyst",
    role=PodRole.WORKER,
    tools=[analyze_data, create_chart, calculate_stats],
    max_iterations=5,
    description="Analyzes data and creates visualizations",
    capabilities=["analysis", "statistics", "visualization"],
)

validator_pod = PodConfig(
    name="validator",
    role=PodRole.VALIDATOR,
    tools=[check_facts, verify_sources],
    max_iterations=3,
    description="Validates research and analysis results",
    capabilities=["validation", "fact_checking"],
)
```

**Pod Roles:**
- `LEADER` - Orchestrates team, delegates tasks
- `WORKER` - Executes assigned tasks
- `VALIDATOR` - Reviews and validates work
- `SPECIALIST` - Deep expertise in specific domain

**Pod Communication:**
```python
# Pods can communicate via workspace
class Pod:
    async def send_message(self, to_pod: str, message: dict):
        """Send message to another pod in the team."""

    async def broadcast(self, message: dict):
        """Broadcast message to all pods in team."""

    async def request_validation(self, work: dict) -> dict:
        """Request validation from validator pod."""
```

---

### 3. Workspace (Shared Memory)

**Purpose:** Shared storage and context for team members

```python
from reactive_agents import Workspace, WorkspaceConfig

# Configure shared workspace
workspace = WorkspaceConfig(
    storage_type="vector",  # "vector", "memory", "hybrid"
    vector_db="chroma",     # For semantic search across team knowledge
    persistence=True,       # Persist across sessions
    access_control={
        "read": ["*"],      # All pods can read
        "write": ["leader", "worker"],  # Only leader and workers can write
        "delete": ["leader"],  # Only leader can delete
    }
)
```

**Workspace Features:**

```python
class Workspace:
    """Shared storage and context for team."""

    async def store(self, key: str, value: Any, metadata: dict = None):
        """Store data in workspace."""

    async def retrieve(self, key: str) -> Any:
        """Retrieve data by key."""

    async def search(self, query: str, top_k: int = 5) -> List[dict]:
        """Semantic search across workspace (vector storage)."""

    async def get_context(self) -> dict:
        """Get current shared context for all pods."""

    async def add_task_result(self, pod_name: str, task: str, result: Any):
        """Record task completion in shared history."""

    async def get_pod_results(self, pod_name: str) -> List[dict]:
        """Get all results from a specific pod."""
```

**Why Workspace?**
- ✅ Pods share knowledge (no duplicate work)
- ✅ Semantic search (find relevant past work)
- ✅ Validation (validators can access worker outputs)
- ✅ Continuity (persist team knowledge across sessions)

---

### 4. Team (Leader + Workers + Workspace)

**Purpose:** Coordinated group of agents with shared goals

```python
from reactive_agents import TeamBuilder

# Define team
research_team = await (
    TeamBuilder()
    .with_name("research_team")
    .with_leader(
        name="coordinator",
        tools=[delegate_task, get_pod_status, request_validation],
        max_iterations=15,
    )
    .add_worker(researcher_pod)
    .add_worker(analyst_pod)
    .add_validator(validator_pod)
    .with_workspace(workspace)
    .with_team_goal("Research and analyze topics thoroughly")
    .build()
)

# Run team
result = await research_team.run(
    "Research AI safety best practices and create comprehensive report"
)
```

**Team Execution Flow:**

```
1. Leader receives task
2. Leader decomposes into subtasks
3. Leader delegates to workers based on capabilities
4. Workers execute in parallel (if possible)
5. Workers store results in workspace
6. Validator reviews critical work
7. Leader aggregates results
8. Team returns final answer
```

**Leader Tools (Auto-injected):**

```python
@tool(category="team")
async def delegate_task(
    pod_name: str,
    task: str,
    context: dict = None,
    priority: int = 1,
) -> dict:
    """Delegate a task to a specific pod.

    Args:
        pod_name: Name of pod to delegate to
        task: Clear description of task
        context: Additional context from workspace
        priority: Task priority (1-5, 5 highest)

    Returns:
        {
            "task_id": "unique_id",
            "status": "assigned",
            "pod": "pod_name",
        }
    """

@tool(category="team")
async def get_pod_status(pod_name: str = None) -> dict:
    """Get status of pods in team.

    Args:
        pod_name: Specific pod (or None for all pods)

    Returns:
        {
            "pod_name": {
                "status": "idle" | "working" | "completed",
                "current_task": "...",
                "completed_tasks": 5,
            }
        }
    """

@tool(category="team")
async def request_validation(
    work_type: str,
    work_data: dict,
    validator: str = None,
) -> dict:
    """Request validation of work from validator pod.

    Args:
        work_type: Type of work (research, analysis, etc.)
        work_data: Work to validate
        validator: Specific validator (or auto-select)

    Returns:
        {
            "validated": True/False,
            "feedback": "...",
            "confidence": 0.95,
        }
    """

@tool(category="team")
async def search_team_knowledge(query: str, top_k: int = 5) -> List[dict]:
    """Search team's shared workspace for relevant knowledge.

    Uses semantic search on workspace vector storage.
    """

@tool(category="team")
async def broadcast_to_team(message: dict) -> dict:
    """Send message to all team members."""
```

**Worker Tools (Auto-injected):**

```python
@tool(category="team")
async def report_progress(status: str, details: dict = None):
    """Report progress to leader."""

@tool(category="team")
async def request_help(issue: str, from_pod: str = None):
    """Request help from leader or specific pod."""

@tool(category="team")
async def store_in_workspace(key: str, value: Any, metadata: dict = None):
    """Store data in shared workspace."""

@tool(category="team")
async def search_workspace(query: str) -> List[dict]:
    """Search workspace for relevant information."""
```

---

### 5. Team Builder API (Ergonomic)

**Design Goal:** Make team creation feel natural

```python
from reactive_agents import TeamBuilder, PodConfig, PodRole

# Approach 1: Explicit pod configs (most control)
team = await (
    TeamBuilder()
    .with_name("data_team")
    .with_leader(
        name="coordinator",
        model=Provider.OLLAMA,
        model_name="cogito:14b",
        max_iterations=20,
    )
    .add_pod(PodConfig(
        name="collector",
        role=PodRole.WORKER,
        tools=[fetch_data, scrape_web],
        capabilities=["data_collection"],
    ))
    .add_pod(PodConfig(
        name="cleaner",
        role=PodRole.WORKER,
        tools=[clean_data, normalize],
        capabilities=["data_cleaning"],
    ))
    .add_pod(PodConfig(
        name="analyzer",
        role=PodRole.WORKER,
        tools=[analyze, visualize],
        capabilities=["analysis"],
    ))
    .with_workspace(storage_type="vector", persistence=True)
    .build()
)

# Approach 2: Quick workers (less verbose for simple cases)
team = await (
    TeamBuilder()
    .with_leader("coordinator")
    .add_worker("researcher", tools=[search, fetch])
    .add_worker("writer", tools=[write_file])
    .add_validator("reviewer", tools=[check_quality])
    .with_shared_workspace()  # Use defaults
    .build()
)

# Approach 3: From template (pre-configured teams)
from reactive_agents.templates import ResearchTeam

team = await ResearchTeam.create(
    model=Provider.OLLAMA,
    model_name="cogito:14b",
    additional_tools=[custom_tool],
)

# Templates available:
# - ResearchTeam (researcher + analyst + writer + validator)
# - DataTeam (collector + cleaner + analyzer + validator)
# - DevTeam (architect + coder + tester + reviewer)
# - ContentTeam (researcher + writer + editor + publisher)
```

**Team Configuration:**

```python
class TeamConfig:
    """Configuration for team behavior."""

    name: str
    leader_config: PodConfig
    worker_configs: List[PodConfig]
    workspace_config: WorkspaceConfig

    # Team behavior
    parallel_execution: bool = True  # Workers run in parallel
    validation_required: bool = False  # Require validation for all work
    max_team_iterations: int = 50  # Total iterations for whole team

    # Communication
    allow_pod_to_pod: bool = True  # Workers can talk directly
    require_leader_approval: bool = False  # All tasks approved by leader

    # Failure handling
    retry_failed_tasks: bool = True
    max_retries_per_task: int = 2
    fallback_strategy: str = "leader_takes_over"  # "fail_fast", "leader_takes_over", "reassign"
```

---

### 6. Advanced Multi-Agent (Cross-Team)

**Purpose:** Multiple teams collaborating on large tasks

```python
from reactive_agents import SwarmBuilder

# Create teams first
research_team = await TeamBuilder().with_leader(...).build()
analysis_team = await TeamBuilder().with_leader(...).build()
writing_team = await TeamBuilder().with_leader(...).build()

# Create swarm
swarm = await (
    SwarmBuilder()
    .with_name("content_pipeline")
    .add_team("research", research_team)
    .add_team("analysis", analysis_team)
    .add_team("writing", writing_team)
    .with_shared_workspace()  # Global workspace across teams
    .enable_cross_team_messaging()
    .with_workflow([
        ("research", "analysis"),  # research → analysis
        ("analysis", "writing"),   # analysis → writing
    ])
    .build()
)

# Run swarm (follows workflow)
result = await swarm.run(
    "Research AI trends, analyze implications, write whitepaper"
)
```

**Swarm Features:**

```python
class Swarm:
    """Multiple teams working together."""

    async def run(self, task: str) -> SwarmResult:
        """Execute task across teams following workflow."""

    async def send_to_team(self, team_name: str, task: str, context: dict):
        """Send task to specific team."""

    async def broadcast_to_all_teams(self, message: dict):
        """Broadcast to all teams."""

    async def get_team_status(self, team_name: str = None) -> dict:
        """Get status of teams."""
```

**Swarm Execution:**

```
Task: "Research AI trends, analyze, write whitepaper"

1. Swarm Controller receives task
2. Breaks into team tasks:
   - Research Team: "Research current AI trends"
   - Analysis Team: "Analyze trends from research"
   - Writing Team: "Write whitepaper from analysis"

3. Execute workflow:
   Research Team:
     - Leader delegates to researcher pods
     - Researchers work in parallel
     - Results stored in global workspace
     → Done → Trigger Analysis Team

   Analysis Team:
     - Reads research from workspace
     - Analysts process data
     - Stores analysis in workspace
     → Done → Trigger Writing Team

   Writing Team:
     - Reads analysis from workspace
     - Writers create sections
     - Editor validates
     → Done → Return to Swarm

4. Swarm aggregates final result
```

---

## API Examples

### Example 1: Solo Agent (Simple Task)

```python
# Quick calculation - no team needed
calc_agent = await (
    AgentBuilder()
    .with_model(Provider.OLLAMA, "cogito:14b")
    .with_tools([calculate])
    .with_max_iterations(2)
    .build()
)

result = await calc_agent.run("What is 15% of 230?")
# Fast, simple, no overhead
```

### Example 2: Team (Research Task)

```python
# Complex research - use team
research_team = await (
    TeamBuilder()
    .with_leader("coordinator")
    .add_worker("web_researcher", tools=[search, fetch, extract])
    .add_worker("paper_researcher", tools=[arxiv_search, pdf_extract])
    .add_worker("synthesizer", tools=[summarize, combine])
    .add_validator("fact_checker", tools=[verify_facts])
    .with_shared_workspace()
    .build()
)

result = await research_team.run(
    "Research transformer architecture innovations in 2025"
)

# Team workflow:
# 1. Leader splits: web research + paper research
# 2. Researchers work in parallel
# 3. Synthesizer combines findings
# 4. Fact checker validates
# 5. Leader produces final report
```

### Example 3: Swarm (Enterprise Pipeline)

```python
# Enterprise content pipeline - use swarm
data_team = await TeamBuilder()...  # Collect and clean data
analysis_team = await TeamBuilder()...  # Analyze data
insight_team = await TeamBuilder()...  # Generate insights
writing_team = await TeamBuilder()...  # Write reports

content_swarm = await (
    SwarmBuilder()
    .add_team("data", data_team)
    .add_team("analysis", analysis_team)
    .add_team("insights", insight_team)
    .add_team("writing", writing_team)
    .with_workflow([
        ("data", "analysis"),
        ("analysis", "insights"),
        ("insights", "writing"),
    ])
    .build()
)

result = await content_swarm.run(
    "Generate Q4 market analysis report from raw sales data"
)
```

---

## Implementation Architecture

### Module Structure

```
reactive_agents/
├── app/
│   ├── agents/
│   │   ├── solo.py         # Solo agent (current)
│   │   ├── pod.py          # Pod agent (team member)
│   │   └── team.py         # Team agent (leader)
│   ├── builders/
│   │   ├── agent_builder.py     # Solo agent builder
│   │   ├── team_builder.py      # Team builder
│   │   └── swarm_builder.py     # Swarm builder
│   └── templates/
│       ├── research_team.py     # Pre-configured research team
│       ├── data_team.py         # Pre-configured data team
│       └── dev_team.py          # Pre-configured dev team
├── core/
│   ├── workspace/
│   │   ├── workspace.py         # Workspace implementation
│   │   ├── vector_store.py      # Vector storage backend
│   │   └── memory_store.py      # In-memory backend
│   ├── communication/
│   │   ├── message.py           # Message protocol
│   │   ├── pod_channel.py       # Pod-to-pod communication
│   │   └── team_channel.py      # Team-to-team communication
│   └── coordination/
│       ├── task_queue.py        # Task distribution
│       ├── workflow.py          # Workflow execution
│       └── aggregator.py        # Result aggregation
└── tools/
    └── team_tools.py            # Team-specific tools
```

### Core Components

#### 1. Workspace Implementation

```python
# reactive_agents/core/workspace/workspace.py

from typing import Any, List, Optional, Dict
from dataclasses import dataclass
import chromadb


@dataclass
class WorkspaceEntry:
    """Entry in workspace."""
    key: str
    value: Any
    metadata: Dict[str, Any]
    pod_name: str
    timestamp: float


class Workspace:
    """Shared workspace for team members."""

    def __init__(self, config: WorkspaceConfig):
        self.config = config
        self.memory: Dict[str, Any] = {}

        if config.storage_type in ["vector", "hybrid"]:
            self.vector_db = chromadb.Client()
            self.collection = self.vector_db.create_collection(
                name=config.name or "team_workspace"
            )

    async def store(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict] = None,
        pod_name: str = "unknown",
    ):
        """Store data in workspace."""
        entry = WorkspaceEntry(
            key=key,
            value=value,
            metadata=metadata or {},
            pod_name=pod_name,
            timestamp=time.time(),
        )

        # Store in memory
        self.memory[key] = entry

        # Store in vector DB for semantic search
        if hasattr(self, 'collection'):
            self.collection.add(
                documents=[str(value)],
                metadatas=[{
                    **metadata,
                    "key": key,
                    "pod_name": pod_name,
                }],
                ids=[key],
            )

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[WorkspaceEntry]:
        """Semantic search across workspace."""
        if not hasattr(self, 'collection'):
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filter,
        )

        # Convert to WorkspaceEntry objects
        entries = []
        for doc_id in results['ids'][0]:
            if doc_id in self.memory:
                entries.append(self.memory[doc_id])

        return entries

    async def get_context(self) -> Dict[str, Any]:
        """Get current shared context."""
        return {
            "total_entries": len(self.memory),
            "pods_active": len(set(e.pod_name for e in self.memory.values())),
            "recent_activity": self._get_recent_activity(limit=10),
        }
```

#### 2. Pod Implementation

```python
# reactive_agents/app/agents/pod.py

from reactive_agents.app.agents.base import Agent
from reactive_agents.core.workspace.workspace import Workspace


class Pod(Agent):
    """Agent with role in a team."""

    def __init__(
        self,
        config: PodConfig,
        workspace: Workspace,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.config = config
        self.workspace = workspace
        self.role = config.role
        self.capabilities = config.capabilities

        # Inject team tools based on role
        self._inject_team_tools()

    def _inject_team_tools(self):
        """Inject team-specific tools based on role."""
        from reactive_agents.tools.team_tools import (
            create_team_tools_for_role
        )

        team_tools = create_team_tools_for_role(
            role=self.role,
            workspace=self.workspace,
            pod=self,
        )

        self.context.tool_manager.tools.extend(team_tools)
        self.context.tool_manager.register_tools()

    async def send_message(self, to_pod: str, message: Dict[str, Any]):
        """Send message to another pod."""
        await self.workspace.store(
            key=f"message_{to_pod}_{int(time.time()*1000)}",
            value=message,
            metadata={
                "type": "message",
                "from_pod": self.config.name,
                "to_pod": to_pod,
            },
            pod_name=self.config.name,
        )

    async def get_messages(self) -> List[Dict[str, Any]]:
        """Get messages sent to this pod."""
        entries = await self.workspace.search(
            query="",  # Get all
            filter={"to_pod": self.config.name, "type": "message"},
        )
        return [e.value for e in entries]
```

#### 3. Team Implementation

```python
# reactive_agents/app/agents/team.py

class Team:
    """Team of agents with shared workspace."""

    def __init__(
        self,
        config: TeamConfig,
        leader: Pod,
        workers: List[Pod],
        workspace: Workspace,
    ):
        self.config = config
        self.leader = leader
        self.workers = workers
        self.workspace = workspace
        self.task_queue = TaskQueue()

    async def run(self, task: str) -> TeamResult:
        """Execute task as a team."""

        # Store task in workspace
        await self.workspace.store(
            key="current_task",
            value=task,
            metadata={"type": "task", "status": "running"},
            pod_name="team",
        )

        # Leader orchestrates
        leader_result = await self.leader.run(task)

        # Aggregate all results from workspace
        all_results = await self._aggregate_results()

        return TeamResult(
            task=task,
            leader_response=leader_result,
            worker_results=all_results,
            workspace_snapshot=await self.workspace.get_context(),
        )

    async def _aggregate_results(self) -> Dict[str, Any]:
        """Aggregate results from all workers."""
        results = {}
        for worker in self.workers:
            worker_entries = await self.workspace.search(
                query="",
                filter={"pod_name": worker.config.name},
            )
            results[worker.config.name] = [e.value for e in worker_entries]

        return results
```

---

## Progressive Enhancement Examples

### Start Simple → Add Complexity

```python
# Week 1: Solo agent
agent = await AgentBuilder().with_tools([...]).build()
await agent.run("simple task")

# Week 2: Add a helper
team = await (
    TeamBuilder()
    .with_leader("main")
    .add_worker("helper", tools=[...])
    .build()
)

# Week 3: Add validation
team = await (
    TeamBuilder()
    .with_leader("main")
    .add_worker("worker", tools=[...])
    .add_validator("checker", tools=[...])  # NEW
    .build()
)

# Week 4: Add shared workspace
team = await (
    TeamBuilder()
    .with_leader("main")
    .add_worker("worker", tools=[...])
    .add_validator("checker", tools=[...])
    .with_shared_workspace()  # NEW - semantic search
    .build()
)

# Week 5: Multiple teams
swarm = await (
    SwarmBuilder()
    .add_team("team1", team1)
    .add_team("team2", team2)
    .build()
)
```

**Key Point:** You don't need to learn everything at once. Start with what you need, add when you grow.

---

## Summary

### Three Agent Modes

1. **Solo** - Fast, lightweight, single agent
   ```python
   agent = await AgentBuilder().with_tools([...]).build()
   ```

2. **Team** - Leader + workers + shared workspace
   ```python
   team = await TeamBuilder()
       .with_leader(...)
       .add_workers([...])
       .with_workspace()
       .build()
   ```

3. **Swarm** - Multi-team collaboration
   ```python
   swarm = await SwarmBuilder()
       .add_teams([...])
       .with_workflow([...])
       .build()
   ```

### Design Principles

✅ **Flexibility** - Choose the right tool for the job
✅ **DX First** - API feels natural, not bureaucratic
✅ **Composable** - Mix and match configurations
✅ **Progressive** - Start simple, add complexity when needed
✅ **No Lock-in** - Change modes as needs evolve
✅ **Shared State** - Workspace for team coordination
✅ **Observable** - Full visibility into team operations

### Next Steps

Should I:
1. **Start implementing Solo → Team migration** (Phase 1)?
2. **Build Workspace + Pod abstractions** (Core components)?
3. **Create TeamBuilder API** (User-facing)?
4. **Prototype a simple team** to validate design?

This architecture gives you **maximum flexibility without sacrificing simplicity**. 🎯
