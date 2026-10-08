"""`hs review export | import | status` paths with no end-to-end test before 2026-10-07 (cloud seat;
DECISIONS B60, B61; BUILD_SPEC §11, A19; docs/REVIEW_PACKET_HOWTO.md).

Ratings are SYNTHETIC, under obviously fake reviewer references, written only under ``tmp_path``.
No code path in the package writes a human rating. Tests that need to patch the export module run
``cli.main`` in-process; the rest go through the subprocess helper the existing CLI tests use.
"""

from __future__ import annotations

import json

import pytest

from humanity_succeed import cli
from humanity_succeed.review import export as review_export

from ..conftest import REPO
from .test_cli import hs

RUN = REPO / "docs" / "receipts" / "wp3" / "run"
LIMITATION_WORDS = "single-reviewer semantic review"


def _export(tmp_path, *extra):
    code, env, err = hs("review", "export", RUN, "--out", tmp_path / "packet",
                        "--state-root", tmp_path / "state", *extra)
    assert code == 0, (env, err)
    return env


def _template(tmp_path) -> dict:
    tpl = json.loads((tmp_path / "packet" / "ratings-template.json").read_text())
    tpl.update(reviewer_ref="synthetic-test-reviewer", rated_at_utc="2026-10-07T00:00:00Z")
    return tpl


def _import(tmp_path, ratings: dict, name: str):
    path = tmp_path / name
    path.write_text(json.dumps(ratings))
    return hs("review", "import", "--packet", tmp_path / "packet", "--ratings", path,
              "--state-root", tmp_path / "state")


def _status(tmp_path):
    code, env, _ = hs("review", "status", "--packet", tmp_path / "packet",
                      "--state-root", tmp_path / "state")
    assert code == 0
    return env


def test_partial_template_round_trip_as_the_howto_describes_it(tmp_path):
    """Audit F06, measured at 3f304a1 and now pinned: the half-filled template is refused whole and
    nothing is recorded; the same rows with the blank rows deleted are recorded, status reads
    partial; the remaining rows later complete the review under the same reference with every
    record still revision 1. ``docs/REVIEW_PACKET_HOWTO.md`` tells the reviewer exactly this."""
    _export(tmp_path)
    tpl = _template(tmp_path)
    assert len(tpl["ratings"]) == 36
    first, rest = tpl["ratings"][:18], tpl["ratings"][18:]
    for r in first:
        r.update(verdict="pass", words="synthetic test words, not a real review")

    code, env, _ = _import(tmp_path, tpl, "half-filled.json")
    assert code == 2 and env["error"]["code"] == "ratings_refused"
    assert env["result"]["problems"] and all("invalid ratings file" in p for p in env["result"]["problems"])
    assert not (tmp_path / "state" / "reviews" / "ledger.jsonl").exists()

    code, env, _ = _import(tmp_path, dict(tpl, ratings=first), "first-18.json")
    assert code == 0 and env["result"] == {"recorded": 18, "votes": 18, "secondary": 0}
    status = _status(tmp_path)["result"]
    assert status["status"] == "single_reviewer_partial" and status["label"] == "single-reviewer"
    assert sum(1 for i in status["items"] if i["human_reviewers"]) == 18
    assert status["agreement"] is None

    for r in rest:
        r.update(verdict="fail", words="synthetic test words, not a real review")
    code, env, _ = _import(tmp_path, dict(tpl, ratings=rest), "last-18.json")
    assert code == 0 and env["result"]["votes"] == 18
    status = _status(tmp_path)["result"]
    assert status["status"] == "single_reviewer_reviewed"
    assert status["distinct_human_reviewers"] == ["synthetic-test-reviewer"]
    verdicts = [i["verdicts"]["synthetic-test-reviewer"]["truthful_notification"] for i in status["items"]]
    assert verdicts.count("pass") == 18 and verdicts.count("fail") == 18

    lines = (tmp_path / "state" / "reviews" / "ledger.jsonl").read_text().splitlines()
    assert len(lines) == 36 and {json.loads(line)["revision"] for line in lines} == {1}


