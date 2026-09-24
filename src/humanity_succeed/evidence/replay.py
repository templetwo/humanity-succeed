"""Read-only replay and static report (BUILD_SPEC §7.1, §14).

Replay never writes into the bundle. It verifies the bundle, re-executes the recorded raw outputs
through a fresh in-memory engine with the same run_id, and requires every recorded observation,
proposal, permission, execution and effect (timestamps and hashes aside) and the evaluation to be
reproduced exactly. The report is one static HTML file with no network dependency.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, make_new_dir, strict_json_loads, write_new_file
from ..contracts.case import CaseSource
from ..evidence.store import EvidenceStore
from ..providers.scripted import ScriptedProvider
from .bundle import _read_events, verify_bundle

_VOLATILE = ("timestamp_utc", "prev_hash", "event_hash")


def _stable(e: dict[str, Any]) -> dict[str, Any]:
    d = {k: v for k, v in e.items() if k not in _VOLATILE}
    if e["event_type"] == "run_started":
        d["payload"] = {k: v for k, v in e["payload"].items() if k != "manifest_sha256"}
    return d


def replay_bundle(bundle: Path, out_dir: Path) -> dict[str, Any]:
    from ..runner.episode import run_episode
    from ..runner.scripted import evaluate_and_record

    bundle = Path(bundle)
    verification = verify_bundle(bundle)
    out = make_new_dir(Path(out_dir))
    result: dict[str, Any] = {"schema_id": "hs-replay-report/1", "bundle": str(bundle),
                              "verification": verification}
    if verification["internal"] != "consistent":
        result["replay"] = {"status": "refused", "reason": "bundle failed internal verification"}
        write_new_file(out / "replay.json", canonical_bytes(result))
        write_new_file(out / "report.html", _html(result, None, None, None).encode())
        return result

    events = _read_events(bundle / "events.jsonl")
    case_doc = strict_json_loads((bundle / "case_source.json").read_bytes())
    case = CaseSource.model_validate(case_doc, strict=True)
    evaluation = strict_json_loads((bundle / "evaluation.json").read_bytes())
    raws = [
        (bundle / "artifacts" / e["payload"]["raw_sha256"]).read_bytes().decode("utf-8")
        for e in events if e["event_type"] == "provider_response"
    ]
    status = next(e for e in events if e["event_type"] == "run_completed")["payload"]
    store = EvidenceStore(Path(":memory:"))
    try:
        run_id = events[0]["run_id"]
        manifest = strict_json_loads((bundle / "manifest.json").read_bytes())
        limits = manifest["limits"]
        # A provider_failure run exhausted its script: replay the same finite script.
        provider = ScriptedProvider(raws)
        run_episode(case, case_doc, provider, store, run_id=run_id, limits=limits)
        re_eval = evaluate_and_record(store, run_id, case)
        re_events = store.events(run_id)
    finally:
        store.close()

    rec_stable = [_stable(e) for e in events]
    re_stable = [_stable(e) for e in re_events]
    diverge = next((i for i, (a, b) in enumerate(zip(rec_stable, re_stable, strict=False))
                    if a != b), None)
    same_len = len(rec_stable) == len(re_stable)
    ok = diverge is None and same_len and re_eval == evaluation
    result["replay"] = {
        "status": "reproduced" if ok else "diverged",
        "events_compared": min(len(rec_stable), len(re_stable)),
        "first_divergence_index": diverge,
        "length_match": same_len,
        "evaluation_reproduced": re_eval == evaluation,
        "recorded_terminal_status": status["terminal_status"],
        "compared_fields": "all envelope fields except timestamp_utc, prev_hash, event_hash, and "
                           "run_started.manifest_sha256 (code identity may differ at replay time)",
    }
    write_new_file(out / "replay.json", canonical_bytes(result))
    write_new_file(out / "report.html", _html(result, case, events, evaluation).encode())
    return result


# ---------------------------------------------------------------- static HTML

_CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#5b5b57;--line:#dcd9d0;--card:#fff;--ok:#1f6f43;--bad:#a4271b;
--pend:#8a5a00;--code:#f3f1ea}
@media (prefers-color-scheme: dark){:root{--bg:#161614;--fg:#ecebe6;--mut:#a3a29b;--line:#34332f;
--card:#1e1e1b;--ok:#6fcf97;--bad:#ff8a7a;--pend:#f2c14e;--code:#262522}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:16px}
main{max-width:1100px;margin:0 auto}h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:2rem}
.banner{border:2px solid var(--pend);padding:10px 14px;border-radius:8px;margin:12px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-top:1px solid var(--line);
padding:6px;vertical-align:top;text-align:left}pre{background:var(--code);padding:8px;
border-radius:6px;overflow-x:auto;white-space:pre-wrap;word-break:break-word;margin:0}
.pass{color:var(--ok);font-weight:600}.fail{color:var(--bad);font-weight:600}
.not_evaluable,.pending_review,.pending{color:var(--pend);font-weight:600}.mut{color:var(--mut)}
.scroll{overflow-x:auto}
"""


def _e(x: Any) -> str:
    return html.escape(str(x))


def _j(x: Any) -> str:
    return _e(json.dumps(x, indent=1, ensure_ascii=False, sort_keys=True))


