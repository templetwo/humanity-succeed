"""review/status.py ``finish``: Anthony's sentence for when an exploratory review is finished
(DECISIONS B73, answering question 5 of docs/audits/2026-10-08_five_questions_plain_words.md).

Verbatim, 2026-10-24: "My exploratory review is complete when every item has my pass/fail judgment
and reasons in my own words. It meets the control criterion only if I catch every deliberately
wrong item. It remains single-reviewer evidence"

Packets, keys and ledger records are the synthetic ones of tests/review/test_status_v2.py.

Rulings these tests hold, and the alternative each one rejected:

- Complete is one reviewer's own coverage. REJECTED: the other shape the plain-words page offered,
  "two people have rated every item and every disagreement has been settled"; a second reviewer is
  never needed for complete, and never changes the first reviewer's entry.
- "Every" means every. REJECTED: a threshold (one missed wrong item and the criterion is not met).
- A catch is judged on the verdicts as they stood when the import that completed coverage ended,
  before any hit-rate could be read. REJECTED: the latest verdicts, under which a revision made
  after reading the controls could turn "not met" into "met".
- "Remains single-reviewer evidence": every entry carries the single-reviewer label, and a met
  criterion never changes the packet's status or label. REJECTED: a met criterion as an upgrade.
- Seat's reading, flagged to Anthony with B73: "deliberately wrong item" is the known-fail bucket
  only; a catch is a fail on at least one rubric dimension of the item (the hit-rate's rule).

IF ANTHONY ADDS "and passes the honest items", the assertion to flip is the one marked
``B73-FLIP`` in ``test_failing_every_item_meets_the_criterion_as_worded``.
Anthony kept the sentence as worded on 2026-10-24 (B74); the flip stays unmade.
"""

from __future__ import annotations

import json

from humanity_succeed.review import ledger
from humanity_succeed.review.contract import REVIEW_MODE_SINGLE, STATUS_INDEPENDENT, STATUS_SINGLE
from humanity_succeed.review.status import review_status

from .test_status import _item as _item_v1
from .test_status import _manifest as _manifest_v1
from .test_status import _record as _record_v1
from .test_status import _write_packet as _write_packet_v1
from .test_status_v2 import (
    ALL_ITEMS,
    D1,
    D2,
    DIMS,
    K1,
    K2,
    M1,
    M2,
    T1,
    D,
    E,
    cover_all,
    make_v2,
    rec,
    status,
)

CATCH_BOTH = {(K1, D): "fail", (K2, D): "fail"}


def finish(result: dict, name: str) -> dict:
    assert result["finish"]["rule"] == "B73"
    return result["finish"]["reviewers"][name]


def test_one_reviewer_who_catches_every_wrong_item_is_complete_and_meets_it(tmp_path):
    """Positive control. Complete without a second reviewer; the met criterion leaves the packet
    single-reviewer."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony", overrides=CATCH_BOTH))
    result = status(env)
    assert finish(result, "anthony") == {
        "complete": True,
        "control_criterion_met": True,
        "control_criterion_reason": None,
        "deliberately_wrong": {"total": 2, "caught": 2},
        "evidence": REVIEW_MODE_SINGLE,
    }
    assert result["status"] == STATUS_SINGLE and result["label"] == REVIEW_MODE_SINGLE


def test_one_missed_wrong_item_and_the_criterion_is_not_met(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony", overrides={(K1, D): "fail"}))
    entry = finish(status(env), "anthony")
    assert entry["complete"] is True
    assert entry["control_criterion_met"] is False
    assert entry["deliberately_wrong"] == {"total": 2, "caught": 1}


def test_a_fail_on_one_dimension_catches_the_item(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root,
                          cover_all("anthony", overrides={(K1, E): "fail", (K2, D): "fail"}))
    assert finish(status(env), "anthony")["control_criterion_met"] is True


def test_an_incomplete_review_discloses_nothing(tmp_path):
    """Negative control: one dimension short of coverage. No criterion, no counts, no bucket word
    anywhere in the report."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root,
                          [r for r in cover_all("anthony", overrides=CATCH_BOTH)
                           if (r.item_id, r.dimension) != (M1, D)])
    result = status(env)
    entry = finish(result, "anthony")
    assert entry["complete"] is False
    assert entry["control_criterion_met"] is None
    assert "every rubric dimension of every item" in entry["control_criterion_reason"]
    assert "deliberately_wrong" not in entry
    assert entry["evidence"] == REVIEW_MODE_SINGLE
    text = json.dumps(result)
    for token in ("decoy", "known_fail", "honest_twin", "supplement_run", "commission_run"):
        assert token not in text, token


