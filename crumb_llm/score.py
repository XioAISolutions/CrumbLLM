"""Deterministic handoff scoring — the no-model path.

Every other command in this package asks a language model a question and then
checks whether the answer can be trusted. This module asks nothing. It reads a
CRUMB and computes, from fixed rules, whether the next agent has what it needs
to continue: a stated goal, context anchored to real artifacts, declared
constraints, an actionable next step, an owner, a way to verify the result, and
references that resolve.

Three deliberate properties, in order of importance:

**No model, so no calibration claim.** The numbers here are coverage scores —
weighted rule hits divided by total weight — not probabilities. A 0.82 means
"14 of 17 weight units of the checklist are satisfied"; it does not mean "82%
likely to succeed", and nothing in this module should ever be described that
way. Systems that score with a model have to earn their numbers with
calibration evidence (an ECE figure on held-out data). A checklist with
arithmetic does not, because it is claiming much less.

**Deterministic.** Same bytes in, same score out, forever. No temperature, no
network, no keys, no GPU. This is what makes the score usable as a CI gate:
``crumblm score handoff.crumb --min 0.6`` fails a pull request the same way on
every machine.

**Auditable.** Every signal carries the exact source lines that produced its
verdict, so a score is never a number you have to take on faith. ``--explain``
prints the evidence for each rule, pass or fail.

The rule weights below are a judgement call, stated openly rather than tuned
against a benchmark that does not exist yet. They encode one claim: a handoff
fails most often because the next step is vague, the context cites nothing
concrete, or there is no way to tell when the work is done — so those three
carry weight 3, and the bookkeeping signals carry 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from crumb_llm.models import CrumbDoc, CrumbPack, extract_file_paths

# --------------------------------------------------------------------------
# the rule table
# --------------------------------------------------------------------------

#: Signal id -> (weight, one-line description). The weights are the whole
#: opinion of this module, so they live in one place where they can be argued
#: with. Weight 3 = the handoff is unusable without it; 2 = the next agent will
#: have to guess; 1 = bookkeeping that makes review cheaper.
WEIGHTS: dict[str, tuple[int, str]] = {
    "goal_stated": (2, "a [goal] section states what outcome is wanted"),
    "context_anchored": (3, "[context] cites at least one concrete artifact"),
    "constraints_declared": (2, "[constraints] lists at least one real bound"),
    "next_step_actionable": (3, "[handoff] carries at least one do= directive"),
    "ownership_assigned": (1, "every do= directive names a to= owner"),
    "verification_defined": (3, "there is a stated way to tell the work worked"),
    "progress_recorded": (1, "at least one completed step is marked [x]"),
    "references_resolvable": (2, "cited paths are grounded or declared as new"),
}

TOTAL_WEIGHT = sum(weight for weight, _ in WEIGHTS.values())

#: Ordinal readiness bands, lowest first. Mirrors an ordinal rubric: the score
#: is continuous, but the decision a reader makes from it has four levels.
BANDS: tuple[tuple[float, str, str], ...] = (
    (0.35, "unusable", "the next agent would have to reconstruct the task from scratch"),
    (0.60, "thin", "enough to start, not enough to finish without asking questions"),
    (0.85, "usable", "a competent next agent can continue unattended"),
    (1.01, "strong", "goal, grounding, bounds, owner and verification are all present"),
)

# A goal shorter than this is a title, not a goal.
_MIN_GOAL_CHARS = 20

# Anchors are things the next agent can actually open, run, or look up.
_SHA_RE = re.compile(r"\b(?:[0-9a-f]{7,40}|sha256:[0-9a-f]{16,64})\b")
_URL_RE = re.compile(r"https?://\S+")
_TICKET_RE = re.compile(r"\b(?:[A-Z][A-Z0-9]+-\d+|#\d+)\b")
_SYMBOL_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\(\)")

# A handoff directive: "- to=any do=switch cart.py to the batched call".
_TO_RE = re.compile(r"\bto=(\S+)")
_DO_RE = re.compile(r"\bdo=(.+?)\s*$")
_DONE_RE = re.compile(r"^\s*-?\s*\[[xX]\]\s*(.+)$")

# Phrases that define "done" rather than describe work. Kept narrow on purpose:
# a false positive here inflates the score of exactly the handoff this module
# exists to catch.
_VERIFICATION_TERMS = (
    "test", "verify", "verified", "verification", "regression", "assert",
    "acceptance", "benchmark", "reproduce", "confirm", "measure", "prove",
    "must pass", "profiler", "profile",
)

# A path that does not exist yet is fine when the line says it is being made.
_CREATION_VERBS = (
    "add", "create", "write", "new", "introduce", "generate", "scaffold",
    "implement", "produce",
)

# Sections that describe work to be done, as opposed to work already grounded.
_FORWARD_SECTIONS = ("handoff", "constraints")
_GROUNDING_SECTIONS = ("context", "goal", "consolidated", "entries", "changes")


# --------------------------------------------------------------------------
# result types
# --------------------------------------------------------------------------

@dataclass
class Signal:
    """One rule's verdict, with the lines that produced it.

    ``passed`` is the rule outcome; ``evidence`` is the exact source text the
    rule matched on (or, on a failure, the text it looked at and rejected), so
    a reader can disagree with the rule rather than with a bare number.
    """

    id: str
    passed: bool
    weight: int
    description: str
    reason: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "passed": self.passed,
            "weight": self.weight,
            "description": self.description,
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclass
class HandoffScore:
    """A deterministic readiness score for one CRUMB, or for a pack.

    ``score`` is weighted rule coverage in [0.0, 1.0]. It is not a probability
    and must not be presented as one — see the module docstring.
    """

    path: str | None
    score: float
    band: str
    band_reason: str
    handoff_kind: str
    blocking_on_human: bool
    signals: list[Signal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def failed(self) -> list[Signal]:
        return [s for s in self.signals if not s.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "score": round(self.score, 3),
            "band": self.band,
            "band_reason": self.band_reason,
            "handoff_kind": self.handoff_kind,
            "blocking_on_human": self.blocking_on_human,
            "signals": [s.to_dict() for s in self.signals],
            "notes": self.notes,
            "weight_total": TOTAL_WEIGHT,
            "weight_earned": sum(s.weight for s in self.signals if s.passed),
        }


@dataclass
class PackScore:
    """Pack-level readiness: every document, plus continuity between them."""

    root: str
    score: float
    band: str
    band_reason: str
    documents: list[HandoffScore] = field(default_factory=list)
    continuity: Signal | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "score": round(self.score, 3),
            "band": self.band,
            "band_reason": self.band_reason,
            "documents": [d.to_dict() for d in self.documents],
            "continuity": self.continuity.to_dict() if self.continuity else None,
            "notes": self.notes,
        }


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _section_lines(doc: CrumbDoc, *names: str) -> list[str]:
    """Non-empty lines from the first of ``names`` that the document has."""
    out: list[str] = []
    for name in names:
        for line in doc.sections.get(name, []):
            if line.strip():
                out.append(line.strip())
    return out


def _joined(doc: CrumbDoc, *names: str) -> str:
    return "\n".join(_section_lines(doc, *names))


def _anchors(text: str) -> list[str]:
    """Concrete, openable references found in ``text``."""
    found: list[str] = []
    found.extend(sorted(extract_file_paths(text)))
    for pattern in (_URL_RE, _TICKET_RE, _SYMBOL_RE, _SHA_RE):
        found.extend(pattern.findall(text))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _directives(doc: CrumbDoc) -> tuple[list[dict[str, str]], list[str]]:
    """Split [handoff] into do= directives and completed [x] markers."""
    directives: list[dict[str, str]] = []
    done: list[str] = []
    for line in _section_lines(doc, "handoff", "tasks"):
        done_match = _DONE_RE.match(line)
        if done_match:
            done.append(line)
            continue
        do_match = _DO_RE.search(line)
        if not do_match:
            continue
        to_match = _TO_RE.search(line)
        directives.append(
            {
                "to": to_match.group(1) if to_match else "",
                "do": do_match.group(1).strip(),
                "raw": line,
            }
        )
    return directives, done


def _truncate(lines: Iterable[str], limit: int = 3) -> list[str]:
    out = []
    for line in lines:
        if len(out) >= limit:
            out.append("...")
            break
        out.append(line if len(line) <= 160 else line[:157] + "...")
    return out


def _band_for(score: float) -> tuple[str, str]:
    for threshold, name, reason in BANDS:
        if score < threshold:
            return name, reason
    return BANDS[-1][1], BANDS[-1][2]


# --------------------------------------------------------------------------
# the signals
# --------------------------------------------------------------------------

def _signal(sid: str, passed: bool, reason: str, evidence: list[str]) -> Signal:
    weight, description = WEIGHTS[sid]
    return Signal(
        id=sid,
        passed=passed,
        weight=weight,
        description=description,
        reason=reason,
        evidence=evidence,
    )


def _goal_stated(doc: CrumbDoc) -> Signal:
    lines = _section_lines(doc, "goal", "consolidated", "identity")
    text = " ".join(lines)
    if not text:
        return _signal("goal_stated", False, "no [goal] section, or it is empty", [])
    if len(text) < _MIN_GOAL_CHARS:
        return _signal(
            "goal_stated",
            False,
            f"[goal] is {len(text)} characters — a title, not an outcome",
            _truncate(lines),
        )
    return _signal("goal_stated", True, f"[goal] states an outcome in {len(text)} characters", _truncate(lines))


def _context_anchored(doc: CrumbDoc) -> Signal:
    lines = _section_lines(doc, *_GROUNDING_SECTIONS)
    if not lines:
        return _signal("context_anchored", False, "no grounding section present", [])
    anchors = _anchors("\n".join(lines))
    if not anchors:
        return _signal(
            "context_anchored",
            False,
            "[context] is prose with no file, symbol, commit, ticket or URL to open",
            _truncate(lines),
        )
    return _signal(
        "context_anchored",
        True,
        f"{len(anchors)} concrete anchor(s) the next agent can open",
        _truncate(anchors, limit=6),
    )


def _constraints_declared(doc: CrumbDoc) -> Signal:
    lines = _section_lines(doc, "constraints")
    if not lines:
        return _signal(
            "constraints_declared",
            False,
            "no [constraints] — the next agent does not know what it must not break",
            [],
        )
    return _signal(
        "constraints_declared", True, f"{len(lines)} constraint line(s) declared", _truncate(lines)
    )


def _next_step_actionable(doc: CrumbDoc, directives: list[dict[str, str]]) -> Signal:
    if not directives:
        return _signal(
            "next_step_actionable",
            False,
            "no do= directive in [handoff] — nothing tells the next agent what to do first",
            _truncate(_section_lines(doc, "handoff")),
        )
    return _signal(
        "next_step_actionable",
        True,
        f"{len(directives)} actionable directive(s)",
        _truncate([d["raw"] for d in directives]),
    )


def _ownership_assigned(directives: list[dict[str, str]]) -> Signal:
    if not directives:
        return _signal("ownership_assigned", False, "no directives to assign", [])
    unowned = [d["raw"] for d in directives if not d["to"]]
    if unowned:
        return _signal(
            "ownership_assigned",
            False,
            f"{len(unowned)} of {len(directives)} directive(s) name no to= owner",
            _truncate(unowned),
        )
    owners = sorted({d["to"] for d in directives})
    return _signal(
        "ownership_assigned", True, f"every directive is owned ({', '.join(owners)})", []
    )


def _verification_defined(doc: CrumbDoc, directives: list[dict[str, str]]) -> Signal:
    # Completed [x] markers describe work already done. "reproduced the
    # starvation with a load test" is evidence of progress, not a statement of
    # how the *remaining* work will be judged, so it must not satisfy this
    # rule — otherwise any handoff that records one past test looks verified.
    haystack_lines = [
        line
        for line in _section_lines(doc, *_FORWARD_SECTIONS)
        if not _DONE_RE.match(line)
    ]
    hits: list[str] = []
    for line in haystack_lines:
        lowered = line.lower()
        if any(term in lowered for term in _VERIFICATION_TERMS):
            hits.append(line)
        elif any("test" in p.lower() for p in extract_file_paths(line)):
            hits.append(line)
    if not hits:
        return _signal(
            "verification_defined",
            False,
            "nothing states how to tell the work succeeded — no test, check or acceptance bound",
            _truncate([d["raw"] for d in directives] or haystack_lines),
        )
    return _signal(
        "verification_defined",
        True,
        f"{len(hits)} line(s) define what 'done' means",
        _truncate(hits),
    )


def _progress_recorded(done: list[str], doc: CrumbDoc) -> Signal:
    if done:
        return _signal(
            "progress_recorded", True, f"{len(done)} completed step(s) recorded", _truncate(done)
        )
    if doc.sections.get("entries") or doc.sections.get("changes"):
        return _signal(
            "progress_recorded",
            True,
            "a log or delta section records what already happened",
            _truncate(_section_lines(doc, "entries", "changes")),
        )
    return _signal(
        "progress_recorded",
        False,
        "no [x] markers and no log — the next agent cannot tell what was already tried",
        [],
    )


def _references_resolvable(doc: CrumbDoc) -> Signal:
    """Paths promised in forward-looking sections should be grounded or new.

    This is the hallucination check run before any model is involved: a path
    named as work-to-do that appears nowhere in the context, and is not
    introduced by a creating verb, is a reference the next agent cannot follow.
    """
    grounded = extract_file_paths(_joined(doc, *_GROUNDING_SECTIONS))
    grounded |= extract_file_paths(" ".join(doc.headers.values()))
    grounded_basenames = {p.rsplit("/", 1)[-1] for p in grounded}

    dangling: list[str] = []
    declared_new: list[str] = []
    for line in _section_lines(doc, *_FORWARD_SECTIONS):
        lowered = line.lower()
        creates = any(re.search(rf"\b{verb}\w*\b", lowered) for verb in _CREATION_VERBS)
        for path in sorted(extract_file_paths(line)):
            if path in grounded or path.rsplit("/", 1)[-1] in grounded_basenames:
                continue
            if creates:
                declared_new.append(f"{path} (declared new: {line})")
            else:
                dangling.append(f"{path} — cited in a next step but never grounded: {line}")

    if dangling:
        return _signal(
            "references_resolvable",
            False,
            f"{len(dangling)} path(s) cited as work but grounded nowhere",
            _truncate(dangling),
        )
    if declared_new:
        return _signal(
            "references_resolvable",
            True,
            f"every cited path resolves; {len(declared_new)} declared as new",
            _truncate(declared_new),
        )
    return _signal("references_resolvable", True, "every cited path is grounded in context", [])


# --------------------------------------------------------------------------
# classification (the non-scored, descriptive outputs)
# --------------------------------------------------------------------------

_KIND_VERBS = {
    "investigation": ("investigate", "find out", "diagnose", "profile", "reproduce", "why", "confirm"),
    "implementation": ("add", "implement", "build", "switch", "migrate", "refactor", "fix", "reduce"),
    "review": ("review", "approve", "audit", "check over", "sign off"),
    "decision": ("decide", "choose", "evaluate", "compare", "select"),
}


def classify_handoff(doc: CrumbDoc, directives: list[dict[str, str]]) -> str:
    """Name the shape of work this handoff describes.

    Descriptive only — it carries no weight in the score. A wrong label costs
    the reader nothing, so this stays a cheap keyword vote rather than
    pretending to more precision than keywords can give.
    """
    text = " ".join(
        [_joined(doc, "goal")] + [d["do"] for d in directives]
    ).lower()
    if not text.strip():
        return "unknown"
    tally = {
        kind: sum(text.count(verb) for verb in verbs)
        for kind, verbs in _KIND_VERBS.items()
    }
    best = max(tally, key=lambda k: tally[k])
    return best if tally[best] else "unknown"


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def score_doc(doc: CrumbDoc) -> HandoffScore:
    """Score one CRUMB against the rule table. No model, no network."""
    directives, done = _directives(doc)

    signals = [
        _goal_stated(doc),
        _context_anchored(doc),
        _constraints_declared(doc),
        _next_step_actionable(doc, directives),
        _ownership_assigned(directives),
        _verification_defined(doc, directives),
        _progress_recorded(done, doc),
        _references_resolvable(doc),
    ]

    earned = sum(s.weight for s in signals if s.passed)
    score = earned / TOTAL_WEIGHT if TOTAL_WEIGHT else 0.0
    band, band_reason = _band_for(score)

    blocking = any(d["to"].lower() == "human" for d in directives)
    notes: list[str] = []
    if blocking:
        notes.append(
            "at least one directive is to=human — this handoff cannot complete unattended"
        )

    return HandoffScore(
        path=doc.path,
        score=score,
        band=band,
        band_reason=band_reason,
        handoff_kind=classify_handoff(doc, directives),
        blocking_on_human=blocking,
        signals=signals,
        notes=notes,
    )


def _continuity(pack: CrumbPack, scores: list[HandoffScore]) -> Signal:
    """Do later documents in a pack build on the anchors of earlier ones?

    A pack of unrelated CRUMBs is a folder, not a memory. Continuity is what
    makes the pack worth more than its documents, so it is scored separately
    rather than averaged away.
    """
    if len(pack.docs) < 2:
        return Signal(
            id="chain_continuity",
            passed=True,
            weight=0,
            description="later documents build on earlier ones",
            reason="single-document pack — continuity does not apply",
        )

    linked = 0
    evidence: list[str] = []
    for index in range(1, len(pack.docs)):
        earlier = set()
        for prior in pack.docs[:index]:
            earlier |= extract_file_paths(prior.raw_text)
        current = extract_file_paths(pack.docs[index].raw_text)
        shared = sorted(earlier & current)
        name = (pack.docs[index].path or f"doc[{index}]").rsplit("/", 1)[-1]
        if shared:
            linked += 1
            evidence.append(f"{name} continues from {', '.join(shared[:3])}")
        else:
            evidence.append(f"{name} shares no artifact with any earlier document")

    passed = linked == len(pack.docs) - 1
    return Signal(
        id="chain_continuity",
        passed=passed,
        weight=0,
        description="later documents build on earlier ones",
        reason=(
            f"{linked} of {len(pack.docs) - 1} transition(s) carry a shared artifact"
        ),
        evidence=_truncate(evidence, limit=6),
    )


def score_pack(pack: CrumbPack) -> PackScore:
    """Score every document in a pack, plus continuity between them."""
    scores = [score_doc(doc) for doc in pack.docs]
    notes: list[str] = []

    if not scores:
        return PackScore(
            root=pack.root,
            score=0.0,
            band="unusable",
            band_reason="the pack contains no readable CRUMB documents",
            documents=[],
            continuity=None,
            notes=["no .crumb files parsed from this directory"],
        )

    continuity = _continuity(pack, scores)

    # The pack is worth its weakest link, not its average: a next agent reading
    # a five-document pack hits every document, and one unusable handoff in the
    # chain stops it. Report both, decide on the worst.
    mean = sum(s.score for s in scores) / len(scores)
    worst = min(s.score for s in scores)
    aggregate = worst if continuity.passed else min(worst, mean * 0.75)

    band, band_reason = _band_for(aggregate)
    notes.append(f"mean {mean:.2f}, weakest document {worst:.2f} over {len(scores)} document(s)")
    if not continuity.passed:
        notes.append(
            "continuity gap: a document does not reference any artifact from an "
            "earlier one, so the pack reads as unrelated sessions"
        )

    return PackScore(
        root=pack.root,
        score=aggregate,
        band=band,
        band_reason=band_reason,
        documents=scores,
        continuity=continuity,
        notes=notes,
    )


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _bar(score: float, width: int = 20) -> str:
    filled = int(round(score * width))
    return "#" * filled + "." * (width - filled)


def render_doc(result: HandoffScore, explain: bool = False) -> str:
    """Human-readable report for one document."""
    name = (result.path or "(memory)").rsplit("/", 1)[-1]
    lines = [
        f"{name}",
        f"  readiness  {result.score:.2f}  [{_bar(result.score)}]  {result.band}",
        f"             {result.band_reason}",
        f"  kind       {result.handoff_kind}",
    ]
    if result.blocking_on_human:
        lines.append("  blocked    a directive is assigned to=human")
    lines.append("")

    for signal in result.signals:
        mark = "PASS" if signal.passed else "FAIL"
        lines.append(f"  [{mark}] {signal.id} (weight {signal.weight}) — {signal.reason}")
        if explain or not signal.passed:
            for item in signal.evidence:
                lines.append(f"         | {item}")

    earned = sum(s.weight for s in result.signals if s.passed)
    lines.append("")
    lines.append(f"  {earned}/{TOTAL_WEIGHT} weight units satisfied")
    for note in result.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


def render_pack(result: PackScore, explain: bool = False) -> str:
    """Human-readable report for a pack."""
    lines = [
        f"{result.root}",
        f"  readiness  {result.score:.2f}  [{_bar(result.score)}]  {result.band}",
        f"             {result.band_reason}",
        "",
    ]
    for doc in result.documents:
        lines.append(render_doc(doc, explain=explain))
        lines.append("")
    if result.continuity is not None:
        mark = "PASS" if result.continuity.passed else "FAIL"
        lines.append(f"  [{mark}] chain_continuity — {result.continuity.reason}")
        for item in result.continuity.evidence:
            lines.append(f"         | {item}")
    for note in result.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)
