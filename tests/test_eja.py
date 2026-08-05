from __future__ import annotations

import copy
from pathlib import Path

from crumb_llm.eja import (
    artifact_hash,
    compare_artifacts,
    load_artifact,
    replay_plan,
    summarize_artifact,
    validate_artifact,
)

EXAMPLE = Path(__file__).parents[1] / "examples" / "einstein-elevator.eja.json"


def test_gaugegap_example_validates_and_hashes():
    artifact = load_artifact(EXAMPLE)
    report = validate_artifact(artifact)
    assert report.valid, report.to_dict()
    assert report.computed_hash == artifact["provenance"]["artifact_hash"]
    assert artifact_hash(artifact).startswith("sha256:")


def test_missing_falsifier_is_rejected():
    artifact = load_artifact(EXAMPLE)
    artifact["candidate_axiom"]["falsifiers"] = []
    report = validate_artifact(artifact, verify_hash=False)
    assert not report.valid
    assert any(issue.path == "candidate_axiom.falsifiers" for issue in report.issues)


def test_hidden_state_exposure_is_rejected():
    artifact = load_artifact(EXAMPLE)
    artifact["provenance"]["hidden_state_exposed_to_agent"] = True
    assert not validate_artifact(artifact, verify_hash=False).valid


def test_replay_plan_preserves_intervention_order():
    artifact = load_artifact(EXAMPLE)
    plan = replay_plan(artifact)
    assert len(plan) == len(artifact["trajectories"])
    assert [p["action_type"] for p in plan] == [
        t["intervention"]["action_type"] for t in artifact["trajectories"]
    ]


def test_compare_reports_repeatability():
    artifact = load_artifact(EXAMPLE)
    result = compare_artifacts(artifact, copy.deepcopy(artifact))
    assert result["same_hash"] is True
    assert result["same_winner"] is True


def test_summary_keeps_claim_boundary_visible():
    artifact = load_artifact(EXAMPLE)
    summary = summarize_artifact(artifact)
    assert "supported_within_scope" in summary
    assert "Candidate axiom" in summary
