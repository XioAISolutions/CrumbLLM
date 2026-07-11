from __future__ import annotations

import json
from pathlib import Path


def demo_payload() -> dict:
    dense_rows = []
    for i in range(420):
        dense_rows.append(
            '{"event":"tool_result","path":"/workspace/src/module_%03d.py","status":"ok","duration_ms":%d,"trace":"%012x"}'
            % (i % 12, 20 + (i % 80), 0xABCDEF120000 + (i % 16))
        )
    old_log = "\n".join(dense_rows) + "\nDeployment target: https://example.com/build/12345678\nTotal: CAD $14,360.00"
    return {
        "blocks": [
            {
                "id": "system",
                "role": "system",
                "kind": "instruction",
                "content": "You are a coding agent. Never modify production without approval.",
                "age_turns": 50,
                "authoritative": True,
            },
            {
                "id": "project-memory",
                "role": "user",
                "kind": "memory",
                "content": ("Decision: preserve the public API.\nConstraint: never rename the CLI.\n" * 180),
                "age_turns": 18,
                "reuse_count": 5,
            },
            {
                "id": "old-tool-output",
                "role": "user",
                "kind": "tool_result",
                "content": old_log,
                "age_turns": 12,
            },
            {
                "id": "current-request",
                "role": "user",
                "kind": "message",
                "content": "Fix the failing test, preserve SHA abcdef1234567890, and do not deploy.",
                "age_turns": 0,
            },
        ]
    }


def write_demo(path: Path) -> None:
    path.write_text(json.dumps(demo_payload(), indent=2), encoding="utf-8")
