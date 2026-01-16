# Contributing

Thank you for your interest in contributing to Reactive Agents!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/tylerjrbuell/reactive-agents
cd reactive-agents

# Install dependencies with Poetry
poetry install

# Activate virtual environment
poetry shell
```

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=reactive_agents

# Run specific test file
poetry run pytest reactive_agents/tests/unit/core/engine/test_execution_engine.py

# Run with verbose output
poetry run pytest -v
```

## Code Quality

```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check .

# Type checking
poetry run pyright
```

## Priority Areas

See the [Roadmap](roadmap.md) for current priorities. Key areas include:

1. **Streaming Support** - Implementing streaming across all providers
2. **Strategy Completion** - Completing PlanExecuteReflect and ReflectDecideAct strategies
3. **Test Coverage** - Increasing coverage on critical components
4. **Documentation** - Improving API documentation and examples

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `poetry run pytest`
6. Commit with descriptive message
7. Push and create a Pull Request

## Commit Message Format

```
type: short description

Longer description if needed.

- Bullet points for multiple changes
- Another change
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

## Code Style

- Use type hints throughout
- Follow PEP 8 conventions
- Use Pydantic models for data structures
- Write docstrings in Google style
- Keep functions focused and testable
