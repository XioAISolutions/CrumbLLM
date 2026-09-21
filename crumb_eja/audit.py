"""Scientific-consistency audits, lineage graphs, and manifests for EJA packs."""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from statistics import fmean
from typing import Any

from .model import artifact_hash, canonical_json, load_artifact
from .pack import discover_artifacts, validate_pack


def _winner(artifact: dict[str, Any]) -> str | None:
    hypotheses = artifact.get("hypotheses") or []
    if not hypotheses:
        return None
    return str(max(hypotheses, key=lambda item: float(item.get("score", 0.0))).get("id"))


def _entries(root: str | Path) -> tuple[Path, list[dict[str, Any]]]:
    directory = Path(root)
    entries: list[dict[str, Any]] = []
    for path in discover_artifacts(directory):
        artifact = load_artifact(path)
        computed = artifact_hash(artifact)
        provenance = artifact.get("provenance") or {}
        axiom = artifact.get("candidate_axiom") or {}
        entries.append(
            {
                "path": str(path.relative_to(directory)),
                "artifact": artifact,
                "hash": computed,
                "recorded_hash": provenance.get("artifact_hash"),
                "parents": list(provenance.get("parent_artifact_hashes") or []),
                "experiment_id": artifact.get("experiment", {}).get("id"),
                "world": artifact.get("experiment", {}).get("world"),
                "seed": artifact.get("experiment", {}).get("deterministic_seed"),
                "winner": _winner(artifact),
                "axiom_id": axiom.get("id"),
                "axiom_status": axiom.get("status"),
                "verdict": artifact.get("verification", {}).get("verdict"),
                "discovery_complete": artifact.get("metrics", {}).get(
                    "discovery_complete"
                ),
            }
        )
    return directory, entries


def build_lineage(root: str | Path) -> dict[str, Any]:
    directory, entries = _entries(root)
    paths_by_hash: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        paths_by_hash[entry["hash"]].append(entry["path"])
    known_hashes = set(paths_by_hash)

    edges: list[dict[str, str]] = []
    missing_parents: list[dict[str, str]] = []
    adjacency: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        child_hash = entry["hash"]
        for raw_parent in entry["parents"]:
            parent_hash = str(raw_parent)
            edges.append({"parent": parent_hash, "child": child_hash})
            if parent_hash in known_hashes:
                adjacency[parent_hash].append(child_hash)
            else:
                missing_parents.append(
                    {
                        "child": child_hash,
                        "child_path": entry["path"],
                        "missing_parent": parent_hash,
                    }
                )

    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in visiting:
            start = stack.index(node) if node in stack else 0
            cycle = stack[start:] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for child in adjacency.get(node, []):
            visit(child)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(known_hashes):
        visit(node)

    duplicate_hashes = {
        digest: sorted(paths)
        for digest, paths in sorted(paths_by_hash.items())
        if len(paths) > 1
    }
    nodes = [
        {
            key: entry[key]
            for key in (
                "path",
                "hash",
                "experiment_id",
                "world",
                "seed",
                "winner",
                "axiom_id",
                "verdict",
                "parents",
            )
        }
        for entry in entries
    ]
    return {
        "artifact_type": "eja_lineage_graph",
        "root": str(directory),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "missing_parents": missing_parents,
        "duplicate_hashes": duplicate_hashes,
        "cycles": cycles,
        "acyclic": not cycles,
        "claim_boundary": (
            "Lineage records declared artifact dependencies and detects structural "
            "problems. It does not prove that a child experiment scientifically "
            "follows from its parent."
        ),
    }


def _replication_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        world = str(entry.get("world") or "unknown-world")
        axiom_id = str(entry.get("axiom_id") or "no-candidate-axiom")
        groups[(world, axiom_id)].append(entry)

    results: list[dict[str, Any]] = []
    for (world, axiom_id), members in sorted(groups.items()):
        verdicts = Counter(str(item.get("verdict")) for item in members)
        winners = Counter(str(item.get("winner")) for item in members)
        completion_values = [
            bool(item["discovery_complete"])
            for item in members
            if item.get("discovery_complete") is not None
        ]
        results.append(
            {
                "world": world,
                "axiom_id": axiom_id,
                "run_count": len(members),
                "seeds": sorted(
                    item["seed"] for item in members if item.get("seed") is not None
                ),
                "verdicts": dict(sorted(verdicts.items())),
                "winners": dict(sorted(winners.items())),
                "consistent_verdict": len(verdicts) <= 1,
                "consistent_winner": len(winners) <= 1,
                "discovery_complete_rate": (
                    round(
                        fmean(1.0 if value else 0.0 for value in completion_values),
                        6,
                    )
                    if completion_values
                    else None
                ),
            }
        )
    return results


