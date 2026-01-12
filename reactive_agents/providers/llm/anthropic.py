import json
import os
import time
import asyncio
import random
from typing import List, Dict, Any, Optional, Type, Union, AsyncIterator
from openai import BaseModel
import requests
from anthropic import Anthropic
from anthropic.types import Message, MessageParam, TextBlock, ToolUseBlock
from anthropic import APIError, RateLimitError, APITimeoutError
import instructor

from .base import BaseModelProvider, CompletionMessage, CompletionResponse, StreamChunk


class AnthropicModelProvider(BaseModelProvider):
    """Anthropic model provider using the official Anthropic Python SDK."""

    id = "anthropic"

    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
        options: Optional[Dict[str, Any]] = None,
        context=None,
    ):
        """
        Initialize the Anthropic model provider.

        Args:
            model: The model to use (e.g., "claude-3-sonnet-20240229", "claude-3-opus-20240229")
            options: Optional configuration options
            context: The agent context for error tracking and logging
        """
        super().__init__(model=model, options=options, context=context)

        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        # Initialize Anthropic client with supported parameters
        client_params = {"api_key": api_key}

        # Add supported client parameters from options if they exist
        if options:
            supported_client_params = {
                "base_url",
                "timeout",
                "max_retries",
                "default_headers",
                "default_query",
            }
            for param in supported_client_params:
                if param in options:
                    client_params[param] = options[param]

        self.client = Anthropic(**client_params)  # type: ignore

        # Initialize instructor client for structured outputs
        try:
            self.instructor_client = instructor.from_anthropic(
                self.client, mode=instructor.Mode.ANTHROPIC_TOOLS
            )
            self._supports_structured = True
        except Exception as e:
            if context and hasattr(context, "agent_logger") and context.agent_logger:
                context.agent_logger.warning(
                    f"Failed to initialize Instructor client for Anthropic: {e}"
                )
            self.instructor_client = None
            self._supports_structured = False

        # Default options
        self.default_options = {
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        # Rate limiting configuration
        self.rate_limit_config = {
            "max_retries": options.get("max_retries", 3) if options else 3,
            "base_delay": options.get("base_delay", 1.0) if options else 1.0,
            "max_delay": (
                options.get("max_delay", 120.0) if options else 120.0
            ),  # 2 minutes max
            "jitter_factor": options.get("jitter_factor", 0.1) if options else 0.1,
            "rate_limit_retry_delay": (
                options.get("rate_limit_retry_delay", 30) if options else 30
            ),  # Default 30 seconds for rate limits
        }

        # Check if model is Claude 3 (supported by SDK) or legacy (requires manual HTTP)
        self.is_claude_3 = self._is_claude_3_model(self.model)

        # Validate model on initialization
        self.validate_model()

    async def _retry_with_backoff(
        self, func, *args, max_retries: Optional[int] = None, **kwargs
    ) -> Any:
        """
        Retry a function with exponential backoff and intelligent rate limit handling.

        Args:
            func: The function to retry
            *args: Positional arguments for the function
            max_retries: Maximum retry attempts (defaults to self.rate_limit_config["max_retries"])
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            Exception: If all retries are exhausted
        """
        max_retries = max_retries or self.rate_limit_config["max_retries"]

        for attempt in range(
            max_retries + 1
        ):  # +1 because first attempt is not a retry
            try:
                result = func(*args, **kwargs)
                # Handle both sync and async functions
                if asyncio.iscoroutine(result):
                    return await result
                else:
                    return result

            except RateLimitError as e:
                if attempt == max_retries:
                    # Log final failure
                    if (
                        self.context
                        and hasattr(self.context, "agent_logger")
                        and self.context.agent_logger
                    ):
                        self.context.agent_logger.error(
                            f"Anthropic rate limit exceeded after {max_retries} retries: {e}"
                        )
                    raise e

                # Parse rate limit information from error
                retry_delay = self._parse_rate_limit_delay(e)

                # Calculate backoff delay with exponential increase and jitter
                backoff_delay = self._calculate_backoff_delay(attempt, retry_delay)

                # Log retry attempt
                if (
                    self.context
                    and hasattr(self.context, "agent_logger")
                    and self.context.agent_logger
                ):
                    self.context.agent_logger.warning(
                        f"Anthropic rate limit hit, retrying in {backoff_delay:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )

                # Wait before retry
                await asyncio.sleep(backoff_delay)

            except APITimeoutError as e:
                if attempt == max_retries:
                    raise e

                # For timeouts, use shorter backoff
                backoff_delay = self._calculate_backoff_delay(
                    attempt, 5.0
                )  # 5 second base

                if (
                    self.context
                    and hasattr(self.context, "agent_logger")
                    and self.context.agent_logger
                ):
                    self.context.agent_logger.warning(
                        f"Anthropic timeout, retrying in {backoff_delay:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )

                await asyncio.sleep(backoff_delay)

            except Exception as e:
                # Non-retryable errors should not be retried
                raise e

    def _parse_rate_limit_delay(self, rate_limit_error: RateLimitError) -> float:
        """
        Parse retry delay information from Anthropic rate limit error.

        Args:
            rate_limit_error: The RateLimitError exception

        Returns:
            Suggested retry delay in seconds
        """
        error_str = str(rate_limit_error)

        # Look for common retry delay patterns in error messages
        retry_patterns = [
            r"retry after (\d+) seconds?",
            r"retry in (\d+) seconds?",
            r"wait (\d+) seconds?",
            r"rate limit.*?(\d+)s",
        ]

        import re

        for pattern in retry_patterns:
            match = re.search(pattern, error_str.lower())
            if match:
                try:
                    delay = int(match.group(1))
                    return float(delay)
                except (ValueError, IndexError):
                    continue

        # Default to configured rate limit retry delay
        return self.rate_limit_config["rate_limit_retry_delay"]

    def _calculate_backoff_delay(self, attempt: int, base_delay: float) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Args:
            attempt: Current attempt number (0-based)
            base_delay: Base delay in seconds

        Returns:
            Calculated delay in seconds
        """
        # Exponential backoff: base_delay * 2^attempt
        exponential_delay = base_delay * (2**attempt)

        # Cap at maximum delay
        capped_delay = min(exponential_delay, self.rate_limit_config["max_delay"])

        # Add jitter to prevent thundering herd
        jitter_range = capped_delay * self.rate_limit_config["jitter_factor"]
        jitter = random.uniform(-jitter_range, jitter_range)

        final_delay = max(0.1, capped_delay + jitter)  # Minimum 0.1 seconds

        return final_delay

    def _should_retry_error(self, error: Exception) -> bool:
        """
        Determine if an error should trigger a retry.

        Args:
            error: The exception that occurred

        Returns:
            True if the error should trigger a retry, False otherwise
        """
        # Always retry rate limits and timeouts
        if isinstance(error, (RateLimitError, APITimeoutError)):
            return True

        # Retry network-related errors
        if isinstance(error, (ConnectionError, OSError)):
            return True

        # Don't retry validation or authentication errors
        if isinstance(error, (ValueError, KeyError, TypeError)):
            return False

        # Don't retry API errors that aren't rate limits or timeouts
        if isinstance(error, APIError):
            return False

        # Default to not retrying unknown errors
        return False

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limiting configuration and status.

        Returns:
            Dictionary with rate limiting information
        """
        return {
            "provider": "anthropic",
            "model": self.model,
            "rate_limit_config": self.rate_limit_config.copy(),
            "supports_retry": True,
            "retry_strategy": "exponential_backoff_with_jitter",
            "max_retry_delay": f"{self.rate_limit_config['max_delay']}s",
            "jitter_enabled": True,
        }

    def update_rate_limit_config(self, **kwargs) -> None:
        """
        Update rate limiting configuration.

        Args:
            **kwargs: Configuration updates (max_retries, base_delay, max_delay, etc.)
        """
        for key, value in kwargs.items():
            if key in self.rate_limit_config:
                self.rate_limit_config[key] = value

        if (
            self.context
            and hasattr(self.context, "agent_logger")
            and self.context.agent_logger
        ):
            self.context.agent_logger.info(
                f"Updated Anthropic rate limit config: {kwargs}"
            )

    def get_native_params(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI-style parameters to Anthropic-native parameters.

        Maps OpenAI parameter names to Anthropic's expected parameter names
        based on the official Anthropic API documentation.

        Args:
            options: OpenAI-style configuration options

        Returns:
            Dictionary with Anthropic-native parameter names and values
        """
        native_params = {}

        # OpenAI -> Anthropic parameter mappings
        param_mapping = {
            "temperature": "temperature",  # Direct mapping
            "max_tokens": "max_tokens",  # Direct mapping
            "top_p": "top_p",  # Direct mapping
            "stream": "stream",  # Direct mapping
            "stop": "stop_sequences",  # OpenAI stop -> Anthropic stop_sequences
        }

        for openai_param, anthropic_param in param_mapping.items():
            if openai_param in options:
                native_params[anthropic_param] = options[openai_param]

        # Handle stop sequences specifically (can be string or list)
        if "stop_sequences" in options:
            native_params["stop_sequences"] = options["stop_sequences"]

        # Anthropic-specific parameters that don't have OpenAI equivalents
        # These will be passed through if present in options
        anthropic_specific = {
            "top_k": int,  # Anthropic-specific sampling parameter
            "system": str,  # System message (handled separately in API calls)
            "tools": list,  # Tool definitions (handled separately)
            "tool_choice": dict,  # Tool choice preference (handled separately)
        }

        for param, expected_type in anthropic_specific.items():
            if param in options:
                try:
                    if expected_type == int:
                        native_params[param] = int(options[param])
                    elif expected_type == str:
                        native_params[param] = str(options[param])
                    else:
                        native_params[param] = options[param]
                except (ValueError, TypeError):
                    # Skip invalid parameters
                    continue

        # Note: Anthropic doesn't support frequency_penalty, presence_penalty, seed, or n
        # These OpenAI parameters will be filtered out

        return native_params

    def _is_claude_3_model(self, model: str) -> bool:
        """Check if the model is Claude 3+ (supported by modern messages API)."""
        # Legacy models that require the old completion API
        legacy_model_prefixes = ["claude-1", "claude-2"]

        # Check if it's a legacy model
        for prefix in legacy_model_prefixes:
            if model.startswith(prefix):
                return False

        # All Claude 3+ models (including aliases) use the modern messages API
        # This includes:
        # - claude-3-5-sonnet-latest (alias for claude-3-5-sonnet-20241022)
        # - claude-3-7-sonnet-latest (alias for claude-3-7-sonnet-20250219)
        # - claude-sonnet-4-0 (alias for claude-sonnet-4-20250514)
        # - claude-opus-4-0 (alias for claude-opus-4-20250514)
        modern_model_prefixes = [
            "claude-3",
            "claude-4",
            "claude-sonnet-4",
            "claude-opus-4",
        ]

        for prefix in modern_model_prefixes:
            if model.startswith(prefix):
                return True

        # Default to modern API for unknown models (safer assumption)
        return True

    def _clean_message(self, msg: dict) -> dict:
        """Clean message to only include fields supported by Anthropic API."""
        # Handle tool results - Anthropic doesn't support "tool" role
        if msg.get("role") == "tool":
            # Convert tool results to user message with tool result content
            tool_result = msg.get("content", "")
            return {"role": "user", "content": f"Tool result: {tool_result}".rstrip()}

        allowed = {"role", "content"}
        cleaned = {k: v for k, v in msg.items() if k in allowed}

        # Ensure required fields are present and roles are valid
        if "role" not in cleaned or cleaned["role"] not in ["user", "assistant"]:
            cleaned["role"] = "user"
        if "content" not in cleaned:
            cleaned["content"] = ""

        # Strip trailing whitespace from content to avoid Anthropic API errors
        if isinstance(cleaned["content"], str):
            cleaned["content"] = cleaned["content"].rstrip()

        return cleaned

    def _convert_tools_to_anthropic_format(self, tools: List[dict]) -> List[dict]:
        """Convert tools from OpenAI format to Anthropic format."""
        converted_tools = []

        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                # Convert from OpenAI format to Anthropic format
                func_def = tool["function"]
                converted_tool = {
                    "type": "custom",
                    "name": func_def["name"],
                    "description": func_def.get("description", ""),
                    "input_schema": func_def.get(
                        "parameters",
                        {"type": "object", "properties": {}, "required": []},
                    ),
                }
                converted_tools.append(converted_tool)
            else:
                # Tool is already in the correct format or unknown format
                converted_tools.append(tool)

        return converted_tools

    def _extract_system_message(
        self, messages: List[dict]
    ) -> tuple[Optional[str], List[dict]]:
        """Extract system message from messages list."""
        system_message = None
        filtered_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg.get("content", "")
            else:
                filtered_messages.append(msg)

        return system_message, filtered_messages

    def validate_model(self, **kwargs) -> dict:
        """Validate that the model is supported by Anthropic."""
        try:
            # Try to get available models from Anthropic API
            available_models = []
            try:
                # Use the client to list available models
                models_response = self.client.models.list()
                available_models = [model.id for model in models_response.data]
            except Exception as api_error:
                # If API call fails, fall back to basic validation
                if not self.is_claude_3:
                    return {
                        "valid": True,
                        "model": self.model,
                        "warning": f"Legacy model - requires manual HTTP implementation. Could not verify: {api_error}",
                    }
                else:
                    # Basic format check as fallback
                    if any(
                        prefix in self.model.lower()
                        for prefix in [
                            "claude-3",
                            "claude-4",
                            "claude-sonnet-4",
                            "claude-opus-4",
                        ]
                    ):
                        return {
                            "valid": True,
                            "model": self.model,
                            "warning": f"Could not verify model with API ({api_error}), but format appears valid",
                        }
                    else:
                        raise ValueError(
                            f"Could not validate model '{self.model}' - API unavailable and unknown format"
                        )

            # Check if model is in the available list
            if self.model in available_models:
                if not self.is_claude_3:
                    return {
                        "valid": True,
                        "model": self.model,
                        "warning": "Legacy model - requires manual HTTP implementation",
                    }
                else:
                    return {"valid": True, "model": self.model}

            # If not found directly, try to validate by making a test API call
            # This handles aliases and new models dynamically
            try:
                # Make a minimal test request to validate the model exists
                self.client.messages.create(
                    model=self.model,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "test"}],
                )
                # If we get here, the model is valid
                if not self.is_claude_3:
                    return {
                        "valid": True,
                        "model": self.model,
                        "warning": "Legacy model - requires manual HTTP implementation (validated via API test)",
                    }
                else:
                    return {
                        "valid": True,
                        "model": self.model,
                        "note": "Model validated via API test (not in models list - may be alias or new model)",
                    }
            except Exception as test_error:
                # If test call fails, the model is truly invalid
                raise ValueError(
                    f"Model '{self.model}' is not available from Anthropic. "
                    f"Available models: {', '.join(available_models[:10])}{'...' if len(available_models) > 10 else ''}. "
                    f"API test failed: {str(test_error)}"
                )

        except Exception as e:
            self._handle_error(e, "validation")
            return {"valid": False, "error": str(e)}

    def _supports_native_tool_calling(self, model: str) -> bool:
        """
        Check if the Anthropic model supports native tool calling.

        Most modern Claude models support tool calling, but older versions may not.

        Args:
            model: Optional model name to check (defaults to self.model)

        Returns:
            True if model supports native tool calling, False otherwise
        """
        model_to_check = model or self.model

        # Models known to NOT support tool calling
        non_tool_calling_models = {
            "claude-instant-1",  # Legacy model
            "claude-1",  # Legacy model
            "claude-1.3",  # Legacy model
            "claude-2.0",  # Older model without tools
        }

        # Check if model is in non-tool-calling list
        return model_to_check not in non_tool_calling_models

    async def _execute_structured_chat_completion(
        self,
        response_model: Type[BaseModel],
        messages: List[dict],
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BaseModel:
        """
        Execute structured chat completion using Instructor for Anthropic.

        Args:
            response_model: The Pydantic model class
            messages: List of message dictionaries
            options: Provider-specific options
            **kwargs: Additional arguments

        Returns:
            An instance of the response_model
        """
        if not self.instructor_client:
            raise RuntimeError(
                "Instructor client not initialized for Anthropic provider"
            )

        try:
            # Extract system message and clean messages
            system_message, cleaned_messages = self._extract_system_message(messages)
            cleaned_messages = [self._clean_message(msg) for msg in cleaned_messages]

            # Merge options
            merged_options = {**self.default_options, **(options or {})}

            # Get OpenAI-style parameters for Instructor (filters out Anthropic-specific params)
            openai_params = self.get_openai_params(merged_options)

            # Prepare API call parameters for instructor
            api_params = {
                "model": self.model,
                "messages": cleaned_messages,
                "response_model": response_model,
                **openai_params,
            }

            # Add system message if present
            if system_message:
                api_params["system"] = system_message

            # Use instructor client for structured response with retry logic
            structured_response = await self._retry_with_backoff(
                lambda: self._call_instructor_client(
                    "chat.completions.create", **api_params
                )
            )

            return structured_response

        except Exception as e:
            self._handle_error(e, "structured_chat_completion")
            raise Exception(f"Anthropic Structured Chat Completion Error: {str(e)}")

    async def _get_provider_chat_completion(self, **kwargs) -> CompletionResponse:
        """
        Get a chat completion from Anthropic.

        Args:
            messages: List of message dictionaries
            stream: Whether to stream the response
            tools: List of tool definitions
            tool_choice: Tool choice preference
            options: Model-specific options
            format: Response format ("json" or "")
            **kwargs: Additional arguments
        """
        messages = kwargs.get("messages", [])
        stream = kwargs.get("stream", False)
        tools = kwargs.get("tools")
        tool_choice = kwargs.get("tool_choice")
        options = kwargs.get("options")
        format = kwargs.get("format", "")

        try:
            if not self.is_claude_3:
                return await self._get_legacy_completion(**kwargs)

            # Extract system message and clean messages
            system_message, cleaned_messages = self._extract_system_message(messages)
            cleaned_messages = [self._clean_message(msg) for msg in cleaned_messages]

            # Merge options
            merged_options = {**self.default_options, **(options or {})}

            # Convert OpenAI-style parameters to Anthropic-native format
            native_options = self.get_native_params(merged_options)

            # Prepare API call parameters
            api_params = {
                "model": self.model,
                "messages": cleaned_messages,
                **native_options,
            }

            # Add system message if present
            if system_message:
                api_params["system"] = system_message

            # Add tools if present (convert to Anthropic format)
            if tools:
                api_params["tools"] = self._convert_tools_to_anthropic_format(tools)
                if tool_choice and tool_choice != "auto":
                    api_params["tool_choice"] = tool_choice

            # Handle JSON format for Claude 3 models (structured outputs handled by base class)
            if format == "json":
                # Add JSON instruction to the last user message
                if cleaned_messages and cleaned_messages[-1].get("role") == "user":
                    cleaned_messages[-1][
                        "content"
                    ] += "\n\nPlease respond in valid JSON format."
                elif system_message:
                    system_message += "\n\nAlways respond in valid JSON format."
                    api_params["system"] = system_message
                else:
                    # Add system message if not present
                    api_params["system"] = "Always respond in valid JSON format."

            # Create completion with retry logic
            completion = await self._retry_with_backoff(
                lambda: self.client.messages.create(**api_params)
            )
            if stream:
                return completion  # Return stream object directly

            # Process non-streaming response
            content = ""
            tool_calls = None

            # Extract content and tool calls
            if completion.content:
                for block in completion.content:
                    if isinstance(block, TextBlock):
                        content += block.text
                    elif isinstance(block, ToolUseBlock):
                        if tool_calls is None:
                            tool_calls = []
                        tool_calls.append(
                            {
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": block.input,
                                },
                            }
                        )

            message = CompletionMessage(
                content=content,
                role="assistant",
                tool_calls=tool_calls,
            )

            return CompletionResponse(
                message=self.extract_and_store_thinking(
                    message, call_context="chat_completion"
                ),
                model=completion.model,
                done=True,
                done_reason=completion.stop_reason,
                prompt_tokens=completion.usage.input_tokens,
                completion_tokens=completion.usage.output_tokens,
                total_duration=None,  # Anthropic doesn't provide timing info
                created_at=str(time.time()),
            )

        except RateLimitError as e:
            if self._should_retry_error(e):
                # Let the retry logic handle it
                raise e
            else:
                self._handle_error(e, "chat_completion")
                raise Exception(f"Anthropic Rate Limit Error: {str(e)}")
        except APITimeoutError as e:
            if self._should_retry_error(e):
                # Let the retry logic handle it
                raise e
            else:
                self._handle_error(e, "chat_completion")
                raise Exception(f"Anthropic API Timeout Error: {str(e)}")
        except APIError as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"Anthropic API Error: {str(e)}")
        except Exception as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"Anthropic Chat Completion Error: {str(e)}")

    async def _stream_provider_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion tokens from Anthropic.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions
            options: Model-specific options
            **kwargs: Additional arguments

        Yields:
            StreamChunk objects containing content and metadata
        """
        try:
            if not self.is_claude_3:
                # Legacy models don't support streaming well, fall back to non-streaming
                self._warn_parameter(
                    f"Legacy model {self.model} has limited streaming support, falling back",
                    level="warning",
                )
                response = await self._get_legacy_completion(
                    messages=messages, options=options, **kwargs
                )
                yield StreamChunk(
                    content=response.message.content,
                    role=response.message.role,
                    finish_reason=response.done_reason,
                    is_final=True,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    total_tokens=response.total_tokens,
                    model=response.model,
                )
                return

            # Extract system message and clean messages
            system_message, cleaned_messages = self._extract_system_message(messages)
            cleaned_messages = [self._clean_message(msg) for msg in cleaned_messages]

            # Merge options
            merged_options = {**self.default_options, **(options or {})}

            # Convert OpenAI-style parameters to Anthropic-native format
            native_options = self.get_native_params(merged_options)
            # Remove stream from options as we handle it explicitly
            native_options.pop("stream", None)

            # Prepare API call parameters
            api_params = {
                "model": self.model,
                "messages": cleaned_messages,
                **native_options,
            }

            # Add system message if present
            if system_message:
                api_params["system"] = system_message

            # Add tools if present (convert to Anthropic format)
            if tools:
                api_params["tools"] = self._convert_tools_to_anthropic_format(tools)

            chunk_index = 0
            accumulated_content = ""
            accumulated_tool_calls: list[dict] = []
            current_tool_call: dict = {}
            input_tokens = 0
            output_tokens = 0

            # Use Anthropic's streaming API
            with self.client.messages.stream(**api_params) as stream:
                for event in stream:
                    # Handle different event types
                    if event.type == "message_start":
                        # Get initial token counts
                        if hasattr(event, "message") and hasattr(event.message, "usage"):
                            input_tokens = event.message.usage.input_tokens

                    elif event.type == "content_block_start":
                        # Check if this is a tool use block
                        if hasattr(event, "content_block"):
                            block = event.content_block
                            if hasattr(block, "type") and block.type == "tool_use":
                                current_tool_call = {
                                    "id": block.id,
                                    "type": "function",
                                    "function": {
                                        "name": block.name,
                                        "arguments": "",
                                    },
                                }

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        content = ""

                        if hasattr(delta, "text"):
                            content = delta.text
                            accumulated_content += content
                        elif hasattr(delta, "partial_json"):
                            # Accumulate tool call arguments
                            if current_tool_call:
                                current_tool_call["function"]["arguments"] += delta.partial_json

                        if content:
                            yield StreamChunk(
                                content=content,
                                role="assistant",
                                chunk_index=chunk_index,
                                model=self.model,
                            )
                            chunk_index += 1

                    elif event.type == "content_block_stop":
                        # Finalize tool call if we have one
                        if current_tool_call:
                            # Parse the accumulated JSON arguments
                            try:
                                args_str = current_tool_call["function"]["arguments"]
                                if args_str:
                                    current_tool_call["function"]["arguments"] = json.loads(args_str)
                            except json.JSONDecodeError:
                                # Keep as string if not valid JSON
                                pass
                            accumulated_tool_calls.append(current_tool_call)
                            current_tool_call = {}

                    elif event.type == "message_delta":
                        # Get output tokens from message delta
                        if hasattr(event, "usage"):
                            output_tokens = event.usage.output_tokens

                    elif event.type == "message_stop":
                        # Final message - yield with complete info
                        pass

                # Yield final chunk with token usage and tool calls
                final_chunk = StreamChunk(
                    content="",
                    role="assistant",
                    finish_reason="end_turn",
                    tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
                    is_final=True,
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    chunk_index=chunk_index,
                    model=self.model,
                )
                yield final_chunk

        except RateLimitError as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"Anthropic Rate Limit Error: {str(e)}")
        except APITimeoutError as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"Anthropic API Timeout Error: {str(e)}")
        except APIError as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"Anthropic API Error: {str(e)}")
        except Exception as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"Anthropic Stream Chat Completion Error: {str(e)}")

    async def _get_legacy_completion(self, **kwargs) -> CompletionResponse:
        """
        Get completion for legacy Claude models using manual HTTP requests.

        This is a fallback for Claude 1/2 models that aren't supported by the SDK.
        """
        messages = kwargs.get("messages", [])
        stream = kwargs.get("stream", False)
        options = kwargs.get("options")
        format = kwargs.get("format", "")

        try:
            # Convert messages to legacy prompt format
            prompt = self._convert_messages_to_legacy_prompt(messages)

            # Prepare request data
            api_key = os.getenv("ANTHROPIC_API_KEY")
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": api_key,
                "anthropic-version": "2023-06-01",
            }

            merged_options = {**self.default_options, **(options or {})}

            # Convert OpenAI-style parameters to Anthropic-native format
            native_options = self.get_native_params(merged_options)

            data = {
                "model": self.model,
                "prompt": prompt,
                "max_tokens_to_sample": native_options.get("max_tokens", 1000),
                "temperature": native_options.get("temperature", 0.7),
                "stream": native_options.get("stream", stream),
            }

            # Add stop sequences if present
            if "stop_sequences" in native_options:
                data["stop_sequences"] = native_options["stop_sequences"]

            # Handle JSON format for legacy models
            if format == "json":
                data["prompt"] += "\n\nPlease respond in valid JSON format."

            # Make request to legacy API
            response = requests.post(
                "https://api.anthropic.com/v1/complete",
                headers=headers,
                json=data,
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()

            message = CompletionMessage(
                content=result.get("completion", ""),
                role="assistant",
                tool_calls=None,  # Legacy API doesn't support tool calls
            )

            return CompletionResponse(
                message=self.extract_and_store_thinking(
                    message, call_context="chat_completion"
                ),
                model=self.model,
                done=True,
                done_reason=result.get("stop_reason"),
                prompt_tokens=0,  # Legacy API doesn't provide token counts
                completion_tokens=0,
                total_duration=None,
                created_at=str(time.time()),
            )

        except Exception as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"Anthropic Legacy Completion Error: {str(e)}")

    def _convert_messages_to_legacy_prompt(self, messages: List[dict]) -> str:
        """Convert messages to legacy Claude prompt format."""
        prompt = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                prompt += f"{content}\n\n"
            elif role == "user":
                prompt += f"Human: {content}\n\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n\n"

        # Ensure it ends with Assistant:
        if not prompt.strip().endswith("Assistant:"):
            prompt += "Assistant:"

        return prompt

    async def _get_provider_completion(self, **kwargs) -> CompletionResponse:
        """
        Get a text completion from Anthropic using the chat completions API.

        Args:
            prompt: The prompt text
            system: Optional system message
            options: Model-specific options
            format: Response format ("json" or "")
            **kwargs: Additional arguments
        """
        prompt = kwargs.get("prompt", "")
        system = kwargs.get("system")
        options = kwargs.get("options")
        format = kwargs.get("format", "")

        try:
            # Build messages
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            # Use chat completion for text completion
            # Remove conflicting parameters from kwargs to avoid "multiple values" error
            filtered_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in ["messages", "options", "format"]
            }
            return await self._get_provider_chat_completion(
                messages=messages, options=options, format=format, **filtered_kwargs
            )

        except Exception as e:
            self._handle_error(e, "completion")
            raise Exception(f"Anthropic Completion Error: {str(e)}")
