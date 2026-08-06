from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path

from crumb_llm.eja import (
    artifact_hash,
    audit_calibration_report,
    calibration_commitment_payload,
    load_artifact,
    render_calibration_html,
)
from crumb_llm.eja.cli import build_parser
from crumb_llm.eja.model import canonical_json

EXAMPLE = Path(__file__).parents[1] / "examples" / "einstein-elevator.eja.json"
THRESHOLD = {"minimum_score": 0.75, "minimum_margin": 0.05}
CALIBRATION_SEEDS = [2101]
TEST_SEEDS = [2201]


def _commitment(value: object) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _record(case_kind: str, expected: str, score: float, margin: float, complete: bool) -> dict:
    record = {
        "split": "calibration",
        "policy": "cold",
        "seed": 2101,
        "case_kind": case_kind,
        "artifact_hash": "sha256:" + case_kind.encode().hex().ljust(64, "0")[:64],
        "expected_outcome": expected,
        "top_semantic_key": "length_gravity_ratio",
        "top_blind_id": "B2",
        "top_score": score,
        "selection_margin": margin,
        "base_discovery_complete": complete,
        "experiments_run": 5,
        "evidence_refs": ["challenge-evidence-001"],
    }
    record["record_hash"] = _commitment(record)
    return record


def _challenge_artifact(*, no_fit: bool, deceptive: bool = False) -> dict:
    artifact = load_artifact(EXAMPLE)
    refs: list[str] = []
    for index, trajectory in enumerate(artifact.get("trajectories") or [], start=1):
        ref = f"challenge-evidence-{index:03d}"
        trajectory["evidence_ref"] = ref
        refs.append(ref)
    case_kind = "deceptive_no_fit" if deceptive else (
        "hybrid_no_fit" if no_fit else "ratio_supported"
    )
    hidden_spec = {
        "challenge_id": f"test-{case_kind}",
        "case_kind": case_kind,
        "deterministic_seed": 2201,
        "base_world": "simple-pendulum-holdout-v0.4",
        "perturbation": {"action": "repeat_observation"} if no_fit else None,
    }
    expected = "abstain" if no_fit else "length_gravity_ratio"
    answer = {
        "expected_outcome": expected,
        "answerable_by_registered_deck": not no_fit,
    }
    selected = expected
    score = 0.73 if deceptive else (0.31 if no_fit else 0.82)
    margin = 0.30 if deceptive else (0.02 if no_fit else 0.22)
    submission = {
        "challenge_id": hidden_spec["challenge_id"],
        "selected_outcome": selected,
        "abstained": no_fit,
        "top_blind_id": "B2",
        "top_score": score,
        "selection_margin": margin,
        "evidence_refs": refs,
    }
    artifact["experiment"].update(
        {
            "id": hidden_spec["challenge_id"],
            "world": "sealed-pendulum-challenge-v0.5",
            "deterministic_seed": 2201,
        }
    )
    artifact["challenge_protocol"] = {
        "protocol": "sealed_none_of_the_above_challenge_v1",
        "case_commitment_hash": _commitment(hidden_spec),
        "answer_commitment_hash": _commitment(answer),
        "submission_hash": _commitment(submission),
        "answer_visible_to_agent": False,
        "case_spec_visible_to_agent": False,
        "selection_rule": {
            "minimum_score": THRESHOLD["minimum_score"],
            "minimum_margin": THRESHOLD["minimum_margin"],
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
            "discovery_complete": not no_fit or deceptive,
            "challenge_case_kind": case_kind,
            "challenge_correct": True,
            "abstained": no_fit,
            "selection_margin": margin,
            "selected_outcome": selected,
            "false_discovery": False,
            "evaluator_selected_semantic_key": "length_gravity_ratio",
            "experiments_run": 5,
        }
    )
    if no_fit:
        artifact["candidate_axiom"] = None
        artifact["deductions"] = []
        artifact["verification"] = {
            "verdict": "not_evaluated_due_to_abstention",
            "claim_boundary": "No model cleared the frozen selection threshold.",
        }
    artifact["provenance"]["hidden_state_exposed_to_agent"] = False
    return artifact


