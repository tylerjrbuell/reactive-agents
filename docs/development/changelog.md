# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive roadmap documentation
- Development documentation section in MkDocs
- **Streaming support** for all LLM providers:
  - `stream_chat_completion()` method in BaseModelProvider
  - `StreamChunk` model for typed streaming responses
  - Full streaming implementation for OpenAI, Anthropic, Ollama, Groq, and Google providers
  - Token usage tracking in final stream chunks
  - Tool call support during streaming

### Changed
- Updated documentation structure

## [0.1.0a6] - 2024-12

### Added
- Enhanced `BaseModelProvider` with parameter validation and logging
- `Provider` enum for type-safe provider selection
- `BuilderValidationError` class for builder validation
- Improved tool and memory manager configuration handling

### Changed
- Refactored `ReactiveAgent` initialization
- Enhanced tool configuration system
- Updated provider parameter translation architecture

### Fixed
- Various type safety improvements

## [0.1.0a5] - 2024-12

### Added
- Instructor integration for structured outputs across all providers
- Dual-parameter architecture (OpenAI-style interface with provider-specific translation)

### Changed
- Unified structured output system using Instructor library
- Improved provider consistency

## [0.1.0a4] - 2024-11

### Added
- Initial configuration and factory modules
- Component-based strategy architecture

### Changed
- Major refactoring of agent initialization
- Improved separation of concerns

## [0.1.0a3] - 2024-11

### Added
- Vector memory manager with ChromaDB
- Event-driven architecture with EventBus
- MCP (Model Context Protocol) integration

## [0.1.0a2] - 2024-10

### Added
- Multiple reasoning strategies
- Custom tool decorator system
- A2A (Agent-to-Agent) communication protocol

## [0.1.0a1] - 2024-10

### Added
- Initial alpha release
- ReactiveAgentBuilder with fluent API
- Support for OpenAI, Anthropic, Google, Groq, Ollama providers
- Basic tool execution system
- Memory persistence
