"""Parse and validate CRUMB documents via the reference parser.

CrumbLLM used to bundle a 334-line fork of the CRUMB grammar in
``crumb_llm.crumb.spec``, and CI ran a job asserting that ``crumb-format`` was
not even importable — independence enforced as a property. The cost of that
independence was silent divergence: three repositories each carried a private
parser, ``CrumbContext`` emitted ``v=1.3`` against a ``v=1.4`` spec, and this
package's own EJA schemas required a ``crumb_version`` of ``"1.5"`` that no
spec defines. The fork's docstring promised it was "kept faithful" to the
canonical parser, but nothing tested the two against each other.

The grammar now lives once, in ``crumb_core`` — stdlib-only and
dependency-free, deliberately carrying none of the crumb-format CLI. This
module remains the single seam between CrumbLLM and the CRUMB grammar; the
rest of the package only ever sees the parsed
``{"headers": {...}, "sections": {...}}`` mapping returned here.
"""

from __future__ import annotations

try:
    import crumb_core
except ImportError as _exc:  # pragma: no cover - exercised by the import-failure test
    raise ImportError(
        "crumb_core is required to read CRUMB files. Install it with "
        "`pip install crumb-format`, which ships the reference parser."
    ) from _exc


class CrumbFormatUnavailable(RuntimeError):
    """Kept for backwards compatibility.

    Previously signalled that no CRUMB reader was present. ``crumb_core`` is a
    hard dependency now, so a missing parser surfaces as an ``ImportError`` at
    module load instead. This name remains importable so existing callers that
    reference it keep working.
    """


def parse_text(text: str) -> dict:
    """Parse CRUMB text into ``{"headers": {...}, "sections": {...}}``.

    Raises ``ValueError`` on malformed CRUMB.
    """
    return crumb_core.parse_crumb(text)


def validate_text(text: str) -> list[str]:
    """Validate CRUMB text. Returns a list of error strings (empty == valid).

    Validation is structural: the parser raises on any problem.
    """
    try:
        parse_text(text)
        return []
    except ValueError as exc:
        return [str(exc)]
