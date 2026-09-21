"""Directory-level validation and reporting for CRUMB EJA experiment packs."""

from __future__ import annotations

from collections import Counter
from html import escape
import json
from pathlib import Path
from statistics import fmean
from typing import Any

from .model import artifact_hash, load_artifact, validate_artifact


def discover_artifacts(root: str | Path) -> list[Path]:
    directory = Path(root)
    if not directory.exists():
        raise FileNotFoundError(directory)
    candidates = sorted(path for path in directory.rglob("*.json") if path.is_file())
    artifacts: list[Path] = []
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("artifact_type") == "eja_experiment":
            artifacts.append(path)
    return artifacts


def _winner(artifact: dict[str, Any]) -> str | None:
    hypotheses = artifact.get("hypotheses") or []
    if not hypotheses:
        return None
    return str(max(hypotheses, key=lambda item: float(item.get("score", 0.0))).get("id"))


def validate_pack(root: str | Path, *, verify_hash: bool = True) -> dict[str, Any]:
    directory = Path(root)
    paths = discover_artifacts(directory)
    entries: list[dict[str, Any]] = []
    for path in paths:
        artifact = load_artifact(path)
        report = validate_artifact(artifact, verify_hash=verify_hash)
        entries.append(
            {
                "path": str(path.relative_to(directory)),
                "valid": report.valid,
                "issues": [issue.to_dict() for issue in report.issues],
                "computed_hash": report.computed_hash,
                "recorded_hash": artifact.get("provenance", {}).get("artifact_hash"),
                "experiment_id": artifact.get("experiment", {}).get("id"),
                "world": artifact.get("experiment", {}).get("world"),
                "winner": _winner(artifact),
                "verdict": artifact.get("verification", {}).get("verdict"),
                "trajectory_count": len(artifact.get("trajectories") or []),
                "discovery_complete": artifact.get("metrics", {}).get(
                    "discovery_complete"
                ),
            }
        )

    worlds = Counter(str(entry["world"]) for entry in entries if entry["world"])
    winners = Counter(str(entry["winner"]) for entry in entries if entry["winner"])
    verdicts = Counter(str(entry["verdict"]) for entry in entries if entry["verdict"])
    valid_count = sum(1 for entry in entries if entry["valid"])
    complete_values = [
        bool(entry["discovery_complete"])
        for entry in entries
        if entry["discovery_complete"] is not None
    ]
    trajectory_counts = [entry["trajectory_count"] for entry in entries]
    return {
        "artifact_type": "eja_pack_report",
        "root": str(directory),
        "artifact_count": len(entries),
        "valid_count": valid_count,
        "invalid_count": len(entries) - valid_count,
        "valid_rate": round(valid_count / len(entries), 6) if entries else 0.0,
        "mean_trajectory_count": (
            round(fmean(trajectory_counts), 6) if trajectory_counts else 0.0
        ),
        "discovery_complete_rate": (
            round(fmean(1.0 if value else 0.0 for value in complete_values), 6)
            if complete_values
            else None
        ),
        "worlds": dict(sorted(worlds.items())),
        "winners": dict(sorted(winners.items())),
        "verdicts": dict(sorted(verdicts.items())),
        "entries": entries,
        "pack_hash": "sha256:"
        + __import__("hashlib").sha256(
            json.dumps(
                [entry["computed_hash"] for entry in entries],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }


def summarize_pack(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"EJA artifacts: {report.get('artifact_count', 0)}",
            f"Valid: {report.get('valid_count', 0)}",
            f"Invalid: {report.get('invalid_count', 0)}",
            f"Valid rate: {report.get('valid_rate', 0.0):.3f}",
            f"Mean trajectories: {report.get('mean_trajectory_count', 0.0):.3f}",
            f"Worlds: {json.dumps(report.get('worlds', {}), sort_keys=True)}",
            f"Winners: {json.dumps(report.get('winners', {}), sort_keys=True)}",
            f"Verdicts: {json.dumps(report.get('verdicts', {}), sort_keys=True)}",
            f"Pack hash: {report.get('pack_hash', 'missing')}",
        ]
    )


def render_pack_html(report: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(entry.get('path')))}</td>"
        f"<td>{escape(str(entry.get('valid')))}</td>"
        f"<td>{escape(str(entry.get('world')))}</td>"
        f"<td>{escape(str(entry.get('winner')))}</td>"
        f"<td>{escape(str(entry.get('verdict')))}</td>"
        f"<td>{escape(str(entry.get('trajectory_count')))}</td>"
        "</tr>"
        for entry in report.get("entries", [])
    )
    raw = escape(json.dumps(report, indent=2, sort_keys=True))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRUMB EJA Pack Report</title><style>body{{font:16px/1.5 system-ui;margin:0;background:#0a1020;color:#edf3ff}}main{{width:min(1180px,94vw);margin:36px auto}}section{{background:#111b31;border:1px solid #2b3b5a;border-radius:16px;padding:20px;margin:16px 0}}.stats{{display:flex;gap:10px;flex-wrap:wrap}}.stat{{border:1px solid #2b3b5a;border-radius:999px;padding:8px 12px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #2b3b5a;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#080d19;padding:14px;border-radius:10px}}</style></head><body><main><h1>CRUMB EJA Pack Report</h1><div class="stats"><span class="stat">Artifacts <strong>{report.get('artifact_count', 0)}</strong></span><span class="stat">Valid <strong>{report.get('valid_count', 0)}</strong></span><span class="stat">Invalid <strong>{report.get('invalid_count', 0)}</strong></span><span class="stat">Pack hash <strong>{escape(str(report.get('pack_hash', 'missing')))}</strong></span></div><section><h2>Experiments</h2><table><thead><tr><th>Path</th><th>Valid</th><th>World</th><th>Winner</th><th>Verdict</th><th>Trajectories</th></tr></thead><tbody>{rows}</tbody></table></section><section><h2>Aggregate</h2><pre>{raw}</pre></section><p>A valid pack proves structural and provenance consistency only. It does not prove that the candidate axioms are true outside their recorded verifier scope.</p></main></body></html>"""


def write_pack_report(report: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_pack_html(report), encoding="utf-8")
    return destination
