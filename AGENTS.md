# AGENTS.md

This file provides guidance to AI Agents when working with code in this repository.

## Quick Start Checklist

**Before running ANY command in this repository:**

- [ ] ✅ Use `poetry run <command>` OR enter `poetry shell` first
- [ ] ❌ NEVER manually activate: `source .venv/bin/activate`
- [ ] ❌ NEVER run Python/pytest directly without `poetry run`
- [ ] ✅ Virtual environment is at `.venv/` (managed by Poetry)
- [ ] ✅ Check you're in project root: `/home/tylerbuell/Documents/AIProjects/reactive-agents`

**Example correct commands:**

```bash
poetry run pytest                           # ✅ Correct
poetry run python playground/runner.py      # ✅ Correct

poetry shell                                # ✅ Enters poetry environment
pytest                                      # ✅ Now correct (inside shell)
python playground/runner.py                 # ✅ Now correct (inside shell)
```

**Example WRONG commands:**

```bash
pytest                                      # ❌ Not in poetry environment
python playground/runner.py                 # ❌ Will fail with import errors
source .venv/bin/activate                   # ❌ Don't manually activate
```

## Development Commands

### Virtual Environment Setup

**IMPORTANT: This project uses Poetry for dependency management.**

The virtual environment is located at `.venv/` in the project root.

```bash
# DO NOT manually activate the virtual environment
# Poetry handles this automatically with 'poetry run'

# WRONG - Don't do this:
source .venv/bin/activate
python script.py

# CORRECT - Use poetry run:
poetry run python script.py
poetry run pytest

# To run multiple commands in the poetry environment:
poetry shell  # Opens a new shell with venv activated
# Now you can run commands directly:
pytest
python playground/runner.py
```

**Key Points:**

