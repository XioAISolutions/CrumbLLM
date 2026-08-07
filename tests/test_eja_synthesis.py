from __future__ import annotations

import copy
import json
from hashlib import sha256
from pathlib import Path

from crumb_llm.eja import (
    artifact_hash,
    audit_synthesis_artifact,
    audit_synthesis_pack,
    audit_synthesis_suite,
    load_artifact,
    render_synthesis_html,
    synthesis_commitment_payload,
)
from crumb_llm.eja.cli import build_parser
from crumb_llm.eja.model import canonical_json

EXAMPLE = Path(__file__).parents[1] / "examples" / "einstein-elevator.eja.json"


def _commitment(value: object) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _candidate(candidate_id: str, exponents: list[float], score: float, complexity: float) -> dict:
    return {
        "candidate_id": candidate_id,
        "expression": f"y = C * x^{exponents[0]} * z^{exponents[1]}",
        "exponents": exponents,
        "fitted_constant": 2.5,
        "fit_score": score,
        "relative_rmse": 0.0 if score == 1.0 else 0.03,
        "max_relative_error": 0.0 if score == 1.0 else 0.05,
        "complexity": complexity,
    }


def _synthesis_artifact(*, no_fit: bool = False, split: str = "test") -> dict:
    artifact = load_artifact(EXAMPLE)
    grammar = {
        "variables": ["x", "z"],
        "response": "y",
        "form": "C * x^a * z^b",
        "exponent_tokens": [-1.0, -0.5, 0.0, 0.5, 1.0],
        "operators": ["multiply", "power"],
        "constant_fit": "geometric_mean_ratio",
        "candidate_generation": "cartesian_enumeration_from_primitives",
        "maximum_candidates": 25,
    }
    top_id = "sha256:" + "1" * 64
    runner_id = "sha256:" + "2" * 64
    top_score = 0.93 if no_fit else 1.0
    candidates = [
        _candidate(top_id, [0.5, -0.5], top_score, 1.2),
        _candidate(runner_id, [0.5, 0.0], 0.70, 0.6),
    ]
    case_spec = {
        "challenge_id": "synth-no-fit" if no_fit else "synth-positive",
        "case_kind": "test_no_fit" if no_fit else "sqrt_ratio_holdout",
        "deterministic_seed": 101,
        "world": "two-variable-scaling-law-v0.7",
        "kind": "offset_piecewise" if no_fit else "power_law",
    }
    target = {
        "expected_outcome": "abstain" if no_fit else "synthesized_power_law",
        "representable_by_grammar": not no_fit,
        "target_exponents": None if no_fit else [0.5, -0.5],
    }
    threshold = {"minimum_score": 0.95, "minimum_margin": 0.05}
    accepted = not no_fit
    artifact["experiment"]["id"] = case_spec["challenge_id"]
    artifact["experiment"]["world"] = "finite-grammar-scaling-law-v0.7"
    artifact["synthesis_protocol"] = {
        "protocol": "finite_symbolic_grammar_v1",
        "split": split,
        "grammar": grammar,
        "grammar_commitment_hash": _commitment(grammar),
        "case_commitment_hash": _commitment(case_spec),
        "target_commitment_hash": _commitment(target),
        "target_visible_to_agent": False,
        "target_expression_pre_registered": False,
        "candidate_generation": "cartesian_enumeration_from_primitives",
        "generated_candidate_count": len(candidates),
        "frozen_threshold": threshold,
        "threshold_commitment_hash": "sha256:" + "3" * 64 if split == "test" else None,
        "calibration_record_hashes": [],
        "test_answers_used_for_calibration": False,
    }
    artifact["synthesis_candidates"] = candidates
    artifact["synthesis_evaluation"] = {
        "hidden_case_spec": case_spec,
        "target_payload": target,
        "selected_candidate_id": top_id,
        "selected_exponents": [0.5, -0.5],
        "selected_outcome": "abstain" if no_fit else "synthesized_power_law",
        "accepted": accepted,
        "correct": True,
        "exact_exponent_recovery": not no_fit,
        "false_discovery": False,
        "positive_abstention": False,
    }
    artifact.setdefault("metrics", {}).update(
        {
            "winner": top_id,
            "winner_score": top_score,
            "abstained": no_fit,
            "selected_outcome": "abstain" if no_fit else "synthesized_power_law",
            "challenge_correct": True,
            "false_discovery": False,
            "selection_margin": top_score - 0.70,
        }
    )
    artifact["provenance"]["hypothesis_origin"] = "finite_symbolic_grammar_enumeration"
    artifact["provenance"]["hidden_state_exposed_to_agent"] = False
    if no_fit:
        artifact["candidate_axiom"] = None
        artifact["deductions"] = []
        artifact["verification"] = {
            "verdict": "not_evaluated_due_to_abstention",
            "claim_boundary": "No generated expression cleared the frozen threshold.",
        }
    else:
        artifact["candidate_axiom"] = {
            "id": "synthesized-scaling-law-test",
            "statement": "Within scope, y follows a generated power law.",
            "assumptions": ["positive inputs"],
            "falsifiers": ["held-out error"],
            "excluded_claims": ["universality"],
            "generated_candidate_id": top_id,
            "exponents": [0.5, -0.5],
        }
        artifact["verification"] = {
            "verdict": "supported_within_scope",
            "claim_boundary": "Synthetic probes only.",
        }
    artifact["provenance"]["artifact_hash"] = artifact_hash(artifact)
    return artifact


