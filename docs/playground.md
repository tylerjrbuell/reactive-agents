# Playground - Testing & Development

The Reactive Agents Playground is a comprehensive testing suite for validating framework functionality, performance, and production readiness.

## Overview

The playground provides interactive test suites for:

- **Basic Functionality** - Core features validation
- **Reasoning Strategies** - Strategy testing and comparison
- **Stress Testing** - Performance and edge case testing
- **Real-World Scenarios** - Production-ready use case validation
- **Memory & Learning** - Persistence and context management
- **System Tools** - Meta-actions and agent control

## Quick Start

```bash
# Navigate to the project root
cd reactive-agents

# Run specific test suite
poetry run python -m playground.runner agents
poetry run python -m playground.runner strategies
poetry run python -m playground.runner stress
poetry run python -m playground.runner real-world

# Run all tests
poetry run python -m playground.runner all

# List available test suites
poetry run python -m playground.runner --list
```

## Test Suites

### 1. Agents (Basic Functionality)

**Purpose:** Validate core framework features

**Tests:**
- Agent creation and lifecycle
- Tool integration and execution
- Event system functionality
- Custom tool registration
- MCP tool integration

**Command:** `poetry run python -m playground.runner agents`

**Expected Duration:** 30-60 seconds

---

### 2. Strategies (Reasoning)

**Purpose:** Test and compare reasoning strategies

**Strategies Tested:**

#### REACTIVE
- **Speed:** Fastest
- **Best For:** Quick responses, simple tasks
- **Iterations:** 1-2
- **Example:** "What is 2+2?"

#### REFLECT_DECIDE_ACT (RDA)
- **Speed:** Moderate
- **Best For:** Thoughtful decisions, quality over speed
- **Iterations:** 3-5
- **Example:** "Should I invest in stocks or bonds?"

#### PLAN_EXECUTE_REFLECT (PER)
- **Speed:** Slower
- **Best For:** Complex multi-step tasks
- **Iterations:** 5-10
- **Example:** "Research and write a report on AI trends"

#### ADAPTIVE
- **Speed:** Variable
- **Best For:** Unknown task complexity
- **Iterations:** AI-determined
- **Example:** Any task - AI selects best strategy

**Command:** `poetry run python -m playground.runner strategies`

**Expected Duration:** 60-120 seconds

---

### 3. Stress Tests

**Purpose:** Push framework to limits and find breaking points

**Test Scenarios:**

#### Complex Multi-Step Reasoning
- Chains multiple tools
- Maintains context across steps
- Tests tool dependency resolution

#### Error Recovery
- Simulates tool failures
- Tests retry mechanisms
- Validates graceful degradation

#### Strategy Switching
- Detects ineffective strategies
- Dynamically switches approaches
- Optimizes execution path

#### Context Management
- Long conversations (20+ messages)
- Context pruning under token limits
- Memory retention verification

#### Concurrent Agents
- Multiple agents running simultaneously
- Resource contention handling
- Thread safety validation

**Command:** `poetry run python -m playground.runner stress`

**Expected Duration:** 120-180 seconds

**What to Watch:**
- Memory leaks with long-running agents
- Context corruption with concurrent execution
- Strategy switching delays
- Tool dependency resolution issues

---

### 4. Real-World Scenarios

**Purpose:** Validate production readiness with realistic use cases

**Scenarios:**

#### Customer Support Agent
- **Task:** Handle customer inquiries professionally
- **Tests:** Multi-turn conversations, order lookups, escalation handling
- **Success Criteria:** Professional tone, accurate information, helpful responses

#### Data Analysis Agent
- **Task:** Analyze datasets and generate insights
- **Tests:** Statistical analysis, visualization, reporting
- **Success Criteria:** Accurate calculations, meaningful insights, clear communication

#### Research Assistant
- **Task:** Synthesize information from multiple sources
- **Tests:** Web search, source citation, comprehensive summaries
- **Success Criteria:** Thorough research, proper attribution, coherent synthesis

#### Code Reviewer
- **Task:** Review code for quality and security
- **Tests:** Security analysis, pattern detection, best practice recommendations
- **Success Criteria:** Accurate findings, helpful suggestions, clear explanations

#### Task Automation
- **Task:** Execute multi-step workflows
- **Tests:** Dependency management, error handling, status reporting
- **Success Criteria:** Workflow completion, proper error recovery, clear status updates

**Command:** `poetry run python -m playground.runner real-world`

**Expected Duration:** 200-300 seconds

**Validation Metrics:**
- Response quality and professionalism
- Tool usage appropriateness
- Context retention across turns
- Insight quality and depth
- Error handling in complex scenarios

---

### 5. Memory & Learning

**Purpose:** Test persistence and cross-session learning

**Tests:**
- Memory storage and retrieval
- Vector similarity search
- Context summarization
- Cross-session learning
- Memory-guided execution

**Command:** `poetry run python -m playground.runner memory`

---

### 6. System Tools

**Purpose:** Test meta-actions and agent control

**Tests:**
- `final_answer` - Task completion signaling
- `request_clarification` - Information gathering
- `agent_stuck` - Loop detection and intervention

**Command:** `poetry run python -m playground.runner system-tools`

---

## Performance Benchmarks

### Expected Performance
*(Using Ollama with local models on standard hardware)*

| Test Suite | Duration | Iterations | Tool Calls |
|------------|----------|------------|------------|
| Agents (Basic) | 30-60s | 1-3 | 2-5 |
| Strategies | 60-120s | 3-10 | 3-8 |
| Stress Tests | 120-180s | 5-15 | 5-20 |
| Real-World | 200-300s | 4-10 | 4-12 |
| Memory | 40-80s | 2-6 | 3-8 |
| System Tools | 30-60s | 2-5 | 2-6 |