def _write_suite(tmp_path: Path) -> Path:
    root = tmp_path / "calibration-pack"
    root.mkdir()
    records = [
        _record("ratio_supported", "length_gravity_ratio", 0.82, 0.22, True),
        _record("deceptive_no_fit", "abstain", 0.73, 0.30, True),
        _record("hybrid_no_fit", "abstain", 0.31, 0.02, False),
    ]
    report = {
        "artifact_type": "jump_lab_calibrated_challenge_suite",
        "suite_version": "0.6",
        "artifact_root": str(root),
        "calibration": {
            "protocol": "disjoint_frozen_threshold_calibration_v1",
            "calibration_seeds": CALIBRATION_SEEDS,
            "case_kinds": ["ratio_supported", "deceptive_no_fit", "hybrid_no_fit"],
            "candidate_grid": {
                "minimum_scores": [0.70, 0.75, 0.80],
                "minimum_margins": [0.05, 0.10],
            },
            "maximum_false_discovery_rate": 0.0,
            "record_hashes": [record["record_hash"] for record in records],
            "chosen_threshold": dict(THRESHOLD),
            "selection_objective": [
                "maximize overall calibration accuracy",
                "respect the maximum false-discovery constraint",
                "minimize positive abstention",
                "maximize coverage",
                "prefer the least restrictive tied threshold",
            ],
            "threshold_commitment_hash": "pending",
            "records": records,
        },
        "test": {
            "test_seeds": TEST_SEEDS,
            "case_kinds": ["ratio_supported", "deceptive_no_fit", "hybrid_no_fit"],
            "answers_used_for_calibration": False,
        },
        "runs": [],
        "summary": {},
        "artifact_index": [],
        "claim_boundary": "Does not establish real-world calibration.",
    }
    report["calibration"]["threshold_commitment_hash"] = _commitment(
        calibration_commitment_payload(report)
    )
    commitment = report["calibration"]["threshold_commitment_hash"]
    for case_kind, artifact in (
        ("ratio_supported", _challenge_artifact(no_fit=False)),
        ("deceptive_no_fit", _challenge_artifact(no_fit=True, deceptive=True)),
        ("hybrid_no_fit", _challenge_artifact(no_fit=True)),
    ):
        artifact["calibration_protocol"] = {
            "protocol": "disjoint_frozen_threshold_calibration_v1",
            "split": "test",
            "threshold_frozen_before_test": True,
            "threshold_commitment_hash": commitment,
            "frozen_threshold": dict(THRESHOLD),
            "calibration_record_hashes": report["calibration"]["record_hashes"],
            "test_answers_used_for_calibration": False,
        }
        artifact["provenance"]["artifact_hash"] = artifact_hash(artifact)
        relative = Path("test") / case_kind / "cold.eja.json"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
        report["artifact_index"].append(
            {
                "split": "test",
                "seed": 2201,
                "case_kind": case_kind,
                "policy": "cold",
                "relative_path": str(relative),
                "artifact_hash": artifact["provenance"]["artifact_hash"],
            }
        )
    report_path = root / "calibration-suite.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report_path


def test_valid_calibration_report_reproduces_threshold_and_test_decisions(tmp_path):
    audit = audit_calibration_report(_write_suite(tmp_path))
    assert audit["calibration_valid"] is True
    assert audit["split_disjoint"] is True
    assert audit["threshold_commitment_valid"] is True
    assert audit["calibration_record_hashes_valid"] is True
    assert audit["chosen_threshold"] == THRESHOLD
    assert audit["reproduced_threshold"] == THRESHOLD
    assert audit["policies"]["cold"]["decision_match_rate"] == 1.0
    assert audit["policies"]["cold"]["false_discovery_rate"] == 0.0


def test_threshold_commitment_tampering_is_rejected(tmp_path):
    path = _write_suite(tmp_path)
    report = json.loads(path.read_text())
    report["calibration"]["chosen_threshold"]["minimum_score"] = 0.70
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    audit = audit_calibration_report(path)
    codes = {issue["code"] for issue in audit["issues"]}
    assert audit["calibration_valid"] is False
    assert "threshold_commitment_mismatch" in codes
    assert "threshold_selection_mismatch" in codes


def test_overlapping_splits_are_rejected(tmp_path):
    path = _write_suite(tmp_path)
    report = json.loads(path.read_text())
    report["test"]["test_seeds"] = [2101]
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    audit = audit_calibration_report(path)
    assert audit["split_disjoint"] is False
    assert "split_overlap" in {issue["code"] for issue in audit["issues"]}


def test_test_artifact_threshold_drift_is_rejected(tmp_path):
    path = _write_suite(tmp_path)
    root = path.parent
    artifact_path = root / "test" / "ratio_supported" / "cold.eja.json"
    artifact = json.loads(artifact_path.read_text())
    artifact["challenge_protocol"]["selection_rule"]["minimum_score"] = 0.70
    artifact["provenance"]["artifact_hash"] = artifact_hash(artifact)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    audit = audit_calibration_report(path)
    assert audit["calibration_valid"] is False
    assert "test_selection_rule_mismatch" in {
        issue["code"] for issue in audit["issues"]
    }


def test_cli_registers_calibration_pack():
    args = build_parser().parse_args(["calibration-pack", "calibration-suite.json"])
    assert args.eja_command == "calibration-pack"


def test_calibration_html_preserves_claim_boundary(tmp_path):
    audit = audit_calibration_report(_write_suite(tmp_path))
    html = render_calibration_html(audit)
    assert "Frozen calibration audit" in html
    assert "Commitment valid" in html
    assert "does not establish scientific truth" in html
