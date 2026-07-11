from __future__ import annotations

import html
from pathlib import Path

from .models import RoutePlan


def write_report(plan: RoutePlan, path: Path) -> None:
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(block.block_id)}</td>"
        f"<td><span class='lane'>{html.escape(block.lane.value)}</span></td>"
        f"<td>{block.estimated_text_tokens:,}</td>"
        f"<td>{block.estimated_routed_tokens:,}</td>"
        f"<td>{block.anchor_count}</td>"
        f"<td>{html.escape(block.reason)}</td>"
        "</tr>"
        for block in plan.blocks
    )
    document = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>CrumbContext routing report</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{ margin:0; background:#080b12; color:#f6f7fb; }}
main {{ max-width:1120px; margin:auto; padding:64px 24px; }}
h1 {{ font-size:52px; margin:0 0 8px; letter-spacing:-.04em; }}
.sub {{ color:#aab1c5; font-size:20px; margin-bottom:36px; }}
.grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }}
.card {{ background:#111723; border:1px solid #273044; border-radius:18px; padding:20px; }}
.label {{ color:#929bb1; font-size:13px; text-transform:uppercase; letter-spacing:.08em; }}
.value {{ font-size:32px; font-weight:750; margin-top:8px; }}
table {{ width:100%; border-collapse:collapse; margin-top:28px; background:#0e1420; border-radius:18px; overflow:hidden; }}
th,td {{ padding:14px; text-align:left; border-bottom:1px solid #222c3f; vertical-align:top; }}
th {{ color:#9ea7bb; font-size:12px; text-transform:uppercase; }}
.lane {{ border:1px solid #53627e; padding:4px 8px; border-radius:999px; font-size:12px; }}
.note {{ color:#8e98ad; margin-top:24px; line-height:1.6; }}
@media(max-width:800px) {{ .grid {{ grid-template-columns:1fr 1fr; }} h1 {{ font-size:40px; }} }}
</style>
</head>
<body><main>
<h1>CrumbContext</h1>
<div class='sub'>Give every AI the context it needs—not the entire conversation.</div>
<section class='grid'>
<div class='card'><div class='label'>Original estimate</div><div class='value'>{plan.estimated_text_tokens:,}</div></div>
<div class='card'><div class='label'>Routed estimate</div><div class='value'>{plan.estimated_routed_tokens:,}</div></div>
<div class='card'><div class='label'>Estimated reduction</div><div class='value'>{plan.reduction_percent}%</div></div>
<div class='card'><div class='label'>Exact anchors protected</div><div class='value'>{plan.exact_anchor_count}</div></div>
</section>
<table><thead><tr><th>Block</th><th>Lane</th><th>Text</th><th>Routed</th><th>Anchors</th><th>Reason</th></tr></thead><tbody>{rows}</tbody></table>
<p class='note'>Token figures are deterministic estimates, not provider billing records. Exact anchors are preserved as native text. Image artifacts are explicitly non-authoritative historical context.</p>
</main></body></html>"""
    path.write_text(document, encoding="utf-8")
