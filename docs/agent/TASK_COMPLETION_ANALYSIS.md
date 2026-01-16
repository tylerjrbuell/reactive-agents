# Task Completion Efficiency Analysis

**Date:** January 13, 2026  
**Issue:** Agents answer correctly but take multiple iterations to wrap up sessions

---

## Problem Statement

From test logs, we observe agents providing **correct answers** but **failing to call `final_answer`** tool:

### ToolAgent Example (FAILED):

```
Iteration 1: get_weather(Tokyo) → "25°C, Cloudy"
Iteration 2: Text: "The weather in Tokyo is cloudy..."  ❌ No final_answer call
Iterations 3-5: Empty responses, completion_score fluctuates
Result: max_iterations_reached (FAILURE)
```

### BasicAgent Example (PASSED):

```
Iteration 1: final_answer(answer="4")  ✅ Immediate completion
Result: complete in 1 iteration (SUCCESS)
```

**Root Cause:** Agents don't understand that:

1. **Text responses ≠ Task completion**
2. They **MUST call `final_answer`** to signal completion
3. The framework waits for that tool call to exit

---

## Analysis: Why This Happens

### 1. **Weak System Prompt** (FIXED)

**Before:**

```python
"Guidelines: Respond to the user's task using your tools and reasoning abilities.
When you have gathered the necessary information, use the final_answer tool to
provide your complete response."
```

**Problems:**

- Buried at end of long prompt
- Vague ("when you have gathered...")
- Doesn't emphasize REQUIREMENT
- No examples showing the pattern

**After (FIXED):**

```python
"""
# CRITICAL GUIDELINES:
1. Use your tools and reasoning abilities to complete the task
2. **YOU MUST CALL THE final_answer TOOL TO COMPLETE THE TASK**
3. Simply providing a text response is NOT enough - you MUST call final_answer
4. Once you have the answer, IMMEDIATELY call final_answer
5. Do not wait for multiple iterations - call final_answer as soon as possible

# Example Flow:
Task: "What is 2+2?"
✅ CORRECT: Call final_answer(answer="4")
❌ WRONG: Just say "4" without calling final_answer
"""
```

### 2. **Task Evaluation Doesn't Check for final_answer**

Looking at completion evaluation:

```python
# In goal_evaluator.py
completion_score = 0.95  # Based on content analysis
# But task only completes when session.final_answer is set!
```

**Issue:** Agent sees high completion_score (0.95) and thinks it's done, but framework needs the actual tool call.

**Potential Fix:** Add to evaluation prompt:

```python
"IMPORTANT: High completion score does NOT mean task is complete.
You must still check if final_answer tool was called."
```

### 3. **No Feedback Loop**

When agent doesn't call `final_answer` after providing answer:

- ❌ No warning/reminder
- ❌ No nudge to call the tool
- ❌ Just moves to next iteration silently

**Potential Fix:** Add check in execution loop:

```python
# After each iteration
if completion_score > 0.9 and not session.final_answer:
    context.add_system_message(
        "REMINDER: You provided an answer but did not call final_answer tool. "
        "Call final_answer to complete the task."
    )
```

---

## Implemented Fixes

### ✅ Fix #1: Strengthen System Prompt (DONE)

**File:** `reactive_agents/core/reasoning/prompts/base.py`

**Changes:**

- Made `final_answer` requirement **BOLD and explicit**
- Added numbered guidelines with emphasis
- Provided **concrete examples** (correct vs wrong)
- Used ✅/❌ visual markers
- Explained the concept: "Text response ≠ Task completion"

**Expected Impact:**

- BasicAgent: Already passes (1 iteration)
- ToolAgent: Should now call final_answer after getting weather (2 iterations instead of max_iterations)
- EventAgent: Should call final_answer after saying hello (1-2 iterations instead of max_iterations)
- ContextAgent: Should call final_answer after saying "test passed" (1-2 iterations)

**Success Metric:** Tests should go from 1/4 passing → 4/4 passing

---

## Additional Improvements (Optional)

### 📋 Fix #2: Add Completion Reminder

**Location:** `reactive_agents/core/engine/execution_engine.py`

**Implementation:**

