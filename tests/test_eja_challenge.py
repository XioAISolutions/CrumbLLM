from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path

from crumb_llm.eja import (
    artifact_hash,
    audit_challenge_artifact,
    audit_challenge_pack,
    load_artifact,
    render_challenge_html,
)
from crumb_llm.eja.cli import build_parser
from crumb_llm.eja.model import canonical_json

EXAMPLE = Path(__file__).parents[1] / "examples" / "einstein-elevator.eja.json"


def _commitment(value: object) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _challenge_artifact(*, no_fit: bool = False) -> dict:
    artifact = load_artifact(EXAMPLE)
    refs: list[str] = []
    for index, trajectory in enumerate(artifact.get("trajectories") or [], start=1):
        ref = f"challenge-evidence-{index:03d}"
        trajectory["evidence_ref"] = ref
        refs.append(ref)
    hidden_spec = {
        "challenge_id": "test-no-fit" if no_fit else "test-positive",
        "case_kind": "hybrid_no_fit" if no_fit else "ratio_supported",
        "deterministic_seed": 101,
        "base_world": "simple-pendulum-holdout-v0.4",
        "perturbation": (
            {"action": "scale_length_and_gravity", "offset_fraction": 0.03}
            if no_fit
            else None
        ),
    }
    expected = "abstain" if no_fit else "length_gravity_ratio"
    selected = expected
    answer = {
        "expected_outcome": expected,
        "answerable_by_registered_deck": not no_fit,
    }
    submission = {
        "challenge_id": hidden_spec["challenge_id"],
        "selected_outcome": selected,
        "abstained": no_fit,
        "top_blind_id": "B2",
        "top_score": 0.82 if not no_fit else 0.73,
        "selection_margin": 0.22 if not no_fit else 0.0,
        "evidence_refs": refs,
    }
    artifact["experiment"]["id"] = hidden_spec["challenge_id"]
    artifact["experiment"]["world"] = "sealed-pendulum-challenge-v0.5"
    artifact["challenge_protocol"] = {
        "protocol": "sealed_none_of_the_above_challenge_v1",
        "case_commitment_hash": _commitment(hidden_spec),
        "answer_commitment_hash": _commitment(answer),
        "submission_hash": _commitment(submission),
        "answer_visible_to_agent": False,
        "case_spec_visible_to_agent": False,
        "selection_rule": {
            "minimum_score": 0.70,
            "minimum_margin": 0.10,
            "evidence_gates_required": True,
            "abstention_allowed": True,
        },
        "reveal_policy": "reveal after submission",
    }
    artifact["challenge_evaluation"] = {
        "hidden_case_spec": hidden_spec,
        "answer_payload": answer,
        "submission_payload": submission,
        "selected_outcome": selected,
        "abstained": no_fit,
        "correct": True,
        "false_discovery": False,
        "positive_abstention": False,
    }
    artifact.setdefault("metrics", {}).update(
        {
            "discovery_complete": not no_fit,
            "challenge_case_kind": hidden_spec["case_kind"],
            "challenge_correct": True,
            "abstained": no_fit,
            "selection_margin": submission["selection_margin"],
            "selected_outcome": selected,
            "false_discovery": False,
        }
    )
    if no_fit:
        artifact["candidate_axiom"] = None
        artifact["deductions"] = []
        artifact["verification"] = {
            "verdict": "not_evaluated_due_to_abstention",
            "claim_boundary": "No model cleared the challenge gates.",
        }
    artifact["provenance"]["hidden_state_exposed_to_agent"] = False
    artifact["provenance"]["artifact_hash"] = artifact_hash(artifact)
    return artifact


def _write_pack(tmp_path: Path) -> Path:
    root = tmp_path / "challenge-pack"
    root.mkdir()
    for name, artifact in (
        ("positive.eja.json", _challenge_artifact()),
        ("no-fit.eja.json", _challenge_artifact(no_fit=True)),
    ):
        (root / name).write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return root


def test_positive_challenge_commitments_and_selection_are_valid():
    report = audit_challenge_artifact(_challenge_artifact())
    assert report["challenge_valid"] is True
    assert report["correct"] is True
    assert report["abstained"] is False
    assert report["commitments"]["all_valid"] is True


def test_no_fit_challenge_accepts_abstention_and_rejects_false_axiom():
    report = audit_challenge_artifact(_challenge_artifact(no_fit=True))
    assert report["challenge_valid"] is True
    assert report["expected_outcome"] == "abstain"
    assert report["abstained"] is True
    assert report["false_discovery"] is False


def test_tampered_answer_breaks_commitment():
    artifact = _challenge_artifact()
    artifact["challenge_evaluation"]["answer_payload"]["expected_outcome"] = "abstain"
    report = audit_challenge_artifact(artifact)
    codes = {issue["code"] for issue in report["issues"]}
    assert report["challenge_valid"] is False
    assert "answer_commitment_mismatch" in codes


def test_no_fit_positive_selection_is_reported_as_false_discovery():
    artifact = _challenge_artifact(no_fit=True)
    artifact["challenge_evaluation"]["selected_outcome"] = "length_gravity_ratio"
    artifact["challenge_evaluation"]["abstained"] = False
    artifact["challenge_evaluation"]["correct"] = False
    artifact["challenge_evaluation"]["false_discovery"] = True
    artifact["challenge_evaluation"]["submission_payload"]["selected_outcome"] = (
        "length_gravity_ratio"
    )
    artifact["challenge_evaluation"]["submission_payload"]["abstained"] = False
    artifact["challenge_protocol"]["submission_hash"] = _commitment(
        artifact["challenge_evaluation"]["submission_payload"]
    )
    artifact["metrics"]["selected_outcome"] = "length_gravity_ratio"
    artifact["metrics"]["abstained"] = False
    artifact["metrics"]["false_discovery"] = True
    report = audit_challenge_artifact(artifact)
    codes = {issue["code"] for issue in report["issues"]}
    assert report["false_discovery"] is True
    assert "false_discovery" in codes


def test_pack_scorecard_measures_accuracy_abstention_and_coverage(tmp_path):
    report = audit_challenge_pack(_write_pack(tmp_path))
    assert report["challenge_valid"] is True
    assert report["artifact_count"] == 2
    assert report["answerable_count"] == 1
    assert report["no_fit_count"] == 1
    assert report["overall_accuracy"] == 1.0
    assert report["answerable_accuracy"] == 1.0
    assert report["abstention_accuracy"] == 1.0
    assert report["false_discovery_rate"] == 0.0
    assert report["coverage"] == 0.5
    assert report["commitment_valid_rate"] == 1.0


def test_cli_registers_challenge_pack():
    args = build_parser().parse_args(["challenge-pack", "artifacts"])
    assert args.eja_command == "challenge-pack"


def test_challenge_html_preserves_claim_boundary(tmp_path):
    report = audit_challenge_pack(_write_pack(tmp_path))
    html = render_challenge_html(report)
    assert "Sealed challenge audit" in html
    assert "False-discovery rate" in html
    assert "does not validate" in html
