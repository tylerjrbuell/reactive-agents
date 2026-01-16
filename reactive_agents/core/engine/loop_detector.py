"""Loop detection system for identifying repeated agent actions.

This module provides loop detection capabilities to identify when agents
are repeating the same actions without making progress, enabling automatic
intervention to break out of unproductive loops.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import json
import hashlib
from collections import deque


@dataclass
class ToolCallRecord:
    """Record of a tool call for loop detection.

    Attributes:
        tool_name: Name of the tool called
        params: Parameters passed to the tool
        iteration: Iteration number when called
        result_hash: Hash of the result (if available)
        signature: Unique signature of this call (tool + params)
    """
    tool_name: str
    params: Dict[str, Any]
    iteration: int
    result_hash: Optional[str] = None
    signature: str = field(init=False)

    def __post_init__(self):
        """Generate signature after initialization."""
        self.signature = self._generate_signature()

    def _generate_signature(self) -> str:
        """Generate unique signature for this tool call.

        Returns:
            SHA256 hash of tool name + sorted params
        """
        # Sort params for consistent hashing
        try:
            params_str = json.dumps(self.params, sort_keys=True)
        except (TypeError, ValueError):
            # If params aren't JSON serializable, use str representation
            params_str = str(sorted(self.params.items()))

        signature_input = f"{self.tool_name}:{params_str}"
        return hashlib.sha256(signature_input.encode()).hexdigest()[:16]


@dataclass
class LoopDetectionResult:
    """Result of loop detection analysis.

    Attributes:
        loop_detected: Whether a loop was detected
        loop_type: Type of loop (exact, similar, progressive)
        loop_length: Number of iterations in the loop
        repeated_calls: List of calls that form the loop
        confidence: Confidence score (0.0-1.0)
        recommendation: Recommended action
    """
    loop_detected: bool
    loop_type: Optional[str] = None
    loop_length: int = 0
    repeated_calls: List[ToolCallRecord] = field(default_factory=list)
    confidence: float = 0.0
    recommendation: Optional[str] = None


class LoopDetector:
    """Detects loops in agent tool call patterns.

    The loop detector tracks tool calls and identifies patterns that indicate
    the agent is stuck in a loop:

    1. **Exact loops**: Same tool + params repeated multiple times
    2. **Similar loops**: Same tool with slightly different params
    3. **Progressive loops**: Sequence of tools repeated multiple times

    When a loop is detected, the detector provides recommendations for
    intervention (strategy switch, nudge, etc.)
    """

    def __init__(
        self,
        window_size: int = 20,
        exact_match_threshold: int = 3,
        similar_match_threshold: int = 4,
        pattern_match_threshold: int = 2,
    ):
        """Initialize loop detector.

        Args:
            window_size: Number of recent calls to track
            exact_match_threshold: Threshold for exact match loops
            similar_match_threshold: Threshold for similar tool loops
            pattern_match_threshold: Threshold for pattern loops
        """
        self.window_size = window_size
        self.exact_match_threshold = exact_match_threshold
        self.similar_match_threshold = similar_match_threshold
        self.pattern_match_threshold = pattern_match_threshold

        # Track recent tool calls
        self.call_history: deque[ToolCallRecord] = deque(maxlen=window_size)

        # Track signature counts for quick exact match detection
        self.signature_counts: Dict[str, int] = {}

        # Track tool name counts for similar match detection
        self.tool_name_counts: Dict[str, int] = {}

    def record_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        iteration: int,
        result: Any = None,
    ) -> LoopDetectionResult:
        """Record a tool call and check for loops.

        Args:
            tool_name: Name of the tool called
            params: Parameters passed to the tool
            iteration: Current iteration number
            result: Tool result (optional, for result-based detection)

        Returns:
            LoopDetectionResult indicating if loop detected
        """
        # Create record
        result_hash = None
        if result is not None:
            try:
                result_str = json.dumps(result, sort_keys=True)
                result_hash = hashlib.sha256(result_str.encode()).hexdigest()[:16]
            except (TypeError, ValueError):
                result_hash = hashlib.sha256(str(result).encode()).hexdigest()[:16]

        record = ToolCallRecord(
            tool_name=tool_name,
            params=params,
            iteration=iteration,
            result_hash=result_hash,
        )

        # Add to history
        self.call_history.append(record)

        # Update counts
        self.signature_counts[record.signature] = (
            self.signature_counts.get(record.signature, 0) + 1
        )
        self.tool_name_counts[tool_name] = (
            self.tool_name_counts.get(tool_name, 0) + 1
        )

        # Check for loops
        return self._detect_loops(record)

    def _detect_loops(self, latest_record: ToolCallRecord) -> LoopDetectionResult:
        """Detect loops in the call history.

        Checks for:
        1. Exact match loops (same signature repeated)
        2. Similar loops (same tool, different params)
        3. Pattern loops (sequence of calls repeated)

        Args:
            latest_record: Most recent tool call record

        Returns:
            LoopDetectionResult with detection details
        """
        # Check exact match loops first (highest confidence)
        exact_result = self._check_exact_loops(latest_record)
        if exact_result.loop_detected:
            return exact_result

        # Check similar tool loops
        similar_result = self._check_similar_loops(latest_record)
        if similar_result.loop_detected:
            return similar_result

        # Check pattern loops (lower confidence)
        pattern_result = self._check_pattern_loops()
        if pattern_result.loop_detected:
            return pattern_result

        # No loop detected
        return LoopDetectionResult(loop_detected=False)

    def _check_exact_loops(
        self, latest_record: ToolCallRecord
    ) -> LoopDetectionResult:
        """Check for exact match loops (same tool + params).

        Args:
            latest_record: Most recent tool call

        Returns:
            LoopDetectionResult for exact loops
        """
        signature = latest_record.signature
        count = self.signature_counts.get(signature, 0)

        if count >= self.exact_match_threshold:
            # Find all matching calls
            matching_calls = [
                record for record in self.call_history
                if record.signature == signature
            ]

            return LoopDetectionResult(
                loop_detected=True,
                loop_type="exact",
                loop_length=count,
                repeated_calls=matching_calls,
                confidence=1.0,
                recommendation=(
                    f"Agent is repeating the exact same call ({latest_record.tool_name}) "
                    f"{count} times. Consider switching strategy or adding constraints."
                ),
            )

        return LoopDetectionResult(loop_detected=False)

    def _check_similar_loops(
        self, latest_record: ToolCallRecord
    ) -> LoopDetectionResult:
        """Check for similar tool loops (same tool, different params).

        Args:
            latest_record: Most recent tool call

        Returns:
            LoopDetectionResult for similar loops
        """
        tool_name = latest_record.tool_name
        count = self.tool_name_counts.get(tool_name, 0)

        if count >= self.similar_match_threshold:
            # Find all calls with same tool
            matching_calls = [
                record for record in self.call_history
                if record.tool_name == tool_name
            ]

            # Check if parameters are similar (heuristic: mostly same keys)
            if len(matching_calls) >= 2:
                param_similarity = self._calculate_param_similarity(matching_calls)

                if param_similarity > 0.6:  # 60% similar parameters
                    return LoopDetectionResult(
                        loop_detected=True,
                        loop_type="similar",
                        loop_length=count,
                        repeated_calls=matching_calls,
                        confidence=param_similarity,
                        recommendation=(
                            f"Agent is repeatedly calling {tool_name} "
                            f"({count} times) with similar parameters. "
                            f"May be stuck in a pattern."
                        ),
                    )

        return LoopDetectionResult(loop_detected=False)

    def _check_pattern_loops(self) -> LoopDetectionResult:
        """Check for repeating patterns in call sequence.

        Returns:
            LoopDetectionResult for pattern loops
        """
        if len(self.call_history) < 6:  # Need at least 6 calls to detect pattern
            return LoopDetectionResult(loop_detected=False)

        # Try to find repeating sequences of length 2-4
        for pattern_length in range(2, 5):
            pattern = self._find_repeating_pattern(pattern_length)
            if pattern:
                return LoopDetectionResult(
                    loop_detected=True,
                    loop_type="pattern",
                    loop_length=len(pattern),
                    repeated_calls=pattern,
                    confidence=0.7,
                    recommendation=(
                        f"Agent is repeating a pattern of {pattern_length} tool calls. "
                        f"May indicate a loop in reasoning."
                    ),
                )

        return LoopDetectionResult(loop_detected=False)

    def _find_repeating_pattern(self, pattern_length: int) -> Optional[List[ToolCallRecord]]:
        """Find repeating pattern of given length in recent history.

        Args:
            pattern_length: Length of pattern to find

        Returns:
            List of records forming the pattern, or None
        """
        if len(self.call_history) < pattern_length * self.pattern_match_threshold:
            return None

        # Get recent calls
        recent_calls = list(self.call_history)[-pattern_length * 3:]

        # Extract pattern from end
        pattern_sigs = [
            record.signature
            for record in recent_calls[-pattern_length:]
        ]

        # Count how many times this pattern repeats
        repeat_count = 0
        for i in range(len(recent_calls) - pattern_length, -1, -pattern_length):
            window_sigs = [
                record.signature
                for record in recent_calls[i:i+pattern_length]
            ]
            if window_sigs == pattern_sigs:
                repeat_count += 1
            else:
                break

        if repeat_count >= self.pattern_match_threshold:
            return recent_calls[-pattern_length:]

        return None

    def _calculate_param_similarity(
        self, calls: List[ToolCallRecord]
    ) -> float:
        """Calculate parameter similarity across calls.

        Args:
            calls: List of tool call records

        Returns:
            Similarity score (0.0-1.0)
        """
        if len(calls) < 2:
            return 0.0

        # Collect all parameter keys
        all_keys = set()
        for call in calls:
            all_keys.update(call.params.keys())

        if not all_keys:
            return 1.0  # All empty params = 100% similar

        # Calculate how many calls share each key
        key_counts = {}
        for key in all_keys:
            count = sum(1 for call in calls if key in call.params)
            key_counts[key] = count

        # Similarity = average key coverage
        total_coverage = sum(key_counts.values())
        max_coverage = len(all_keys) * len(calls)

        return total_coverage / max_coverage if max_coverage > 0 else 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current loop detection state.

        Returns:
            Dictionary with statistics and current state
        """
        return {
            "total_calls_tracked": len(self.call_history),
            "unique_signatures": len(self.signature_counts),
            "unique_tools": len(self.tool_name_counts),
            "most_called_tool": (
                max(self.tool_name_counts.items(), key=lambda x: x[1])
                if self.tool_name_counts else None
            ),
            "most_repeated_signature": (
                max(self.signature_counts.items(), key=lambda x: x[1])
                if self.signature_counts else None
            ),
        }

    def reset(self) -> None:
        """Reset loop detection state."""
        self.call_history.clear()
        self.signature_counts.clear()
        self.tool_name_counts.clear()
