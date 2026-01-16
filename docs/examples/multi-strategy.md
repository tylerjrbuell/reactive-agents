# Multi-Strategy Example

Compare different reasoning strategies on the same task.

## Complete Code

```python
import asyncio
from reactive_agents import ReactiveAgentBuilder, tool, ReasoningStrategies

@tool()
async def search(query: str) -> str:
    """Search for information.

    Args:
        query: The search query
    """
    # Simulated search results
    return f"Search results for '{query}': Found 3 relevant articles."


@tool()
async def analyze(data: str) -> str:
    """Analyze data and extract insights.

    Args:
        data: The data to analyze
    """
    return f"Analysis of '{data}': Key insight - positive trend detected."


async def create_agent(strategy: ReasoningStrategies, name: str):
    """Create an agent with a specific strategy."""
    return await (
        ReactiveAgentBuilder()
        .with_name(name)
        .with_model("ollama:llama3")
        .with_role("Research Analyst")
        .with_instructions(
            "You are a research analyst. Use available tools to gather "
            "information and provide thorough analysis."
        )
        .with_reasoning_strategy(strategy)
        .with_enable_dynamic_strategy_switching(False)  # Lock strategy
        .with_custom_tools([search, analyze])
        .with_max_iterations(15)
        .build()
    )


async def run_with_strategy(strategy: ReasoningStrategies, task: str):
    """Run a task with a specific strategy and report results."""
    name = f"{strategy.value}Agent"
    print(f"\n{'='*60}")
    print(f"Strategy: {strategy.value.upper()}")
    print(f"{'='*60}")

    agent = await create_agent(strategy, name)

    iteration_count = 0
    tools_used = []

    def on_iteration(e):
        nonlocal iteration_count
        iteration_count = e["iteration"]
        print(f"  Iteration {e['iteration']}: {e['strategy']}")

    def on_tool(e):
        tools_used.append(e["tool_name"])
        print(f"    -> Tool: {e['tool_name']}")

    agent.on_iteration_started(on_iteration)
    agent.on_tool_called(on_tool)

    async with agent:
        result = await agent.run(task)

        print(f"\nResults:")
        print(f"  Status: {result.status.value}")
        print(f"  Iterations: {iteration_count}")
        print(f"  Tools used: {', '.join(tools_used) or 'None'}")
        print(f"  Success: {result.was_successful()}")
        print(f"\nAnswer:\n{result.final_answer}")

    return {
        "strategy": strategy.value,
        "iterations": iteration_count,
        "tools_used": tools_used,
        "success": result.was_successful()
    }


async def main():
    task = (
        "Research the current trends in renewable energy and provide "
        "a brief analysis with key insights."
    )

    print(f"Task: {task}")

    # Test each strategy
    strategies = [
        ReasoningStrategies.REACTIVE,
        ReasoningStrategies.REFLECT_DECIDE_ACT,
        ReasoningStrategies.PLAN_EXECUTE_REFLECT,
    ]

    results = []
    for strategy in strategies:
        result = await run_with_strategy(strategy, task)
        results.append(result)

    # Summary comparison
    print(f"\n{'='*60}")
    print("STRATEGY COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"{'Strategy':<25} {'Iterations':>10} {'Tools':>10} {'Success':>10}")
    print("-" * 60)
    for r in results:
        print(
            f"{r['strategy']:<25} "
            f"{r['iterations']:>10} "
            f"{len(r['tools_used']):>10} "
            f"{'Yes' if r['success'] else 'No':>10}"
        )


if __name__ == "__main__":
    asyncio.run(main())
```

## Strategy Behaviors

### REACTIVE Strategy

- **Approach**: Direct prompt-response
- **Iterations**: Usually 1-3
- **Best for**: Simple, straightforward tasks
- **Behavior**: Makes quick decisions, calls tools immediately if needed

### REFLECT_DECIDE_ACT Strategy

- **Approach**: Think before acting
- **Iterations**: Usually 3-7
- **Best for**: Tasks requiring careful consideration
- **Behavior**: Reflects on progress, considers alternatives

### PLAN_EXECUTE_REFLECT Strategy

- **Approach**: Plan first, then execute
- **Iterations**: Usually 5-15
- **Best for**: Complex multi-step tasks
- **Behavior**: Creates explicit plan, executes step by step

## Expected Output

```
Task: Research the current trends in renewable energy...

============================================================
Strategy: REACTIVE
============================================================
  Iteration 1: reactive
    -> Tool: search
  Iteration 2: reactive
    -> Tool: analyze

Results:
  Status: complete
  Iterations: 2
  Tools used: search, analyze
  Success: Yes

Answer:
Based on my research, renewable energy trends show...

============================================================
Strategy: REFLECT_DECIDE_ACT
============================================================
  Iteration 1: reflect_decide_act
  Iteration 2: reflect_decide_act
    -> Tool: search
  Iteration 3: reflect_decide_act
  Iteration 4: reflect_decide_act
    -> Tool: analyze

Results:
  Status: complete
  Iterations: 4
  Tools used: search, analyze
  Success: Yes

Answer:
After careful reflection and research, here's my analysis...

============================================================
Strategy: PLAN_EXECUTE_REFLECT
============================================================
  Iteration 1: plan_execute_reflect
  Iteration 2: plan_execute_reflect
    -> Tool: search
  Iteration 3: plan_execute_reflect
  Iteration 4: plan_execute_reflect
    -> Tool: analyze
  Iteration 5: plan_execute_reflect
  Iteration 6: plan_execute_reflect

Results:
  Status: complete
  Iterations: 6
  Tools used: search, analyze
  Success: Yes

Answer:
Following my research plan:
1. Initial search revealed...
2. Analysis shows...
3. Key insights include...

============================================================
STRATEGY COMPARISON SUMMARY
============================================================
Strategy                  Iterations      Tools    Success
------------------------------------------------------------
reactive                           2          2        Yes
reflect_decide_act                 4          2        Yes
plan_execute_reflect               6          2        Yes
```

## Choosing the Right Strategy

### Use REACTIVE when:

- Tasks are simple and well-defined
- Quick responses are important
- Tool calls are straightforward

### Use REFLECT_DECIDE_ACT when:

- Tasks require careful thought
- Mistakes would be costly
- You want more deliberate reasoning

### Use PLAN_EXECUTE_REFLECT when:

- Tasks have multiple steps
- Order of operations matters
- You need structured output

### Use ADAPTIVE when:

- Task complexity is unknown
- You want the framework to decide
- Tasks vary significantly
