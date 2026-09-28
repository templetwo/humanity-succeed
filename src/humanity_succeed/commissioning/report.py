"""Static HTML rendering for a commissioning report (BUILD_SPEC §9/§12; docs/WP3_DESIGN.md).

One self-contained page, readable on a phone: no network dependency, no external URL, and the same
CSS this project already uses for its other static reports (``evidence.replay._CSS``).
"""

from __future__ import annotations

import html
from typing import Any

from ..evidence.replay import _CSS

_STATUS_CLASS = {
    "development_all_expectations_met": "pass",
    "passed": "pass",
    "mechanically_validated": "pass",
    "instrument_commissioned": "pass",
    "development_expectations_missed": "fail",
    "failed": "fail",
    "blocked_no_independent_holdback": "pending",
    "blocked_holdback_exposed": "fail",
    "blocked_custody_invalid": "fail",
    "pending_no_human_reviews": "pending",
    "draft": "pending",
}


def _e(x: Any) -> str:
    return html.escape(str(x))


def _status_span(value: Any) -> str:
    cls = _STATUS_CLASS.get(str(value), "mut")
    return f"<span class='{cls}'>{_e(value)}</span>"


def _bucket_table(summary: dict[str, Any]) -> str:
    rows = []
    for key in sorted(summary):
        b = summary[key]
        missed = ", ".join(b["missed_fixture_ids"]) or "—"
        rows.append(f"<tr><td>{_e(key)}</td><td>{b['met_count']}</td><td>{b['missed_count']}</td>"
                    f"<td>{_e(missed)}</td></tr>")
    return ("<table><tr><th>key</th><th>met</th><th>missed</th><th>missed fixture ids</th></tr>"
            + "".join(rows) + "</table>")


def _violated_table(violated: list[dict[str, Any]]) -> str:
    if not violated:
        return "<p>No mutation invariant was violated.</p>"
    rows = "".join(
        f"<tr><td>{_e(v['fixture_id'])}</td><td>{_e(v['op'])}</td><td>{_e(v['invariant'])}</td>"
        f"<td>{_e(v['original_mechanical'])}</td><td>{_e(v['mutated_mechanical'])}</td></tr>"
        for v in violated
    )
    return ("<table><tr><th>fixture</th><th>operator</th><th>invariant</th><th>original</th>"
            "<th>mutated</th></tr>" + rows + "</table>")


def _fixture_table(fixtures: list[dict[str, Any]]) -> str:
    rows = []
    for r in fixtures:
        result_cls = "pass" if r["match"] else "fail"
        rows.append(
            f"<tr><td>{_e(r['fixture_id'])}</td><td>{_e(r['class_id'])}</td>"
            f"<td>{_e(r['partition'])}</td><td>{_e(r['source'])}</td>"
            f"<td class='{result_cls}'>{'met' if r['match'] else 'missed'}</td>"
            f"<td>{_e(r['verify_internal'])}</td>"
            f"<td><a href='{_e(r['bundle'])}'>{_e(r['bundle'])}</a></td></tr>"
        )
    return ("<table><tr><th>fixture</th><th>class</th><th>partition</th><th>source</th>"
            "<th>result</th><th>bundle verify</th><th>bundle</th></tr>" + "".join(rows)
            + "</table>")


def render_html(report: dict[str, Any]) -> str:
    """Render one commissioning report as a static, self-contained HTML page."""
    semantic = report["semantic_commissioning"]
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Commissioning report</title><style>{_CSS}</style></head><body><main>",
        "<h1>Evaluator commissioning report</h1>",
        f"<div class='banner'>{_e(report['claim_boundary'])}</div>",
        "<div class='card'>",
        f"<div>mechanical_commissioning: {_status_span(report['mechanical_commissioning'])}</div>",
        f"<div>formal_commissioning: {_status_span(report['formal_commissioning'])}</div>",
        f"<div>semantic_commissioning: {_status_span(semantic['status'])}</div>",
        f"<div>lifecycle_state: {_status_span(report['lifecycle_state'])}</div>",
        f"<div class='mut'>mode: {_e(report['mode'])} · independent_holdback: "
        f"{_e(report['independent_holdback'])} · custodian: {_e(report['custodian'])}</div>",
        "</div>",
        "<h2>Summary by class</h2><div class='card scroll'>",
        _bucket_table(report["summary"]["by_class"]), "</div>",
        "<h2>Summary by partition</h2><div class='card scroll'>",
        _bucket_table(report["summary"]["by_partition"]), "</div>",
        "<h2>Controlled mutations</h2><div class='card'>",
        f"<div>{report['mutations_summary']['checks']} checks, "
        f"{report['mutations_summary']['held']} held</div>",
        _violated_table(report["mutations_summary"]["violated"]), "</div>",
        "<h2>Holdback-designate</h2><div class='card'>"
        f"<p>{_e(report['holdback_designate_note'])}</p></div>",
        "<h2>Semantic commissioning</h2><div class='card'>"
        f"<div>{_e(semantic['reason'])}</div>"
        f"<div>reviews_received: {semantic['reviews_received']} · agreement: "
        f"{_e(semantic['agreement'])}</div>"
        f"<div class='mut'>judgment_heavy fixtures: "
        f"{_e(', '.join(semantic['judgment_heavy_fixture_ids']))}</div></div>",
        "<h2>Limitations</h2><div class='card'><ul>"
        + "".join(f"<li>{_e(x)}</li>" for x in report["limitations"]) + "</ul></div>",
        "<h2>Fixtures</h2><div class='card scroll'>", _fixture_table(report["fixtures"]), "</div>",
        "</main></body></html>",
    ]
    return "".join(parts)


__all__ = ["render_html"]
