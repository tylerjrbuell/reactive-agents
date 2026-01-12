"""
Streaming Tests - Test streaming responses from all providers.

Tests the StreamChunk model and streaming capabilities across providers.
"""

import asyncio
from typing import Optional


async def test_ollama_streaming(model: str = "cogito:14b") -> bool:
    """Test streaming with Ollama provider."""
    print("\n--- Ollama Streaming ---")

    from reactive_agents.providers.llm import OllamaModelProvider

    try:
        provider = OllamaModelProvider(model=model)
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Count from 1 to 5."},
        ]

        print("Response: ", end="", flush=True)
        chunk_count = 0
        async for chunk in provider.stream_chat_completion(messages):
            print(chunk.content, end="", flush=True)
            chunk_count += 1
            if chunk.is_final:
                print(f"\n[{chunk_count} chunks, {chunk.total_tokens} tokens]")

        return chunk_count > 0
    except Exception as e:
        print(f"\nError: {e}")
        return False


async def test_openai_streaming(model: str = "gpt-4o-mini") -> bool:
    """Test streaming with OpenAI provider."""
    print("\n--- OpenAI Streaming ---")

    from reactive_agents.providers.llm import OpenAIModelProvider

    try:
        provider = OpenAIModelProvider(model=model)
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Count from 1 to 5."},
        ]

        print("Response: ", end="", flush=True)
        chunk_count = 0
        async for chunk in provider.stream_chat_completion(messages):
            print(chunk.content, end="", flush=True)
            chunk_count += 1
            if chunk.is_final:
                print(f"\n[{chunk_count} chunks, {chunk.total_tokens} tokens]")

        return chunk_count > 0
    except Exception as e:
        print(f"\nError: {e}")
        return False


async def test_anthropic_streaming(model: str = "claude-3-5-haiku-20241022") -> bool:
    """Test streaming with Anthropic provider."""
    print("\n--- Anthropic Streaming ---")

    from reactive_agents.providers.llm import AnthropicModelProvider

    try:
        provider = AnthropicModelProvider(model=model)
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Count from 1 to 5."},
        ]

        print("Response: ", end="", flush=True)
        chunk_count = 0
        async for chunk in provider.stream_chat_completion(messages):
            print(chunk.content, end="", flush=True)
            chunk_count += 1
            if chunk.is_final:
                print(f"\n[{chunk_count} chunks, {chunk.total_tokens} tokens]")

        return chunk_count > 0
    except Exception as e:
        print(f"\nError: {e}")
        return False


async def test_groq_streaming(model: str = "llama-3.1-8b-instant") -> bool:
    """Test streaming with Groq provider."""
    print("\n--- Groq Streaming ---")

    from reactive_agents.providers.llm import GroqModelProvider

    try:
        provider = GroqModelProvider(model=model)
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Count from 1 to 5."},
        ]

        print("Response: ", end="", flush=True)
        chunk_count = 0
        async for chunk in provider.stream_chat_completion(messages):
            print(chunk.content, end="", flush=True)
            chunk_count += 1
            if chunk.is_final:
                print(f"\n[{chunk_count} chunks, {chunk.total_tokens} tokens]")

        return chunk_count > 0
    except Exception as e:
        print(f"\nError: {e}")
        return False


async def run(provider: Optional[str] = None) -> dict:
    """
    Run streaming tests.

    Args:
        provider: Specific provider to test (ollama, openai, anthropic, groq)
                  or None to test all available.

    Returns:
        Dict with test results.
    """
    print("=" * 60)
    print("STREAMING TESTS")
    print("=" * 60)

    results = {}

    if provider is None or provider == "ollama":
        results["ollama"] = await test_ollama_streaming()

    if provider is None or provider == "openai":
        results["openai"] = await test_openai_streaming()

    if provider is None or provider == "anthropic":
        results["anthropic"] = await test_anthropic_streaming()

    if provider is None or provider == "groq":
        results["groq"] = await test_groq_streaming()

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    return results


if __name__ == "__main__":
    asyncio.run(run())
