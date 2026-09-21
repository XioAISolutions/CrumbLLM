"""Tests for the deterministic scorer.

Two properties matter more than any individual rule and are tested first:
the score never depends on a model or the network, and the same bytes always
produce the same number. Everything after that is one test per rule, each
asserting the rule fires on the failure it exists to catch.
"""

import json

import pytest

from crumb_llm.crumb.loader import load_crumb, load_crumb_text
from crumb_llm.crumb.pack_reader import read_pack
from crumb_llm.score import (
    BANDS,
    TOTAL_WEIGHT,
    WEIGHTS,
    classify_handoff,
    render_doc,
    render_pack,
    score_doc,
    score_pack,
)

STRONG = """BEGIN CRUMB
v=1.2
kind=task
title=Add rate limiting
source=test
---
[goal]
Add per-token rate limiting so one client cannot exhaust the worker pool.

[context]
The limiter belongs in src/gateway/middleware.py, called from
src/gateway/server.py. Redis config lives in config/redis.yaml.

[constraints]
- No breaking changes to the response schema
- Add a regression test before merging

[handoff]
- to=any do=implement the limiter in src/gateway/middleware.py
- to=any do=add a test in tests/test_rate_limit.py that fails on main
- [x] reproduced the starvation with a load test
END CRUMB
"""

WEAK = """BEGIN CRUMB
v=1.2
kind=task
title=Fix it
source=test
---
[goal]
Make it better.

[context]
We discussed this yesterday and everyone knows the background.

[constraints]
- Don't break anything

[handoff]
- do=clean up the auth code in src/auth/session_store.py
END CRUMB
"""


def _signal(result, sid):
    return next(s for s in result.signals if s.id == sid)


# -- the two properties the whole module rests on ---------------------------

def test_scoring_touches_no_provider(monkeypatch):
    """A score must never reach for a model, a key or the network."""
    import crumb_llm.providers as providers
    import urllib.request

    def explode(*args, **kwargs):  # pragma: no cover - the point is it never runs
        raise AssertionError("the scorer must not open a network connection")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    monkeypatch.setattr(
        providers, "get_provider", lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("the scorer must not build a provider")
        )
    )
    result = score_doc(load_crumb_text(STRONG))
    assert 0.0 <= result.score <= 1.0


def test_scoring_is_deterministic():
    doc = load_crumb_text(STRONG)
    first = score_doc(doc).to_dict()
    for _ in range(5):
        assert score_doc(load_crumb_text(STRONG)).to_dict() == first


def test_weights_sum_to_the_published_total():
    """The README quotes TOTAL_WEIGHT; the table must agree with it."""
    assert TOTAL_WEIGHT == sum(w for w, _ in WEIGHTS.values())
    assert TOTAL_WEIGHT == 17


def test_bands_are_ordered_and_cover_the_range():
    thresholds = [t for t, _, _ in BANDS]
    assert thresholds == sorted(thresholds)
    assert thresholds[-1] > 1.0, "the top band must catch a perfect score"


# -- the score itself --------------------------------------------------------

def test_strong_handoff_scores_high():
    result = score_doc(load_crumb_text(STRONG))
    assert result.score > 0.85
    assert result.band == "strong"
    assert result.failed == []


def test_weak_handoff_scores_low_and_names_every_gap():
    result = score_doc(load_crumb_text(WEAK))
    assert result.score < 0.35
    assert result.band == "unusable"
    failed = {s.id for s in result.failed}
    assert {
        "goal_stated",
        "context_anchored",
        "ownership_assigned",
        "verification_defined",
        "references_resolvable",
    } <= failed


def test_score_equals_earned_weight_over_total():
    result = score_doc(load_crumb_text(WEAK))
    earned = sum(s.weight for s in result.signals if s.passed)
    assert result.score == pytest.approx(earned / TOTAL_WEIGHT)


# -- one test per rule, on the failure the rule exists to catch --------------

def test_goal_of_title_length_is_not_a_goal():
    doc = load_crumb_text(WEAK)
    signal = _signal(score_doc(doc), "goal_stated")
    assert not signal.passed
    assert "title, not an outcome" in signal.reason


def test_context_without_an_anchor_fails():
    signal = _signal(score_doc(load_crumb_text(WEAK)), "context_anchored")
    assert not signal.passed
    assert signal.evidence, "a failing rule must show what it rejected"


@pytest.mark.parametrize(
    "anchor",
    [
        "see src/gateway/server.py",
        "fixed in commit a1b2c3d4e5f",
        "tracked as PROJ-1421",
        "the hotspot is compute_tax()",
        "context at https://example.com/runbook",
    ],
)
def test_any_concrete_anchor_grounds_the_context(anchor):
    text = STRONG.replace(
        "The limiter belongs in src/gateway/middleware.py, called from\n"
        "src/gateway/server.py. Redis config lives in config/redis.yaml.",
        anchor,
    )
    assert _signal(score_doc(load_crumb_text(text)), "context_anchored").passed