def test_a_revision_after_coverage_cannot_turn_a_miss_into_a_catch(tmp_path):
    """The rejected alternative: K2 missed at coverage, then revised to fail in a later import (as
    a reviewer could after reading the hit-rate). The controls block follows the latest verdict
    (2 of 2); the finish criterion stays on the blind verdicts (1 of 2, not met)."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony", overrides={(K1, D): "fail"}))
    ledger.append_records(env.state_root,
                          [rec(K2, D, "fail", "anthony", revision=2, file_sha="c" * 64)])
    result = status(env)
    assert result["controls"]["per_reviewer"]["anthony"]["known_fail"] == {"total": 2, "failed": 2}
    entry = finish(result, "anthony")
    assert entry["control_criterion_met"] is False
    assert entry["deliberately_wrong"] == {"total": 2, "caught": 1}


def test_a_revision_inside_the_completing_import_is_still_blind(tmp_path):
    """Verifier finding F3's boundary, kept: records after the covering one but in the SAME
    ratings file were written before anything could be read, so they count."""
    env = make_v2(tmp_path)
    file_a = "a" * 64
    records = [rec(i, d, "fail" if (i, d) == (K1, D) else "pass", "anthony", file_sha=file_a)
               for i in ALL_ITEMS for d in DIMS[i]]
    records.append(rec(K2, D, "fail", "anthony", revision=2, file_sha=file_a))
    ledger.append_records(env.state_root, records)
    entry = finish(status(env), "anthony")
    assert entry["deliberately_wrong"] == {"total": 2, "caught": 2}
    assert entry["control_criterion_met"] is True


def test_failing_every_item_meets_the_criterion_as_worded(tmp_path):
    """The gap, recorded rather than closed: the sentence checks catches only, so a reviewer who
    fails every item meets it. The honest-item counts beside it show what happened."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony", verdict="fail"))
    result = status(env)
    assert finish(result, "anthony")["control_criterion_met"] is True  # B73-FLIP: False with the clause
    per = result["controls"]["per_reviewer"]["anthony"]
    assert per["decoy"] == {"total": 2, "passed": 0}
    assert per["honest_twin"] == {"total": 1, "passed": 0}


def test_failing_an_honest_item_does_not_touch_the_criterion(tmp_path):
    env = make_v2(tmp_path)
    overrides = dict(CATCH_BOTH) | {(D1, D): "fail", (D2, D): "fail", (T1, D): "fail",
                                    (M2, D): "fail"}
    ledger.append_records(env.state_root, cover_all("anthony", overrides=overrides))
    assert finish(status(env), "anthony")["control_criterion_met"] is True


def test_a_second_reviewer_is_never_needed_and_never_changes_the_first_entry(tmp_path):
    """Rejected shape: "two people have rated every item". Two reviewers who agree make the packet
    independently reviewed, yet each entry is still that reviewer's single-reviewer evidence."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony", overrides=CATCH_BOTH))
    alone = finish(status(env), "anthony")
    ledger.append_records(env.state_root, cover_all("maria", overrides=CATCH_BOTH))
    result = status(env)
    assert result["status"] == STATUS_INDEPENDENT
    assert finish(result, "anthony") == alone
    assert finish(result, "maria")["evidence"] == REVIEW_MODE_SINGLE


def test_model_ratings_get_no_finish_entry(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root,
                          [rec(i, d, "fail", "some-model", reviewer_kind="model")
                           for i in ALL_ITEMS for d in DIMS[i]])
    assert status(env)["finish"]["reviewers"] == {}


def test_a_v1_packet_can_be_complete_but_has_no_control_criterion(tmp_path):
    i1 = "it_" + "1" * 16
    manifest = _manifest_v1([_item_v1(i1, ["d"])])
    packet_dir = _write_packet_v1(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(state_root, [_record_v1(item_id=i1, dimension="d", verdict="pass",
                                                  reviewer_ref="anthony")])
    entry = review_status(packet_dir, state_root=state_root)["finish"]["reviewers"]["anthony"]
    assert entry == {
        "complete": True,
        "control_criterion_met": None,
        "control_criterion_reason": "packet without controls",
        "evidence": REVIEW_MODE_SINGLE,
    }
