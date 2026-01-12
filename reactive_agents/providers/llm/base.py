from __future__ import annotations
from abc import ABC, ABCMeta, abstractmethod
from typing import List, Optional, Type, Dict, Any, Union, TYPE_CHECKING, AsyncIterator
import traceback
import time

# Import provider types from centralized location
from reactive_agents.core.types.provider_types import (
    CompletionMessage,
    CompletionResponse,
    ModelInfo,
    ProviderStatus,
    ProviderHealth,
    StreamChunk,
)

# Import for structured outputs
from pydantic import BaseModel

from reactive_agents.core.types.status_types import TaskStatus
from reactive_agents.core.types.event_types import AgentStateEvent

if TYPE_CHECKING:
    from reactive_agents.core.context.agent_context import AgentContext


# Dictionary to store registered model providers
model_providers: Dict[str, Type["BaseModelProvider"]] = {}


class AutoRegisterModelMeta(ABCMeta):
    """Metaclass for auto-registering model providers."""

    def __init__(cls, name: str, bases: tuple, attrs: dict):
        super().__init__(name, bases, attrs)
        if name != "BaseModelProvider":
            BaseModelProvider.register_provider(cls)


class BaseModelProvider(ABC, metaclass=AutoRegisterModelMeta):
    """Base class for model providers."""

    _providers: Dict[str, Type["BaseModelProvider"]] = {}

    @classmethod
    def register_provider(cls, provider_class: Type["BaseModelProvider"]) -> None:
        """Register a model provider class."""
        provider_name = provider_class.__name__.replace("ModelProvider", "").lower()
        cls._providers[provider_name] = provider_class

    def __init__(
        self,
        model: str,
        options: Optional[Dict[str, Any]] = None,
        context: Optional["AgentContext"] = None,
    ):
        """
        Initialize the model provider.

        Args:
            model: The model to use
            options: Optional configuration options
            context: The agent context for error tracking and logging
        """
        self.model = model
        self.options = options or {}
        self.context = context
        self.name = self.__class__.__name__.replace("ModelProvider", "").lower()

        # Structured output support
        self.instructor_client = None
        self._supports_structured = True

        # Track dropped parameters for debugging
        self._dropped_params: List[str] = []

    def _warn_parameter(self, message: str, level: str = "warning") -> None:
        """
        Log a parameter-related warning if context and logger are available.

        Args:
            message: Warning message to log
            level: Log level ("warning", "debug", or "info")
        """
        if self.context and hasattr(self.context, "agent_logger") and self.context.agent_logger:
            if level == "warning":
                self.context.agent_logger.warning(message)
            elif level == "debug":
                self.context.agent_logger.debug(message)
            else:
                self.context.agent_logger.info(message)

    def get_openai_params(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract OpenAI-style parameters for Instructor and OpenAI-compatible providers.

        The framework uses OpenAI parameter names as the standard interface.
        This method filters and validates OpenAI-compatible parameters.

        Args:
            options: Configuration options from agent builder

        Returns:
            Dictionary with OpenAI-style parameters for Instructor
        """
        openai_params = {}
        processed_params: set = set()

        # Standard OpenAI parameters that Instructor supports across all providers
        standard_params = {
            "temperature": float,
            "max_tokens": int,
            "top_p": float,
            "frequency_penalty": float,
            "presence_penalty": float,
            "seed": int,
            "stream": bool,
            "n": int,
        }

        # Client configuration params (not passed to API calls, handled by provider __init__)
        client_params = {
            "base_url", "timeout", "max_retries", "default_headers", "default_query",
            "api_key", "organization", "base_delay", "max_delay", "jitter_factor",
            "rate_limit_retry_delay",
        }

        for param, expected_type in standard_params.items():
            if param in options:
                processed_params.add(param)
                try:
                    # Type conversion and validation
                    if expected_type == float:
                        openai_params[param] = float(options[param])
                    elif expected_type == int:
                        openai_params[param] = int(options[param])
                    elif expected_type == bool:
                        openai_params[param] = bool(options[param])
                    else:
                        openai_params[param] = options[param]
                except (ValueError, TypeError) as e:
                    # Warn about type conversion failures
                    self._warn_parameter(
                        f"[{self.name}] Parameter '{param}' has invalid type: "
                        f"expected {expected_type.__name__}, got {type(options[param]).__name__}. "
                        f"Parameter will be dropped. Error: {e}"
                    )
                    self._dropped_params.append(param)

        # Handle stop sequences (can be string or list)
        if "stop" in options:
            openai_params["stop"] = options["stop"]
            processed_params.add("stop")
        elif "stop_sequences" in options:
            openai_params["stop"] = options["stop_sequences"]
            processed_params.add("stop_sequences")

        # Warn about unrecognized parameters (excluding known client params)
        for param in options:
            if param not in processed_params and param not in client_params:
                self._warn_parameter(
                    f"[{self.name}] Unrecognized parameter '{param}' will be ignored. "
                    f"Supported API parameters: {', '.join(sorted(standard_params.keys()))}",
                    level="warning"
                )
                self._dropped_params.append(param)

        return openai_params

    def get_native_params(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI-style options to provider-native parameters for fallback scenarios.

        This method should be overridden by each provider to map OpenAI parameters
        to their specific API format when falling back to native SDK calls.

        Args:
            options: OpenAI-style configuration options

        Returns:
            Dictionary with provider-native parameter names and values
        """
        # Default implementation returns OpenAI params as-is
        # (works for OpenAI and OpenAI-compatible providers)
        return self.get_openai_params(options)

    def get_dropped_params(self) -> List[str]:
        """
        Get list of parameters that were dropped during configuration.

        Returns:
            List of parameter names that were dropped (due to type errors or being unrecognized)
        """
        return self._dropped_params.copy()

    def report_configuration_summary(self) -> None:
        """
        Log a summary of the provider configuration, including any dropped parameters.

        This is useful for debugging configuration issues.
        """
        if not self._dropped_params:
            self._warn_parameter(
                f"[{self.name}] All configuration parameters validated successfully.",
                level="debug"
            )
        else:
            self._warn_parameter(
                f"[{self.name}] Configuration summary: {len(self._dropped_params)} parameter(s) "
                f"were dropped: {', '.join(self._dropped_params)}",
                level="warning"
            )

    def _handle_error(self, error: Exception, operation: str) -> None:
        """
        Centralized error handling for model provider operations.

        Args:
            error: The exception that occurred
            operation: The operation that failed (e.g., 'completion', 'chat_completion', 'validation')
        """
        if not self.context:
            raise error  # If no context, just raise the error

        error_data = {
            "error": str(error),
            "traceback": traceback.format_exc(),
            "timestamp": time.time(),
            "error_type": "critical",
            "component": "model_provider",
            "operation": operation,
            "provider": self.name,
            "model": self.model,
        }

        # Add to errors list
        if hasattr(self.context, "session") and self.context.session:
            self.context.session.errors.append(error_data)
            self.context.session.error = str(error)
            self.context.session.task_status = TaskStatus.ERROR

        # Log the error
        if hasattr(self.context, "agent_logger") and self.context.agent_logger:
            self.context.agent_logger.error(
                f"Model provider error during {operation}: {error}\n{traceback.format_exc()}"
            )

        # Emit error event
        if hasattr(self.context, "emit_event"):
            self.context.emit_event(
                AgentStateEvent.ERROR_OCCURRED,
                {
                    "error": f"Model provider {operation} error",
                    "details": str(error),
                    "provider": self.name,
                    "model": self.model,
                    "is_critical": True,
                },
            )

        raise error  # Re-raise the error after handling

    def _adapt_context_for_provider(
        self, messages: List[dict], tools: Optional[List[dict]] = None
    ) -> List[dict]:
        """
        Provider-specific context adaptation hook.

        This method allows providers to adapt agent context to fit their specific
        SDK requirements and best practices without corrupting the agent's core context.

        Design Principles:
        - PRESERVE: Never replace agent role, instructions, or task context
        - ADAPT: Modify format/structure to fit provider requirements
        - MINIMAL: Keep adaptations focused and lightweight
        - ADDITIVE: Append provider-specific hints when necessary

        Args:
            messages: Original message chain from agent context
            tools: Available tools for the interaction

        Returns:
            Messages adapted for this provider's requirements

        Default implementation returns messages unchanged.
        Providers should override to add specific adaptations.

        Examples of valid adaptations:
        - Message role conversions (tool -> user for OpenAI)
        - Tool format conversions (OpenAI -> Anthropic format)
        - Adding provider-specific system context hints
        - Message ordering adjustments for API requirements

        Examples of INVALID adaptations:
        - Replacing agent role ("coding assistant" -> "helpful assistant")
        - Overriding agent instructions or task context
        - Changing the agent's personality or behavior guidelines
        """
        return messages

    def _supports_native_tool_calling(self, model: str) -> bool:
        """
        Check if the current model supports native tool calling.

        This method should be overridden by providers to implement their specific
        tool calling compatibility checks. The default implementation returns True
        to maintain backward compatibility.

        Args:
            model: Optional model name to check (defaults to self.model)

        Returns:
            True if model supports native tool calling, False otherwise
        """
        return True

    async def _get_manual_tool_calls(
        self, task: str, tools: List[dict], max_calls: int = 1
    ) -> List[dict]:
        """
        Generate tool calls manually for models that don't support native tool calling.

        This enhanced method uses focused tool execution history to make
        more informed tool selection decisions, optimized for token efficiency.

        Args:
            task: The current task description
            tools: Available tool signatures
            max_calls: Maximum number of tool calls to generate

        Returns:
            List of tool call dictionaries
        """
        if not self.context:
            print("No context found")
            return []

        try:
            # Get optimized tool context focused on execution history
            if (
                not self.context
                or not hasattr(self.context, "context_manager")
                or not self.context.context_manager
            ):
                print("No context manager found")
                return []

            tool_context = self.context.context_manager.get_tool_calling_context()

            # Use centralized prompt system with optimized parameters
            result = await self.context.reasoning_engine.get_prompt(
                "tool_selection"
            ).get_completion(
                task=task,
                tool_signatures=tools,
                max_calls=max_calls,
                provider=self.name,
                model=self.model,
                context_summary=tool_context["context_summary"],
                tool_summaries=tool_context["tool_summaries"],  # Structured tool data
            )

            if result and result.result_json:
                tool_calls = result.result_json.get("tool_calls", [])

                # Log optimized tool selection if available
                if hasattr(self.context, "agent_logger") and self.context.agent_logger:
                    self.context.agent_logger.debug(
                        f"Optimized tool selection for {self.name}: "
                        f"Generated {len(tool_calls)} calls using {len(tool_context['tool_summaries'])} tool summaries"
                    )

                return tool_calls

        except Exception as e:
            if hasattr(self.context, "agent_logger") and self.context.agent_logger:
                self.context.agent_logger.warning(
                    f"Optimized manual tool calling failed for {self.name}: {e}"
                )

        return []

    def integrate_tool_result(
        self,
        tool_name: str,
        tool_result: Any,
        tool_call_id: Optional[str] = None,
        execution_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Integrate tool execution results into the context management system.

        This method ensures that tool results are properly stored and made
        available for future context-aware tool calling decisions.

        Args:
            tool_name: Name of the executed tool
            tool_result: Result from tool execution
            tool_call_id: Optional ID of the tool call
            execution_metadata: Optional metadata about the execution
        """
        if not self.context or not hasattr(self.context, "context_manager"):
            return

        # Prepare tool result metadata
        metadata = {
            "tool_name": tool_name,
            "is_tool_result": True,
            "execution_timestamp": time.time(),
            "preserve": True,  # Mark for preservation during context pruning
        }

        if tool_call_id:
            metadata["tool_call_id"] = tool_call_id

        if execution_metadata:
            metadata.update(execution_metadata)

        # Format tool result content
        result_content = self._format_tool_result_content(tool_name, tool_result)

        # Add tool result to context
        if self.context.context_manager:
            self.context.context_manager.add_message(
                role="tool", content=result_content, metadata=metadata
            )

            # Add tool preservation rules if not already added
            self.context.context_manager.add_tool_preservation_rules()

        # Log tool result integration
        if hasattr(self.context, "agent_logger") and self.context.agent_logger:
            self.context.agent_logger.debug(
                f"Integrated tool result for {tool_name}: {str(tool_result)[:100]}..."
            )

    def _format_tool_result_content(self, tool_name: str, tool_result: Any) -> str:
        """
        Format tool result content for storage in context.

        Args:
            tool_name: Name of the tool
            tool_result: Raw tool result

        Returns:
            Formatted content string
        """
        if isinstance(tool_result, dict):
            # Handle structured results
            if "error" in tool_result:
                return f"Tool {tool_name} error: {tool_result['error']}"
            elif "result" in tool_result:
                return f"Tool {tool_name} result: {tool_result['result']}"
            else:
                # Convert dict to readable format
                result_str = ", ".join([f"{k}: {v}" for k, v in tool_result.items()])
                return f"Tool {tool_name} result: {result_str}"
        elif isinstance(tool_result, (list, tuple)):
            # Handle list/tuple results
            return f"Tool {tool_name} result: {len(tool_result)} items - {str(tool_result)[:200]}"
        else:
            # Handle string/primitive results
            return f"Tool {tool_name} result: {str(tool_result)}"

    def track_tool_call_attempt(
        self, tool_calls: List[dict], is_manual: bool = False
    ) -> None:
        """
        Track tool call attempts for context awareness.

        Args:
            tool_calls: List of tool calls being attempted
            is_manual: Whether these are manually generated tool calls
        """
        if not self.context or not hasattr(self.context, "context_manager"):
            return

        # Create tracking metadata
        metadata = {
            "is_tool_call_attempt": True,
            "is_manual_tool_call": is_manual,
            "tool_count": len(tool_calls),
            "attempt_timestamp": time.time(),
            "preserve": True,
        }

        # Format tool call information
        tool_names = [
            call.get("function", {}).get("name", "unknown") for call in tool_calls
        ]
        call_summary = (
            f"Attempting {len(tool_calls)} tool calls: {', '.join(tool_names)}"
        )

        if is_manual:
            call_summary = f"Manual {call_summary}"

        # Add to context
        if self.context.context_manager:
            self.context.context_manager.add_message(
                role="assistant", content=call_summary, metadata=metadata
            )

        # Log tool call tracking
        if hasattr(self.context, "agent_logger") and self.context.agent_logger:
            self.context.agent_logger.debug(
                f"Tracked {'manual' if is_manual else 'native'} tool call attempt: {call_summary}"
            )

    async def _handle_tool_calling_compatibility(
        self, **kwargs
    ) -> tuple[bool, List[dict]]:
        """
        Handle tool calling compatibility by checking native support and falling back to manual.

        This method centralizes the logic for determining whether to use native or manual
        tool calling based on model capabilities.

        Args:
            messages: Message chain
            tools: Available tools
            **kwargs: Additional parameters

        Returns:
            Tuple of (use_native_tools, manual_tool_calls)
            - use_native_tools: Whether to use native tool calling
            - manual_tool_calls: List of manually generated tool calls (empty if using native)
        """
        # Remove tools from kwargs to avoid parameter conflict
        tools = kwargs.get("tools", [])
        messages = kwargs.get("messages", [])
        if not tools:
            return True, []
        # Check if model supports native tool calling
        supports_native = self._supports_native_tool_calling(self.model)

        if supports_native:
            return True, []

        # Generate manual tool calls for non-supporting models
        if (
            self.context
            and hasattr(self.context, "agent_logger")
            and self.context.agent_logger
        ):
            self.context.agent_logger.info(
                f"Model {self.model} doesn't support native tool calling, using manual approach"
            )

        # Extract task from messages
        task = "Complete the user's request"
        for msg in reversed(messages):
            if msg.get("role") == "user":
                task = msg.get("content", task)
                break

        manual_calls = await self._get_manual_tool_calls(task, tools)
        return False, manual_calls

    # --- Structured Output Interface ---
    def _get_instructor_client(self):
        """
        Get the instructor client for this provider.

        Override in each provider to return the configured instructor client.

        Returns:
            The instructor client instance or None if not supported
        """
        return self.instructor_client

    async def _call_instructor_client(self, method_path: str, **kwargs):
        """
        Helper method to call instructor client methods with async/sync compatibility.

        Args:
            method_path: The method path (e.g., "chat.completions.create")
            **kwargs: Arguments to pass to the method

        Returns:
            The response from the instructor client
        """
        if not self.instructor_client:
            raise RuntimeError(
                f"Instructor client not initialized for {self.name} provider"
            )

        # Navigate to the method
        method = self.instructor_client
        for part in method_path.split("."):
            method = getattr(method, part)

        # Try sync first, then async if needed
        try:
            return method(**kwargs)
        except TypeError as sync_error:
            if "'await' expression" in str(sync_error):
                # If it's actually async, await it
                return await method(**kwargs)
            else:
                raise sync_error

    def supports_structured_outputs(self) -> bool:
        """
        Check if this provider supports structured outputs via Instructor.

        Returns:
            True if structured outputs are supported, False otherwise
        """
        return self._supports_structured and self.instructor_client is not None

    async def get_structured_completion(
        self,
        response_model: Type[BaseModel],
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BaseModel:
        """
        Get a structured completion using the specified Pydantic model.

        This method provides a unified interface for structured outputs across all providers
        using the Instructor library. It handles validation, retries, and error handling
        automatically.

        Args:
            response_model: The Pydantic model class to structure the response
            prompt: The user prompt
            system: Optional system message
            options: Model-specific options
            **kwargs: Additional arguments passed to the instructor client

        Returns:
            An instance of the response_model with validated data

        Raises:
            NotImplementedError: If the provider doesn't support structured outputs
            RuntimeError: If the instructor client is not initialized
            ValidationError: If the response doesn't match the model schema
        """
        if not self.supports_structured_outputs():
            raise NotImplementedError(
                f"{self.name} provider doesn't support structured outputs. "
                f"Initialize with instructor_client or use legacy format='json' parameter."
            )

        return await self._execute_structured_completion(
            response_model=response_model,
            prompt=prompt,
            system=system,
            options=options,
            **kwargs,
        )

    async def get_structured_chat_completion(
        self,
        response_model: Type[BaseModel],
        messages: List[dict],
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BaseModel:
        """
        Get a structured chat completion using the specified Pydantic model.

        This method provides a unified interface for structured chat completions across
        all providers using the Instructor library.

        Args:
            response_model: The Pydantic model class to structure the response
            messages: List of message dictionaries
            options: Model-specific options
            **kwargs: Additional arguments passed to the instructor client

        Returns:
            An instance of the response_model with validated data

        Raises:
            NotImplementedError: If the provider doesn't support structured outputs
            RuntimeError: If the instructor client is not initialized
            ValidationError: If the response doesn't match the model schema
        """
        if not self.supports_structured_outputs():
            raise NotImplementedError(
                f"{self.name} provider doesn't support structured outputs. "
                f"Initialize with instructor_client or use legacy format='json' parameter."
            )

        return await self._execute_structured_chat_completion(
            response_model=response_model, messages=messages, options=options, **kwargs
        )

    async def _execute_structured_completion(
        self,
        response_model: Type[BaseModel],
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BaseModel:
        """
        Provider-specific implementation of structured completion.

        Override in each provider to implement the specific instructor client logic.
        This method should handle the provider-specific details of calling the
        instructor client with the appropriate parameters.

        Args:
            response_model: The Pydantic model class
            prompt: The user prompt
            system: Optional system message
            options: Provider-specific options
            **kwargs: Additional arguments

        Returns:
            An instance of the response_model
        """
        # Default implementation converts to chat completion format
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self._execute_structured_chat_completion(
            response_model=response_model, messages=messages, options=options, **kwargs
        )

    async def _execute_structured_chat_completion(
        self,
        response_model: Type[BaseModel],
        messages: List[dict],
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BaseModel:
        """
        Provider-specific implementation of structured chat completion.

        This method must be implemented by each provider to handle the specific
        instructor client calls and provider-specific parameter handling.

        Args:
            response_model: The Pydantic model class
            messages: List of message dictionaries
            options: Provider-specific options
            **kwargs: Additional arguments

        Returns:
            An instance of the response_model
        """
        raise NotImplementedError(
            f"Structured chat completion not implemented for {self.name} provider. "
            f"Override _execute_structured_chat_completion in the provider class."
        )

    @abstractmethod
    async def validate_model(self, **kwargs) -> dict:
        pass

    async def get_chat_completion(
        self, **kwargs
    ) -> Union[CompletionResponse, BaseModel]:
        """
        Get a chat completion from the model with automatic structured output detection.

        Args:
            **kwargs: Arbitrary keyword arguments. Should include:
                - messages: List of message dictionaries
                - options: Dict of model-specific parameters (temperature, max_tokens, etc.)
                - format: Response format ("json", "", or BaseModel class for structured output)
                - stream: Whether to stream the response
                - tools: List of tool/function definitions
                - tool_choice: Tool choice preference

        Returns:
            CompletionResponse for regular completions, or BaseModel instance for structured outputs
        """
        # Check if format is a BaseModel class for structured output
        format_param = kwargs.get("format", "")
        if isinstance(format_param, type) and issubclass(format_param, BaseModel):
            # Use structured output interface
            return await self.get_structured_chat_completion(
                response_model=format_param,
                messages=kwargs.get("messages", []),
                options=kwargs.get("options"),
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["format", "messages", "options"]
                },
            )
        # Otherwise use provider-specific implementation
        return await self._get_provider_chat_completion(**kwargs)

    @abstractmethod
    async def _get_provider_chat_completion(self, **kwargs) -> CompletionResponse:
        """
        Provider-specific chat completion implementation.

        This method should be implemented by each provider for their specific chat completion logic.
        The format parameter will only contain string values ("json" or "") at this level.
        """
        pass

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion tokens from the model.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            tools: Optional list of tool/function definitions
            options: Dict of model-specific parameters (temperature, max_tokens, etc.)
            **kwargs: Additional provider-specific arguments

        Yields:
            StreamChunk objects containing content and metadata

        Example:
            ```python
            async for chunk in provider.stream_chat_completion(messages):
                print(chunk.content, end="", flush=True)
                if chunk.is_final:
                    print(f"\\nTokens used: {chunk.total_tokens}")
            ```
        """
        # Default implementation calls _stream_provider_chat_completion
        async for chunk in self._stream_provider_chat_completion(
            messages=messages,
            tools=tools,
            options=options,
            **kwargs,
        ):
            yield chunk

    async def _stream_provider_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Provider-specific streaming implementation.

        Override this method in provider subclasses to implement streaming.
        Default implementation falls back to non-streaming and yields a single chunk.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tool definitions
            options: Model-specific options
            **kwargs: Additional arguments

        Yields:
            StreamChunk objects
        """
        # Default fallback: call non-streaming and yield single chunk
        self._warn_parameter(
            f"Streaming not implemented for {self.name} provider, falling back to non-streaming",
            level="warning",
        )
        response = await self._get_provider_chat_completion(
            messages=messages,
            tools=tools,
            options=options,
            **kwargs,
        )
        yield StreamChunk(
            content=response.message.content,
            role=response.message.role,
            finish_reason=response.done_reason,
            tool_calls=response.message.tool_calls,
            is_final=True,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            model=response.model,
        )

    async def get_completion(self, **kwargs) -> Union[CompletionResponse, BaseModel]:
        """
        Get a text completion from the model with automatic structured output detection.

        Args:
            **kwargs: Arbitrary keyword arguments. Should include:
                - prompt: The input prompt string
                - system: Optional system message
                - options: Dict of model-specific parameters
                - format: Response format ("json", "", or BaseModel class for structured output)

        Returns:
            CompletionResponse for regular completions, or BaseModel instance for structured outputs
        """
        # Check if format is a BaseModel class for structured output
        format_param = kwargs.get("format", "")
        if isinstance(format_param, type) and issubclass(format_param, BaseModel):
            # Use structured output interface
            return await self.get_structured_completion(
                response_model=format_param,
                prompt=kwargs.get("prompt", ""),
                system=kwargs.get("system"),
                options=kwargs.get("options"),
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["format", "prompt", "system", "options"]
                },
            )
        # Otherwise use provider-specific implementation
        return await self._get_provider_completion(**kwargs)

    @abstractmethod
    async def _get_provider_completion(self, **kwargs) -> CompletionResponse:
        """
        Provider-specific completion implementation.

        This method should be implemented by each provider for their specific completion logic.
        The format parameter will only contain string values ("json" or "") at this level.
        """
        pass

    def extract_and_store_thinking(
        self,
        message: CompletionMessage,
        call_context: str = "unknown",
    ) -> CompletionMessage:
        """
        Extracts <think> content from the message, cleans the message content, and stores the thinking in the context if present.

        Args:
            message: The message object (dict) from the model response
            call_context: The context of the call (e.g., "think_chain", "summary_generation")

        Returns:
            The updated message dict with cleaned content and thinking removed from content.
        """
        content = message.content
        if not content:
            return message

        think_start = content.find("<think>")
        think_end = content.find("</think>")
        thinking_content = None
        if think_start != -1 and think_end != -1 and think_end > think_start:
            thinking_content = content[think_start + 7 : think_end].strip()
            cleaned_content = (content[:think_start] + content[think_end + 8 :]).strip()
            message.content = cleaned_content
        else:
            message.content = content.strip()

        if thinking_content and self.context and hasattr(self.context, "session"):
            thinking_entry = {
                "timestamp": time.time(),
                "call_context": call_context,
                "thinking": thinking_content,
            }
            self.context.session.thinking_log.append(thinking_entry)
            if hasattr(self.context, "agent_logger") and self.context.agent_logger:
                self.context.agent_logger.debug(
                    f"Stored thinking for {call_context}: {thinking_content[:100]}..."
                )
        return message
