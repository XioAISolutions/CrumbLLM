# CRUMB EJA v0.5

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

The v0.4 evidence graph connects recorded intervention evidence to hypotheses,
deductions, candidate axioms, and verifier results. For blinded model-selection
artifacts, it also checks target-language leakage, statement exposure, mapping
and prompt hashes, and declared hypothesis origin.

## Sealed challenge and abstention audit

v0.5 adds a review gate for challenge artifacts in which the evaluator commits
to a hidden case and answer before execution. The expected answer may be a
registered model or `abstain` when the deck contains no adequate explanation.

```bash
crumblm eja challenge-pack artifacts/jump-lab-challenge \
  --out artifacts/eja-challenge-audit.json \
  --html artifacts/eja-challenge-audit.html
```

The challenge audit independently recomputes:

- hidden case commitment;
- hidden answer commitment;
- submitted selection commitment;
- selection and abstention consistency;
- evidence references carried by the submission;
- candidate-axiom behavior after abstention;
- stored correctness, false-discovery, and positive-abstention flags.

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

The pack scorecard reports:

- overall accuracy;
- answerable-case accuracy;
- none-of-the-above abstention accuracy;
- false-discovery rate;
- positive-abstention rate;
- coverage and selective accuracy;
- commitment-valid rate.

This separates two questions that should not be conflated: whether the system
can select a useful registered explanation and whether it knows when the deck is
not adequate.

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
Run `challenge-pack` alongside the bundle for sealed challenge scorecards.

## Claim boundary

A valid artifact, pack, audit, challenge scorecard, evidence graph, lineage
graph, manifest, or bundle establishes internal format, provenance, commitment,
and consistency properties only. It does not prove a candidate axiom outside the
verifier scope recorded by the experiment, and it does not turn pre-registered
model selection into open-ended scientific discovery.
