from __future__ import annotations

import json
from pathlib import Path
import shutil

from crumb_llm.eja import render_pack_html, summarize_pack, validate_pack
from crumb_llm.eja.cli import build_parser

EXAMPLE = Path(__file__).parents[1] / "examples" / "einstein-elevator.eja.json"


def _pack(tmp_path: Path) -> Path:
    root = tmp_path / "pack"
    root.mkdir()
    shutil.copy(EXAMPLE, root / "run-a.json")
    shutil.copy(EXAMPLE, root / "run-b.json")
    (root / "not-an-artifact.json").write_text(json.dumps({"kind": "other"}))
    return root


def test_validate_pack_aggregates_only_eja_artifacts(tmp_path):
    report = validate_pack(_pack(tmp_path))
    assert report["artifact_count"] == 2
    assert report["valid_count"] == 2
    assert report["invalid_count"] == 0
    assert report["valid_rate"] == 1.0
    assert report["pack_hash"].startswith("sha256:")


def test_pack_hash_is_deterministic(tmp_path):
    root = _pack(tmp_path)
    assert validate_pack(root)["pack_hash"] == validate_pack(root)["pack_hash"]


def test_pack_summary_and_html_preserve_scope_warning(tmp_path):
    report = validate_pack(_pack(tmp_path))
    summary = summarize_pack(report)
    html = render_pack_html(report)
    assert "EJA artifacts: 2" in summary
    assert "CRUMB EJA Pack Report" in html
    assert "does not prove" in html


def test_standalone_cli_registers_pack_commands():
    parser = build_parser()
    args = parser.parse_args(["validate-pack", "examples", "--skip-hash"])
    assert args.eja_command == "validate-pack"
    args = parser.parse_args(["report-pack", "examples", "--out", "report.html"])
    assert args.eja_command == "report-pack"
