"""CrumbLLM — AI analysis over CRUMB files and CRUMB packs.

CrumbLLM reads CRUMB files (the project-memory handoff format), understands
project memory, and produces summaries, risks, next actions, PR notes, and
improved handoffs.

It is *not* IBM Bob session capture (that lives in ``Crumb-Bob``). CrumbLLM
only reads CRUMB artifacts and reasons over them; the grammar itself lives
once, in ``crumb_core``, which ships with ``crumb-format``.

Two paths, deliberately separate:

* :mod:`crumb_llm.score` reads a CRUMB and returns a readiness score from
  fixed rules — no model, no network, no keys, deterministic.
* :class:`crumb_llm.engine.CrumbEngine` asks a language model, then gates the
  answer. Every result carries the warnings the gates raised.
"""

from crumb_llm.models import (
    AnalysisResult,
    CrumbDoc,
    CrumbPack,
    ProviderConfig,
)
from crumb_llm.score import (
    HandoffScore,
    PackScore,
    Signal,
    score_doc,
    score_pack,
)

__version__ = "0.1.0"

__all__ = [
    "AnalysisResult",
    "CrumbDoc",
    "CrumbPack",
    "HandoffScore",
    "PackScore",
    "ProviderConfig",
    "Signal",
    "score_doc",
    "score_pack",
    "__version__",
]
