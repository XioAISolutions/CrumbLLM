# CRUMB EJA v0.7

> **A separate package, on purpose.** CRUMB EJA is a discovery-artifact format.
> It is not the CRUMB handoff format, it shares no code with `crumb_llm`, and
> its claims are different ones. It lived under `crumb_llm/eja/` until it was
> found to import nothing from its host — so it became `crumb_eja`, with its
> own `crumb-eja` command. `crumblm eja ...` still works for existing scripts.
>
> Moving it to its own repository is now a directory move plus a
> `pyproject.toml`. CI enforces the decoupling that keeps it that cheap.

CRUMB EJA stores a complete discovery handoff rather than a prose-only context
summary. An artifact keeps raw observations, the recorded surprise, competing or
generated hypotheses, ordered interventions, trajectories, a scoped candidate
axiom, deductions, verifier output, metrics, and provenance.

## Single artifacts

```bash
crumb-eja validate crumb_eja/examples/einstein-elevator.eja.json
crumb-eja summarize crumb_eja/examples/einstein-elevator.eja.json
crumb-eja replay-plan crumb_eja/examples/einstein-elevator.eja.json

python -m crumb_eja validate crumb_eja/examples/einstein-elevator.eja.json
```

Validation rejects missing falsifiers, collapsed hypothesis diversity, unclear
scope, hidden-state exposure, and mismatched canonical hashes.

## Pack validation and scientific audit

```bash
crumb-eja validate-pack artifacts \
  --out artifacts/eja-pack.json \
  --html artifacts/eja-pack.html

crumb-eja audit-pack artifacts \
  --out artifacts/eja-audit.json \
  --html artifacts/eja-audit.html
```

The scientific audit checks structural validity, evidence completion, candidate
status versus verifier verdict, replication consistency, and lineage integrity.

## Evidence-reference and blind-protocol audit

```bash
crumb-eja evidence-pack artifacts \
  --out artifacts/eja-evidence.json \
  --html artifacts/eja-evidence.html
```

The evidence graph connects recorded intervention evidence to hypotheses,
deductions, candidate axioms, and verifier results. For blinded model-selection
artifacts, it also checks target-language leakage, statement exposure, mapping
and prompt hashes, and declared hypothesis origin.

## Sealed challenge and abstention audit

```bash
crumb-eja challenge-pack artifacts/jump-lab-challenge \
  --out artifacts/eja-challenge-audit.json \
  --html artifacts/eja-challenge-audit.html
```

The v0.5 challenge gate independently recomputes hidden case, hidden answer, and
submitted-selection commitments. It checks abstention consistency, referenced
evidence, candidate-axiom behavior after abstention, and false-discovery flags.

## Frozen calibration audit

```bash
crumb-eja calibration-pack \
  artifacts/jump-lab-calibration/calibration-suite.json \
  --out artifacts/jump-lab-calibration/calibration-audit.json \
  --html artifacts/jump-lab-calibration/calibration-audit.html
```

v0.6 independently verifies disjoint calibration/test seeds, calibration-record
hashes, the frozen threshold commitment, deterministic threshold reproduction,
answer leakage, threshold drift, and unseen-test decision reproduction.

## Finite-grammar symbolic synthesis audit

v0.7 adds a separate review lane for artifacts that generate symbolic candidates
from a committed grammar instead of selecting from a pre-registered list of
complete models.

```bash
crumb-eja synthesis-pack artifacts/jump-lab-synthesis \
  --suite artifacts/jump-lab-synthesis/synthesis-suite.json \
  --out artifacts/jump-lab-synthesis/synthesis-audit.json \
  --html artifacts/jump-lab-synthesis/synthesis-audit.html
```

The artifact-level audit checks:

- grammar SHA-256 commitment;
- hidden case and target commitments;
- `target_visible_to_agent: false`;
- `target_expression_pre_registered: false`;
- generated candidate count versus the committed grammar budget;
- every exponent token against the grammar;
- unique candidate IDs;
- deterministic ranking by fit, complexity, and candidate ID;
- selected candidate consistency;
- frozen-threshold acceptance and abstention;
- exact exponent recovery after the target reveal;
- prevention of candidate-axiom compilation for no-fit cases;
- candidate-axiom linkage to the generated expression;
- required post-selection verifier verdicts;
- declared hypothesis origin and hidden-state boundary.

When `--suite` is supplied, CRUMB also recomputes:

- calibration-record hashes;
- the synthesis threshold commitment;
- the deterministic threshold selected from the declared grid and objective;
- calibration/test seed disjointness;
- positive held-out exponent-pair disjointness;
- the shared frozen threshold commitment referenced by test artifacts.

The v0.7 scorecard reports test accuracy, held-out exact exponent recovery,
no-fit abstention accuracy, false-discovery rate, positive-abstention rate, and
grammar-commitment validity.

The companion schema is:

```text
crumb_eja/schemas/eja-synthesis-v1.schema.json
```

This lane is intentionally called **finite-grammar symbolic synthesis**. A
passing audit proves that the recorded grammar search and commitments are
internally reproducible. It does not mean that the system invented arbitrary new
operators, variables, or scientific concepts.

## Lineage graph

```bash
crumb-eja lineage-pack artifacts \
  --out artifacts/eja-lineage.json \
  --html artifacts/eja-lineage.html
```

A declared parent edge means that one run consumed an artifact or bounded memory
derived from another. It does not prove scientific implication.

## Reproducibility manifest

```bash
crumb-eja manifest-pack artifacts --out artifacts/eja-manifest.json
```

The manifest records paths, canonical hashes, experiments, worlds, seeds,
winners, candidate-axiom IDs, verdicts, and parent hashes, then hashes the
manifest itself.

## Deterministic review bundle

```bash
crumb-eja bundle-pack artifacts \
  --out artifacts/eja-review-bundle.zip \
  --report artifacts/eja-review-bundle-result.json
```

The deterministic ZIP contains source artifacts, structural validation,
scientific audit, evidence audit, lineage, manifest, and a content-hashed index.
Specialized challenge, calibration, and synthesis scorecards remain available as
separate explicit audit commands.

## Claim boundary

A valid artifact, pack, audit, challenge scorecard, calibration audit, synthesis
audit, evidence graph, lineage graph, manifest, or bundle establishes internal
format, provenance, commitment, split, threshold, grammar, and consistency
properties only. It does not prove a candidate axiom outside the verifier scope
recorded by the experiment, establish real-world probabilistic calibration, or
turn a finite hand-authored grammar into open-ended scientific discovery.
