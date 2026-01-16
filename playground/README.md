# Reactive Agents Playground

Comprehensive testing suite for the Reactive Agents framework.

## Test Suites

### 1. Basic Tests (agents, streaming, workflows)

**Purpose:** Validate core functionality

- Agent creation and lifecycle
- Tool integration
- Event system
- Streaming responses
- Workflow orchestration

**Run:** `python main.py agents`

### 2. Strategy Tests

**Purpose:** Test reasoning strategies

- REACTIVE: Quick, single-step responses
- REFLECT_DECIDE_ACT: Thoughtful, deliberate actions
- PLAN_EXECUTE_REFLECT: Structured planning and execution
- ADAPTIVE: Dynamic strategy switching

**Run:** `python main.py strategies`

### 3. Stress Tests ⚡ NEW

**Purpose:** Push the framework to its limits

**Tests:**

- **Complex Multi-Step Reasoning**: Chain multiple tools, maintain context
- **Error Recovery**: Handle failures gracefully, retry with adaptations
- **Strategy Switching**: Detect when strategy isn't working, switch dynamically
- **Context Management**: Handle long conversations, context pruning, memory retention
- **Concurrent Agents**: Multiple agents running simultaneously
- **Max Iterations**: Behavior when hitting iteration limits
- **Tool Chaining**: Complex dependent tool calls

**Run:** `python main.py stress`

**What to Watch For:**

- Memory leaks with long-running agents
- Context corruption with concurrent execution
- Strategy switching delays
- Tool dependency resolution
- Graceful degradation under constraints

### 4. Real-World Scenarios 🌍 NEW

**Purpose:** Validate production readiness

**Scenarios:**

- **Customer Support Agent**: Multi-turn conversations, order lookups, professional responses
- **Data Analysis Agent**: Statistical analysis, insight generation, report creation
- **Research Assistant**: Multi-source synthesis, citation tracking, comprehensive summaries
- **Code Reviewer**: Security analysis, pattern detection, best practice recommendations
- **Task Automation**: Workflow execution, dependency management, status reporting

**Run:** `python main.py real-world`

**What to Watch For:**

- Response quality and professionalism
- Tool usage appropriateness
- Context retention across turns
- Insight quality
- Error handling in complex scenarios

## Running Tests

```bash
# Run specific test suite
python main.py agents
python main.py stress
python main.py real-world

# Run all tests
python main.py all

# List available tests
python main.py --list
```

## Test Design Philosophy

### Stress Tests

Focus on **breaking the framework** to find:

- Edge cases
- Performance bottlenecks
- Resource leaks
- Concurrency issues
- Error handling gaps

### Real-World Tests

Focus on **practical applicability** to validate:

- Use case coverage
- Response quality
- Professional behavior
- Production readiness
- Business value

## Adding New Tests

1. Create test file in `playground/`
2. Implement test functions
3. Add `run_all_*()` aggregator function
4. Add `async def run()` entry point
5. Register in `runner.py` TEST_SUITES

Example:

```python
async def test_my_scenario(model: str = "cogito:14b") -> bool:
    """Test description."""
    agent = await ReactiveAgentBuilder()...
    result = await agent.run(task)
    return result.was_successful()

async def run_all_my_tests(model: str = "cogito:14b"):
    """Run all tests in this module."""
    results = {}
    # ... run tests
    return results

async def run(model: str = "cogito:14b", **kwargs):
    """Entry point for runner."""
    return await run_all_my_tests(model)
```

## Performance Benchmarks

### Expected Performance (cogito:14b on local hardware)

**Basic Tests:**

- Simple Q&A: 8-10s, 1-2 iterations
- Tool usage: 15-20s, 2-3 iterations
- Workflows: 50-90s, multi-agent

**Stress Tests:**

- Complex reasoning: 30-60s, 5-8 iterations
- Error recovery: 20-40s, 3-6 iterations
- Concurrent agents: 15-25s total (parallel)

**Real-World Tests:**

- Customer support: 30-50s, 4-6 iterations
- Data analysis: 40-60s, 5-8 iterations
- Research: 50-80s, 6-10 iterations

## Metrics to Track

For each test run, monitor:

- **Success Rate**: % of tests passing
- **Iteration Count**: Efficiency indicator
- **Tool Usage**: Are tools being called appropriately?
- **Duration**: Performance benchmark
- **Error Count**: Reliability indicator
- **Strategy Switches**: Adaptation effectiveness

## Debugging Failed Tests

1. **Check Logs**: Set `log_level="debug"` in agent builder
2. **Inspect Session**: `result.session` contains full execution history
3. **Tool Calls**: `result.session.successful_tools` shows which tools ran
4. **Iterations**: High count may indicate stuck loops
5. **Context**: Check if context is being maintained properly

## Contributing Tests

Good tests should:

- ✅ Test ONE specific capability
- ✅ Have clear success criteria
- ✅ Provide diagnostic output
- ✅ Be reproducible
- ✅ Document expected behavior
- ✅ Handle exceptions gracefully

Avoid:

- ❌ Testing multiple unrelated things
- ❌ Relying on specific LLM responses
- ❌ Flaky assertions
- ❌ Silent failures
- ❌ Insufficient error messages

## Next Steps

1. **Run Stress Tests** - Find breaking points
2. **Run Real-World Tests** - Validate practical use
3. **Analyze Failures** - Identify improvement areas
4. **Add New Scenarios** - Expand coverage
5. **Benchmark Performance** - Track improvements over time
6. **Iterate** - Continuous improvement cycle
