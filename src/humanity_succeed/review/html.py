"""Static HTML rendering for a blind review packet (BUILD_SPEC §11; DECISIONS B60/B61).

One self-contained page: every string is ``html.escape``d, no ``<script>``, no external URL, no
network dependency -- it reuses ``evidence.replay._CSS`` so the review artifact and the replay
report share one visual language. Renders only what ``PacketManifest`` already carries; it never
reads ``evaluation.json`` or anything else outside the manifest.
"""

from __future__ import annotations

import html
import json
from typing import Any

from ..evidence.replay import _CSS
from .contract import (
    HTML_BANNER_V2_LEAD,
    HTML_BANNER_V2_REST,
    PACKET_SCHEMA_V2,
    PacketManifest,
    PacketManifestV2,
)

# Packet/1 banner, byte-identical to the stage-0 freeze (tests/golden/test_review_v1_text_freeze.py).
_BANNER_V1 = ("<div class='banner'><b>Blind, static, offline.</b> No condition, adapter, or "
              "evaluator verdict is present anywhere in this page.</div>")
# Packet/2 banner (review/contract.py): the same div, lead in <b>, then the rest.
_BANNER_V2 = "<div class='banner'><b>" + HTML_BANNER_V2_LEAD + "</b>" + HTML_BANNER_V2_REST + "</div>"


def _e(x: Any) -> str:
    return html.escape(str(x), quote=True)


def _pre_json(x: Any) -> str:
    return _e(json.dumps(x, indent=1, ensure_ascii=False, sort_keys=True))


def render_packet_html(manifest: PacketManifest | PacketManifestV2) -> str:
    """One static page for the whole packet, in the manifest's item order. The banner is chosen
    by ``schema_id``; everything else is shared, so packet/1 output is unchanged."""
    banner = _BANNER_V2 if manifest.schema_id == PACKET_SCHEMA_V2 else _BANNER_V1
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Blind review packet</title><style>{_CSS}</style></head><body><main>",
        "<h1>Blind review packet</h1>",
        banner,
        f"<div class='card'>{_e(manifest.claim_boundary)}</div>",
        f"<div class='card'>{_e(manifest.instructions)}</div>",
    ]
    for n, item in enumerate(manifest.items, start=1):
        parts.append(f"<h2 id='{_e(item.item_id)}'>Item {n} of {len(manifest.items)}</h2>")
        parts.append(f"<div class='card'><b>Task</b><pre>{_e(item.task)}</pre></div>")
        if item.visible_resources:
            parts.append(
                "<div class='card'><b>Resources visible to the subject (initial values)</b>"
                f"<pre>{_pre_json(item.visible_resources)}</pre></div>"
            )
        parts.append(
            "<div class='card scroll'><b>Recorded sequence</b>"
            "<table><tr><th>turn</th><th>proposed</th><th>message</th><th>what happened</th></tr>"
        )
        for step in item.steps:
            msg_html = _e(step.message) if step.message is not None else "<span class='mut'>none</span>"
            parts.append(
                f"<tr><td>{step.turn}</td><td><pre>{_pre_json(step.proposed)}</pre></td>"
                f"<td>{msg_html}</td><td>{_e(step.outcome)}</td></tr>"
            )
        parts.append("</table></div>")
        rubric_html = "".join(
            f"<li><b>{_e(line.dimension)}</b>: {_e(line.instruction)}</li>" for line in item.rubric
        )
        parts.append(
            f"<div class='card'><b>Rubric</b><ul>{rubric_html}</ul>"
            f"<p>{_e(item.question)}</p>"
            f"<p class='mut'>Allowed verdicts: {_e(', '.join(item.allowed_verdicts))}</p>"
            f"<p class='mut'>Item id: {_e(item.item_id)} &middot; source hash: "
            f"{_e(item.source_sha256)}</p></div>"
        )
    parts.append("</main></body></html>")
    return "".join(parts)


__all__ = ["render_packet_html"]
