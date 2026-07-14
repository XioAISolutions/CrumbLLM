# CrumbLLM ↔ turbovec

This document covers two things:

1. **How CrumbLLM uses [turbovec](https://github.com/RyanCodrai/turbovec)** — the
   optional semantic-retrieval layer shipped in `crumb_llm/retrieval/`.
2. **A proposal for turbovec** — two patterns from CrumbLLM that would make
   turbovec a stronger RAG building block, written so it can be lifted into an
   upstream issue/PR.

The two projects solve complementary halves of the same problem. turbovec is a
fast, memory-efficient **retrieval** layer; CrumbLLM is a **reasoning** layer
with honesty/quality gates. They compose cleanly in both directions.

---

## 1. turbovec as CrumbLLM's retrieval backend

### The problem it solves

A CRUMB *pack* is a directory of `.crumb` files. The original engine
concatenated **every** file into one prompt (`CrumbPack.as_text()`). That is
fine for a handful of files, but a long-lived project accumulates hundreds of
session crumbs and the context blows past the model window — and pays for a lot
of irrelevant tokens.

`crumb_llm/retrieval/` adds semantic search so a task reasons only over the
**relevant slice** of a pack.

### Design

```
query ──► Embedder ──► VectorBackend.search(k) ──► top-k CrumbDocs ──► engine
                          │
            ┌─────────────┴──────────────┐
            │                            │
     TurboVecBackend              BruteForceBackend
   (turbovec installed)        (pure-Python fallback)
```

- **`HashingEmbedder`** (default) — dependency-free signed feature hashing into
  a fixed-length, L2-normalised vector. Deterministic and offline. Swap in a
  neural embedder by satisfying the `Embedder` protocol (`dim`, `embed(text)`).
- **`TurboVecBackend`** — wraps turbovec's online index (`TurboQuantIndex`
  inside an `IdMapIndex` for stable ids). Used automatically when `turbovec`
  imports cleanly.
- **`BruteForceBackend`** — exact cosine search in pure Python. The safe default
  when turbovec is not installed.
- **`get_backend()`** — prefers turbovec, falls back to brute force, and returns
  a warning explaining *why* the faster path was skipped. CrumbLLM never
  silently changes behaviour.

This mirrors CrumbLLM's existing philosophy: turbovec is an **optional**
dependency exactly like the OpenAI/Anthropic SDKs, and the package still runs
with zero dependencies.

### Usage

```bash
pip install crumb-llm            # works today, brute-force search
pip install turbovec             # opt in to quantized, memory-efficient search

# Rank a pack's files by relevance (no LLM call):
crumblm search ./pack --query "rate limiter 500s" --top-k 5

# Reason over only the relevant files of a large pack:
crumblm summarize ./pack --query "auth token expiry" --top-k 5
crumblm risks     ./pack --query "payment webhook" --top-k 8 --format json
crumblm next      ./pack --query "release blockers"
```

Library:

```python
from crumb_llm.crumb.pack_reader import read_pack
from crumb_llm.retrieval import focus_pack
from crumb_llm.engine import CrumbEngine

pack = read_pack("./pack")
focused, warnings = focus_pack(pack, "auth token expiry", k=5)
result = CrumbEngine().summarize(focused)
```

---

## 2. Proposal for turbovec

These are two patterns CrumbLLM already implements that would strengthen
turbovec as a RAG component. Neither requires changing turbovec's core index.

### 2a. A grounding/quality-gate hook for the RAG integrations

turbovec ships LangChain / LlamaIndex / Haystack integrations whose end goal is
feeding retrieved context to an LLM — but turbovec provides nothing to check
that the generated answer is actually grounded in what was retrieved.

CrumbLLM's `crumb_llm/evals/` does exactly this and is small and
dependency-free:

- `hallucination_check` — extracts file-path-like tokens from the model output
  and flags any that do **not** appear in the retrieved source.
- `json_check` — validates structured output.
- `check_generic_empty` — flags empty / "as an AI I can't…" non-answers.

**Suggestion:** a tiny optional `turbovec.evals` module (or a documented recipe)
that, given `retrieved_docs` and `answer`, returns grounding warnings. This
turns turbovec's RAG demos from "retrieve + hope" into "retrieve + verify" with
no new heavy dependencies — a strong differentiator for a retrieval library.

### 2b. An optional embedding-provider adapter

turbovec indexes vectors but leaves producing embeddings entirely to the user,
so every quickstart starts with boilerplate wiring of an embedding model.

CrumbLLM's `providers/base.py` is a good template: a thin `generate()` interface
over plain `urllib` with OpenAI/Anthropic/Ollama/LM Studio adapters and **zero
required SDKs**. The same shape works for embeddings:

```python
class Embedder(Protocol):
    dim: int
    def embed(self, text: str) -> list[float]: ...
```

**Suggestion:** an optional `turbovec.embed` with adapters for common providers
(behind extras, like `turbovec[openai]`), so a user can go text → vectors →
index in one pipeline. Keep it optional and stdlib-HTTP-based to preserve
turbovec's lean install.

---

## Why this is mutually reinforcing

- CrumbLLM gets scalable retrieval over large project memory and a real
  showcase of turbovec.
- turbovec gets a concrete "memory RAG" reference use case, plus two patterns
  (grounding checks, embedding adapters) that make it more useful out of the box
  without bloating its dependency footprint.
