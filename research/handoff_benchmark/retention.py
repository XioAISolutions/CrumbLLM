"""Measure what survives a handoff, at a fixed budget.

This answers a **proxy** question, and the distinction matters more than the
numbers do.

The question worth answering is *does a structured handoff let a fresh agent
finish the job more often than dumping the transcript?* Answering that needs an
agent loop, real repositories, and a verifiable completion check — the protocol
for it is in `protocol.md`, and it has **not been run**. Nothing in this module
should be quoted as if it had been.

What this module measures instead is **fact retention under a token budget**:
given the facts session 2 provably needs, declared in the task fixture before
any handoff was written, how many of them survive each handoff strategy when
all strategies are capped at the same budget?

That is a ceiling, not an outcome. Retaining a fact is necessary for using it
and nowhere near sufficient. A handoff can carry every fact and still be
unusable, which is exactly why the outcome benchmark is the real deliverable.

Two biases are deliberate and stated rather than corrected, because correcting
them would mean pretending to a rigour this measurement does not have:

1. **The prose and CRUMB handoffs in the fixtures are hand-authored.** This
   measures what each format can hold at a budget, not what an agent would
   actually write. A model-written summary is the honest baseline and belongs
   in the outcome benchmark.
2. **Matching is substring, case-folded.** A handoff that names
   `src/gateway/middleware.py` scores the fact whether or not it says anything
   useful about it. This inflates every strategy, and it inflates the verbose
   ones most.

The `tail` strategy is not a fixture. It is computed from the transcript at run
time by keeping the last N tokens, because that is what dumping a transcript
actually does — and the reason it loses is structural: constraints get stated
at the *start* of a session and truncation eats the start.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Token approximation: words and standalone punctuation. This is NOT a model
#: tokenizer, and every "tokens" figure this module reports is approximate.
#: It is used only to give all three strategies the *same* budget, which is a
#: comparison it is adequate for; it is not adequate for a cost claim.
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def count_tokens(text: str) -> int:
    """Approximate token count. See the module note — not a model tokenizer."""
    return len(_TOKEN_RE.findall(text or ""))


def truncate_to_budget(text: str, budget: int) -> str:
    """Keep the LAST ``budget`` tokens — what dumping a transcript gives you."""
    positions = [m.start() for m in _TOKEN_RE.finditer(text or "")]
    if len(positions) <= budget:
        return text
    # Slice the original text at the start of the first kept token, so the
    # excerpt reads as real text rather than a rejoined token list.
    return text[positions[len(positions) - budget]:]


@dataclass
class FactResult:
    id: str
    kind: str
    retained: bool
    why: str


@dataclass
class StrategyResult:
    """One handoff strategy measured against one task."""

    strategy: str
    tokens: int
    budget: int
    over_budget: bool
    facts: list[FactResult] = field(default_factory=list)

    @property
    def retained(self) -> int:
        return sum(1 for f in self.facts if f.retained)

    @property
    def total(self) -> int:
        return len(self.facts)

    @property
    def retention(self) -> float:
        return self.retained / self.total if self.total else 0.0

    @property
    def density(self) -> float:
        """Retained facts per 100 approximate tokens."""
        return (100.0 * self.retained / self.tokens) if self.tokens else 0.0

    def missing(self) -> list[FactResult]:
        return [f for f in self.facts if not f.retained]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "tokens": self.tokens,
            "budget": self.budget,
            "over_budget": self.over_budget,
            "retained": self.retained,
            "total": self.total,
            "retention": round(self.retention, 3),
            "facts_per_100_tokens": round(self.density, 2),
            "missing": [
                {"id": f.id, "kind": f.kind, "why": f.why} for f in self.missing()
            ],
        }


#: Markdown emphasis and line wrapping break substring matching on text that
#: does contain the fact. The first version of this module scored the
#: transcript tail as having lost `ordering_trap` even when given the whole
#: transcript, purely because the source said `must run *before* the limiter`
#: and the alias said `before the limiter`. That artifact biased the baseline
#: down, which is the direction a measurement's bugs are least likely to be
#: noticed in, so matching normalises both sides first.
_EMPHASIS_RE = re.compile(r"[*_`]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Fold case, strip markdown emphasis, collapse whitespace and line wraps."""
    return _WHITESPACE_RE.sub(" ", _EMPHASIS_RE.sub("", (text or "").lower())).strip()


def fact_present(fact: dict, handoff_text: str) -> bool:
    """Normalised substring match on the fact's `match` or any alias."""
    haystack = normalise(handoff_text)
    candidates = [fact["match"]] + list(fact.get("aliases", []))
    return any(normalise(c) in haystack for c in candidates if c)


def measure(handoff_text: str, task: dict, strategy: str, budget: int) -> StrategyResult:
    """Score one handoff against one task's declared critical facts."""
    tokens = count_tokens(handoff_text)
    results = [
        FactResult(
            id=fact["id"],
            kind=fact["kind"],
            retained=fact_present(fact, handoff_text),
            why=fact["why"],
        )
        for fact in task["critical_facts"]
    ]
    return StrategyResult(
        strategy=strategy,
        tokens=tokens,
        budget=budget,
        over_budget=tokens > budget,
        facts=results,
    )


def load_task(task_dir: str | Path) -> tuple[dict, Path]:
    root = Path(task_dir)
    task = json.loads((root / "task.json").read_text(encoding="utf-8"))
    return task, root


def run_task(task_dir: str | Path, budget: int) -> dict[str, Any]:
    """Measure every strategy for one task at one budget.

    ``budget`` is applied to ``tail`` by truncation. The authored handoffs are
    not truncated — they are reported with their own token counts and an
    ``over_budget`` flag, because silently trimming them would make the
    comparison meaningless. A fixture whose authored handoffs exceed the budget
    is a broken fixture, and the runner says so.
    """
    task, root = load_task(task_dir)
    transcript = (root / task["transcript"]).read_text(encoding="utf-8")

    results = [
        measure(truncate_to_budget(transcript, budget), task, "tail", budget)
    ]
    for name, filename in task["handoffs"].items():
        text = (root / filename).read_text(encoding="utf-8")
        results.append(measure(text, task, name, budget))

    return {
        "task": task["id"],
        "goal": task["goal"],
        "budget_tokens": budget,
        "transcript_tokens": count_tokens(transcript),
        "critical_facts": len(task["critical_facts"]),
        "strategies": [r.to_dict() for r in results],
        "measures": "fact retention under a token budget — a proxy, not task completion",
    }
