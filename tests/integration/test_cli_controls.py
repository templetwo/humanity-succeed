"""`hs controls generate|check|plan|run`, `hs review export-controls|import|status|adjudicate` end to
end (DECISIONS B68-B71). Lead-authored integration test: the cross-lane interactions no single
lane's verifier could see.

Every rating here is SYNTHETIC, under obviously fake reviewer_refs, written only into temporary
directories. No code path in the package writes a human rating. No model is called.
"""

from __future__ import annotations

import json
from pathlib import Path

from humanity_succeed.review.contract import CONTROL_FORBIDDEN_TOKENS, CONTROLS_CONFIG
from humanity_succeed.semantic_controls.contract import ANGLES, GROUPS

from ..conftest import REPO
from .test_cli import hs

COMMISSION_RUN = REPO / "docs" / "receipts" / "wp3" / "run"
SUPPLEMENT = REPO / "cases" / "supplement_a1_semantic_controls_v1"
MEASURED = 36
EXPECTED_ITEMS = (MEASURED + CONTROLS_CONFIG["decoys"] + CONTROLS_CONFIG["known_fail"]
                  + CONTROLS_CONFIG["twins"])


def _run_supplement(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    code, env, _ = hs("controls", "check", "--out", SUPPLEMENT)
    assert code == 0, env
    code, env, _ = hs("controls", "plan", "--supplement", SUPPLEMENT, "--out", tmp_path / "plan",
                      "--state-root", state)
    assert code == 0, env
    code, env, _ = hs("controls", "run", "--plan", tmp_path / "plan" / "plan.json",
                      "--out", tmp_path / "sc-run", "--state-root", state)
    assert code == 0, env
    report = json.loads((tmp_path / "sc-run" / "report.json").read_text())
    rows = report["fixtures"]
    assert len(rows) == GROUPS * 2
    assert all(r["match"] and r["verify_internal"] == "consistent" for r in rows)
    wrong_roles = [r["role"] for r in rows if r["role"] != "true_notice"]
    assert wrong_roles.count("blame") == GROUPS // len(ANGLES)
    return tmp_path / "sc-run"


def _export(tmp_path: Path, sc_run: Path) -> tuple[Path, dict]:
    state = tmp_path / "state"
    code, env, _ = hs("review", "export-controls", COMMISSION_RUN, "--supplement", sc_run,
                      "--out", tmp_path / "packet", "--state-root", state)
    assert code == 0, env
    assert env["result"]["items"] == EXPECTED_ITEMS
    assert env["result"]["counts"] == {"measured": MEASURED, "decoy": CONTROLS_CONFIG["decoys"],
                                       "known_fail": CONTROLS_CONFIG["known_fail"],
                                       "honest_twin": CONTROLS_CONFIG["twins"]}
    keys = list((state / "reviews" / "keys").glob("pk_*.json"))
    assert len(keys) == 1 and not list((tmp_path / "packet").glob("*key*"))
    key = json.loads(keys[0].read_text())
    assert key["schema_id"] == "hs-review-key/2"
    return tmp_path / "packet", key


def _ratings(packet_dir: Path, ref: str, verdict_for) -> Path:
    tpl = json.loads((packet_dir / "ratings-template.json").read_text())
    tpl.update(reviewer_ref=ref, rated_at_utc="2026-10-08T00:00:00Z")
    for r in tpl["ratings"]:
        r.update(verdict=verdict_for(r["item_id"]), words="synthetic test words, not a real review")
    out = packet_dir.parent / f"ratings-{ref}.json"
    out.write_text(json.dumps(tpl))
    return out


def test_controls_pipeline_end_to_end(tmp_path):
    state = tmp_path / "state"
    sc_run = _run_supplement(tmp_path)
    packet_dir, key = _export(tmp_path, sc_run)

    # the reviewer-facing files carry no role, angle, id or expectation vocabulary
    packet_text = (packet_dir / "packet.json").read_text()
    html_text = (packet_dir / "index.html").read_text()
    for tok in CONTROL_FORBIDDEN_TOKENS:
        bare = tok.strip('"')
        if bare == "blame":
            continue  # the pinned rubric line contains it; forbidden only quoted
        assert bare not in packet_text and bare not in html_text, tok
    for entry in key["entries"]:
        assert entry["fixture_id"] not in packet_text and entry["fixture_id"] not in html_text

    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", state)
    assert code == 0 and env["result"]["status"] == "pending_no_human_reviews"
    assert env["result"]["controls"] is None

    # reviewer one passes everything: a non-reader. Controls disclose only after full coverage.
    r1 = _ratings(packet_dir, "synthetic-reviewer-one", lambda _i: "pass")
    code, env, _ = hs("review", "import", "--packet", packet_dir, "--ratings", r1, "--state-root", state)
    assert code == 0, env
    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", state)
    res = env["result"]
    assert res["status"] == "single_reviewer_reviewed" and res["label"] == "single-reviewer"
    assert res["agreement"] is None
    ctl = res["controls"]
    assert ctl is not None and ctl["counts"]["known_fail"] == CONTROLS_CONFIG["known_fail"]
    one = ctl["per_reviewer"]["synthetic-reviewer-one"]
    assert one["known_fail"] == {"total": CONTROLS_CONFIG["known_fail"], "failed": 0}
    assert one["decoy"] == {"total": CONTROLS_CONFIG["decoys"], "passed": CONTROLS_CONFIG["decoys"]}
    assert one["honest_twin"] == {"total": CONTROLS_CONFIG["twins"], "passed": CONTROLS_CONFIG["twins"]}

    # reviewer two reads: fails exactly the known-fail items (the operator key says which)
    known_fail = {e["item_id"] for e in key["entries"] if e["role"] == "known_fail"}
    r2 = _ratings(packet_dir, "synthetic-reviewer-two",
                  lambda i: "fail" if i in known_fail else "pass")
    code, env, _ = hs("review", "import", "--packet", packet_dir, "--ratings", r2, "--state-root", state)
    assert code == 0, env
    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", state)
    res = env["result"]
    assert res["status"] == "split_unadjudicated" and res["label"] == "single-reviewer"
    assert len(res["open_disagreements"]) == CONTROLS_CONFIG["known_fail"]
    two = res["controls"]["per_reviewer"]["synthetic-reviewer-two"]
    assert two["known_fail"] == {"total": CONTROLS_CONFIG["known_fail"],
                                 "failed": CONTROLS_CONFIG["known_fail"]}
    # agreement over all items is defined now (fail prevalence > 0); measured-only has no fails
    assert res["agreement"] is not None and res["agreement_measured"] is not None

    # the named adjudicator settles each split; the ledger of ratings is untouched by it
    ledger_before = (state / "reviews" / "ledger.jsonl").read_bytes()
    for n, d in enumerate(res["open_disagreements"]):
        code, env, _ = hs("review", "adjudicate", "--packet", packet_dir, "--item", d["item_id"],
                          "--dimension", d["dimension"], "--adjudicator", "synthetic-adjudicator",
                          "--decision", "fail", "--words", "synthetic adjudication words",
                          "--at", f"2026-10-08T01:00:{n:02d}Z", "--state-root", state)
        assert code == 0, env
    assert (state / "reviews" / "ledger.jsonl").read_bytes() == ledger_before
    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", state)
    res = env["result"]
    assert res["status"] == "independently_reviewed" and res["label"] is None
    assert res["open_disagreements"] == []
    assert len(res["adjudications"]) == CONTROLS_CONFIG["known_fail"]
    assert all(not a["stale"] for a in res["adjudications"])

    # a second adjudication on a still-disagreeing item is the adjudicator's REVISION (the votes
    # still differ; the contract refuses only when they agree); it supersedes the first
    first = res["adjudications"][0]
    code, env, _ = hs("review", "adjudicate", "--packet", packet_dir, "--item", first["item_id"],
                      "--dimension", first["dimension"], "--adjudicator", "synthetic-adjudicator",
                      "--decision", "pass", "--words", "synthetic revised adjudication",
                      "--at", "2026-10-08T02:00:00Z", "--state-root", state)
    assert code == 0 and env["result"]["revision"] == 2, env
    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", state)
    res = env["result"]
    assert res["status"] == "independently_reviewed" and res["open_disagreements"] == []
    latest = [a for a in res["adjudications"] if a["item_id"] == first["item_id"]]
    assert latest and max(a["revision"] for a in latest) == 2

    # an adjudication on an item where the two reviewers AGREE is refused: nothing to settle
    agreed = next(e["item_id"] for e in key["entries"] if e["role"] == "measured")
    code, env, _ = hs("review", "adjudicate", "--packet", packet_dir, "--item", agreed,
                      "--dimension", first["dimension"], "--adjudicator", "synthetic-adjudicator",
                      "--decision", "pass", "--words", "x", "--at", "2026-10-08T02:00:01Z",
                      "--state-root", state)
    assert code == 2 and env["error"]["code"] == "adjudication_refused"

    # reviewer one revises one known-fail item after the disclosure: the split reopens and the
    # revision after full coverage is counted
    target = sorted(known_fail)[0]
    r1b = _ratings(packet_dir, "synthetic-reviewer-one", lambda i: "fail" if i == target else "pass")
    code, env, _ = hs("review", "import", "--packet", packet_dir, "--ratings", r1b, "--state-root", state)
    assert code == 0, env
    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", state)
    res = env["result"]
    # every item was re-rated (a revision each), so every adjudication record, both revisions of
    # the re-adjudicated item included, is stale
    assert res["adjudications"] and all(a["stale"] for a in res["adjudications"])
    settled = {(a["item_id"], a["dimension"]) for a in res["adjudications"]}
    assert len(settled) == CONTROLS_CONFIG["known_fail"]
    assert res["status"] == "split_unadjudicated"
    assert res["controls"]["per_reviewer"]["synthetic-reviewer-one"]["revisions_after_full_coverage"] \
        == EXPECTED_ITEMS

    # the supplement's committed tree and the commission run are untouched by all of this
    code, env, _ = hs("controls", "check", "--out", SUPPLEMENT)
    assert code == 0, env


def test_v1_export_refuses_a_supplement_run(tmp_path):
    sc_run = _run_supplement(tmp_path)
    code, env, _ = hs("review", "export", sc_run, "--out", tmp_path / "p1",
                      "--state-root", tmp_path / "state")
    assert code != 0 and not (tmp_path / "p1").exists()
