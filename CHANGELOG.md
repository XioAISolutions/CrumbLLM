# Changelog

All notable changes to CrumbLLM are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **The CRUMB grammar now lives in one place.** `crumb_llm/crumb/spec.py`, a
  334-line fork of the canonical parser, is deleted; `parser_adapter` delegates
  to `crumb_core` instead. The fork's docstring promised it was "kept faithful"
  to the canonical implementation, but nothing tested the two against each
  other — and across the ecosystem that produced real divergence: crumb-format
  emitted `v=1.4`, CrumbContext hand-wrote `v=1.3`, and this package's EJA
  schemas demanded a `crumb_version` of `"1.5"` that no spec defines.
- **CI now enforces the opposite of what it used to.** The old job installed a
  meta-path finder that made `crumb_format` unimportable, asserting
  independence as a property. Independence bought silent drift. The job now
  asserts that parsing goes *through* `crumb_core` and that no fork has
  reappeared under the old module name.
- **`crumb_version` renamed to `eja_schema_version`** in the EJA schema, model,
  and example. An EJA artifact is JSON, not a CRUMB document, and its schema
  generation is versioned independently; the old name asserted a CRUMB v1.5
  that does not exist. The value is unchanged, so EJA semantics are unaffected.
  `examples/einstein-elevator.eja.json` is resealed, since renaming a key
  changes the canonical JSON and therefore the artifact hash.

### Added
- `crumb-format>=1.2.0` as a runtime dependency, which supplies `crumb_core`.

### Fixed
- **Install instructions no longer 404.** `README.md` and
  `RELEASE_NOTES_0.1.0.md` both instructed `pip install crumb-llm`; the name has
  never been registered on PyPI. Both now point at the git install and say so
  plainly.

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
