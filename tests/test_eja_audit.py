from __future__ import annotations

import copy
import json
from pathlib import Path

from crumb_llm.eja import (
    artifact_hash,
    audit_pack,
    build_lineage,
    build_manifest,
    load_artifact,
    render_audit_html,
    render_lineage_html,
)
from crumb_llm.eja.cli import build_parser

EXAMPLE = Path(__file__).parents[1] / "examples" / "einstein-elevator.eja.json"


def _write(root: Path, name: str, artifact: dict) -> Path:
    artifact.setdefault("provenance", {})["artifact_hash"] = "pending"
    artifact["provenance"]["artifact_hash"] = artifact_hash(artifact)
    path = root / name
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return path


def _lineage_pack(tmp_path: Path) -> Path:
    root = tmp_path / "lineage"
    root.mkdir()
    parent = load_artifact(EXAMPLE)
    parent["experiment"]["id"] = "parent-run"
    _write(root, "parent.json", parent)

    child = load_artifact(EXAMPLE)
    child["experiment"]["id"] = "child-run"
    child.setdefault("provenance", {})["parent_artifact_hashes"] = [
        parent["provenance"]["artifact_hash"]
    ]
    _write(root, "child.json", child)
    return root


def test_lineage_builds_internal_parent_child_edge(tmp_path):
    graph = build_lineage(_lineage_pack(tmp_path))
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1
    assert graph["missing_parents"] == []
    assert graph["acyclic"] is True


def test_audit_accepts_consistent_lineage_pack(tmp_path):
    report = audit_pack(_lineage_pack(tmp_path))
    assert report["audit_valid"] is True
    assert report["error_count"] == 0
    assert report["lineage_summary"]["edge_count"] == 1
    assert report["replication_groups"][0]["consistent_verdict"] is True


def test_audit_rejects_premature_axiom(tmp_path):
    root = tmp_path / "premature"
    root.mkdir()
    artifact = load_artifact(EXAMPLE)
    artifact["metrics"] = {"discovery_complete": False}
    _write(root, "run.json", artifact)
    report = audit_pack(root)
    assert report["audit_valid"] is False
    assert any(issue["code"] == "premature_axiom" for issue in report["issues"])


def test_audit_rejects_conflicting_replicated_verdicts(tmp_path):
    root = tmp_path / "conflict"
    root.mkdir()
    first = load_artifact(EXAMPLE)
    first["experiment"]["id"] = "first"
    _write(root, "first.json", first)

    second = copy.deepcopy(first)
    second["experiment"]["id"] = "second"
    second["verification"]["verdict"] = "contradicted"
    _write(root, "second.json", second)
    report = audit_pack(root)
    assert report["audit_valid"] is False
    codes = {issue["code"] for issue in report["issues"]}
    assert "conflicting_verdicts" in codes
    assert "axiom_verdict_mismatch" in codes


def test_missing_external_parent_is_warning_not_false_proof(tmp_path):
    root = tmp_path / "external-parent"
    root.mkdir()
    artifact = load_artifact(EXAMPLE)
    artifact.setdefault("provenance", {})["parent_artifact_hashes"] = [
        "sha256:" + "f" * 64
    ]
    _write(root, "run.json", artifact)
    report = audit_pack(root)
    assert report["audit_valid"] is True
    assert any(issue["code"] == "missing_parent" for issue in report["issues"])


def test_manifest_is_deterministic_and_hash_addressed(tmp_path):
    root = _lineage_pack(tmp_path)
    first = build_manifest(root)
    second = build_manifest(root)
    assert first == second
    assert first["manifest_hash"].startswith("sha256:")
    assert first["pack_hash"].startswith("sha256:")
    assert len(first["entries"]) == 2


def test_audit_and_lineage_html_preserve_claim_boundaries(tmp_path):
    root = _lineage_pack(tmp_path)
    audit_html = render_audit_html(audit_pack(root))
    lineage_html = render_lineage_html(build_lineage(root))
    assert "Scientific Audit" in audit_html
    assert "Claim boundary" in audit_html
    assert "CRUMB EJA v0.3 Lineage" in lineage_html
    assert "does not prove" in lineage_html


def test_cli_registers_v03_pack_commands():
    parser = build_parser()
    assert parser.parse_args(["audit-pack", "artifacts"]).eja_command == "audit-pack"
    assert (
        parser.parse_args(["lineage-pack", "artifacts"]).eja_command
        == "lineage-pack"
    )
    assert (
        parser.parse_args(["manifest-pack", "artifacts"]).eja_command
        == "manifest-pack"
    )
