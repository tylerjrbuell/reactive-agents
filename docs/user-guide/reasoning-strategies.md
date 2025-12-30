# Reasoning Strategies

Reactive Agents supports multiple reasoning strategies for different task types.

## Available Strategies

```python
from reactive_agents import ReasoningStrategies

ReasoningStrategies.REACTIVE              # Simple prompt-response
ReasoningStrategies.REFLECT_DECIDE_ACT    # Reflection-based
ReasoningStrategies.PLAN_EXECUTE_REFLECT  # Planning upfront
ReasoningStrategies.ADAPTIVE              # Dynamic switching
```

## Strategy Comparison

| Strategy | Best For | Iterations | Complexity |
|----------|----------|------------|------------|
| REACTIVE | Simple tasks, Q&A | Few | Low |
| REFLECT_DECIDE_ACT | Tasks needing careful thought | Medium | Medium |
| PLAN_EXECUTE_REFLECT | Complex multi-step tasks | Many | High |
| ADAPTIVE | Unknown or varied tasks | Varies | Auto |

## REACTIVE Strategy

The simplest strategy - direct prompt-response with state tracking.

```python
.with_reasoning_strategy(ReasoningStrategies.REACTIVE)
```

**Best for:**

- Simple questions and answers
- Single-step tasks
- Tool-augmented responses
- Quick interactions

**How it works:**

1. Receive task
2. Think and optionally call tools
3. Provide final answer

**Example tasks:**

- "What is 2 + 2?"
- "Search for the weather in Paris"
- "Summarize this text"

## REFLECT_DECIDE_ACT Strategy

Adds explicit reflection before each action.

```python
.with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)
```

**Best for:**

- Tasks requiring careful consideration
- Multi-turn reasoning
- Error-prone operations
- Tasks where mistakes are costly

**How it works:**

1. **Reflect** - Consider the current state and progress
2. **Decide** - Choose the best next action
3. **Act** - Execute the decision
4. Repeat until complete

**Example tasks:**

- "Debug this code and explain your reasoning"
- "Analyze this data and make recommendations"
- "Research this topic thoroughly"

## PLAN_EXECUTE_REFLECT Strategy

Creates an explicit plan before execution.

```python
.with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
```

**Best for:**

- Complex multi-step tasks
- Projects with clear milestones
- Tasks requiring coordination
- When you need visibility into the approach

**How it works:**

1. **Plan** - Create a detailed step-by-step plan
2. **Execute** - Work through each step
3. **Reflect** - After each step, evaluate progress
4. **Adapt** - Modify the plan if needed

**Example tasks:**

- "Build a web scraper that extracts product data"
- "Create a report analyzing sales trends"
- "Implement a new feature with tests"

## ADAPTIVE Strategy

Automatically selects the best strategy based on task analysis.

```python
.with_reasoning_strategy(ReasoningStrategies.ADAPTIVE)
```

**Best for:**

- Varied or unknown task types
- When you don't know the best approach
- Production systems handling diverse requests

**How it works:**

1. Analyzes the task characteristics
2. Selects the most appropriate strategy
3. Can switch strategies mid-execution if needed

## Choosing a Strategy

### Decision Flowchart

```
Is the task simple and straightforward?
├─ Yes → REACTIVE
└─ No
    ├─ Do you need careful reasoning at each step?
    │   └─ Yes → REFLECT_DECIDE_ACT
    ├─ Is there a clear sequence of steps?
    │   └─ Yes → PLAN_EXECUTE_REFLECT
    └─ Unsure? → ADAPTIVE
```

### Task Type Guidelines

| Task Type | Recommended Strategy |
|-----------|---------------------|
| Simple Q&A | REACTIVE |
| Tool usage | REACTIVE |
| Analysis | REFLECT_DECIDE_ACT |
| Debugging | REFLECT_DECIDE_ACT |
| Multi-step projects | PLAN_EXECUTE_REFLECT |
| Research | PLAN_EXECUTE_REFLECT |
| Mixed/Unknown | ADAPTIVE |

## Strategy Configuration

### Disable Dynamic Switching

By default, agents may switch strategies. To lock to a specific strategy:

```python
.with_reasoning_strategy(ReasoningStrategies.REACTIVE)
.with_enable_dynamic_strategy_switching(False)  # Lock to REACTIVE
```

### Strategy Mode

```python
# Static mode - never switch
.with_strategy_mode("static")
.with_static_strategy("reactive")

# Adaptive mode - can switch based on task
.with_strategy_mode("adaptive")
```

## Iteration Settings

Each strategy has different iteration needs:

```python
# REACTIVE - usually completes quickly
.with_reasoning_strategy(ReasoningStrategies.REACTIVE)
.with_max_iterations(5)

# REFLECT_DECIDE_ACT - needs more iterations
.with_reasoning_strategy(ReasoningStrategies.REFLECT_DECIDE_ACT)
.with_max_iterations(10)

# PLAN_EXECUTE_REFLECT - may need many iterations
.with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
.with_max_iterations(20)
```

## Monitoring Strategy Execution

Use events to see which strategy is executing:

```python
agent.on_iteration_started(lambda e: print(f"Strategy: {e['strategy']}"))
agent.on_iteration_completed(lambda e: print(f"Iteration {e['iteration']} done"))
```

## Strategy Performance

Check which strategy was used after execution:

```python
result = await agent.run("Task")
print(f"Strategy used: {result.strategy_used}")
print(f"Iterations: {result.session.iterations}")
```

## Best Practices

1. **Start simple** - Use REACTIVE unless you have a reason not to
2. **Match complexity** - More complex tasks need more sophisticated strategies
3. **Set appropriate iterations** - Under-iteration causes incomplete results
4. **Use ADAPTIVE when unsure** - Let the framework decide
5. **Monitor and tune** - Watch execution to understand strategy behavior
