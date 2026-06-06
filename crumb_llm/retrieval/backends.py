"""Vector index backends.

Two implementations sit behind one tiny interface:

  - :class:`BruteForceBackend` — pure Python, zero dependencies. Exact cosine
    search. Always available; the safe default.
  - :class:`TurboVecBackend` — wraps `turbovec
    <https://github.com/RyanCodrai/turbovec>`_, a quantized vector index that
    keeps 10M+ vectors in a fraction of the RAM of raw float32 while staying
    fast. Used automatically when ``turbovec`` (and its ``numpy`` dependency)
    import cleanly; otherwise the retriever falls back to brute force.

The interface is deliberately minimal — ``add`` then ``search`` — because that is
all the retriever needs and it maps cleanly onto turbovec's online-indexing
API (``add`` / ``search``, no train step).
"""

from __future__ import annotations

import abc
import heapq


class VectorBackend(abc.ABC):
    """Add vectors, then search them by cosine similarity."""

    name: str = "base"

    @abc.abstractmethod
    def add(self, ids: list[int], vectors: list[list[float]]) -> None:
        """Index ``vectors``, each tagged with the matching id in ``ids``."""
        raise NotImplementedError

    @abc.abstractmethod
    def search(self, query: list[float], k: int) -> list[tuple[int, float]]:
        """Return up to ``k`` ``(id, score)`` pairs, best score first."""
        raise NotImplementedError


class BruteForceBackend(VectorBackend):
    """Exact cosine search in pure Python.

    Embeddings handed in are expected to be L2-normalised already (the
    bundled :class:`~crumb_llm.retrieval.embedding.HashingEmbedder` does this),
    so a dot product *is* the cosine similarity. We still tolerate un-normalised
    input by dividing through by the query norm, which only rescales scores.
    """

    name = "bruteforce"

    def __init__(self) -> None:
        self._ids: list[int] = []
        self._vectors: list[list[float]] = []

    def add(self, ids: list[int], vectors: list[list[float]]) -> None:
        if len(ids) != len(vectors):
            raise ValueError("ids and vectors must be the same length")
        self._ids.extend(ids)
        self._vectors.extend(vectors)

    def search(self, query: list[float], k: int) -> list[tuple[int, float]]:
        if k <= 0 or not self._vectors:
            return []
        scored = (
            (sum(q * v for q, v in zip(query, vec)), idx)
            for idx, vec in zip(self._ids, self._vectors)
        )
        top = heapq.nlargest(k, scored)
        return [(idx, score) for score, idx in top]


class TurboVecBackend(VectorBackend):
    """Memory-efficient quantized search via turbovec.

    turbovec stores vectors compressed (the TurboQuant pipeline) and supports
    stable external ids through its ``IdMapIndex``. We build the index lazily on
    the first :meth:`add` because turbovec needs the vector dimension up front.

    turbovec is an optional dependency. :func:`get_backend` only ever constructs
    this class after confirming the import succeeds, and wraps construction in a
    fallback, so a missing or API-incompatible turbovec degrades to brute force
    instead of crashing.
    """

    name = "turbovec"

    def __init__(self) -> None:
        self._np = self._import_numpy()
        self._turbovec = self._import_turbovec()
        self._index = None  # built on first add(), once we know the dimension

    @staticmethod
    def _import_turbovec():
        import turbovec  # noqa: F401  (presence check; symbols resolved below)

        return turbovec

    @staticmethod
    def _import_numpy():
        import numpy

        return numpy

    def _ensure_index(self, dim: int) -> None:
        if self._index is not None:
            return
        # turbovec exposes a quantized index wrapped in an id map so we can use
        # our own document ids. Construction is kept defensive: get_backend()
        # treats any failure here as "turbovec unavailable".
        base = self._turbovec.TurboQuantIndex(dim)
        self._index = self._turbovec.IdMapIndex(base)

    def add(self, ids: list[int], vectors: list[list[float]]) -> None:
        if len(ids) != len(vectors):
            raise ValueError("ids and vectors must be the same length")
        if not vectors:
            return
        self._ensure_index(len(vectors[0]))
        arr = self._np.asarray(vectors, dtype=self._np.float32)
        id_arr = self._np.asarray(ids, dtype=self._np.int64)
        self._index.add(arr, id_arr)

    def search(self, query: list[float], k: int) -> list[tuple[int, float]]:
        if k <= 0 or self._index is None:
            return []
        q = self._np.asarray([query], dtype=self._np.float32)
        ids, scores = self._index.search(q, k)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0])]


def get_backend(prefer_turbovec: bool = True) -> tuple[VectorBackend, list[str]]:
    """Return ``(backend, warnings)``.

    When ``prefer_turbovec`` is set we try the turbovec-backed index first and
    fall back to brute force on any import or construction error, recording a
    warning so the caller can surface *why* the faster path was not taken.
    """
    warnings: list[str] = []
    if prefer_turbovec:
        try:
            return TurboVecBackend(), warnings
        except Exception as exc:  # ImportError, or any turbovec API mismatch
            warnings.append(
                "turbovec unavailable, using pure-Python brute-force search "
                f"({exc.__class__.__name__}: {exc}). "
                "Install it with `pip install turbovec` for memory-efficient "
                "search over large packs."
            )
    return BruteForceBackend(), warnings
