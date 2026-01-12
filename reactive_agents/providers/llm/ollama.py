import json
import os
import time
from typing import List, Literal, Optional, Dict, Any, Type, AsyncIterator

from reactive_agents.core.types.tool_types import ToolCall
from pydantic import BaseModel
import instructor
import ollama

from .base import (
    BaseModelProvider,
    CompletionMessage,
    CompletionResponse,
    StreamChunk,
)

DEFAULT_OPTIONS = {"temperature": 0.2, "num_ctx": 10000}


class OllamaModelProvider(BaseModelProvider):
    id = "ollama"

    def __init__(
        self,
        model: str,
        host: Optional[str] = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        or DEFAULT_OPTIONS.get("host"),
        options: Optional[Dict[str, Any]] = None,
        context=None,
    ):
        """
        Initialize the Ollama model provider.

        Args:
            model: The model to use
            options: Optional configuration options
            context: The agent context for error tracking and logging
        """
        super().__init__(model=model, options=options, context=context)
        self.host = host
        self.client = ollama.AsyncClient(host=self.host)
        # Initialize instructor client for structured outputs
        try:
            # Initialize OpenAI client for Ollama compatibility
            from openai import OpenAI

            openai_client = OpenAI(
                base_url=f"{self.host}/v1",
                api_key="ollama",  # required, but unused
            )

            # Patch with instructor for structured outputs
            self.instructor_client = instructor.from_openai(
                openai_client,
                mode=instructor.Mode.JSON,
            )
            self._supports_structured = True
        except Exception as e:
            if context and hasattr(context, "agent_logger") and context.agent_logger:
                context.agent_logger.warning(
                    f"Failed to initialize Instructor client for Ollama: {e}"
                )
            self.instructor_client = None
            self._supports_structured = False

        # Validate model after initialization
        self.validate_model()

    def validate_model(self, **kwargs) -> dict:
        """Validate that the model is available in Ollama."""
        try:
            models = ollama.Client(host=self.host).list().models
            model = self.model
            if ":" not in self.model:
                model = f"{self.model}:latest"
            available_models = [m.model for m in models if m.model is not None]
            if model not in available_models:
                raise ValueError(
                    f"Model {self.model} is either not supported or has not been downloaded from Ollama. "
                    f"Run `ollama pull {self.model}` to download the model. "
                    f"Available models: {', '.join(available_models)}"
                )
            return {"valid": True, "model": self.model}
        except Exception as e:
            self._handle_error(e, "validation")
            return {"valid": False, "error": str(e)}

    def get_native_params(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI-style parameters to Ollama-native parameters.

        Maps OpenAI parameter names to Ollama's expected parameter names
        based on the official Ollama API documentation.

        Args:
            options: OpenAI-style configuration options

        Returns:
            Dictionary with Ollama-native parameter names and values
        """
        native_params = {}

        # OpenAI -> Ollama parameter mappings
        param_mapping = {
            "temperature": "temperature",  # Direct mapping
            "max_tokens": "num_predict",  # OpenAI max_tokens -> Ollama num_predict
            "top_p": "top_p",  # Direct mapping
            "seed": "seed",  # Direct mapping
            "stop": "stop",  # Direct mapping
        }

        for openai_param, ollama_param in param_mapping.items():
            if openai_param in options:
                native_params[ollama_param] = options[openai_param]

        # Handle frequency_penalty -> repeat_penalty conversion
        if "frequency_penalty" in options:
            # OpenAI frequency_penalty (0.0 to 2.0) -> Ollama repeat_penalty
            # OpenAI 0.0 = no penalty, 2.0 = high penalty
            # Ollama 1.0 = no penalty, >1.0 = penalty
            freq_penalty = float(options["frequency_penalty"])
            if freq_penalty > 0:
                native_params["repeat_penalty"] = 1.0 + freq_penalty

        # Handle Ollama-specific parameters directly
        ollama_specific = {
            "num_ctx": int,  # Context window size
            "num_gpu": int,  # GPU layers to offload
            "num_thread": int,  # Number of threads
            "num_predict": int,  # Max tokens to predict (alternative to max_tokens)
            "repeat_last_n": int,  # Look back for repetition prevention
            "repeat_penalty": float,  # Repetition penalty
            "top_k": int,  # Top-K sampling
            "tfs_z": float,  # Tail free sampling
            "typical_p": float,  # Typical sampling
            "mirostat": int,  # Mirostat sampling
            "mirostat_eta": float,  # Mirostat learning rate
            "mirostat_tau": float,  # Mirostat target entropy
            "penalize_newline": bool,  # Penalize newlines
            "thinking_enabled": bool,  # Enable thinking mode -> "think" parameter
        }

        for param, expected_type in ollama_specific.items():
            if param in options:
                try:
                    if param == "thinking_enabled":
                        # Map thinking_enabled to Ollama's "think" parameter
                        native_params["think"] = bool(options[param])
                    elif expected_type == int:
                        native_params[param] = int(options[param])
                    elif expected_type == float:
                        native_params[param] = float(options[param])
                    elif expected_type == bool:
                        native_params[param] = bool(options[param])
                    else:
                        native_params[param] = options[param]
                except (ValueError, TypeError):
                    # Skip invalid parameters
                    continue

        # Add sensible defaults only if user hasn't specified values
        defaults = {
            "num_ctx": 4096,  # Context window size
            "repeat_last_n": 64,  # Look back for repetition prevention
            "top_k": 40,  # Top-K sampling
        }

        for param, default_value in defaults.items():
            if param not in native_params:
                native_params[param] = default_value

        return native_params

    def _supports_native_tool_calling(self, model: str) -> bool:
        """
        Check if the Ollama model supports native tool calling.

        Args:
            model: Optional model name to check (defaults to self.model)

        Returns:
            True if model supports native tool calling, False otherwise
        """
        try:
            model_to_check = model or self.model
            model_info = ollama.Client(host=self.host).show(model_to_check)
            capabilities = model_info.get("capabilities", [])
            return "tools" in capabilities
        except Exception:
            # If we can't determine capabilities, assume no tool support for safety
            return False

    async def _execute_structured_chat_completion(
        self,
        response_model: Type[BaseModel],
        messages: List[dict],
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BaseModel:
        """
        Execute structured chat completion using Instructor for Ollama.

        Args:
            response_model: The Pydantic model class
            messages: List of message dictionaries
            options: Provider-specific options
            **kwargs: Additional arguments

        Returns:
            An instance of the response_model
        """
        if not self.instructor_client:
            raise RuntimeError("Instructor client not initialized for Ollama provider")

        try:
            # Merge options with defaults
            merged_options = {**DEFAULT_OPTIONS, **(options or {})}

            # Get OpenAI-style parameters for Instructor (filters out Ollama-specific params)
            openai_params = self.get_openai_params(merged_options)

            # Prepare API call parameters for instructor
            api_params = {
                "model": self.model,
                "messages": messages,
                "response_model": response_model,
                "max_retries": 1,  # Reduce retries for faster fallback
                **openai_params,
            }

            # Enhanced debug logging
            # print(f"DEBUG: Instructor API params for {response_model.__name__}: {api_params}")
            # print(f"DEBUG: Response model schema: {response_model.model_json_schema()}")
            # print(f"DEBUG: Messages being sent: {messages}")

            # Try instructor first, but with better error handling
            try:
                structured_response = await self._call_instructor_client(
                    "chat.completions.create", **api_params
                )

                print(
                    f"DEBUG: Instructor succeeded for {response_model.__name__}: {structured_response}"
                )
                return structured_response

            except Exception as instructor_error:
                print(
                    f"DEBUG: Instructor failed for {response_model.__name__}: {instructor_error}"
                )

                # Check if it's a validation error vs other errors
                if (
                    "validation error" in str(instructor_error).lower()
                    or "field required" in str(instructor_error).lower()
                ):
                    print(
                        f"DEBUG: Detected validation error, falling back to native Ollama for {response_model.__name__}"
                    )
                else:
                    print(
                        f"DEBUG: Non-validation error, falling back to native Ollama for {response_model.__name__}"
                    )

                # Always fallback to native Ollama format for now
                return await self._execute_native_ollama_structured(
                    response_model, messages, merged_options
                )

        except Exception as e:
            print(
                f"DEBUG: Outer exception in structured chat completion for {response_model.__name__}: {e}"
            )
            self._handle_error(e, "structured_chat_completion")
            raise Exception(f"Ollama Structured Chat Completion Error: {str(e)}")

    async def _execute_native_ollama_structured(
        self,
        response_model: Type[BaseModel],
        messages: List[dict],
        options: Dict[str, Any],
    ) -> BaseModel:
        """
        Execute structured completion using native Ollama format.

        Args:
            response_model: The Pydantic model class
            messages: List of message dictionaries
            options: Ollama-specific options

        Returns:
            An instance of the response_model
        """
        import json

        print(
            f"DEBUG: Using native Ollama structured completion for {response_model.__name__}"
        )

        # Use universal parameter translation for native Ollama
        native_options = self.get_native_params(options)
        print(f"DEBUG: Translated native Ollama options: {native_options}")

        # Get the JSON schema
        schema = response_model.model_json_schema()
        print(f"DEBUG: Native Ollama schema for {response_model.__name__}: {schema}")

        # Use native Ollama chat with format parameter
        result = await self.client.chat(
            model=self.model,
            messages=messages,
            format=schema,
            options=native_options,
            stream=False,
        )

        print(
            f"DEBUG: Native Ollama raw response for {response_model.__name__}: {result.message.content}"
        )

        # Parse the JSON response into the Pydantic model
        try:
            if not result.message.content:
                print(
                    f"DEBUG: Empty response from native Ollama for {response_model.__name__}, returning default"
                )
                return response_model()

            response_json = json.loads(result.message.content)
            print(f"DEBUG: Parsed JSON for {response_model.__name__}: {response_json}")

            validated_response = response_model(**response_json)
            print(
                f"DEBUG: Successfully validated {response_model.__name__}: {validated_response}"
            )
            return validated_response

        except (json.JSONDecodeError, ValueError) as e:
            print(f"DEBUG: JSON parsing failed for {response_model.__name__}: {e}")
            print(f"DEBUG: Raw content was: {result.message.content}")
            self._handle_error(e, "structured_chat_completion")
            # Return empty model if parsing fails
            return response_model()
        except Exception as e:
            print(f"DEBUG: Validation failed for {response_model.__name__}: {e}")
            print(f"DEBUG: Parsed JSON was: {response_json}")
            self._handle_error(e, "structured_chat_completion")
            return response_model()

    async def _get_provider_chat_completion(self, **kwargs) -> CompletionResponse:
        try:
            if not kwargs.get("model"):
                kwargs["model"] = self.model

                # Use universal tool calling compatibility system
            tools = kwargs.get("tools", [])

            use_native_tools, manual_tool_calls = (
                await self._handle_tool_calling_compatibility(**kwargs)
            )
            # If we have manual tool calls, return them immediately
            if manual_tool_calls:
                return CompletionResponse(
                    message=CompletionMessage(
                        content="",
                        role="assistant",
                        tool_calls=manual_tool_calls,
                    ),
                    model=self.model,
                    done=True,
                    done_reason=None,
                    prompt_tokens=0,
                    completion_tokens=0,
                    prompt_eval_duration=0,
                    load_duration=0,
                    total_duration=0,
                    created_at=str(time.time()),
                )

            # Use native tool calling if supported
            # Convert OpenAI-style options to Ollama-native format
            merged_options = {**DEFAULT_OPTIONS, **(kwargs.get("options", {}))}
            native_options = self.get_native_params(merged_options)

            result = await self.client.chat(
                model=kwargs["model"],
                messages=kwargs["messages"],
                stream=kwargs["stream"] if kwargs.get("stream") else False,
                tools=tools if use_native_tools else [],
                format=kwargs["format"] if kwargs.get("format") else None,
                options=native_options,
            )

            message = CompletionMessage(
                content=result.message.content or "",
                thinking=result.message.thinking,
                role=result.message.role or "assistant",
                tool_calls=(
                    [tool_call.model_dump() for tool_call in result.message.tool_calls]
                    if result.message.tool_calls
                    else None
                ),
            )

            return CompletionResponse(
                message=self.extract_and_store_thinking(
                    message, call_context="chat_completion"
                ),
                model=result.model or self.model,
                done=result.done or False,
                done_reason=result.done_reason,
                prompt_tokens=int(result.prompt_eval_count or 0),
                completion_tokens=int(result.eval_count or 0),
                prompt_eval_duration=result.eval_duration,
                load_duration=result.load_duration,
                total_duration=result.total_duration,
                created_at=result.created_at,
            )
        except Exception as e:
            self._handle_error(e, "chat_completion")
            # This line will never be reached due to _handle_error raising the exception
            # But we need it for type checking
            raise

    async def _stream_provider_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion tokens from Ollama.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions
            options: Model-specific options
            **kwargs: Additional arguments

        Yields:
            StreamChunk objects containing content and metadata
        """
        try:
            # Handle tool calling compatibility
            use_native_tools, manual_tool_calls = (
                await self._handle_tool_calling_compatibility(
                    messages=messages, tools=tools, **kwargs
                )
            )

            # If we have manual tool calls, yield them and return
            if manual_tool_calls:
                yield StreamChunk(
                    content="",
                    role="assistant",
                    tool_calls=manual_tool_calls,
                    is_final=True,
                    model=self.model,
                )
                return

            # Convert OpenAI-style options to Ollama-native format
            merged_options = {**DEFAULT_OPTIONS, **(options or {})}
            native_options = self.get_native_params(merged_options)

            chunk_index = 0
            accumulated_content = ""
            accumulated_thinking = ""
            accumulated_tool_calls: list[dict] = []

            # Stream from Ollama
            async for chunk in await self.client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                tools=tools if use_native_tools else [],
                options=native_options,
            ):
                content = chunk.message.content or ""
                thinking = chunk.message.thinking or ""
                accumulated_content += content
                accumulated_thinking += thinking

                # Handle tool calls in streaming
                if chunk.message.tool_calls:
                    for tool_call in chunk.message.tool_calls:
                        accumulated_tool_calls.append(tool_call.model_dump())

                # Check if this is the final chunk
                is_final = chunk.done or False

                # Build the stream chunk
                stream_chunk = StreamChunk(
                    content=content,
                    role=chunk.message.role or "assistant",
                    finish_reason=chunk.done_reason if is_final else None,
                    tool_calls=accumulated_tool_calls if is_final and accumulated_tool_calls else None,
                    is_final=is_final,
                    chunk_index=chunk_index,
                    model=chunk.model or self.model,
                )

                # Add token usage on final chunk
                if is_final:
                    stream_chunk.prompt_tokens = int(chunk.prompt_eval_count or 0)
                    stream_chunk.completion_tokens = int(chunk.eval_count or 0)
                    stream_chunk.total_tokens = (
                        stream_chunk.prompt_tokens + stream_chunk.completion_tokens
                    )

                yield stream_chunk
                chunk_index += 1

        except Exception as e:
            self._handle_error(e, "stream_chat_completion")
            raise

    async def _get_provider_completion(self, **kwargs) -> CompletionResponse:
        try:
            if not kwargs.get("model"):
                kwargs["model"] = self.model

            # Convert OpenAI-style options to Ollama-native format
            merged_options = {**DEFAULT_OPTIONS, **(kwargs.get("options", {}))}
            native_options = self.get_native_params(merged_options)
            kwargs["options"] = native_options

            completion = await self.client.generate(**kwargs)
            message = CompletionMessage(
                content=completion.response,
                thinking=completion.thinking,
            )
            return CompletionResponse(
                message=self.extract_and_store_thinking(
                    message, call_context="completion"
                ),
                model=completion.model or self.model,
                done=completion.done or False,
                done_reason=completion.done_reason,
                prompt_tokens=completion.prompt_eval_count,
                completion_tokens=completion.eval_count,
                prompt_eval_duration=completion.eval_duration,
                load_duration=completion.load_duration,
                total_duration=completion.total_duration,
                created_at=completion.created_at,
            )
        except Exception as e:
            self._handle_error(e, "completion")
            # This line will never be reached due to _handle_error raising the exception
            # But we need it for type checking
            raise
