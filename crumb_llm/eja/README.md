# CRUMB EJA v0.2

CRUMB EJA stores a complete discovery handoff rather than a prose-only context
summary. An artifact keeps raw observations, the recorded surprise, competing
hypotheses, ordered interventions, trajectories, a scoped candidate axiom,
deductions, verifier output, and provenance.

## Single-artifact workflow

```bash
crumblm eja validate examples/einstein-elevator.eja.json
crumblm eja summarize examples/einstein-elevator.eja.json
crumblm eja replay-plan examples/einstein-elevator.eja.json
crumblm eja hash examples/einstein-elevator.eja.json
```

## Pack workflow

A pack is any directory tree containing one or more JSON objects whose
`artifact_type` is `eja_experiment`.

```bash
crumblm eja validate-pack artifacts \
  --out artifacts/eja-pack.json \
  --html artifacts/eja-pack.html

crumblm eja summarize-pack artifacts
crumblm eja report-pack artifacts --out artifacts/eja-pack.html
```

Pack reports aggregate structural validity, worlds, winning hypotheses,
verdicts, trajectory counts, optional discovery-completion metrics and a stable
pack hash derived from the ordered canonical artifact hashes.

The zero-dependency standalone entrypoint supports the same commands:

```bash
python -m crumb_llm.eja validate examples/einstein-elevator.eja.json
python -m crumb_llm.eja validate-pack artifacts
```

Validation rejects missing falsifiers, collapsed hypothesis diversity, unclear
scope, hidden-state exposure and a mismatched canonical hash. A valid artifact
or pack proves structural and provenance consistency only; it does not prove a
candidate axiom outside the verifier scope recorded in that artifact.
