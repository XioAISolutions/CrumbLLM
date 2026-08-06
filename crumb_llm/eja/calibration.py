"""Audit disjoint threshold calibration and frozen unseen-test decisions."""

from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

from .challenge import audit_challenge_artifact
from .model import artifact_hash, canonical_json, load_artifact, validate_artifact

CALIBRATION_ARTIFACT_TYPE = "jump_lab_calibrated_challenge_suite"


def _commitment(value: Any) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _issue(
    issues: list[dict[str, str]],
    code: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
) -> None:
    issues.append(
        {
            "severity": severity,
            "code": code,
            "path": path,
            "message": message,
        }
    )


def calibration_commitment_payload(report: dict[str, Any]) -> dict[str, Any]:
    calibration = report.get("calibration") or {}
    return {
        "protocol": calibration.get("protocol"),
        "calibration_seeds": calibration.get("calibration_seeds"),
        "case_kinds": calibration.get("case_kinds"),
        "candidate_grid": calibration.get("candidate_grid"),
        "maximum_false_discovery_rate": calibration.get(
            "maximum_false_discovery_rate"
        ),
        "record_hashes": calibration.get("record_hashes"),
        "chosen_threshold": calibration.get("chosen_threshold"),
        "selection_objective": calibration.get("selection_objective"),
    }


def _record_hash(record: dict[str, Any]) -> str:
    clone = dict(record)
    clone.pop("record_hash", None)
    return _commitment(clone)


def _rate(items: list[dict[str, Any]], field: str) -> float | None:
    if not items:
        return None
    return round(fmean(1.0 if item[field] else 0.0 for item in items), 6)


def apply_frozen_threshold(
    record: dict[str, Any],
    threshold: dict[str, float],
) -> dict[str, Any]:
    accepted = bool(
        record.get("base_discovery_complete")
        and float(record.get("top_score", 0.0)) >= float(threshold["minimum_score"])
        and float(record.get("selection_margin", 0.0))
        >= float(threshold["minimum_margin"])
    )
    selected = record.get("top_semantic_key") if accepted else "abstain"
    expected = record.get("expected_outcome")
    return {
        **record,
        "selected_outcome": selected,
        "abstained": not accepted,
        "correct": selected == expected,
        "false_discovery": bool(expected == "abstain" and accepted),
        "positive_abstention": bool(expected != "abstain" and not accepted),
    }


def score_threshold(
    records: list[dict[str, Any]],
    threshold: dict[str, float],
) -> dict[str, Any]:
    decisions = [apply_frozen_threshold(record, threshold) for record in records]
    answerable = [item for item in decisions if item["expected_outcome"] != "abstain"]
    no_fit = [item for item in decisions if item["expected_outcome"] == "abstain"]
    accepted = [item for item in decisions if not item["abstained"]]
    return {
        "minimum_score": round(float(threshold["minimum_score"]), 6),
        "minimum_margin": round(float(threshold["minimum_margin"]), 6),
        "overall_accuracy": _rate(decisions, "correct"),
        "answerable_accuracy": _rate(answerable, "correct"),
        "abstention_accuracy": _rate(no_fit, "correct"),
        "false_discovery_rate": _rate(no_fit, "false_discovery"),
        "positive_abstention_rate": _rate(answerable, "positive_abstention"),
        "coverage": round(len(accepted) / len(decisions), 6) if decisions else None,
        "selective_accuracy": _rate(accepted, "correct"),
        "decision_count": len(decisions),
    }


