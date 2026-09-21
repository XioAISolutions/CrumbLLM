"""Measure what `crumblm score` costs. Reproduces the number in the README.

    python research/bench_score.py

Nothing here is imported by the package. It exists so the latency claim in the
README is a measurement anyone can repeat rather than a number someone typed.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from crumb_llm.crumb.loader import load_crumb  # noqa: E402
from crumb_llm.crumb.pack_reader import read_pack  # noqa: E402
from crumb_llm.score import score_doc, score_pack  # noqa: E402


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _time(fn, iterations: int) -> dict[str, float]:
    fn()  # warm the import and any lru_cache
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return {
        "iterations": iterations,
        "p50_ms": round(statistics.median(samples), 4),
        "mean_ms": round(statistics.mean(samples), 4),
        "p95_ms": round(_percentile(samples, 0.95), 4),
        "max_ms": round(max(samples), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--out", help="Write the results as JSON")
    args = parser.parse_args()

    examples = REPO_ROOT / "examples"
    doc = load_crumb(examples / "basic.crumb")
    pack = read_pack(examples / "pack")

    results = {
        "machine": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
        },
        "score_doc (parsed already)": _time(lambda: score_doc(doc), args.iterations),
        "load + score_doc (what the CLI pays)": _time(
            lambda: score_doc(load_crumb(examples / "basic.crumb")),
            max(1, args.iterations // 5),
        ),
        "score_pack, 2 documents": _time(lambda: score_pack(pack), args.iterations),
    }

    for name, stats in results.items():
        if name == "machine":
            continue
        print(f"{name:40s} p50 {stats['p50_ms']:8.3f} ms   p95 {stats['p95_ms']:8.3f} ms")

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