def test_model_ratings_through_the_cli_are_secondary_and_leave_status_pending(tmp_path):
    _export(tmp_path)
    tpl = _template(tmp_path)
    tpl.update(reviewer_ref="synthetic-critique-model", reviewer_kind="model")
    for r in tpl["ratings"]:
        r.update(verdict="pass", words="synthetic model words, not a review")
    code, env, _ = _import(tmp_path, tpl, "model.json")
    assert code == 0 and env["result"] == {"recorded": 36, "votes": 0, "secondary": 36}
    status = _status(tmp_path)["result"]
    assert status["status"] == "pending_no_human_reviews"
    assert status["secondary_ratings"] == 36 and status["distinct_human_reviewers"] == []


def test_export_envelope_names_the_artifacts_the_limitation_and_a_key_outside_the_packet(tmp_path):
    env = _export(tmp_path)
    paths = env["result"]["paths"]
    assert env["artifacts"] == [str(tmp_path / "packet")]
    assert any(LIMITATION_WORDS in lim for lim in env["limitations"])
    assert any("operator key" in lim for lim in env["limitations"])
    assert paths["key"].startswith(str(tmp_path / "state"))
    assert not paths["key"].startswith(str(tmp_path / "packet"))
    assert env["result"]["packet_id"].startswith("pk_") and env["result"]["items"] == 36


def test_export_without_state_root_uses_hs_state_root_for_the_key(tmp_path, monkeypatch):
    """The conftest sets HS_STATE_ROOT under tmp_path; the key must land there, never beside the
    packet, when the operator does not pass ``--state-root``."""
    import os

    code, env, _ = hs("review", "export", RUN, "--out", tmp_path / "packet")
    assert code == 0
    assert env["result"]["paths"]["key"].startswith(os.environ["HS_STATE_ROOT"])
    assert not list((tmp_path / "packet").glob("*key*"))


def test_export_that_would_leak_exits_3_with_blind_packet_leak_and_writes_nothing(
    tmp_path, monkeypatch, capsys,
):
    original = review_export._build_item

    def leaking(bundle_dir, item_id):
        item = original(bundle_dir, item_id)
        return item.model_copy(update={"task": item.task + " c1-g01-real_correction"})

    monkeypatch.setattr(review_export, "_build_item", leaking)
    code = cli.main(["review", "export", str(RUN), "--out", str(tmp_path / "packet"),
                     "--state-root", str(tmp_path / "state")])
    env = json.loads(capsys.readouterr().out)
    assert code == 3 and env["status"] == "blocked"
    assert env["error"]["code"] == "blind_packet_leak"
    assert "c1-g01-real_correction" in env["result"]["problems"]
    assert not (tmp_path / "packet").exists()
    assert not (tmp_path / "state" / "reviews").exists()


def test_import_with_a_missing_ratings_file_is_a_refusal_not_a_crash(tmp_path):
    _export(tmp_path)
    code, env, _ = hs("review", "import", "--packet", tmp_path / "packet", "--ratings",
                      tmp_path / "nowhere.json", "--state-root", tmp_path / "state")
    assert code == 2 and env["error"]["code"] == "ratings_refused"
    assert "cannot read ratings file" in env["error"]["message"]


def test_status_on_a_corrupt_ledger_is_invalid_input_not_an_empty_report(tmp_path):
    _export(tmp_path)
    ledger = tmp_path / "state" / "reviews" / "ledger.jsonl"
    ledger.write_text("not a record\n", encoding="utf-8")
    code, env, _ = hs("review", "status", "--packet", tmp_path / "packet", "--state-root", tmp_path / "state")
    assert code == 2 and env["error"]["code"] == "invalid_input"
    assert "line 1" in env["error"]["message"]
    assert env["result"] is None


def test_status_on_a_missing_packet_is_invalid_input(tmp_path):
    code, env, _ = hs("review", "status", "--packet", tmp_path / "no-packet",
                      "--state-root", tmp_path / "state")
    assert code == 2 and env["error"]["code"] == "invalid_input"


@pytest.mark.parametrize("args", [
    ("review",),
    ("review", "export"),
    ("review", "import", "--packet", "p"),
    ("review", "status"),
])
def test_review_subcommands_require_their_arguments(args):
    code, env, err = hs(*args)
    assert code == 2 and env is None
    assert "usage:" in err
