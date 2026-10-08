"""`hs review export | import | status` end to end (DECISIONS B60, B61; BUILD_SPEC §11, A19).

The ratings used here are SYNTHETIC test data under an obviously fake reviewer_ref, written only
into temporary directories. No code path in the package writes a human rating.
"""

import json

from ..conftest import REPO
from .test_cli import hs

RUN = REPO / "docs" / "receipts" / "wp3" / "run"


def _export(tmp_path):
    code, env, _ = hs("review", "export", RUN, "--out", tmp_path / "packet",
                      "--state-root", tmp_path / "state")
    assert code == 0, env
    return env


def test_export_import_status_round_trip(tmp_path):
    env = _export(tmp_path)
    assert env["result"]["items"] == 36
    packet_dir = tmp_path / "packet"
    assert (packet_dir / "index.html").is_file() and (packet_dir / "packet.json").is_file()
    # the operator key is under the state root, never in the reviewer's directory
    keys = list((tmp_path / "state" / "reviews" / "keys").glob("pk_*.json"))
    assert len(keys) == 1 and not list(packet_dir.glob("*key*"))

    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", tmp_path / "state")
    assert code == 0 and env["result"]["status"] == "pending_no_human_reviews"

    # the untouched template is refused: blanks are never defaulted into a verdict
    code, env, _ = hs("review", "import", "--packet", packet_dir, "--ratings",
                      packet_dir / "ratings-template.json", "--state-root", tmp_path / "state")
    assert code == 2 and env["error"]["code"] == "ratings_refused"
    assert not (tmp_path / "state" / "reviews" / "ledger.jsonl").exists()

    tpl = json.loads((packet_dir / "ratings-template.json").read_text())
    tpl.update(reviewer_ref="synthetic-test-reviewer", rated_at_utc="2026-09-28T00:00:00Z")
    for r in tpl["ratings"]:
        r.update(verdict="pass", words="synthetic test words, not a real review")
    filled = tmp_path / "ratings.json"
    filled.write_text(json.dumps(tpl))
    code, env, _ = hs("review", "import", "--packet", packet_dir, "--ratings", filled,
                      "--state-root", tmp_path / "state")
    assert code == 0 and env["result"]["votes"] == len(tpl["ratings"])

    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", tmp_path / "state")
    res = env["result"]
    assert res["status"] == "single_reviewer_reviewed" and res["label"] == "single-reviewer"
    assert res["agreement"] is None

    # the same person again is a revision, never a second reviewer
    code, env, _ = hs("review", "import", "--packet", packet_dir, "--ratings", filled,
                      "--state-root", tmp_path / "state")
    assert code == 0
    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", tmp_path / "state")
    assert env["result"]["status"] == "single_reviewer_reviewed"


def test_export_refuses_an_existing_out_dir(tmp_path):
    (tmp_path / "packet").mkdir()
    code, env, _ = hs("review", "export", RUN, "--out", tmp_path / "packet",
                      "--state-root", tmp_path / "state")
    assert code == 2 and env["error"]["code"] == "refuse_overwrite"


def test_export_of_a_tampered_run_is_refused(tmp_path):
    import shutil

    run = tmp_path / "run"
    shutil.copytree(RUN, run)
    report = json.loads((run / "report.json").read_text())
    fx = next(f for f in report["fixtures"] if f["expected"]["judgment_heavy"])
    ev = run / fx["bundle"] / "events.jsonl"
    ev.write_text(ev.read_text().replace("\"allow\"", "\"deny\"", 1))
    code, env, _ = hs("review", "export", run, "--out", tmp_path / "packet",
                      "--state-root", tmp_path / "state")
    assert code == 5 and not (tmp_path / "packet").exists()


def test_a_variant_spelling_of_the_same_reviewer_is_refused_not_counted_twice(tmp_path):
    """Measured on 2026-10-07 at 3f304a1: importing the same synthetic ratings as 'anthony' and
    then as 'Anthony ' moved `hs review status` to independently_reviewed, dropped the
    single-reviewer label and emitted an agreement block. B61 says one person is never two."""
    _export(tmp_path)
    packet_dir = tmp_path / "packet"
    state = tmp_path / "state"
    tpl = json.loads((packet_dir / "ratings-template.json").read_text())
    for r in tpl["ratings"]:
        r.update(verdict="pass", words="synthetic test words, not a real review")

    first = dict(tpl, reviewer_ref="anthony", rated_at_utc="2026-10-07T00:00:00Z")
    (tmp_path / "first.json").write_text(json.dumps(first))
    code, env, _ = hs("review", "import", "--packet", packet_dir, "--ratings", tmp_path / "first.json",
                      "--state-root", state)
    assert code == 0 and env["result"]["votes"] == 36

    for n, variant in enumerate(("Anthony ", "Anthony", "ANTHONY")):
        again = dict(tpl, reviewer_ref=variant, rated_at_utc="2026-10-07T00:00:00Z")
        (tmp_path / f"again{n}.json").write_text(json.dumps(again))
        code, env, _ = hs("review", "import", "--packet", packet_dir, "--ratings",
                          tmp_path / f"again{n}.json", "--state-root", state)
        assert code == 2 and env["error"]["code"] == "ratings_refused", variant

    code, env, _ = hs("review", "status", "--packet", packet_dir, "--state-root", state)
    res = env["result"]
    assert res["status"] == "single_reviewer_reviewed"
    assert res["label"] == "single-reviewer"
    assert res["distinct_human_reviewers"] == ["anthony"]
    assert res["agreement"] is None
    assert res["reviewer_ref_collisions"] == []
