"""review/adjudication.py and the adjudication ledger (DECISIONS B71; audit F24, F28;
review/contract.py ``AdjudicationRecord``, ``ADJUDICATIONS_PATH``).

Synthetic /2 packets, keys and records from tests/review/test_status_v2.py. Reviewer references are
fake. Every refusal is checked by the name it gives, and every refusal appends nothing.

Rejected alternatives these tests hold the line against: an adjudication written INTO the review
ledger (a ledger line never gains a field or a kind, F28; the ledger file is byte-identical after an
adjudication); an adjudication as a third rating (it never changes coverage or the reviewer count);
an adjudication surviving a new vote on what it settled (stale, split reopened); an adjudicator
reference that is a case/whitespace variant of a recorded reviewer (B61: one person, one reference).
"""

from __future__ import annotations

import json

import pytest

from humanity_succeed.review import ledger
from humanity_succeed.review.adjudication import record_adjudication
from humanity_succeed.review.contract import (
    ADJUDICATION_SCHEMA,
    ADJUDICATIONS_PATH,
    STATUS_INDEPENDENT,
    STATUS_SPLIT,
    AdjudicationRecord,
)
from humanity_succeed.review.ledger import (
    LedgerCorrupt,
    adjudications_path,
    append_adjudications,
    ledger_path,
    read_adjudications,
)

from .test_status_v2 import (
    K1,
    M1,
    M2,
    PACKET_ID,
    V2,
    WHEN,
    D,
    E,
    cover_all,
    make_v2,
    rec,
    status,
)


def _split_env(tmp_path, name: str = "adj") -> V2:
    """anthony and maria cover everything; they disagree on M2 only."""
    env = make_v2(tmp_path, name=name)
    ledger.append_records(env.state_root, cover_all("anthony")
                          + cover_all("maria", overrides={(M2, D): "fail"}))
    return env


def adjudicate(env: V2, **overrides) -> dict:
    args = dict(item_id=M2, dimension=D, adjudicator_ref="anthony", decision="pass",
                words="The notice names the corrected total and blames no one.",
                adjudicated_at_utc=WHEN)
    args.update(overrides)
    return record_adjudication(env.packet_dir, state_root=env.state_root, **args)


def _adj_bytes(env: V2) -> bytes:
    p = adjudications_path(env.state_root)
    return p.read_bytes() if p.exists() else b""


# ============================================================================== the record


def test_an_adjudication_records_every_latest_vote_and_never_touches_the_review_ledger(tmp_path):
    env = _split_env(tmp_path)
    ledger.append_records(env.state_root, [rec(M2, D, "fail", "maria", revision=2)])
    review_ledger_before = ledger_path(env.state_root).read_bytes()

    result = adjudicate(env)

    assert result["status"] == "ok" and result["problems"] == []
    assert ledger_path(env.state_root).read_bytes() == review_ledger_before   # byte-identical
    assert adjudications_path(env.state_root) == env.state_root.joinpath(*ADJUDICATIONS_PATH)
    stored = read_adjudications(env.state_root)
    assert len(stored) == 1
    assert stored[0].model_dump(mode="json") == result["record"]
    record = stored[0]
    assert record.schema_id == ADJUDICATION_SCHEMA
    assert record.packet_id == PACKET_ID and record.packet_sha256 == env.packet_sha256
    entry = next(e for e in env.key.entries if e.item_id == M2)
    item = next(i for i in env.manifest.items if i.item_id == M2)
    assert record.fixture_id == entry.fixture_id
    assert record.source_sha256 == item.source_sha256
    assert record.adjudicator_kind == "human" and record.revision == 1
    assert [(v.reviewer_ref, v.verdict, v.revision) for v in record.reviewers] == [
        ("anthony", "pass", 1), ("maria", "fail", 2)
    ]
    # not a third rating: coverage and the reviewer count are unchanged
    after = status(env)
    assert after["distinct_human_reviewers"] == ["anthony", "maria"]
    m2 = next(i for i in after["items"] if i["item_id"] == M2)
    assert m2["verdicts"] == {"anthony": {D: "pass"}, "maria": {D: "fail"}}


def test_an_adjudication_over_three_reviewers_records_all_three_and_is_not_stale(tmp_path):
    env = _split_env(tmp_path)
    ledger.append_records(env.state_root, cover_all("omar"))
    result = adjudicate(env, adjudicator_ref="lead-adjudicator")
    assert result["status"] == "ok"
    assert [(v["reviewer_ref"], v["verdict"]) for v in result["record"]["reviewers"]] == [
        ("anthony", "pass"), ("maria", "fail"), ("omar", "pass")
    ]
    report = status(env)
    assert report["adjudications"][0]["stale"] is False
    assert report["status"] == STATUS_INDEPENDENT


def test_revisions_of_an_adjudication_are_numbered_per_item_and_dimension(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony")
                          + cover_all("maria", overrides={(M2, D): "fail", (K1, E): "fail"}))
    assert adjudicate(env)["record"]["revision"] == 1
    assert adjudicate(env, item_id=K1, dimension=E)["record"]["revision"] == 1
    assert adjudicate(env, decision="fail")["record"]["revision"] == 2
    assert status(env)["status"] == STATUS_INDEPENDENT