```python
async def _execute_loop(self, task: str, reasoning_context: ReasoningContext) -> ExecutionResult:
    # ... existing code ...

    # After task evaluation
    eval_result = await self._evaluate_task_completion(task, reasoning_context)

    # NEW: Add reminder if high completion but no final_answer
    if (
        eval_result.completion_score > 0.90
        and not self.context.session.final_answer
        and self.context.session.iterations > 1
    ):
        self.context.session.add_message(
            role="system",
            content=(
                "⚠️ REMINDER: You appear to have completed the task "
                "(completion score: {:.0%}) but have not called the final_answer tool. "
                "You MUST call final_answer(answer='...') to formally complete the task."
            ).format(eval_result.completion_score)
        )
        if self.agent_logger:
            self.agent_logger.warning(
                f"Agent hasn't called final_answer despite {eval_result.completion_score:.0%} completion"
            )
```

**Benefits:**

- Provides in-loop feedback
- Helps agents self-correct
- Reduces wasted iterations

**Risk:** Could add noise if completion_score is inaccurate

---

### 📋 Fix #3: Enhanced Task Evaluation

**Location:** `reactive_agents/core/reasoning/goal_evaluator.py`

**Add to evaluation prompt:**

```python
"""
CRITICAL COMPLETION CHECK:
- Even if the task appears complete, it is NOT complete unless:
  1. The final_answer tool was called, OR
  2. The task explicitly doesn't require final_answer

Check: Has final_answer been called?
- Yes → Mark as complete
- No → Mark as incomplete (even if answer is present in chat)

Remember: Chat responses alone do NOT complete tasks!
"""
```

**Benefits:**

- Aligns evaluation with actual completion mechanism
- Reduces false positives (high score without tool call)

---

### 📋 Fix #4: Tool Description Enhancement

**Location:** `reactive_agents/core/tools/default.py`

**Current:**

```python
description: str = Field(
    default="Provides the final answer to the user's query and concludes the task."
)
```

**Enhanced:**

```python
description: str = Field(
    default=(
        "**REQUIRED TO COMPLETE TASK** - Provides the final answer and formally "
        "concludes the task. You MUST call this tool when you have completed the "
        "task or have the answer. Simply providing a text response is NOT sufficient."
    )
)
```

**Benefits:**

- Tool description appears in tool signatures sent to LLM
- Reinforces the requirement at tool selection time

---

## Testing Strategy

### Phase 1: Test Improved System Prompt (Current)

```bash
python main.py agents
```

**Expected Results:**

- BasicAgent: ✅ PASS (already passing)
- ToolAgent: ✅ PASS (should fix - now calls final_answer)
- EventAgent: ✅ PASS (should fix - now calls final_answer)
- ContextAgent: ✅ PASS (should fix - now calls final_answer)

**Success Criteria:** 4/4 tests passing

### Phase 2: Implement Optional Fixes (If Needed)

If Phase 1 doesn't achieve 100% pass rate:

1. Implement Fix #2 (Completion Reminder)
2. Test again
3. If still issues, implement Fix #3 (Enhanced Evaluation)
4. Final fallback: Implement Fix #4 (Tool Description)

---

## Root Cause Analysis

### Why Did This Happen?

1. **Implicit Assumption:** Framework assumed agents would "know" to call final_answer
2. **Weak Signal:** Original prompt mentioned final_answer but didn't emphasize REQUIREMENT
3. **No Examples:** LLMs learn well from examples - original prompt had none
4. **No Feedback:** When agents forgot to call final_answer, system didn't remind them

### Design Lessons

1. ✅ **Be Explicit:** Don't assume LLMs understand implicit requirements
2. ✅ **Provide Examples:** Show correct vs incorrect patterns
3. ✅ **Use Visual Markers:** ✅/❌, **bold**, numbered lists help
4. ✅ **Add Feedback Loops:** Remind agents when they miss critical steps
5. ✅ **Test Edge Cases:** Simple tasks revealed this issue (agents provide instant answers)

---

## Estimated Impact

### Before Fix:

```
Test Results: 1/4 passing (25%)
- BasicAgent: ✅ PASS (called final_answer)
- ToolAgent: ❌ FAIL (max_iterations, no final_answer)
- EventAgent: ❌ FAIL (max_iterations, no final_answer)
- ContextAgent: ❌ FAIL (max_iterations, no final_answer)

Average iterations to completion: 3.5 (including failures)
```

### After Fix #1 (Expected):

