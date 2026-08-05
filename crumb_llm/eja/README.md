# CRUMB EJA v0.4

CRUMB EJA stores a complete discovery handoff rather than a prose-only context
summary. An artifact keeps raw observations, the recorded surprise, competing
hypotheses, ordered interventions, trajectories, a scoped candidate axiom,
deductions, verifier output, metrics, and provenance.

## Single artifacts

```bash
crumblm eja validate examples/einstein-elevator.eja.json
crumblm eja summarize examples/einstein-elevator.eja.json
crumblm eja replay-plan examples/einstein-elevator.eja.json

# The zero-dependency standalone entrypoint also works:
python -m crumb_llm.eja validate examples/einstein-elevator.eja.json
```

Validation rejects missing falsifiers, collapsed hypothesis diversity, unclear
scope, hidden-state exposure, and mismatched canonical hashes.

## Pack validation and reports

```bash
crumblm eja validate-pack artifacts \
  --out artifacts/eja-pack.json \
  --html artifacts/eja-pack.html

crumblm eja summarize-pack artifacts
crumblm eja report-pack artifacts --out artifacts/eja-pack.html
```

Pack validation recursively discovers EJA JSON artifacts, validates each one,
and reports aggregate worlds, winners, verdicts, trajectory counts, completion
rates, and a stable pack hash.

## Scientific-consistency audit

```bash
crumblm eja audit-pack artifacts \
  --out artifacts/eja-audit.json \
  --html artifacts/eja-audit.html
```

The scientific audit checks structural validity, evidence completion, candidate
status versus verifier verdict, replication consistency, and lineage integrity.
Warnings do not automatically fail an audit. Structural contradictions and
scientific-state inconsistencies do.

## Evidence-reference and blind-protocol audit

v0.4 adds a graph from recorded intervention evidence to hypotheses, deductions,
candidate axioms, and verifier results.

```bash
crumblm eja evidence-pack artifacts \
  --out artifacts/eja-evidence.json \
  --html artifacts/eja-evidence.html
```

For blinded pre-registered model-selection artifacts, the audit also checks:

- unique `evidence_ref` values;
- hypothesis and deduction references that resolve to recorded trajectories;
- target-language leakage recorded by the benchmark;
- whether semantic model statements were hidden during selection;
- whether the artifact honestly labels the task as model selection rather than
  open-ended abduction;
- model-deck mapping and agent-prompt hashes;
- declared hypothesis origin.

Older non-blind artifacts remain compatible. Their prose evidence can produce
warnings, but it is not silently reinterpreted as a precise evidence reference.

## Lineage graph

Artifacts may declare hash-addressed parents:

```json
{
  "provenance": {
    "parent_artifact_hashes": ["sha256:..."]
  }
}
```

Build the graph with:

```bash
crumblm eja lineage-pack artifacts \
  --out artifacts/eja-lineage.json \
  --html artifacts/eja-lineage.html
```

A declared edge means that one run consumed an artifact or bounded memory
derived from another; it does not prove scientific implication.

## Reproducibility manifest

```bash
crumblm eja manifest-pack artifacts --out artifacts/eja-manifest.json
```

The manifest records each path, canonical hash, experiment, world, seed, winner,
candidate-axiom ID, verdict, and parent hashes, then hashes the manifest itself.

## Deterministic review bundle

```bash
crumblm eja bundle-pack artifacts \
  --out artifacts/eja-review-bundle.zip \
  --report artifacts/eja-review-bundle-result.json
```

The ZIP contains:

- every source EJA artifact under its relative path;
- structural validation;
- scientific audit;
- evidence audit;
- lineage graph;
- reproducibility manifest;
- a content-hashed `INDEX.json`.

Archive paths, ordering, timestamps, and report serialization are deterministic,
so an unchanged source pack produces the same bundle hash.

## Claim boundary

A valid artifact, pack, audit, evidence graph, lineage graph, manifest, or bundle
establishes internal format, provenance, and consistency properties only. It
does not prove a candidate axiom outside the verifier scope recorded by the
experiment, and it does not turn pre-registered model selection into open-ended
scientific discovery.
