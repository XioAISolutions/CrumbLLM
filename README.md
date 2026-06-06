# CrumbLLM

**CrumbLLM is the local/cloud AI engine that reads CRUMB files, understands
project memory, and produces summaries, risks, next actions, PR notes, and
improved handoffs.**

It works fully offline against a local model, or against a cloud provider when
you want stronger reasoning. It never trusts model output blindly: every result
carries quality-gate warnings (hallucinated paths, invalid JSON, generic
non-answers).

```bash
pip install crumb-llm
crumblm analyze path/to/session.crumb
```

---

## What CrumbLLM is

- An **analysis engine** over CRUMB artifacts (single `.crumb` files and CRUMB
  *packs* — directories of CRUMB files).
- A set of focused tasks: **analyze, summarize, risks, next actions, improve
  handoff**.
- **Provider-agnostic**: OpenAI, Anthropic, Ollama, and LM Studio are adapters
  behind one interface. A fully-offline `mock` provider is the default so the
  package always runs without keys.
- **Standalone**: it bundles its own CRUMB reader, so `pip install crumb-llm`
  has **zero required dependencies** — nothing else is needed to read `.crumb`
  files.
- **Honest**: results include warnings; CrumbLLM never silently trusts a model.

## What CrumbLLM is *not*

- **Not the CRUMB spec authority.** The canonical format, grammar, validator,
  linter, and base CLI live in
  [`crumb-format`](https://github.com/XioAISolutions/crumb-format). CrumbLLM
  ships its own small, faithful reader for the CRUMB wire format and uses it
  exclusively, so it is fully independent of `crumb-format`.
- **Not session capture.** Capturing IBM Bob sessions and *generating* CRUMB
  packs is [`Crumb-Bob`](https://github.com/XioAISolutions)'s job. CrumbLLM only
  *reads* packs; it contains no Bob-specific logic.
- **Not a training framework.** CrumbLLM does **not** train a model by default.
  An experimental from-scratch path exists for power users (see below).

## How it relates to crumb-format and Crumb-Bob

```
                   ┌────────────────────────────────────────────┐
                   │ crumb-format                                │
                   │   CRUMB spec • parser • validator • linter  │
                   │   base `crumb` CLI                          │
                   └────────────────────────────────────────────┘
                          (canonical spec — separate project)

        capture & generate                          read & reason
   ┌──────────────┐        ┌───────────────┐        (this repo)
   │  Crumb-Bob   │ ─────▶ │  .crumb files │ ─────▶ ┌─────────────┐
   │ IBM Bob      │  packs │   & packs     │        │  CrumbLLM   │
   │ session cap. │        └───────────────┘        │  analysis   │
   └──────────────┘                                 └─────────────┘
```

- **crumb-format** is the canonical home of the spec and the validation/linting
  primitives. CrumbLLM tracks the same wire format but does **not** depend on it.
- **Crumb-Bob** turns IBM Bob sessions into `.crumb` files and packs.
- **CrumbLLM** (this package) reads those artifacts and produces AI analysis.

CrumbLLM reads CRUMB through `crumb_llm/crumb/parser_adapter.py`, which uses its
own bundled reader (`crumb_llm/crumb/spec.py`) exclusively. It never imports,
prefers, or requires `crumb-format`.

---

## Install

```bash
pip install crumb-llm                  # independent — zero required deps
pip install 'crumb-llm[openai]'        # optional OpenAI SDK (not required)
pip install 'crumb-llm[anthropic]'     # optional Anthropic SDK (not required)
pip install 'crumb-llm[scratch]'       # EXPERIMENTAL local-from-scratch (torch)
```

Cloud and local-server providers talk plain HTTP over the standard library, so
no SDK is strictly required.

---

## Local vs cloud providers

| Provider   | Type        | Needs a key?            | Default endpoint                       |
|------------|-------------|-------------------------|----------------------------------------|
| `mock`     | offline     | no                      | — (built-in, default)                  |
| `ollama`   | local       | **no**                  | `http://localhost:11434/api/generate`  |
| `lmstudio` | local       | **no**                  | `http://localhost:1234/v1`             |
| `openai`   | cloud       | `OPENAI_API_KEY`        | `https://api.openai.com/v1`            |
| `anthropic`| cloud       | `ANTHROPIC_API_KEY`     | `https://api.anthropic.com/v1`         |
| `scratch`  | local (exp) | no (needs torch + ckpt) | —                                      |

**The package works without any cloud key** by using a local provider
(`ollama`/`lmstudio`) or the built-in `mock`.

> 🔒 **Secrets are never stored.** `crumblm setup` writes only non-secret routing
> (provider, model, base URL) to `~/.config/crumb-llm/config.json`. API keys are
> read from environment variables at call time and are never written to disk or
> any database.

### Configure a provider

```bash
crumblm setup openai    --model gpt-4o-mini
crumblm setup anthropic --model claude-sonnet-4-6
crumblm setup local --backend ollama   --model llama3.1
crumblm setup local --backend lmstudio --model my-local-model
crumblm status            # shows config + whether the key env var is present
```

---

## Usage

```bash
# Analyze a single CRUMB file
crumblm analyze examples/basic.crumb

# Analyze a whole CRUMB pack (a directory of .crumb files, e.g. from Crumb-Bob)
crumblm analyze-pack examples/pack

# Summarize project memory to a file
crumblm summarize examples/pack --out summary.md

# Classify risks as text or JSON
crumblm risks examples/basic.crumb --format text
crumblm risks examples/pack       --format json

# What should the next agent/human do?
crumblm next examples/pack

# Tighten a handoff so the next agent can act with zero ambiguity
crumblm improve examples/basic.crumb --out improved.txt
```

Every command accepts either a `.crumb` file or a pack directory where
`<crumb_or_pack>` is shown. Warnings (hallucinated paths, invalid JSON, empty
responses) are printed to **stderr** and included in `--format json` output.

### Example: analyze a pack

```bash
$ crumblm analyze-pack examples/pack
**Summary** — Two linked sessions on the storefront checkout latency
regression...
**Risks** — Rounding drift if tax batching changes per-item values...
**Next actions** — 1. Add compute_tax_batch() in src/checkout/tax.py ...
```

---

## Semantic retrieval over large packs (optional turbovec)

Long-lived projects accumulate hundreds of CRUMB files. Instead of stuffing the
whole pack into one prompt, narrow it to the files relevant to a query with
`--query`:

```bash
# Rank a pack's files by relevance — pure retrieval, no model call:
crumblm search examples/pack --query "checkout latency" --top-k 5

# Reason over only the relevant slice of a large pack:
crumblm summarize examples/pack --query "tax rounding" --top-k 5
crumblm risks     examples/pack --query "payment webhook" --format json
```

Retrieval is **zero-dependency by default** (a built-in feature-hashing embedder
plus exact pure-Python cosine search). Install
[turbovec](https://github.com/RyanCodrai/turbovec) to transparently switch to
its memory-efficient quantized index for large packs:

```bash
pip install turbovec     # optional, like the provider SDKs
```

CrumbLLM never silently changes behaviour: when turbovec is absent it falls back
to brute force and says so on stderr. See
[`docs/turbovec-integration.md`](docs/turbovec-integration.md) for the design
and a reciprocal proposal for the turbovec project.

---

## Quality gates

CrumbLLM **never silently trusts model output**. Each result is an
`AnalysisResult` with a `warnings` list, populated by:

- **JSON validity** — when JSON output is requested, the response must parse.
- **Hallucinated paths** — file paths in the output are compared against the
  paths that actually appear in the source CRUMB; ungrounded paths are flagged.
- **Generic / empty answers** — empty, too-short, or boilerplate "as an AI…"
  responses are flagged.

```python
from crumb_llm.crumb.loader import load_crumb
from crumb_llm.engine import CrumbEngine

result = CrumbEngine().analyze(load_crumb("examples/basic.crumb"))
print(result.text)
print(result.warnings)   # [] when clean
print(result.ok)         # True when no gate fired
```

---

## Export training data

You can export a directory of CRUMB files as a JSONL dataset (plain-LM records
plus instruction/input/output records for SFT):

```bash
crumblm export-dataset path/to/crumbs --out data/crumb_training.jsonl
```

Then optionally prepare it for supervised fine-tuning:

```python
from crumb_llm.training.prepare_sft import prepare_sft
prepare_sft("data/crumb_training.jsonl", "data/sft.txt", tokenize=True)
```

No datasets, models, or checkpoints are committed to this repo.

---

## ⚠️ Scratch models are experimental

The `scratch` provider and `crumb_llm/training/train_scratch.py` implement a
**tiny, experimental, from-scratch transformer** (cannibalized from
[FareedKhan-dev/train-llm-from-scratch](https://github.com/FareedKhan-dev/train-llm-from-scratch)).

- It is **not** installed by default (`pip install 'crumb-llm[scratch]'`).
- CrumbLLM **never trains automatically** — training requires an explicit
  `confirm=True`.
- The scratch provider **fails gracefully** when torch or a checkpoint is
  missing.
- Quality is not production-grade. Use a cloud or local-server provider for real
  work; treat scratch as a research toy.

---

## License

MIT © XIO AI Solutions
