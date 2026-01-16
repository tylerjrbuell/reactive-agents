import json
import os
import time
from typing import List, Dict, Any, Optional, Union, Type, AsyncIterator
from openai import BaseModel, OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai import OpenAIError, RateLimitError, APITimeoutError
import instructor

from .base import BaseModelProvider, CompletionMessage, CompletionResponse
from reactive_agents.core.types.provider_types import StreamChunk


class OpenAIModelProvider(BaseModelProvider):
    """OpenAI model provider using the official OpenAI Python SDK."""

    id = "openai"

    def __init__(
        self,
        model: str = "gpt-4",
        options: Optional[Dict[str, Any]] = None,
        context=None,
    ):
        """
        Initialize the OpenAI model provider.

        Args:
            model: The model to use (e.g., "gpt-4", "gpt-3.5-turbo", "gpt-4o")
            options: Optional configuration options
            context: The agent context for error tracking and logging
        """
        super().__init__(model=model, options=options, context=context)

        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.client = OpenAI(api_key=api_key)

        # Initialize instructor client for structured outputs
        try:
            self.instructor_client = instructor.from_openai(self.client)
            self._supports_structured = True
        except Exception as e:
            if context and hasattr(context, "agent_logger") and context.agent_logger:
                context.agent_logger.warning(
                    f"Failed to initialize Instructor client for OpenAI: {e}"
                )
            self.instructor_client = None
            self._supports_structured = False

        # Default options
        self.default_options = {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }

        # Validate model on initialization
        self.validate_model()

    def _clean_message(self, msg: dict) -> dict:
        """Clean message to only include fields supported by OpenAI API."""
        allowed = {"role", "content", "name", "tool_call_id", "tool_calls"}
        cleaned = {k: v for k, v in msg.items() if k in allowed}

        # Handle tool messages - OpenAI has strict requirements for tool message ordering
        # Convert tool messages to user messages with clear labeling
        if cleaned.get("role") == "tool":
            cleaned["role"] = "user"
            # Preserve the tool result information in the content
            original_content = cleaned.get("content", "")
            tool_call_id = cleaned.get("tool_call_id", "unknown")
            cleaned["content"] = f"[Tool Result for {tool_call_id}]: {original_content}"

            # Remove tool-specific fields since we're converting to user message
            cleaned.pop("tool_call_id", None)

        # Ensure required fields are present
        if "role" not in cleaned:
            cleaned["role"] = "user"
        if "content" not in cleaned:
            cleaned["content"] = ""

        return cleaned

    def _validate_message_sequence(self, messages: List[dict]) -> List[dict]:
        """Validate and fix message sequence for OpenAI's tool calling requirements."""
        if not messages:
            return messages

        validated_messages = []
        i = 0

        while i < len(messages):
            msg = messages[i]

            # If this is a tool message, ensure it follows an assistant message with tool_calls
            if msg.get("role") == "tool":
                # Look back to find the most recent assistant message with tool_calls
                assistant_with_tools_idx = None
                for j in range(len(validated_messages) - 1, -1, -1):
                    if validated_messages[j].get(
                        "role"
                    ) == "assistant" and validated_messages[j].get("tool_calls"):
                        assistant_with_tools_idx = j
                        break

                # If we found an assistant message with tool_calls, but it's not the immediate predecessor
                if (
                    assistant_with_tools_idx is not None
                    and assistant_with_tools_idx != len(validated_messages) - 1
                ):
                    # Remove any intermediate messages that aren't tool messages
                    # Keep only tool messages that might be part of the same tool call sequence
                    filtered_messages = validated_messages[
                        : assistant_with_tools_idx + 1
                    ]
                    for k in range(
                        assistant_with_tools_idx + 1, len(validated_messages)
                    ):
                        if validated_messages[k].get("role") == "tool":
                            filtered_messages.append(validated_messages[k])
                    validated_messages = filtered_messages

                validated_messages.append(msg)
            else:
                validated_messages.append(msg)

            i += 1

        return validated_messages

    def _process_tool_calls(self, tool_calls):
        """Process tool calls to ensure arguments are properly formatted as dictionaries."""
        if not tool_calls:
            return None

        processed_calls = []
        for call in tool_calls:
            processed_call = {
                "id": call.id,
                "type": call.type,
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }

            # Ensure function arguments are dictionaries, not JSON strings
            args = processed_call["function"]["arguments"]
            if isinstance(args, str):
                try:
                    processed_call["function"]["arguments"] = (
                        json.loads(args) if args else {}
                    )
                except (json.JSONDecodeError, TypeError):
                    processed_call["function"]["arguments"] = {}
            elif not isinstance(args, dict):
                processed_call["function"]["arguments"] = {}

            processed_calls.append(processed_call)

        return processed_calls

    def validate_model(self, **kwargs) -> dict:
        """Validate that the model is supported by OpenAI."""
        try:
            # Get available models
            models = self.client.models.list()
            available_models = [model.id for model in models.data]

            if self.model not in available_models:
                raise ValueError(
                    f"Model '{self.model}' is not available. "
                    f"Available models: {', '.join(available_models[:10])}..."
                )

            return {"valid": True, "model": self.model}
        except Exception as e:
            self._handle_error(e, "validation")
            return {"valid": False, "error": str(e)}

    def _supports_native_tool_calling(self, model: str) -> bool:
        """
        Check if the OpenAI model supports native tool calling.

        OpenAI models generally support tool calling, but we can check specific models
        that are known to have limitations.

        Args:
            model: Optional model name to check (defaults to self.model)

        Returns:
            True if model supports native tool calling, False otherwise
        """
        model_to_check = model or self.model

        # Models known to NOT support tool calling
        non_tool_calling_models = {
            "gpt-3.5-turbo-instruct",  # Completion-only model
            "text-davinci-003",  # Legacy completion model
            "text-davinci-002",  # Legacy completion model
            "davinci",  # Legacy model
            "curie",  # Legacy model
            "babbage",  # Legacy model
            "ada",  # Legacy model
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
        Execute structured chat completion using Instructor for OpenAI.

        Args:
            response_model: The Pydantic model class
            messages: List of message dictionaries
            options: Provider-specific options
            **kwargs: Additional arguments

        Returns:
            An instance of the response_model
        """
        if not self.instructor_client:
            raise RuntimeError("Instructor client not initialized for OpenAI provider")

        try:
            # Clean messages
            cleaned_messages = [self._clean_message(msg) for msg in messages]

            # Validate message sequence for OpenAI's tool calling requirements
            cleaned_messages = self._validate_message_sequence(cleaned_messages)

            # Merge options
            merged_options = {**self.default_options, **(options or {})}

            # Prepare API call parameters for instructor
            api_params = {
                "model": self.model,
                "messages": cleaned_messages,
                "response_model": response_model,
                **merged_options,
            }

            # Use instructor client for structured response
            structured_response = await self._call_instructor_client(
                "chat.completions.create", **api_params
            )

            return structured_response

        except Exception as e:
            self._handle_error(e, "structured_chat_completion")
            raise Exception(f"OpenAI Structured Chat Completion Error: {str(e)}")

    async def _get_provider_chat_completion(self, **kwargs) -> CompletionResponse:
        """
        Get a chat completion from OpenAI.

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
            # Clean messages
            cleaned_messages = [self._clean_message(msg) for msg in messages]

            # Validate message sequence for OpenAI's tool calling requirements
            cleaned_messages = self._validate_message_sequence(cleaned_messages)

            # Merge options
            merged_options = {**self.default_options, **(options or {})}

            # Prepare API call parameters
            api_params = {
                "model": self.model,
                "messages": cleaned_messages,
                "stream": stream,
                **merged_options,
            }

            # Add optional parameters
            if tools:
                api_params["tools"] = tools
                if tool_choice is None:
                    api_params["tool_choice"] = "auto"
                else:
                    api_params["tool_choice"] = tool_choice

            # Handle JSON format (structured outputs handled by base class)
            if format == "json":
                api_params["response_format"] = {"type": "json_object"}

            # Create completion (no more custom parse() logic)
            completion = self.client.chat.completions.create(**api_params)

            if stream:
                return completion

            # Process non-streaming response
            result = completion.choices[0]

            # Extract tool calls if present
            tool_calls = self._process_tool_calls(result.message.tool_calls)

            message = CompletionMessage(
                content=result.message.content or "",
                role=result.message.role,
                tool_calls=tool_calls,
            )

            return CompletionResponse(
                message=self.extract_and_store_thinking(
                    message, call_context="chat_completion"
                ),
                model=completion.model,
                done=True,
                done_reason=result.finish_reason,
                prompt_tokens=(
                    int(completion.usage.prompt_tokens or 0) if completion.usage else 0
                ),
                completion_tokens=(
                    int(completion.usage.completion_tokens or 0)
                    if completion.usage
                    else 0
                ),
                total_duration=None,  # OpenAI doesn't provide timing info
                created_at=str(completion.created),
            )

        except RateLimitError as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"OpenAI Rate Limit Error: {str(e)}")
        except APITimeoutError as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"OpenAI API Timeout Error: {str(e)}")
        except OpenAIError as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"OpenAI API Error: {str(e)}")
        except Exception as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"OpenAI Chat Completion Error: {str(e)}")

    async def _stream_provider_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion from OpenAI.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions
            options: Model-specific options
            **kwargs: Additional arguments

        Yields:
            StreamChunk objects containing streamed content
        """
        try:
            # Clean messages
            cleaned_messages = [self._clean_message(msg) for msg in messages]
            cleaned_messages = self._validate_message_sequence(cleaned_messages)

            # Merge options
            merged_options = {**self.default_options, **(options or {})}

            # Prepare API call parameters
            api_params = {
                "model": self.model,
                "messages": cleaned_messages,
                "stream": True,
                "stream_options": {"include_usage": True},
                **merged_options,
            }

            # Add tools if provided
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = kwargs.get("tool_choice", "auto")

            # Handle JSON format
            format_param = kwargs.get("format", "")
            if format_param == "json":
                api_params["response_format"] = {"type": "json_object"}

            # Create streaming completion
            stream = self.client.chat.completions.create(**api_params)

            chunk_index = 0
            accumulated_content = ""
            accumulated_tool_calls: List[Dict[str, Any]] = []
            finish_reason = None
            prompt_tokens = 0
            completion_tokens = 0

            for chunk in stream:
                if not chunk.choices:
                    # Final chunk with usage info
                    if chunk.usage:
                        prompt_tokens = chunk.usage.prompt_tokens or 0
                        completion_tokens = chunk.usage.completion_tokens or 0
                    continue

                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Extract content
                content = delta.content or ""
                accumulated_content += content

                # Extract tool calls from delta
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_index = tc.index
                        # Extend list if needed
                        while len(accumulated_tool_calls) <= tc_index:
                            accumulated_tool_calls.append({
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            })
                        # Update tool call
                        if tc.id:
                            accumulated_tool_calls[tc_index]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[tc_index]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[tc_index]["function"]["arguments"] += tc.function.arguments

                # Determine if this is the final chunk
                is_final = finish_reason is not None

                yield StreamChunk(
                    content=content,
                    role=delta.role if hasattr(delta, "role") and delta.role else "assistant",
                    finish_reason=finish_reason,
                    tool_calls=accumulated_tool_calls if is_final and accumulated_tool_calls else None,
                    is_final=is_final,
                    prompt_tokens=prompt_tokens if is_final else 0,
                    completion_tokens=completion_tokens if is_final else 0,
                    total_tokens=(prompt_tokens + completion_tokens) if is_final else 0,
                    chunk_index=chunk_index,
                    model=self.model,
                )
                chunk_index += 1

        except RateLimitError as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"OpenAI Rate Limit Error: {str(e)}")
        except APITimeoutError as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"OpenAI API Timeout Error: {str(e)}")
        except OpenAIError as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"OpenAI API Error: {str(e)}")
        except Exception as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"OpenAI Stream Chat Completion Error: {str(e)}")

    async def _get_provider_completion(self, **kwargs) -> CompletionResponse:
        """
        Get a text completion from OpenAI using the chat completions API.

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
            raise Exception(f"OpenAI Completion Error: {str(e)}")
