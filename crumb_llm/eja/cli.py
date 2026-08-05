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
from .pack import summarize_pack, validate_pack, write_pack_report


def _write(value: str, out: str | None) -> None:
    if out:
        destination = Path(out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            value + ("" if value.endswith("\n") else "\n"), encoding="utf-8"
        )
    else:
        print(value)


def cmd_eja(args: argparse.Namespace) -> int:
    command = args.eja_command
    if command in {"validate-pack", "summarize-pack", "report-pack"}:
        report = validate_pack(args.directory, verify_hash=not getattr(args, "skip_hash", False))
        if command == "validate-pack":
            _write(json.dumps(report, indent=2, sort_keys=True), args.out)
            if args.html:
                write_pack_report(report, args.html)
            return 0 if report["invalid_count"] == 0 and report["artifact_count"] > 0 else 1
        if command == "summarize-pack":
            _write(summarize_pack(report), args.out)
            return 0
        write_pack_report(report, args.out)
        return 0

    artifact = load_artifact(args.artifact)
    if command == "validate":
        report = validate_artifact(artifact, verify_hash=not args.skip_hash)
        _write(json.dumps(report.to_dict(), indent=2, sort_keys=True), args.out)
        return 0 if report.valid else 1
    if command == "summarize":
        _write(summarize_artifact(artifact), args.out)
        return 0
    if command == "hash":
        _write(artifact_hash(artifact), args.out)
        return 0
    if command == "replay-plan":
        _write(json.dumps(replay_plan(artifact), indent=2, sort_keys=True), args.out)
        return 0
    if command == "compare":
        other = load_artifact(args.other)
        _write(
            json.dumps(compare_artifacts(artifact, other), indent=2, sort_keys=True),
            args.out,
        )
        return 0
    raise ValueError(f"unknown EJA command: {command}")


def _add_commands(commands: argparse._SubParsersAction) -> None:
    validate = commands.add_parser("validate", help="Validate an EJA experiment artifact")
    validate.add_argument("artifact")
    validate.add_argument("--skip-hash", action="store_true")
    validate.add_argument("--out")
    validate.set_defaults(func=cmd_eja, eja_command="validate")

    summarize = commands.add_parser("summarize", help="Summarize an EJA artifact")
    summarize.add_argument("artifact")
    summarize.add_argument("--out")
    summarize.set_defaults(func=cmd_eja, eja_command="summarize")

    digest = commands.add_parser("hash", help="Compute a canonical EJA artifact hash")
    digest.add_argument("artifact")
    digest.add_argument("--out")
    digest.set_defaults(func=cmd_eja, eja_command="hash")

    replay = commands.add_parser("replay-plan", help="Emit ordered interventions for a replayer")
    replay.add_argument("artifact")
    replay.add_argument("--out")
    replay.set_defaults(func=cmd_eja, eja_command="replay-plan")

    compare = commands.add_parser("compare", help="Compare two EJA artifacts")
    compare.add_argument("artifact")
    compare.add_argument("other")
    compare.add_argument("--out")
    compare.set_defaults(func=cmd_eja, eja_command="compare")

    validate_pack_parser = commands.add_parser(
        "validate-pack", help="Validate every EJA artifact under a directory"
    )
    validate_pack_parser.add_argument("directory")
    validate_pack_parser.add_argument("--skip-hash", action="store_true")
    validate_pack_parser.add_argument("--out")
    validate_pack_parser.add_argument("--html")
    validate_pack_parser.set_defaults(func=cmd_eja, eja_command="validate-pack")

    summarize_pack_parser = commands.add_parser(
        "summarize-pack", help="Summarize a directory of EJA artifacts"
    )
    summarize_pack_parser.add_argument("directory")
    summarize_pack_parser.add_argument("--skip-hash", action="store_true")
    summarize_pack_parser.add_argument("--out")
    summarize_pack_parser.set_defaults(func=cmd_eja, eja_command="summarize-pack")

    report_pack_parser = commands.add_parser(
        "report-pack", help="Render a standalone HTML report for an EJA directory"
    )
    report_pack_parser.add_argument("directory")
    report_pack_parser.add_argument("--skip-hash", action="store_true")
    report_pack_parser.add_argument("--out", required=True)
    report_pack_parser.set_defaults(func=cmd_eja, eja_command="report-pack")


def register_eja_subparser(subparsers: argparse._SubParsersAction) -> None:
    root = subparsers.add_parser(
        "eja", help="Validate and inspect E-J-A discovery artifacts"
    )
    commands = root.add_subparsers(dest="eja_command", required=True)
    _add_commands(commands)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m crumb_llm.eja")
    commands = parser.add_subparsers(dest="eja_command", required=True)
    _add_commands(commands)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
