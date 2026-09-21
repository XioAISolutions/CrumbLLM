"""Tests for the handoff retention harness.

The harness exists to produce a number that will be published, so the tests
care most about the ways a measurement can flatter its author: a budget that
is not actually applied to every strategy, a matcher that fails on text that
does contain the fact, and facts that were written after the handoffs they
score.
"""

import json
from pathlib import Path

import pytest

from research.handoff_benchmark.retention import (
    count_tokens,
    fact_present,
    measure,
    normalise,
    run_task,
    truncate_to_budget,
)

TASKS = Path(__file__).resolve().parent.parent / "research" / "handoff_benchmark" / "tasks"
RATE_LIMIT = TASKS / "rate-limit"


# -- the harness must not flatter the thing it measures ---------------------

def test_every_shipped_task_declares_facts_before_handoffs():
    """A fact written after the handoff it scores is not evidence."""
    for task_dir in TASKS.iterdir():
        task_file = task_dir / "task.json"
        if not task_file.exists():
            continue
        task = json.loads(task_file.read_text(encoding="utf-8"))
        assert task.get("facts_declared_before_handoffs_were_written") is True, task_dir


def test_truncation_keeps_the_end_not_the_start():
    """`tail` must model dumping a transcript, which loses the beginning."""
    text = "alpha beta gamma delta epsilon"
    assert "epsilon" in truncate_to_budget(text, 2)
    assert "alpha" not in truncate_to_budget(text, 2)


def test_truncation_is_a_no_op_under_budget():
    text = "alpha beta gamma"
    assert truncate_to_budget(text, 99) == text


def test_budget_is_reported_not_silently_enforced():
    """Trimming an authored handoff to fit would hide a broken fixture."""
    result = run_task(RATE_LIMIT, budget=50)
    authored = [s for s in result["strategies"] if s["strategy"] != "tail"]
    assert all(s["over_budget"] for s in authored)
    tail = next(s for s in result["strategies"] if s["strategy"] == "tail")
    assert tail["tokens"] <= 50 and not tail["over_budget"]


def test_matching_survives_markdown_emphasis_and_line_wrapping():
    """The bug this guards against biased the baseline down, not up."""
    fact = {"id": "x", "kind": "trap", "match": "before the limiter", "aliases": [], "why": ""}
    assert fact_present(fact, "must run *before* the limiter")
    assert fact_present(fact, "must run before\nthe limiter")
    assert fact_present(fact, "must run `before the limiter`")
    assert not fact_present(fact, "must run after the limiter")


def test_normalise_is_idempotent():
    text = "  **Some**   `text`\nhere "
    assert normalise(normalise(text)) == normalise(text)


def test_aliases_are_honoured():
    fact = {"id": "x", "kind": "goal", "match": "per-token", "aliases": ["per token"], "why": ""}
    assert fact_present(fact, "limit per token")
    assert fact_present(fact, "limit per-token")


# -- the measurement itself --------------------------------------------------

def test_full_transcript_retains_everything():
    """If the untruncated transcript lost a fact, the fixture is wrong."""
    result = run_task(RATE_LIMIT, budget=result_transcript_tokens())
    tail = next(s for s in result["strategies"] if s["strategy"] == "tail")
    assert tail["retention"] == 1.0, tail["missing"]


def result_transcript_tokens() -> int:
    return run_task(RATE_LIMIT, budget=1)["transcript_tokens"]


def test_truncation_is_what_loses_facts():
    generous = run_task(RATE_LIMIT, budget=result_transcript_tokens())
    tight = run_task(RATE_LIMIT, budget=200)
    g = next(s for s in generous["strategies"] if s["strategy"] == "tail")
    t = next(s for s in tight["strategies"] if s["strategy"] == "tail")
    assert t["retention"] < g["retention"]


def test_constraints_are_what_truncation_eats_first():
    """Constraints are stated at the start of a session, so the tail loses them."""
    result = run_task(RATE_LIMIT, budget=200)
    tail = next(s for s in result["strategies"] if s["strategy"] == "tail")
    lost_kinds = {m["kind"] for m in tail["missing"]}
    assert "constraint" in lost_kinds


def test_authored_handoffs_beat_the_tail_at_a_budget_that_favours_the_tail():
    """The tail is given MORE tokens than either authored handoff here."""
    result = run_task(RATE_LIMIT, budget=320)
    by_name = {s["strategy"]: s for s in result["strategies"]}
    assert by_name["tail"]["tokens"] >= by_name["prose"]["tokens"]
    assert by_name["tail"]["tokens"] >= by_name["crumb"]["tokens"]
    assert by_name["prose"]["retention"] > by_name["tail"]["retention"]
    assert by_name["crumb"]["retention"] > by_name["tail"]["retention"]


def test_this_fixture_cannot_separate_crumb_from_prose():
    """A ceiling effect, asserted so it cannot be quietly forgotten.

    Both authored formats retain every declared fact, so this task measures
    'someone wrote a handoff' and nothing finer. If a future fixture breaks
    this tie, delete the test and say which format won — but do not let the
    write-up claim a separation this data does not contain.
    """
    result = run_task(RATE_LIMIT, budget=320)
    by_name = {s["strategy"]: s for s in result["strategies"]}
    assert by_name["prose"]["retention"] == by_name["crumb"]["retention"] == 1.0


def test_crumb_costs_more_tokens_than_prose_for_the_same_facts():
    """Recorded because it is the finding least flattering to this project."""
    result = run_task(RATE_LIMIT, budget=320)
    by_name = {s["strategy"]: s for s in result["strategies"]}
    assert by_name["crumb"]["tokens"] > by_name["prose"]["tokens"]
    assert by_name["crumb"]["facts_per_100_tokens"] < by_name["prose"]["facts_per_100_tokens"]


def test_token_count_is_deterministic():
    text = (RATE_LIMIT / "transcript.md").read_text(encoding="utf-8")
    assert count_tokens(text) == count_tokens(text)


def test_measure_reports_every_declared_fact():
    task = json.loads((RATE_LIMIT / "task.json").read_text(encoding="utf-8"))
    result = measure("nothing useful here", task, "empty", budget=10)
    assert result.total == len(task["critical_facts"])
    assert result.retained == 0
    assert result.retention == 0.0


def test_missing_facts_carry_their_reason():
    task = json.loads((RATE_LIMIT / "task.json").read_text(encoding="utf-8"))
    result = measure("", task, "empty", budget=10).to_dict()
    assert all(m["why"] for m in result["missing"])