def test_directive_without_an_owner_fails_ownership():
    signal = _signal(score_doc(load_crumb_text(WEAK)), "ownership_assigned")
    assert not signal.passed
    assert "no to= owner" in signal.reason


def test_verification_requires_a_definition_of_done():
    without = STRONG.replace(
        "- Add a regression test before merging", "- Ship it soon"
    ).replace("- to=any do=add a test in tests/test_rate_limit.py that fails on main\n", "")
    assert not _signal(score_doc(load_crumb_text(without)), "verification_defined").passed
    assert _signal(score_doc(load_crumb_text(STRONG)), "verification_defined").passed


def test_new_files_are_allowed_when_the_line_says_they_are_new():
    """`add a test in tests/x.py` is not a dangling reference."""
    signal = _signal(score_doc(load_crumb_text(STRONG)), "references_resolvable")
    assert signal.passed


def test_path_cited_as_work_but_grounded_nowhere_is_flagged():
    signal = _signal(score_doc(load_crumb_text(WEAK)), "references_resolvable")
    assert not signal.passed
    assert "src/auth/session_store.py" in " ".join(signal.evidence)


def test_progress_marker_is_recognised():
    assert _signal(score_doc(load_crumb_text(STRONG)), "progress_recorded").passed
    assert not _signal(score_doc(load_crumb_text(WEAK)), "progress_recorded").passed


# -- descriptive outputs -----------------------------------------------------

def test_blocking_on_human_is_detected():
    text = STRONG.replace("- to=any do=implement", "- to=human do=implement")
    result = score_doc(load_crumb_text(text))
    assert result.blocking_on_human
    assert any("to=human" in note for note in result.notes)


def test_classification_reads_the_verbs():
    doc = load_crumb_text(STRONG)
    directives = [{"to": "any", "do": "implement the limiter", "raw": ""}]
    assert classify_handoff(doc, directives) == "implementation"


def test_classification_admits_when_it_cannot_tell():
    text = STRONG.replace("Add per-token rate limiting so one client cannot exhaust the worker pool.", "Something happens here.")
    doc = load_crumb_text(text)
    assert classify_handoff(doc, []) == "unknown"


# -- packs -------------------------------------------------------------------

def test_pack_reports_the_weakest_document_not_the_average(tmp_path):
    (tmp_path / "a.crumb").write_text(STRONG, encoding="utf-8")
    (tmp_path / "b.crumb").write_text(WEAK, encoding="utf-8")
    result = score_pack(read_pack(tmp_path))
    per_doc = [d.score for d in result.documents]
    assert result.score <= min(per_doc)
    assert any("weakest document" in n for n in result.notes)


def test_continuity_flags_unrelated_sessions(tmp_path):
    (tmp_path / "a.crumb").write_text(STRONG, encoding="utf-8")
    (tmp_path / "b.crumb").write_text(
        STRONG.replace("src/gateway", "src/unrelated").replace(
            "tests/test_rate_limit.py", "tests/test_other.py"
        ).replace("config/redis.yaml", "config/other.yaml"),
        encoding="utf-8",
    )
    result = score_pack(read_pack(tmp_path))
    assert result.continuity is not None
    assert not result.continuity.passed


def test_continuity_passes_on_the_example_pack(example_pack):
    result = score_pack(read_pack(example_pack))
    assert result.continuity.passed


def test_empty_pack_is_unusable_not_a_crash(tmp_path):
    result = score_pack(read_pack(tmp_path))
    assert result.score == 0.0
    assert result.band == "unusable"


# -- rendering and serialisation --------------------------------------------

def test_json_round_trips():
    payload = json.dumps(score_doc(load_crumb_text(STRONG)).to_dict())
    parsed = json.loads(payload)
    assert parsed["weight_total"] == TOTAL_WEIGHT
    assert len(parsed["signals"]) == len(WEIGHTS)


def test_render_shows_failures_without_explain_and_passes_with_it():
    result = score_doc(load_crumb_text(STRONG))
    plain = render_doc(result, explain=False)
    verbose = render_doc(result, explain=True)
    assert len(verbose) > len(plain)
    assert "readiness" in plain


def test_render_pack_includes_every_document(example_pack):
    text = render_pack(score_pack(read_pack(example_pack)))
    assert "session-01.crumb" in text and "session-02.crumb" in text


# -- the shipped examples ----------------------------------------------------

def test_shipped_examples_score_where_the_docs_say_they_do(basic_crumb):
    """README quotes these bands; a change that moves them must update the docs."""
    assert score_doc(load_crumb(basic_crumb)).band in {"usable", "strong"}


def test_weak_example_is_shipped_and_fails(example_pack):
    weak = example_pack.parent / "weak-handoff.crumb"
    assert weak.exists(), "the counter-example the README demonstrates must ship"
    assert score_doc(load_crumb(weak)).band == "unusable"
