# CrumbLLM v0.1.0

First release of **CrumbLLM** — the local/cloud AI engine that reads CRUMB
files and packs and produces summaries, risks, next actions, and improved
handoffs.

## Highlights

- **Fully independent.** CrumbLLM bundles its own CRUMB v1.1–v1.4 reader
  (`crumb_llm/crumb/spec.py`) and uses it exclusively. `pip install crumb-llm`
  pulls in **zero required dependencies** — it never imports, prefers, or
  requires `crumb-format`.
- **Runs with no API keys.** A built-in offline `mock` provider is the default.
  OpenAI, Anthropic, Ollama, and LM Studio are available behind one interface;
  cloud/local providers talk plain HTTP over the standard library, so no SDK is
  strictly required.
- **Honest by design.** Every result carries quality-gate warnings:
  hallucinated-path detection, JSON validity, and generic/empty-answer checks.

## Commands

`analyze`, `analyze-pack`, `summarize`, `risks`, `next`, `improve`, plus
`setup` / `status` and `export-dataset`.

```bash
pip install crumb-llm
crumblm analyze path/to/session.crumb
```

## Install extras (all optional)

```bash
pip install 'crumb-llm[openai]'      # OpenAI SDK
pip install 'crumb-llm[anthropic]'   # Anthropic SDK
pip install 'crumb-llm[scratch]'     # EXPERIMENTAL local-from-scratch (torch)
```

## Verification

- Test suite: **24 passed** on Python 3.10 / 3.11 / 3.12.
- Built wheel declares **zero required dependencies**; `twine check` passes on
  both the wheel and sdist.
- CI installs the package with `crumb_format` import-blocked, parses a CRUMB via
  the bundled reader, and asserts `crumb_format` never enters `sys.modules`.

## Notes

- No models, checkpoints, or datasets are committed to this repo.
- Secrets are never stored: `crumblm setup` writes only non-secret routing
  (provider, model, base URL); API keys are read from environment variables at
  call time.

**Full changelog:** see [`CHANGELOG.md`](./CHANGELOG.md).