def audit_pack(root: str | Path, *, verify_hash: bool = True) -> dict[str, Any]:
    directory, entries = _entries(root)
    validation = validate_pack(directory, verify_hash=verify_hash)
    lineage = build_lineage(directory)
    issues: list[dict[str, str]] = []

    if not entries:
        issues.append(
            {
                "severity": "error",
                "code": "empty_pack",
                "path": str(directory),
                "message": "No EJA experiment artifacts were found.",
            }
        )

    for validation_entry in validation.get("entries", []):
        if not validation_entry.get("valid"):
            issues.append(
                {
                    "severity": "error",
                    "code": "invalid_artifact",
                    "path": str(validation_entry.get("path")),
                    "message": "Artifact failed structural or provenance validation.",
                }
            )

    for entry in entries:
        artifact = entry["artifact"]
        candidate = artifact.get("candidate_axiom")
        complete = entry.get("discovery_complete")
        if complete is False and candidate is not None:
            issues.append(
                {
                    "severity": "error",
                    "code": "premature_axiom",
                    "path": entry["path"],
                    "message": "A candidate axiom exists although discovery_complete is false.",
                }
            )
        if complete is True and candidate is None:
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_completed_axiom",
                    "path": entry["path"],
                    "message": "Discovery is marked complete but no candidate axiom is recorded.",
                }
            )
        if candidate is not None:
            status = str(candidate.get("status", ""))
            verdict = str(entry.get("verdict", ""))
            if status == "supported_within_scope" and verdict != "supported_within_scope":
                issues.append(
                    {
                        "severity": "error",
                        "code": "axiom_verdict_mismatch",
                        "path": entry["path"],
                        "message": "Candidate status claims support but verifier verdict does not.",
                    }
                )
        if entry["hash"] in entry["parents"]:
            issues.append(
                {
                    "severity": "error",
                    "code": "self_parent",
                    "path": entry["path"],
                    "message": "Artifact declares itself as a parent.",
                }
            )

    for digest, paths in lineage.get("duplicate_hashes", {}).items():
        issues.append(
            {
                "severity": "warning",
                "code": "duplicate_artifact_hash",
                "path": ", ".join(paths),
                "message": f"The same canonical artifact hash occurs more than once: {digest}",
            }
        )
    for missing in lineage.get("missing_parents", []):
        issues.append(
            {
                "severity": "warning",
                "code": "missing_parent",
                "path": missing["child_path"],
                "message": f"Declared parent is outside this pack: {missing['missing_parent']}",
            }
        )
    for cycle in lineage.get("cycles", []):
        issues.append(
            {
                "severity": "error",
                "code": "lineage_cycle",
                "path": " -> ".join(cycle),
                "message": "Artifact lineage contains a cycle.",
            }
        )

    replication = _replication_groups(entries)
    for group in replication:
        if not group["consistent_verdict"]:
            issues.append(
                {
                    "severity": "error",
                    "code": "conflicting_verdicts",
                    "path": f"{group['world']}::{group['axiom_id']}",
                    "message": "Replicated runs record conflicting verifier verdicts.",
                }
            )
        if not group["consistent_winner"]:
            issues.append(
                {
                    "severity": "warning",
                    "code": "winner_instability",
                    "path": f"{group['world']}::{group['axiom_id']}",
                    "message": "Replicated runs do not share the same leading hypothesis.",
                }
            )

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "artifact_type": "eja_scientific_audit",
        "audit_version": "0.3",
        "root": str(directory),
        "audit_valid": error_count == 0 and bool(entries),
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
        "validation_summary": {
            key: validation.get(key)
            for key in (
                "artifact_count",
                "valid_count",
                "invalid_count",
                "valid_rate",
                "pack_hash",
            )
        },
        "lineage_summary": {
            "node_count": lineage["node_count"],
            "edge_count": lineage["edge_count"],
            "missing_parent_count": len(lineage["missing_parents"]),
            "duplicate_hash_count": len(lineage["duplicate_hashes"]),
            "acyclic": lineage["acyclic"],
        },
        "replication_groups": replication,
        "claim_boundary": (
            "A passing audit establishes internal structural, provenance, lineage, "
            "and verdict consistency. It does not establish the truth of any candidate "
            "axiom beyond each artifact's recorded verifier scope."
        ),
    }


def build_manifest(root: str | Path, *, verify_hash: bool = True) -> dict[str, Any]:
    directory, entries = _entries(root)
    validation = validate_pack(directory, verify_hash=verify_hash)
    manifest_entries = [
        {
            key: entry[key]
            for key in (
                "path",
                "hash",
                "recorded_hash",
                "experiment_id",
                "world",
                "seed",
                "winner",
                "axiom_id",
                "verdict",
                "parents",
            )
        }
        for entry in entries
    ]
    manifest: dict[str, Any] = {
        "artifact_type": "eja_pack_manifest",
        "manifest_version": "0.3",
        "root": str(directory),
        "pack_hash": validation.get("pack_hash"),
        "entries": manifest_entries,
        "manifest_hash": "pending",
        "claim_boundary": (
            "The manifest identifies pack contents and declared lineage. It is not a "
            "scientific endorsement of the recorded candidate axioms."
        ),
    }
    clone = json.loads(json.dumps(manifest))
    clone["manifest_hash"] = "pending"
    manifest["manifest_hash"] = "sha256:" + sha256(
        canonical_json(clone).encode("utf-8")
    ).hexdigest()
    return manifest


