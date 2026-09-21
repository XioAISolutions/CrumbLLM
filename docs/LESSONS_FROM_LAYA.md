# What Laya and Jev can teach CrumbLLM

*Written 2026-09-21, against `NandhaKishorM/laya` at commit `42626c3` and the CrumbLLM tree at `bad7461`.*

---

## The uncomfortable part, first

Laya reached **4,487 stars in three days**. CrumbLLM has **0**, `crumb-format` has **2**, and the ten repositories in the XIO AI Solutions organisation hold roughly **four stars between them**.

The gap is not a README gap. Laya shipped **weights** — a capability that did not previously exist in open form — and benchmarked them head-to-head against a named commercial product. CrumbLLM ships prompt templates around somebody else's model, over a file format that almost nobody has adopted. Copying Laya's README onto this repository would produce a better-looking repository with 0 stars.

So this document separates three things that get conflated whenever a project goes viral:

1. **What cannot be copied** — Laya's actual position in the market. Skip to [§2](#2-what-cannot-be-copied).
2. **What was borrowed, not created** — the demand Laya intercepted rather than generated. [§3](#3-what-was-borrowed-not-created)
3. **What is pure craft and transfers to any repository** — [§4](#4-what-transfers) — which is where the changes in this branch come from.

The honest read on the last one: the craft is worth doing and will not, by itself, produce 4,487 stars. It raises the ceiling on an event that has to come from somewhere else. [§6](#6-the-one-lever-that-actually-moves-this) says where that somewhere else could be for CrumbLLM, and what the odds look like.

---

## 1. What Laya and Jev actually are

**Jev** is TypeSafe AI's closed "System One" model. You hand it some state and a list of typed questions; it answers each one in parallel with a calibrated probability, a pick from options you defined, or a position on a scale you defined. Three primitives:

| primitive | returns |
|---|---|
| `choice` | one of up to 255 options you supply |
| `score` | a position on an ordinal rubric you define |
| `noul` | a calibrated probability in [0, 1] |

Roughly 100 ms per request, $0.042 per million input tokens, output free. It explicitly cannot count, do arithmetic, or reason about dates. It is sold for classification, routing, ranking, verification and guardrails — the decisions software makes, not the prose software writes.

**Laya** is the open-weights answer to it: the same three primitives, three Apache-2.0 checkpoints on Hugging Face (`laya` 421M / ModernBERT-large, `laya-multilingual` 322M / mmBERT-base, `laya-typed-decisions` 421M), plus a `Router` that picks between them per request by detecting the input's script in under half a millisecond of pure Python.

The published head-to-head:

| | Jev 1.13.0 | Laya (routed) |
|---|---|---|
| typed-decisions, 2,000 decisions | 0.727 | **0.766** |
| AG News, 4 labels | 0.910 | **0.950** |
| DAIR Emotion, 6 labels | 0.480 | **0.595** |
| Banking77, 72–77 labels | **0.870** | 0.425 |
| ECE *(lower better)* | 0.246 | **0.081** |
| p50 latency, one question | 236–276 ms | **32.8 ms** |
| weights | closed API | **Apache 2.0** |
| cost | $0.042 / 1M tokens | **$0 self-hosted** |

That table is the entire launch. Everything else in the repository exists to make it credible.

---

## 2. What cannot be copied

**Laya had a capability to give away, and a named incumbent to give it away against.** Two conditions, both hard:

*There was a thing people already wanted and could not have.* Jev is a paid API with closed weights. "Same primitives, Apache 2.0, 7× faster, self-hostable" is a complete pitch in one line, and it lands because somebody is already paying for the alternative. A project with no incumbent has to explain why the problem matters before it can explain why it solved it — and explaining that the problem matters is where almost every infrastructure project dies.

*The claim was falsifiable and someone could check it in an afternoon.* `pip install laya`, three lines of Python, a Colab badge, a Hugging Face Space. The distance from "saw the link" to "confirmed the claim myself" was minutes. A claim nobody can check is a claim nobody repeats.

**CrumbLLM satisfies neither today.** There is no incumbent charging money for CRUMB handoff analysis, because there is no category. And the central claim — "better handoffs" — was, before this branch, unfalsifiable: there was no number to check, and `crumblm analyze` on a fresh install printed `Mock analysis (no live provider configured).`

This is the structural finding. Everything in §4 is downstream of it.

---

## 3. What was borrowed, not created

Laya did not manufacture its audience. It intercepted one.

TypeSafe's Jev launch had already produced a wave: at least **six independently authored "awesome-jev" lists** exist on GitHub (`jexp`, `keltokhy`, `cobanov`, `yibie`, `Anil-matcha`, `miniLV`, plus `AbdelStark/awesome-typesafe`), and at least two independent benchmark repositories measuring Jev — `AbdelStark/jev-benchmarks` and `nibzard/decision-model-benchmark`. A named category with a paid incumbent, dozens of people already writing about it, and third-party numbers sitting there waiting to be cited.

Three consequences worth internalising:

**Laya never ran Jev.** `research/README.md` states it plainly: "There is no TypeSafe API credential in this project, so Jev was never run here." Every Jev figure is third-party published, with different sample sizes and prompts. Laya's entire competitive claim is built on **other people's measurements of the incumbent**, cited by name and link, with the methodological caveat stated up front. That is cheaper and more credible than running the comparison yourself, because the reader does not have to trust you about the half of the table that makes you look good.

**The vindication narrative carried the link.** The Dev.to article is titled *"I built non-autoregressive decision models a year ago, then a frontier lab called it a [System One model]"*. That is a priority claim plus an implicit endorsement from a bigger player. It is a story a reader can retell in one sentence, and retellability is what a link needs to travel. "I wrote a CRUMB analyser" is not retellable.

**The honesty section is a distribution asset, not a liability.** There is a commit literally titled `docs: add transparent acknowledgment of where Jev leads`. The README gives Jev a **Where Jev leads** section — Banking77 0.870 vs Laya's 0.425, soft accuracy 0.580 vs 0.471, better raw pre-temperature calibration — and BENCHMARKS.md opens its limits section with *"the base checkpoints are near chance on typed-decisions zero-shot."*

A sceptical reader who finds the weakness themselves discounts the whole table. A sceptical reader who finds it already disclosed, with the mechanism explained (options share a fixed `head_max_len` budget, so 77 labels get ~4 tokens each), upgrades their trust in everything else. **Laya's "Honest limits" section is doing more persuasive work than its headline number.**

That one is fully transferable, costs nothing, and is the single most under-used move in infrastructure READMEs.

---

## 4. What transfers

Everything in this section is craft. None of it requires weights, an incumbent, or a wave.

### 4.1 The first command must demonstrate the product, with nothing configured

Laya's quickstart returns a real routed decision, with a confidence and a machine-readable reason:

```python
res_hi["routing"]
# {'model': 'multilingual',
#  'reason': "non-Latin script (devanagari, 100% of letters); the English checkpoint cannot read it"}
```

CrumbLLM's first documented command returned this:

```text
Mock analysis (no live provider configured).
Configure a provider with `crumblm setup ...` to get real output.
```

Worse, that stub passed every quality gate the package advertises — it parses, it is long enough, and it matches no refusal phrase — so `AnalysisResult.ok` was `True` over a sentence that says nothing about the CRUMB. **The gate that exists to catch generic non-answers was passing the most generic non-answer the package can produce.**

*Fixed in this branch:* providers declare `is_stub`, and the engine emits a warning, so `ok` is `False` on stub output. And `crumblm score` now gives a fresh install something real to do with no key, no network and no configuration.

### 4.2 Ship a deterministic path, and refuse to overclaim it

The line doing the most work in Laya's README is: *"No text generation, so nothing to parse and nothing to hallucinate."*

CrumbLLM's equivalent asset was already in the repository and unreachable: the quality gates and the EJA audits are deterministic and need no model at all — but you could only reach them as a side effect of running an LLM. `crumblm score` makes that path primary: eight rules, 17 weight units, ~0.3 ms, no model, same bytes in and same number out forever.

The overclaim it deliberately avoids is instructive. Laya can call its outputs *calibrated probabilities* because it earned the right with an ECE figure on held-out data, and it still discloses that both base checkpoints ship over-confident and that `laya-multilingual` ships with **no fitted temperatures at all**. CrumbLLM's score has no model behind it, so it is weighted rule coverage and says so:

> A 0.82 means "14 of 17 weight units are satisfied". It does not mean "82% likely to succeed", and nothing here should be described that way.

Claiming less is what makes the smaller claim believable.

### 4.3 Publish the rules, not just the number

Every Laya routing decision carries a `reason` string. Every Laya benchmark ships with the raw JSON in `research/results/` and the harness in `research/scripts/`.

`crumblm score` follows the same shape: every rule prints the exact source lines it matched or rejected, `--explain` shows the evidence for passing rules too, `--format json` emits everything, and the weight table is published in the README so a reader can disagree with the rules rather than with the number. The latency claim ships with `research/bench_score.py` and the raw JSON it wrote.

### 4.4 A broken quickstart is worse than no quickstart

Laya's issue tracker on its viral days: **#21 "Can't reproduce Quickstart"** (closed), **#24 "invalid notebook"** (closed), **#34 "Quickstart Guide Incomplete"**. Those are the ones that cost real traffic, and they were closed in hours — seven tags, `v0.2.0` through `v0.3.4`, inside three days.

CrumbLLM's documented install was **broken for every user**, and CI could not see it:

```console
$ pip install git+https://github.com/XioAISolutions/CrumbLLM
ERROR: Could not find a version that satisfies the requirement crumb-format>=1.2.0 (from versions: 0.2.0)
```

`crumb_core` ships in `crumb-format` 1.2.0, which is merged but unpublished; PyPI still serves 0.2.0. Every CI job installed `crumb-format` from git *before* touching this package, so CI was green over an install path no stranger could complete. The README even asserted the dependency "is installed automatically" — the one sentence that was flatly false.

*Fixed in this branch:* the README documents the two commands that work today, between `<!-- install:start -->` markers; a new CI job extracts those exact commands, runs them in a clean virtualenv with no help from the other jobs, and then runs the README's first command. **The documentation can no longer rot while CI stays green.**

### 4.5 Keep the package small and the repository legible

Laya's importable package is **1,436 lines** across seven files. Everything else — benchmarks, notebooks, plots — sits outside it in `research/` and `notebooks/`, clearly marked *"nothing here is imported by the `laya` package."*

CrumbLLM is 5,605 lines, and **55% of that is CRUMB EJA** — a discovery-artifact format with its own schemas, audits, challenge protocols, calibration gates and synthesis lanes. EJA may well be the more interesting work. It is also a different product for a different audience, sharing a CLI and a README with the handoff analyser, and its presence roughly triples the surface a first-time reader has to parse before deciding whether this repository is for them.

*Addressed in this branch, and more cheaply than this section first estimated.* The estimate was "~a day". Grepping the imports first showed why it was wrong: **`crumb_llm/eja/` imported nothing from the rest of `crumb_llm`** — the entire coupling was one line in `cli.py`. So it became a top-level `crumb_eja` package with its own `crumb-eja` command, `crumblm eja ...` kept working for existing scripts, and a CI job now enforces that the decoupling holds. Moving it to its own repository is a `git mv` plus a `pyproject.toml`.

The lesson is not about EJA. **The cost estimate was wrong by an order of magnitude because it was made by reading the directory tree rather than the import graph**, and the same mistake is available on every "that would be a big refactor" in this repository.

### 4.6 Presentation details that cost nothing

Observed in Laya, absent here, cheap to add:

- **A Colab badge** — the shortest possible path from link to confirmed claim.
- **A hosted demo** (Laya has a Hugging Face Space) — for CrumbLLM the analogue is a paste-a-CRUMB-get-a-score page; the scorer is pure stdlib and small enough to run client-side.
- **A logo**, with a dark-mode variant via `<picture>`. Laya committed SVG sources and the generating script.
- **Absolute image URLs** in the README, so figures render on PyPI (`c369320 fix(docs): absolute image URLs so the figure renders on PyPI`).
- **A one-line description on the repository itself.** CrumbLLM's is empty. That string is what GitHub search, the org page, and every social embed show.
- **Dependabot and a secret-scanning workflow.** Laya committed a terminal transcript by accident (`31280fc security: remove terminal transcript committed by mistake`) and added a working-tree gitleaks scan in response.

---

## 5. What is done and what is left

Stated plainly, because a list of recommendations with the expensive ones quietly omitted is the same failure as a benchmark table with the losses omitted.

**Done since this document was first written:** the EJA decoupling ([§4.5](#45-keep-the-package-small-and-the-repository-legible)), the handoff benchmark harness and its first measurement ([§6](#6-the-one-lever-that-actually-moves-this)), a client-side demo of the scorer, a logo, and `RELEASE.md`.

**Left:**

| not done | why | cost |
|---|---|---|
| **Create the separate EJA repository** | the decoupling is done and CI-enforced; creating a public repository under the organisation is an outward-facing act, so it waits on the maintainer | ~20 minutes, now that it is a `git mv` |
| **Publish `crumb-format` 1.2.0 and `crumb-llm` to PyPI** | needs credentials no workflow here has; until then every install is a git URL, which roughly halves the people who will try it. The ordered checklist is now written down in [`RELEASE.md`](../RELEASE.md) — the step that cannot be automated is the only one left | ~an hour, by a human with upload rights |
| **Run the outcome benchmark** | the harness, the task format and the pre-registered protocol now exist in `research/handoff_benchmark/`; what is missing is an agent loop and an API budget | ~a week and a few dollars |
| **Calibrate the rule weights** | still no outcome dataset. The protocol's `crumb+score` arm is the one that would produce it, and if that arm does not beat plain `crumb`, the eight weights are measuring the wrong things and should change | blocked on the outcome run |
| **Make the demo public** | it exists and runs client-side; publishing it is a sharing decision, not an engineering one | minutes |
| **Split the EJA repository** | ✅ decoupled and CI-enforced; only the repository creation is left | ~20 minutes |

---

## 6. The one lever that actually moves this

Everything above raises the ceiling. None of it creates the event.

Laya's event was a measurable claim against a named incumbent. CrumbLLM has no incumbent — but it has access to something better, and nobody has published it:

> **Does structured handoff actually beat dumping the transcript?**

Every team running coding agents hits context exhaustion and hands off. Nobody has published a controlled comparison of how. The experiment is unglamorous and entirely runnable:

- Take *N* real multi-session tasks with verifiable completion criteria — a failing test that must pass.
- Truncate context at a fixed budget, then hand off three ways: **(a)** the raw transcript tail, **(b)** a model-written prose summary, **(c)** a CRUMB.
- Have a fresh agent continue from each. Measure task completion, turns-to-completion, and tokens consumed.
- Publish the harness, the raw JSON, and the per-task detail — Laya's `research/` layout, exactly.

Three properties make this the right bet:

1. **The result is interesting either way.** If CRUMB wins, that is the launch. If prose summaries win, that is a more surprising and more shareable finding, and it is the kind of honesty §3 shows compounds.
2. **It creates the number CrumbLLM lacks.** `crumblm score` currently has published weights and no calibration data. A handoff-outcome dataset is exactly what turns those weights from a stated judgement call into a fitted one — which is the difference between "we think these eight things matter" and "we measured which of these eight things predicts continuation."
3. **It reframes the whole stack.** CRUMB stops being a file format looking for adopters and becomes the thing that won a measured comparison.

**The honest odds:** [Guessing] a well-run benchmark with an interesting result is worth a few hundred stars and a Hacker News front page on a good day, not 4,487. Laya's number required an incumbent, a wave, and a vindication story, and at most one of those three is manufacturable. Aim at the benchmark because it is the right thing to build regardless of what it does for the star count — it is the only work here that also makes the product correct.

---

## Appendix: the two defects this analysis surfaced

Both were found by running the documentation rather than reading it, which is the §4.4 lesson applied to this repository.

**1. The documented install fails for every user.**

```console
$ pip install git+https://github.com/XioAISolutions/CrumbLLM
ERROR: Could not find a version that satisfies the requirement crumb-format>=1.2.0 (from versions: 0.2.0)
```

**2. The quality gate passed its own placeholder.**

```console
$ python -c "..."
text     : 'Mock analysis (no live provider configured).\nConfigure a pro'
warnings : []
result.ok: True
```

---

## Sources

- [`NandhaKishorM/laya`](https://github.com/NandhaKishorM/laya) — README, `BENCHMARKS.md`, `research/README.md`, commit log, issue tracker
- [`convaiinnovations/laya`](https://huggingface.co/convaiinnovations/laya) and the [demo Space](https://huggingface.co/spaces/convaiinnovations/laya-demo)
- [The Dev.to writeup](https://dev.to/nandakishor_m_6cc0adfde9f/i-built-non-autoregressive-decision-models-a-year-ago-then-a-frontier-lab-called-it-a-18me)
- Third-party Jev benchmarks: [`AbdelStark/jev-benchmarks`](https://github.com/AbdelStark/jev-benchmarks), [`nibzard/decision-model-benchmark`](https://github.com/nibzard/decision-model-benchmark)
- The `awesome-jev` ecosystem: [`cobanov/awesome-jev`](https://github.com/cobanov/awesome-jev), [`yibie/awesome-jev`](https://github.com/yibie/awesome-jev), [`jexp/awesome-jev-typesafe`](https://github.com/jexp/awesome-jev-typesafe), [`Anil-matcha/awesome-jev-by-typesafe`](https://github.com/Anil-matcha/awesome-jev-by-typesafe), [`AbdelStark/awesome-typesafe`](https://github.com/AbdelStark/awesome-typesafe)
