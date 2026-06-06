# Changelog

All notable changes to CrumbLLM are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Semantic retrieval over CRUMB packs (`crumb_llm/retrieval/`): a `search`
  command and a `--query`/`--top-k` flag on `summarize`, `risks`, `next`, and
  `analyze-pack` so tasks reason over only the relevant slice of a large pack.
- Optional [turbovec](https://github.com/RyanCodrai/turbovec) backend for
  memory-efficient quantized vector search, with a zero-dependency
  feature-hashing embedder and pure-Python brute-force fallback. turbovec is
  optional like the provider SDKs; when absent, retrieval falls back to brute
  force and says so on stderr.
- `docs/turbovec-integration.md`: integration design plus a reciprocal proposal
  for the turbovec project.

## [0.1.0] - 2026-05-31

Initial release of CrumbLLM as a standalone, independent package.

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
- **CrumbLLM is fully independent of `crumb-format`.** It bundles its own CRUMB
  reader and uses it exclusively — never importing, preferring, or requiring
  `crumb-format`. `pip install crumb-llm` has zero required dependencies.

[0.1.0]: https://github.com/XioAISolutions/CrumbLLM/releases/tag/v0.1.0
