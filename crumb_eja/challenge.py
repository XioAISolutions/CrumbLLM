"""Sealed challenge commitment, abstention, and false-discovery audits."""

from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from pathlib import Path
from statistics import fmean
from typing import Any

from .model import artifact_hash, canonical_json, load_artifact
from .pack import discover_artifacts


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


def audit_challenge_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Verify one sealed challenge after the evaluator reveals its commitments."""
    protocol = artifact.get("challenge_protocol")
    evaluation = artifact.get("challenge_evaluation")
    metrics = artifact.get("metrics") or {}
    issues: list[dict[str, str]] = []

    if not isinstance(protocol, dict):
        _issue(
            issues,
            "missing_challenge_protocol",
            "challenge_protocol",
            "Sealed challenge metadata is missing.",
        )
        protocol = {}
    if not isinstance(evaluation, dict):
        _issue(
            issues,
            "missing_challenge_evaluation",
            "challenge_evaluation",
            "Post-run evaluator reveal is missing.",
        )
        evaluation = {}

    if protocol.get("protocol") != "sealed_none_of_the_above_challenge_v1":
        _issue(
            issues,
            "unsupported_challenge_protocol",
            "challenge_protocol.protocol",
            "Challenge protocol must equal sealed_none_of_the_above_challenge_v1.",
        )
    if protocol.get("answer_visible_to_agent") is not False:
        _issue(
            issues,
            "answer_exposure",
            "challenge_protocol.answer_visible_to_agent",
            "The expected answer must remain hidden during selection.",
        )
    if protocol.get("case_spec_visible_to_agent") is not False:
        _issue(
            issues,
            "case_spec_exposure",
            "challenge_protocol.case_spec_visible_to_agent",
            "The hidden case specification must remain hidden during selection.",
        )

    selection_rule = protocol.get("selection_rule")
    if not isinstance(selection_rule, dict):
        _issue(
            issues,
            "missing_selection_rule",
            "challenge_protocol.selection_rule",
            "Challenge selection and abstention thresholds are missing.",
        )
        selection_rule = {}
    elif selection_rule.get("abstention_allowed") is not True:
        _issue(
            issues,
            "abstention_disabled",
            "challenge_protocol.selection_rule.abstention_allowed",
            "None-of-the-above cases require an explicit abstention option.",
        )

    hidden_spec = evaluation.get("hidden_case_spec")
    answer_payload = evaluation.get("answer_payload")
    submission_payload = evaluation.get("submission_payload")
    case_commitment_valid = bool(
        isinstance(hidden_spec, dict)
        and protocol.get("case_commitment_hash") == _commitment(hidden_spec)
    )
    answer_commitment_valid = bool(
        isinstance(answer_payload, dict)
        and protocol.get("answer_commitment_hash") == _commitment(answer_payload)
    )
    submission_commitment_valid = bool(
        isinstance(submission_payload, dict)
        and protocol.get("submission_hash") == _commitment(submission_payload)
    )
    if not case_commitment_valid:
        _issue(
            issues,
            "case_commitment_mismatch",
            "challenge_protocol.case_commitment_hash",
            "The revealed hidden case does not match its pre-run commitment.",
        )
    if not answer_commitment_valid:
        _issue(
            issues,
            "answer_commitment_mismatch",
            "challenge_protocol.answer_commitment_hash",
            "The revealed expected answer does not match its pre-run commitment.",
        )
    if not submission_commitment_valid:
        _issue(
            issues,
            "submission_commitment_mismatch",
            "challenge_protocol.submission_hash",
            "The recorded submission does not match its committed payload.",
        )

    expected = (
        answer_payload.get("expected_outcome")
        if isinstance(answer_payload, dict)
        else None
    )
    selected = evaluation.get("selected_outcome")
    abstained = evaluation.get("abstained") is True
    recomputed_correct = bool(expected is not None and selected == expected)
    if evaluation.get("correct") is not recomputed_correct:
        _issue(
            issues,
            "incorrect_evaluation_flag",
            "challenge_evaluation.correct",
            "The stored correctness flag does not match selected_outcome and expected_outcome.",
        )
    if metrics.get("selected_outcome") != selected:
        _issue(
            issues,
            "selection_metric_mismatch",
            "metrics.selected_outcome",
            "Metrics and evaluator record disagree about the selected outcome.",
        )
    if bool(metrics.get("abstained")) != abstained:
        _issue(
            issues,
            "abstention_metric_mismatch",
            "metrics.abstained",
            "Metrics and evaluator record disagree about abstention.",
        )
    if isinstance(submission_payload, dict):
        if submission_payload.get("selected_outcome") != selected:
            _issue(
                issues,
                "submission_selection_mismatch",
                "challenge_evaluation.submission_payload.selected_outcome",
                "Committed submission and evaluator selection disagree.",
            )
        if bool(submission_payload.get("abstained")) != abstained:
            _issue(
                issues,
                "submission_abstention_mismatch",
                "challenge_evaluation.submission_payload.abstained",
                "Committed submission and evaluator abstention disagree.",
            )

    evidence_refs = {
        str(item.get("evidence_ref"))
        for item in artifact.get("trajectories") or []
        if item.get("evidence_ref")
    }
    if isinstance(submission_payload, dict):
        for raw_ref in submission_payload.get("evidence_refs") or []:
            ref = str(raw_ref)
            if ref not in evidence_refs:
                _issue(
                    issues,
                    "submission_missing_evidence",
                    "challenge_evaluation.submission_payload.evidence_refs",
                    f"Submission references unknown evidence {ref}.",
                )

    candidate = artifact.get("candidate_axiom")
    verdict = artifact.get("verification", {}).get("verdict")
    expected_abstention = expected == "abstain"
    false_discovery = bool(expected_abstention and not abstained)
    positive_abstention = bool(not expected_abstention and abstained)

    if expected_abstention:
        if not abstained:
            _issue(
                issues,
                "false_discovery",
                "challenge_evaluation.abstained",
                "A no-fit challenge produced a positive selection.",
            )
        if candidate is not None:
            _issue(
                issues,
                "axiom_after_required_abstention",
                "candidate_axiom",
                "No-fit cases must not compile a candidate axiom.",
            )
        if verdict != "not_evaluated_due_to_abstention":
            _issue(
                issues,
                "verifier_ran_after_abstention",
                "verification.verdict",
                "The accepted challenge verdict must record abstention rather than support.",
            )
    else:
        if abstained:
            _issue(
                issues,
                "positive_case_abstention",
                "challenge_evaluation.abstained",
                "An answerable challenge was abstained on.",
                severity="warning",
            )
        if not abstained and selected == expected and candidate is None:
            _issue(
                issues,
                "missing_positive_candidate",
                "candidate_axiom",
                "A correct accepted positive selection should include its scoped candidate axiom.",
            )

    stored_false_discovery = bool(evaluation.get("false_discovery"))
    if stored_false_discovery != false_discovery:
        _issue(
            issues,
            "false_discovery_flag_mismatch",
            "challenge_evaluation.false_discovery",
            "Stored false-discovery flag is inconsistent with expected outcome and abstention.",
        )
    stored_positive_abstention = bool(evaluation.get("positive_abstention"))
    if stored_positive_abstention != positive_abstention:
        _issue(
            issues,
            "positive_abstention_flag_mismatch",
            "challenge_evaluation.positive_abstention",
            "Stored positive-abstention flag is inconsistent with the evaluator outcome.",
        )

    if artifact.get("provenance", {}).get("hidden_state_exposed_to_agent") is not False:
        _issue(
            issues,
            "hidden_state_exposure",
            "provenance.hidden_state_exposed_to_agent",
            "A valid challenge artifact must keep hidden state inaccessible to the agent.",
        )

    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    commitments_valid = (
        case_commitment_valid
        and answer_commitment_valid
        and submission_commitment_valid
    )
    return {
        "artifact_type": "eja_challenge_audit",
        "audit_version": "0.5",
        "experiment_id": artifact.get("experiment", {}).get("id"),
        "artifact_hash": artifact_hash(artifact),
        "challenge_valid": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
        "case_kind": metrics.get("challenge_case_kind"),
        "expected_outcome": expected,
        "selected_outcome": selected,
        "abstained": abstained,
        "correct": recomputed_correct,
        "false_discovery": false_discovery,
        "positive_abstention": positive_abstention,
        "commitments": {
            "case": case_commitment_valid,
            "answer": answer_commitment_valid,
            "submission": submission_commitment_valid,
            "all_valid": commitments_valid,
        },
        "selection": {
            "top_score": (
                submission_payload.get("top_score")
                if isinstance(submission_payload, dict)
                else None
            ),
            "margin": (
                submission_payload.get("selection_margin")
                if isinstance(submission_payload, dict)
                else None
            ),
            "minimum_score": selection_rule.get("minimum_score"),
            "minimum_margin": selection_rule.get("minimum_margin"),
        },
        "claim_boundary": (
            "A passing challenge audit establishes commitment integrity, selection "
            "bookkeeping, and abstention consistency. It does not establish scientific "
            "truth or open-ended hypothesis invention."
        ),
    }


def audit_challenge_pack(root: str | Path) -> dict[str, Any]:
    directory = Path(root)
    entries: list[dict[str, Any]] = []
    for path in discover_artifacts(directory):
        artifact = load_artifact(path)
        if not isinstance(artifact.get("challenge_protocol"), dict):
            continue
        report = audit_challenge_artifact(artifact)
        entries.append(
            {
                "path": str(path.relative_to(directory)),
                "experiment_id": report["experiment_id"],
                "artifact_hash": report["artifact_hash"],
                "case_kind": report["case_kind"],
                "expected_outcome": report["expected_outcome"],
                "selected_outcome": report["selected_outcome"],
                "abstained": report["abstained"],
                "correct": report["correct"],
                "false_discovery": report["false_discovery"],
                "positive_abstention": report["positive_abstention"],
                "commitments_valid": report["commitments"]["all_valid"],
                "challenge_valid": report["challenge_valid"],
                "error_count": report["error_count"],
                "warning_count": report["warning_count"],
                "issues": report["issues"],
            }
        )

    answerable = [entry for entry in entries if entry["expected_outcome"] != "abstain"]
    no_fit = [entry for entry in entries if entry["expected_outcome"] == "abstain"]
    accepted = [entry for entry in entries if not entry["abstained"]]
    error_count = sum(entry["error_count"] for entry in entries)
    warning_count = sum(entry["warning_count"] for entry in entries)

    def rate(items: list[dict[str, Any]], field: str) -> float | None:
        if not items:
            return None
        return round(fmean(1.0 if item[field] else 0.0 for item in items), 6)

    selective_accuracy = rate(accepted, "correct")
    return {
        "artifact_type": "eja_challenge_pack_audit",
        "audit_version": "0.5",
        "root": str(directory),
        "challenge_valid": bool(entries) and error_count == 0,
        "artifact_count": len(entries),
        "answerable_count": len(answerable),
        "no_fit_count": len(no_fit),
        "accepted_count": len(accepted),
        "error_count": error_count,
        "warning_count": warning_count,
        "overall_accuracy": rate(entries, "correct"),
        "answerable_accuracy": rate(answerable, "correct"),
        "abstention_accuracy": rate(no_fit, "correct"),
        "false_discovery_rate": rate(no_fit, "false_discovery"),
        "positive_abstention_rate": rate(answerable, "positive_abstention"),
        "coverage": (
            round(len(accepted) / len(entries), 6) if entries else None
        ),
        "selective_accuracy": selective_accuracy,
        "commitment_valid_rate": rate(entries, "commitments_valid"),
        "entries": entries,
        "claim_boundary": (
            "This scorecard measures sealed challenge bookkeeping, answerable accuracy, "
            "abstention, and false discoveries. It does not validate the underlying "
            "physical model outside each artifact's recorded verifier scope."
        ),
    }


def render_challenge_html(report: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(entry.get('path')))}</td>"
        f"<td>{escape(str(entry.get('case_kind')))}</td>"
        f"<td>{escape(str(entry.get('expected_outcome')))}</td>"
        f"<td>{escape(str(entry.get('selected_outcome')))}</td>"
        f"<td>{escape(str(entry.get('correct')))}</td>"
        f"<td>{escape(str(entry.get('false_discovery')))}</td>"
        f"<td>{escape(str(entry.get('commitments_valid')))}</td>"
        "</tr>"
        for entry in report.get("entries", [])
    )
    raw = escape(json.dumps(report, indent=2, sort_keys=True))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRUMB EJA Challenge Audit</title><style>body{{font:16px/1.5 system-ui;margin:0;background:#091020;color:#eff5ff}}main{{width:min(1240px,94vw);margin:36px auto}}section{{background:#111b31;border:1px solid #2b3c5d;border-radius:16px;padding:20px;margin:16px 0}}.stats{{display:flex;gap:10px;flex-wrap:wrap}}.stat{{padding:8px 12px;border:1px solid #2b3c5d;border-radius:999px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #2b3c5d;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#070c18;padding:14px;border-radius:10px}}</style></head><body><main><h1>CRUMB EJA v0.5 · Sealed challenge audit</h1><div class="stats"><span class="stat">Valid <strong>{escape(str(report.get('challenge_valid')))}</strong></span><span class="stat">Accuracy <strong>{escape(str(report.get('overall_accuracy')))}</strong></span><span class="stat">Abstention accuracy <strong>{escape(str(report.get('abstention_accuracy')))}</strong></span><span class="stat">False-discovery rate <strong>{escape(str(report.get('false_discovery_rate')))}</strong></span><span class="stat">Coverage <strong>{escape(str(report.get('coverage')))}</strong></span></div><section><table><thead><tr><th>Path</th><th>Case</th><th>Expected</th><th>Selected</th><th>Correct</th><th>False discovery</th><th>Commitments</th></tr></thead><tbody>{rows}</tbody></table></section><section><pre>{raw}</pre></section><p>{escape(str(report.get('claim_boundary', 'missing')))}</p></main></body></html>"""
