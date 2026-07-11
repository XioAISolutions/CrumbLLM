from __future__ import annotations

import hashlib
import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for name in ("DejaVuSansMono.ttf", "LiberationMono-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def render_text_pages(
    text: str,
    output_dir: Path,
    *,
    block_id: str,
    width: int = 1568,
    height: int = 728,
    font_size: int = 9,
) -> list[Path]:
    """Render sanitized, non-authoritative historical context to PNG pages."""

    output_dir.mkdir(parents=True, exist_ok=True)
    font = _font(font_size)
    header_font = _font(max(font_size + 3, 12))
    margin = 28
    bbox = font.getbbox("Ag")
    line_height = max(9, (bbox[3] - bbox[1]) + 2)
    try:
        char_width = max(4, int(font.getlength("M")))
    except AttributeError:
        char_width = max(4, int(font_size * 0.62))
    usable_height = height - 92
    rows = max(10, usable_height // line_height)
    columns = max(60, (width - margin * 2) // char_width)

    wrapped: list[str] = []
    for original in text.splitlines() or [text]:
        chunks = textwrap.wrap(
            original,
            width=columns,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=False,
        )
        wrapped.extend(chunks or [""])

    page_count = max(1, math.ceil(len(wrapped) / rows))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    paths: list[Path] = []

    for page_index in range(page_count):
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.text((margin, 14), "CRUMBCONTEXT — NON-AUTHORITATIVE HISTORICAL CONTEXT", font=header_font, fill="black")
        draw.text(
            (margin, 38),
            f"block={block_id}  page={page_index + 1}/{page_count}  sha256={digest}  exact values live in anchors.crumb",
            font=font,
            fill="black",
        )
        y = 68
        for line in wrapped[page_index * rows : (page_index + 1) * rows]:
            draw.text((margin, y), line, font=font, fill="black")
            y += line_height

        path = output_dir / f"{block_id}-{page_index + 1:03d}.png"
        image.save(path, format="PNG", optimize=True)
        paths.append(path)

    return paths