def choose_frozen_threshold(
    records: list[dict[str, Any]],
    score_grid: Iterable[float],
    margin_grid: Iterable[float],
    maximum_false_discovery_rate: float,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    candidates = [
        score_threshold(
            records,
            {"minimum_score": float(score), "minimum_margin": float(margin)},
        )
        for score in score_grid
        for margin in margin_grid
    ]
    feasible = [
        item
        for item in candidates
        if item["false_discovery_rate"] is not None
        and float(item["false_discovery_rate"]) <= maximum_false_discovery_rate
    ]
    chosen = min(
        feasible or candidates,
        key=lambda item: (
            -float(item["overall_accuracy"] or 0.0),
            float(item["false_discovery_rate"] or 0.0),
            float(item["positive_abstention_rate"] or 0.0),
            -float(item["coverage"] or 0.0),
            float(item["minimum_score"]),
            float(item["minimum_margin"]),
        ),
    )
    return {
        "minimum_score": float(chosen["minimum_score"]),
        "minimum_margin": float(chosen["minimum_margin"]),
    }, candidates


def discover_calibration_reports(root: str | Path) -> list[Path]:
    source = Path(root)
    candidates = [source] if source.is_file() else sorted(source.rglob("*.json"))
    reports: list[Path] = []
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("artifact_type") == CALIBRATION_ARTIFACT_TYPE:
            reports.append(path)
    return reports


def _resolve_artifact_root(report_path: Path, report: dict[str, Any]) -> Path | None:
    raw = report.get("artifact_root")
    if raw in (None, ""):
        return report_path.parent
    root = Path(str(raw))
    if root.is_absolute():
        return root
    candidates = [
        Path.cwd() / root,
        report_path.parent / root,
        report_path.parent,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _record_from_artifact(artifact: dict[str, Any], *, policy: str) -> dict[str, Any]:
    metrics = artifact.get("metrics") or {}
    evaluation = artifact.get("challenge_evaluation") or {}
    submission = evaluation.get("submission_payload") or {}
    answer = evaluation.get("answer_payload") or {}
    return {
        "split": "test",
        "policy": policy,
        "seed": artifact.get("experiment", {}).get("deterministic_seed"),
        "case_kind": metrics.get("challenge_case_kind"),
        "artifact_hash": artifact.get("provenance", {}).get("artifact_hash"),
        "expected_outcome": answer.get("expected_outcome"),
        "top_semantic_key": metrics.get("evaluator_selected_semantic_key"),
        "top_blind_id": submission.get("top_blind_id"),
        "top_score": float(submission.get("top_score", 0.0)),
        "selection_margin": float(submission.get("selection_margin", 0.0)),
        "base_discovery_complete": bool(metrics.get("discovery_complete")),
        "experiments_run": int(metrics.get("experiments_run", 0)),
        "evidence_refs": list(submission.get("evidence_refs") or []),
    }


def audit_calibration_report(source: str | Path) -> dict[str, Any]:
    reports = discover_calibration_reports(source)
    issues: list[dict[str, str]] = []
    if len(reports) != 1:
        return {
            "artifact_type": "eja_calibration_audit",
            "audit_version": "0.6",
            "calibration_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "issues": [
                {
                    "severity": "error",
                    "code": "calibration_report_count",
                    "path": str(source),
                    "message": f"Expected exactly one calibration suite report, found {len(reports)}.",
                }
            ],
            "entries": [],
            "claim_boundary": (
                "The audit checks split, threshold, commitment, and decision bookkeeping. "
                "It does not establish scientific truth or real-world calibration."
            ),
        }

    report_path = reports[0]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    calibration = report.get("calibration") or {}
    test = report.get("test") or {}
    chosen = calibration.get("chosen_threshold") or {}

    if report.get("suite_version") != "0.6":
        _issue(
            issues,
            "unsupported_calibration_version",
            "suite_version",
            "Calibration suite version must equal 0.6.",
        )
    if calibration.get("protocol") != "disjoint_frozen_threshold_calibration_v1":
        _issue(
            issues,
            "unsupported_calibration_protocol",
            "calibration.protocol",
            "Calibration protocol must equal disjoint_frozen_threshold_calibration_v1.",
        )

    calibration_seeds = [int(value) for value in calibration.get("calibration_seeds") or []]
    test_seeds = [int(value) for value in test.get("test_seeds") or []]
    split_disjoint = not bool(set(calibration_seeds) & set(test_seeds))
    if not calibration_seeds or not test_seeds:
        _issue(
            issues,
            "empty_calibration_split",
            "calibration/test",
            "Calibration and test seed sets must both be non-empty.",
        )
    if not split_disjoint:
        _issue(
            issues,
            "split_overlap",
            "calibration/test seeds",
            "Calibration and test seeds overlap.",
        )
    if test.get("answers_used_for_calibration") is not False:
        _issue(
            issues,
            "test_answer_leakage",
            "test.answers_used_for_calibration",
            "Test answers must not be used to select the frozen threshold.",
        )

    recorded_commitment = calibration.get("threshold_commitment_hash")
    computed_commitment = _commitment(calibration_commitment_payload(report))
    commitment_valid = recorded_commitment == computed_commitment
    if not commitment_valid:
        _issue(
            issues,
            "threshold_commitment_mismatch",
            "calibration.threshold_commitment_hash",
            "Frozen threshold commitment does not match the revealed calibration payload.",
        )

    records = calibration.get("records") or []
    record_hashes = calibration.get("record_hashes") or []
    computed_record_hashes = [_record_hash(record) for record in records]
    records_valid = computed_record_hashes == record_hashes
    if not records_valid:
        _issue(
            issues,
            "calibration_record_hash_mismatch",
            "calibration.record_hashes",
            "Calibration record hashes do not match the revealed records or order.",
        )
    for record in records:
        if int(record.get("seed", -1)) not in calibration_seeds:
            _issue(
                issues,
                "foreign_calibration_seed",
                "calibration.records",
                "A calibration record uses a seed outside the declared calibration split.",
            )
        if record.get("split") != "calibration":
            _issue(
                issues,
                "calibration_record_split_mismatch",
                "calibration.records",
                "Every calibration record must declare split=calibration.",
            )

    grid = calibration.get("candidate_grid") or {}
    score_grid = grid.get("minimum_scores") or []
    margin_grid = grid.get("minimum_margins") or []
    reproduced_threshold: dict[str, float] | None = None
    reproduced_scorecards: list[dict[str, Any]] = []
    if records and score_grid and margin_grid:
        reproduced_threshold, reproduced_scorecards = choose_frozen_threshold(
            records,
            score_grid,
            margin_grid,
            float(calibration.get("maximum_false_discovery_rate", 0.0)),
        )
        if reproduced_threshold != chosen:
            _issue(
                issues,
                "threshold_selection_mismatch",
                "calibration.chosen_threshold",
                "The chosen threshold is not reproduced by the declared grid and objective.",
            )
    else:
        _issue(
            issues,
            "incomplete_calibration_grid",
            "calibration.candidate_grid",
            "Calibration records and both threshold grids are required.",
        )

    root = _resolve_artifact_root(report_path, report)
    entries: list[dict[str, Any]] = []
    test_hashes: set[str] = set()
    for index in report.get("artifact_index") or []:
        if index.get("split") != "test":
            continue
        relative = index.get("relative_path")
        if not relative or root is None:
            _issue(
                issues,
                "missing_test_artifact_path",
                "artifact_index",
                "Test artifact entry is missing a resolvable relative path.",
            )
            continue
        path = root / str(relative)
        if not path.exists():
            _issue(
                issues,
                "missing_test_artifact",
                str(path),
                "Declared test artifact does not exist.",
            )
            continue
        artifact = load_artifact(path)
        validation = validate_artifact(artifact)
        challenge = audit_challenge_artifact(artifact)
        protocol = artifact.get("calibration_protocol") or {}
        selection_rule = artifact.get("challenge_protocol", {}).get("selection_rule") or {}
        record = _record_from_artifact(artifact, policy=str(index.get("policy")))
        frozen = apply_frozen_threshold(record, chosen)
        actual = artifact.get("challenge_evaluation") or {}
        decision_matches = bool(
            frozen["selected_outcome"] == actual.get("selected_outcome")
            and frozen["correct"] == bool(actual.get("correct"))
        )
        artifact_commitment_valid = bool(
            protocol.get("split") == "test"
            and protocol.get("threshold_frozen_before_test") is True
            and protocol.get("threshold_commitment_hash") == recorded_commitment
            and protocol.get("frozen_threshold") == chosen
            and protocol.get("calibration_record_hashes") == record_hashes
            and protocol.get("test_answers_used_for_calibration") is False
        )
        selection_rule_matches = bool(
            float(selection_rule.get("minimum_score", -1.0))
            == float(chosen.get("minimum_score", -2.0))
            and float(selection_rule.get("minimum_margin", -1.0))
            == float(chosen.get("minimum_margin", -2.0))
        )
        if not artifact_commitment_valid:
            _issue(
                issues,
                "test_threshold_protocol_mismatch",
                str(path),
                "Test artifact does not carry the committed frozen threshold and calibration hashes.",
            )
        if not selection_rule_matches:
            _issue(
                issues,
                "test_selection_rule_mismatch",
                str(path),
                "Challenge selection rule differs from the frozen threshold.",
            )
        if not decision_matches:
            _issue(
                issues,
                "frozen_decision_mismatch",
                str(path),
                "Stored test decision is not reproduced from the frozen threshold.",
            )
        recorded_hash = artifact.get("provenance", {}).get("artifact_hash")
        test_hashes.add(str(recorded_hash))
        entries.append(
            {
                "path": str(path),
                "seed": record["seed"],
                "case_kind": record["case_kind"],
                "policy": record["policy"],
                "artifact_hash": artifact_hash(artifact),
                "structural_valid": validation.valid,
                "challenge_valid": challenge["challenge_valid"],
                "artifact_threshold_valid": artifact_commitment_valid,
                "selection_rule_matches": selection_rule_matches,
                "decision_matches_frozen": decision_matches,
                "expected_outcome": record["expected_outcome"],
                "selected_outcome": actual.get("selected_outcome"),
                "correct": bool(actual.get("correct")),
                "abstained": bool(actual.get("abstained")),
                "false_discovery": bool(actual.get("false_discovery")),
                "top_score": record["top_score"],
                "selection_margin": record["selection_margin"],
            }
        )

    if test_hashes & set(str(value) for value in record_hashes):
        _issue(
            issues,
            "test_artifact_in_calibration_commitment",
            "calibration.record_hashes",
            "A test artifact hash appears in the calibration-only commitment payload.",
        )

    policies: dict[str, Any] = {}
    for policy in sorted({str(entry["policy"]) for entry in entries}):
        items = [entry for entry in entries if entry["policy"] == policy]
        answerable = [item for item in items if item["expected_outcome"] != "abstain"]
        no_fit = [item for item in items if item["expected_outcome"] == "abstain"]
        accepted = [item for item in items if not item["abstained"]]
        policies[policy] = {
            "artifact_count": len(items),
            "overall_accuracy": _rate(items, "correct"),
            "answerable_accuracy": _rate(answerable, "correct"),
            "abstention_accuracy": _rate(no_fit, "correct"),
            "false_discovery_rate": _rate(no_fit, "false_discovery"),
            "coverage": round(len(accepted) / len(items), 6) if items else None,
            "selective_accuracy": _rate(accepted, "correct"),
            "decision_match_rate": _rate(items, "decision_matches_frozen"),
        }

    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "artifact_type": "eja_calibration_audit",
        "audit_version": "0.6",
        "source_report": str(report_path),
        "calibration_valid": error_count == 0 and bool(entries),
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
        "split_disjoint": split_disjoint,
        "threshold_commitment_valid": commitment_valid,
        "calibration_record_hashes_valid": records_valid,
        "chosen_threshold": chosen,
        "reproduced_threshold": reproduced_threshold,
        "candidate_scorecards_reproduced": reproduced_scorecards,
        "test_artifact_count": len(entries),
        "policies": policies,
        "entries": entries,
        "claim_boundary": (
            "A passing calibration audit establishes disjoint-split bookkeeping, "
            "threshold commitment integrity, deterministic threshold reproduction, and "
            "frozen test-decision consistency. It does not establish scientific truth, "
            "probabilistic calibration, or open-ended discovery."
        ),
    }