**Note:** Actual performance varies by:
- Model provider (OpenAI, Anthropic, Google, Groq, Ollama)
- Model size (7B, 14B, 70B parameters)
- Hardware (CPU vs GPU, available VRAM)
- Network latency (cloud APIs vs local models)

---

## Metrics to Track

For each test run, the playground tracks:

### Success Metrics
- **Pass Rate:** Percentage of tests passing
- **Iteration Efficiency:** Average iterations per task
- **Tool Usage:** Appropriate tool selection
- **Duration:** Performance benchmarks
- **Error Rate:** Reliability indicators

### Quality Metrics
- **Completion Score:** Task completion quality (0-1.0)
- **Tool Usage Score:** Tool usage efficiency (0-1.0)
- **Overall Score:** Combined performance metric (0-1.0)
- **Strategy Switches:** Adaptation effectiveness

### Diagnostic Data
- Full execution history
- Context evolution
- Tool call sequences
- Error traces
- Memory snapshots

---

## Debugging Failed Tests

### Step-by-Step Debugging

#### 1. Enable Debug Logging
```python
from reactive_agents import ReactiveAgentBuilder, LogLevel

agent = await (
    ReactiveAgentBuilder()
    .with_log_level(LogLevel.DEBUG)
    .build()
)
```

#### 2. Inspect Session Data
```python
result = await agent.run(task)

# Check session metrics
print(f"Iterations: {result.session.iteration_count}")
print(f"Completion Score: {result.session.completion_score}")
print(f"Tool Calls: {len(result.session.tool_call_history)}")

# Inspect tool usage
for tool_call in result.session.successful_tools:
    print(f"Tool: {tool_call['tool_name']}")
    print(f"Result: {tool_call['result']}")
```

#### 3. Analyze Context
```python
# Check context messages
context_manager = agent.context.context_manager
messages = context_manager.get_messages()

for msg in messages:
    print(f"{msg['role']}: {msg['content'][:100]}...")
```

#### 4. Review Event History
```python
# Subscribe to events for real-time monitoring
def on_tool_called(event):
    print(f"Tool called: {event['tool_name']}")

agent = await (
    ReactiveAgentBuilder()
    .on_tool_called(on_tool_called)
    .build()
)
```

---

## Adding Custom Tests

### Test Structure

Create a new test file in `playground/`:

```python
"""
test_my_feature.py - Description of what this tests
"""

import asyncio
from reactive_agents import ReactiveAgentBuilder

async def test_my_scenario(model: str = "ollama:qwen2:7b") -> bool:
    """
    Test specific scenario.

    Returns:
        bool: True if test passed
    """
    try:
        agent = await (
            ReactiveAgentBuilder()
            .with_name("Test Agent")
            .with_model(model)
            .build()
        )

        async with agent:
            result = await agent.run("Test task description")

            # Validate results
            assert result.was_successful()
            assert result.final_answer

            return True

    except Exception as e:
        print(f"Test failed: {e}")
        return False


async def run_all_tests(model: str = "ollama:qwen2:7b"):
    """Run all tests in this module."""
    results = {}

    print("\n=== Running My Tests ===\n")

    results["my_scenario"] = await test_my_scenario(model)

    # Print summary
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")

    return results


async def run(model: str = "ollama:qwen2:7b", **kwargs):
    """Entry point for runner."""
    return await run_all_tests(model)


if __name__ == "__main__":
    asyncio.run(run())
```

### Register in Runner

Add to `playground/runner.py`:

```python
TEST_SUITES = {
    # ... existing tests
    "my-tests": {
        "module": test_my_feature,
        "description": "Test my custom feature",
    },
}
```

### Run Your Tests

```bash
poetry run python -m playground.runner my-tests
```

---

## Best Practices

### Good Tests Should

✅ **Test ONE specific capability** - Focus on single feature

✅ **Have clear success criteria** - Assertions and validations

✅ **Provide diagnostic output** - Helpful error messages

✅ **Be reproducible** - Consistent results across runs

✅ **Document expected behavior** - Comments and docstrings

✅ **Handle exceptions gracefully** - Try/except with logging

### Avoid

❌ **Testing multiple unrelated things** - Keep tests focused

❌ **Relying on specific LLM responses** - Responses vary

❌ **Flaky assertions** - Use robust validation

❌ **Silent failures** - Always log failures

❌ **Insufficient error messages** - Provide context

---

## Continuous Testing

### Pre-Commit Testing
```bash
# Quick smoke test before commits
poetry run python -m playground.runner agents
```

### Full Test Suite
```bash
# Comprehensive validation before releases
poetry run python -m playground.runner all
```

### Performance Monitoring
```bash
# Track performance over time
poetry run python -m playground.runner stress > perf_log.txt
```

---

## Next Steps

1. **Run Basic Tests** - Validate installation
   ```bash
   poetry run python -m playground.runner agents
   ```

2. **Explore Strategies** - Compare reasoning approaches
   ```bash
   poetry run python -m playground.runner strategies
   ```

3. **Stress Test** - Find breaking points
   ```bash
   poetry run python -m playground.runner stress
   ```

4. **Validate Production** - Test real scenarios
   ```bash
   poetry run python -m playground.runner real-world
   ```

5. **Add Custom Tests** - Extend coverage for your use cases

---

## Contributing

Found an issue? Want to add tests?

1. Create test file in `playground/`
2. Follow the test structure guidelines
3. Register in `runner.py`
4. Submit a pull request

---

**Happy Testing! 🚀**
