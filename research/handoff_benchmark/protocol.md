# Outcome protocol — not yet run

This is the experiment worth running. It is written down before it is run so
that the design cannot be adjusted after the numbers are known, and so that
anyone with an API budget can run it without asking.

**Nothing in this file has been executed. There are no results to cite.**

## Question

Given a fixed context budget, does the *form* of a handoff change whether a
fresh agent completes the task?

## Design

**Tasks.** N ≥ 30 multi-session software tasks, each with:
- a repository at a known commit,
- a goal,
- a **verifiable completion check** — a command that exits non-zero before the
  work and zero after it. No human judging, no LLM judging.

Tasks should span the failure modes that matter: a task whose constraints are
stated only at the start; one whose key finding is a dead end already explored;
one where the verification command is non-obvious.

**Session 1.** One agent works each task under a fixed turn budget and stops
short of completion. Its transcript is captured. This session is identical
across all arms — the split happens after it.

**Handoff arms.** From that one transcript, produce:

| arm | production |
|---|---|
| `tail` | last B tokens, mechanically |
| `prose` | a model-written summary, prompted only to "summarise for the next agent", capped at B |
| `crumb` | a model-written CRUMB, capped at B |
| `crumb+score` | as `crumb`, but regenerated while `crumblm score` is below 0.6, up to 3 attempts |

The fourth arm is the one that tests this project's actual claim. If it does
not beat `crumb`, the scorer's rule weights are wrong and should be changed or
withdrawn.

**Session 2.** A fresh agent receives the repository and **only** the handoff —
no transcript, no session-1 memory. Same model, same turn budget, same tools
across arms. Run each arm k ≥ 5 times with different seeds.

## Metrics

Primary:
- **completion rate** — fraction of runs where the check command passes.

Secondary:
- **turns to completion**, and **tokens consumed** by session 2;
- **rediscovery cost** — turns spent re-deriving a fact the handoff could have
  carried, detected by matching session-2 tool calls against session 1's;
- **constraint violations** — completions that pass the check while breaking a
  declared constraint. A handoff that gets the job done by ignoring the bounds
  is not a success, and completion rate alone would score it as one.

## Pre-registered predictions

Recorded now so they can be wrong.

1. `tail` ≪ every authored arm on completion rate. *(Confidence: high. The
   retention measurement already shows the mechanism.)*
2. `crumb` ≈ `prose` on completion rate. *(Confidence: moderate. Retention
   found no separation at all, and prose was cheaper.)*
3. `crumb` < `prose` on tokens consumed. *(Confidence: moderate.)*
4. `crumb` > `prose` on **constraint violations avoided**, because a declared
   `[constraints]` section survives summarisation pressure that prose bullet
   points do not. *(Confidence: low — this is the real hypothesis, and the one
   most likely to be wrong.)*
5. `crumb+score` > `crumb` on completion rate. *(Confidence: low. If this
   fails, the eight rules in `crumb_llm/score.py` are not measuring what makes
   a handoff work.)*

## Reporting rules

- Publish the harness, the raw per-run JSON, and the per-task detail — not just
  a summary table.
- Report every arm, including the ones that lose.
- If `crumb` does not beat `prose`, **say so in the README headline**. That
  result is more interesting than the alternative, and burying it would make
  every other number in this repository worth less.

## Cost

Roughly 30 tasks x 4 arms x 5 seeds x 2 sessions = 1,200 agent runs. At a few
cents each this is a small number of dollars and a large number of hours. The
harness in `retention.py` shares the task fixture format, so a task written for
retention is already most of a task written for this.