def _suite_report() -> dict:
    grammar = _synthesis_artifact()["synthesis_protocol"]["grammar"]
    positive = {
        "split": "calibration",
        "seed": 1,
        "case_kind": "linear_ratio",
        "expected_outcome": "synthesized_power_law",
        "target_exponents": [1.0, -1.0],
        "top_candidate_id": "sha256:" + "a" * 64,
        "top_exponents": [1.0, -1.0],
        "top_score": 1.0,
        "selection_margin": 0.3,
    }
    positive["record_hash"] = _commitment(positive)
    no_fit = {
        "split": "calibration",
        "seed": 1,
        "case_kind": "calibration_no_fit",
        "expected_outcome": "abstain",
        "target_exponents": None,
        "top_candidate_id": "sha256:" + "b" * 64,
        "top_exponents": [0.5, -0.5],
        "top_score": 0.93,
        "selection_margin": 0.2,
    }
    no_fit["record_hash"] = _commitment(no_fit)
    report = {
        "artifact_type": "jump_lab_symbolic_synthesis_suite",
        "suite_version": "0.7",
        "grammar": grammar,
        "grammar_commitment_hash": _commitment(grammar),
        "calibration": {
            "protocol": "disjoint_frozen_synthesis_threshold_v1",
            "calibration_seeds": [1],
            "calibration_cases": ["linear_ratio", "calibration_no_fit"],
            "record_hashes": [positive["record_hash"], no_fit["record_hash"]],
            "candidate_grid": {
                "minimum_scores": [0.90, 0.95],
                "minimum_margins": [0.0],
            },
            "maximum_false_discovery_rate": 0.0,
            "chosen_threshold": {"minimum_score": 0.95, "minimum_margin": 0.0},
            "selection_objective": [
                "maximize calibration accuracy",
                "respect the maximum false-discovery constraint",
                "minimize positive abstention",
                "maximize exact exponent recovery",
                "maximize coverage",
                "prefer the least restrictive tied threshold",
            ],
            "threshold_commitment_hash": "pending",
            "records": [positive, no_fit],
        },
        "test": {
            "test_seeds": [2],
            "test_cases": ["sqrt_ratio_holdout"],
            "answers_used_for_calibration": False,
        },
        "runs": [
            {
                "split": "test",
                "seed": 2,
                "case_kind": "sqrt_ratio_holdout",
                "expected_outcome": "synthesized_power_law",
                "target_exponents": [0.5, -0.5],
                "top_exponents": [0.5, -0.5],
                "top_score": 1.0,
                "selection_margin": 0.3,
            }
        ],
    }
    report["calibration"]["threshold_commitment_hash"] = _commitment(
        synthesis_commitment_payload(report)
    )
    return report


def test_positive_and_no_fit_synthesis_artifacts_audit_cleanly():
    positive = audit_synthesis_artifact(_synthesis_artifact())
    no_fit = audit_synthesis_artifact(_synthesis_artifact(no_fit=True))
    assert positive["synthesis_valid"] is True
    assert positive["exact_exponent_recovery"] is True
    assert no_fit["synthesis_valid"] is True
    assert no_fit["false_discovery"] is False


def test_grammar_tampering_is_detected():
    artifact = _synthesis_artifact()
    artifact["synthesis_protocol"]["grammar"]["exponent_tokens"].append(2.0)
    report = audit_synthesis_artifact(artifact)
    codes = {issue["code"] for issue in report["issues"]}
    assert report["synthesis_valid"] is False
    assert "grammar_commitment_mismatch" in codes


def test_suite_reproduces_threshold_and_holdout_disjointness():
    report = audit_synthesis_suite(_suite_report())
    assert report["suite_valid"] is True
    assert report["threshold_commitment_valid"] is True
    assert report["holdout_target_pairs_disjoint"] is True
    assert report["threshold_reproduced"] == {"minimum_score": 0.95, "minimum_margin": 0.0}


def test_pack_scorecard_and_suite_crosscheck(tmp_path):
    root = tmp_path / "pack"
    root.mkdir()
    positive = _synthesis_artifact()
    no_fit = _synthesis_artifact(no_fit=True)
    suite = _suite_report()
    commitment = suite["calibration"]["threshold_commitment_hash"]
    positive["synthesis_protocol"]["threshold_commitment_hash"] = commitment
    no_fit["synthesis_protocol"]["threshold_commitment_hash"] = commitment
    positive["provenance"]["artifact_hash"] = artifact_hash(positive)
    no_fit["provenance"]["artifact_hash"] = artifact_hash(no_fit)
    (root / "positive.eja.json").write_text(json.dumps(positive, indent=2, sort_keys=True) + "\n")
    (root / "no-fit.eja.json").write_text(json.dumps(no_fit, indent=2, sort_keys=True) + "\n")
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(suite, indent=2, sort_keys=True) + "\n")
    report = audit_synthesis_pack(root, suite=suite_path)
    assert report["synthesis_valid"] is True
    assert report["test_accuracy"] == 1.0
    assert report["heldout_exact_recovery_rate"] == 1.0
    assert report["no_fit_abstention_accuracy"] == 1.0
    assert report["false_discovery_rate"] == 0.0


def test_cli_registers_synthesis_pack_and_html_preserves_boundary(tmp_path):
    args = build_parser().parse_args(["synthesis-pack", "artifacts", "--suite", "suite.json"])
    assert args.eja_command == "synthesis-pack"
    root = tmp_path / "pack"
    root.mkdir()
    artifact = _synthesis_artifact()
    (root / "positive.eja.json").write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    report = audit_synthesis_pack(root)
    html = render_synthesis_html(report)
    assert "Finite-grammar symbolic synthesis audit" in html
    assert "Exact recovery" in html
    assert "does not validate open-ended scientific discovery" in html
