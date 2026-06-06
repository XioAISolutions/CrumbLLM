"""Embedders: turn CRUMB text into fixed-length vectors.

The default :class:`HashingEmbedder` is intentionally dependency-free. It uses
the signed feature-hashing ("hashing trick") to map a bag of word/character
n-gram tokens into a fixed-dimension, L2-normalised vector. This is not a
neural embedding, but it is deterministic, fast, offline, and good enough to
rank the CRUMB files in a pack by lexical relevance to a query — which is the
job CrumbLLM needs done before it reasons over the result.

Embedders are pluggable: anything exposing ``dim`` and ``embed(text) -> list``
satisfies the :class:`Embedder` protocol, so a caller can drop in a
provider-backed neural embedder without touching the retriever or the backends.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, runtime_checkable

# Word tokens plus their adjacent bigrams give a little context sensitivity
# without pulling in a tokenizer dependency.
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


@runtime_checkable
class Embedder(Protocol):
    """Anything that can turn text into a fixed-length vector."""

    dim: int

    def embed(self, text: str) -> list[float]:
        """Return an L2-normalised vector of length ``dim``."""
        ...


def _tokens(text: str) -> list[str]:
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    if len(words) < 2:
        return words
    bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:])]
    return words + bigrams


def _hash(token: str, dim: int) -> tuple[int, float]:
    """Map a token to (bucket, sign) via a stable hash.

    The low bits pick the bucket; one extra bit picks the sign, so colliding
    tokens partially cancel instead of always reinforcing — the standard signed
    hashing trick.
    """
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    bucket = value % dim
    sign = 1.0 if (value >> 63) & 1 else -1.0
    return bucket, sign


class HashingEmbedder:
    """Dependency-free signed feature-hashing embedder.

    Token counts are dampened with ``log1p`` (sublinear term frequency) so a
    word repeated many times does not dominate the vector, then the whole
    vector is L2-normalised so cosine similarity reduces to a dot product.
    """

    def __init__(self, dim: int = 256):
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        counts: dict[str, int] = {}
        for tok in _tokens(text):
            counts[tok] = counts.get(tok, 0) + 1
        for tok, count in counts.items():
            bucket, sign = _hash(tok, self.dim)
            vec[bucket] += sign * math.log1p(count)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            vec = [x / norm for x in vec]
        return vec
