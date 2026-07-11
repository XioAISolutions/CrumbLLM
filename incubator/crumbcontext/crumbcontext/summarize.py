from __future__ import annotations

import re

_IMPORTANT = re.compile(
    r"\b(decision|decided|must|never|require|constraint|warning|error|failed|risk|todo|next|approved|blocked|deadline|because)\b",
    re.IGNORECASE,
)


def extractive_summary(text: str, max_chars: int = 1800) -> str:
    """Produce a deterministic, dependency-free summary for stale context."""

    normalized = [line.strip() for line in text.splitlines() if line.strip()]
    if not normalized:
        return ""
    if len(text) <= max_chars:
        return text.strip()

    selected: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        compact = " ".join(line.split())
        if compact and compact not in seen:
            selected.append(compact)
            seen.add(compact)

    for line in normalized[:4]:
        add(line)
    for line in normalized:
        if _IMPORTANT.search(line):
            add(line)
    for line in normalized[-4:]:
        add(line)

    output: list[str] = []
    size = 0
    for line in selected:
        addition = len(line) + 2
        if output and size + addition > max_chars:
            break
        output.append(f"- {line}")
        size += addition
    return "\n".join(output)
