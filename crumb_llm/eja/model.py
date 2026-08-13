"""Zero-dependency model and validation helpers for CRUMB EJA artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

# Named eja_schema_version, not crumb_version: an EJA artifact is JSON, not a
# CRUMB document, and its schema generation is versioned independently of the
# CRUMB wire format. The old name asserted a CRUMB v1.5 that no spec defines.
REQUIRED_TOP_LEVEL = (
    "eja_schema_version",
    "artifact_type",
    "experiment",
    "experience",
    "surprise",
    "hypotheses",
    "trajectories",
    "candidate_axiom",
    "verification",
    "provenance",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def artifact_hash(artifact: dict[str, Any]) -> str:
    """Compute a stable self-referential-safe artifact hash."""
    clone = json.loads(json.dumps(artifact))
    clone.setdefault("provenance", {})["artifact_hash"] = "pending"
    return "sha256:" + sha256(canonical_json(clone).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message, "severity": self.severity}


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    issues: tuple[ValidationIssue, ...]
    computed_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "computed_hash": self.computed_hash,
        }


def load_artifact(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("EJA artifact root must be a JSON object")
    return data


def dump_artifact(artifact: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def _mapping(value: Any, path: str, issues: list[ValidationIssue]) -> dict[str, Any]:
    if not isinstance(value, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return {}
    return value


def _list(value: Any, path: str, issues: list[ValidationIssue]) -> list[Any]:
    if not isinstance(value, list):
        issues.append(ValidationIssue(path, "must be an array"))
        return []
    return value


def validate_artifact(artifact: dict[str, Any], *, verify_hash: bool = True) -> ValidationReport:
    issues: list[ValidationIssue] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in artifact:
            issues.append(ValidationIssue(key, "required field is missing"))

    if artifact.get("artifact_type") != "eja_experiment":
        issues.append(ValidationIssue("artifact_type", "must equal 'eja_experiment'"))

    experiment = _mapping(artifact.get("experiment"), "experiment", issues)
    for key in ("id", "world", "deterministic_seed"):
        if key not in experiment:
            issues.append(ValidationIssue(f"experiment.{key}", "required field is missing"))

    experience = _mapping(artifact.get("experience"), "experience", issues)
    observations = experience.get("initial_observations", experience.get("observations"))
    for index, observation in enumerate(_list(observations, "experience.initial_observations", issues)):
        item = _mapping(observation, f"experience.initial_observations[{index}]", issues)
        if "sensor_readings" not in item:
            issues.append(
                ValidationIssue(
                    f"experience.initial_observations[{index}].sensor_readings",
                    "raw observations must be preserved separately from interpretation",
                )
            )

    surprise = _mapping(artifact.get("surprise"), "surprise", issues)
    for key in ("type", "description"):
        if not surprise.get(key):
            issues.append(ValidationIssue(f"surprise.{key}", "must be non-empty"))

    hypotheses = _list(artifact.get("hypotheses"), "hypotheses", issues)
    if len(hypotheses) < 2:
        issues.append(ValidationIssue("hypotheses", "must preserve competing explanations"))
    classes: set[str] = set()
    for index, hypothesis in enumerate(hypotheses):
        item = _mapping(hypothesis, f"hypotheses[{index}]", issues)
        for key in ("id", "class", "statement", "assumptions", "falsifiers"):
            if key not in item:
                issues.append(ValidationIssue(f"hypotheses[{index}].{key}", "required"))
        if item.get("class"):
            classes.add(str(item["class"]))
        if not item.get("falsifiers"):
            issues.append(ValidationIssue(f"hypotheses[{index}].falsifiers", "must contain at least one falsifier"))
    if len(classes) < 2:
        issues.append(ValidationIssue("hypotheses", "hypothesis classes are not meaningfully diverse"))

    trajectories = _list(artifact.get("trajectories"), "trajectories", issues)
    for index, trajectory in enumerate(trajectories):
        item = _mapping(trajectory, f"trajectories[{index}]", issues)
        if "intervention" not in item:
            issues.append(ValidationIssue(f"trajectories[{index}].intervention", "required"))
        if not item.get("observations"):
            issues.append(ValidationIssue(f"trajectories[{index}].observations", "required"))

    axiom = artifact.get("candidate_axiom")
    if axiom is not None:
        axiom_map = _mapping(axiom, "candidate_axiom", issues)
        for key in ("id", "statement", "assumptions", "falsifiers", "excluded_claims"):
            if not axiom_map.get(key):
                issues.append(ValidationIssue(f"candidate_axiom.{key}", "must be non-empty"))
        statement = str(axiom_map.get("statement", "")).lower()
        excluded = " ".join(str(x).lower() for x in axiom_map.get("excluded_claims", []))
        if "local" not in statement and "global" not in excluded:
            issues.append(ValidationIssue("candidate_axiom", "scope boundary is unclear"))

    verification = _mapping(artifact.get("verification"), "verification", issues)
    if not verification.get("verdict"):
        issues.append(ValidationIssue("verification.verdict", "required"))

    provenance = _mapping(artifact.get("provenance"), "provenance", issues)
    if provenance.get("hidden_state_exposed_to_agent") is not False:
        issues.append(
            ValidationIssue(
                "provenance.hidden_state_exposed_to_agent",
                "must be false for a valid hidden-cause benchmark",
            )
        )

    computed = artifact_hash(artifact)
    recorded = provenance.get("artifact_hash")
    if verify_hash and recorded and recorded != computed:
        issues.append(ValidationIssue("provenance.artifact_hash", "does not match canonical artifact hash"))

    return ValidationReport(not issues, tuple(issues), computed)


def summarize_artifact(artifact: dict[str, Any]) -> str:
    hypotheses = artifact.get("hypotheses") or []
    winner = max(hypotheses, key=lambda h: float(h.get("score", 0.0))) if hypotheses else {}
    axiom = artifact.get("candidate_axiom") or {}
    verification = artifact.get("verification") or {}
    return "\n".join(
        [
            f"Experiment: {artifact.get('experiment', {}).get('id', 'unknown')}",
            f"World: {artifact.get('experiment', {}).get('world', 'unknown')}",
            f"Surprise: {artifact.get('surprise', {}).get('description', 'not recorded')}",
            f"Leading hypothesis: {winner.get('id', 'none')} — {winner.get('statement', 'none')}",
            f"Candidate axiom: {axiom.get('statement', 'none')}",
            f"Verdict: {verification.get('verdict', 'unverified')}",
            f"Trajectories: {len(artifact.get('trajectories') or [])}",
            f"Hash: {artifact_hash(artifact)}",
        ]
    )


def compare_artifacts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    def winner(artifact: dict[str, Any]) -> str | None:
        hypotheses = artifact.get("hypotheses") or []
        if not hypotheses:
            return None
        return str(max(hypotheses, key=lambda h: float(h.get("score", 0.0))).get("id"))

    return {
        "same_world": left.get("experiment", {}).get("world") == right.get("experiment", {}).get("world"),
        "same_winner": winner(left) == winner(right),
        "left_winner": winner(left),
        "right_winner": winner(right),
        "left_verdict": left.get("verification", {}).get("verdict"),
        "right_verdict": right.get("verification", {}).get("verdict"),
        "left_trajectory_count": len(left.get("trajectories") or []),
        "right_trajectory_count": len(right.get("trajectories") or []),
        "same_hash": artifact_hash(left) == artifact_hash(right),
    }


def replay_plan(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for index, trajectory in enumerate(artifact.get("trajectories") or []):
        intervention = trajectory.get("intervention") or {}
        plan.append(
            {
                "step": index + 1,
                "action_type": intervention.get("action_type"),
                "parameters": intervention.get("parameters") or {},
            }
        )
    return plan
