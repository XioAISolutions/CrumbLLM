"""Parse and validate CRUMB documents.

CrumbLLM is **independent**: it bundles its own CRUMB reader in
:mod:`crumb_llm.crumb.spec` and uses it exclusively. Reading ``.crumb`` files
has no dependency on ``crumb-format`` (or anything else) — CrumbLLM never
imports, prefers, or requires it. This module is the single seam between
CrumbLLM and the CRUMB grammar; the rest of the package only ever sees the
parsed ``{"headers": {...}, "sections": {...}}`` mapping returned here.
"""

from __future__ import annotations

from crumb_llm.crumb import spec


class CrumbFormatUnavailable(RuntimeError):
    """Kept for backwards compatibility.

    CrumbLLM bundles its own CRUMB reader, so parsing is always available and
    this is never raised. It remains importable so existing callers that
    reference it keep working.
    """


def parse_text(text: str) -> dict:
    """Parse CRUMB text into ``{"headers": {...}, "sections": {...}}``.

    Raises ``ValueError`` on malformed CRUMB.
    """
    return spec.parse_crumb(text)


def validate_text(text: str) -> list[str]:
    """Validate CRUMB text. Returns a list of error strings (empty == valid).

    Validation is structural: the parser raises on any problem.
    """
    try:
        parse_text(text)
        return []
    except ValueError as exc:
        return [str(exc)]
    except Exception as exc:  # pragma: no cover - defensive
        return [f"unexpected parse error: {exc}"]