- Virtual environment: `.venv/` (already created, don't recreate)
- Python version: 3.10+ (check with `poetry run python --version`)
- Always prefix commands with `poetry run` OR enter `poetry shell` first
- If you see import errors, you're likely not in the poetry environment

### Build & Test

```bash
# Install dependencies (first time or after pyproject.toml changes)
poetry install

# Run all tests (MUST use 'poetry run')
poetry run pytest

# Run specific test categories
poetry run pytest -m unit           # Unit tests only
poetry run pytest -m integration    # Integration tests only
poetry run pytest -m providers      # Provider tests only
poetry run pytest -m slow           # Long-running tests

# Run with coverage
poetry run pytest --cov=reactive_agents --cov-report=html

# Run specific test file
poetry run pytest reactive_agents/tests/unit/core/engine/test_execution_engine.py

# Run playground tests (manual/exploratory)
poetry run python playground/runner.py agents        # Basic functionality
poetry run python playground/runner.py strategies    # Reasoning strategies
poetry run python playground/runner.py stress        # Stress testing
poetry run python playground/runner.py real-world    # Real-world scenarios
```

### Linting & Formatting

```bash
# Format code
poetry run black .

# Check code style
poetry run ruff check .
```

### Documentation

```bash
# Build documentation
cd docs
mkdocs build

# Serve documentation locally
mkdocs serve
```

## Architecture Overview

### Core Component Hierarchy

The framework follows a **component-based architecture** with clear separation of concerns:

```
ReactiveAgent (app layer)
    ↓
ExecutionEngine (core/engine)
    ↓ coordinates
    ├── ReasoningEngine + StrategyManager (core/reasoning)
    ├── ToolManager (core/tools)
    ├── MemoryManager (core/memory)
    ├── EventBus (core/events)
    ├── MetricsManager (core/metrics)
    └── WorkflowManager (core/workflows)
```

### Key Design Patterns

1. **Builder Pattern**: `ReactiveAgentBuilder` provides fluent API for agent creation
2. **Strategy Pattern**: Multiple reasoning strategies (Reactive, Plan-Execute-Reflect, Reflect-Decide-Act, Adaptive)
3. **Event-Driven**: `EventBus` enables loose coupling and real-time monitoring
4. **Factory Pattern**: `ComponentFactory` creates and wires components
5. **Context Object**: `AgentContext` provides shared state across components

### Provider Architecture

All LLM providers implement `BaseModelProvider` with:

- **Universal Interface**: OpenAI-style parameters work across all providers
- **Native Translation**: Automatic conversion to provider-specific formats
- **Structured Outputs**: Uses `instructor` package for Pydantic validation

Supported providers:

- `openai`: GPT-4o, GPT-4, GPT-3.5
- `anthropic`: Claude 3.5 Sonnet, Claude 3
- `groq`: Llama 3, Mixtral (ultra-fast inference)
- `ollama`: Any local model (privacy-focused)
- `google`: Gemini Pro, Gemini Flash

### Tool System

Tools are registered and managed by `ToolManager`:

- **Custom Tools**: Python functions decorated with `@tool()`
- **MCP Tools**: Model Context Protocol servers (brave-search, sqlite, filesystem, etc.)
- **System Tools**: Internal framework actions (finish_task, pause, resume, etc.)
- **Meta Actions**: Agent self-monitoring and control

Tool lifecycle:

1. Registration → 2. Validation → 3. Execution → 4. Result handling → 5. Caching (optional)

### Reasoning Strategies

Each strategy implements `BaseReasoningStrategy`:

- **REACTIVE**: Fast, direct problem-solving (fewest iterations)
- **REFLECT_DECIDE_ACT**: Thoughtful, deliberate actions with reflection
- **PLAN_EXECUTE_REFLECT**: Structured planning and execution
- **ADAPTIVE**: AI selects strategy based on task complexity (default)

Strategy components:

- Planners (create execution plans)
- Executors (run tool calls)
- Reflectors (evaluate progress)
- Goal Evaluators (assess task completion)

### Memory System

Two-tier memory architecture:

- **Session Memory**: Short-term context maintained during execution
- **Vector Memory**: Long-term storage using ChromaDB with sentence-transformers embeddings

Memory operations:

- Context pruning strategies (oldest-first, least-relevant, token-based)
- Semantic search for retrieving relevant history
- Automatic summarization for context optimization

### Event System

Event types (all in `core/types/event_types.py`):

- Session events: `SessionStartedEvent`, `SessionEndedEvent`
- Task events: `TaskStatusChangedEvent`, `IterationStartedEvent`, `IterationCompletedEvent`
- Tool events: `ToolCalledEvent`, `ToolCompletedEvent`, `ToolFailedEvent`
- Reasoning events: `ReflectionGeneratedEvent`, `FinalAnswerSetEvent`
- System events: `MetricsUpdatedEvent`, `ErrorOccurredEvent`

## Type System

All types use Pydantic models for validation:

- `agent_types.py`: Agent configuration and state
- `reasoning_types.py`: Reasoning strategies and results
- `execution_types.py`: Execution results and agent output
- `session_types.py`: Session tracking and metrics
- `event_types.py`: Event data structures
- `status_types.py`: Task status enums
- `tool_types.py`: Tool definitions and results

When adding features, **always define Pydantic models in designated types files** before implementing logic.

## Important Implementation Notes

### Adding New Reasoning Strategies

1. Create strategy class in `core/reasoning/strategies/`
2. Implement `BaseReasoningStrategy` protocol
3. Register in `StrategyManager.STRATEGIES` dict
4. Add to `ReasoningStrategies` enum in `core/types/reasoning_types.py`
5. Add tests in `tests/unit/core/reasoning/strategies/`

### Adding New Tools

Custom tools:

```python
from reactive_agents import tool

@tool()
async def my_tool(param: str) -> str:
    """Tool description for the LLM."""
    # Implementation
    return result
```

MCP tools are auto-discovered from `~/.claude/mcp_config.json` or environment variable `MCP_CONFIG_PATH`.

### Adding New Providers

1. Create provider class in `providers/llm/`
2. Implement `BaseModelProvider` abstract methods
3. Define parameter mappings (`get_openai_params`, `get_native_params`)
4. Register in `providers/llm/factory.py`
5. Add to `Provider` enum in `app/builders/agent.py`
6. Add tests in `tests/integration/` with markers

### Event Handling

Always emit events for significant state changes:

```python
await context.event_bus.emit(
    AgentStateEvent.TOOL_CALLED,
    ToolCalledEventData(tool_name=name, arguments=args)
)
```

### Error Handling

The framework uses:

- **ErrorRecoveryOrchestrator**: Automatic retry with exponential backoff
- **Graceful Degradation**: Fallback strategies when primary approach fails
- **Comprehensive Logging**: Structured logs at multiple levels

Never swallow exceptions silently. Either handle them appropriately or let them propagate with context.

## Testing Guidelines

### Test Structure

Follow the template in `tests/README.md`:

- Unit tests: Test individual components in isolation
- Integration tests: Test component interactions
- Playground tests: Manual exploratory testing

### Running Tests Before Commits

```bash
# Quick validation
poetry run pytest -m unit --timeout=30

# Full test suite
poetry run pytest --cov=reactive_agents

# Integration tests (slower)
poetry run pytest -m integration
```

### Mocking External Dependencies

Use fixtures from `tests/conftest.py` and `tests/mocks.py`:

- `mock_agent_context`: Pre-configured context with all components
- `mock_tool_manager`: Tool manager with mock tools
- `mock_reasoning_engine`: Reasoning engine for testing
- `mock_mcp_client`: MCP client that doesn't require real servers

## Public API vs Internal Components

**What users should interact with:**

### Public API (in `reactive_agents/__init__.py`)

Users should ONLY import from main package:

```python
from reactive_agents import (
    ReactiveAgentBuilder,      # Agent creation
    tool,                       # Tool decorator
    Provider,                   # LLM provider enum
    ReasoningStrategies,        # Strategy enum
    ExecutionResult,            # Agent output
    AgentSession,               # Session info
    # ... other explicitly exported items
)
```

### Internal Components (NOT for direct user import)

Everything else is internal:

- `reactive_agents.core.*` - Framework internals
- `reactive_agents.app.agents.*` - Agent implementations
- `reactive_agents.providers.*` - Provider implementations
- `reactive_agents.config.*` - Configuration internals

**Rule:** If it's not in `reactive_agents/__init__.py.__all__`, it's internal and subject to change.

## Common Pitfalls

1. **Poetry environment**: ALWAYS use `poetry run` before commands, or enter `poetry shell` first. Never activate `.venv/bin/activate` manually. If you get import errors, you're not in the poetry environment.
2. **Don't bypass the builder**: Always use `ReactiveAgentBuilder` to create agents, never instantiate `ReactiveAgent` directly
3. **Context management**: The agent is an async context manager - use `async with agent:` or call `await agent.__aenter__()` explicitly
4. **Tool decorator**: The `@tool()` decorator requires parentheses even with no arguments
5. **Provider strings**: Use format `"provider:model"` (e.g., `"ollama:llama3"`) not just model name
6. **Async everywhere**: All agent operations are async, don't forget `await`
7. **Don't import internals**: Only import from `reactive_agents`, not `reactive_agents.core.*` in user code

## Project Structure Conventions

- `reactive_agents/app/`: User-facing API and high-level abstractions
- `reactive_agents/core/`: Framework internals and core logic
- `reactive_agents/providers/`: External integrations (LLMs, storage, MCP)
- `reactive_agents/config/`: Configuration management
- `reactive_agents/utils/`: Shared utilities
- `reactive_agents/tests/`: Test suite (mirrors source structure)
- `playground/`: Manual testing and experimentation
- `examples/`: User-facing example code
- `docs/`: Documentation source
- `.claude/session_docs/`: **Session-specific documentation** (analysis, reports, temporary docs)
- `AGENTS.md`: **Permanent agent guidance** (this file, lives in root)

### Documentation File Conventions

**Permanent documentation** (committed to repo):

- `AGENTS.md` - Agent guidance (root directory)
- `README.md` - User-facing project overview
- `docs/` - MkDocs documentation
- `reactive_agents/tests/README.md` - Test suite documentation
- `playground/README.md` - Playground usage guide

**Session-specific documentation** (temporary, not committed):

- `.claude/session_docs/` - All session analysis, findings, reports
- Examples: analysis reports, implementation plans, investigation summaries
- These files are session-specific and should NOT be committed to the repository

**Rule:** When creating documentation during a session (analysis, findings, plans), write to `.claude/session_docs/`. Only if you are a claude agent. Otherwise, write to permanent root-level or where appropriate.

## Quick Reference: File Locations

**"I want to..." → "Edit this file"**

| Task                        | Primary File(s)                       | Related Files                                                         |
| --------------------------- | ------------------------------------- | --------------------------------------------------------------------- |
| Add new builder method      | `app/builders/agent.py`               | `core/types/agent_types.py`                                           |
| Add new reasoning strategy  | `core/reasoning/strategies/[name].py` | `core/reasoning/strategy_manager.py`, `core/types/reasoning_types.py` |
| Add new LLM provider        | `providers/llm/[provider].py`         | `providers/llm/factory.py`, `app/builders/agent.py`                   |
| Add new tool                | `core/tools/[category].py`            | `core/tools/tool_manager.py`                                          |
| Add new event type          | `core/types/event_types.py`           | `core/events/event_bus.py`                                            |
| Modify execution loop       | `core/engine/execution_engine.py`     | `core/reasoning/engine.py`                                            |
| Change tool execution       | `core/tools/tool_executor.py`         | `core/tools/tool_manager.py`                                          |
| Add memory functionality    | `core/memory/memory_manager.py`       | `core/memory/vector_memory_manager.py`                                |
| Add workflow features       | `core/workflows/workflow_manager.py`  | `app/workflows/`                                                      |
| Change agent initialization | `app/agents/reactive_agent.py`        | `core/factory/component_factory.py`                                   |
| Add metrics/scoring         | `core/metrics/metrics_manager.py`     | `core/types/session_types.py`                                         |
| Modify prompts              | `core/reasoning/prompts/base.py`      | `core/reasoning/strategy_components.py`                               |

## Key Files to Read First

**Priority reading list for understanding the codebase:**

### Tier 1: Essential Architecture (Read these first)

1. `reactive_agents/__init__.py` - Public API surface
2. `app/builders/agent.py` - How agents are created (Builder pattern)
3. `core/engine/execution_engine.py` - Main execution loop
4. `core/types/` - All type definitions (scan all files here)

### Tier 2: Core Systems (Read next)

5. `core/tools/tool_manager.py` - Tool registration and execution
6. `core/reasoning/strategy_manager.py` - Strategy selection
7. `core/events/event_bus.py` - Event system
8. `core/context/agent_context.py` - Shared state container

### Tier 3: Implementation Details (Read as needed)

9. `providers/llm/base.py` - Provider interface
10. `core/reasoning/strategies/` - Individual strategy implementations
11. `core/factory/component_factory.py` - Component wiring

## Common Code Patterns

**Copy-paste starting points for common tasks:**

### Creating an Agent (User Code)

```python
# Save as: example_agent.py
# Run with: poetry run python example_agent.py

from reactive_agents import ReactiveAgentBuilder, tool, ReasoningStrategies
import asyncio

@tool()
async def custom_tool(query: str) -> str:
    """Tool description for LLM."""
    return f"Result: {query}"

async def main():
    agent = await (
        ReactiveAgentBuilder()
        .with_name("Agent Name")
        .with_model("ollama:llama3")
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_custom_tools([custom_tool])
        .with_mcp_tools(["brave-search"])
        .with_instructions("System instructions here")
        .build()
    )

    async with agent:
        result = await agent.run("Task description")
        print(result.final_answer)

if __name__ == "__main__":
    asyncio.run(main())
```

### Adding a Builder Method

```python
def with_new_feature(self, value: SomeType) -> "ReactiveAgentBuilderT":
    """Configure new feature.

    Args:
        value: Description of parameter

    Returns:
        Self for method chaining
    """
    self._config["new_feature"] = value
    return self
```

### Emitting Events

```python
from reactive_agents.core.types.event_types import AgentStateEvent, CustomEventData

await self.context.event_bus.emit(
    AgentStateEvent.CUSTOM_EVENT,
    CustomEventData(
        field1="value1",
        field2="value2"
    )
)
```

### Defining New Types

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class MyNewType(BaseModel):
    """Description of this type."""

    field1: str = Field(..., description="Required field")
    field2: Optional[int] = Field(None, description="Optional field")
    field3: List[str] = Field(default_factory=list, description="List field")

    model_config = ConfigDict(frozen=True)  # Immutable
```

### Adding Tool with Validation

```python
from reactive_agents import tool
from pydantic import BaseModel, Field

class ToolInput(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(10, ge=1, le=100, description="Result limit")

@tool(name="search_tool", description="Searches for information")
async def search_tool(input: ToolInput) -> dict:
    """Search implementation."""
    return {
        "results": [...],
        "count": input.limit
    }
```

### Testing with Fixtures

```python
import pytest
from reactive_agents.core.context.agent_context import AgentContext

@pytest.fixture
async def agent_context():
    """Create test agent context."""
    from tests.mocks import create_mock_context
    return create_mock_context()

async def test_feature(agent_context: AgentContext):
    """Test description."""
    # Arrange
    expected = "value"

    # Act
    result = await some_function(agent_context)

    # Assert
    assert result == expected
```

## Entry Points Reference

**Where execution starts for different use cases:**

### User Agent Execution

1. User calls `ReactiveAgentBuilder().build()` → `app/builders/agent.py:build()`
2. Creates components via `ComponentFactory` → `core/factory/component_factory.py`
3. Initializes `ReactiveAgent` → `app/agents/reactive_agent.py:__init__()`
4. User calls `agent.run()` → `app/agents/reactive_agent.py:run()`
5. Delegates to `ExecutionEngine.execute()` → `core/engine/execution_engine.py:execute()`

### Tool Execution Flow

1. LLM requests tool → `core/engine/execution_engine.py` receives tool call
2. Validates tool → `core/tools/tool_validator.py:validate_tool_call()`
3. Checks confirmation → `core/tools/tool_confirmation.py` (if enabled)
4. Executes tool → `core/tools/tool_executor.py:execute_tool()`
5. Emits events → `core/events/event_bus.py:emit()`
6. Returns result → Back to execution engine

### Strategy Selection Flow

1. Task received → `core/engine/execution_engine.py:execute()`
2. Classify task → `core/reasoning/task_classifier.py:classify_task()`
3. Select strategy → `core/reasoning/strategy_manager.py:select_strategy()`
4. Execute strategy → `core/reasoning/strategies/[strategy].py:execute_iteration()`
5. Monitor progress → `core/reasoning/goal_evaluator.py:evaluate_progress()`

## Configuration Files Map

**Where to find and modify settings:**

| Configuration   | File Location                              | Environment Variable                        |
| --------------- | ------------------------------------------ | ------------------------------------------- |
| Poetry deps     | `pyproject.toml`                           | -                                           |
| Test settings   | `pyproject.toml` [tool.pytest.ini_options] | -                                           |
| MCP servers     | `~/.claude/mcp_config.json`                | `MCP_CONFIG_PATH`                           |
| API keys        | `.env` (not in repo)                       | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. |
| Logging         | `config/logging.py`                        | `LOG_LEVEL`                                 |
| Default prompts | `core/reasoning/prompts/base.py`           | -                                           |
| Model defaults  | `providers/llm/[provider].py`              | `OLLAMA_HOST`, etc.                         |

## Naming Conventions

**Follow these patterns for consistency:**

### Files

- Types: `[domain]_types.py` (e.g., `agent_types.py`, `tool_types.py`)
- Managers: `[component]_manager.py` (e.g., `tool_manager.py`)
- Protocols: `[component]_protocol.py` or within `protocols.py`
- Tests: `test_[component].py`

### Classes

- Managers: `[Component]Manager` (e.g., `ToolManager`, `MemoryManager`)
- Builders: `[Component]Builder` (e.g., `ReactiveAgentBuilder`)
- Protocols: `[Component]Protocol` (e.g., `ToolProtocol`)
- Events: `[EventName]EventData` (e.g., `ToolCalledEventData`)
- Configs: `[Component]Config` (e.g., `ReactiveAgentConfig`)

### Methods

- Builder methods: `with_[feature]()` (returns self)
- Async operations: Always use `async def` prefix with `await`
- Private methods: `_[method_name]()` (single underscore)
- Event handlers: `on_[event_name]()` or `handle_[event_name]()`

### Variables

- Context: `context` or `agent_context`
- Configuration: `config` or `[component]_config`
- Results: `result` (single) or `results` (multiple)
- Sessions: `session`

## Common Imports Cheat Sheet

**Frequently used imports:**

```python
# Core types
from reactive_agents.core.types.agent_types import ReactiveAgentConfig
from reactive_agents.core.types.reasoning_types import ReasoningStrategies, ReasoningContext
from reactive_agents.core.types.execution_types import ExecutionResult
from reactive_agents.core.types.event_types import AgentStateEvent
from reactive_agents.core.types.session_types import AgentSession
from reactive_agents.core.types.tool_types import Tool, ToolResult

# Public API
from reactive_agents import (
    ReactiveAgentBuilder,
    tool,
    Provider,
    ReasoningStrategies,
)

# Context and managers
from reactive_agents.core.context.agent_context import AgentContext
from reactive_agents.core.tools.tool_manager import ToolManager
from reactive_agents.core.events.event_bus import EventBus

# Type checking (avoid circular imports)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from reactive_agents.app.agents.base import Agent

# Pydantic
from pydantic import BaseModel, Field, ConfigDict
```

## Execution Flow Quick View

**High-level flow for typical agent execution:**

```
User Code
  ↓
ReactiveAgentBuilder.build()
  ↓
ComponentFactory.create_all_components()
  ├→ Create ToolManager (registers tools)
  ├→ Create MemoryManager (initializes storage)
  ├→ Create EventBus (sets up listeners)
  ├→ Create ReasoningEngine (loads strategies)
  └→ Create ExecutionEngine (orchestrates all)
  ↓
ReactiveAgent.__init__() (wires components)
  ↓
agent.run(task) [User calls this]
  ↓
ExecutionEngine.execute(task)
  ↓
TaskClassifier.classify_task(task)
  ↓
StrategyManager.select_strategy(classification)
  ↓
ReasoningStrategy.execute_iteration(task, context)
  ├→ Generate plan (if needed)
  ├→ Call LLM with tools
  ├→ Parse tool calls
  └→ Execute tools via ToolManager
      ↓
  ToolExecutor.execute_tool()
      ├→ Validate arguments
      ├→ Check confirmation (if needed)
      ├→ Run tool function
      └→ Return ToolResult
  ↓
GoalEvaluator.evaluate_progress(session)
  ├→ Check if task complete
  ├→ Evaluate quality
  └→ Decide: continue or finish
  ↓
Return ExecutionResult to user
```

## Debugging Quick Guide

**Common issues and where to look:**

### Import errors / Module not found

- **First check:** Are you using `poetry run` or inside `poetry shell`?
- **Check:** Run `poetry install` to ensure all dependencies are installed
- **Check:** Virtual environment exists: `ls .venv/`
- **Check:** Python version: `poetry run python --version` (should be 3.10+)
- **Never:** Don't manually activate with `source .venv/bin/activate`

### Agent won't start / Build fails

- **Check:** `ComponentFactory.create_all_components()` in `core/factory/component_factory.py`
- **Check:** Required parameters in `ReactiveAgentConfig` in `core/types/agent_types.py`
- **Check:** Provider initialization in `providers/llm/factory.py`

### Tools not executing

- **Check:** Tool registration in `ToolManager.register_tool()`
- **Check:** Tool schema validation in `core/tools/tool_validator.py`
- **Check:** MCP server connectivity (try: `mcp list` in terminal)
- **Check:** `self.context.tool_manager.tools` contains expected tools

### Strategy not working as expected

- **Check:** Task classification in `core/reasoning/task_classifier.py:classify_task()`
- **Check:** Strategy selection logic in `core/reasoning/strategy_manager.py:select_strategy()`
- **Check:** Strategy state machine in `core/reasoning/state_machine.py`
- **Debug:** Add logging in `ExecutionEngine._execute_reasoning_iteration()`

### Memory/Context issues

- **Check:** Context pruning settings in builder (`.with_context_pruning_strategy()`)
- **Check:** Token counting in `core/memory/memory_manager.py`
- **Check:** Vector store initialization in `core/memory/vector_memory_manager.py`

### Events not firing

- **Check:** Event subscription in `core/events/event_bus.py:subscribe()`
- **Check:** Event emission in component code (search for `.emit()`)
- **Check:** Event type is in `AgentStateEvent` enum

### Tests failing

- **Check:** Fixtures in `tests/conftest.py` and `tests/mocks.py`
- **Check:** Async handling - all test functions should be `async def`
- **Check:** Mock MCP client is enabled with `export MOCK_MCP_CLIENT=1`
- **Run:** Single test with `-v -s` flags for detailed output

### Type errors from LSP

- **Import issue:** Add `from typing import TYPE_CHECKING` and conditional import
- **Circular import:** Move import inside TYPE_CHECKING block
- **Missing type:** Check if type is exported in `__init__.py`
- **Protocol violation:** Check method signatures match protocol definition

### Performance issues

- **Profile:** Check `session.iteration_count` (high = inefficient)
- **Profile:** Check `session.tool_call_history` (too many = strategy issue)
- **Profile:** Check context size with `len(session.context)`
- **Optimize:** Enable context pruning, adjust `max_iterations`, or change strategy

## LSP and Type Safety

The codebase uses Pyright LSP for type checking. Always:

- Fix LSP diagnostic errors before committing
- Use type hints on all public functions
- Import TYPE_CHECKING for circular dependency resolution
- Use `TypeVar` for generic types in builders

When you see IDE diagnostics, prioritize fixing them - they usually indicate real issues.
