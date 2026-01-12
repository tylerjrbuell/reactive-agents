# Streaming Examples

Stream responses token-by-token from any LLM provider.

## Basic Provider Streaming

Stream directly from a provider for real-time output:

```python
import asyncio
from reactive_agents.providers.llm import OpenAIModelProvider

async def main():
    # Initialize provider
    provider = OpenAIModelProvider(model="gpt-4o-mini")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short poem about coding."}
    ]

    # Stream the response
    print("Streaming response: ", end="", flush=True)
    async for chunk in provider.stream_chat_completion(messages):
        print(chunk.content, end="", flush=True)

        # Check if this is the final chunk
        if chunk.is_final:
            print(f"\n\nTokens used: {chunk.total_tokens}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Multi-Provider Streaming

The streaming API is consistent across all providers:

=== "OpenAI"

    ```python
    from reactive_agents.providers.llm import OpenAIModelProvider

    provider = OpenAIModelProvider(model="gpt-4o")

    async for chunk in provider.stream_chat_completion(messages):
        print(chunk.content, end="", flush=True)
    ```

=== "Anthropic"

    ```python
    from reactive_agents.providers.llm import AnthropicModelProvider

    provider = AnthropicModelProvider(model="claude-3-5-sonnet-20241022")

    async for chunk in provider.stream_chat_completion(messages):
        print(chunk.content, end="", flush=True)
    ```

=== "Ollama"

    ```python
    from reactive_agents.providers.llm import OllamaModelProvider

    provider = OllamaModelProvider(model="llama3")

    async for chunk in provider.stream_chat_completion(messages):
        print(chunk.content, end="", flush=True)
    ```

=== "Groq"

    ```python
    from reactive_agents.providers.llm import GroqModelProvider

    provider = GroqModelProvider(model="llama-3.1-70b-versatile")

    async for chunk in provider.stream_chat_completion(messages):
        print(chunk.content, end="", flush=True)
    ```

=== "Google"

    ```python
    from reactive_agents.providers.llm import GoogleModelProvider

    provider = GoogleModelProvider(model="gemini-1.5-pro")

    async for chunk in provider.stream_chat_completion(messages):
        print(chunk.content, end="", flush=True)
    ```

## StreamChunk Properties

Each chunk contains useful metadata:

```python
async for chunk in provider.stream_chat_completion(messages):
    # Content for this chunk
    print(f"Content: {chunk.content}")

    # Role (usually "assistant")
    print(f"Role: {chunk.role}")

    # Chunk position in stream
    print(f"Index: {chunk.chunk_index}")

    # Model that generated this
    print(f"Model: {chunk.model}")

    # Is this the last chunk?
    if chunk.is_final:
        print(f"Finish reason: {chunk.finish_reason}")
        print(f"Prompt tokens: {chunk.prompt_tokens}")
        print(f"Completion tokens: {chunk.completion_tokens}")
        print(f"Total tokens: {chunk.total_tokens}")

        # Tool calls (if any)
        if chunk.tool_calls:
            for tool_call in chunk.tool_calls:
                print(f"Tool: {tool_call['function']['name']}")
```

## Streaming with Tools

Stream responses that may include tool calls:

```python
import asyncio
from reactive_agents.providers.llm import OpenAIModelProvider

async def main():
    provider = OpenAIModelProvider(model="gpt-4o-mini")

    messages = [
        {"role": "user", "content": "What's the weather in Paris?"}
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]

    async for chunk in provider.stream_chat_completion(messages, tools=tools):
        if chunk.content:
            print(chunk.content, end="", flush=True)

        if chunk.is_final and chunk.tool_calls:
            print("\n\nTool calls:")
            for tc in chunk.tool_calls:
                print(f"  - {tc['function']['name']}({tc['function']['arguments']})")

if __name__ == "__main__":
    asyncio.run(main())
```

## Collecting Full Response

Accumulate chunks into a complete response:

```python
async def get_full_response(provider, messages):
    """Collect streaming chunks into full response."""
    full_content = ""
    total_tokens = 0

    async for chunk in provider.stream_chat_completion(messages):
        full_content += chunk.content

        if chunk.is_final:
            total_tokens = chunk.total_tokens

    return full_content, total_tokens

# Usage
content, tokens = await get_full_response(provider, messages)
print(f"Response ({tokens} tokens): {content}")
```

## Progress Indicator

Show a progress indicator while streaming:

```python
import sys

async def stream_with_progress(provider, messages):
    """Stream with a simple progress indicator."""
    chars_received = 0

    async for chunk in provider.stream_chat_completion(messages):
        chars_received += len(chunk.content)

        # Print content
        print(chunk.content, end="", flush=True)

        # Update progress in terminal title (optional)
        if chunk.is_final:
            print(f"\n[{chunk.completion_tokens} tokens generated]")

await stream_with_progress(provider, messages)
```

## Error Handling

Handle streaming errors gracefully:

```python
async def safe_stream(provider, messages):
    """Stream with error handling."""
    try:
        async for chunk in provider.stream_chat_completion(messages):
            print(chunk.content, end="", flush=True)

            if chunk.is_final:
                return True

    except Exception as e:
        print(f"\nStreaming error: {e}")
        return False

success = await safe_stream(provider, messages)
```

## Streaming with Options

Pass provider-specific options:

```python
async for chunk in provider.stream_chat_completion(
    messages,
    options={
        "temperature": 0.7,
        "max_tokens": 500,
        "top_p": 0.9
    }
):
    print(chunk.content, end="", flush=True)
```

## Real-Time Chat Interface

Build a simple streaming chat:

```python
import asyncio
from reactive_agents.providers.llm import OllamaModelProvider

async def chat():
    provider = OllamaModelProvider(model="llama3")
    messages = []

    print("Chat with AI (type 'quit' to exit)")
    print("-" * 40)

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            break

        messages.append({"role": "user", "content": user_input})

        print("\nAI: ", end="", flush=True)
        assistant_message = ""

        async for chunk in provider.stream_chat_completion(messages):
            print(chunk.content, end="", flush=True)
            assistant_message += chunk.content

        messages.append({"role": "assistant", "content": assistant_message})
        print()

if __name__ == "__main__":
    asyncio.run(chat())
```

## Expected Output

```
Chat with AI (type 'quit' to exit)
----------------------------------------

You: Hello! What can you help me with?

AI: Hello! I can help you with a wide variety of tasks, including:

- Answering questions on many topics
- Writing and editing text
- Explaining concepts
- Coding assistance
- Creative writing
- And much more!

What would you like to explore today?

You: quit
```

## Next Steps

- Learn about [Custom Tools](tool-usage.md) for function calling
- Explore [Multi-Strategy](multi-strategy.md) reasoning patterns
- See the [API Reference](/reference/) for full details
