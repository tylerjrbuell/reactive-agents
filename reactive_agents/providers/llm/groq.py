import os
import time
import re
from typing import Type, Optional, Dict, Any, List, cast, Union, AsyncIterator
from groq import BadRequestError, Groq, InternalServerError, Stream
from groq.types.chat import ChatCompletion, ChatCompletionChunk
from groq.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pydantic import BaseModel
import instructor
import json

from .base import BaseModelProvider, CompletionMessage, CompletionResponse, StreamChunk


class GroqModelProvider(BaseModelProvider):
    id = "groq"

    def __init__(
        self, model="llama3-groq-70b-8192-tool-use-preview", options=None, context=None
    ):
        # Call parent __init__ first for consistency
        super().__init__(model=model, options=options, context=context)

        # Initialize Groq client
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")

        self.client = Groq(api_key=api_key)

        # Initialize instructor client for structured outputs
        try:
            self.instructor_client = instructor.from_groq(self.client)
            self._supports_structured = True
        except Exception as e:
            if context and hasattr(context, "agent_logger") and context.agent_logger:
                context.agent_logger.warning(
                    f"Failed to initialize Instructor client for Groq: {e}"
                )
            self.instructor_client = None
            self._supports_structured = False

        # Default options
        self.default_options = {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
        }

        # Tool calling configuration
        self.tool_calling_config = {
            "max_retries": 2,
            "fallback_to_text": True,
            "validate_tool_calls": True,
            "strict_tool_format": False,  # Groq models are less strict
        }

        # Validate model after initialization
        self.validate_model()

    def get_native_params(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI-style parameters to Groq-native parameters.

        Maps OpenAI parameter names to Groq's expected parameter names.
        Since Groq uses OpenAI-compatible API, most parameters map directly.

        Args:
            options: OpenAI-style configuration options

        Returns:
            Dictionary with Groq-native parameter names and values
        """
        native_params = {}

        # OpenAI -> Groq parameter mappings (mostly direct since Groq is OpenAI-compatible)
        param_mapping = {
            "temperature": "temperature",  # Direct mapping
            "max_tokens": "max_tokens",  # Groq uses max_tokens (OpenAI-compatible)
            "top_p": "top_p",  # Direct mapping
            "frequency_penalty": "frequency_penalty",  # Direct mapping
            "presence_penalty": "presence_penalty",  # Direct mapping
            "stop": "stop",  # Direct mapping
            "stream": "stream",  # Direct mapping
            "seed": "seed",  # Direct mapping (if supported)
        }

        for openai_param, groq_param in param_mapping.items():
            if openai_param in options:
                native_params[groq_param] = options[openai_param]

        # Handle stop sequences specifically (can be string or list, up to 4 sequences)
        if "stop_sequences" in options:
            stop_sequences = options["stop_sequences"]
            if isinstance(stop_sequences, list):
                # Groq supports up to 4 stop sequences
                native_params["stop"] = stop_sequences[:4]
            else:
                native_params["stop"] = [stop_sequences]

        # Groq-specific parameters that don't have OpenAI equivalents
        groq_specific = {
            "response_format": dict,  # Response format specification
            "tool_choice": str,  # Tool choice preference
            "tools": list,  # Tool definitions (handled separately)
            "user": str,  # User identifier for monitoring
        }

        for param, expected_type in groq_specific.items():
            if param in options:
                try:
                    if expected_type == dict and isinstance(options[param], dict):
                        native_params[param] = options[param]
                    elif expected_type == str:
                        native_params[param] = str(options[param])
                    elif expected_type == list and isinstance(options[param], list):
                        native_params[param] = options[param]
                except (ValueError, TypeError):
                    # Skip invalid parameters
                    continue

        # Note: Groq currently only supports n=1, so we don't include n parameter

        return native_params

    def _clean_message(self, msg: dict):
        allowed = {"role", "content", "name", "tool_call_id"}
        return {k: v for k, v in msg.items() if k in allowed}

    def _validate_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> bool:
        """
        Validate that tool calls have the correct format.

        Args:
            tool_calls: List of tool call dictionaries

        Returns:
            True if all tool calls are valid, False otherwise
        """
        if not tool_calls:
            return True

        for call in tool_calls:
            # Check basic structure
            if not isinstance(call, dict):
                return False

            # Check for required fields
            if "function" not in call:
                return False

            function = call["function"]
            if not isinstance(function, dict):
                return False

            if "name" not in function or "arguments" not in function:
                return False

            # Check arguments format
            args = function["arguments"]
            if isinstance(args, str):
                try:
                    # Try to parse as JSON
                    json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    return False
            elif not isinstance(args, dict):
                return False

        return True

    def _extract_tool_calls_from_text(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract tool calls from malformed text content.

        This handles cases where Groq generates tool calls in invalid formats
        like <function=name{args}></function> or similar patterns.

        Args:
            content: The text content that may contain malformed tool calls

        Returns:
            List of properly formatted tool call dictionaries
        """
        if not content:
            return []

        tool_calls = []

        # Pattern 1: <function=name{args}></function>
        pattern1 = r"<function=([^>]+)></function>"
        matches1 = re.findall(pattern1, content)

        for match in matches1:
            # Try to extract function name and arguments
            if "{" in match and "}" in match:
                name_start = match.find("{")
                func_name = match[:name_start].strip()
                args_str = match[name_start + 1 : match.rfind("}")]

                try:
                    # Try to parse arguments as JSON
                    args = json.loads(args_str)
                except (json.JSONDecodeError, TypeError):
                    # If JSON parsing fails, create a basic structure
                    args = {"raw_args": args_str}

                tool_calls.append(
                    {
                        "id": f"extracted_{len(tool_calls)}",
                        "type": "function",
                        "function": {"name": func_name, "arguments": args},
                    }
                )
            else:
                # Just function name without arguments
                tool_calls.append(
                    {
                        "id": f"extracted_{len(tool_calls)}",
                        "type": "function",
                        "function": {"name": match.strip(), "arguments": {}},
                    }
                )

        # Pattern 2: function_name(args) - basic function call format
        pattern2 = r"(\w+)\s*\(([^)]*)\)"
        matches2 = re.findall(pattern2, content)

        for func_name, args_str in matches2:
            args_str = args_str.strip()
            if args_str:
                try:
                    # Try to parse as JSON-like arguments
                    args = json.loads(args_str)
                except (json.JSONDecodeError, TypeError):
                    # Create basic structure for malformed args
                    args = {"raw_args": args_str}
            else:
                args = {}

            tool_calls.append(
                {
                    "id": f"extracted_{len(tool_calls)}",
                    "type": "function",
                    "function": {"name": func_name.strip(), "arguments": args},
                }
            )

        return tool_calls

    def _process_tool_calls(self, tool_calls):
        """Process tool calls to ensure arguments are properly formatted as dictionaries with correct types."""
        if not tool_calls:
            return None

        processed_calls = []
        for call in tool_calls:
            call_dict = call.model_dump() if hasattr(call, "model_dump") else dict(call)

            # Ensure function arguments are dictionaries, not JSON strings
            if "function" in call_dict and "arguments" in call_dict["function"]:
                args = call_dict["function"]["arguments"]
                if isinstance(args, str):
                    try:
                        call_dict["function"]["arguments"] = (
                            json.loads(args) if args else {}
                        )
                    except (json.JSONDecodeError, TypeError):
                        call_dict["function"]["arguments"] = {}
                elif not isinstance(args, dict):
                    call_dict["function"]["arguments"] = {}

                # Now process the arguments to fix type mismatches
                if isinstance(call_dict["function"]["arguments"], dict):
                    call_dict["function"]["arguments"] = self._fix_argument_types(
                        call_dict["function"]["arguments"]
                    )

            processed_calls.append(call_dict)

        return processed_calls

    def _fix_argument_types(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix argument types to match expected schema requirements.

        This handles common type mismatches like strings for integers, booleans, etc.

        Args:
            arguments: The arguments dictionary

        Returns:
            Arguments with corrected types
        """
        if not arguments:
            return arguments

        fixed_args = {}

        for key, value in arguments.items():
            if value is None:
                fixed_args[key] = None
                continue

            # Common type conversions based on parameter names and values
            if key in [
                "max_results",
                "max_output_tokens",
                "max_tokens",
                "limit",
                "count",
                "size",
            ]:
                # These should be integers
                try:
                    fixed_args[key] = int(value)
                except (ValueError, TypeError):
                    # If conversion fails, try to extract number from string
                    if isinstance(value, str):
                        import re

                        number_match = re.search(r"\d+", value)
                        if number_match:
                            fixed_args[key] = int(number_match.group())
                        else:
                            fixed_args[key] = 0  # Default fallback
                    else:
                        fixed_args[key] = 0

            elif key in [
                "temperature",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
                "top_k",
            ]:
                # These should be floats
                try:
                    fixed_args[key] = float(value)
                except (ValueError, TypeError):
                    fixed_args[key] = 0.0  # Default fallback

            elif key in ["enabled", "active", "force", "strict"]:
                # These should be booleans
                if isinstance(value, str):
                    fixed_args[key] = value.lower() in ["true", "1", "yes", "on"]
                else:
                    fixed_args[key] = bool(value)

            elif key in [
                "query",
                "message",
                "content",
                "text",
                "description",
                "name",
                "email",
                "subject",
                "body",
            ]:
                # These should be strings
                fixed_args[key] = str(value) if value is not None else ""

            else:
                # For unknown parameters, try to preserve the original value
                # but ensure it's a basic type
                if isinstance(value, (str, int, float, bool)):
                    fixed_args[key] = value
                else:
                    fixed_args[key] = str(value)

        return fixed_args

    def _create_fallback_response(
        self, messages: List[dict], native_options: Dict[str, Any]
    ) -> CompletionResponse:
        """
        Create a fallback response when tool calling fails.

        Args:
            messages: The original messages
            native_options: Native Groq options

        Returns:
            CompletionResponse with fallback content
        """
        try:
            # Try to get a basic text response without tools
            fallback_completion = self.client.chat.completions.create(
                model=self.model,
                messages=cast(List[ChatCompletionMessageParam], messages),
                tools=None,  # Disable tools for fallback
                tool_choice="none",
                **native_options,
            )

            if isinstance(fallback_completion, ChatCompletion):
                result = fallback_completion.choices[0]
                message = CompletionMessage(
                    content=(
                        result.message.content
                        if result.message.content
                        else "[Model failed to generate tool calls, provided fallback response]"
                    ),
                    role=(result.message.role if result.message.role else "assistant"),
                    thinking="False",
                    tool_calls=None,
                )
                return CompletionResponse(
                    message=self.extract_and_store_thinking(
                        message, call_context="chat_completion"
                    ),
                    model=fallback_completion.model or self.model,
                    done=True,
                    done_reason=result.finish_reason or None,
                    prompt_tokens=(
                        int(fallback_completion.usage.prompt_tokens or 0)
                        if fallback_completion.usage
                        else 0
                    ),
                    completion_tokens=(
                        int(fallback_completion.usage.completion_tokens)
                        if fallback_completion.usage
                        else 0
                    ),
                    prompt_eval_duration=(
                        int(fallback_completion.usage.prompt_time or 0)
                        if fallback_completion.usage
                        else 0
                    ),
                    load_duration=(
                        int(fallback_completion.usage.completion_time or 0)
                        if fallback_completion.usage
                        else 0
                    ),
                    total_duration=(
                        int(fallback_completion.usage.total_time or 0)
                        if fallback_completion.usage
                        else 0
                    ),
                    created_at=(
                        str(fallback_completion.created)
                        if fallback_completion.created
                        else None
                    ),
                )
            else:
                # If not a ChatCompletion, create error response
                error_message = CompletionMessage(
                    content="[Unexpected completion type from fallback]",
                    role="assistant",
                    thinking="False",
                    tool_calls=None,
                )

                return CompletionResponse(
                    message=self.extract_and_store_thinking(
                        error_message, call_context="chat_completion"
                    ),
                    model=self.model,
                    done=True,
                    done_reason="error",
                    prompt_tokens=0,
                    completion_tokens=0,
                    prompt_eval_duration=0,
                    load_duration=0,
                    total_duration=0,
                    created_at=str(time.time()),
                )
        except Exception as fallback_error:
            # If fallback also fails, create a minimal error response
            if (
                self.context
                and hasattr(self.context, "agent_logger")
                and self.context.agent_logger
            ):
                self.context.agent_logger.error(
                    f"Groq fallback completion failed: {fallback_error}"
                )

            # Create minimal error response
            error_message = CompletionMessage(
                content="[Tool calling failed and fallback unavailable. Please try again or use a different approach.]",
                role="assistant",
                thinking="False",
                tool_calls=None,
            )

            return CompletionResponse(
                message=self.extract_and_store_thinking(
                    error_message, call_context="chat_completion"
                ),
                model=self.model,
                done=True,
                done_reason="error",
                prompt_tokens=0,
                completion_tokens=0,
                prompt_eval_duration=0,
                load_duration=0,
                total_duration=0,
                created_at=str(time.time()),
            )

    def validate_model(self, **kwargs) -> dict:
        """Validate that the model is supported by Groq."""
        try:
            supported_models = self.client.models.list().model_dump().get("data", [])
            available_models = [m.get("id") for m in supported_models]

            if self.model not in available_models:
                raise ValueError(
                    f"Model '{self.model}' is not supported by Groq. "
                    f"Available models: {', '.join(available_models[:10])}..."
                )

            return {"valid": True, "model": self.model}
        except Exception as e:
            self._handle_error(e, "validation")
            return {"valid": False, "error": str(e)}

    def _supports_native_tool_calling(self, model: str) -> bool:
        """
        Check if the Groq model supports native tool calling.

        Most models on Groq support tool calling, but some older or
        specialized models may not.

        Args:
            model: Optional model name to check (defaults to self.model)

        Returns:
            True if model supports native tool calling, False otherwise
        """
        model_to_check = model or self.model

        # Models known to NOT support tool calling
        non_tool_calling_models = {
            "whisper-large-v3",  # Audio transcription model
            "distil-whisper-large-v3-en",  # Audio transcription model
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
        Execute structured chat completion using Instructor for Groq.

        Args:
            response_model: The Pydantic model class
            messages: List of message dictionaries
            options: Provider-specific options
            **kwargs: Additional arguments

        Returns:
            An instance of the response_model
        """
        if not self.instructor_client:
            raise RuntimeError("Instructor client not initialized for Groq provider")

        try:
            # Clean messages for Groq
            cleaned_messages = [self._clean_message(msg) for msg in messages]

            # Merge options
            merged_options = options or {}

            # Get OpenAI-style parameters for Instructor (filters out Groq-specific params)
            openai_params = self.get_openai_params(merged_options)

            # Prepare API call parameters for instructor
            api_params = {
                "model": self.model,
                "messages": cleaned_messages,
                "response_model": response_model,
                **openai_params,
            }

            # Use instructor client for structured response
            structured_response = await self._call_instructor_client(
                "chat.completions.create", **api_params
            )

            return structured_response

        except Exception as e:
            self._handle_error(e, "structured_chat_completion")
            raise Exception(f"Groq Structured Chat Completion Error: {str(e)}")

    def _adapt_context_for_provider(
        self, messages: list, tools: list | None = None
    ) -> list:
        """
        Adapt context for Groq's specific requirements and best practices.

        Since tool context is now centralized in base strategy system messages,
        this method focuses on Groq-specific optimizations only.

        Groq Adaptations:
        - Preserve all agent context (role, instructions, task, tools)
        - Follow Groq's recommendation for clear completion signals
        """
        if not tools:
            return messages

        adapted_messages = messages.copy()

        # Add minimal completion guidance to existing system message (preserves agent context)
        # This helps Groq models understand when to finish tasks properly
        completion_hint = "\n\nIMPORTANT: After using the required tools, you MUST call 'final_answer' to complete your response."

        system_message_found = False
        for i in range(len(adapted_messages)):
            if adapted_messages[i].get("role") == "system":
                original_content = adapted_messages[i].get("content", "")
                adapted_messages[i] = {
                    **adapted_messages[i],
                    "content": original_content + completion_hint,
                }
                system_message_found = True
                break

        # Only add minimal system message if none exists (rare in framework)
        if not system_message_found:
            minimal_system_msg = {
                "role": "system",
                "content": f"Use tools to complete tasks, then MUST call 'final_answer' to finish.{completion_hint}",
            }
            adapted_messages.insert(0, minimal_system_msg)

        return adapted_messages

    async def _get_provider_chat_completion(self, **kwargs):
        messages = kwargs.get("messages", [])
        stream = kwargs.get("stream", False)
        tools = kwargs.get("tools")
        options = kwargs.get("options")
        format = kwargs.get("format", "")

        try:
            messages = [self._clean_message(m) for m in messages]

            # Adapt context for Groq's requirements (preserves agent context)
            if tools:
                messages = self._adapt_context_for_provider(messages, tools)

            # Convert OpenAI-style parameters to Groq-native format
            native_options = self.get_native_params(options or {})

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=cast(List[ChatCompletionMessageParam], messages),
                tools=tools if tools else None,
                response_format=(
                    {"type": "json_object"} if format == "json" else {"type": "text"}
                ),
                tool_choice=(
                    # Groq models struggle with "required" - use "auto" instead
                    "auto"
                    if tools
                    else "none"
                ),
                **native_options,
            )
            if stream:
                return completion

            if isinstance(completion, ChatCompletion):
                result = completion.choices[0]
                message = CompletionMessage(
                    content=result.message.content if result.message.content else "",
                    role=result.message.role if result.message.role else "assistant",
                    thinking="False",
                    tool_calls=(
                        self._process_tool_calls(result.message.tool_calls)
                        if result.message.tool_calls
                        else None
                    ),
                )
                return CompletionResponse(
                    message=self.extract_and_store_thinking(
                        message, call_context="chat_completion"
                    ),
                    model=completion.model or self.model,
                    done=True,
                    done_reason=result.finish_reason or None,
                    prompt_tokens=(
                        int(completion.usage.prompt_tokens or 0)
                        if completion.usage
                        else 0
                    ),
                    completion_tokens=(
                        int(completion.usage.completion_tokens)
                        if completion.usage
                        else 0
                    ),
                    prompt_eval_duration=(
                        int(completion.usage.prompt_time or 0)
                        if completion.usage
                        else 0
                    ),
                    load_duration=(
                        int(completion.usage.completion_time or 0)
                        if completion.usage
                        else 0
                    ),
                    total_duration=(
                        int(completion.usage.total_time or 0) if completion.usage else 0
                    ),
                    created_at=(
                        str(completion.created) if completion.created else None
                    ),
                )
            else:
                raise Exception("Unexpected completion type")
        except InternalServerError as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"Groq Internal Server Error: {e.message}")
        except BadRequestError as e:
            # Handle tool_use_failed gracefully but still use proper error handling
            error_data = getattr(e, "response", None)
            if error_data and hasattr(error_data, "json"):
                error_json = error_data.json()
                if (
                    isinstance(error_json, dict)
                    and error_json.get("error", {}).get("code") == "tool_use_failed"
                ):
                    # For tool_use_failed, try to provide a fallback response without tools
                    tool_error = error_json["error"].get("failed_generation", "")

                    # If failed_generation is empty, the model couldn't generate tool calls properly
                    if not tool_error.strip():
                        # Retry without tools to get a basic response
                        try:
                            fallback_completion = self.client.chat.completions.create(
                                model=self.model,
                                messages=cast(
                                    List[ChatCompletionMessageParam], messages
                                ),  # messages are already cleaned at this point
                                tools=None,  # Disable tools for fallback
                                tool_choice="none",
                                **native_options,
                            )

                            if isinstance(fallback_completion, ChatCompletion):
                                result = fallback_completion.choices[0]
                                message = CompletionMessage(
                                    content=(
                                        result.message.content
                                        if result.message.content
                                        else "[Model failed to generate tool calls, provided fallback response]"
                                    ),
                                    role=(
                                        result.message.role
                                        if result.message.role
                                        else "assistant"
                                    ),
                                    thinking="False",
                                    tool_calls=None,
                                )
                                return CompletionResponse(
                                    message=self.extract_and_store_thinking(
                                        message, call_context="chat_completion"
                                    ),
                                    model=fallback_completion.model or self.model,
                                    done=True,
                                    done_reason=result.finish_reason or None,
                                    prompt_tokens=(
                                        int(
                                            fallback_completion.usage.prompt_tokens or 0
                                        )
                                        if fallback_completion.usage
                                        else 0
                                    ),
                                    completion_tokens=(
                                        int(fallback_completion.usage.completion_tokens)
                                        if fallback_completion.usage
                                        else 0
                                    ),
                                    prompt_eval_duration=(
                                        int(fallback_completion.usage.prompt_time or 0)
                                        if fallback_completion.usage
                                        else 0
                                    ),
                                    load_duration=(
                                        int(
                                            fallback_completion.usage.completion_time
                                            or 0
                                        )
                                        if fallback_completion.usage
                                        else 0
                                    ),
                                    total_duration=(
                                        int(fallback_completion.usage.total_time or 0)
                                        if fallback_completion.usage
                                        else 0
                                    ),
                                    created_at=(
                                        str(fallback_completion.created)
                                        if fallback_completion.created
                                        else None
                                    ),
                                )
                        except Exception as fallback_error:
                            # If fallback also fails, log both errors
                            self._handle_error(e, "chat_completion")
                            self._handle_error(
                                fallback_error, "chat_completion_fallback"
                            )
                            raise Exception(
                                f"Groq Tool Use Failed and Fallback Failed: {str(e)} | Fallback: {str(fallback_error)}"
                            )

                    # Try to extract tool calls from the malformed text
                    if tool_error and self.tool_calling_config["fallback_to_text"]:
                        extracted_tool_calls = self._extract_tool_calls_from_text(
                            tool_error
                        )

                        if extracted_tool_calls:
                            # Successfully extracted tool calls, create response
                            if (
                                self.context
                                and hasattr(self.context, "agent_logger")
                                and self.context.agent_logger
                            ):
                                self.context.agent_logger.info(
                                    f"Successfully extracted {len(extracted_tool_calls)} tool calls from malformed text"
                                )

                            # Process the extracted tool calls with type fixing
                            processed_tool_calls = (
                                self._process_tool_calls(extracted_tool_calls) or []
                            )

                            # Additional validation: ensure all tool calls have valid arguments
                            validated_tool_calls = []
                            for call in processed_tool_calls:
                                if call.get("function", {}).get("arguments") is None:
                                    # Fix None arguments to empty dict
                                    call["function"]["arguments"] = {}
                                validated_tool_calls.append(call)

                            message = CompletionMessage(
                                content="[Tool calls extracted from malformed response]",
                                role="assistant",
                                thinking="False",
                                tool_calls=validated_tool_calls,
                            )

                            return CompletionResponse(
                                message=self.extract_and_store_thinking(
                                    message, call_context="chat_completion"
                                ),
                                model=self.model,
                                done=True,
                                done_reason="tool_calls",
                                prompt_tokens=0,  # Unknown for extracted calls
                                completion_tokens=0,
                                prompt_eval_duration=0,
                                load_duration=0,
                                total_duration=0,
                                created_at=str(time.time()),
                            )

                    # If extraction failed or not enabled, try fallback response
                    if self.tool_calling_config["fallback_to_text"]:
                        if (
                            self.context
                            and hasattr(self.context, "agent_logger")
                            and self.context.agent_logger
                        ):
                            self.context.agent_logger.info(
                                "Attempting fallback response without tools"
                            )

                        return self._create_fallback_response(
                            messages, native_options or {}
                        )

                    # If no fallback, report the error
                    self._handle_error(e, "chat_completion")
                    raise Exception(f"Groq Tool Use Failed: {tool_error}")

            self._handle_error(e, "chat_completion")
            raise Exception(f"Groq Bad Request Error: {e.message}")
        except Exception as e:
            self._handle_error(e, "chat_completion")
            raise Exception(f"Groq Chat Completion Error: {e}")

    async def _stream_provider_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion tokens from Groq.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions
            options: Model-specific options
            **kwargs: Additional arguments

        Yields:
            StreamChunk objects containing content and metadata
        """
        try:
            # Clean messages for Groq
            cleaned_messages = [self._clean_message(m) for m in messages]

            # Adapt context for Groq's requirements
            if tools:
                cleaned_messages = self._adapt_context_for_provider(cleaned_messages, tools)

            # Convert OpenAI-style parameters to Groq-native format
            native_options = self.get_native_params(options or {})

            chunk_index = 0
            accumulated_content = ""
            accumulated_tool_calls: list[dict] = []
            current_tool_calls: dict[int, dict] = {}

            # Stream from Groq
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=cast(List[ChatCompletionMessageParam], cleaned_messages),
                tools=tools if tools else None,
                stream=True,
                tool_choice="auto" if tools else "none",
                **native_options,
            )

            for chunk in stream:
                if not isinstance(chunk, ChatCompletionChunk):
                    continue

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Get content if present
                content = delta.content or ""
                accumulated_content += content

                # Handle tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc.id or f"call_{idx}",
                                "type": "function",
                                "function": {
                                    "name": tc.function.name if tc.function else "",
                                    "arguments": "",
                                },
                            }
                        else:
                            # Accumulate function arguments
                            if tc.function and tc.function.arguments:
                                current_tool_calls[idx]["function"]["arguments"] += tc.function.arguments
                            # Update name if provided
                            if tc.function and tc.function.name:
                                current_tool_calls[idx]["function"]["name"] = tc.function.name

                # Check if this is the final chunk
                is_final = choice.finish_reason is not None

                # On final chunk, process tool calls
                if is_final and current_tool_calls:
                    for idx in sorted(current_tool_calls.keys()):
                        tc = current_tool_calls[idx]
                        # Parse arguments JSON
                        try:
                            args_str = tc["function"]["arguments"]
                            if args_str:
                                tc["function"]["arguments"] = json.loads(args_str)
                        except json.JSONDecodeError:
                            tc["function"]["arguments"] = {}
                        accumulated_tool_calls.append(tc)

                # Build stream chunk
                stream_chunk = StreamChunk(
                    content=content,
                    role="assistant",
                    finish_reason=choice.finish_reason if is_final else None,
                    tool_calls=accumulated_tool_calls if is_final and accumulated_tool_calls else None,
                    is_final=is_final,
                    chunk_index=chunk_index,
                    model=chunk.model or self.model,
                )

                # Add token usage on final chunk if available
                if is_final and hasattr(chunk, "x_groq") and chunk.x_groq:
                    usage = getattr(chunk.x_groq, "usage", None)
                    if usage:
                        stream_chunk.prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                        stream_chunk.completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                        stream_chunk.total_tokens = stream_chunk.prompt_tokens + stream_chunk.completion_tokens

                yield stream_chunk
                chunk_index += 1

        except InternalServerError as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"Groq Internal Server Error: {e.message}")
        except BadRequestError as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"Groq Bad Request Error: {e.message}")
        except Exception as e:
            self._handle_error(e, "stream_chat_completion")
            raise Exception(f"Groq Stream Chat Completion Error: {e}")

    async def _get_provider_completion(self, **kwargs) -> CompletionResponse:
        try:
            # Build messages for consistency with other providers
            messages = []
            if kwargs.get("system"):
                messages.append({"role": "system", "content": kwargs["system"]})
            messages.append({"role": "user", "content": kwargs.get("prompt", "")})

            # Use chat completion for text completion (like other providers)
            return await self._get_provider_chat_completion(
                messages=messages,
                tools=kwargs.get("tools"),
                format=kwargs.get("format", ""),
                options=kwargs.get("options"),
            )

        except Exception as e:
            self._handle_error(e, "completion")
            raise Exception(f"Groq Completion Error: {e}")
