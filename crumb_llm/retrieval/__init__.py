"""Semantic retrieval over CRUMB packs.

This package turns a CRUMB pack (a directory of ``.crumb`` files) into a
searchable vector index, so CrumbLLM can reason over the *relevant* slice of a
large pack instead of concatenating every file into one over-long prompt.

Design goals (matching the rest of CrumbLLM):

  - **Zero required dependencies.** The default embedder is a dependency-free
    feature-hashing embedder, and the default backend is a pure-Python
    brute-force cosine search. ``pip install crumb-llm`` keeps working offline.
  - **turbovec is optional, like the provider SDKs.** When
    `turbovec <https://github.com/RyanCodrai/turbovec>`_ is installed, the
    retriever uses its memory-efficient quantized index transparently; when it
    is not, the brute-force backend is used and a warning is surfaced. CrumbLLM
    never silently changes behaviour.
  - **Honest.** Backends report which engine actually ran, and the retriever
    surfaces warnings rather than guessing.
"""

from crumb_llm.retrieval.backends import (
    BruteForceBackend,
    TurboVecBackend,
    VectorBackend,
    get_backend,
)
from crumb_llm.retrieval.embedding import Embedder, HashingEmbedder
from crumb_llm.retrieval.retriever import CrumbRetriever, RetrievedDoc, focus_pack

__all__ = [
    "BruteForceBackend",
    "CrumbRetriever",
    "Embedder",
    "HashingEmbedder",
    "RetrievedDoc",
    "TurboVecBackend",
    "VectorBackend",
    "focus_pack",
    "get_backend",
]
