# Development

Welcome to the development section of the Reactive Agents documentation. This section covers project planning, contribution guidelines, and release history.

## Current Status

**Version:** 0.1.0a6 (Alpha)

The framework is under active development. Breaking changes are expected during the alpha phase.

## Quick Links

- [Roadmap](roadmap.md) - Version milestones and planned features
- [Contributing](contributing.md) - How to contribute to the project
- [Changelog](changelog.md) - Version history and release notes

## Test Coverage

| Component | Coverage |
|-----------|----------|
| Overall | 61% |
| Core Engine | 87% |
| Tool Manager | 87% |
| Event Bus | 100% |

## Getting Started with Development

```bash
# Clone the repository
git clone https://github.com/tylerjrbuell/reactive-agents
cd reactive-agents

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=reactive_agents
```

## Priority Areas

1. **Streaming Support** - Add streaming to all providers
2. **Strategy Completion** - Complete PlanExecuteReflect and ReflectDecideAct
3. **Test Coverage** - Increase coverage to 75%+
4. **Documentation** - Complete API reference
