"""Run the handoff retention measurement and print a table.

    python research/handoff_benchmark/run.py
    python research/handoff_benchmark/run.py --budget 150 --out results.json

Measures fact retention under a token budget — a proxy for the question the
project actually cares about. See `retention.py` and `protocol.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.handoff_benchmark.retention import run_task  # noqa: E402

TASKS_DIR = Path(__file__).resolve().parent / "tasks"


def render(result: dict) -> str:
    lines = [
        f"task            {result['task']} — {result['goal']}",
        f"budget          {result['budget_tokens']} tokens "
        f"(transcript is {result['transcript_tokens']})",
        f"critical facts  {result['critical_facts']}, declared before the handoffs were written",
        "",
        f"  {'strategy':<10} {'tokens':>7} {'retained':>10} {'retention':>10} {'facts/100tok':>13}",
        f"  {'-' * 10} {'-' * 7} {'-' * 10} {'-' * 10} {'-' * 13}",
    ]
    for s in result["strategies"]:
        flag = " !over budget" if s["over_budget"] else ""
        lines.append(
            f"  {s['strategy']:<10} {s['tokens']:>7} "
            f"{str(s['retained']) + '/' + str(s['total']):>10} "
            f"{s['retention']:>10.3f} {s['facts_per_100_tokens']:>13.2f}{flag}"
        )
    lines.append("")
    for s in result["strategies"]:
        if s["missing"]:
            lost = ", ".join(m["id"] for m in s["missing"])
            lines.append(f"  {s['strategy']} lost: {lost}")
    lines.append("")
    lines.append(f"  measures: {result['measures']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--budget",
        type=int,
        default=200,
        help="Token budget the transcript tail is truncated to (default 200)",
    )
    parser.add_argument("--task", help="Run one task directory instead of all")
    parser.add_argument("--out", help="Write results as JSON")
    args = parser.parse_args()

    task_dirs = (
        [Path(args.task)]
        if args.task
        else sorted(d for d in TASKS_DIR.iterdir() if (d / "task.json").exists())
    )
    if not task_dirs:
        print(f"no tasks found under {TASKS_DIR}", file=sys.stderr)
        return 1

    results = [run_task(d, args.budget) for d in task_dirs]
    for result in results:
        print(render(result))
        print()

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
