# Reactive-Agents Framework Roadmap

> **Current Version:** 0.1.0a6 (Alpha)
> **Last Updated:** December 2024
> **Status:** Active Development - Breaking changes expected

---

## Version Milestones

| Version | Status | Focus |
|---------|--------|-------|
| **0.1.0a6** | ✅ Current | Core refactoring, provider architecture, builder pattern, **streaming support** |
| **0.1.0a7** | 🔄 Next | Google SDK migration, test coverage improvement |
| **0.1.0a8** | 📋 Planned | Complete strategy implementations |
| **0.1.0b1** | 📋 Planned | Beta - Production features (caching, rate limiting) |
| **0.1.0** | 🎯 Target | Stable release - Full feature parity |

---

## Current State (v0.1.0a6)

### Recent Improvements

The framework has undergone significant refactoring with these key improvements:

- **Provider Architecture**: Unified dual-parameter system with OpenAI-style interface
- **Builder Pattern**: Type-safe `ReactiveAgentBuilder` with fluent API
- **Component Factory**: Dependency injection for all components
- **Type System**: Comprehensive Pydantic models (~3,900 lines)
- **Event System**: Type-safe EventBus with async support
- **MCP Integration**: First-class Model Context Protocol support

### Test Coverage

| Category | Coverage | Status |
|----------|----------|--------|
| Overall | 61% | Needs improvement |
| Core Engine | 87% | Good |
| Tool Manager | 87% | Good |
| Event Bus | 100% | Excellent |
| Strategies | 36-96% | Mixed |
| Providers | 14-64% | Needs work |

### Provider Support

| Provider | Completion | Tools | Structured Output | Streaming |
|----------|:----------:|:-----:|:-----------------:|:---------:|
| OpenAI | ✅ | ✅ | ✅ | ✅ |
| Anthropic | ✅ | ✅ | ✅ | ✅ |
| Google | ✅ | ⚠️ | ✅ | ✅ |
| Groq | ✅ | ⚠️ | ⚠️ | ✅ |
| Ollama | ✅ | ⚠️ | ⚠️ | ✅ |

---

## Phase 1: v0.1.0a7 - Critical Fixes

> **Timeline:** 1-2 weeks
> **Goal:** Migrate Google SDK, improve test coverage

### 1.1 Fix Failing Tests ✅ COMPLETED

**Issue:** Google provider test was failing

```
TestGoogleModelProvider::test_get_completion
AssertionError: Expected 'get_chat_completion' to have been called once. Called 0 times.
```

**Resolution:** Fixed mock target from `get_chat_completion` to `_get_provider_chat_completion` in test file.

---

### 1.2 Google SDK Migration

**Issue:** Deprecated SDK warning

```
FutureWarning: All support for the `google.generativeai` package has ended.
Switch to the `google.genai` package.
```

**Migration Steps:**

1. Update `pyproject.toml`:
   ```toml
   google-genai = "^0.5.0"  # Replace google-generativeai
   ```

2. Update imports in `reactive_agents/providers/llm/google.py`:
   ```python
   # Before
   import google.generativeai as genai

   # After
   from google import genai
   ```

3. Update API calls to match new SDK patterns

**Action Items:**

- [ ] Update dependencies in `pyproject.toml`
- [ ] Refactor `GoogleModelProvider` for new SDK
- [ ] Update type hints and response handling
- [ ] Test all Google functionality
- [ ] Update documentation

---

### 1.3 Increase Test Coverage

**Priority Targets:**

| Component | Current | Target | Priority |
|-----------|---------|--------|----------|
| `task_classifier.py` | 13% | 70% | High |
| `prompts/base.py` | 34% | 60% | Medium |
| `strategies/plan_execute_reflect.py` | 36% | 70% | High |
| `strategies/reflect_decide_act.py` | 43% | 70% | High |
| `providers/llm/groq.py` | 14% | 60% | Medium |
| `providers/llm/anthropic.py` | 40% | 70% | High |

**Action Items:**

- [ ] Write unit tests for `TaskClassifier.classify_task()`
- [ ] Write unit tests for fallback classification
- [ ] Add integration tests for strategy selection
- [ ] Add provider-specific test cases

---

### Phase 1 Deliverables