def audit_calibration_directory(root: str | Path) -> dict[str, Any]:
    reports = discover_calibration_reports(root)
    entries = [audit_calibration_report(path) for path in reports]
    error_count = sum(entry["error_count"] for entry in entries)
    warning_count = sum(entry["warning_count"] for entry in entries)
    return {
        "artifact_type": "eja_calibration_directory_audit",
        "audit_version": "0.6",
        "root": str(root),
        "report_count": len(entries),
        "calibration_valid": bool(entries) and error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "entries": entries,
        "claim_boundary": (
            "The directory audit aggregates calibration protocol checks only. It does "
            "not validate physical claims outside recorded verifier scopes."
        ),
    }


def render_calibration_html(report: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(entry.get('seed')))}</td>"
        f"<td>{escape(str(entry.get('case_kind')))}</td>"
        f"<td>{escape(str(entry.get('policy')))}</td>"
        f"<td>{escape(str(entry.get('selected_outcome')))}</td>"
        f"<td>{escape(str(entry.get('correct')))}</td>"
        f"<td>{escape(str(entry.get('decision_matches_frozen')))}</td>"
        "</tr>"
        for entry in report.get("entries", [])
    )
    raw = escape(json.dumps(report, indent=2, sort_keys=True))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRUMB EJA Calibration Audit</title><style>body{{font:16px/1.5 system-ui;margin:0;background:#091020;color:#eff5ff}}main{{width:min(1260px,94vw);margin:36px auto}}section{{background:#111b31;border:1px solid #2b3c5d;border-radius:16px;padding:20px;margin:16px 0}}.stats{{display:flex;gap:10px;flex-wrap:wrap}}.stat{{padding:8px 12px;border:1px solid #2b3c5d;border-radius:999px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #2b3c5d;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#070c18;padding:14px;border-radius:10px}}</style></head><body><main><h1>CRUMB EJA v0.6 · Frozen calibration audit</h1><div class="stats"><span class="stat">Valid <strong>{escape(str(report.get('calibration_valid')))}</strong></span><span class="stat">Split disjoint <strong>{escape(str(report.get('split_disjoint')))}</strong></span><span class="stat">Commitment valid <strong>{escape(str(report.get('threshold_commitment_valid')))}</strong></span><span class="stat">Test artifacts <strong>{escape(str(report.get('test_artifact_count')))}</strong></span></div><section><table><thead><tr><th>Seed</th><th>Case</th><th>Policy</th><th>Selection</th><th>Correct</th><th>Frozen match</th></tr></thead><tbody>{rows}</tbody></table></section><section><pre>{raw}</pre></section><p>{escape(str(report.get('claim_boundary', 'missing')))}</p></main></body></html>"""