# ============================================================================== refusals


@pytest.mark.parametrize("overrides,named", [
    ({"item_id": "it_" + "9" * 16}, "unknown item_id"),
    ({"dimension": E}, "unknown dimension"),
    ({"decision": "unsure"}, "decision 'unsure' is not one of pass, fail"),
    ({"decision": "Pass"}, "decision 'Pass'"),
    ({"words": "  \t "}, "blank words"),
    ({"adjudicated_at_utc": "2026-10-07T14:03:00+00:00"}, "adjudicated_at_utc"),
    ({"adjudicated_at_utc": "2026-10-07"}, "adjudicated_at_utc"),
    ({"adjudicated_at_utc": "2026-02-30T00:00:00Z"}, "adjudicated_at_utc"),
    ({"adjudicator_ref": " anthony"}, "whitespace"),
    ({"adjudicator_ref": "аnthony"}, "outside ASCII"),
    ({"adjudicator_ref": "Anthony"}, "collides with recorded reference 'anthony'"),
    ({"adjudicator_ref": "anthony."}, "collides with recorded reference 'anthony'"),
    ({"item_id": M1}, "agree"),
])
def test_each_refusal_is_named_and_appends_nothing(tmp_path, overrides, named):
    env = _split_env(tmp_path)
    review_before = ledger_path(env.state_root).read_bytes()
    result = adjudicate(env, **overrides)
    assert result["status"] == "refused" and result["record"] is None
    assert any(named in p for p in result["problems"]), result["problems"]
    assert _adj_bytes(env) == b""
    assert ledger_path(env.state_root).read_bytes() == review_before


def test_the_canonical_collision_anthony_space_versus_anthony_is_refused(tmp_path):
    """'Anthony ' is the audit's measured variant of 'anthony': refused for its stray whitespace
    AND named as a collision with the recorded reference."""
    env = _split_env(tmp_path)
    result = adjudicate(env, adjudicator_ref="Anthony ")
    assert result["status"] == "refused"
    assert any("whitespace" in p for p in result["problems"])
    assert any("collides with recorded reference 'anthony'" in p for p in result["problems"])
    assert _adj_bytes(env) == b""


def test_an_adjudicator_colliding_with_an_earlier_adjudicator_is_refused(tmp_path):
    env = _split_env(tmp_path)
    assert adjudicate(env, adjudicator_ref="lead-adjudicator")["status"] == "ok"
    result = adjudicate(env, adjudicator_ref="Lead_Adjudicator")
    assert result["status"] == "refused"
    assert any("collides with recorded reference 'lead-adjudicator'" in p for p in result["problems"])


def test_a_model_reference_cannot_adjudicate(tmp_path):
    env = _split_env(tmp_path)
    ledger.append_records(env.state_root, [rec(M1, D, "pass", "some-model", reviewer_kind="model")])
    result = adjudicate(env, adjudicator_ref="some-model")
    assert result["status"] == "refused"
    assert any("recorded as a model reviewer" in p for p in result["problems"])


def test_one_reviewer_alone_has_nothing_to_adjudicate(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony")
                          + [rec(M2, D, "fail", "anthony", revision=2)])
    result = adjudicate(env)
    assert result["status"] == "refused"
    assert any("1 distinct human reviewer(s)" in p for p in result["problems"])


def test_a_model_vote_does_not_make_a_split(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony")
                          + [rec(M2, D, "fail", "some-model", reviewer_kind="model")])
    result = adjudicate(env, adjudicator_ref="lead-adjudicator")
    assert result["status"] == "refused"
    assert any("1 distinct human reviewer(s)" in p for p in result["problems"])


def test_an_unbound_packet_is_refused_by_name(tmp_path):
    env = _split_env(tmp_path)
    env.key_path.write_bytes(b'{"schema_id": "hs-review-key/2"}')
    result = adjudicate(env)
    assert result["status"] == "refused"
    assert any("not bound to its operator key" in p and "malformed" in p for p in result["problems"])
    env.key_path.unlink()
    result = adjudicate(env)
    assert any("no operator key" in p for p in result["problems"])
    assert _adj_bytes(env) == b""


def test_a_missing_or_invalid_packet_is_refused_by_name(tmp_path):
    env = _split_env(tmp_path)
    result = record_adjudication(tmp_path / "nowhere", state_root=env.state_root, item_id=M2,
                                 dimension=D, adjudicator_ref="anthony", decision="pass", words="w",
                                 adjudicated_at_utc=WHEN)
    assert result["status"] == "refused" and any("cannot read packet" in p for p in result["problems"])
    (env.packet_dir / "packet.json").write_bytes(b'{"schema_id": "hs-review-packet/2"}')
    result = adjudicate(env)
    assert result["status"] == "refused"
    assert any("invalid packet manifest" in p for p in result["problems"])