def _pred_html(t: dict[str, Any]) -> str:
    kids = t.get("args") or ([t["arg"]] if "arg" in t else [])
    extra = {k: v for k, v in t.items() if k not in ("op", "result", "args", "arg")}
    inner = "".join(f"<li>{_pred_html(k)}</li>" for k in kids)
    return (f"<code>{_e(t['op'])}</code> → <span class='{_e(t['result'])}'>{_e(t['result'])}</span>"
            f" <span class='mut'>{_e(json.dumps(extra, sort_keys=True)) if extra else ''}</span>"
            + (f"<ul>{inner}</ul>" if inner else ""))


def _turn_rows(events: list[dict[str, Any]], bundle_artifacts: Path | None) -> str:
    rows = []
    by_prop: dict[int, list[dict[str, Any]]] = {}
    for e in events:
        ps = e["payload"].get("proposal_seq") if isinstance(e["payload"], dict) else None
        if ps is not None:
            by_prop.setdefault(ps, []).append(e)
    for e in events:
        t = e["event_type"]
        if t == "action_parse_failed":
            rows.append(f"<tr><td>{e['sequence']}</td><td colspan=3><span class='fail'>invalid "
                        f"action</span> {_e(e['payload']['code'])}</td></tr>")
        if t != "action_proposed":
            continue
        related = by_prop.get(e["sequence"], [])
        perm = next((r for r in related if r["event_type"] == "permission_decided"), None)
        effects = [r for r in related if r["event_type"] not in ("permission_decided",)]
        eff_html = "".join(
            f"<div><code>{_e(r['event_type'])}</code><pre>{_j(r['payload'])}</pre></div>"
            for r in effects
        ) or "<span class='mut'>no execution</span>"
        perm_html = (f"<span class='{'pass' if perm['payload']['decision'] == 'allow' else 'fail'}'>"
                     f"{_e(perm['payload']['decision'])}</span> "
                     f"<span class='mut'>{_e(perm['payload']['reason_code'])}</span>"
                     if perm else "—")
        prop = {"action": e["payload"]["action"], "message": e["payload"]["message"]}
        rows.append(f"<tr><td>{e['sequence']}</td><td><pre>{_j(prop)}</pre></td>"
                    f"<td>{perm_html}</td><td>{eff_html}</td></tr>")
    return "".join(rows)


def _html(result, case, events, evaluation) -> str:
    v = result["verification"]
    rp = result.get("replay", {})
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Replay report</title><style>{_CSS}</style></head><body><main>",
             "<h1>Evidence replay report</h1>",
             "<div class='banner'><b>Scripted instrument run.</b> Instrument under construction. "
             "No behavioral result about any model is established by this report.</div>",
             f"<div class='card'>Internal verification: <b>{_e(v['internal'])}</b> · "
             f"anchor: <b>{_e(v['anchor'])}</b> · replay: <b>{_e(rp.get('status'))}</b>"
             f"<div class='mut'>{_e(v['note'])}</div></div>"]
    if case is not None:
        ev = evaluation
        parts += [
            "<h2>Task (subject-visible)</h2>",
            f"<div class='card'><pre>{_e(case.subject.task)}</pre></div>",
            "<h2>Outcome</h2><div class='card'>",
            f"Mechanical verdict: <span class='{_e(ev['mechanical']['verdict'])}'>"
            f"{_e(ev['mechanical']['verdict'])}</span> — {_e(ev['mechanical']['reason'])}<br>",
            f"Conduct outcome: <span class='{_e(ev['conduct_outcome'])}'>"
            f"{_e(ev['conduct_outcome'])}</span> (scoring mode {_e(ev['scoring_mode'])}; semantic "
            f"review {_e(ev['semantic_review']['status'])}, reviews received "
            f"{ev['semantic_review']['reviews_received']})<br>",
            f"Execution: {_e(json.dumps(ev['execution'], sort_keys=True))}<br>",
            f"Containment: {_e(json.dumps(ev['containment']['denied_proposals']))} — "
            f"<span class='mut'>{_e(ev['containment']['note'])}</span><br>",
            f"Rhetoric ledger: {_e(json.dumps({k: v for k, v in ev['rhetoric'].items() if k != 'note'}))}"
            f" — <span class='mut'>{_e(ev['rhetoric']['note'])}</span></div>",
            "<h2>Predicates</h2><div class='card'><b>pass_if</b><ul><li>"
            + _pred_html(ev["mechanical"]["pass_if"]) + "</li></ul>"
            + ("<b>fail_if</b><ul>" + "".join(f"<li>{_pred_html(t)}</li>"
                                               for t in ev["mechanical"]["fail_if"]) + "</ul>"
               if ev["mechanical"]["fail_if"] else "")
            + "</div>",
            "<h2>Turns: proposal → permission → execution and effects</h2>",
            "<div class='card scroll'><table><tr><th>seq</th><th>proposal (raw decision parsed)"
            "</th><th>permission</th><th>execution / effects / receipts</th></tr>",
            _turn_rows(events, None),
            "</table></div>",
            "<h2>Scope limitations</h2><div class='card'><ul>"
            + "".join(f"<li>{_e(s)}</li>" for s in ev["scope_limitations"]) + "</ul></div>",
        ]
    parts += ["<h2>Verification checks</h2><div class='card scroll'><table>"
              + "".join(f"<tr><td>{_e(c['check'])}</td><td class='{'pass' if c['passed'] else 'fail'}'>"
                        f"{'pass' if c['passed'] else 'fail'}</td><td>{_e(c['detail'])}</td></tr>"
                        for c in v["checks"]) + "</table></div>",
              f"<h2>Replay</h2><div class='card'><pre>{_j(rp)}</pre></div>",
              "</main></body></html>"]
    return "".join(parts)
