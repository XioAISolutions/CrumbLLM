from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .bundle import load_blocks, route_to_directory
from .demo import write_demo
from .router import RouterConfig, route_blocks


def _config(args) -> RouterConfig:
    return RouterConfig(
        vision_allowed=not getattr(args, "no_images", False),
        recent_turns=getattr(args, "recent_turns", 2),
    )


def cmd_analyze(args) -> int:
    blocks = load_blocks(Path(args.input))
    plan = route_blocks(blocks, _config(args))
    print(json.dumps(plan.to_dict(), indent=2))
    return 0


def cmd_route(args) -> int:
    blocks = load_blocks(Path(args.input))
    out = Path(args.out)
    plan = route_to_directory(blocks, out, _config(args))
    print(f"Routed {len(blocks)} blocks to {out}")
    print(f"Estimated tokens: {plan.estimated_text_tokens:,} -> {plan.estimated_routed_tokens:,} ({plan.reduction_percent}% reduction)")
    print(f"Protected exact anchors: {plan.exact_anchor_count}")
    print(f"Open {out / 'report.html'}")
    return 0


def cmd_demo(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fixture = out / "demo-input.json"
    write_demo(fixture)
    blocks = load_blocks(fixture)
    plan = route_to_directory(blocks, out, _config(args))
    print(f"Demo created at {out / 'report.html'}")
    print(json.dumps(plan.to_dict()["totals"], indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crumbcontext",
        description="Protect exact facts, route stale AI context, and produce measurable context bundles.",
    )
    parser.add_argument("--version", action="version", version=f"crumbcontext {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Print a routing plan for a JSON transcript")
    analyze.add_argument("input")
    analyze.add_argument("--no-images", action="store_true")
    analyze.add_argument("--recent-turns", type=int, default=2)
    analyze.set_defaults(func=cmd_analyze)

    route = sub.add_parser("route", help="Write images, CRUMBs, summaries, exact anchors, and an HTML report")
    route.add_argument("input")
    route.add_argument("--out", default="crumbcontext-output")
    route.add_argument("--no-images", action="store_true")
    route.add_argument("--recent-turns", type=int, default=2)
    route.set_defaults(func=cmd_route)

    demo = sub.add_parser("demo", help="Generate a screenshot-ready benchmark demo")
    demo.add_argument("--out", default="crumbcontext-demo")
    demo.add_argument("--no-images", action="store_true")
    demo.add_argument("--recent-turns", type=int, default=2)
    demo.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
