# Handoff benchmark

> **The headline result is not the one this project wanted.** At an equal token
> budget, a hand-written prose summary retains exactly as many critical facts
> as a CRUMB, and does it in 13% fewer tokens. The only thing this measurement
> separates is *someone wrote a handoff* from *someone dumped the transcript* —
> and there the gap is large.

Nothing here is imported by the `crumb_llm` package.

---

## What is measured, and what is not

Two different questions, kept apart on purpose.

| | question | status |
|---|---|---|
| **Outcome** | does a structured handoff let a fresh agent *finish the job* more often? | protocol written, **not run** — [`protocol.md`](protocol.md) |
| **Retention** | at a fixed token budget, how many of the facts the next agent needs *survive*? | run, results below |

Retention is a **proxy and a ceiling**. Carrying a fact is necessary for using
it and nowhere near sufficient: a handoff can contain every fact and still be
unusable. No retention number should ever be quoted as a completion rate.

```bash
python research/handoff_benchmark/run.py                 # default budget 320
python research/handoff_benchmark/run.py --budget 200
python research/handoff_benchmark/run.py --out results.json
```

## Protocol, in brief

One task fixture holds a real multi-turn session transcript (785 approximate
tokens), and **16 critical facts declared before any handoff was written** —
the paths, constraints, traps, findings and verification command that session 2
provably needs. A CI test asserts that declaration order, because a fact
written after the handoff it scores is not evidence.

Three handoff strategies are scored against those facts:

| strategy | how it is produced |
|---|---|
| `tail` | the last N tokens of the transcript, computed at run time — what dumping a transcript actually gives you |
| `prose` | a hand-written prose summary |
| `crumb` | a hand-written CRUMB |

The budget is applied to `tail` by truncation. The authored handoffs are
**never silently trimmed to fit** — they are reported with their real token
counts and an `over_budget` flag, because quietly trimming them would hide a
broken fixture.

## Results

Budget 320 tokens, chosen so that **the baseline gets more room than either
authored handoff** (prose is 281 tokens, CRUMB is 317). The comparison is
deliberately tilted toward the transcript.

| strategy | tokens | facts retained | retention | facts / 100 tokens |
|---|---:|---:|---:|---:|
| `tail` | 320 | 9 / 16 | 0.562 | 2.81 |
| `prose` | 281 | **16 / 16** | **1.000** | **5.69** |
| `crumb` | 317 | **16 / 16** | **1.000** | 5.05 |

Across budgets, `tail` only:

| budget | 100 | 200 | 320 | 500 | 785 (whole transcript) |
|---|---:|---:|---:|---:|---:|
| facts retained | 2 / 16 | 5 / 16 | 9 / 16 | 12 / 16 | 16 / 16 |

Raw JSON: [`results/retention_sweep.json`](results/retention_sweep.json).

### What the transcript loses, and why it is not random

At budget 200 the tail has lost every **constraint** — "do not break the
response schema", "no dependencies beyond redis-py" — along with all four file
paths and the reproduction commit.

That is structural, not bad luck. Constraints get stated **at the start of a
session**, and truncating a transcript eats the start. The facts most expensive
to rediscover are the ones truncation takes first.

### Where CRUMB loses

* **It is not distinguishable from good prose here.** Both retain 16/16. This
  fixture measures a ceiling that both formats hit, so it supports no claim
  that structure beats prose. A test asserts this tie so the write-up cannot
  quietly drift into claiming otherwise.
* **It costs 13% more tokens for the same facts** — 317 against 281, and 5.05
  facts per 100 tokens against prose's 5.69. Section headers are not free.
* **Its advantages are untested here.** Machine-readability, `crumblm score`,
  diffability and continuity across a pack are real differences from prose, and
  *none* of them is what retention measures.

## Honest limits

- **N = 1.** One task, one domain, one author. Treat the direction as
  suggestive and the magnitude as meaningless.
- **The prose and CRUMB handoffs are hand-authored**, so this measures what
  each format can hold at a budget, not what an agent would write. A
  model-written summary is the honest baseline and belongs in the outcome run.
- **Matching is normalised substring.** Naming `src/gateway/middleware.py`
  scores the fact whether or not the handoff says anything useful about it.
  This inflates every strategy, and inflates verbose ones most.
- **The tokenizer is a regex**, not a model tokenizer. It is adequate for
  giving three strategies the same budget; it is not adequate for a cost claim.
- **The result that matters is still unrun.** Retention is a ceiling. See
  [`protocol.md`](protocol.md).

## Contributing a task

The most useful contribution is a fixture whose facts **break the prose/CRUMB
tie** — in either direction. Add a directory under `tasks/` with a
`transcript.md`, a `task.json` declaring the critical facts, and one file per
authored handoff. Declare the facts first.
