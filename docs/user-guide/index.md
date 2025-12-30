# User Guide

This guide covers the core concepts and features of Reactive Agents.

## Core Concepts

- [Building Agents](building-agents.md) - The builder pattern and agent lifecycle
- [Custom Tools](custom-tools.md) - Creating tools for your agents
- [Reasoning Strategies](reasoning-strategies.md) - How agents think and decide
- [Event System](events.md) - Monitor and react to agent execution
- [MCP Integration](mcp-integration.md) - Using Model Context Protocol tools

## Architecture Overview

```
ReactiveAgentBuilder
        │
        ▼
    ReactiveAgent
        │
        ├── AgentContext (state & configuration)
        │
        ├── ReasoningEngine (LLM interaction)
        │
        ├── ExecutionEngine (task execution)
        │
        ├── ToolManager (tool orchestration)
        │
        └── EventBus (event dispatching)
```

## Key Components

### ReactiveAgentBuilder

The entry point for creating agents. Uses a fluent builder pattern for configuration.

### ReactiveAgent

The main agent class that orchestrates execution. Manages the reasoning loop and tool execution.

### ExecutionEngine

Handles the execution loop, strategy selection, and state management.

### ToolManager

Manages tool registration, execution, and result handling.

### AgentContext

Holds agent state, configuration, and shared resources.
