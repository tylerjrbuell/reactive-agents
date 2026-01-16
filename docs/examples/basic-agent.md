# Basic Agent Example

A simple example showing how to create and run an agent.

## Complete Code

```python
import asyncio
from reactive_agents import ReactiveAgentBuilder, ReasoningStrategies

async def main():
    # Create the agent using the builder pattern
    agent = await (
        ReactiveAgentBuilder()
        .with_name("BasicAgent")
        .with_model("ollama:llama3")  # Use your preferred model
        .with_role("Helpful Assistant")
        .with_instructions(
            "You are a helpful assistant. Answer questions clearly and concisely."
        )
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .with_max_iterations(5)
        .with_log_level("info")
        .build()
    )

    try:
        # Run a simple task
        result = await agent.run("What is the capital of France?")

        # Check the result
        print(f"\nStatus: {result.status.value}")
        print(f"Success: {result.was_successful()}")
        print(f"Iterations: {result.session.iterations}")
        print(f"\nAnswer:\n{result.final_answer}")

    finally:
        # Always clean up
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
```

## Step-by-Step Explanation

### 1. Import Required Classes

```python
from reactive_agents import ReactiveAgentBuilder, ReasoningStrategies
```

- `ReactiveAgentBuilder` - The builder for creating agents
- `ReasoningStrategies` - Enum with available strategies

### 2. Build the Agent

```python
agent = await (
    ReactiveAgentBuilder()
    .with_name("BasicAgent")
    .with_model("ollama:llama3")
    .with_role("Helpful Assistant")
    .with_instructions("...")
    .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
    .with_max_iterations(5)
    .build()
)
```

Each method configures an aspect of the agent:

- `with_name()` - Identifier for logging
- `with_model()` - LLM provider and model
- `with_role()` - Agent's persona
- `with_instructions()` - Behavioral guidelines
- `with_reasoning_strategy()` - How the agent thinks
- `with_max_iterations()` - Maximum reasoning cycles

### 3. Run a Task

```python
result = await agent.run("What is the capital of France?")
```

The `run()` method:

- Starts a new session
- Executes the reasoning strategy
- Returns an `ExecutionResult`

### 4. Process the Result

```python
print(f"Status: {result.status.value}")
print(f"Success: {result.was_successful()}")
print(f"Answer: {result.final_answer}")
```

The `ExecutionResult` provides:

- `status` - TaskStatus enum (COMPLETE, ERROR, etc.)
- `was_successful()` - Boolean check
- `final_answer` - The agent's response
- `session` - Session details (iterations, errors, etc.)

### 5. Clean Up

```python
await agent.close()
```

Always close the agent to release resources.

## Using Context Manager

For automatic cleanup:

```python
async def main():
    agent = await (
        ReactiveAgentBuilder()
        .with_name("BasicAgent")
        .with_model("ollama:llama3")
        .build()
    )

    async with agent:
        result = await agent.run("What is 2 + 2?")
        print(result.final_answer)
    # Agent is automatically closed
```

## Multiple Tasks

Run multiple tasks with the same agent:

```python
async def main():
    agent = await builder.build()

    async with agent:
        # First task
        result1 = await agent.run("What is the capital of France?")
        print(f"Answer 1: {result1.final_answer}")

        # Second task
        result2 = await agent.run("What is the capital of Germany?")
        print(f"Answer 2: {result2.final_answer}")

        # Third task
        result3 = await agent.run("What is 15 * 7?")
        print(f"Answer 3: {result3.final_answer}")
```

## With Event Monitoring

Add events to see what's happening:

```python
async def main():
    agent = await builder.build()

    # Add event handlers
    agent.on_session_started(
        lambda e: print(f"Started session {e['session_id']}")
    )
    agent.on_iteration_started(
        lambda e: print(f"Iteration {e['iteration']}")
    )
    agent.on_session_ended(
        lambda e: print("Session complete")
    )

    async with agent:
        result = await agent.run("Tell me a joke")
        print(f"\n{result.final_answer}")
```

## Expected Output

```
Started session abc-123
Iteration 1
Session complete

Status: complete
Success: True
Iterations: 1

Answer:
The capital of France is Paris.
```