- [ ] All tests passing (429/429)
- [ ] Google SDK migrated to `google.genai`
- [ ] Critical component coverage > 60%
- [ ] No deprecation warnings

---

## Phase 2: Streaming Support ✅ COMPLETED (v0.1.0a6)

> **Status:** ✅ Completed
> **Goal:** Add streaming across all providers

### 2.1 Streaming Architecture ✅

Implemented in `reactive_agents/core/types/provider_types.py` and `reactive_agents/providers/llm/base.py`:

```python
class StreamChunk(BaseModel):
    """Single chunk in streaming response."""
    content: str = ""
    role: Optional[str] = None
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    is_final: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    chunk_index: int = 0
    model: Optional[str] = None

class BaseModelProvider:
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """Stream chat completion tokens."""
        ...
```

### 2.2 Provider Implementations ✅

All providers implemented with `_stream_provider_chat_completion()`:

| Provider | Status | Notes |
|----------|--------|-------|
| OpenAI | ✅ | Native streaming with `stream_options` |
| Anthropic | ✅ | Event-based streaming with `messages.stream()` |
| Google | ✅ | `generate_content()` with `stream=True` |
| Groq | ✅ | OpenAI-compatible streaming |
| Ollama | ✅ | Native async streaming |

### 2.3 Remaining Integration

**Pending for future versions:**

- [ ] Add streaming event types
- [ ] Integrate with `ExecutionEngine`
- [ ] Add `stream_run()` to `ReactiveAgent`
- [x] Add streaming example (see `docs/examples/streaming.md`)

### Phase 2 Deliverables ✅

- [x] Streaming works in all 5 providers
- [x] `StreamChunk` model defined
- [x] Token usage tracking in final chunks
- [x] Tool call support during streaming

---

## Phase 3: v0.1.0a9 - Complete Strategies

> **Timeline:** 2-3 weeks
> **Goal:** Complete all reasoning strategy implementations

### 3.1 PlanExecuteReflect Strategy

**Current Coverage:** 36%

**Missing Components:**

- Plan generation with validation
- Step-by-step execution tracking
- Reflection after each step
- Plan revision based on outcomes

**Files:**

- `reactive_agents/core/reasoning/strategies/plan_execute_reflect.py`
- `reactive_agents/core/reasoning/steps/plan_execute_reflect_steps.py`

**Action Items:**

- [ ] Implement `PlanStep.execute()` with proper LLM prompting
- [ ] Implement `ExecutionStep.execute()` with tool integration
- [ ] Implement `ReflectionStep.execute()` with memory storage
- [ ] Add plan validation and scoring
- [ ] Add plan revision capability
- [ ] Write comprehensive tests (target: 80%)

---

### 3.2 ReflectDecideAct Strategy

**Current Coverage:** 43%

**Missing Components:**

- Proper reflection generation
- Decision making based on reflection
- Action selection algorithm
- Learning from outcomes

**Files:**

- `reactive_agents/core/reasoning/strategies/reflect_decide_act.py`
- `reactive_agents/core/reasoning/steps/reflect_decide_act_steps.py`

**Action Items:**

- [ ] Implement `ReflectStep.execute()`
- [ ] Implement `DecideStep.execute()` with scoring
- [ ] Implement `ActStep.execute()` with tool selection
- [ ] Add outcome evaluation
- [ ] Write comprehensive tests (target: 80%)

---

### 3.3 Token Counting

**Add to all providers:**

```python
class BaseModelProvider:
    def count_tokens(self, text: str) -> int:
        """Count tokens using provider's tokenizer."""
        raise NotImplementedError

    def get_context_window(self) -> int:
        """Get model's context window size."""
        raise NotImplementedError
```

**Action Items:**

- [ ] Add `count_tokens()` to OpenAI (tiktoken)
- [ ] Add `count_tokens()` to Anthropic (anthropic-tokenizer)
- [ ] Add `count_tokens()` to Google
- [ ] Add `count_tokens()` to Groq
- [ ] Add `count_tokens()` to Ollama
- [ ] Add token tracking to `CompletionResponse`

---

### Phase 3 Deliverables

- [ ] PlanExecuteReflect coverage > 80%
- [ ] ReflectDecideAct coverage > 80%
- [ ] Token counting in all providers
- [ ] Overall test coverage > 75%

