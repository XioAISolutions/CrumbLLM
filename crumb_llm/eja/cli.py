"""CLI registration and standalone entrypoint for EJA artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import (
    audit_pack,
    build_lineage,
    build_manifest,
    render_audit_html,
    render_lineage_html,
    write_html_report,
)
from .challenge import audit_challenge_pack, render_challenge_html
from .evidence import (
    audit_evidence_pack,
    build_review_bundle,
    render_evidence_html,
)
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
    if command in {
        "validate-pack",
        "summarize-pack",
        "report-pack",
        "audit-pack",
        "lineage-pack",
        "manifest-pack",
        "evidence-pack",
        "challenge-pack",
        "bundle-pack",
    }:
        verify_hash = not getattr(args, "skip_hash", False)
        if command == "audit-pack":
            report = audit_pack(args.directory, verify_hash=verify_hash)
            _write(json.dumps(report, indent=2, sort_keys=True), args.out)
            if args.html:
                write_html_report(render_audit_html(report), args.html)
            return 0 if report["audit_valid"] else 1
        if command == "lineage-pack":
            graph = build_lineage(args.directory)
            _write(json.dumps(graph, indent=2, sort_keys=True), args.out)
            if args.html:
                write_html_report(render_lineage_html(graph), args.html)
            return 0 if graph["acyclic"] else 1
        if command == "manifest-pack":
            manifest = build_manifest(args.directory, verify_hash=verify_hash)
            _write(json.dumps(manifest, indent=2, sort_keys=True), args.out)
            return 0
        if command == "evidence-pack":
            report = audit_evidence_pack(args.directory)
            _write(json.dumps(report, indent=2, sort_keys=True), args.out)
            if args.html:
                write_html_report(render_evidence_html(report), args.html)
            return 0 if report["evidence_valid"] else 1
        if command == "challenge-pack":
            report = audit_challenge_pack(args.directory)
            _write(json.dumps(report, indent=2, sort_keys=True), args.out)
            if args.html:
                write_html_report(render_challenge_html(report), args.html)
            return 0 if report["challenge_valid"] else 1
        if command == "bundle-pack":
            result = build_review_bundle(args.directory, args.out)
            _write(json.dumps(result, indent=2, sort_keys=True), args.report)
            required = (
                result["validation_valid"]
                and result["scientific_audit_valid"]
                and result["evidence_audit_valid"]
            )
            if result.get("challenge_artifact_count", 0):
                required = required and result.get("challenge_audit_valid", False)
            return 0 if required else 1

        report = validate_pack(args.directory, verify_hash=verify_hash)
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

    audit_pack_parser = commands.add_parser(
        "audit-pack",
        help="Audit evidence gates, verdict consistency, replication, and lineage",
    )
    audit_pack_parser.add_argument("directory")
    audit_pack_parser.add_argument("--skip-hash", action="store_true")
    audit_pack_parser.add_argument("--out")
    audit_pack_parser.add_argument("--html")
    audit_pack_parser.set_defaults(func=cmd_eja, eja_command="audit-pack")

    lineage_pack_parser = commands.add_parser(
        "lineage-pack", help="Build a parent-child graph for an EJA directory"
    )
    lineage_pack_parser.add_argument("directory")
    lineage_pack_parser.add_argument("--out")
    lineage_pack_parser.add_argument("--html")
    lineage_pack_parser.set_defaults(func=cmd_eja, eja_command="lineage-pack")

    manifest_pack_parser = commands.add_parser(
        "manifest-pack", help="Create a stable reproducibility manifest for an EJA pack"
    )
    manifest_pack_parser.add_argument("directory")
    manifest_pack_parser.add_argument("--skip-hash", action="store_true")
    manifest_pack_parser.add_argument("--out")
    manifest_pack_parser.set_defaults(func=cmd_eja, eja_command="manifest-pack")

    evidence_pack_parser = commands.add_parser(
        "evidence-pack",
        help="Audit evidence references and blinded-model provenance",
    )
    evidence_pack_parser.add_argument("directory")
    evidence_pack_parser.add_argument("--out")
    evidence_pack_parser.add_argument("--html")
    evidence_pack_parser.set_defaults(func=cmd_eja, eja_command="evidence-pack")

    challenge_pack_parser = commands.add_parser(
        "challenge-pack",
        help="Audit sealed commitments, abstentions, and false discoveries",
    )
    challenge_pack_parser.add_argument("directory")
    challenge_pack_parser.add_argument("--out")
    challenge_pack_parser.add_argument("--html")
    challenge_pack_parser.set_defaults(func=cmd_eja, eja_command="challenge-pack")

    bundle_pack_parser = commands.add_parser(
        "bundle-pack",
        help="Create a deterministic ZIP with artifacts, audits, lineage, and manifests",
    )
    bundle_pack_parser.add_argument("directory")
    bundle_pack_parser.add_argument("--out", required=True)
    bundle_pack_parser.add_argument("--report")
    bundle_pack_parser.set_defaults(func=cmd_eja, eja_command="bundle-pack")


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
