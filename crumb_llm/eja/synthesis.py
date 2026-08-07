"""Audits for CRUMB EJA v0.7 finite-grammar symbolic synthesis artifacts."""

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


def _float_pair(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        return [float(value[0]), float(value[1])]
    except (TypeError, ValueError):
        return None


def audit_synthesis_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Audit one finite-grammar synthesis artifact after target reveal."""
    protocol = artifact.get("synthesis_protocol")
    evaluation = artifact.get("synthesis_evaluation")
    candidates = artifact.get("synthesis_candidates")
    metrics = artifact.get("metrics") or {}
    issues: list[dict[str, str]] = []

    if not isinstance(protocol, dict):
        _issue(issues, "missing_synthesis_protocol", "synthesis_protocol", "Synthesis protocol metadata is missing.")
        protocol = {}
    if not isinstance(evaluation, dict):
        _issue(issues, "missing_synthesis_evaluation", "synthesis_evaluation", "Post-run synthesis evaluation is missing.")
        evaluation = {}
    if not isinstance(candidates, list) or not candidates:
        _issue(issues, "missing_generated_candidates", "synthesis_candidates", "Generated candidate table is missing or empty.")
        candidates = []

    if protocol.get("protocol") != "finite_symbolic_grammar_v1":
        _issue(issues, "unsupported_synthesis_protocol", "synthesis_protocol.protocol", "Protocol must equal finite_symbolic_grammar_v1.")
    if protocol.get("target_visible_to_agent") is not False:
        _issue(issues, "target_exposure", "synthesis_protocol.target_visible_to_agent", "The target expression must remain hidden during synthesis.")
    if protocol.get("target_expression_pre_registered") is not False:
        _issue(issues, "pre_registered_target", "synthesis_protocol.target_expression_pre_registered", "The full target expression must not be pre-registered in the synthesis lane.")

    grammar = protocol.get("grammar")
    grammar_valid = bool(
        isinstance(grammar, dict)
        and protocol.get("grammar_commitment_hash") == _commitment(grammar)
    )
    if not grammar_valid:
        _issue(issues, "grammar_commitment_mismatch", "synthesis_protocol.grammar_commitment_hash", "The grammar payload does not match its commitment.")
        grammar = grammar if isinstance(grammar, dict) else {}

    exponent_tokens = grammar.get("exponent_tokens") or []
    try:
        allowed_exponents = {float(value) for value in exponent_tokens}
    except (TypeError, ValueError):
        allowed_exponents = set()
        _issue(issues, "invalid_exponent_tokens", "synthesis_protocol.grammar.exponent_tokens", "Exponent tokens must be numeric.")
    maximum_candidates = grammar.get("maximum_candidates")
    if isinstance(maximum_candidates, int) and len(candidates) > maximum_candidates:
        _issue(issues, "candidate_budget_exceeded", "synthesis_candidates", "Generated candidates exceed the committed grammar budget.")
    if protocol.get("generated_candidate_count") != len(candidates):
        _issue(issues, "candidate_count_mismatch", "synthesis_protocol.generated_candidate_count", "Recorded candidate count does not match the candidate table.")

    candidate_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        path = f"synthesis_candidates[{index}]"
        if not isinstance(candidate, dict):
            _issue(issues, "invalid_candidate", path, "Generated candidate must be an object.")
            continue
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            _issue(issues, "missing_candidate_id", f"{path}.candidate_id", "Generated candidate is missing an ID.")
        elif candidate_id in candidate_ids:
            _issue(issues, "duplicate_candidate_id", f"{path}.candidate_id", f"Duplicate generated candidate ID {candidate_id}.")
        else:
            candidate_ids.add(candidate_id)
        pair = _float_pair(candidate.get("exponents"))
        if pair is None:
            _issue(issues, "invalid_candidate_exponents", f"{path}.exponents", "Candidate exponents must be a numeric pair.")
        elif any(value not in allowed_exponents for value in pair):
            _issue(issues, "candidate_outside_grammar", f"{path}.exponents", "Generated candidate uses an exponent outside the committed grammar.")
        try:
            float(candidate.get("fit_score"))
            float(candidate.get("complexity"))
        except (TypeError, ValueError):
            _issue(issues, "invalid_candidate_score", path, "Candidate fit score and complexity must be numeric.")

    ranked = sorted(
        [candidate for candidate in candidates if isinstance(candidate, dict)],
        key=lambda item: (
            -float(item.get("fit_score", 0.0)),
            float(item.get("complexity", 0.0)),
            str(item.get("candidate_id", "")),
        ),
    )
    top = ranked[0] if ranked else {}
    selected_candidate_id = evaluation.get("selected_candidate_id")
    if top and selected_candidate_id != top.get("candidate_id"):
        _issue(issues, "selection_not_top_ranked", "synthesis_evaluation.selected_candidate_id", "Selected candidate is not the deterministic top-ranked generated expression.")

    hidden_spec = evaluation.get("hidden_case_spec")
    target_payload = evaluation.get("target_payload")
    case_commitment_valid = bool(
        isinstance(hidden_spec, dict)
        and protocol.get("case_commitment_hash") == _commitment(hidden_spec)
    )
    target_commitment_valid = bool(
        isinstance(target_payload, dict)
        and protocol.get("target_commitment_hash") == _commitment(target_payload)
    )
    if not case_commitment_valid:
        _issue(issues, "case_commitment_mismatch", "synthesis_protocol.case_commitment_hash", "Revealed hidden case does not match its commitment.")
    if not target_commitment_valid:
        _issue(issues, "target_commitment_mismatch", "synthesis_protocol.target_commitment_hash", "Revealed target does not match its commitment.")

    threshold = protocol.get("frozen_threshold")
    accepted = evaluation.get("accepted") is True
    top_score = float(top.get("fit_score", 0.0)) if top else 0.0
    runner_score = float(ranked[1].get("fit_score", 0.0)) if len(ranked) > 1 else 0.0
    margin = top_score - runner_score
    if isinstance(threshold, dict):
        try:
            recomputed_accepted = bool(
                top_score >= float(threshold["minimum_score"])
                and margin >= float(threshold["minimum_margin"])
            )
        except (KeyError, TypeError, ValueError):
            recomputed_accepted = False
            _issue(issues, "invalid_frozen_threshold", "synthesis_protocol.frozen_threshold", "Frozen threshold must contain numeric minimum_score and minimum_margin.")
        else:
            if recomputed_accepted != accepted:
                _issue(issues, "acceptance_decision_mismatch", "synthesis_evaluation.accepted", "Stored acceptance does not match the frozen threshold and candidate scores.")
    else:
        _issue(issues, "missing_frozen_threshold", "synthesis_protocol.frozen_threshold", "Synthesis artifact is missing its selection threshold.")

    expected = target_payload.get("expected_outcome") if isinstance(target_payload, dict) else None
    target_pair = _float_pair(target_payload.get("target_exponents")) if isinstance(target_payload, dict) else None
    selected_pair = _float_pair(evaluation.get("selected_exponents"))
    exact_recovery = bool(accepted and target_pair is not None and selected_pair == target_pair)
    recomputed_correct = bool(
        (expected == "abstain" and not accepted)
        or (expected == "synthesized_power_law" and exact_recovery)
    )
    if bool(evaluation.get("exact_exponent_recovery")) != exact_recovery:
        _issue(issues, "exact_recovery_flag_mismatch", "synthesis_evaluation.exact_exponent_recovery", "Exact exponent recovery flag is inconsistent with revealed target and selected exponents.")
    if bool(evaluation.get("correct")) != recomputed_correct:
        _issue(issues, "incorrect_synthesis_flag", "synthesis_evaluation.correct", "Stored synthesis correctness does not match the revealed target and decision.")

    candidate_axiom = artifact.get("candidate_axiom")
    verdict = (artifact.get("verification") or {}).get("verdict")
    false_discovery = bool(expected == "abstain" and accepted)
    positive_abstention = bool(expected == "synthesized_power_law" and not accepted)
    if expected == "abstain":
        if accepted:
            _issue(issues, "false_discovery", "synthesis_evaluation.accepted", "A no-fit synthesis case was accepted.")
        if candidate_axiom is not None:
            _issue(issues, "axiom_after_required_abstention", "candidate_axiom", "No-fit synthesis cases must not compile a candidate axiom.")
        if verdict != "not_evaluated_due_to_abstention":
            _issue(issues, "verifier_ran_after_synthesis_abstention", "verification.verdict", "No-fit synthesis case must record abstention rather than support.")
    elif accepted:
        if not isinstance(candidate_axiom, dict):
            _issue(issues, "missing_synthesized_axiom", "candidate_axiom", "Accepted synthesis requires a scoped candidate axiom.")
        else:
            if candidate_axiom.get("generated_candidate_id") != selected_candidate_id:
                _issue(issues, "axiom_candidate_mismatch", "candidate_axiom.generated_candidate_id", "Candidate axiom is not linked to the selected generated expression.")
        if verdict not in {"supported_within_scope", "refuted_within_scope"}:
            _issue(issues, "missing_synthesis_verdict", "verification.verdict", "Accepted synthesis must be independently verified or refuted.")

    if artifact.get("provenance", {}).get("hypothesis_origin") != "finite_symbolic_grammar_enumeration":
        _issue(issues, "invalid_hypothesis_origin", "provenance.hypothesis_origin", "Synthesis hypotheses must declare finite_symbolic_grammar_enumeration origin.")
    if artifact.get("provenance", {}).get("hidden_state_exposed_to_agent") is not False:
        _issue(issues, "hidden_state_exposure", "provenance.hidden_state_exposed_to_agent", "Hidden state must remain inaccessible to the synthesis agent.")
    if protocol.get("split") == "test":
        if protocol.get("test_answers_used_for_calibration") is not False:
            _issue(issues, "test_answer_leakage", "synthesis_protocol.test_answers_used_for_calibration", "Test answers must not be used for synthesis-threshold calibration.")
        if not isinstance(protocol.get("threshold_commitment_hash"), str):
            _issue(issues, "missing_threshold_commitment", "synthesis_protocol.threshold_commitment_hash", "Test synthesis artifact must reference the frozen calibration commitment.")

    if metrics.get("winner") != selected_candidate_id:
        _issue(issues, "winner_metric_mismatch", "metrics.winner", "Winner metric does not match the selected generated candidate.")
    if bool(metrics.get("abstained")) != (not accepted):
        _issue(issues, "abstention_metric_mismatch", "metrics.abstained", "Metrics and synthesis evaluation disagree about abstention.")

    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "artifact_type": "eja_synthesis_audit",
        "audit_version": "0.7",
        "experiment_id": artifact.get("experiment", {}).get("id"),
        "artifact_hash": artifact_hash(artifact),
        "synthesis_valid": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
        "split": protocol.get("split"),
        "case_kind": (hidden_spec or {}).get("case_kind") if isinstance(hidden_spec, dict) else None,
        "expected_outcome": expected,
        "accepted": accepted,
        "correct": recomputed_correct,
        "exact_exponent_recovery": exact_recovery,
        "false_discovery": false_discovery,
        "positive_abstention": positive_abstention,
        "grammar_commitment_valid": grammar_valid,
        "case_commitment_valid": case_commitment_valid,
        "target_commitment_valid": target_commitment_valid,
        "threshold_commitment_hash": protocol.get("threshold_commitment_hash"),
        "candidate_count": len(candidates),
        "claim_boundary": (
            "A passing synthesis artifact audit establishes grammar, commitment, candidate-generation, "
            "ranking, and abstention bookkeeping. It does not establish open-ended scientific invention."
        ),
    }


def _apply_threshold(record: dict[str, Any], threshold: dict[str, float]) -> dict[str, Any]:
    accepted = bool(
        float(record.get("top_score", 0.0)) >= float(threshold["minimum_score"])
        and float(record.get("selection_margin", 0.0)) >= float(threshold["minimum_margin"])
    )
    expected = record.get("expected_outcome")
    target_pair = _float_pair(record.get("target_exponents"))
    top_pair = _float_pair(record.get("top_exponents"))
    exact = bool(accepted and target_pair is not None and top_pair == target_pair)
    correct = bool(
        (expected == "abstain" and not accepted)
        or (expected == "synthesized_power_law" and exact)
    )
    return {
        **record,
        "accepted": accepted,
        "correct": correct,
        "false_discovery": bool(expected == "abstain" and accepted),
        "positive_abstention": bool(expected != "abstain" and not accepted),
        "exact_exponent_recovery": exact,
    }


def _rate(items: list[dict[str, Any]], field: str) -> float | None:
    if not items:
        return None
    return round(fmean(1.0 if item[field] else 0.0 for item in items), 6)


def _score_threshold(records: list[dict[str, Any]], threshold: dict[str, float]) -> dict[str, Any]:
    decisions = [_apply_threshold(record, threshold) for record in records]
    positives = [item for item in decisions if item.get("expected_outcome") != "abstain"]
    no_fit = [item for item in decisions if item.get("expected_outcome") == "abstain"]
    accepted = [item for item in decisions if item["accepted"]]
    return {
        "minimum_score": float(threshold["minimum_score"]),
        "minimum_margin": float(threshold["minimum_margin"]),
        "overall_accuracy": _rate(decisions, "correct"),
        "positive_accuracy": _rate(positives, "correct"),
        "abstention_accuracy": _rate(no_fit, "correct"),
        "false_discovery_rate": _rate(no_fit, "false_discovery"),
        "positive_abstention_rate": _rate(positives, "positive_abstention"),
        "coverage": round(len(accepted) / len(decisions), 6) if decisions else None,
        "exact_recovery_rate": _rate(positives, "exact_exponent_recovery"),
    }


def _choose_threshold(report: dict[str, Any]) -> dict[str, float] | None:
    calibration = report.get("calibration") or {}
    grid = calibration.get("candidate_grid") or {}
    records = calibration.get("records") or []
    score_values = grid.get("minimum_scores") or []
    margin_values = grid.get("minimum_margins") or []
    try:
        scorecards = [
            _score_threshold(
                records,
                {"minimum_score": float(score), "minimum_margin": float(margin)},
            )
            for score in score_values
            for margin in margin_values
        ]
    except (TypeError, ValueError):
        return None
    maximum_false_discovery_rate = float(calibration.get("maximum_false_discovery_rate", 0.0))
    feasible = [
        item
        for item in scorecards
        if item["false_discovery_rate"] is not None
        and float(item["false_discovery_rate"]) <= maximum_false_discovery_rate
    ]
    if not scorecards:
        return None
    chosen = min(
        feasible or scorecards,
        key=lambda item: (
            -float(item["overall_accuracy"] or 0.0),
            float(item["false_discovery_rate"] or 0.0),
            float(item["positive_abstention_rate"] or 0.0),
            -float(item["exact_recovery_rate"] or 0.0),
            -float(item["coverage"] or 0.0),
            float(item["minimum_score"]),
            float(item["minimum_margin"]),
        ),
    )
    return {
        "minimum_score": float(chosen["minimum_score"]),
        "minimum_margin": float(chosen["minimum_margin"]),
    }


def synthesis_commitment_payload(report: dict[str, Any]) -> dict[str, Any]:
    calibration = report.get("calibration") or {}
    return {
        "protocol": calibration.get("protocol"),
        "grammar_commitment_hash": report.get("grammar_commitment_hash"),
        "calibration_seeds": calibration.get("calibration_seeds"),
        "calibration_cases": calibration.get("calibration_cases"),
        "record_hashes": calibration.get("record_hashes"),
        "candidate_grid": calibration.get("candidate_grid"),
        "maximum_false_discovery_rate": calibration.get("maximum_false_discovery_rate"),
        "chosen_threshold": calibration.get("chosen_threshold"),
        "selection_objective": calibration.get("selection_objective"),
    }


def audit_synthesis_suite(report: dict[str, Any]) -> dict[str, Any]:
    """Reproduce the calibration commitment and holdout split from a v0.7 suite report."""
    issues: list[dict[str, str]] = []
    calibration = report.get("calibration") or {}
    test = report.get("test") or {}
    records = calibration.get("records") or []

    grammar = report.get("grammar")
    grammar_valid = bool(
        isinstance(grammar, dict)
        and report.get("grammar_commitment_hash") == _commitment(grammar)
    )
    if not grammar_valid:
        _issue(issues, "suite_grammar_commitment_mismatch", "grammar_commitment_hash", "Suite grammar commitment does not match the recorded grammar.")

    calibration_seeds = {int(value) for value in calibration.get("calibration_seeds") or []}
    test_seeds = {int(value) for value in test.get("test_seeds") or []}
    split_disjoint = bool(calibration_seeds and test_seeds and calibration_seeds.isdisjoint(test_seeds))
    if not split_disjoint:
        _issue(issues, "synthesis_split_overlap", "calibration.calibration_seeds", "Calibration and test seed sets must be non-empty and disjoint.")
    if test.get("answers_used_for_calibration") is not False:
        _issue(issues, "suite_test_answer_leakage", "test.answers_used_for_calibration", "Test answers must not be used for calibration.")

    record_hashes = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            _issue(issues, "invalid_calibration_record", f"calibration.records[{index}]", "Calibration record must be an object.")
            continue
        payload = dict(record)
        stored_hash = payload.pop("record_hash", None)
        recomputed = _commitment(payload)
        record_hashes.append(recomputed)
        if stored_hash != recomputed:
            _issue(issues, "calibration_record_hash_mismatch", f"calibration.records[{index}].record_hash", "Calibration record hash does not match its canonical payload.")
    if calibration.get("record_hashes") != record_hashes:
        _issue(issues, "calibration_record_index_mismatch", "calibration.record_hashes", "Calibration record hash index does not match recomputed record hashes.")

    commitment_valid = calibration.get("threshold_commitment_hash") == _commitment(
        synthesis_commitment_payload(report)
    )
    if not commitment_valid:
        _issue(issues, "synthesis_threshold_commitment_mismatch", "calibration.threshold_commitment_hash", "Frozen synthesis threshold commitment does not match the calibration payload.")

    reproduced_threshold = _choose_threshold(report)
    if reproduced_threshold != calibration.get("chosen_threshold"):
        _issue(issues, "synthesis_threshold_not_reproducible", "calibration.chosen_threshold", "Chosen synthesis threshold cannot be reproduced from the declared grid and objective.")

    calibration_pairs = {
        tuple(pair)
        for pair in (_float_pair(record.get("target_exponents")) for record in records)
        if pair is not None
    }
    run_rows = report.get("runs") or []
    test_pairs = {
        tuple(pair)
        for pair in (_float_pair(row.get("target_exponents")) for row in run_rows if isinstance(row, dict))
        if pair is not None
    }
    holdout_disjoint = calibration_pairs.isdisjoint(test_pairs)
    if not holdout_disjoint:
        _issue(issues, "holdout_target_pair_overlap", "runs", "Positive test exponent pairs must be absent from calibration target pairs.")

    error_count = sum(issue["severity"] == "error" for issue in issues)
    return {
        "artifact_type": "eja_synthesis_suite_audit",
        "audit_version": "0.7",
        "suite_valid": error_count == 0,
        "error_count": error_count,
        "issues": issues,
        "grammar_commitment_valid": grammar_valid,
        "split_disjoint": split_disjoint,
        "threshold_commitment_valid": commitment_valid,
        "threshold_reproduced": reproduced_threshold,
        "holdout_target_pairs_disjoint": holdout_disjoint,
        "calibration_target_pairs": [list(pair) for pair in sorted(calibration_pairs)],
        "test_target_pairs": [list(pair) for pair in sorted(test_pairs)],
        "claim_boundary": (
            "A passing suite audit establishes grammar, split, threshold, and holdout bookkeeping. "
            "It does not establish scientific truth or open-ended hypothesis invention."
        ),
    }


def audit_synthesis_pack(root: str | Path, *, suite: str | Path | None = None) -> dict[str, Any]:
    directory = Path(root)
    entries: list[dict[str, Any]] = []
    for path in discover_artifacts(directory):
        artifact = load_artifact(path)
        if not isinstance(artifact.get("synthesis_protocol"), dict):
            continue
        report = audit_synthesis_artifact(artifact)
        entries.append(
            {
                "path": str(path.relative_to(directory)),
                "experiment_id": report["experiment_id"],
                "artifact_hash": report["artifact_hash"],
                "split": report["split"],
                "case_kind": report["case_kind"],
                "expected_outcome": report["expected_outcome"],
                "accepted": report["accepted"],
                "correct": report["correct"],
                "exact_exponent_recovery": report["exact_exponent_recovery"],
                "false_discovery": report["false_discovery"],
                "positive_abstention": report["positive_abstention"],
                "grammar_commitment_valid": report["grammar_commitment_valid"],
                "synthesis_valid": report["synthesis_valid"],
                "error_count": report["error_count"],
                "warning_count": report["warning_count"],
                "issues": report["issues"],
                "threshold_commitment_hash": report["threshold_commitment_hash"],
            }
        )

    test_entries = [entry for entry in entries if entry["split"] == "test"]
    positive_test = [entry for entry in test_entries if entry["expected_outcome"] != "abstain"]
    no_fit_test = [entry for entry in test_entries if entry["expected_outcome"] == "abstain"]
    error_count = sum(entry["error_count"] for entry in entries)
    warning_count = sum(entry["warning_count"] for entry in entries)

    suite_audit = None
    if suite is not None:
        suite_path = Path(suite)
        suite_audit = audit_synthesis_suite(json.loads(suite_path.read_text(encoding="utf-8")))
        expected_commitment = (
            json.loads(suite_path.read_text(encoding="utf-8"))
            .get("calibration", {})
            .get("threshold_commitment_hash")
        )
        for entry in test_entries:
            if entry["threshold_commitment_hash"] != expected_commitment:
                _issue(
                    entry["issues"],
                    "test_threshold_commitment_drift",
                    entry["path"],
                    "Test artifact does not reference the suite's frozen synthesis threshold commitment.",
                )
                entry["synthesis_valid"] = False
                entry["error_count"] += 1
                error_count += 1

    return {
        "artifact_type": "eja_synthesis_pack_audit",
        "audit_version": "0.7",
        "root": str(directory),
        "synthesis_valid": bool(entries)
        and error_count == 0
        and (suite_audit is None or suite_audit["suite_valid"]),
        "artifact_count": len(entries),
        "test_artifact_count": len(test_entries),
        "error_count": error_count + (suite_audit["error_count"] if suite_audit else 0),
        "warning_count": warning_count,
        "test_accuracy": _rate(test_entries, "correct"),
        "heldout_exact_recovery_rate": _rate(positive_test, "exact_exponent_recovery"),
        "no_fit_abstention_accuracy": _rate(no_fit_test, "correct"),
        "false_discovery_rate": _rate(no_fit_test, "false_discovery"),
        "positive_abstention_rate": _rate(positive_test, "positive_abstention"),
        "grammar_commitment_valid_rate": _rate(entries, "grammar_commitment_valid"),
        "entries": entries,
        "suite_audit": suite_audit,
        "claim_boundary": (
            "This scorecard audits bounded finite-grammar synthesis, exact held-out exponent recovery, "
            "and no-fit abstention. It does not validate open-ended scientific discovery."
        ),
    }


def render_synthesis_html(report: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(entry.get('path')))}</td>"
        f"<td>{escape(str(entry.get('split')))}</td>"
        f"<td>{escape(str(entry.get('case_kind')))}</td>"
        f"<td>{escape(str(entry.get('correct')))}</td>"
        f"<td>{escape(str(entry.get('exact_exponent_recovery')))}</td>"
        f"<td>{escape(str(entry.get('false_discovery')))}</td>"
        f"<td>{escape(str(entry.get('synthesis_valid')))}</td>"
        "</tr>"
        for entry in report.get("entries", [])
    )
    raw = escape(json.dumps(report, indent=2, sort_keys=True))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRUMB EJA Symbolic Synthesis Audit</title><style>body{{font:16px/1.5 system-ui;margin:0;background:#091020;color:#eff5ff}}main{{width:min(1240px,94vw);margin:36px auto}}section{{background:#111b31;border:1px solid #2b3c5d;border-radius:16px;padding:20px;margin:16px 0}}.stats{{display:flex;gap:10px;flex-wrap:wrap}}.stat{{padding:8px 12px;border:1px solid #2b3c5d;border-radius:999px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #2b3c5d;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#070c18;padding:14px;border-radius:10px}}</style></head><body><main><h1>CRUMB EJA v0.7 · Finite-grammar symbolic synthesis audit</h1><div class="stats"><span class="stat">Valid <strong>{escape(str(report.get('synthesis_valid')))}</strong></span><span class="stat">Test accuracy <strong>{escape(str(report.get('test_accuracy')))}</strong></span><span class="stat">Exact recovery <strong>{escape(str(report.get('heldout_exact_recovery_rate')))}</strong></span><span class="stat">False discovery <strong>{escape(str(report.get('false_discovery_rate')))}</strong></span></div><section><table><thead><tr><th>Path</th><th>Split</th><th>Case</th><th>Correct</th><th>Exact recovery</th><th>False discovery</th><th>Valid</th></tr></thead><tbody>{rows}</tbody></table></section><section><pre>{raw}</pre></section><p>{escape(str(report.get('claim_boundary', 'missing')))}</p></main></body></html>"""