---

## Phase 4: v0.1.0b1 - Production Features (Beta)

> **Timeline:** 3-4 weeks
> **Goal:** Add production-grade features

### 4.1 Caching System

**Components:**

- LLM response cache (exact match)
- Semantic cache (similar queries)
- Tool result cache
- Pluggable backends (memory, Redis, SQLite)

```python
class CacheConfig:
    enabled: bool = True
    backend: Literal["memory", "redis", "sqlite"] = "memory"
    ttl_seconds: int = 3600
    semantic_threshold: float = 0.95
```

---

### 4.2 Rate Limiting

**Features:**

- Per-provider rate limits
- Token bucket algorithm
- Automatic retry with backoff
- Request queuing

```python
class RateLimitConfig:
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    concurrent_requests: int = 10
```

---

### 4.3 Model Fallback

**Features:**

- Automatic failover on errors
- Health-based provider ordering
- Configurable fallback chain

```python
agent = await (
    ReactiveAgentBuilder()
    .with_provider(Provider.OPENAI, "gpt-4")
    .with_fallback_providers([
        (Provider.ANTHROPIC, "claude-3-sonnet"),
        (Provider.GROQ, "llama-3.1-70b"),
    ])
    .build()
)
```

---

### 4.4 Observability

**Features:**

- OpenTelemetry tracing
- Prometheus metrics
- Structured logging with correlation IDs
- Grafana dashboard template

---

### Phase 4 Deliverables

- [ ] LLM response caching
- [ ] Semantic caching
- [ ] Per-provider rate limiting
- [ ] Model fallback system
- [ ] OpenTelemetry integration
- [ ] Prometheus metrics
- [ ] Grafana dashboard template

---

## Phase 5: v0.1.0 - Stable Release

> **Timeline:** 2-3 weeks
> **Goal:** Polish and stabilize for production use

### 5.1 Advanced Multi-Agent

- Hierarchical agent orchestration
- Agent pools with load balancing
- Shared memory between agents
- Enhanced A2A protocol

### 5.2 Tool Enhancements

- Tool chaining/pipelines
- Tool dependency resolution
- Parallel tool execution improvements

### 5.3 Vision/Multimodal

- Image input support (OpenAI, Anthropic, Google)
- Multimodal tool results

### 5.4 Documentation & Polish

- Complete API reference
- Tutorial series
- Best practices guide
- Performance benchmarks

---

## Technical Debt

### High Priority

| ID | Description | Location | Effort | Status |
|----|-------------|----------|--------|--------|
| TD-001 | Google SDK deprecation | `providers/llm/google.py` | Medium | ⏳ Pending |
| TD-002 | Incomplete strategies | `core/reasoning/strategies/` | Large | ⏳ Pending |
| ~~TD-003~~ | ~~Missing streaming~~ | ~~All providers~~ | ~~Large~~ | ✅ **Completed** |
| TD-004 | Context summarization TODO | `context_manager.py:550` | Medium | ⏳ Pending |

### Medium Priority

| ID | Description | Location | Effort |
|----|-------------|----------|--------|
| TD-005 | Plugin system TODOs | `plugins/plugin_manager.py` | Medium |
| TD-006 | Low provider coverage | Multiple providers | Medium |
| TD-007 | Circular import workarounds | Various | Small |

---

## Success Metrics

### v0.1.0a6 (Current) ✅

- [x] 0 failing tests (429/429 passing)
- [x] Streaming in 5/5 providers
- [x] StreamChunk model with token tracking

### v0.1.0a7

- [ ] 0 deprecation warnings (Google SDK migrated)
- [ ] Task classifier coverage > 60%
- [ ] Provider coverage improvement

### v0.1.0a8

- [ ] Strategy coverage > 80%
- [ ] Overall coverage > 75%

### v0.1.0b1

- [ ] < 100ms cache hit latency
- [ ] 0 rate limit errors in normal operation
- [ ] Full trace visibility

### v0.1.0

- [ ] Production deployments
- [ ] Complete documentation
- [ ] Benchmark results published

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Priority Areas

1. ~~Streaming implementation~~ ✅ Completed
2. Google SDK migration
3. Strategy completeness
4. Test coverage
5. Documentation

---

*This roadmap is a living document updated as the project evolves.*
