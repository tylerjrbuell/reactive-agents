# Installation

## Requirements

- Python 3.10 or higher
- pip or Poetry package manager

## Install with pip

```bash
pip install reactive-agents
```

## Install with Poetry

```bash
poetry add reactive-agents
```

## Development Installation

For contributing or development:

```bash
git clone https://github.com/tylerjrbuell/reactive-agents.git
cd reactive-agents
poetry install
```

To include documentation dependencies:

```bash
poetry install --with docs
```

## LLM Provider Setup

### Ollama (Local)

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull a model:
   ```bash
   ollama pull llama3
   ```
3. Configure your agent:
   ```python
   .with_model("ollama:llama3")
   ```

### OpenAI

1. Get an API key from [platform.openai.com](https://platform.openai.com)
2. Set the environment variable:
   ```bash
   export OPENAI_API_KEY="your-key-here"
   ```
3. Configure your agent:
   ```python
   .with_model("openai:gpt-4")
   ```

### Anthropic

1. Get an API key from [console.anthropic.com](https://console.anthropic.com)
2. Set the environment variable:
   ```bash
   export ANTHROPIC_API_KEY="your-key-here"
   ```
3. Configure your agent:
   ```python
   .with_model("anthropic:claude-3-sonnet")
   ```

### Google (Gemini)

1. Get an API key from Google AI Studio
2. Set the environment variable:
   ```bash
   export GOOGLE_API_KEY="your-key-here"
   ```
3. Configure your agent:
   ```python
   .with_model("google:gemini-pro")
   ```

### Groq

1. Get an API key from [console.groq.com](https://console.groq.com)
2. Set the environment variable:
   ```bash
   export GROQ_API_KEY="your-key-here"
   ```
3. Configure your agent:
   ```python
   .with_model("groq:llama3-70b")
   ```

## Verify Installation

```python
import reactive_agents
print(reactive_agents.__version__)
```

## Next Steps

- [Quick Start](quickstart.md) - Build your first agent
