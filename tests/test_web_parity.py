"""The browser scorer must agree with the Python one, rule by rule.

This repository has already paid for the alternative. Three projects each kept
a private copy of the CRUMB grammar, each promised in a docstring that it was
"kept faithful", nothing compared them, and they drifted until one shipped
`v=1.3` against a `v=1.4` spec. `web/crumb-score.js` is a second implementation
of `crumb_llm/score.py`, which is the same shape of mistake unless something
checks — so this does.

Parity is asserted on the score, the band, the classification, and every
signal's pass/fail, for every CRUMB the repository ships plus a set of edge
cases chosen to hit each rule's boundary. Reasons and evidence strings are NOT
compared: they are prose for a human, and requiring them to match byte for byte
would make the two implementations harder to keep honest rather than easier.

Skipped when node is unavailable, so a contributor without it can still run the
suite — CI has node and does not skip.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from crumb_llm.crumb.loader import load_crumb_text
from crumb_llm.score import score_doc

REPO = Path(__file__).resolve().parent.parent
SCORER_JS = REPO / "web" / "crumb-score.js"

node = shutil.which("node")
requires_node = pytest.mark.skipif(node is None, reason="node is not installed")


def score_in_node(text: str) -> dict:
    """Run the browser scorer under node and return its result."""
    script = (
        "const S=require(process.argv[1]);"
        "let d='';process.stdin.on('data',c=>d+=c);"
        "process.stdin.on('end',()=>process.stdout.write(JSON.stringify(S.scoreText(d))));"
    )
    proc = subprocess.run(
        [node, "-e", script, str(SCORER_JS)],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def assert_parity(text: str, label: str) -> None:
    py = score_doc(load_crumb_text(text)).to_dict()
    js = score_in_node(text)

    assert round(js["score"], 3) == py["score"], f"{label}: score"
    assert js["band"] == py["band"], f"{label}: band"
    assert js["handoff_kind"] == py["handoff_kind"], f"{label}: kind"
    assert js["blocking_on_human"] == py["blocking_on_human"], f"{label}: blocking"
    assert js["weight_earned"] == py["weight_earned"], f"{label}: weight"
    assert js["weight_total"] == py["weight_total"], f"{label}: total weight"

    py_signals = {s["id"]: s for s in py["signals"]}
    js_signals = {s["id"]: s for s in js["signals"]}
    assert set(js_signals) == set(py_signals), f"{label}: signal ids differ"
    for sid, py_sig in py_signals.items():
        assert js_signals[sid]["passed"] == py_sig["passed"], f"{label}: {sid} verdict"
        assert js_signals[sid]["weight"] == py_sig["weight"], f"{label}: {sid} weight"


# -- every CRUMB the repository ships ---------------------------------------

SHIPPED = sorted(
    list((REPO / "examples").rglob("*.crumb"))
    + list((REPO / "research").rglob("*.crumb"))
)


def test_the_repository_actually_ships_crumbs_to_check():
    assert SHIPPED, "no .crumb fixtures found — this test would pass vacuously"


@requires_node
@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: p.name)
def test_parity_on_shipped_examples(path):
    assert_parity(path.read_text(encoding="utf-8"), path.name)


# -- boundaries, one per rule ------------------------------------------------

BASE = """BEGIN CRUMB
v=1.2
kind=task
title=T
source=test
---
[goal]
{goal}
[context]
{context}
[constraints]
{constraints}
[handoff]
{handoff}
END CRUMB
"""


def build(goal="Add a limiter so one client cannot exhaust the pool.",
          context="Lives in src/gateway/middleware.py.",
          constraints="- No breaking changes",
          handoff="- to=any do=add a test in tests/test_x.py"):
    return BASE.format(goal=goal, context=context, constraints=constraints, handoff=handoff)


EDGE_CASES = {
    "goal_exactly_at_threshold": build(goal="x" * 20),
    "goal_one_under_threshold": build(goal="x" * 19),
    "context_with_no_anchor": build(context="We discussed it yesterday."),
    "context_anchored_by_symbol": build(context="The hotspot is compute_tax()."),
    "context_anchored_by_sha": build(context="Broke at a1b2c3d4e5f."),
    "context_anchored_by_ticket": build(context="Tracked as PROJ-1421."),
    "context_anchored_by_url": build(context="See https://example.com/runbook."),
    "directive_without_owner": build(handoff="- do=add a test in tests/test_x.py"),
    "directive_to_human": build(handoff="- to=human do=review the diff"),
    "no_directive_at_all": build(handoff="- some prose with no directive"),
    "done_marker_only": build(handoff="- [x] already reproduced it"),
    "dangling_path": build(handoff="- to=any do=clean up src/other/thing.py"),
    "new_path_declared": build(handoff="- to=any do=create src/other/thing.py"),
    "verification_via_done_marker_only": build(
        constraints="- Ship it",
        handoff="- to=any do=change the thing\n- [x] ran a load test",
    ),
    "unicode_and_emoji": build(goal="Ré-implémenter le limiteur 🥖 pour éviter la famine."),
    "windows_line_endings": build().replace("\n", "\r\n"),
}


@requires_node
@pytest.mark.parametrize("label", sorted(EDGE_CASES))
def test_parity_on_edge_cases(label):
    assert_parity(EDGE_CASES[label], label)


@requires_node
def test_the_parity_check_can_actually_fail():
    """A comparison that cannot fail proves nothing."""
    py = score_doc(load_crumb_text(build())).to_dict()
    js = score_in_node(build(context="We discussed it yesterday."))
    assert js["score"] != py["score"]
