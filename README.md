# CrumbLLM 🥖🧠

<p align="center">
  <strong>Score a handoff before you trust it. Deterministically, in 0.3&nbsp;ms, with no model at all.</strong>
</p>

<p align="center">
  <a href="https://github.com/XioAISolutions/CrumbLLM/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/XioAISolutions/CrumbLLM/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="One dependency" src="https://img.shields.io/badge/required%20dependencies-1-53f2a3">
  <img alt="MIT" src="https://img.shields.io/badge/license-MIT-8b5cf6">
</p>

> **Looking for context routing and token optimization?** CrumbContext now lives in its own standalone repository: [`XioAISolutions/CrumbContext`](https://github.com/XioAISolutions/CrumbContext).

CrumbLLM reads `.crumb` files — the portable AI handoff format — and answers one question well: **can the next agent actually continue from this?**

It answers it twice, along two deliberately separate paths.

| | `crumblm score` | `crumblm analyze` and friends |
|---|---|---|
| needs a model | **no** | yes |
| needs a key or network | **no** | yes, unless local |
| same input → same output | **always** | no |
| latency | **0.3 ms** | seconds |
| tells you | which parts of the handoff are missing, and why | prose, risks, next actions, better handoffs |

The scoring path is the one to reach for first. It cannot hallucinate, because it never generates.

---

## Quickstart

<!-- install:start -->
```bash
# crumb-format 1.2.0 is not on PyPI yet (the index still serves 0.2.0), so both
# installs come from git today. CI runs these exact two lines on every commit.
pip install "crumb-format @ git+https://github.com/XioAISolutions/crumb-format@main"
pip install "git+https://github.com/XioAISolutions/CrumbLLM"
```
<!-- install:end -->

```bash
crumblm score examples/weak-handoff.crumb
```

```text
weak-handoff.crumb
  readiness  0.29  [######..............]  unusable
             the next agent would have to reconstruct the task from scratch
  kind       unknown

  [FAIL] goal_stated (weight 2) — [goal] is 18 characters — a title, not an outcome
         | Make login better.
  [FAIL] context_anchored (weight 3) — [context] is prose with no file, symbol, commit, ticket or URL to open
         | We talked about this yesterday and agreed the current approach is not great.
         | The team knows the background. Someone should clean it up before the release.
         | Make login better.
  [PASS] constraints_declared (weight 2) — 1 constraint line(s) declared
  [PASS] next_step_actionable (weight 3) — 2 actionable directive(s)
  [FAIL] ownership_assigned (weight 1) — 2 of 2 directive(s) name no to= owner
         | - do=clean up the auth code in src/auth/session_store.py
         | - do=probably also look at the middleware
  [FAIL] verification_defined (weight 3) — nothing states how to tell the work succeeded — no test, check or acceptance bound
         | - do=clean up the auth code in src/auth/session_store.py
         | - do=probably also look at the middleware
  [FAIL] progress_recorded (weight 1) — no [x] markers and no log — the next agent cannot tell what was already tried
  [FAIL] references_resolvable (weight 2) — 1 path(s) cited as work but grounded nowhere
         | src/auth/session_store.py — cited in a next step but never grounded: - do=clean up the auth code in src/auth/session_store.py

  5/17 weight units satisfied
```

No API key was set. No model ran. No network call was made. Run it again on a different machine and you get the same 0.29.

Measured at **0.30 ms p50** end to end — parse from disk plus score, 200 iterations, Python 3.11 on an x86-64 Linux container (`score_doc` alone: 0.24 ms p50, 0.32 ms p95 over 1,000 iterations). Reproduce with [`research/bench_score.py`](research/bench_score.py); the raw numbers are in [`research/score_latency.json`](research/score_latency.json). Every figure in this README is measured on the machine that ran CI, not estimated.

---

## Gate it in CI

`--min` turns readiness into an exit code, which is the whole point of a deterministic score:

```bash
crumblm score handoff.crumb --min 0.6   # exit 1 when the handoff is too thin to hand over
```

```yaml
- name: Handoffs must be usable
  run: crumblm score .crumb/ --min 0.6
```

```bash
crumblm score examples/pack --format json   # machine-readable, every rule and its evidence
```

---

## The rule table

Eight rules, 17 weight units, all of them public and all of them arguable. Weight 3 means the handoff is unusable without it; weight 1 is bookkeeping that makes review cheaper.

| rule | weight | fails when |
|---|---:|---|
| `goal_stated` | 2 | there is no `[goal]`, or it is under 20 characters — a title, not an outcome |
| `context_anchored` | 3 | `[context]` is prose with no file, symbol, commit, ticket or URL to open |
| `constraints_declared` | 2 | nothing says what the next agent must not break |
| `next_step_actionable` | 3 | `[handoff]` carries no `do=` directive |
| `ownership_assigned` | 1 | a `do=` directive names no `to=` owner |
| `verification_defined` | 3 | nothing states how to tell the work succeeded |
| `progress_recorded` | 1 | no `[x]` markers and no log — you cannot tell what was already tried |
| `references_resolvable` | 2 | a path is cited as work but appears nowhere in context and is not declared new |

Readiness is `earned weight / 17`, reported in four bands: **unusable** (<0.35), **thin** (<0.60), **usable** (<0.85), **strong**.

Packs get one extra check that documents cannot have on their own — `chain_continuity`, whether each session references an artifact from an earlier one. A pack whose sessions share nothing is a folder, not a memory. The pack score reports the **weakest** document rather than the mean, because a reader hits every document and one unusable link stops them.

### What the number is not

It is weighted rule coverage, not a probability. A 0.82 means "14 of 17 weight units are satisfied". It does **not** mean "82% likely to succeed", and nothing here should be described that way.

That distinction is the reason this path needs no calibration evidence: a system that scores with a model owes you an ECE figure on held-out data before you branch on its confidence. A checklist with arithmetic owes you the checklist, which is above.

### Honest limits

- **The rules check structure, not truth.** A handoff can cite `src/gateway/server.py`, score `strong`, and still be wrong about what that file does. `context_anchored` proves an anchor exists; it does not open it.
- **The weights are a judgement call**, not a fit to a benchmark. There is no published handoff-outcome dataset to fit them to. Disagree with them by reading the table above, not by trusting the number.
- **`verification_defined` is keyword-driven** and will miss a definition of done phrased in words it does not know.
- **`handoff_kind` is a keyword vote** and is descriptive only — it carries no weight in the score.
- **`references_resolvable` reads paths, not repositories.** It cannot tell you that `src/gateway/server.py` was deleted last week.

---

## The model path

Everything below needs a provider. Each result carries the warnings its quality gates raised, and `result.ok` is False whenever any fired.

```bash
crumblm analyze examples/basic.crumb            # one CRUMB
crumblm analyze-pack examples/pack              # a whole pack
crumblm summarize examples/pack --out summary.md
crumblm risks examples/pack --format json
crumblm next examples/pack
crumblm improve examples/basic.crumb --out improved.txt
crumblm export-dataset path/to/crumbs --out data/crumb_training.jsonl
```

Without a configured provider these run against a built-in stub and say so:

```text
warning: provider 'mock' returns placeholder text, not analysis — run
`crumblm setup` to configure a real provider, or `crumblm score` for a result
that needs no model
```

Configure a real one:

```bash
crumblm setup local --backend ollama --model <local-model>
crumblm setup local --backend lmstudio --model <local-model>
crumblm setup openai --model <model>
crumblm setup anthropic --model <model>
crumblm status
```

| Provider | Runs where | Key required? |
|---|---|---:|
| `mock` | built in (stub output, always warns) | no |
| `ollama` | local server | no |
| `lmstudio` | local server | no |
| `openai` | cloud | yes |
| `anthropic` | cloud | yes |
| `scratch` | local experimental model | no |

> 🔒 Provider keys are read from environment variables at call time. `crumblm setup` stores only non-secret routing configuration.

Optional SDK extras (the providers work over stdlib HTTP without them):

```bash
pip install 'crumb-llm[openai] @ git+https://github.com/XioAISolutions/CrumbLLM'
pip install 'crumb-llm[anthropic] @ git+https://github.com/XioAISolutions/CrumbLLM'
pip install 'crumb-llm[scratch] @ git+https://github.com/XioAISolutions/CrumbLLM'
```

### Quality gates

CrumbLLM never treats model output as automatically trustworthy. Every `AnalysisResult` carries warnings from:

- **stub detection** — a provider that returns canned text is never reported as `ok`;
- **JSON validity** — structured output must parse;
- **hallucinated paths** — paths in the output are compared against paths in the source CRUMB;
- **empty or generic output** — boilerplate and unusably short answers are flagged.

```python
from crumb_llm import score_doc
from crumb_llm.crumb.loader import load_crumb
from crumb_llm.engine import CrumbEngine

doc = load_crumb("examples/basic.crumb")

readiness = score_doc(doc)          # no model
print(readiness.score, readiness.band)
for signal in readiness.failed:
    print(signal.id, "—", signal.reason)

result = CrumbEngine().analyze(doc)  # model
print(result.text, result.warnings, result.ok)
```

---

## CRUMB EJA

CrumbLLM also carries **CRUMB EJA**, a separate discovery-artifact format with its own validators, audits, and review bundles. It shares the CLI but nothing else — different format, different claims, different audience.

```bash
crumblm eja validate examples/einstein-elevator.eja.json
crumblm eja audit-pack artifacts --out artifacts/eja-audit.json
```

Full documentation: [`crumb_llm/eja/README.md`](crumb_llm/eja/README.md).

---

## How the CRUMB projects fit together

```text
Crumb-Bob ──captures sessions──▶ .crumb files and packs
                                      │
crumb-format ──specifies + validates──┤
                                      ▼
CrumbContext ──routes + protects──▶ model-ready context
                                      │
                                      ▼
CrumbLLM ──scores · summarizes · checks · plans · improves handoffs
```

| Project | Responsibility |
|---|---|
| [`crumb-format`](https://github.com/XioAISolutions/crumb-format) | canonical format, parser (`crumb_core`), validator, linter, base CLI |
| [`Crumb-Bob`](https://github.com/XioAISolutions/Crumb-Bob) | session capture and CRUMB generation |
| [`CrumbContext`](https://github.com/XioAISolutions/CrumbContext) | safety-first context routing and exact-anchor protection |
| **CrumbLLM** | readiness scoring and local/cloud reasoning over CRUMB files and packs |

The CRUMB grammar lives exactly once, in `crumb_core`. CrumbLLM used to fork it; that fork drifted, and deleting it is why `crumb-format` is now a real dependency.

## What CrumbLLM is not

- It is not the canonical CRUMB specification.
- It does not capture sessions.
- It does not automatically train models.
- Its experimental scratch model is not production-grade.
- It does not replace CrumbContext's routing and exactness layer.
- Its readiness score is not a prediction of whether the work will succeed.

## Development

```bash
git clone https://github.com/XioAISolutions/CrumbLLM.git
cd CrumbLLM
pip install "crumb-format @ git+https://github.com/XioAISolutions/crumb-format@main"
python -m pip install -e '.[dev]'
pytest
crumblm score examples/weak-handoff.crumb
```

CI tests Python 3.10–3.12, enforces that parsing goes through `crumb_core` with no vendored fork, builds the distribution, checks the wheel's dependency surface, and — in a job of its own — **runs the install commands from this README verbatim in a clean environment**, so the quickstart cannot rot while CI stays green.

## Contributing

Useful contributions include:

- new scoring rules, with the failure they catch and a test that fails without them;
- a counter-example CRUMB that the current rules score wrongly;
- stronger quality gates on the model path;
- additional provider adapters;
- better pack-level reasoning.

Keep CrumbLLM focused on reading and judging CRUMB artifacts. Context routing belongs in [`CrumbContext`](https://github.com/XioAISolutions/CrumbContext); grammar and validation belong in [`crumb-format`](https://github.com/XioAISolutions/crumb-format).

## License

MIT © XIO AI Solutions