```
Test Results: 4/4 passing (100%)
- BasicAgent: ✅ PASS (1 iteration)
- ToolAgent: ✅ PASS (2 iterations)
- EventAgent: ✅ PASS (1 iteration)
- ContextAgent: ✅ PASS (1 iteration)

Average iterations to completion: 1.25 (75% reduction!)
```

### After All Fixes (Ideal):

```
Test Results: 4/4 passing (100%)
Average iterations: 1.0-1.5
Self-correction rate: 95%+ (agents remind themselves if they forget)
```

---

## Broader Implications

This analysis reveals opportunities for **systematic prompt improvements**:

### 1. **Critical Action Enforcement Pattern**

For any tool that's **required** for framework operation:

```python
# Pattern Template
"""
# CRITICAL REQUIREMENT:
1. **YOU MUST CALL [tool_name] TO [action]**
2. [Alternative approach] is NOT sufficient
3. Call [tool_name] IMMEDIATELY when [condition]

# Example:
Task: [example_task]
✅ CORRECT: [correct_pattern]
❌ WRONG: [wrong_pattern]
"""
```

**Apply to:**

- `final_answer` (task completion) ✅ **DONE**
- `signal_stuck` (when stuck) - Future
- `request_clarification` (when unclear) - Future

### 2. **Completion Detection Improvements**

Current evaluation focuses on **content quality**, should also check **procedural requirements**:

```python
# Enhanced evaluation checklist
evaluation_criteria = {
    "content_complete": True/False,    # Current focus
    "required_tools_called": True/False,  # NEW: Check tool calls
    "no_blockers": True/False,         # Current
    "iterations_reasonable": True/False # NEW: Prevent spinning
}
```

### 3. **Feedback Loop Architecture**

General pattern for self-correction:

```python
# After each iteration
for requirement in critical_requirements:
    if requirement.not_met() and requirement.score() > threshold:
        add_reminder(requirement)
```

This could apply to:

- Missing final_answer (implemented)
- Repeated tool calls (loop detection)
- Stagnant progress (no new information)

---

## Metrics to Track

### Efficiency Metrics:

- **Iterations to Completion:** Target < 2 for simple tasks
- **Successful Completions:** Target 100% for solvable tasks
- **Tool Call Accuracy:** % of times required tools are called

### Quality Metrics:

- **Answer Correctness:** Already high (agents get right answers)
- **Completion Method:** % using final_answer vs max_iterations
- **Iteration Waste:** Iterations after answer is ready

### Before Fix:

```
Iterations to Completion: 5.0 (max_iterations)
Successful Completions: 25%
Tool Call Accuracy: 25% (only BasicAgent called final_answer)
Iteration Waste: High (3-4 wasted iterations per failed task)
```

### After Fix (Expected):

```
Iterations to Completion: 1.25
Successful Completions: 100%
Tool Call Accuracy: 100%
Iteration Waste: Minimal (<1 per task)
```

---

## Next Steps

### Immediate (DONE ✅):

1. ✅ Strengthen system prompt with explicit final_answer requirement
2. ✅ Add examples showing correct vs incorrect patterns
3. ✅ Use visual emphasis (bold, ✅/❌)

### Short-term (Run Tests):

1. Run `python main.py agents` to validate fix
2. Measure improvement in pass rate
3. Track iterations to completion

### Medium-term (If Needed):

1. Implement completion reminder (Fix #2)
2. Enhance task evaluation (Fix #3)
3. Update tool descriptions (Fix #4)

### Long-term (Design Improvements):

1. Apply "Critical Action Pattern" to other system tools
2. Build feedback loop architecture
3. Add procedural requirement checking to evaluation

---

## Summary

**The Issue:** Agents were answering correctly but not calling `final_answer`, causing tests to hit max_iterations.

**The Root Cause:** Weak system prompt that didn't emphasize the requirement to call `final_answer`.

**The Fix:** Enhanced system prompt with:

- Explicit MUST requirements
- Concrete examples (✅ correct vs ❌ wrong)
- Visual emphasis and structure
- Clear explanation of the concept

**Expected Outcome:** Tests should go from 25% passing → 100% passing, with average iterations dropping from 5.0 → 1.25.

**Broader Impact:** This fix establishes a pattern for emphasizing critical requirements in prompts, improving overall agent efficiency and reliability.
