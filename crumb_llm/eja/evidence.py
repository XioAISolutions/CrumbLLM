"""Evidence graphs, blinded-protocol audits, and deterministic review bundles."""

from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .audit import audit_pack, build_lineage, build_manifest
from .model import artifact_hash, canonical_json, load_artifact
from .pack import discover_artifacts, validate_pack


def _node_id(prefix: str, value: str) -> str:
    return f"{prefix}:{value}"


def build_evidence_graph(artifact: dict[str, Any]) -> dict[str, Any]:
    """Build a directed graph from observations to hypotheses, deductions, and verdict."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    evidence_ids: set[str] = set()
    duplicate_evidence_refs: list[str] = []

    observations = artifact.get("experience", {}).get("initial_observations") or []
    for index, observation in enumerate(observations):
        observation_id = str(observation.get("observation_id") or f"initial-{index + 1}")
        node_id = _node_id("observation", observation_id)
        nodes.append(
            {
                "id": node_id,
                "type": "observation",
                "label": observation_id,
                "source": "experience.initial_observations",
            }
        )

    trajectory_ref_by_index: list[str] = []
    for index, trajectory in enumerate(artifact.get("trajectories") or []):
        evidence_ref = str(trajectory.get("evidence_ref") or f"trajectory-{index + 1}")
        if evidence_ref in evidence_ids:
            duplicate_evidence_refs.append(evidence_ref)
        evidence_ids.add(evidence_ref)
        trajectory_ref_by_index.append(evidence_ref)
        nodes.append(
            {
                "id": _node_id("evidence", evidence_ref),
                "type": "intervention_evidence",
                "label": evidence_ref,
                "action": (trajectory.get("intervention") or {}).get("action_type"),
                "signature": trajectory.get("observed_signature"),
            }
        )

    missing_references: list[dict[str, str]] = []
    hypotheses = artifact.get("hypotheses") or []
    for hypothesis in hypotheses:
        hypothesis_id = str(hypothesis.get("id") or "unknown")
        hypothesis_node = _node_id("hypothesis", hypothesis_id)
        nodes.append(
            {
                "id": hypothesis_node,
                "type": "hypothesis",
                "label": hypothesis_id,
                "class": hypothesis.get("class"),
                "score": hypothesis.get("score"),
            }
        )
        for relation, field in (("supports", "evidence_for"), ("challenges", "evidence_against")):
            for raw_ref in hypothesis.get(field) or []:
                ref = str(raw_ref)
                if ref in evidence_ids:
                    edges.append(
                        {
                            "from": _node_id("evidence", ref),
                            "to": hypothesis_node,
                            "relation": relation,
                        }
                    )
                elif artifact.get("blind_protocol") is not None:
                    missing_references.append(
                        {
                            "owner": hypothesis_node,
                            "field": field,
                            "missing_ref": ref,
                        }
                    )

    winner_id: str | None = None
    if hypotheses:
        winner = max(hypotheses, key=lambda item: float(item.get("score", 0.0)))
        winner_id = str(winner.get("id"))

    axiom = artifact.get("candidate_axiom")
    axiom_node: str | None = None
    if isinstance(axiom, dict):
        axiom_id = str(axiom.get("id") or "candidate")
        axiom_node = _node_id("axiom", axiom_id)
        nodes.append(
            {
                "id": axiom_node,
                "type": "candidate_axiom",
                "label": axiom_id,
                "status": axiom.get("status"),
            }
        )
        if winner_id:
            edges.append(
                {
                    "from": _node_id("hypothesis", winner_id),
                    "to": axiom_node,
                    "relation": "compiled_into",
                }
            )

    deduction_nodes: list[str] = []
    for index, deduction in enumerate(artifact.get("deductions") or []):
        deduction_id = str(deduction.get("id") or f"deduction-{index + 1}")
        deduction_node = _node_id("deduction", deduction_id)
        deduction_nodes.append(deduction_node)
        nodes.append(
            {
                "id": deduction_node,
                "type": "deduction",
                "label": deduction_id,
                "prediction": deduction.get("prediction"),
            }
        )
        if axiom_node:
            edges.append(
                {
                    "from": axiom_node,
                    "to": deduction_node,
                    "relation": "deduces",
                }
            )
        for raw_ref in deduction.get("evidence_refs") or []:
            ref = str(raw_ref)
            if ref in evidence_ids:
                edges.append(
                    {
                        "from": _node_id("evidence", ref),
                        "to": deduction_node,
                        "relation": "tests",
                    }
                )
            else:
                missing_references.append(
                    {
                        "owner": deduction_node,
                        "field": "evidence_refs",
                        "missing_ref": ref,
                    }
                )

    verdict = artifact.get("verification", {}).get("verdict")
    verification_node = _node_id("verification", str(verdict or "unverified"))
    nodes.append(
        {
            "id": verification_node,
            "type": "verification",
            "label": str(verdict or "unverified"),
        }
    )
    sources = deduction_nodes or ([axiom_node] if axiom_node else [])
    for source in sources:
        if source:
            edges.append(
                {
                    "from": source,
                    "to": verification_node,
                    "relation": "evaluated_by",
                }
            )

    referenced_evidence = {
        edge["from"].split(":", 1)[1]
        for edge in edges
        if edge["from"].startswith("evidence:")
    }
    orphan_evidence = sorted(evidence_ids - referenced_evidence)
    return {
        "artifact_type": "eja_evidence_graph",
        "experiment_id": artifact.get("experiment", {}).get("id"),
        "artifact_hash": artifact_hash(artifact),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "missing_references": missing_references,
        "duplicate_evidence_refs": sorted(set(duplicate_evidence_refs)),
        "orphan_evidence": orphan_evidence,
        "claim_boundary": (
            "The graph proves that recorded references resolve inside the artifact. "
            "It does not prove that the evidence scientifically supports the claim."
        ),
    }


def audit_evidence_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    graph = build_evidence_graph(artifact)
    issues: list[dict[str, str]] = []
    for missing in graph["missing_references"]:
        issues.append(
            {
                "severity": "error",
                "code": "missing_evidence_reference",
                "path": missing["owner"],
                "message": f"{missing['field']} references unknown evidence {missing['missing_ref']}",
            }
        )
    for ref in graph["duplicate_evidence_refs"]:
        issues.append(
            {
                "severity": "error",
                "code": "duplicate_evidence_reference",
                "path": ref,
                "message": "Evidence references must be unique within an artifact.",
            }
        )
    for ref in graph["orphan_evidence"]:
        issues.append(
            {
                "severity": "warning",
                "code": "orphan_evidence",
                "path": ref,
                "message": "Recorded intervention evidence is not cited by a hypothesis or deduction.",
            }
        )

    blind = artifact.get("blind_protocol")
    if isinstance(blind, dict):
        if blind.get("model_statements_visible_to_agent") is not False:
            issues.append(
                {
                    "severity": "error",
                    "code": "blind_statement_exposure",
                    "path": "blind_protocol.model_statements_visible_to_agent",
                    "message": "Blind model statements must remain hidden during selection.",
                }
            )
        if blind.get("open_ended_abduction") is not False:
            issues.append(
                {
                    "severity": "error",
                    "code": "misclassified_open_ended_claim",
                    "path": "blind_protocol.open_ended_abduction",
                    "message": "A pre-registered model deck must not be labeled open-ended abduction.",
                }
            )
        if blind.get("leakage_hits"):
            issues.append(
                {
                    "severity": "error",
                    "code": "target_language_leakage",
                    "path": "blind_protocol.leakage_hits",
                    "message": "Agent-visible input contains withheld target language.",
                }
            )
        for field in ("mapping_hash", "agent_prompt_hash", "reveal_policy"):
            if not blind.get(field):
                issues.append(
                    {
                        "severity": "error",
                        "code": "incomplete_blind_protocol",
                        "path": f"blind_protocol.{field}",
                        "message": "Required blind-protocol provenance is missing.",
                    }
                )
        origin = artifact.get("provenance", {}).get("hypothesis_origin")
        if origin != "pre_registered_anonymous_prediction_deck":
            issues.append(
                {
                    "severity": "error",
                    "code": "untracked_hypothesis_origin",
                    "path": "provenance.hypothesis_origin",
                    "message": "Blind artifacts must record the pre-registered deck as hypothesis origin.",
                }
            )

    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "artifact_type": "eja_evidence_audit",
        "experiment_id": artifact.get("experiment", {}).get("id"),
        "artifact_hash": artifact_hash(artifact),
        "evidence_valid": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
        "graph": graph,
        "claim_boundary": (
            "A passing evidence audit establishes reference integrity and blind-protocol "
            "bookkeeping only. It does not establish scientific truth or causal validity."
        ),
    }


def audit_evidence_pack(root: str | Path) -> dict[str, Any]:
    directory = Path(root)
    entries = []
    for path in discover_artifacts(directory):
        artifact = load_artifact(path)
        report = audit_evidence_artifact(artifact)
        entries.append(
            {
                "path": str(path.relative_to(directory)),
                "experiment_id": report["experiment_id"],
                "artifact_hash": report["artifact_hash"],
                "evidence_valid": report["evidence_valid"],
                "error_count": report["error_count"],
                "warning_count": report["warning_count"],
                "issues": report["issues"],
                "node_count": report["graph"]["node_count"],
                "edge_count": report["graph"]["edge_count"],
            }
        )
    error_count = sum(entry["error_count"] for entry in entries)
    warning_count = sum(entry["warning_count"] for entry in entries)
    valid_count = sum(1 for entry in entries if entry["evidence_valid"])
    return {
        "artifact_type": "eja_evidence_pack_audit",
        "audit_version": "0.4",
        "root": str(directory),
        "artifact_count": len(entries),
        "valid_count": valid_count,
        "invalid_count": len(entries) - valid_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "evidence_valid": bool(entries) and error_count == 0,
        "entries": entries,
        "claim_boundary": (
            "This pack audit checks evidence references and blind-protocol provenance. "
            "It does not validate the scientific conclusions in the pack."
        ),
    }


def render_evidence_html(report: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(entry.get('path')))}</td>"
        f"<td>{escape(str(entry.get('evidence_valid')))}</td>"
        f"<td>{escape(str(entry.get('node_count')))}</td>"
        f"<td>{escape(str(entry.get('edge_count')))}</td>"
        f"<td>{escape(str(entry.get('error_count')))}</td>"
        f"<td>{escape(str(entry.get('warning_count')))}</td>"
        "</tr>"
        for entry in report.get("entries", [])
    )
    raw = escape(json.dumps(report, indent=2, sort_keys=True))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRUMB EJA Evidence Audit</title><style>body{{font:16px/1.5 system-ui;margin:0;background:#091020;color:#eff5ff}}main{{width:min(1220px,94vw);margin:36px auto}}section{{background:#111b31;border:1px solid #2b3c5d;border-radius:16px;padding:20px;margin:16px 0}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #2b3c5d;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#070c18;padding:14px;border-radius:10px}}</style></head><body><main><h1>CRUMB EJA v0.4 Evidence Audit</h1><p>Valid: <strong>{escape(str(report.get('evidence_valid')))}</strong> · Errors: <strong>{escape(str(report.get('error_count')))}</strong> · Warnings: <strong>{escape(str(report.get('warning_count')))}</strong></p><section><table><thead><tr><th>Path</th><th>Valid</th><th>Nodes</th><th>Edges</th><th>Errors</th><th>Warnings</th></tr></thead><tbody>{rows}</tbody></table></section><section><pre>{raw}</pre></section><p>{escape(str(report.get('claim_boundary', 'missing')))}</p></main></body></html>"""


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_review_bundle(root: str | Path, output: str | Path) -> dict[str, Any]:
    """Create a deterministic ZIP containing artifacts and all review reports."""
    directory = Path(root)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    artifacts = discover_artifacts(directory)
    validation = validate_pack(directory)
    scientific = audit_pack(directory)
    lineage = build_lineage(directory)
    manifest = build_manifest(directory)
    evidence = audit_evidence_pack(directory)

    report_files = {
        "reports/validation.json": validation,
        "reports/scientific-audit.json": scientific,
        "reports/lineage.json": lineage,
        "reports/manifest.json": manifest,
        "reports/evidence-audit.json": evidence,
    }
    index_entries = []
    for path in artifacts:
        raw = path.read_bytes()
        relative = str(path.relative_to(directory)).replace("\\", "/")
        index_entries.append(
            {
                "path": f"artifacts/{relative}",
                "sha256": sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
        )
    for name, value in sorted(report_files.items()):
        raw = _json_bytes(value)
        index_entries.append(
            {"path": name, "sha256": sha256(raw).hexdigest(), "size_bytes": len(raw)}
        )
    index = {
        "artifact_type": "eja_review_bundle_index",
        "bundle_version": "0.4",
        "source_root": str(directory),
        "entries": sorted(index_entries, key=lambda item: item["path"]),
        "validation_valid": validation.get("invalid_count") == 0 and validation.get("artifact_count", 0) > 0,
        "scientific_audit_valid": scientific.get("audit_valid"),
        "evidence_audit_valid": evidence.get("evidence_valid"),
        "claim_boundary": (
            "The bundle is a deterministic review package. Inclusion does not imply "
            "scientific endorsement of any candidate axiom."
        ),
    }
    index["index_hash"] = "sha256:" + sha256(canonical_json(index).encode("utf-8")).hexdigest()

    with ZipFile(destination, "w") as archive:
        for path in artifacts:
            relative = str(path.relative_to(directory)).replace("\\", "/")
            archive.writestr(_zip_info(f"artifacts/{relative}"), path.read_bytes())
        for name, value in sorted(report_files.items()):
            archive.writestr(_zip_info(name), _json_bytes(value))
        archive.writestr(_zip_info("INDEX.json"), _json_bytes(index))

    raw_bundle = destination.read_bytes()
    return {
        "artifact_type": "eja_review_bundle_result",
        "bundle_version": "0.4",
        "path": str(destination),
        "file_count": len(index_entries) + 1,
        "bundle_sha256": "sha256:" + sha256(raw_bundle).hexdigest(),
        "index_hash": index["index_hash"],
        "validation_valid": index["validation_valid"],
        "scientific_audit_valid": index["scientific_audit_valid"],
        "evidence_audit_valid": index["evidence_audit_valid"],
        "claim_boundary": index["claim_boundary"],
    }
