from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from .anchors import extract_anchors, unique_anchors
from .bundle import load_blocks, route_to_directory
from .demo import write_demo
from .models import Lane
from .router import RouterConfig


@dataclass(frozen=True)
class BenchmarkResult:
    passed: bool
    checks: dict[str, bool]
    original_chars: int
    estimated_text_tokens: int
    estimated_routed_tokens: int
    estimated_reduction_percent: float
    exact_anchors_expected: int
    exact_anchors_preserved: int

    def to_dict(self) -> dict:
        return asdict(self)


def _write_share_card(result: BenchmarkResult, path: Path) -> None:
    status = "PASS" if result.passed else "CHECK FAILED"
    status_fill = "#53f2a3" if result.passed else "#ff6b7a"
    reduction = f"{result.estimated_reduction_percent:.1f}%"
    anchors = f"{result.exact_anchors_preserved}/{result.exact_anchors_expected}"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<defs>
  <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
    <stop offset="0" stop-color="#070b13"/><stop offset="1" stop-color="#14233b"/>
  </linearGradient>
  <linearGradient id="glow" x1="0" x2="1">
    <stop offset="0" stop-color="#7c5cff"/><stop offset="1" stop-color="#27d9ff"/>
  </linearGradient>
</defs>
<rect width="1200" height="630" rx="34" fill="url(#bg)"/>
<circle cx="1070" cy="72" r="210" fill="#7c5cff" opacity=".12"/>
<circle cx="104" cy="585" r="240" fill="#27d9ff" opacity=".08"/>
<text x="72" y="92" fill="#94a3bd" font-family="Inter,Arial,sans-serif" font-size="24" letter-spacing="4">CRUMBCONTEXT BENCHMARK</text>
<text x="72" y="165" fill="#ffffff" font-family="Inter,Arial,sans-serif" font-weight="800" font-size="62">Context without the baggage.</text>
<text x="72" y="215" fill="#aab6cc" font-family="Inter,Arial,sans-serif" font-size="25">Exact facts stay exact. Stale context takes the cheaper lane.</text>
<g transform="translate(72 276)">
  <rect width="315" height="174" rx="22" fill="#101827" stroke="#29344a"/>
  <text x="28" y="46" fill="#8fa0ba" font-family="Inter,Arial,sans-serif" font-size="18">ESTIMATED REDUCTION</text>
  <text x="28" y="120" fill="url(#glow)" font-family="Inter,Arial,sans-serif" font-size="66" font-weight="800">{escape(reduction)}</text>
</g>
<g transform="translate(414 276)">
  <rect width="315" height="174" rx="22" fill="#101827" stroke="#29344a"/>
  <text x="28" y="46" fill="#8fa0ba" font-family="Inter,Arial,sans-serif" font-size="18">EXACT ANCHORS</text>
  <text x="28" y="120" fill="#ffffff" font-family="Inter,Arial,sans-serif" font-size="62" font-weight="800">{escape(anchors)}</text>
</g>
<g transform="translate(756 276)">
  <rect width="372" height="174" rx="22" fill="#101827" stroke="#29344a"/>
  <text x="28" y="46" fill="#8fa0ba" font-family="Inter,Arial,sans-serif" font-size="18">SELF-CHECK</text>
  <text x="28" y="120" fill="{status_fill}" font-family="Inter,Arial,sans-serif" font-size="58" font-weight="800">{status}</text>
</g>
<text x="72" y="526" fill="#8fa0ba" font-family="ui-monospace,Menlo,monospace" font-size="20">crumbcontext benchmark --out proof</text>
<text x="72" y="572" fill="#65738b" font-family="Inter,Arial,sans-serif" font-size="17">Planning estimates, not provider billing claims • github.com/XioAISolutions/CrumbLLM</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def run_benchmark(output_dir: Path, config: RouterConfig | None = None) -> BenchmarkResult:
    """Run the reproducible offline benchmark and verify its own artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    fixture = output_dir / "benchmark-input.json"
    write_demo(fixture)
    blocks = load_blocks(fixture)
    plan = route_to_directory(blocks, output_dir, config or RouterConfig())

    expected = {
        (anchor.kind, anchor.value)
        for block in blocks
        for anchor in unique_anchors(extract_anchors(block.content))
    }
    sidecars = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((output_dir / "crumbs").glob("*-anchors.crumb"))
    )
    preserved = {(kind, value) for kind, value in expected if value in sidecars}

    plan_by_id = {item.block_id: item for item in plan.blocks}
    authority_exact = all(
        plan_by_id[block.id].lane is Lane.EXACT
        for block in blocks
        if block.authoritative or block.role.lower() in {"system", "developer"}
    )
    recent_exact = all(
        plan_by_id[block.id].lane is Lane.EXACT
        for block in blocks
        if block.age_turns <= 2
    )
    checks = {
        "all_exact_anchors_preserved": preserved == expected,
        "authority_blocks_stay_exact": authority_exact,
        "recent_turns_stay_exact": recent_exact,
        "image_artifact_created": any((output_dir / "images").glob("*.png")),
        "routing_plan_created": (output_dir / "plan.json").is_file(),
        "interactive_report_created": (output_dir / "report.html").is_file(),
    }
    result = BenchmarkResult(
        passed=all(checks.values()),
        checks=checks,
        original_chars=plan.original_chars,
        estimated_text_tokens=plan.estimated_text_tokens,
        estimated_routed_tokens=plan.estimated_routed_tokens,
        estimated_reduction_percent=plan.reduction_percent,
        exact_anchors_expected=len(expected),
        exact_anchors_preserved=len(preserved),
    )
    (output_dir / "benchmark.json").write_text(
        json.dumps(result.to_dict(), indent=2), encoding="utf-8"
    )
    _write_share_card(result, output_dir / "share-card.svg")
    return result
