# CRUMB EJA v0.3

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

The v0.3 audit checks:

- structural and canonical-hash validity;
- candidate axioms created before evidence completion;
- completed discoveries missing their candidate axiom;
- candidate-status and verifier-verdict mismatches;
- conflicting verdicts across replicated world/axiom groups;
- leading-hypothesis instability across replications;
- duplicate artifacts, missing declared parents, self-parent links, and lineage
  cycles.

Warnings do not automatically fail an audit. Structural contradictions and
scientific-state inconsistencies do.

## Lineage graph

Artifacts may declare:

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

The graph records hash-addressed parent-child edges, duplicate hashes, missing
parents, and cycles. A declared edge means that one run consumed an artifact or
bounded memory derived from another; it does not prove scientific implication.

## Reproducibility manifest

```bash
crumblm eja manifest-pack artifacts --out artifacts/eja-manifest.json
```

The manifest records each path, canonical hash, experiment, world, seed, winner,
candidate-axiom ID, verdict, and parent hashes, then hashes the manifest itself.

## Claim boundary

A valid artifact, pack, audit, lineage graph, or manifest establishes internal
format, provenance, and consistency properties only. It does not prove a
candidate axiom outside the verifier scope recorded by the experiment.
