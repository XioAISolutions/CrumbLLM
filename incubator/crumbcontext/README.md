# CrumbContext 🧠🧱

> **Give every AI the context it needs—not the entire conversation.**

CrumbContext is a safety-first context router for long AI sessions. It protects exact facts and authority boundaries first, then routes stale context into the best representation: exact text, provider cache, CRUMB memory, sanitized images, or deterministic summaries.

## Run the proof

```bash
python -m pip install -e '.[dev]'
crumbcontext benchmark --out proof --open
```

You get:

```text
proof/
├── report.html          # inspect every decision
├── share-card.svg       # share the result
├── benchmark.json       # self-check outcome
├── plan.json            # machine-readable routing plan
├── images/              # sanitized historical context
├── crumbs/              # exact anchors + structured memory
└── summaries/           # deterministic stale-context summaries
```

Typical bundled fixture:

```text
CrumbContext benchmark: PASS
Estimated tokens: 18,687 -> 6,392 (65.8% reduction)
Exact anchors: 31/31 preserved
```

> These are deterministic planning estimates, not provider billing records. A public savings claim requires a same-request provider counterfactual.

## Pick a mission

<details open>
<summary><strong>See the demo</strong></summary>

```bash
crumbcontext demo --out demo --open
```

</details>

<details>
<summary><strong>Route your own transcript</strong></summary>

Create a JSON file:

```json
{
  "blocks": [
    {"id":"system","role":"system","kind":"instruction","content":"Never deploy without approval.","authoritative":true},
    {"id":"old-log","role":"user","kind":"tool_result","content":"...","age_turns":12},
    {"id":"now","role":"user","kind":"message","content":"Fix the test.","age_turns":0}
  ]
}
```

Then:

```bash
crumbcontext analyze transcript.json
crumbcontext route transcript.json --out routed --open
```

</details>

<details>
<summary><strong>Test without image routing</strong></summary>

```bash
crumbcontext benchmark --no-images --out proof-text-only
```

This is useful for comparing summary/cache routing against the image lane.

</details>

## The rule that matters

**Exact facts never depend on pixels.**

Before any lossy transform, CrumbContext extracts:

- paths;
- hashes and long hex values;
- UUIDs;
- URLs and emails;
- dates and timestamps;
- currency amounts;
- environment variables;
- long numeric identifiers.

Those values go into native-text CRUMB sidecars. Images and summaries receive stable labels such as `[EXACT_7:sha_or_hex]` instead of the original value.

## Routing lanes

| Lane | Use |
|---|---|
| `exact` | system/developer/current/precision-critical context |
| `cache` | stable context reused across requests |
| `crumb` | structured project memory and handoffs |
| `image` | old dense logs or tool output, after exact values are removed |
| `summary` | old semantic context that does not need verbatim wording |

Every decision includes a reason in `plan.json`.

## Honest status

v0.1 is a working provider-neutral router, artifact generator, self-verifying benchmark, and report surface. It is **not yet a transparent network proxy**.

Provider adapters will only be added where role and authority semantics can be preserved. CrumbContext will not move system instructions into user content merely to gain image support.

## Relationship to CRUMB

- `crumb-format`: portable context and handoff standard.
- `CrumbLLM`: reasoning engine over CRUMB artifacts.
- `CrumbContext`: routing and exactness layer.
- `ai-memory`: private dogfood and persistent memory source.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
crumbcontext benchmark --out proof
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for routing invariants and [`docs/LAUNCH.md`](docs/LAUNCH.md) for release gates.

MIT © XIO AI Solutions