def test_a_corrupt_review_ledger_is_refused_not_skipped(tmp_path):
    env = _split_env(tmp_path)
    with open(ledger_path(env.state_root), "ab") as fh:
        fh.write(b"not a record\n")
    result = adjudicate(env)
    assert result["status"] == "refused"
    assert any("ledger corrupt" in p for p in result["problems"])


# ======================================================================= identity and staleness


def test_an_adjudicator_who_is_one_of_the_reviewers_is_allowed_and_flagged(tmp_path):
    env = _split_env(tmp_path)
    assert adjudicate(env, adjudicator_ref="anthony")["status"] == "ok"
    assert status(env)["adjudications"][0]["adjudicator_is_reviewer"] is True

    other = _split_env(tmp_path, name="other")
    assert adjudicate(other, adjudicator_ref="lead-adjudicator")["status"] == "ok"
    report = status(other)
    assert report["adjudications"][0]["adjudicator_is_reviewer"] is False
    assert report["status"] == STATUS_INDEPENDENT


def test_a_third_reviewers_later_disagreeing_vote_makes_the_adjudication_stale(tmp_path):
    env = _split_env(tmp_path)
    assert adjudicate(env)["status"] == "ok"
    assert status(env)["status"] == STATUS_INDEPENDENT
    ledger.append_records(env.state_root, cover_all("omar", overrides={(M2, D): "fail"}))
    result = status(env)
    assert result["adjudications"][0]["stale"] is True
    assert result["status"] == STATUS_SPLIT
    assert result["open_disagreements"] == [
        {"item_id": M2, "dimension": D, "votes": {"anthony": "pass", "maria": "fail", "omar": "fail"}}
    ]


def test_a_third_reviewer_who_agrees_with_the_decision_still_makes_it_stale(tmp_path):
    """The rule is any change in the set of latest votes, not "a change the adjudicator would mind".
    The disagreement anthony/maria is still there, so the split reopens."""
    env = _split_env(tmp_path)
    assert adjudicate(env)["status"] == "ok"
    ledger.append_records(env.state_root, cover_all("omar"))
    result = status(env)
    assert result["adjudications"][0]["stale"] is True
    assert result["status"] == STATUS_SPLIT


def test_an_adjudication_bound_to_other_packet_bytes_is_stale(tmp_path):
    env = _split_env(tmp_path)
    good = AdjudicationRecord.model_validate(adjudicate(env)["record"])
    adjudications_path(env.state_root).unlink()
    append_adjudications(env.state_root, [good.model_copy(update={"packet_sha256": "f" * 64})])
    result = status(env)
    assert result["adjudications"][0]["stale"] is True
    assert result["status"] == STATUS_SPLIT


# ======================================================================= the adjudication ledger


def test_a_duplicate_adjudication_line_is_ledger_corrupt_everywhere(tmp_path):
    env = _split_env(tmp_path)
    record = AdjudicationRecord.model_validate(adjudicate(env)["record"])
    append_adjudications(env.state_root, [record])           # same (packet, item, dim, revision)
    with pytest.raises(LedgerCorrupt, match="line 2.*already appears at line 1"):
        read_adjudications(env.state_root)
    with pytest.raises(LedgerCorrupt):
        status(env)
    refused = adjudicate(env)
    assert refused["status"] == "refused" and any("ledger corrupt" in p for p in refused["problems"])


@pytest.mark.parametrize("line", [
    b"not json",
    b'{"schema_id": "hs-review-adjudication/1"}',
])
def test_a_malformed_adjudication_line_is_ledger_corrupt_naming_the_line(tmp_path, line):
    env = _split_env(tmp_path)
    assert adjudicate(env)["status"] == "ok"
    with open(adjudications_path(env.state_root), "ab") as fh:
        fh.write(line + b"\n")
    with pytest.raises(LedgerCorrupt, match="line 2"):
        read_adjudications(env.state_root)


def test_an_extra_field_on_an_adjudication_line_is_corrupt(tmp_path):
    env = _split_env(tmp_path)
    doc = adjudicate(env)["record"]
    doc["note"] = "smuggled"
    doc["revision"] = 2
    with open(adjudications_path(env.state_root), "ab") as fh:
        fh.write(json.dumps(doc).encode() + b"\n")
    with pytest.raises(LedgerCorrupt, match="line 2"):
        read_adjudications(env.state_root)


def test_adjudication_ledger_reads_nothing_from_a_missing_file_filters_by_packet_and_appends_once(
        tmp_path):
    env = _split_env(tmp_path)
    assert read_adjudications(env.state_root) == []
    append_adjudications(env.state_root, [])
    assert not adjudications_path(env.state_root).exists()
    record = AdjudicationRecord.model_validate(adjudicate(env)["record"])
    other = record.model_copy(update={"packet_id": "pk_" + "2" * 16})
    append_adjudications(env.state_root, [other])
    assert [r.packet_id for r in read_adjudications(env.state_root)] == [PACKET_ID, "pk_" + "2" * 16]
    assert read_adjudications(env.state_root, packet_id=PACKET_ID) == [record]
    # the other packet's adjudication never settles anything here
    assert len(status(env)["adjudications"]) == 1
