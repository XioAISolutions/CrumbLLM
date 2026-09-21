import json

from crumb_llm.crumb.loader import load_crumb
from crumb_llm.crumb.pack_reader import read_pack
from crumb_llm.engine import CrumbEngine
from crumb_llm.providers.base import BaseProvider, MockProvider


class GroundedProvider(BaseProvider):
    """Returns text that only references a known source path."""

    name = "grounded"

    def generate(self, prompt, max_tokens=1024, temperature=0.2):
        return "Summary: implement the limiter in src/gateway/middleware.py."


class HallucinatingProvider(BaseProvider):
    name = "halluc"

    def generate(self, prompt, max_tokens=1024, temperature=0.2):
        return "You should edit totally/made-up/path.py to fix this."


def test_engine_analyze_with_mock(basic_crumb):
    doc = load_crumb(basic_crumb)
    engine = CrumbEngine(provider=MockProvider())
    result = engine.analyze(doc)
    assert result.task == "analyze"
    assert result.provider == "mock"
    assert result.text


def test_engine_grounded_has_no_path_warnings(basic_crumb):
    doc = load_crumb(basic_crumb)
    engine = CrumbEngine(provider=GroundedProvider())
    result = engine.summarize(doc)
    assert not any("hallucinated" in w for w in result.warnings)


def test_engine_flags_hallucinated_paths(basic_crumb):
    doc = load_crumb(basic_crumb)
    engine = CrumbEngine(provider=HallucinatingProvider())
    result = engine.summarize(doc)
    assert any("hallucinated" in w for w in result.warnings)


def test_engine_risks_json(example_pack):
    pack = read_pack(example_pack)

    class JsonProvider(BaseProvider):
        name = "json"

        def generate(self, prompt, max_tokens=1024, temperature=0.2):
            return json.dumps({"risks": []})

    engine = CrumbEngine(provider=JsonProvider())
    result = engine.risks(pack, as_json=True)
    assert result.data == {"risks": []}
    assert not result.warnings


def test_engine_risks_json_invalid_warns(basic_crumb):
    doc = load_crumb(basic_crumb)

    class BadJsonProvider(BaseProvider):
        name = "badjson"

        def generate(self, prompt, max_tokens=1024, temperature=0.2):
            return "this is not json at all but long enough"

    engine = CrumbEngine(provider=BadJsonProvider())
    result = engine.risks(doc, as_json=True)
    assert any("did not parse" in w for w in result.warnings)


# --- stub providers must never be reported as trustworthy ------------------

def test_stub_provider_output_is_never_ok():
    """A gate that passes its own placeholder is not a gate.

    MockProvider text parses, is long enough, and matches no refusal phrase,
    so every content gate passed it and `ok` was True over a sentence that
    says nothing about the CRUMB. The provider knows it is a stub; the engine
    says so.
    """
    from crumb_llm.crumb.loader import load_crumb_text
    from crumb_llm.engine import CrumbEngine

    doc = load_crumb_text(
        "BEGIN CRUMB\nv=1.2\nkind=task\nsource=test\n---\n"
        "[goal]\ng\n[context]\nc\n[constraints]\nn\nEND CRUMB"
    )
    result = CrumbEngine().analyze(doc)
    assert result.provider == "mock"
    assert not result.ok
    assert any("placeholder text" in w for w in result.warnings)


def test_a_real_provider_is_not_flagged_as_a_stub():
    from crumb_llm.crumb.loader import load_crumb_text
    from crumb_llm.engine import CrumbEngine
    from crumb_llm.providers.base import BaseProvider

    class RealEnough(BaseProvider):
        name = "fake-real"

        def generate(self, prompt, max_tokens=1024, temperature=0.2):
            return "The goal is to add a limiter; the risk is worker starvation."

    doc = load_crumb_text(
        "BEGIN CRUMB\nv=1.2\nkind=task\nsource=test\n---\n"
        "[goal]\ng\n[context]\nc\n[constraints]\nn\nEND CRUMB"
    )
    result = CrumbEngine(provider=RealEnough()).analyze(doc)
    assert result.ok, result.warnings
