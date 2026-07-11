# CrumbContext architecture

CrumbContext treats context optimization as a routing problem, not a single compression trick.

## Invariants

1. System, developer, policy, approval, citation, and recent-turn blocks remain native text.
2. Exact anchors are extracted before any summary or image transform.
3. Images are labelled non-authoritative historical context.
4. Every routing decision has a machine-readable reason.
5. Estimated token reduction is not advertised as measured billing reduction.

## Lanes

- `exact`: unchanged native text.
- `cache`: stable, repeatedly reused provider-cache candidates.
- `crumb`: structured memory folded into CRUMB summary/full form.
- `image`: stale dense content rendered after exact anchors are removed.
- `summary`: stale semantic context reduced extractively.
- `drop`: reserved for explicit user policy; never selected automatically in v0.1.

## Planned provider adapters

The v0.1 package builds provider-neutral bundles. A future gateway can map those bundles into provider-native APIs only where the provider preserves role and authority semantics. It must not relocate system content into a user message merely to gain image support.
