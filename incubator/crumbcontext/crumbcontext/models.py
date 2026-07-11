from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Lane(str, Enum):
    EXACT = "exact"
    CACHE = "cache"
    CRUMB = "crumb"
    IMAGE = "image"
    SUMMARY = "summary"
    DROP = "drop"


@dataclass(frozen=True)
class Anchor:
    kind: str
    value: str
    start: int
    end: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextBlock:
    id: str
    role: str
    kind: str
    content: str
    age_turns: int = 0
    reuse_count: int = 0
    authoritative: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any], index: int = 0) -> "ContextBlock":
        return cls(
            id=str(value.get("id") or f"block-{index}"),
            role=str(value.get("role") or "user"),
            kind=str(value.get("kind") or "message"),
            content=str(value.get("content") or ""),
            age_turns=max(0, int(value.get("age_turns") or 0)),
            reuse_count=max(0, int(value.get("reuse_count") or 0)),
            authoritative=bool(value.get("authoritative", False)),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class RoutedBlock:
    block_id: str
    lane: Lane
    reason: str
    original_chars: int
    estimated_text_tokens: int
    estimated_routed_tokens: int
    anchor_count: int = 0
    artifact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lane"] = self.lane.value
        return data


@dataclass
class RoutePlan:
    blocks: list[RoutedBlock]
    original_chars: int
    estimated_text_tokens: int
    estimated_routed_tokens: int
    exact_anchor_count: int

    @property
    def reduction_percent(self) -> float:
        if self.estimated_text_tokens <= 0:
            return 0.0
        reduction = 1 - (self.estimated_routed_tokens / self.estimated_text_tokens)
        return round(max(0.0, reduction) * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocks": [block.to_dict() for block in self.blocks],
            "totals": {
                "original_chars": self.original_chars,
                "estimated_text_tokens": self.estimated_text_tokens,
                "estimated_routed_tokens": self.estimated_routed_tokens,
                "estimated_reduction_percent": self.reduction_percent,
                "exact_anchor_count": self.exact_anchor_count,
            },
            "disclaimer": (
                "Token figures are deterministic estimates for comparison, not provider billing records. "
                "Run a provider-specific counterfactual before publishing savings claims."
            ),
        }
