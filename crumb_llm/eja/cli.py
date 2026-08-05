"""CLI registration and standalone entrypoint for EJA artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import (
    artifact_hash,
    compare_artifacts,
    load_artifact,
    replay_plan,
    summarize_artifact,
    validate_artifact,
)


def _write(value: str, out: str | None) -> None:
    if out:
        Path(out).write_text(value + ("" if value.endswith("\n") else "\n"), encoding="utf-8")
    else:
        print(value)


def cmd_eja(args: argparse.Namespace) -> int:
    artifact = load_artifact(args.artifact)
    if args.eja_command == "validate":
        report = validate_artifact(artifact, verify_hash=not args.skip_hash)
        _write(json.dumps(report.to_dict(), indent=2, sort_keys=True), args.out)
        return 0 if report.valid else 1
    if args.eja_command == "summarize":
        _write(summarize_artifact(artifact), args.out)
        return 0
    if args.eja_command == "hash":
        _write(artifact_hash(artifact), args.out)
        return 0
    if args.eja_command == "replay-plan":
        _write(json.dumps(replay_plan(artifact), indent=2, sort_keys=True), args.out)
        return 0
    if args.eja_command == "compare":
        other = load_artifact(args.other)
        _write(json.dumps(compare_artifacts(artifact, other), indent=2, sort_keys=True), args.out)
        return 0
    raise ValueError(f"unknown EJA command: {args.eja_command}")


def register_eja_subparser(subparsers: argparse._SubParsersAction) -> None:
    root = subparsers.add_parser("eja", help="Validate and inspect E-J-A discovery artifacts")
    commands = root.add_subparsers(dest="eja_command", required=True)

    validate = commands.add_parser("validate", help="Validate an EJA experiment artifact")
    validate.add_argument("artifact")
    validate.add_argument("--skip-hash", action="store_true")
    validate.add_argument("--out")
    validate.set_defaults(func=cmd_eja)

    summarize = commands.add_parser("summarize", help="Summarize an EJA artifact")
    summarize.add_argument("artifact")
    summarize.add_argument("--out")
    summarize.set_defaults(func=cmd_eja)

    digest = commands.add_parser("hash", help="Compute a canonical EJA artifact hash")
    digest.add_argument("artifact")
    digest.add_argument("--out")
    digest.set_defaults(func=cmd_eja)

    replay = commands.add_parser("replay-plan", help="Emit ordered interventions for a replayer")
    replay.add_argument("artifact")
    replay.add_argument("--out")
    replay.set_defaults(func=cmd_eja)

    compare = commands.add_parser("compare", help="Compare two EJA artifacts")
    compare.add_argument("artifact")
    compare.add_argument("other")
    compare.add_argument("--out")
    compare.set_defaults(func=cmd_eja)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m crumb_llm.eja")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("artifact")
    validate.add_argument("--skip-hash", action="store_true")
    validate.add_argument("--out")
    validate.set_defaults(func=cmd_eja, eja_command="validate")

    summarize = sub.add_parser("summarize")
    summarize.add_argument("artifact")
    summarize.add_argument("--out")
    summarize.set_defaults(func=cmd_eja, eja_command="summarize")

    digest = sub.add_parser("hash")
    digest.add_argument("artifact")
    digest.add_argument("--out")
    digest.set_defaults(func=cmd_eja, eja_command="hash")

    replay = sub.add_parser("replay-plan")
    replay.add_argument("artifact")
    replay.add_argument("--out")
    replay.set_defaults(func=cmd_eja, eja_command="replay-plan")

    compare = sub.add_parser("compare")
    compare.add_argument("artifact")
    compare.add_argument("other")
    compare.add_argument("--out")
    compare.set_defaults(func=cmd_eja, eja_command="compare")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