def render_audit_html(report: dict[str, Any]) -> str:
    issue_rows = "".join(
        "<tr>"
        f"<td>{escape(str(issue.get('severity')))}</td>"
        f"<td>{escape(str(issue.get('code')))}</td>"
        f"<td>{escape(str(issue.get('path')))}</td>"
        f"<td>{escape(str(issue.get('message')))}</td>"
        "</tr>"
        for issue in report.get("issues", [])
    )
    replication_rows = "".join(
        "<tr>"
        f"<td>{escape(str(group.get('world')))}</td>"
        f"<td>{escape(str(group.get('axiom_id')))}</td>"
        f"<td>{escape(str(group.get('run_count')))}</td>"
        f"<td>{escape(str(group.get('consistent_verdict')))}</td>"
        f"<td>{escape(str(group.get('consistent_winner')))}</td>"
        "</tr>"
        for group in report.get("replication_groups", [])
    )
    raw = escape(json.dumps(report, indent=2, sort_keys=True))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRUMB EJA Scientific Audit</title><style>body{{font:16px/1.5 system-ui;margin:0;background:#091020;color:#eff5ff}}main{{width:min(1220px,94vw);margin:36px auto}}section{{background:#111b31;border:1px solid #2b3c5d;border-radius:16px;padding:20px;margin:16px 0}}.stats{{display:flex;gap:10px;flex-wrap:wrap}}.stat{{padding:8px 12px;border:1px solid #2b3c5d;border-radius:999px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #2b3c5d;text-align:left;vertical-align:top}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#070c18;padding:14px;border-radius:10px}}</style></head><body><main><h1>CRUMB EJA v0.3 Scientific Audit</h1><div class="stats"><span class="stat">Valid <strong>{escape(str(report.get('audit_valid')))}</strong></span><span class="stat">Errors <strong>{escape(str(report.get('error_count')))}</strong></span><span class="stat">Warnings <strong>{escape(str(report.get('warning_count')))}</strong></span></div><section><h2>Issues</h2><table><thead><tr><th>Severity</th><th>Code</th><th>Path</th><th>Message</th></tr></thead><tbody>{issue_rows}</tbody></table></section><section><h2>Replication groups</h2><table><thead><tr><th>World</th><th>Axiom</th><th>Runs</th><th>Verdict stable</th><th>Winner stable</th></tr></thead><tbody>{replication_rows}</tbody></table></section><section><h2>Raw audit</h2><pre>{raw}</pre></section><p><strong>Claim boundary:</strong> {escape(str(report.get('claim_boundary', 'missing')))}</p></main></body></html>"""


def render_lineage_html(graph: dict[str, Any]) -> str:
    node_rows = "".join(
        "<tr>"
        f"<td>{escape(str(node.get('path')))}</td>"
        f"<td>{escape(str(node.get('experiment_id')))}</td>"
        f"<td>{escape(str(node.get('world')))}</td>"
        f"<td>{escape(str(len(node.get('parents') or [])))}</td>"
        f"<td><code>{escape(str(node.get('hash')))}</code></td>"
        "</tr>"
        for node in graph.get("nodes", [])
    )
    edge_rows = "".join(
        "<tr>"
        f"<td><code>{escape(str(edge.get('parent')))}</code></td>"
        f"<td><code>{escape(str(edge.get('child')))}</code></td>"
        "</tr>"
        for edge in graph.get("edges", [])
    )
    raw = escape(json.dumps(graph, indent=2, sort_keys=True))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRUMB EJA Lineage</title><style>body{{font:16px/1.5 system-ui;margin:0;background:#08101d;color:#eef5ff}}main{{width:min(1220px,94vw);margin:36px auto}}section{{background:#111c30;border:1px solid #2a3d5a;border-radius:16px;padding:20px;margin:16px 0}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #2a3d5a;text-align:left;vertical-align:top}}code{{font-size:.78rem;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#070c16;padding:14px;border-radius:10px}}</style></head><body><main><h1>CRUMB EJA v0.3 Lineage</h1><p>Nodes: <strong>{escape(str(graph.get('node_count')))}</strong> · Edges: <strong>{escape(str(graph.get('edge_count')))}</strong> · Acyclic: <strong>{escape(str(graph.get('acyclic')))}</strong></p><section><h2>Artifacts</h2><table><thead><tr><th>Path</th><th>Experiment</th><th>World</th><th>Parents</th><th>Hash</th></tr></thead><tbody>{node_rows}</tbody></table></section><section><h2>Edges</h2><table><thead><tr><th>Parent</th><th>Child</th></tr></thead><tbody>{edge_rows}</tbody></table></section><section><h2>Raw graph</h2><pre>{raw}</pre></section><p><strong>Claim boundary:</strong> {escape(str(graph.get('claim_boundary', 'missing')))}</p></main></body></html>"""


def write_html_report(content: str, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination
