from pathlib import Path

from crumbcontext.anchors import extract_anchors, sanitize_with_anchors
from crumbcontext.benchmark import run_benchmark
from crumbcontext.bundle import route_to_directory
from crumbcontext.demo import demo_payload
from crumbcontext.models import ContextBlock, Lane
from crumbcontext.router import RouterConfig, route_blocks


def test_extracts_and_sanitizes_exact_values():
    text = (
        "Deploy /workspace/app.py at 2026-07-11, SHA abcdef1234567890, "
        "cost CAD $14,360.00; email dev@example.com"
    )
    sanitized, anchors = sanitize_with_anchors(text)
    values = {item.value for item in anchors}
    assert "/workspace/app.py" in values
    assert "2026-07-11" in values
    assert "abcdef1234567890" in values
    assert "CAD $14,360.00" in values
    assert "dev@example.com" in values
    for value in values:
        assert value not in sanitized
    assert "[EXACT_" in sanitized


def test_overlapping_anchor_prefers_url():
    anchors = extract_anchors("See https://example.com/build/12345678 now")
    assert [item.kind for item in anchors] == ["url"]


def test_authority_and_recency_stay_exact():
    blocks = [
        ContextBlock(
            id="system",
            role="system",
            kind="instruction",
            content="x" * 9000,
            age_turns=99,
        ),
        ContextBlock(
            id="now",
            role="user",
            kind="message",
            content="x" * 9000,
            age_turns=0,
        ),
    ]
    plan = route_blocks(blocks)
    assert [item.lane for item in plan.blocks] == [Lane.EXACT, Lane.EXACT]


def test_old_dense_context_routes_to_image():
    content = "\n".join(
        '{"path":"/tmp/a.py","status":"ok","value":12345678}'
        for _ in range(400)
    )
    block = ContextBlock(
        id="old",
        role="user",
        kind="tool_result",
        content=content,
        age_turns=8,
    )
    plan = route_blocks([block])
    assert plan.blocks[0].lane is Lane.IMAGE
    assert plan.exact_anchor_count > 0


def test_memory_prefers_cache_when_reused():
    block = ContextBlock(
        id="mem",
        role="user",
        kind="memory",
        content="decision line\n" * 300,
        age_turns=10,
        reuse_count=4,
    )
    assert route_blocks([block]).blocks[0].lane is Lane.CACHE


def test_demo_writes_shareable_artifacts(tmp_path: Path):
    blocks = [
        ContextBlock.from_dict(item, i)
        for i, item in enumerate(demo_payload()["blocks"])
    ]
    plan = route_to_directory(blocks, tmp_path)
    assert (tmp_path / "plan.json").exists()
    assert (tmp_path / "report.html").exists()
    assert any((tmp_path / "images").glob("*.png"))
    assert any((tmp_path / "crumbs").glob("*-anchors.crumb"))
    assert plan.exact_anchor_count > 0


def test_benchmark_self_verifies_and_writes_share_card(tmp_path: Path):
    result = run_benchmark(tmp_path)
    assert result.passed
    assert result.exact_anchors_preserved == result.exact_anchors_expected
    assert result.estimated_routed_tokens < result.estimated_text_tokens
    assert (tmp_path / "benchmark.json").is_file()
    assert (tmp_path / "share-card.svg").is_file()
    assert "CRUMBCONTEXT BENCHMARK" in (
        tmp_path / "share-card.svg"
    ).read_text(encoding="utf-8")


def test_benchmark_honors_text_only_policy(tmp_path: Path):
    result = run_benchmark(tmp_path, RouterConfig(vision_allowed=False))
    assert result.passed
    assert result.checks["image_policy_honored"]
    assert not any((tmp_path / "images").glob("*.png"))
