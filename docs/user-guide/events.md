# Event System

Monitor and react to agent execution with the event system.

## Overview

Reactive Agents emits events throughout the execution lifecycle, allowing you to:

- Monitor progress in real-time
- Log execution details
- Build custom UIs
- Integrate with external systems

## Subscribing to Events

```python
agent = await builder.build()

# Lambda syntax
agent.on_session_started(lambda e: print(f"Started: {e['agent_name']}"))

# Function syntax
def on_tool(event):
    print(f"Tool called: {event['tool_name']}")
    print(f"Arguments: {event['arguments']}")

agent.on_tool_called(on_tool)
```

## Available Events

### Session Events

```python
# Session started
agent.on_session_started(lambda e: ...)
# Event data: agent_name, session_id, initial_task

# Session ended
agent.on_session_ended(lambda e: ...)
# Event data: final_result, session_id
```

### Iteration Events

```python
# Iteration started
agent.on_iteration_started(lambda e: ...)
# Event data: iteration, max_iterations, strategy, state

# Iteration completed
agent.on_iteration_completed(lambda e: ...)
# Event data: iteration, result, state
```

### Tool Events

```python
# Tool called
agent.on_tool_called(lambda e: ...)
# Event data: tool_name, arguments

# Tool result
agent.on_tool_result(lambda e: ...)
# Event data: tool_name, result
```

### Control Events

```python
# Pause/Resume
agent.on_pause_requested(lambda e: ...)
agent.on_paused(lambda e: ...)
agent.on_resume_requested(lambda e: ...)
agent.on_resumed(lambda e: ...)

# Stop/Terminate
agent.on_stop_requested(lambda e: ...)
agent.on_stopped(lambda e: ...)
agent.on_terminate_requested(lambda e: ...)
agent.on_terminated(lambda e: ...)
```

## Event Data Structure

All events provide a dictionary with:

```python
{
    "session_id": "...",     # Current session ID
    "agent_name": "...",     # Agent name
    "task": "...",           # Current task
    "task_status": "...",    # Status enum value
    "iterations": 0,         # Current iteration count
    # ... event-specific data
}
```

## Example: Progress Monitor

```python
class ProgressMonitor:
    def __init__(self, agent):
        self.agent = agent
        self.events = []

        agent.on_session_started(self.on_start)
        agent.on_iteration_started(self.on_iteration)
        agent.on_tool_called(self.on_tool)
        agent.on_session_ended(self.on_end)

    def on_start(self, e):
        print(f"Starting task: {e.get('initial_task', '')}")

    def on_iteration(self, e):
        print(f"Iteration {e['iteration']}/{e['max_iterations']} - {e['strategy']}")

    def on_tool(self, e):
        print(f"  Tool: {e['tool_name']}")

    def on_end(self, e):
        print("Task completed")

# Usage
agent = await builder.build()
monitor = ProgressMonitor(agent)
result = await agent.run("Do something")
```

## Example: Event Logger

```python
import json
from datetime import datetime

class EventLogger:
    def __init__(self, agent, log_file="events.jsonl"):
        self.log_file = log_file
        self.subscribe_all(agent)

    def subscribe_all(self, agent):
        events = [
            "session_started", "session_ended",
            "iteration_started", "iteration_completed",
            "tool_called", "tool_result"
        ]
        for event in events:
            handler_name = f"on_{event}"
            if hasattr(agent, handler_name):
                getattr(agent, handler_name)(
                    lambda e, ev=event: self.log(ev, e)
                )

    def log(self, event_type, data):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

## Example: Real-time UI

```python
from rich.live import Live
from rich.table import Table

class LiveUI:
    def __init__(self, agent):
        self.current_iteration = 0
        self.max_iterations = 0
        self.current_tool = None
        self.status = "Starting"

        agent.on_iteration_started(self.on_iteration)
        agent.on_tool_called(self.on_tool)
        agent.on_session_ended(self.on_end)

    def on_iteration(self, e):
        self.current_iteration = e["iteration"]
        self.max_iterations = e["max_iterations"]
        self.status = e["strategy"]

    def on_tool(self, e):
        self.current_tool = e["tool_name"]

    def on_end(self, e):
        self.status = "Complete"

    def render(self):
        table = Table()
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Progress", f"{self.current_iteration}/{self.max_iterations}")
        table.add_row("Strategy", self.status)
        table.add_row("Current Tool", self.current_tool or "-")
        return table
```

## Async Event Handlers

Event handlers can be async:

```python
async def async_handler(event):
    await some_async_operation(event)
    print(f"Processed: {event}")

agent.on_tool_called(async_handler)
```

## Unsubscribing

Events are tied to the agent lifecycle. When the agent is closed, all subscriptions are cleaned up.

For manual unsubscription, keep a reference to the handler:

```python
def my_handler(e):
    print(e)

# Subscribe
agent.on_tool_called(my_handler)

# The handler will be called until agent.close()
```

## Best Practices

1. **Keep handlers fast** - Don't block execution with slow handlers
2. **Use async for I/O** - For network or file operations
3. **Handle errors** - Wrap handlers in try/except to avoid breaking execution
4. **Clean up** - Always close agents to release resources
