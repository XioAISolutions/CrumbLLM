"""Parse and validate CRUMB documents.

CrumbLLM is **standalone**: it bundles its own CRUMB reader in
:mod:`crumb_llm.crumb.spec`, so reading ``.crumb`` files has no runtime
dependency on ``crumb-format`` (or anything else). This module is the single
seam between CrumbLLM and the CRUMB grammar — the rest of the package only ever
sees the parsed ``{"headers": {...}, "sections": {...}}`` mapping returned here.

If the canonical ``crumb-format`` package is installed it is *preferred* (so
CrumbLLM tracks the upstream spec automatically), but it is never required: the
bundled reader is a complete fallback.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from crumb_llm.crumb import spec


class CrumbFormatUnavailable(RuntimeError):
    """Kept for backwards compatibility.

    CrumbLLM now bundles its own CRUMB reader, so parsing is always available
    and this is never raised. It remains importable so existing callers that
    reference it keep working.
    """


@lru_cache(maxsize=1)
def _resolve_parser() -> Callable[[str], dict]:
    # Prefer the canonical crumb-format parser when it is installed, so CrumbLLM
    # tracks the upstream spec; otherwise fall back to the bundled reader.
    try:
        from crumb_format import parse_crumb  # type: ignore

        return parse_crumb
    except Exception:
        pass
    try:
        from cli.crumb import parse_crumb  # type: ignore

        return parse_crumb
    except Exception:
        pass
    return spec.parse_crumb


def parse_text(text: str) -> dict:
    """Parse CRUMB text into ``{"headers": {...}, "sections": {...}}``.

    Raises ``ValueError`` on malformed CRUMB.
    """
    return _resolve_parser()(text)


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
