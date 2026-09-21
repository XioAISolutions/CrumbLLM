# Changelog

All notable changes to CrumbLLM are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`crumblm score` — readiness scoring with no model, no keys and no network.**
  Eight published rules over 17 weight units decide whether the next agent can
  actually continue from a handoff: is there a goal, is the context anchored to
  something openable, are the constraints declared, is there an actionable
  directive with an owner, is there a way to tell the work succeeded, is
  progress recorded, and do the cited paths resolve. Deterministic — the same
  bytes always produce the same number — which is what makes `--min` usable as
  a CI gate. Packs get a `chain_continuity` check and are scored on their
  weakest document rather than their mean. Measured at 0.30 ms p50 end to end.
  The score is weighted rule coverage, deliberately *not* a probability; see
  the README's "What the number is not".
- `research/bench_score.py` and `research/score_latency.json`, so the latency
  figure in the README is a measurement anyone can repeat rather than a number
  someone typed. Nothing in `research/` is imported by the package.
- `examples/weak-handoff.crumb` — the counter-example the README demonstrates.
  A scorer that only ever runs against good input proves nothing.
- `docs/LESSONS_FROM_LAYA.md` — what `NandhaKishorM/laya` (4,487 stars in three
  days) and TypeSafe's Jev imply for this project, separating the part that
  cannot be copied from the craft that transfers.

### Fixed
- **The documented install failed for every user.** `pip install
  git+.../CrumbLLM` cannot resolve `crumb-format>=1.2.0`, because PyPI still
  serves 0.2.0 — `crumb_core` ships in 1.2.0, which is merged but unpublished.
  Every CI job installed `crumb-format` from git *before* touching this
  package, so CI stayed green over an install path no stranger could complete,
  and the README asserted the dependency "is installed automatically", which
  was false. The README now documents the two commands that work today, and a
  new `quickstart` CI job extracts those exact commands from the README, runs
  them in a clean virtualenv with no help from the other jobs, and then runs
  the README's first command. The documentation can no longer rot while CI
  stays green.
- **The quality gate passed its own placeholder.** `MockProvider` output parses,
  is long enough, and matches no refusal phrase, so `crumblm analyze` on a
  fresh install reported `ok=True` over a sentence saying nothing about the
  CRUMB — the gate that exists to catch generic non-answers was passing the
  most generic non-answer the package can produce. Providers now declare
  `is_stub`, and the engine turns that into a warning.
- `verification_defined` counted a completed `[x]` step as a definition of
  done. "reproduced the starvation with a load test" is evidence of progress,
  not a statement of how the remaining work will be judged; completed markers
  are now excluded from that rule.
- The `crumb_llm` package docstring still claimed CrumbLLM "bundles its own
  CRUMB reader and is independent of `crumb-format`", which stopped being true
  when the vendored fork was deleted.

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
