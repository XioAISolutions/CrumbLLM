"""Tests for the turbovec-backed semantic retrieval layer.

These exercise the dependency-free default path (HashingEmbedder +
BruteForceBackend). turbovec itself is optional and not installed in CI, so the
fallback behaviour is what we assert here.
"""

import math

from crumb_llm.crumb.pack_reader import read_pack
from crumb_llm.models import CrumbDoc, CrumbPack
from crumb_llm.retrieval import (
    BruteForceBackend,
    CrumbRetriever,
    HashingEmbedder,
    focus_pack,
    get_backend,
)


def _doc(name: str, body: str) -> CrumbDoc:
    raw = f"# notes\n{body}"
    return CrumbDoc(
        path=f"{name}.crumb",
        headers={"kind": "session", "title": name},
        sections={"notes": [body]},
        raw_text=raw,
    )


def _pack(*docs) -> CrumbPack:
    return CrumbPack(root="(test)", docs=list(docs))


def test_hashing_embedder_is_normalised_and_fixed_length():
    emb = HashingEmbedder(dim=64)
    vec = emb.embed("rate limiter middleware gateway")
    assert len(vec) == 64
    assert math.isclose(math.sqrt(sum(x * x for x in vec)), 1.0, rel_tol=1e-9)


def test_hashing_embedder_empty_text_is_zero_vector():
    emb = HashingEmbedder(dim=16)
    assert emb.embed("") == [0.0] * 16


def test_bruteforce_orders_by_similarity():
    emb = HashingEmbedder()
    backend = BruteForceBackend()
    texts = ["database migration postgres", "frontend react button styling"]
    backend.add([0, 1], [emb.embed(t) for t in texts])
    hits = backend.search(emb.embed("postgres migration"), k=2)
    assert hits[0][0] == 0  # the database doc ranks first
    assert hits[0][1] >= hits[1][1]


def test_get_backend_falls_back_without_turbovec():
    # turbovec is not installed in CI, so we expect brute force + a warning.
    backend, warnings = get_backend(prefer_turbovec=True)
    assert backend.name == "bruteforce"
    assert any("turbovec" in w for w in warnings)


def test_get_backend_can_skip_turbovec_silently():
    backend, warnings = get_backend(prefer_turbovec=False)
    assert backend.name == "bruteforce"
    assert warnings == []


def test_retriever_returns_most_relevant_doc_first():
    pack = _pack(
        _doc("auth", "fix the login session token expiry bug in the gateway"),
        _doc("ui", "tweak the dashboard chart colors and spacing"),
        _doc("infra", "bump the kubernetes node pool and helm chart version"),
    )
    hits = CrumbRetriever().index_pack(pack).retrieve("login token bug", k=2)
    assert len(hits) == 2
    assert hits[0].doc.title == "auth"


def test_focus_pack_narrows_and_preserves_manifest():
    pack = _pack(
        _doc("a", "payment stripe checkout webhook handling"),
        _doc("b", "logging and metrics dashboards"),
        _doc("c", "stripe refund webhook retries"),
    )
    pack.manifest = {"session": "demo"}
    focused, warnings = focus_pack(pack, "stripe webhook", k=2)
    assert len(focused) == 2
    assert focused.manifest == {"session": "demo"}
    assert focused.root == pack.root
    titles = {d.title for d in focused.docs}
    assert "a" in titles and "c" in titles  # both stripe docs beat the logging one
    # warnings is the turbovec-fallback note (list, possibly empty).
    assert isinstance(warnings, list)


def test_retrieve_before_index_raises():
    try:
        CrumbRetriever().retrieve("anything")
    except RuntimeError as exc:
        assert "index_pack" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_focus_pack_on_example_pack(example_pack):
    pack = read_pack(example_pack)
    focused, _ = focus_pack(pack, "session work", k=1)
    assert len(focused) == 1
