from __future__ import annotations
import time
from typing import List, Dict, Any, Optional, Union, Callable, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass, field

import tiktoken

if TYPE_CHECKING:
    from reactive_agents.core.context.agent_context import AgentContext


class MessageRole(Enum):
    """Standard message roles for context management."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class ContextWindow:
    """
    Represents a logical window of related messages in the context.
    Used to group messages that should be managed together.
    """

    name: str
    start_idx: int
    end_idx: int
    importance: float = 1.0  # Higher = less likely to be pruned
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """
    Manages context for reasoning strategies, providing strategy-aware
    context manipulation, preservation, and pruning.

    This class centralizes all operations related to managing the agent's
    conversation context, including adding messages, pruning, summarizing,
    and preserving important information.
    """

    def __init__(self, agent_context: "AgentContext"):
        """
        Initialize the context manager.

        Args:
            agent_context: The agent context to manage
        """
        self.agent_context = agent_context
        self.windows: List[ContextWindow] = []
        self.preservation_rules: List[Callable[[Dict[str, Any]], bool]] = []
        self._current_strategy: str | None = None

        # Strategy-specific pruning configurations
        self.strategy_configs = {
            "reactive": {
                "summarization_frequency": 4,
                "token_threshold_multiplier": 1.0,
                "message_threshold_multiplier": 1.0,
                "preserved_roles": [MessageRole.USER],
            },
            "plan_execute_reflect": {
                "summarization_frequency": 8,
                "token_threshold_multiplier": 1.5,
                "message_threshold_multiplier": 1.5,
                "preserved_roles": [MessageRole.USER, MessageRole.ASSISTANT],
            },
            "reflect_decide_act": {
                "summarization_frequency": 6,
                "token_threshold_multiplier": 1.2,
                "message_threshold_multiplier": 1.3,
                "preserved_roles": [MessageRole.USER, MessageRole.SYSTEM],
            },
            # Default configuration for any strategy
            "default": {
                "summarization_frequency": 4,
                "token_threshold_multiplier": 1.0,
                "message_threshold_multiplier": 1.0,
                "preserved_roles": [MessageRole.USER],
            },
        }

    def set_active_strategy(self, strategy_name: str | None) -> None:
        """
        Set the current active strategy to adjust context management behavior.

        Args:
            strategy_name: Name of the active strategy
        """
        self._current_strategy = strategy_name
        if self.agent_context.agent_logger:
            self.agent_context.agent_logger.debug(
                f"Context manager: Set active strategy to {strategy_name}"
            )

    @property
    def messages(self) -> List[Dict[str, Any]]:
        """
        Get all messages in the context.

        Returns:
            List of messages
        """
        return self.agent_context.session.messages

    def add_message(
        self,
        role: Union[str, MessageRole],
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Add a message to the context.

        Args:
            role: Role of the message sender
            content: Content of the message
            metadata: Optional metadata for the message

        Returns:
            Index of the added message
        """
        role_value = role.value if isinstance(role, MessageRole) else role
        message: Dict[str, Any] = {"role": role_value, "content": content}
        if metadata:
            message["metadata"] = metadata  # type: ignore

        self.agent_context.session.messages.append(message)

        # Log the addition if logging is enabled
        if self.agent_context.agent_logger:
            self.agent_context.agent_logger.debug(
                f"Context manager: Added {role_value} message, index={len(self.messages) - 1}"
            )

        return len(self.messages) - 1

    def add_nudge(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a nudge message to the context.
        """
        self.add_message(MessageRole.USER, f"**REMINDER**: {content}", metadata)

    def add_window(
        self, name: str, start_idx: Optional[int] = None, importance: float = 1.0
    ) -> ContextWindow:
        """
        Create a new context window starting at the given index or next message.

        Args:
            name: Name of the window
            start_idx: Starting message index
            importance: Importance value (0.0-1.0)

        Returns:
            The created window
        """
        if start_idx is None:
            start_idx = len(self.messages)  # Start at the next message index

        window = ContextWindow(
            name=name, start_idx=start_idx, end_idx=start_idx, importance=importance
        )
        self.windows.append(window)

        # Log the window creation if logging is enabled
        if self.agent_context.agent_logger:
            self.agent_context.agent_logger.debug(
                f"Context manager: Created window '{name}', start={start_idx}, importance={importance}"
            )

        return window

    def close_window(self, window: Union[str, ContextWindow]) -> None:
        """
        Close a context window at the current message.

        Args:
            window: Window or window name to close
        """
        if isinstance(window, str):
            # Find by name
            for w in self.windows:
                if w.name == window:
                    window = w
                    break

        if isinstance(window, ContextWindow):
            window.end_idx = len(self.messages) - 1

            # Log the window closure if logging is enabled
            if self.agent_context.agent_logger:
                self.agent_context.agent_logger.debug(
                    f"Context manager: Closed window '{window.name}', span={window.start_idx}-{window.end_idx}"
                )

    def get_messages_by_role(
        self, role: Union[str, MessageRole]
    ) -> List[Dict[str, Any]]:
        """
        Get all messages with a specific role.

        Args:
            role: Role to filter by

        Returns:
            List of messages with the specified role
        """
        role_value = role.value if isinstance(role, MessageRole) else role
        return [m for m in self.messages if m.get("role") == role_value]

    def get_messages_in_window(
        self, window: Union[str, ContextWindow]
    ) -> List[Dict[str, Any]]:
        """
        Get all messages in a specific window.

        Args:
            window: Window or window name to get messages from

        Returns:
            List of messages in the window
        """
        if isinstance(window, str):
            # Find by name
            for w in self.windows:
                if w.name == window:
                    window = w
                    break

        if isinstance(window, ContextWindow):
            return self.messages[window.start_idx : window.end_idx + 1]
        return []

    def add_preservation_rule(self, rule: Callable[[Dict[str, Any]], bool]) -> None:
        """
        Add a rule for preserving messages during pruning.

        Args:
            rule: Function that takes a message and returns True if it should be preserved
        """
        self.preservation_rules.append(rule)

    def should_preserve_message(self, message: Dict[str, Any]) -> bool:
        """
        Check if a message should be preserved during pruning.

        Args:
            message: The message to check

        Returns:
            True if the message should be preserved
        """
        # Check custom rules
        for rule in self.preservation_rules:
            if rule(message):
                return True

        # Check strategy-specific preserved roles
        if self._current_strategy and self._current_strategy in self.strategy_configs:
            config = self.strategy_configs[self._current_strategy]
            preserved_role_values = [r.value for r in config.get("preserved_roles", [])]
            if message.get("role") in preserved_role_values:
                return True

        # Check metadata for preservation flag
        metadata = message.get("metadata", {})
        if metadata.get("preserve") is True:
            return True

        return False

    def get_optimal_pruning_config(self) -> Dict[str, Any]:
        """
        Get optimal pruning configuration based on model capabilities.
        This is used by ContextManager for strategy-aware context management.
        """
        # Fallback to reasonable defaults
        model_name = getattr(self.agent_context, "provider_model_name", "")
        if "gpt-4" in model_name:
            return {"max_tokens": 120000, "max_messages": 60}
        elif "gpt-3.5" in model_name:
            return {"max_tokens": 12000, "max_messages": 40}
        elif "claude-3" in model_name:
            return {"max_tokens": 180000, "max_messages": 80}
        else:
            return {"max_tokens": 8000, "max_messages": 30}

    def estimate_context_tokens(self) -> int:
        """
        Estimate the number of tokens in the current context.
        This is used by ContextManager for pruning decisions.
        """
        try:
            # Use tiktoken for accurate token counting
            encoding = tiktoken.encoding_for_model(
                self.agent_context.provider_model_name.replace("ollama:", "")
            )
            total_tokens = 0

            # Count tokens in session messages
            for message in self.agent_context.session.messages:
                content = message.get("content", "")
                if isinstance(content, str):
                    total_tokens += len(encoding.encode(content))

            return total_tokens
        except Exception:
            # Fallback to character-based estimation
            total_chars = sum(
                len(str(msg.get("content", "")))
                for msg in self.agent_context.session.messages
            )
            return total_chars // 4  # Rough estimate: 4 chars per token

    def summarize_and_prune(self, force: bool = False) -> bool:
        """
        Check if summarization/pruning should occur and perform it if needed.

        Args:
            force: Force summarization/pruning regardless of thresholds

        Returns:
            True if pruning occurred
        """
        # Get strategy-specific configuration
        config = self.strategy_configs.get(
            self._current_strategy if self._current_strategy else "default"
        )

        base_config = self._get_pruning_config()

        # Calculate thresholds based on strategy
        summarization_frequency = max(
            4,
            getattr(self.agent_context, "context_summarization_frequency", 5)
            * (config.get("summarization_frequency", 1) if config else 1),
        )

        max_tokens_threshold = base_config["max_tokens"] * (
            config.get("token_threshold_multiplier", 1.0) if config else 1.0
        )
        max_messages_threshold = base_config["max_messages"] * (
            config.get("message_threshold_multiplier", 1.0) if config else 1.0
        )

        current_iteration = self.agent_context.session.iterations

        # Determine if we should summarize/prune
        should_summarize = force or (
            getattr(self.agent_context, "enable_context_summarization", True)
            and (current_iteration % summarization_frequency == 0)
        )

        should_prune = force or (
            getattr(self.agent_context, "enable_context_pruning", True)
            and (
                self.estimate_context_tokens() > max_tokens_threshold
                or len(self.messages) > max_messages_threshold
            )
        )

        # Log decision
        if self.agent_context.agent_logger:
            self.agent_context.agent_logger.debug(
                f"Context manager ({self._current_strategy or 'default'}): "
                f"iteration={current_iteration}, "
                f"should_summarize={should_summarize}, should_prune={should_prune}, "
                f"tokens={self.estimate_context_tokens()}, max_tokens={max_tokens_threshold}, "
                f"messages={len(self.messages)}, max_messages={max_messages_threshold}"
            )

        if should_summarize or should_prune:
            # Perform actual summarization and pruning
            self._perform_summarize_and_prune(should_summarize)
            return True

        return False

    def _get_pruning_config(self) -> Dict[str, Any]:
        """
        Get the pruning configuration.

        Returns:
            Pruning configuration
        """
        # Try to use the agent's method if available
        if hasattr(self.agent_context, "get_optimal_pruning_config"):
            return self.get_optimal_pruning_config()

        # Fallback to reasonable defaults
        model_name = getattr(self.agent_context, "provider_model_name", "")
        if "gpt-4" in model_name:
            return {"max_tokens": 120000, "max_messages": 60}
        elif "gpt-3.5" in model_name:
            return {"max_tokens": 12000, "max_messages": 40}
        elif "claude-3" in model_name:
            return {"max_tokens": 180000, "max_messages": 80}
        else:
            return {"max_tokens": 8000, "max_messages": 30}

    def _perform_summarize_and_prune(self, should_summarize: bool = True) -> None:
        """
        Actually perform the summarization and pruning operations.

        Args:
            should_summarize: Whether summarization should be performed
        """
        if len(self.messages) < 3:
            # Not enough messages to summarize/prune
            return

        preserved_indices = set()
        prunable_indices = []

        # First pass: identify messages to preserve
        for i, message in enumerate(self.messages):
            # Always keep the first system message and the last few messages
            if i == 0 and message.get("role") == "system":
                preserved_indices.add(i)
                continue

            # Keep the most recent messages
            if i >= len(self.messages) - 3:
                preserved_indices.add(i)
                continue

            if self.should_preserve_message(message):
                preserved_indices.add(i)
            else:
                # Check if message is in an important window
                in_important_window = False
                for window in self.windows:
                    if (
                        window.start_idx <= i <= window.end_idx
                        and window.importance > 0.7
                        and (len(self.messages) - i)
                        > 5  # Not one of the most recent messages
                    ):
                        in_important_window = True
                        break

                prunable_indices.append((i, message, in_important_window))

        # If summarization is requested, create summary chunks for prunable segments
        if should_summarize:
            # Find contiguous chunks of prunable messages
            chunks = self._identify_prunable_chunks(prunable_indices, preserved_indices)

            # Summarize each chunk
            for chunk in chunks:
                if len(chunk) >= 3:  # Only summarize if enough messages
                    start_idx, end_idx = chunk[0][0], chunk[-1][0]
                    chunk_messages = [m[1] for m in chunk]
                    summary = self._generate_summary(chunk_messages, start_idx, end_idx)

                    # Add summary message where the chunk starts
                    self.messages[start_idx] = {
                        "role": MessageRole.ASSISTANT.value,
                        "content": summary,
                        "metadata": {
                            "is_summary": True,
                            "summarized_range": [start_idx, end_idx],
                            "preserve": True,
                        },
                    }
                    # Mark all other messages in the chunk for removal
                    indices_to_remove = [
                        i
                        for i in range(start_idx + 1, end_idx + 1)
                        if i not in preserved_indices
                    ]
                    for i in sorted(indices_to_remove, reverse=True):
                        del self.messages[i]

        # Sync the session messages with the updated messages list
        self.agent_context.session.messages = self.messages.copy()

        # Log the results if logging is enabled
        if self.agent_context.agent_logger:
            self.agent_context.agent_logger.info(
                f"Context manager: Pruned context from {len(self.messages)} to "
                f"{len(self.agent_context.session.messages)} messages"
            )

    def _identify_prunable_chunks(
        self, prunable_indices: List[tuple], preserved_indices: set
    ) -> List[List[tuple]]:
        """
        Identify contiguous chunks of prunable messages.

        Args:
            prunable_indices: List of (index, message, in_important_window) tuples
            preserved_indices: Set of indices that must be preserved

        Returns:
            List of chunks, where each chunk is a list of prunable message tuples
        """
        chunks = []
        current_chunk = []

        for item in sorted(prunable_indices):
            idx = item[0]
            if not current_chunk or idx == current_chunk[-1][0] + 1:
                # Contiguous message
                current_chunk.append(item)
            else:
                # Start of a new chunk
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [item]

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _generate_summary(
        self, messages: List[Dict[str, Any]], start_idx: int, end_idx: int
    ) -> str:
        """
        Generate a summary of the messages.

        Args:
            messages: Messages to summarize
            start_idx: Starting index
            end_idx: Ending index

        Returns:
            Summary text
        """
        # Implement your summarization logic here, for now we'll use a simple approach
        roles = [m.get("role", "unknown") for m in messages]
        role_counts = {role: roles.count(role) for role in set(roles)}

        # Create a simple summary
        summary = (
            f"[Summary of {len(messages)} messages from indices {start_idx}-{end_idx}: "
        )
        for role, count in role_counts.items():
            summary += f"{count} {role} messages, "
        summary = summary.rstrip(", ") + "]"

        # TODO: Implement more sophisticated summarization using LLM
        # This would typically use the agent's LLM to create a better summary

        return summary

    # Additional utility methods
    def get_latest_n_messages(self, n: int) -> List[Dict[str, Any]]:
        """
        Get the latest N messages from context.

        Args:
            n: Number of messages to retrieve

        Returns:
            List of messages
        """
        return self.messages[-n:] if len(self.messages) >= n else self.messages

    def get_context_for_strategy(self) -> List[Dict[str, Any]]:
        """
        Get optimized context based on current strategy.

        Returns:
            List of messages optimized for the current strategy
        """
        # Strategy-specific logic for constructing optimal context
        if not self._current_strategy:
            return self.messages

        if self._current_strategy == "reactive":
            # Reactive strategies work best with most recent context
            return self.get_latest_n_messages(20)

        elif self._current_strategy == "plan_execute_reflect":
            # Plan-execute-reflect needs planning context
            return self._get_plan_execute_reflect_context()

        elif self._current_strategy == "reflect_decide_act":
            # Reflect-decide-act needs reflection context
            return self._get_reflect_decide_act_context()

        # Default: return all messages
        return self.messages

    def _get_plan_execute_reflect_context(self) -> List[Dict[str, Any]]:
        """
        Get optimized context for plan-execute-reflect strategy.

        Returns:
            List of messages
        """
        # Find plan windows
        plan_window = None
        for window in self.windows:
            if "plan" in window.name.lower():
                plan_window = window
                break

        if plan_window:
            # Include the plan window and recent messages
            plan_messages = self.get_messages_in_window(plan_window)
            recent_messages = self.get_latest_n_messages(10)

            # Combine and deduplicate
            context = []
            seen_indices = set()

            # Add system messages first
            for i, message in enumerate(self.messages):
                if message.get("role") == "system" and i not in seen_indices:
                    context.append(message)
                    seen_indices.add(i)

            # Add plan messages
            for message in plan_messages:
                idx = self.messages.index(message)
                if idx not in seen_indices:
                    context.append(message)
                    seen_indices.add(idx)

            # Add recent messages
            for message in recent_messages:
                idx = self.messages.index(message)
                if idx not in seen_indices:
                    context.append(message)
                    seen_indices.add(idx)

            return context

        # Fallback: recent messages plus summaries
        context = []
        for message in self.messages:
            if (
                message.get("role") == "system"
                or (message.get("metadata", {}).get("is_summary") is True)
                or message in self.get_latest_n_messages(15)
            ):
                context.append(message)

        return context

    def _get_reflect_decide_act_context(self) -> List[Dict[str, Any]]:
        """
        Get optimized context for reflect-decide-act strategy.

        Returns:
            List of messages
        """
        # Prioritize reflection messages and recent exchanges
        reflection_messages = [
            m
            for m in self.messages
            if m.get("metadata", {}).get("type") == "reflection"
        ]

        # Get recent messages
        recent_messages = self.get_latest_n_messages(12)

        # Combine and deduplicate
        context = []
        seen_indices = set()

        # Add system messages first
        for i, message in enumerate(self.messages):
            if message.get("role") == "system" and i not in seen_indices:
                context.append(message)
                seen_indices.add(i)

        # Add reflection messages
        for message in reflection_messages:
            idx = self.messages.index(message)
            if idx not in seen_indices:
                context.append(message)
                seen_indices.add(idx)

        # Add recent messages
        for message in recent_messages:
            idx = self.messages.index(message)
            if idx not in seen_indices:
                context.append(message)
                seen_indices.add(idx)

        return context

    def get_tool_calling_context(self, max_tool_summaries: int = 8) -> Dict[str, Any]:
        """
        Get optimized context for tool calling scenarios focused on tool execution history.

        Args:
            max_tool_summaries: Maximum number of recent tool summaries to include

        Returns:
            Dictionary containing optimized context for tool calling
        """
        # Get tool summaries from reasoning_log and task_progress
        tool_summaries = self._extract_tool_summaries(max_tool_summaries)

        # Extract current objective from the last user message
        current_objective = self._extract_current_objective()

        # Build focused context summary for tool calling
        context_summary = self._build_tool_focused_summary(
            tool_summaries, current_objective
        )

        return {
            "current_objective": current_objective,
            "tool_summaries": tool_summaries,
            "context_summary": context_summary,
            "available_context_tokens": self._estimate_available_tokens(),
        }

    def _extract_tool_summaries(self, max_summaries: int) -> List[Dict[str, Any]]:
        """
        Extract tool summaries from session logs, focusing on tool execution results.

        Args:
            max_summaries: Maximum number of summaries to extract

        Returns:
            List of structured tool summary data
        """
        tool_summaries = []

        # Get tool summaries from reasoning_log and task_progress
        all_entries = (
            self.agent_context.session.reasoning_log
            + self.agent_context.session.task_progress
        )

        # Filter for tool summaries and extract data
        for entry in reversed(all_entries):  # Most recent first
            if isinstance(entry, str) and "[TOOL SUMMARY]" in entry:
                # Parse tool summary for structured data
                tool_data = self._parse_tool_summary(entry)
                if tool_data:
                    tool_summaries.append(tool_data)

                if len(tool_summaries) >= max_summaries:
                    break

        return tool_summaries

    def _parse_tool_summary(self, summary: str) -> Optional[Dict[str, Any]]:
        """
        Parse a tool summary string to extract structured data.
        
        Args:
            summary: Tool summary string
            
        Returns:
            Structured tool data or None if parsing fails
        """
        try:
            # Remove the [TOOL SUMMARY] prefix
            content = summary.replace("[TOOL SUMMARY]", "").strip()
            
            # Extract tool name (look for patterns like "Used tool_name with" or "Executed tool_name")
            tool_name = "unknown"
            if "Used the " in content:
                # Pattern: "Used the tool_name with parameters"
                start = content.find("Used the ") + 9
                if " with " in content[start:]:
                    end = content.find(" with ", start)
                    tool_name = content[start:end].strip()
            elif "Used " in content and " with " in content:
                # Pattern: "Used tool_name with parameters"
                start = content.find("Used ") + 5
                end = content.find(" with ", start)
                if end > start:
                    tool_name = content[start:end].strip()
            
            # Extract key data from the summary
            extracted_data = {}
            
            # Look for common data patterns in tool results
            if "id" in content.lower():
                # Extract IDs (message IDs, user IDs, etc.)
                import re
                id_matches = re.findall(r'["\']([a-f0-9]{10,})["\']', content)
                if id_matches:
                    extracted_data["ids"] = id_matches
            
            if "status" in content.lower():
                # Extract status information
                import re
                status_matches = re.findall(r'status["\s]*[:\s]*["\s]*(\w+)', content, re.IGNORECASE)
                if status_matches:
                    extracted_data["status"] = status_matches[0]
            
            if "count" in content.lower():
                # Extract count information
                import re
                count_matches = re.findall(r'count["\s]*[:\s]*["\s]*(\d+)', content, re.IGNORECASE)
                if count_matches:
                    extracted_data["count"] = int(count_matches[0])
            
            # Extract error context for better decision making
            error_context = None
            if "error" in content.lower():
                # Extract specific error messages
                if "not authenticated" in content.lower():
                    error_context = "authentication_required"
                    extracted_data["required_action"] = "authenticate"
                elif "401" in content:
                    error_context = "authentication_required"
                    extracted_data["required_action"] = "authenticate"
                elif "403" in content:
                    error_context = "permission_denied"
                elif "404" in content:
                    error_context = "not_found"
                elif "timeout" in content.lower():
                    error_context = "timeout"
                else:
                    error_context = "general_error"
            
            # Extract success/failure indicators
            success_indicators = ["success", "sent", "created", "completed", "found"]
            failure_indicators = ["error", "failed", "denied", "invalid"]
            
            content_lower = content.lower()
            is_successful = any(indicator in content_lower for indicator in success_indicators)
            is_failed = any(indicator in content_lower for indicator in failure_indicators)
            
            return {
                "tool_name": tool_name,
                "summary": content[:200],  # First 200 chars for brevity
                "extracted_data": extracted_data,
                "error_context": error_context,
                "is_successful": is_successful and not is_failed,
                "is_failed": is_failed,
                "timestamp": time.time()
            }
            
        except Exception as e:
            if self.agent_context.agent_logger:
                self.agent_context.agent_logger.debug(f"Failed to parse tool summary: {e}")
            return None

    def _build_tool_focused_summary(
        self, tool_summaries: List[Dict[str, Any]], objective: str
    ) -> str:
        """
        Build a concise summary focused on tool execution results.
        
        Args:
            tool_summaries: List of tool summary data
            objective: Current objective
            
        Returns:
            Focused context summary string
        """
        if not tool_summaries:
            return f"Objective: {objective}"
        
        summary_parts = [f"Objective: {objective}"]
        
        # Count successful and failed tools
        successful_tools = [t for t in tool_summaries if t.get("is_successful")]
        failed_tools = [t for t in tool_summaries if t.get("is_failed")]
        
        summary_parts.append(f"Tools: {len(successful_tools)} ✅ / {len(failed_tools)} ❌")
        
        # Show critical issues (generic)
        if failed_tools:
            error_types = set(t.get("error_context", "error") for t in failed_tools)
            required_actions = set()
            for t in failed_tools:
                action = t.get("extracted_data", {}).get("required_action")
                if action:
                    required_actions.add(action)
            
            if required_actions:
                summary_parts.append(f"⚠️ Required: {', '.join(required_actions)}")
            elif error_types:
                summary_parts.append(f"⚠️ Issues: {', '.join(error_types)}")
        
        # Show available data from successful tools
        if successful_tools:
            data_available = []
            for tool in successful_tools[-2:]:  # Last 2 successful
                extracted = tool.get("extracted_data", {})
                if extracted.get("ids"):
                    data_available.append(f"{len(extracted['ids'])} ID(s)")
                elif extracted.get("status"):
                    data_available.append(f"status: {extracted['status']}")
                elif extracted.get("count"):
                    data_available.append(f"count: {extracted['count']}")
            
            if data_available:
                summary_parts.append(f"Data: {', '.join(data_available)}")
        
        return " | ".join(summary_parts)

    def _extract_current_objective(self) -> str:
        """
        Extract the current objective from conversation flow.

        Returns:
            Current objective as a string
        """
        # Look for the most recent user request or task
        for message in reversed(self.messages):
            if message.get("role") == "user":
                content = message.get("content", "")
                if content.strip():
                    return content.strip()

        return "Complete the user's request"

    def _build_tool_context_summary(
        self,
        recent_messages: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        objective: str,
    ) -> str:
        """
        Build a concise summary of the context for tool calling.

        Args:
            recent_messages: Recent conversation messages
            tool_results: Recent tool execution results
            objective: Current objective

        Returns:
            Context summary string
        """
        summary_parts = [f"Current objective: {objective}"]

        if tool_results:
            summary_parts.append(
                f"Recent tool executions: {len(tool_results)} results available"
            )

            # Summarize recent tool results
            for result in tool_results[-3:]:  # Last 3 tool results
                tool_name = result.get("metadata", {}).get("tool_name", "unknown_tool")
                result_summary = (
                    str(result.get("content", ""))[:100] + "..."
                    if len(str(result.get("content", ""))) > 100
                    else str(result.get("content", ""))
                )
                summary_parts.append(f"- {tool_name}: {result_summary}")

        # Add conversation context
        user_messages = [m for m in recent_messages if m.get("role") == "user"]
        if len(user_messages) > 1:
            summary_parts.append(
                f"Conversation has {len(user_messages)} user interactions"
            )

        return " | ".join(summary_parts)

    def _estimate_available_tokens(self) -> int:
        """
        Estimate available tokens for tool calling context.

        Returns:
            Estimated available tokens
        """
        current_tokens = self.estimate_context_tokens()
        max_tokens = self.get_optimal_pruning_config().get("max_tokens", 8000)

        # Reserve some tokens for the tool calling prompt and response
        reserved_tokens = max_tokens * 0.3  # 30% reserved
        available = max(0, max_tokens - current_tokens - reserved_tokens)

        return int(available)

    def add_tool_preservation_rules(self) -> None:
        """
        Add preservation rules specific to tool calling scenarios.
        """

        def preserve_tool_calls(message: Dict[str, Any]) -> bool:
            """Preserve messages with tool calls."""
            return "tool_calls" in message or message.get("role") == "tool"

        def preserve_tool_results(message: Dict[str, Any]) -> bool:
            """Preserve recent tool results."""
            metadata = message.get("metadata", {})
            return metadata.get("is_tool_result") or metadata.get("tool_name")

        def preserve_user_requests(message: Dict[str, Any]) -> bool:
            """Preserve user requests that might contain task context."""
            if message.get("role") == "user":
                content = message.get("content", "").lower()
                # Preserve if it looks like a task or question
                task_indicators = [
                    "can you",
                    "please",
                    "help",
                    "need",
                    "want",
                    "how",
                    "what",
                    "?",
                ]
                return any(indicator in content for indicator in task_indicators)
            return False

        # Add the preservation rules
        self.add_preservation_rule(preserve_tool_calls)
        self.add_preservation_rule(preserve_tool_results)
        self.add_preservation_rule(preserve_user_requests)
