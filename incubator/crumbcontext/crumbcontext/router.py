from __future__ import annotations

import math
from dataclasses import dataclass

from .anchors import extract_anchors, unique_anchors
from .models import ContextBlock, Lane, RoutePlan, RoutedBlock


@dataclass(frozen=True)
class RouterConfig:
    recent_turns: int = 2
    minimum_compress_chars: int = 1800
    image_min_chars: int = 6000
    cache_reuse_threshold: int = 3
    summary_ratio: float = 0.22
    crumb_ratio: float = 0.30
    cache_equivalent_ratio: float = 0.10
    image_width: int = 1568
    image_height: int = 728
    image_page_chars: int = 15000
    vision_allowed: bool = True


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    punctuation = sum(1 for char in text if char in "{}[]():,;=<>/\\")
    density_bonus = min(0.8, punctuation / max(1, len(text)) * 12)
    chars_per_token = max(2.2, 4.0 - density_bonus)
    return max(1, math.ceil(len(text) / chars_per_token))


def _image_tokens(chars: int, config: RouterConfig) -> int:
    pages = max(1, math.ceil(chars / config.image_page_chars))
    per_page = math.ceil(config.image_width / 28) * math.ceil(config.image_height / 28)
    return pages * per_page


def _is_dense(text: str) -> bool:
    if not text:
        return False
    lines = text.splitlines() or [text]
    structured = sum(
        1
        for line in lines
        if any(token in line for token in ("{", "}", "[", "]", "=", ":", "->", "::", "|"))
    )
    avg_line = sum(len(line) for line in lines) / max(1, len(lines))
    return structured / max(1, len(lines)) >= 0.28 or avg_line >= 90


def _decision(block: ContextBlock, config: RouterConfig) -> tuple[Lane, str]:
    role = block.role.lower()
    kind = block.kind.lower()

    if block.authoritative or role in {"system", "developer"}:
        return Lane.EXACT, "authority boundary: system/developer/explicitly authoritative context stays native text"
    if block.age_turns <= config.recent_turns:
        return Lane.EXACT, "recency boundary: current and recent turns stay native text"
    if kind in {"tool_schema", "policy", "instruction", "approval", "citation"}:
        return Lane.EXACT, f"exactness boundary: {kind} blocks are not transformed"
    if len(block.content) < config.minimum_compress_chars:
        return Lane.EXACT, "too small to transform profitably"
    if block.reuse_count >= config.cache_reuse_threshold and kind in {"reference", "docs", "memory", "system_reference"}:
        return Lane.CACHE, "stable context is reused often enough to prefer provider caching"
    if kind in {"crumb", "memory", "handoff", "project_map"}:
        return Lane.CRUMB, "structured project memory is folded into a CRUMB summary/full representation"
    if config.vision_allowed and len(block.content) >= config.image_min_chars and _is_dense(block.content):
        return Lane.IMAGE, "old token-dense context is eligible for a sanitized image plus exact-value sidecar"
    return Lane.SUMMARY, "old semantic context is reduced with deterministic extractive summarization"


def route_blocks(blocks: list[ContextBlock], config: RouterConfig | None = None) -> RoutePlan:
    config = config or RouterConfig()
    routed: list[RoutedBlock] = []
    original_chars = 0
    text_tokens_total = 0
    routed_tokens_total = 0
    all_anchor_keys: set[tuple[str, str]] = set()

    for block in blocks:
        original_chars += len(block.content)
        text_tokens = estimate_text_tokens(block.content)
        text_tokens_total += text_tokens
        anchors = unique_anchors(extract_anchors(block.content))
        all_anchor_keys.update((anchor.kind, anchor.value) for anchor in anchors)
        lane, reason = _decision(block, config)

        if lane is Lane.EXACT:
            routed_tokens = text_tokens
        elif lane is Lane.CACHE:
            routed_tokens = max(1, math.ceil(text_tokens * config.cache_equivalent_ratio))
        elif lane is Lane.CRUMB:
            routed_tokens = max(1, math.ceil(text_tokens * config.crumb_ratio)) + estimate_text_tokens(" ".join(a.value for a in anchors))
        elif lane is Lane.IMAGE:
            sanitized_chars = max(0, len(block.content) - sum(len(a.value) for a in anchors))
            routed_tokens = _image_tokens(sanitized_chars, config) + estimate_text_tokens(" ".join(a.value for a in anchors))
        elif lane is Lane.SUMMARY:
            routed_tokens = max(1, math.ceil(text_tokens * config.summary_ratio)) + estimate_text_tokens(" ".join(a.value for a in anchors))
        else:
            routed_tokens = 0

        routed_tokens_total += routed_tokens
        routed.append(
            RoutedBlock(
                block_id=block.id,
                lane=lane,
                reason=reason,
                original_chars=len(block.content),
                estimated_text_tokens=text_tokens,
                estimated_routed_tokens=routed_tokens,
                anchor_count=len(anchors),
            )
        )

    return RoutePlan(
        blocks=routed,
        original_chars=original_chars,
        estimated_text_tokens=text_tokens_total,
        estimated_routed_tokens=routed_tokens_total,
        exact_anchor_count=len(all_anchor_keys),
    )
