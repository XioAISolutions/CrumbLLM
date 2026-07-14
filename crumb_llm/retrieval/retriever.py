"""CrumbRetriever — semantic search over a CRUMB pack.

The retriever embeds each CRUMB file in a pack, indexes the embeddings in a
:class:`~crumb_llm.retrieval.backends.VectorBackend`, and answers queries with
the most relevant files. :func:`focus_pack` is the convenience that ties this
back into the existing engine: it returns a *new* :class:`CrumbPack` containing
only the top-k files, so every existing task (`summarize`, `risks`, `next`, …)
can run over the relevant slice of a large pack with no other changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from crumb_llm.models import CrumbDoc, CrumbPack
from crumb_llm.retrieval.backends import VectorBackend, get_backend
from crumb_llm.retrieval.embedding import Embedder, HashingEmbedder


@dataclass
class RetrievedDoc:
    """A single search hit: the matched CRUMB file and its relevance score."""

    doc: CrumbDoc
    score: float


class CrumbRetriever:
    """Index a CRUMB pack and retrieve the files most relevant to a query."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        backend: VectorBackend | None = None,
        prefer_turbovec: bool = True,
    ):
        self.embedder = embedder or HashingEmbedder()
        if backend is not None:
            self.backend = backend
            self.warnings: list[str] = []
        else:
            self.backend, self.warnings = get_backend(prefer_turbovec)
        self._docs: list[CrumbDoc] = []
        self._indexed = False

    @property
    def backend_name(self) -> str:
        return getattr(self.backend, "name", "unknown")

    def index_pack(self, pack: CrumbPack) -> "CrumbRetriever":
        """Embed and index every CRUMB file in ``pack``. Returns ``self``."""
        self._docs = list(pack.docs)
        if self._docs:
            vectors = [self.embedder.embed(doc.as_text()) for doc in self._docs]
            self.backend.add(list(range(len(self._docs))), vectors)
        self._indexed = True
        return self

    def retrieve(self, query: str, k: int = 5) -> list[RetrievedDoc]:
        """Return up to ``k`` files most relevant to ``query``, best first."""
        if not self._indexed:
            raise RuntimeError("call index_pack() before retrieve()")
        if not self._docs:
            return []
        query_vec = self.embedder.embed(query)
        hits = self.backend.search(query_vec, k)
        return [RetrievedDoc(self._docs[idx], score) for idx, score in hits]


def focus_pack(
    pack: CrumbPack,
    query: str,
    k: int = 5,
    embedder: Embedder | None = None,
    prefer_turbovec: bool = True,
) -> tuple[CrumbPack, list[str]]:
    """Return ``(focused_pack, warnings)`` for the top-k files matching ``query``.

    The returned pack keeps the original ``root`` and ``manifest`` so downstream
    tasks behave identically — only the file set is narrowed to what is relevant.
    Backend warnings (e.g. turbovec not installed) are passed through so callers
    stay honest about which search engine actually ran.
    """
    retriever = CrumbRetriever(embedder=embedder, prefer_turbovec=prefer_turbovec)
    retriever.index_pack(pack)
    hits = retriever.retrieve(query, k=k)
    focused = CrumbPack(
        root=pack.root,
        docs=[hit.doc for hit in hits],
        manifest=pack.manifest,
    )
    return focused, retriever.warnings
