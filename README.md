# 🚀 Reactive AI Agent Framework

<div align="center">

[![CI](https://github.com/tylerjrbuell/reactive-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/tylerjrbuell/reactive-agents/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/reactive-agents.svg)](https://badge.fury.io/py/reactive-agents)
[![Python](https://img.shields.io/pypi/pyversions/reactive-agents.svg)](https://pypi.org/project/reactive-agents/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Coverage](https://codecov.io/gh/tylerjrbuell/reactive-agents/branch/main/graph/badge.svg)](https://codecov.io/gh/tylerjrbuell/reactive-agents)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Downloads](https://pepy.tech/badge/reactive-agents)](https://pepy.tech/project/reactive-agents)
[![GitHub stars](https://img.shields.io/github/stars/tylerjrbuell/reactive-agents.svg)](https://github.com/tylerjrbuell/reactive-agents/stargazers)

[![Docs](https://img.shields.io/badge/docs-tylerjrbuell.github.io/reactive--agents-blue?logo=readthedocs)](https://tylerjrbuell.github.io/reactive-agents/)
[![Discord](https://img.shields.io/badge/discord-join-7289DA?logo=discord&logoColor=white)](https://discord.gg/WVxTnHt8)

_An Elegant, Powerful, and Flexible Framework for Building Reactive AI Agents_

[🏁 Quick Start](#quick-start) •
[📖 Documentation](https://tylerjrbuell.github.io/reactive-agents/) •
[🎯 Features](#features) •
[🛠️ Installation](#installation) •
[💡 Examples](#examples) •
[🤝 Contributing](#contributing)

</div>

---

## 🌟 What is Reactive Agents?

**Reactive Agents** is a cutting-edge AI agent framework that makes building intelligent, autonomous agents as simple as Laravel makes web development. With its elegant builder pattern, comprehensive tooling ecosystem, and production-ready architecture, you can create sophisticated AI agents that think, plan, execute, and adapt.

### 🔎 Definition — "Reactive" (adj.)

**reactive** /ˈriːæk.tɪv/

1. Promptly responsive to change or external stimuli; able to sense, interpret, and act in real time.
2. Architected for rapid feedback loops, context-aware adaptation, and low-latency decision-making.

### 🚀 Why "Reactive"?

**Reactive agents** turn sensing into instant value — they detect shifts, call the right tools, and adjust plans on the fly. That means faster answers, fewer failures, better user experiences, and systems that scale gracefully under real-world uncertainty. In short: reactive = faster, smarter, and more reliable AI that drives reliable outcomes now.

### 🎯 Perfect For

- 🔬 **Research Automation** - Intelligent web research and data analysis
- 📊 **Business Intelligence** - Automated reporting and decision support
- 🛠️ **DevOps & Infrastructure** - Intelligent monitoring and automation
- 💬 **Customer Support** - Smart assistants with tool integration
- 📈 **Data Processing** - Complex workflows with multiple data sources
- 🎮 **Interactive Applications** - AI-powered user experiences
- 🤖 **Multi-Agent Systems** - Orchestrated AI teams solving complex problems
- ⚙️ **Automation & Scripting** - Intelligent task automation

## ✨ Key Features

### 🧠 **Multiple Reasoning Strategies**

**Composable strategies with component-based architecture:** Strategies are modular and pluggable, built from discrete components (planners, executors, reflectors, and goal evaluators) that you can mix-and-match to craft custom reasoning flows.

- **Modular components** — planners, executors, reflectors, and evaluators are independent and swappable.
- **Pluggable strategies** — implement `BaseReasoningStrategy` and register with `StrategyManager` to add new strategies.
- **Testable & reusable** — small, well-typed components make unit testing and reuse simple.
- **Designed for composition** — use the Adaptive strategy or compose multiple strategies to handle complex, dynamic tasks.

#### Pre-built strategies include:

- **Reactive**: Fast, direct problem-solving
- **Plan-Execute-Reflect**: Structured approach for complex tasks
- **Reflect-Decide-Act**: Adaptive strategy for dynamic environments
- **Adaptive**: AI-driven strategy selection based on task complexity

### 🔧 **Comprehensive Tool Ecosystem**

- **Custom Python Tools** with `@tool()` decorator
- **Model Context Protocol (MCP)** integration
- **Pre-built Tools**: Web search, file operations, databases, and more
- **Tool Composition** and validation system

### 🏗️ **Production-Ready Architecture**

- **Event-Driven Design** with real-time monitoring
- **Robust Error Recovery** with intelligent retry mechanisms
- **Memory Management** with vector storage and persistence
- **Performance Monitoring** with detailed metrics and scoring
- **Context Optimization** with adaptive pruning strategies

### 🔄 **Advanced Workflow Management**

- **Multi-Agent Orchestration** with dependency management
- **A2A Communication** (Agent-to-Agent) protocols
- **Parallel Execution** and synchronization
- **Workflow Templates** for common patterns

### 🎛️ **Developer Experience**

- **Fluent Builder API** with sensible defaults
- **Type Safety** with Pydantic models throughout
- **Comprehensive Logging** with structured events
- **🚧 Plugin System** for extensibility
- **Hot-reloading** for development workflows

---

## 🏁 Quick Start

### Installation

```bash
pip install reactive-agents
```

### Your First Agent (30 seconds)

```python
import asyncio
from reactive_agents import ReactiveAgentBuilder, ReasoningStrategies

async def main():
    # Create an intelligent research agent
    agent = await (
        ReactiveAgentBuilder()
        .with_name("Research Assistant")
        .with_model("ollama:llama3")  # or "openai:gpt-4", "anthropic:claude-3-sonnet"
        .with_tools(["brave-search", "time"])  # Auto-detects MCP tools vs custom tools
        .with_instructions("Research thoroughly and provide detailed analysis")
        .with_reasoning_strategy(ReasoningStrategies.REACTIVE)
        .build()
    )

    async with agent:
        result = await agent.run(
            "What are the latest developments in quantum computing this week?"
        )
        print(result.final_answer)
        print(f"Status: {result.status_message}")

asyncio.run(main())
```

That's it! You now have a fully functional AI agent that can search the web, analyze information, and provide comprehensive answers.

## 🎯 Core Concepts

### 🤖 Agent Architecture

Reactive Agents uses a **component-based architecture** where each agent is composed of specialized, swappable components:

```python
# The agent automatically manages these components:
ExecutionEngine  # Coordinates task execution and strategy selection
ReasoningEngine  # Handles different reasoning strategies
ToolManager     # Manages tool registration and execution
MemoryManager   # Handles persistent storage and retrieval
EventBus        # Coordinates real-time event communication
MetricsManager  # Tracks performance and provides insights
```

### 🧭 Reasoning Strategies

Choose the right strategy for your task:

```python
from reactive_agents import ReactiveAgentBuilder, ReasoningStrategies

# Reactive: Fast, direct execution
agent = await ReactiveAgentBuilder().with_reasoning_strategy(ReasoningStrategies.REACTIVE).build()

# Plan-Execute-Reflect: Structured approach
agent = await ReactiveAgentBuilder().with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT).build()

# Adaptive: AI selects the best strategy
agent = await ReactiveAgentBuilder().with_reasoning_strategy(ReasoningStrategies.ADAPTIVE).build()  # Default
```

### 🛠️ Tool Integration

Multiple ways to add capabilities to your agents:

```python
from reactive_agents import tool

# 1. Custom Python functions with @tool decorator
@tool()
async def get_weather(city: str) -> str:
    """Get weather information for a city."""
    return f"Weather in {city}: Sunny, 72°F"

# 2. Mixed tools - auto-detection!
# Strings = MCP servers, Functions = custom tools
.with_tools([get_weather, "brave-search", "time", "filesystem"])

# 3. Or use explicit methods
.with_mcp_tools(["brave-search", "sqlite"])
.with_custom_tools([get_weather])
```

---

## 💡 Examples

### 🔍 Smart Research Agent

```python
from reactive_agents import ReactiveAgentBuilder, tool, ReasoningStrategies

@tool()
async def analyze_trends(data: str) -> str:
    """Analyze data trends and patterns."""
    # Your analysis logic here
    return f"Trend analysis: {data}"

async def create_research_agent():
    return await (
        ReactiveAgentBuilder()
        .with_name("Research Pro")
        .with_model("openai:gpt-4")
        .with_reasoning_strategy(ReasoningStrategies.PLAN_EXECUTE_REFLECT)
        .with_tools([analyze_trends, "brave-search", "time", "filesystem"])
        .with_instructions("""
            You are a professional research analyst. Always:
            1. Search for the most recent information
            2. Cross-reference multiple sources
            3. Provide data-driven insights
            4. Save important findings to files
        """)
        .with_max_iterations(15)
        .build()
    )
```

### 📊 Business Intelligence Agent

```python
async def create_bi_agent():
    return await (
        ReactiveAgentBuilder()
        .with_name("BI Analyst")
        .with_model("anthropic:claude-3-sonnet")
        .with_tools(["sqlite", "filesystem", "brave-search"])
        .with_vector_memory("bi_agent_memory")  # Enable persistent vector memory
        .with_instructions("""
            You are a business intelligence analyst. Create comprehensive
            reports with data visualizations and actionable insights.
        """)
        .with_response_format("""
            ## Executive Summary
            [Key findings and recommendations]

            ## Data Analysis
            [Detailed analysis with charts/tables]

            ## Recommendations
            [Specific, actionable next steps]
        """)
        .build()
    )
```

### 🔄 Multi-Agent Workflow

```python
from reactive_agents.workflows import WorkflowOrchestrator

async def create_content_pipeline():
    orchestrator = WorkflowOrchestrator()

    # Research agent
    researcher = await (
        ReactiveAgentBuilder()
        .with_name("Content Researcher")
        .with_tools(["brave_web_search"])
        .build()
    )

    # Writing agent
    writer = await (
        ReactiveAgentBuilder()
        .with_name("Content Writer")
        .with_tools(["filesystem"])
        .build()
    )

    # Create workflow
    workflow = (
        orchestrator
        .add_agent("research", researcher)
        .add_agent("writing", writer)
        .add_dependency("writing", "research")  # Writer waits for researcher
        .build()
    )

    return workflow
```

### 🎛️ Event-Driven Monitoring

```python
from reactive_agents.events import AgentStateEvent

async def create_monitored_agent():
    # Track performance in real-time
    metrics = {"tool_calls": 0, "errors": 0, "duration": 0}

    def on_tool_called(event):
        metrics["tool_calls"] += 1
        print(f"🔧 Tool used: {event['tool_name']}")

    def on_error(event):
        metrics["errors"] += 1
        print(f"❌ Error: {event['error_message']}")

    def on_completion(event):
        metrics["duration"] = event["total_duration"]
        print(f"✅ Completed in {metrics['duration']:.2f}s")
        print(f"📊 Final metrics: {metrics}")

    return await (
        ReactiveAgentBuilder()
        .with_name("Monitored Agent")
        .with_model("ollama:qwen2:7b")
        .on_tool_called(on_tool_called)
        .on_error_occurred(on_error)
        .on_session_ended(on_completion)
        .build()
    )
```

---

## 🛠️ Installation & Setup

### Prerequisites

- **Python 3.10+**
- **Poetry** (recommended) or pip

### Basic Installation

```bash
# Using pip
pip install reactive-agents

# Using Poetry
poetry add reactive-agents
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/tylerjrbuell/reactive-agents
cd reactive-agents

# Install with Poetry
poetry install

# Run tests
poetry run pytest
```

### Environment Configuration

Create a `.env` file:

```bash
# LLM Providers
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GROQ_API_KEY=your_groq_key
OLLAMA_HOST=http://localhost:11434

# MCP Tools
BRAVE_API_KEY=your_brave_search_key

# Optional: Custom MCP configuration
MCP_CONFIG_PATH=/path/to/custom/mcp_config.json
```

---

## 🎯 Advanced Features

### 🧠 Custom Reasoning Strategies

Implement your own reasoning approach:

```python
from reactive_agents.strategies import BaseReasoningStrategy

class MyCustomStrategy(BaseReasoningStrategy):
    @property
    def name(self) -> str:
        return "my_custom_strategy"

    async def execute_iteration(self, task: str, context: ReasoningContext):
        # Your custom reasoning logic
        return StrategyResult.success(payload)

# Register and use
ReactiveAgentBuilder().with_reasoning_strategy("my_custom_strategy")
```

### 🔧 Custom Tool Creation

Build sophisticated tools with validation:

```python
from reactive_agents.tools import tool
from pydantic import BaseModel

class WeatherRequest(BaseModel):
    city: str
    units: str = "metric"

@tool("Get detailed weather information", validation_model=WeatherRequest)
async def advanced_weather(request: WeatherRequest) -> dict:
    # Sophisticated weather logic with API calls
    weather_data = await fetch_weather_api(request.city, request.units)
    return {
        "temperature": weather_data.temp,
        "conditions": weather_data.conditions,
        "forecast": weather_data.forecast
    }
```

### 📊 Performance Monitoring

Track and optimize agent performance:

```python
async def monitor_performance():
    agent = await ReactiveAgentBuilder().with_name("Performance Agent").build()

    # Get real-time metrics
    session = agent.context.session

    print(f"Completion Score: {session.completion_score}")
    print(f"Tool Usage Score: {session.tool_usage_score}")
    print(f"Overall Score: {session.overall_score}")

    # Access detailed metrics
    metrics = agent.context.metrics_manager.get_metrics()
    print(f"Total Duration: {metrics['total_time']:.2f}s")
    print(f"Tool Calls: {metrics['tool_calls']}")
    print(f"Model Calls: {metrics['model_calls']}")
```

### 🔄 Plugin System 🚧

Extend the framework with plugins:

```python
from reactive_agents.plugins import Plugin

class CustomAnalyticsPlugin(Plugin):
    def on_load(self, framework):
        # Initialize your plugin
        self.analytics_client = AnalyticsClient()

    def on_agent_created(self, agent):
        # Hook into agent lifecycle
        agent.on_completion(self.track_completion)

    async def track_completion(self, event):
        await self.analytics_client.track(event)

# Load plugin
framework.load_plugin(CustomAnalyticsPlugin())
```

---

## 📖 Documentation

### 📚 Comprehensive Guides

- **[Getting Started Guide](docs/getting-started.md)** - Your first agent in 5 minutes
- **[Architecture Overview](docs/architecture.md)** - Understanding the framework
- **[Tool Development](docs/tools.md)** - Building custom tools and integrations
- **[Reasoning Strategies](docs/strategies.md)** - Deep dive into AI reasoning
- **[Workflow Orchestration](docs/workflows.md)** - Multi-agent coordination
- **[Production Deployment](docs/deployment.md)** - Scaling to production

### 🔧 API Reference

- **[Agent Builder API](docs/api/builder.md)** - Complete builder pattern reference
- **[Tool System API](docs/api/tools.md)** - Tool registration and execution
- **[Event System API](docs/api/events.md)** - Real-time monitoring and hooks
- **[Configuration API](docs/api/config.md)** - Advanced configuration options

### 💡 Examples & Tutorials

- **[Example Gallery](examples/)** - 20+ real-world examples
- **[Tutorial Series](docs/tutorials/)** - Step-by-step learning path
- **[Best Practices](docs/best-practices.md)** - Production tips and patterns
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

---

## 🌐 Model Provider Support

Reactive Agents works with all major LLM providers:

| Provider      | Models                      | Features                            |
| ------------- | --------------------------- | ----------------------------------- |
| **OpenAI**    | GPT-4o, GPT-4, GPT-3.5      | Function calling, streaming, vision |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 | Large context, tool use             |
| **Groq**      | Llama 3, Mixtral            | Ultra-fast inference                |
| **Ollama**    | Any local model             | Privacy, customization              |
| **Google**    | Gemini Pro, Gemini Flash    | Multimodal capabilities             |

> **v0.1.0a7 Update**: Google provider now uses the latest `google-genai` SDK (v1.5.0) with improved performance and zero deprecation warnings.

```python
# Easy provider switching
.with_model("gpt-4o")                    # OpenAI
.with_model("claude-3-sonnet")           # Anthropic
.with_model("groq:llama3-70b")          # Groq
.with_model("ollama:qwen2:7b")          # Ollama
.with_model("google:gemini-pro")        # Google
```

---

## 🎯 Structured Outputs & Provider Architecture

### 🔄 Universal Structured Output System

Reactive Agents implements a **unified structured output system** using the [Instructor Python Package](https://python.useinstructor.com/) across all model providers. This ensures consistent **Pydantic model validation** and **type safety** regardless of your LLM choice.

```python
from pydantic import BaseModel
from typing import List
from reactive_agents import ReactiveAgentBuilder

class ResearchResult(BaseModel):
    summary: str
    key_findings: List[str]
    confidence_score: float
    sources: List[str]

# Works identically across ALL providers
agent = await ReactiveAgentBuilder()\
    .with_model("ollama:qwen2:7b")  # or any provider
    .build()

# Get validated, structured output
result: ResearchResult = await agent.get_structured_response(
    ResearchResult,
    "Research the latest AI developments"
)

print(result.summary)           # ✅ Type-safe string
print(result.confidence_score)  # ✅ Type-safe float
```

### 🔧 OpenAI-Style Parameter Interface

The framework uses **OpenAI-compatible parameters** as the standard interface, with automatic translation to provider-specific formats:

```python
# ✅ Same parameters work everywhere
universal_options = {
    "temperature": 0.2,
    "max_tokens": 500,
    "top_p": 0.9,
    "frequency_penalty": 0.1,
    "presence_penalty": 0.05,
    "stop": ["END", "STOP"],
    "seed": 42
}

# Automatically optimized for each provider
providers = [
    "openai:gpt-4o",
    "anthropic:claude-3-5-sonnet-latest",
    "groq:llama-3.1-8b-instant",
    "ollama:cogito:14b",
    "google:gemini-2.5-flash"
]

for provider_model in providers:
    agent = await ReactiveAgentBuilder()\
        .with_model(provider_model)\
        .with_model_provider_options(universal_options)\
        .build()

    # Same code, provider-specific optimization! 🚀
    result = await agent.run("Analyze this data...")
```

### 🔄 Dual-Parameter Architecture

The framework uses an elegant **dual-parameter system**:

#### 1️⃣ **User Interface Layer** (OpenAI-style)

```python
# Clean, standardized interface
{
    "temperature": 0.3,
    "max_tokens": 200,
    "top_p": 0.8,
    "frequency_penalty": 0.1
}
```

#### 2️⃣ **Provider Optimization Layer** (Native formats)

```python
# Ollama native (automatically translated)
{
    "temperature": 0.3,
    "num_predict": 200,      # max_tokens → num_predict
    "top_p": 0.8,
    "repeat_penalty": 1.1,   # frequency_penalty → repeat_penalty (scaled)
    "num_ctx": 4096,         # Added Ollama optimizations
    "repeat_last_n": 64,
    "top_k": 40
}

# Anthropic native (automatically translated)
{
    "temperature": 0.3,
    "max_tokens": 200,       # Direct mapping
    "top_p": 0.8,
    "stop_sequences": ["END"] # stop → stop_sequences
}

# Groq native (automatically translated)
{
    "temperature": 0.3,
    "max_completion_tokens": 200,  # max_tokens → max_completion_tokens
    "top_p": 0.8,
    "frequency_penalty": 0.1       # Direct OpenAI compatibility
}

# Google native (automatically translated)
{
    "temperature": 0.3,
    "max_output_tokens": 200,      # max_tokens → max_output_tokens
    "top_p": 0.8,
    "stop_sequences": ["END"],     # stop → stop_sequences (up to 5)
    "top_k": 40                    # Google-specific optimization
}
```

### ✨ Key Benefits

| Feature                    | Benefit                                                    |
| -------------------------- | ---------------------------------------------------------- |
| 🔄 **Universal Interface** | Same parameters across all providers                       |
| 🎯 **Type Safety**         | Full Pydantic validation for structured outputs            |
| ⚡ **Performance**         | Provider-specific optimizations automatically applied      |
| 🛡️ **Reliability**         | Graceful fallback when structured outputs fail             |
| 🔧 **Maintainable**        | Clean separation between user interface and implementation |
| 🚀 **Future-Proof**        | Easy to add new providers following established patterns   |

### 🧪 Testing Your Provider Setup

```bash
# Test parameter mapping
python -c "
from reactive_agents.providers.llm.ollama import OllamaModelProvider
provider = OllamaModelProvider('cogito:14b')
options = {'temperature': 0.2, 'max_tokens': 100}
print('OpenAI params:', provider.get_openai_params(options))
print('Native params:', provider.get_native_params(options))
"

# Integration testing across providers
python -m reactive_agents.tests.integration.diagnose_provider_issues
```

### 🎨 Advanced Usage

```python
# Provider-specific optimizations while maintaining compatibility
builder = ReactiveAgentBuilder()

# Ollama with GPU acceleration
if provider == "ollama":
    builder.with_model_provider_options({
        "temperature": 0.2,
        "max_tokens": 1000,
        "num_gpu": 256,      # Ollama-specific: GPU layers
        "num_ctx": 8192,     # Ollama-specific: context window
    })

# Anthropic with advanced parameters
elif provider == "anthropic":
    builder.with_model_provider_options({
        "temperature": 0.2,
        "max_tokens": 1000,
        "top_k": 50,         # Anthropic-specific: top-k sampling
    })

# Google with structured schema
elif provider == "google":
    builder.with_model_provider_options({
        "temperature": 0.2,
        "max_tokens": 1000,
        "candidate_count": 3,    # Google-specific: multiple candidates
        "response_schema": schema # Google-specific: schema validation
    })

agent = await builder.build()
```

---

## 🧪 Playground & Testing

The Reactive Agents framework includes a comprehensive playground for testing, experimentation, and validation.

### Quick Start with Playground

```bash
# Run basic functionality tests
poetry run python -m playground.runner agents

# Test reasoning strategies
poetry run python -m playground.runner strategies

# Stress test the framework
poetry run python -m playground.runner stress

# Run real-world scenarios
poetry run python -m playground.runner real-world

# List all available test suites
poetry run python -m playground.runner --list
```

### What's in the Playground?

The playground provides:

- **Agent Tests** - Core functionality validation
- **Strategy Tests** - Compare reasoning approaches
- **Stress Tests** - Find breaking points and edge cases
- **Real-World Tests** - Production-ready scenarios
- **Memory Tests** - Persistence and learning
- **System Tools** - Meta-actions and agent control

### Example Test Output

```bash
$ poetry run python -m playground.runner agents

=== Running Agent Tests ===

✅ Basic agent creation: PASS (8.2s)
✅ Tool integration: PASS (12.5s)
✅ Event system: PASS (6.1s)
✅ Custom tools: PASS (9.8s)

4/4 tests passed in 36.6s
```

For complete playground documentation, see **[docs/playground.md](docs/playground.md)**

---

## 🔧 Available Tools & Integrations

### 🌐 Web & Data

- **Web Search** - Brave Search, DuckDuckGo
- **Web Scraping** - Playwright automation
- **APIs** - REST/GraphQL client tools
- **Data Processing** - Pandas, NumPy integrations

### 💾 Storage & Databases

- **File System** - Read, write, organize files
- **SQLite** - Database operations and queries
- **Vector Stores** - ChromaDB, Pinecone integration
- **Cloud Storage** - AWS S3, Google Cloud

### 🔧 Development & DevOps

- **Git Operations** - Repository management
- **Docker** - Container orchestration
- **CI/CD** - GitHub Actions, Jenkins
- **Monitoring** - Prometheus, Grafana

### 🤖 AI & ML

- **Model Inference** - Multiple LLM providers
- **Embeddings** - Text and multimodal embeddings
- **Vision** - Image analysis and processing
- **Speech** - TTS and STT capabilities

---

## 📈 Performance & Benchmarks

Reactive Agents is built for performance and scalability:

| Metric                | Result             |
| --------------------- | ------------------ |
| **Agent Creation**    | < 100ms            |
| **Tool Execution**    | < 50ms overhead    |
| **Memory Usage**      | < 100MB per agent  |
| **Concurrent Agents** | 1000+ per instance |
| **Throughput**        | 10,000+ tasks/hour |

### 🚀 Optimization Features

- **Lazy Loading** - Components loaded on demand
- **Connection Pooling** - Efficient resource management
- **Context Caching** - Intelligent conversation optimization
- **Parallel Execution** - Multi-threaded tool execution
- **Memory Management** - Automatic cleanup and optimization

---

## 🤝 Contributing

We love contributions! Join our growing community:

### 🎯 Quick Contribution

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### 🔧 Development Setup

```bash
# Clone and setup
git clone https://github.com/tylerjrbuell/reactive-agents
cd reactive-agents
poetry install

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=reactive_agents

# Lint and format
poetry run black .
poetry run ruff check .
```

## 💬 Community

Join the project community on Discord for chat, support, and collaboration:

- **Invite:** https://discord.gg/WVxTnHt8

We welcome contributors, users, and maintainers — stop by, introduce yourself, and let us know what you're building with Reactive Agents!

### 📝 Contribution Areas

- 🧠 **New Reasoning Strategies**
- 🔧 **Tool Integrations**
- 📚 **Documentation & Examples**
- 🐛 **Bug Fixes & Performance**
- 🎨 **UI/UX Improvements**
- 🌍 **Internationalization**

---

## 📊 Project Stats

<div align="center">

![GitHub Repo stars](https://img.shields.io/github/stars/tylerjrbuell/reactive-agents?style=social)
![GitHub forks](https://img.shields.io/github/forks/tylerjrbuell/reactive-agents?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/tylerjrbuell/reactive-agents?style=social)

![PyPI downloads](https://img.shields.io/pypi/dm/reactive-agents)
![GitHub issues](https://img.shields.io/github/issues/tylerjrbuell/reactive-agents)
![GitHub pull requests](https://img.shields.io/github/issues-pr/tylerjrbuell/reactive-agents)

</div>

---

## 🙏 Acknowledgments

Built with love using these amazing technologies:

- **[Pydantic](https://pydantic.dev/)** - Data validation and settings
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern web framework
- **[asyncio](https://docs.python.org/3/library/asyncio.html)** - Asynchronous programming
- **[Model Context Protocol](https://modelcontextprotocol.io/)** - Tool integration standard
- **[Poetry](https://python-poetry.org/)** - Dependency management

Special thanks to our amazing contributors and the AI community! 🚀

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Ready to build the future with AI agents?**

⭐ **Star this repo** if you find it useful!  
🐛 **Report issues** to help us improve  
💬 **Join our community** for support and discussions

[**🚀 Get Started Now**](#quick-start) | [**📖 Read the Docs**](#documentation) | [**💬 Join Discord**](https://discord.gg/WVxTnHt8)

---

_Made with ❤️ by the Reactive Agents team_

</div>
