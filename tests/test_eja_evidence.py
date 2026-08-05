from __future__ import annotations

import json
from pathlib import Path

from crumb_llm.eja import (
    artifact_hash,
    audit_evidence_artifact,
    audit_evidence_pack,
    build_evidence_graph,
    build_review_bundle,
    load_artifact,
)
from crumb_llm.eja.cli import build_parser

EXAMPLE = Path(__file__).parents[1] / "examples" / "einstein-elevator.eja.json"


def _blind_artifact() -> dict:
    artifact = load_artifact(EXAMPLE)
    refs = []
    for index, trajectory in enumerate(artifact.get("trajectories") or [], start=1):
        ref = f"evidence-{index:03d}"
        trajectory["evidence_ref"] = ref
        trajectory["observed_signature"] = "pair_matches"
        refs.append(ref)
    if not refs:
        raise AssertionError("example must contain trajectories")
    for index, hypothesis in enumerate(artifact["hypotheses"]):
        hypothesis["evidence_for"] = [refs[index % len(refs)]]
        hypothesis["evidence_against"] = []
        hypothesis["statement_visible_to_agent"] = False
        hypothesis["semantic_key"] = f"model-{index + 1}"

    artifact["deductions"] = artifact.get("deductions") or [
        {
            "id": "D-test",
            "derived_from": artifact["candidate_axiom"]["id"],
            "prediction": "Recorded intervention evidence tests the candidate axiom.",
        }
    ]
    for deduction in artifact["deductions"]:
        deduction["evidence_refs"] = [refs[0]]

    artifact["blind_protocol"] = {
        "protocol": "pre_registered_anonymous_model_selection_v1",
        "open_ended_abduction": False,
        "model_statements_visible_to_agent": False,
        "target_terms_withheld": ["target phrase"],
        "leakage_hits": [],
        "mapping_hash": "sha256:" + "1" * 64,
        "agent_prompt_hash": "sha256:" + "2" * 64,
        "reveal_policy": "reveal only after selection",
    }
    artifact["provenance"]["hypothesis_origin"] = (
        "pre_registered_anonymous_prediction_deck"
    )
    artifact["provenance"]["artifact_hash"] = artifact_hash(artifact)
    return artifact


def _pack(tmp_path: Path) -> Path:
    root = tmp_path / "pack"
    root.mkdir()
    artifact = _blind_artifact()
    path = root / "blind-run.eja.json"
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return root


def test_evidence_graph_resolves_hypothesis_and_deduction_references():
    artifact = _blind_artifact()
    graph = build_evidence_graph(artifact)
    assert graph["missing_references"] == []
    assert graph["duplicate_evidence_refs"] == []
    assert any(edge["relation"] == "supports" for edge in graph["edges"])
    assert any(edge["relation"] == "tests" for edge in graph["edges"])
    assert any(node["type"] == "verification" for node in graph["nodes"])


def test_blind_evidence_audit_accepts_complete_provenance():
    report = audit_evidence_artifact(_blind_artifact())
    assert report["evidence_valid"] is True
    assert report["error_count"] == 0


def test_blind_evidence_audit_rejects_leakage_and_missing_refs():
    artifact = _blind_artifact()
    artifact["blind_protocol"]["leakage_hits"] = ["target phrase"]
    artifact["hypotheses"][0]["evidence_for"] = ["missing-evidence"]
    report = audit_evidence_artifact(artifact)
    codes = {issue["code"] for issue in report["issues"]}
    assert report["evidence_valid"] is False
    assert "target_language_leakage" in codes
    assert "missing_evidence_reference" in codes


def test_pack_evidence_audit_aggregates_artifacts(tmp_path):
    report = audit_evidence_pack(_pack(tmp_path))
    assert report["artifact_count"] == 1
    assert report["valid_count"] == 1
    assert report["evidence_valid"] is True


def test_review_bundle_is_deterministic_and_contains_review_gates(tmp_path):
    root = _pack(tmp_path)
    first = build_review_bundle(root, tmp_path / "first.zip")
    second = build_review_bundle(root, tmp_path / "second.zip")
    assert first["bundle_sha256"] == second["bundle_sha256"]
    assert first["validation_valid"] is True
    assert first["scientific_audit_valid"] is True
    assert first["evidence_audit_valid"] is True
    assert first["file_count"] >= 7


def test_cli_registers_evidence_and_bundle_commands():
    parser = build_parser()
    evidence = parser.parse_args(["evidence-pack", "examples"])
    bundle = parser.parse_args(
        ["bundle-pack", "examples", "--out", "review.zip"]
    )
    assert evidence.eja_command == "evidence-pack"
    assert bundle.eja_command == "bundle-pack"
