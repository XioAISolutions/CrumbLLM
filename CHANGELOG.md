# Changelog

All notable changes to CrumbLLM are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-31

Initial release of CrumbLLM as a standalone package.

### Added
- AI analysis engine over CRUMB files and packs: `analyze`, `analyze-pack`,
  `summarize`, `risks`, `next`, and `improve`, plus `setup`/`status` and
  `export-dataset`.
- Provider adapters for OpenAI, Anthropic, Ollama, and LM Studio behind one
  interface, with a built-in offline `mock` provider as the default (runs with
  no API keys).
- Quality gates on every result: hallucinated-path detection, JSON validity,
  and generic/empty-answer checks.
- Bundled CRUMB v1.1–v1.4 reader (`crumb_llm/crumb/spec.py`).

### Changed
- **CrumbLLM is now standalone.** It no longer requires `crumb-format` at
  runtime — `pip install crumb-llm` has zero required dependencies. When
  `crumb-format` is installed (optional `[crumb-format]` extra) it is preferred
  so analysis can track the upstream spec.

[0.1.0]: https://github.com/XioAISolutions/CrumbLLM/releases/tag/v0.1.0
