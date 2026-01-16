# Changelog

All notable changes to the Reactive-Agents framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0a7] - 2026-01-16

### Changed
- **BREAKING**: Migrated from `google-generativeai` to `google-genai` SDK (v1.5.0)
  - Updated all Google provider imports from `import google.generativeai as genai` to `from google import genai`
  - Changed from module-level configuration to client-based architecture (`genai.Client()`)
  - Updated safety settings to use new `types.SafetySetting` format
  - All API calls now use `client.models.generate_content()` instead of `GenerativeModel.generate_content()`
- Updated `instructor` dependency to support `google-genai` extra (v1.10.0)
- Made `GoogleModelProvider.validate_model()` async to match base class interface

### Fixed
- Eliminated all deprecation warnings from Google SDK
- Fixed type annotations in Google provider (safety settings, response handling)
- Fixed all diagnostic issues in Google provider (0 errors, 0 warnings)
- Updated all Google provider tests to use new SDK mocks (21/21 passing)

### Known Issues
- The `instructor` package (v1.10.0) still imports the deprecated `google.generativeai` internally, causing a FutureWarning on import
- This is an upstream issue in instructor, not our code
- The warning is automatically suppressed in reactive-agents v0.1.0a7
- Our Google provider uses the new `google-genai` SDK correctly

### Developer Notes
- Google provider now requires `GOOGLE_API_KEY` or `GEMINI_API_KEY` environment variable
- Client initialization pattern changed: `genai.Client(api_key=api_key)` instead of `genai.configure()`
- Model validation is now async: `await provider.validate_model()`

## [0.1.0a6] - 2025-01-11

### Added
- Complete streaming support across all LLM providers (OpenAI, Anthropic, Google, Groq, Ollama)
- `StreamChunk` model with comprehensive token tracking
- Event-based streaming for Anthropic provider
- Native async streaming for all providers

### Changed
- Enhanced `BaseModelProvider` with parameter validation and logging
- Improved builder pattern with new `Provider` enum
- Refactored tool and memory managers for better configuration handling

### Fixed
- Various test fixes and improvements
- Provider initialization edge cases

### Developer Notes
- All providers now implement `stream_chat_completion()` method
- Streaming returns `AsyncIterator[StreamChunk]`
- Token usage tracked in final chunks

---

## Version History

- **v0.1.0a7** (2026-01-16): Google SDK migration, deprecation warnings eliminated
- **v0.1.0a6** (2025-01-11): Streaming support, provider enhancements
- **v0.1.0a5** and earlier: Initial alpha releases

---

[Unreleased]: https://github.com/tylerbuell/reactive-ai-agent/compare/v0.1.0a7...HEAD
[0.1.0a7]: https://github.com/tylerbuell/reactive-ai-agent/compare/v0.1.0a6...v0.1.0a7
[0.1.0a6]: https://github.com/tylerbuell/reactive-ai-agent/releases/tag/v0.1.0a6
