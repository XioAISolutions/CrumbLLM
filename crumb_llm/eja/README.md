# CRUMB EJA v0.6

CRUMB EJA stores a complete discovery handoff rather than a prose-only context
summary. An artifact keeps raw observations, the recorded surprise, competing
hypotheses, ordered interventions, trajectories, a scoped candidate axiom,
deductions, verifier output, metrics, and provenance.

## Single artifacts

```bash
crumblm eja validate examples/einstein-elevator.eja.json
crumblm eja summarize examples/einstein-elevator.eja.json
crumblm eja replay-plan examples/einstein-elevator.eja.json

python -m crumb_llm.eja validate examples/einstein-elevator.eja.json
```

Validation rejects missing falsifiers, collapsed hypothesis diversity, unclear
scope, hidden-state exposure, and mismatched canonical hashes.

## Pack validation and scientific audit

```bash
crumblm eja validate-pack artifacts \
  --out artifacts/eja-pack.json \
  --html artifacts/eja-pack.html

crumblm eja audit-pack artifacts \
  --out artifacts/eja-audit.json \
  --html artifacts/eja-audit.html
```

The scientific audit checks structural validity, evidence completion, candidate
status versus verifier verdict, replication consistency, and lineage integrity.

## Evidence-reference and blind-protocol audit

```bash
crumblm eja evidence-pack artifacts \
  --out artifacts/eja-evidence.json \
  --html artifacts/eja-evidence.html
```

The evidence graph connects recorded intervention evidence to hypotheses,
deductions, candidate axioms, and verifier results. For blinded model-selection
artifacts, it also checks target-language leakage, statement exposure, mapping
and prompt hashes, and declared hypothesis origin.

## Sealed challenge and abstention audit

```bash
crumblm eja challenge-pack artifacts/jump-lab-challenge \
  --out artifacts/eja-challenge-audit.json \
  --html artifacts/eja-challenge-audit.html
```

The v0.5 challenge gate independently recomputes hidden case, hidden answer, and
submitted-selection commitments. It checks abstention consistency, referenced
evidence, candidate-axiom behavior after abstention, and false-discovery flags.

A valid no-fit case must record:

```json
{
  "challenge_evaluation": {
    "selected_outcome": "abstain",
    "abstained": true,
    "false_discovery": false
  },
  "candidate_axiom": null,
  "verification": {
    "verdict": "not_evaluated_due_to_abstention"
  }
}
```

## Frozen calibration audit

v0.6 audits selection thresholds chosen on a disjoint calibration split and
frozen before unseen test seeds execute.

```bash
crumblm eja calibration-pack \
  artifacts/jump-lab-calibration/calibration-suite.json \
  --out artifacts/jump-lab-calibration/calibration-audit.json \
  --html artifacts/jump-lab-calibration/calibration-audit.html
```

The audit independently verifies:

- non-empty, disjoint calibration and test seed sets;
- `answers_used_for_calibration: false`;
- canonical hashes for every revealed calibration record;
- the threshold commitment over calibration seeds, case kinds, candidate grid,
  false-discovery constraint, record hashes, chosen threshold, and objective;
- deterministic reproduction of the chosen score and margin threshold;
- one identical frozen threshold across all test artifacts;
- challenge selection rules matching that frozen threshold;
- test decisions reproduced from each artifact's top score, margin, and evidence
  completion state;
- structural and sealed-challenge validity for every test artifact;
- test artifact hashes excluded from the calibration-only record commitment.

The resulting scorecard reports per-policy:

- overall and answerable accuracy;
- abstention accuracy;
- false-discovery rate;
- coverage and selective accuracy;
- frozen-decision reproduction rate.

This checks threshold discipline, not probability calibration. Anonymous-model
scores are not assumed to be calibrated probabilities.

A test artifact records:

```json
{
  "calibration_protocol": {
    "protocol": "disjoint_frozen_threshold_calibration_v1",
    "split": "test",
    "threshold_frozen_before_test": true,
    "threshold_commitment_hash": "sha256:...",
    "frozen_threshold": {
      "minimum_score": 0.75,
      "minimum_margin": 0.05
    },
    "calibration_record_hashes": ["sha256:..."],
    "test_answers_used_for_calibration": false
  }
}
```

The numeric values above illustrate the structure only; the suite must reproduce
whatever threshold its declared calibration records actually select.

## Lineage graph

```bash
crumblm eja lineage-pack artifacts \
  --out artifacts/eja-lineage.json \
  --html artifacts/eja-lineage.html
```

A declared parent edge means that one run consumed an artifact or bounded memory
derived from another. It does not prove scientific implication.

## Reproducibility manifest

```bash
crumblm eja manifest-pack artifacts --out artifacts/eja-manifest.json
```

The manifest records paths, canonical hashes, experiments, worlds, seeds,
winners, candidate-axiom IDs, verdicts, and parent hashes, then hashes the
manifest itself.

## Deterministic review bundle

```bash
crumblm eja bundle-pack artifacts \
  --out artifacts/eja-review-bundle.zip \
  --report artifacts/eja-review-bundle-result.json
```

The deterministic ZIP contains source artifacts, structural validation,
scientific audit, evidence audit, lineage, manifest, and a content-hashed index.
Run `challenge-pack` and `calibration-pack` alongside the bundle for their
specialized scorecards.

## Claim boundary

A valid artifact, pack, audit, challenge scorecard, calibration audit, evidence
graph, lineage graph, manifest, or bundle establishes internal format,
provenance, commitment, split, threshold, and consistency properties only. It
does not prove a candidate axiom outside the verifier scope recorded by the
experiment, establish real-world probabilistic calibration, or turn
pre-registered model selection into open-ended scientific discovery.
