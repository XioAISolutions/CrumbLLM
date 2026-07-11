# CrumbContext

**Give every AI the context it needs—not the entire conversation.**

CrumbContext is a safety-first context router for long AI sessions. It protects exact facts and authority boundaries first, then routes stale context into the cheapest appropriate representation: provider cache, CRUMB memory, sanitized images, or deterministic summaries.

```bash
pip install -e .
crumbcontext demo --out demo
open demo/report.html
```

The demo produces a screenshot-ready report plus the actual routed artifacts:

```text
demo/
├── report.html
├── plan.json
├── anchors-all.txt
├── images/
├── crumbs/
└── summaries/
```

## Why this exists

Visual context compression can be powerful, but it is lossy. Exact identifiers, hashes, paths, amounts, citations, and instructions should not depend on visual recall. CrumbContext extracts those values into native-text CRUMB sidecars before any image or summary transform.

It also refuses to blur authority boundaries: system/developer instructions, policy blocks, approvals, citations, and current turns remain exact text.

## Route your own transcript

Create a JSON file containing context blocks:

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
crumbcontext route transcript.json --out routed
```

## Routing lanes

| Lane | Use |
|---|---|
| `exact` | System/developer/current/precision-critical context |
| `cache` | Stable context reused across requests |
| `crumb` | Structured project memory and handoffs |
| `image` | Old dense logs or tool output, after exact values are removed |
| `summary` | Old semantic context that does not need verbatim wording |

Every decision includes a reason in `plan.json`.

## Honest status

v0.1 is a working provider-neutral router, artifact generator, and benchmark/report surface. It is **not yet a transparent network proxy**. Provider adapters will only be added where role and authority semantics can be preserved; CrumbContext will not move system instructions into user content merely to compress them.

Token counts are deterministic estimates for A/B planning, not billing claims. A public savings claim requires a provider-specific counterfactual benchmark against the exact same requests.

## Relationship to CRUMB

- `crumb-format`: portable context and handoff standard.
- `CrumbLLM`: reasoning engine over CRUMB artifacts.
- `CrumbContext`: routing and exactness layer.
- `ai-memory`: private dogfood and persistent memory source.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
crumbcontext demo --out demo
```

MIT © XIO AI Solutions
