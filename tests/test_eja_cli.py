from pathlib import Path

from crumb_llm.cli import main

EXAMPLE = Path(__file__).parents[1] / "examples" / "einstein-elevator.eja.json"


def test_root_cli_registers_eja_validate(capsys):
    assert main(["eja", "validate", str(EXAMPLE)]) == 0
    assert '"valid": true' in capsys.readouterr().out


def test_root_cli_eja_summary(capsys):
    assert main(["eja", "summarize", str(EXAMPLE)]) == 0
    assert "supported_within_scope" in capsys.readouterr().out
