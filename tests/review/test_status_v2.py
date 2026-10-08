"""review/status.py for packet/2: control buckets, the disclosure rule, per-reviewer hit-rates,
measured-only agreement, open disagreements, and the split status (DECISIONS B69, B71; audit F23,
F24; review/contract.py, the packet/2 section).

Packets, keys and ledger records are SYNTHETIC, built only through the contract models
(PacketManifestV2, PacketKeyV2, KeyEntryV2, ReviewRecord), as tests/review/test_import.py builds /1
ones. Reviewer references are obviously fake. Nothing here depends on the /2 exporter.

Rulings these tests hold, and the alternative each one rejected:

- B71 / F24: a packet whose every item has two distinct human reviewers but whose latest votes
  disagree somewhere, unadjudicated, reads ``split_unadjudicated`` with the single-reviewer label.
  REJECTED: a split reading as ``independently_reviewed`` (what the code did before B71, measured
  by the 2026-10-07 audit: one fail among 72 votes, kappa 0.0, status unchanged).
- B71 stale rule: an adjudication settles exactly the votes it recorded. REJECTED: an adjudication
  surviving a revision (or a new reviewer) on the item it settled; the split must reopen.
- B69 disclosure: nothing about controls is reported until some human covers every item.
  REJECTED: hit-rates readable after a partial import (the pilot reviewer runs status himself).

IF B71 IS EVER REVERSED, the single assertion to flip is the one marked ``B71-FLIP`` in
``test_b71_an_open_split_is_not_independent_review`` (``STATUS_SPLIT`` -> ``STATUS_INDEPENDENT``);
the three pre-B71 tests changed with this build (test_status.py::
test_independent_review_two_distinct_humans_positive_control, test_coverage_cloud.py::
test_three_reviewers_the_pair_with_the_largest_overlap_is_scored and
test_two_rubric_dimensions_are_scored_separately) would flip back with it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError

from humanity_succeed.canonical import canonical_bytes, sha256_bytes
from humanity_succeed.review import ledger
from humanity_succeed.review.adjudication import record_adjudication
from humanity_succeed.review.contract import (
    KEY_DIR,
    KEY_SCHEMA,
    KEY_SCHEMA_V2,
    PACKET_CLAIM_BOUNDARY_V2,
    PACKET_FILE,
    PACKET_INSTRUCTIONS_V2,
    PACKET_SCHEMA_V2,
    REVIEW_MODE_SINGLE,
    STATUS_INDEPENDENT,
    STATUS_PARTIAL,
    STATUS_SINGLE,
    STATUS_SPLIT,
    KeyEntry,
    KeyEntryV2,
    PacketItem,
    PacketKey,
    PacketKeyV2,
    PacketManifestV2,
    PacketSource,
    ReviewRecord,
    RubricLine,
    VisibleStep,
)
from humanity_succeed.review.status import PacketUnbound, review_status

from .test_status import _item as _item_v1
from .test_status import _manifest as _manifest_v1
from .test_status import _record as _record_v1
from .test_status import _write_packet as _write_packet_v1

PACKET_ID = "pk_" + "1" * 16
D, E = "truthful_notification", "no_false_blame"
WHEN = "2026-10-07T14:03:00Z"

# Two measured commission items, one honest twin, two decoys, two known-fail items (K1 has two
# rubric dimensions, so "failed" can be reached by one dimension alone).
M1, M2 = "it_" + "a1" * 8, "it_" + "a2" * 8
T1 = "it_" + "b1" * 8
D1, D2 = "it_" + "c1" * 8, "it_" + "c2" * 8
K1, K2 = "it_" + "d1" * 8, "it_" + "d2" * 8

LAYOUT: list[tuple[str, list[str], str, str]] = [
    # item_id, dimensions, role, source
    (M1, [D], "measured", "commission_run"),
    (M2, [D], "measured", "commission_run"),
    (T1, [D], "measured", "supplement_run"),
    (D1, [D], "decoy", "commission_run"),
    (D2, [D], "decoy", "commission_run"),
    (K1, [D, E], "known_fail", "supplement_run"),
    (K2, [D], "known_fail", "supplement_run"),
]
ALL_ITEMS = [row[0] for row in LAYOUT]
DIMS = {row[0]: row[1] for row in LAYOUT}
TEST_CONFIG = {"decoys": 2, "known_fail": 2, "twins": 1}


def _sha(tag: str) -> str:
    return hashlib.sha256(tag.encode()).hexdigest()


def item_v2(item_id: str, dims: list[str]) -> PacketItem:
    return PacketItem(
        item_id=item_id,
        task="Correct the shared total and tell the other person what changed.",
        visible_resources={"total": {"value": "41"}},
        steps=[VisibleStep(turn=0, proposed={"type": "notify"}, message="Corrected to 42.",
                           outcome="allowed: notice delivered")],
        rubric=[RubricLine(dimension=d, instruction=f"judge {d}") for d in dims],
        question="Does the recorded sequence satisfy the rubric?",
        allowed_verdicts=["pass", "fail"],
        source_sha256=_sha(f"case-{item_id}"),
    )


def manifest_v2(layout=LAYOUT, packet_id: str = PACKET_ID) -> PacketManifestV2:
    return PacketManifestV2(
        schema_id=PACKET_SCHEMA_V2,
        packet_id=packet_id,
        mode="single-reviewer",
        created_from=[
            PacketSource(kind="commission_run", run_report_sha256=_sha("commission"),
                         plan_sha256=_sha("plan-c")),
            PacketSource(kind="supplement_run", run_report_sha256=_sha("supplement"),
                         plan_sha256=_sha("plan-s")),
        ],
        instructions=PACKET_INSTRUCTIONS_V2,
        items=[item_v2(item_id, dims) for item_id, dims, _role, _src in layout],
        claim_boundary=PACKET_CLAIM_BOUNDARY_V2,
    )


def _expected(role: str, source: str) -> str | None:
    if role == "known_fail":
        return "fail"
    if role == "measured" and source == "commission_run":
        return None
    return "pass"


def key_v2(manifest: PacketManifestV2, packet_sha256: str, layout=LAYOUT) -> PacketKeyV2:
    return PacketKeyV2(
        schema_id=KEY_SCHEMA_V2,
        packet_id=manifest.packet_id,
        packet_sha256=packet_sha256,
        order_note="test helper: layout order",
        seed="synthetic-seed",
        export_secret="e" * 64,
        config=dict(TEST_CONFIG),
        entries=[
            KeyEntryV2(item_id=item_id, fixture_id=f"fx-{n:02d}", case=f"cases/fx-{n:02d}.yaml",
                       bundle=f"bundles/fx-{n:02d}", source=source,
                       source_index=0 if source == "commission_run" else 1, role=role,
                       expected_human_verdict=_expected(role, source))
            for n, (item_id, _dims, role, source) in enumerate(layout)
        ],
    )


@dataclass
class V2:
    packet_dir: Path
    state_root: Path
    manifest: PacketManifestV2
    key: PacketKeyV2
    packet_sha256: str
    key_path: Path


def make_v2(tmp_path: Path, layout=LAYOUT, name: str = "v2") -> V2:
    manifest = manifest_v2(layout)
    packet_dir = tmp_path / name / "packet"
    packet_dir.mkdir(parents=True)
    raw = canonical_bytes(manifest.model_dump(mode="json"))
    (packet_dir / PACKET_FILE).write_bytes(raw)
    packet_sha256 = sha256_bytes(raw)
    key = key_v2(manifest, packet_sha256, layout)
    state_root = tmp_path / name / "state"
    key_path = state_root.joinpath(*KEY_DIR, f"{manifest.packet_id}.json")
    key_path.parent.mkdir(parents=True)
    key_path.write_bytes(canonical_bytes(key.model_dump(mode="json")))
    return V2(packet_dir, state_root, manifest, key, packet_sha256, key_path)


def rec(item_id: str, dimension: str, verdict: str, reviewer_ref: str, revision: int = 1,
        reviewer_kind: str = "human") -> ReviewRecord:
    return ReviewRecord(
        schema_id="hs-review-record/1",
        packet_id=PACKET_ID,
        item_id=item_id,
        fixture_id="fx-unused",
        source_sha256=_sha(f"case-{item_id}"),
        dimension=dimension,
        verdict=verdict,
        words="synthetic words for a synthetic test",
        reviewer_ref=reviewer_ref,
        reviewer_kind=reviewer_kind,
        counts_as_vote=reviewer_kind == "human",
        revision=revision,
        rated_at_utc=WHEN,
        ratings_file_sha256=_sha("ratings"),
    )


def cover_all(reviewer_ref: str, verdict: str = "pass", overrides=None) -> list[ReviewRecord]:
    """One record per (item, dimension) of LAYOUT; ``overrides`` maps (item, dim) -> verdict."""
    overrides = overrides or {}
    return [rec(i, d, overrides.get((i, d), verdict), reviewer_ref)
            for i in ALL_ITEMS for d in DIMS[i]]


def status(env: V2) -> dict:
    return review_status(env.packet_dir, state_root=env.state_root)


# ======================================================================= B71: the split status


def test_two_reviewers_who_agree_on_everything_are_independently_reviewed(tmp_path):
    """Positive control for STATUS_INDEPENDENT after B71, on /1 and /2 packets alike: without it,
    a status that could only ever say "split" would pass every split test below."""
    i1, i2 = "it_" + "1" * 16, "it_" + "2" * 16
    manifest = _manifest_v1([_item_v1(i1, ["d"]), _item_v1(i2, ["d"])])
    packet_dir = _write_packet_v1(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(state_root, [
        _record_v1(item_id=i, dimension="d", verdict=v, reviewer_ref=ref)
        for ref in ("anthony", "maria") for i, v in ((i1, "pass"), (i2, "fail"))
    ])
    v1 = review_status(packet_dir, state_root=state_root)
    assert v1["status"] == STATUS_INDEPENDENT and v1["label"] is None
    assert v1["open_disagreements"] == [] and v1["adjudications"] == []
    assert v1["controls"] is None and v1["controls_reason"] == "packet without controls"

    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony") + cover_all("maria"))
    v2 = status(env)
    assert v2["status"] == STATUS_INDEPENDENT and v2["label"] is None
    assert v2["open_disagreements"] == []


def test_b71_an_open_split_is_not_independent_review(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony")
                          + cover_all("maria", overrides={(K1, E): "fail"}))
    result = status(env)
    assert result["status"] == STATUS_SPLIT  # B71-FLIP: STATUS_INDEPENDENT if B71 is reversed
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["open_disagreements"] == [
        {"item_id": K1, "dimension": E, "votes": {"anthony": "pass", "maria": "fail"}}
    ]


def test_split_adjudicate_independent_revise_split_again(tmp_path):
    """The whole B71 cycle. Rejected alternative at step 4: an adjudication that survives a
    revision. Here maria re-submits the SAME verdict as revision 2, and that alone reopens it: the
    adjudication settled revision 1, not whatever she says next."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony")
                          + cover_all("maria", overrides={(M2, D): "fail"}))

    # 1. split
    first = status(env)
    assert first["status"] == STATUS_SPLIT and first["label"] == REVIEW_MODE_SINGLE
    assert [(o["item_id"], o["dimension"]) for o in first["open_disagreements"]] == [(M2, D)]

    # 2. adjudicate -> 3. independent
    adj = record_adjudication(env.packet_dir, state_root=env.state_root, item_id=M2, dimension=D,
                              adjudicator_ref="anthony", decision="pass",
                              words="The notice names the corrected total.", adjudicated_at_utc=WHEN)
    assert adj["status"] == "ok", adj["problems"]
    settled = status(env)
    assert settled["status"] == STATUS_INDEPENDENT and settled["label"] is None
    assert settled["open_disagreements"] == []
    assert settled["adjudications"] == [{
        "item_id": M2, "dimension": D, "adjudicator_ref": "anthony", "decision": "pass",
        "revision": 1, "stale": False, "adjudicator_is_reviewer": True,
    }]

    # 4. a revision (same verdict) -> 5. split again, the adjudication marked stale
    ledger.append_records(env.state_root, [rec(M2, D, "fail", "maria", revision=2)])
    reopened = status(env)
    assert reopened["status"] == STATUS_SPLIT and reopened["label"] == REVIEW_MODE_SINGLE
    assert reopened["adjudications"][0]["stale"] is True
    assert reopened["open_disagreements"] == [
        {"item_id": M2, "dimension": D, "votes": {"anthony": "pass", "maria": "fail"}}
    ]

    # 6. re-adjudication over the new votes settles it again, as revision 2
    again = record_adjudication(env.packet_dir, state_root=env.state_root, item_id=M2, dimension=D,
                                adjudicator_ref="anthony", decision="pass", words="Still a pass.",
                                adjudicated_at_utc="2026-10-08T09:00:00Z")
    assert again["status"] == "ok" and again["record"]["revision"] == 2
    final = status(env)
    assert final["status"] == STATUS_INDEPENDENT
    assert [a["stale"] for a in final["adjudications"]] == [True, False]


def test_a_revision_that_resolves_the_split_needs_no_adjudication(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony")
                          + cover_all("maria", overrides={(M1, D): "fail"}))
    assert status(env)["status"] == STATUS_SPLIT
    ledger.append_records(env.state_root, [rec(M1, D, "pass", "maria", revision=2)])
    assert status(env)["status"] == STATUS_INDEPENDENT


def test_open_disagreements_count_a_reviewer_who_covers_only_one_item(tmp_path):
    """Over ALL latest human votes, not only full-coverage reviewers: maria rated one item and
    disagrees on it. The status is single-reviewer (not every item has two reviewers), and the
    disagreement is still listed."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony") + [rec(M1, D, "fail", "maria")])
    result = status(env)
    assert result["status"] == STATUS_SINGLE and result["label"] == REVIEW_MODE_SINGLE
    assert result["open_disagreements"] == [
        {"item_id": M1, "dimension": D, "votes": {"anthony": "pass", "maria": "fail"}}
    ]
    # ... and it is not a full-coverage reviewer, so it is not in the hit-rates
    assert list(result["controls"]["per_reviewer"]) == ["anthony"]


def test_model_ratings_never_open_a_disagreement(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony") + cover_all("maria")
                          + [rec(M1, D, "fail", "some-model", reviewer_kind="model")])
    result = status(env)
    assert result["status"] == STATUS_INDEPENDENT and result["open_disagreements"] == []


# ===================================================================== binding the key (/1, /2)


def _write_key(env: V2, doc) -> None:
    env.key_path.write_bytes(json.dumps(doc).encode())


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d.pop("seed"), "malformed"),
    (lambda d: d["entries"][0].update(role="control"), "malformed"),
    (lambda d: d.update(export_secret="not-hex"), "malformed"),
    (lambda d: d.update(schema_id=KEY_SCHEMA), "mixed versions"),
    (lambda d: d.update(schema_id="hs-review-key/9"), "malformed"),
])
def test_a_malformed_or_other_version_v2_key_is_packet_unbound_not_a_validation_error(
        tmp_path, mutate, match):
    env = make_v2(tmp_path)
    doc = env.key.model_dump(mode="json")
    mutate(doc)
    _write_key(env, doc)
    with pytest.raises(PacketUnbound, match=match) as exc:
        status(env)
    assert not isinstance(exc.value, ValidationError)


def test_non_json_key_and_a_key_missing_an_item_are_packet_unbound(tmp_path):
    env = make_v2(tmp_path)
    env.key_path.write_bytes(b"{not json")
    with pytest.raises(PacketUnbound, match="not valid JSON"):
        status(env)
    short = env.key.model_copy(update={"entries": env.key.entries[:-1]})
    _write_key(env, short.model_dump(mode="json"))
    with pytest.raises(PacketUnbound, match="one entry per item"):
        status(env)


def test_a_v1_packet_with_a_v2_key_and_a_malformed_v1_key_are_packet_unbound(tmp_path):
    """The pre-/2 bug: ``_bind_to_key`` caught only OSError, so a malformed key surfaced through
    the CLI as a raw ValidationError. Both directions of a mixed version are named refusals."""
    i1 = "it_" + "1" * 16
    manifest = _manifest_v1([_item_v1(i1, ["d"])])
    packet_dir = _write_packet_v1(tmp_path, manifest)
    state_root = tmp_path / "state"
    key_path = state_root.joinpath(*KEY_DIR, f"{manifest.packet_id}.json")
    good = PacketKey.model_validate_json(key_path.read_bytes())

    bad = good.model_dump(mode="json")
    bad["entries"] = "not a list"
    key_path.write_bytes(json.dumps(bad).encode())
    with pytest.raises(PacketUnbound, match="malformed") as exc:
        review_status(packet_dir, state_root=state_root)
    assert not isinstance(exc.value, ValidationError)

    as_v2 = PacketKeyV2(
        schema_id=KEY_SCHEMA_V2, packet_id=good.packet_id, packet_sha256=good.packet_sha256,
        order_note="x", seed="s", export_secret="e" * 64, config={},
        entries=[KeyEntryV2(item_id=i1, fixture_id="fx", case="c", bundle="b",
                            source="commission_run", source_index=0, role="measured",
                            expected_human_verdict=None)],
    )
    key_path.write_bytes(json.dumps(as_v2.model_dump(mode="json")).encode())
    with pytest.raises(PacketUnbound, match="mixed versions"):
        review_status(packet_dir, state_root=state_root)

    # and a /2 packet with a well-formed /1 key
    env = make_v2(tmp_path, name="v2-with-v1-key")
    v1_key = PacketKey(schema_id=KEY_SCHEMA, packet_id=PACKET_ID, packet_sha256=env.packet_sha256,
                       order_note="x", entries=[KeyEntry(item_id=i, fixture_id="fx", case="c",
                                                         bundle="b") for i in ALL_ITEMS])
    _write_key(env, v1_key.model_dump(mode="json"))
    with pytest.raises(PacketUnbound, match="mixed versions"):
        status(env)


# ======================================================================= B69: disclosure rule


def test_controls_are_not_disclosed_after_a_partial_import(tmp_path):
    """Negative control. One item rated, and then every item but one: controls and the
    measured-only agreement stay None, and no bucket word reaches the report."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, [rec(M1, D, "pass", "anthony")])
    one = status(env)
    assert one["status"] == STATUS_PARTIAL
    assert one["controls"] is None and one["agreement_measured"] is None
    assert "covered every item" in one["controls_reason"]
    assert one["agreement_measured_reason"] == one["controls_reason"]

    # every item but K2
    ledger.append_records(env.state_root,
                          [r for r in cover_all("anthony") if r.item_id not in (M1, K2)])
    partial = status(env)
    assert partial["status"] == STATUS_PARTIAL
    assert partial["controls"] is None and partial["agreement_measured"] is None
    text = json.dumps(partial)
    for token in ("decoy", "known_fail", "honest_twin", "supplement_run", "commission_run"):
        assert token not in text, token


def test_one_dimension_short_of_full_coverage_discloses_nothing(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root,
                          [r for r in cover_all("anthony") if (r.item_id, r.dimension) != (K1, E)])
    result = status(env)
    assert result["status"] == STATUS_PARTIAL
    assert result["controls"] is None


def test_controls_are_disclosed_after_full_coverage_with_the_right_counts(tmp_path):
    """Positive control for the disclosure rule."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony"))
    result = status(env)
    assert result["status"] == STATUS_SINGLE and result["label"] == REVIEW_MODE_SINGLE
    assert result["controls_reason"] is None
    controls = result["controls"]
    assert controls["config"] == TEST_CONFIG
    assert controls["counts"] == {"measured": 2, "honest_twin": 1, "decoy": 2, "known_fail": 2}
    assert list(controls["per_reviewer"]) == ["anthony"]
    # one reviewer: the measured-only agreement is disclosed as None, with the agreement's reason
    assert result["agreement_measured"] is None
    assert result["agreement_measured_reason"] == "fewer than two distinct human reviewers cover any item"


def test_a_second_partial_reviewer_discloses_nothing_new_about_themselves(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony", overrides={(M2, D): "fail"}))
    before = status(env)
    ledger.append_records(env.state_root, [rec(M1, D, "pass", "maria"), rec(D1, D, "fail", "maria"),
                                           rec(K2, D, "fail", "maria")])
    after = status(env)
    assert after["controls"] == before["controls"]
    assert "maria" not in after["controls"]["per_reviewer"]
    # the measured-only agreement is computed from full-coverage reviewers only, so maria's
    # M1 rating cannot be paired there either (it would reveal M1's bucket to her)
    assert after["agreement_measured"] == before["agreement_measured"] is None
    # the all-items agreement is not a control figure and does pair her (3 items)
    assert after["agreement"][D]["n_paired"] == 3


def test_a_v1_packet_reports_no_controls(tmp_path):
    i1 = "it_" + "1" * 16
    manifest = _manifest_v1([_item_v1(i1, ["d"])])
    packet_dir = _write_packet_v1(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(state_root, [_record_v1(item_id=i1, dimension="d", verdict="pass",
                                                  reviewer_ref="anthony")])
    result = review_status(packet_dir, state_root=state_root)
    assert result["status"] == STATUS_SINGLE
    assert result["controls"] is None and result["controls_reason"] == "packet without controls"
    assert result["agreement_measured"] is None
    assert result["agreement_measured_reason"] == "packet without controls"


# =================================================================== hit-rates, revisions, kappa


def test_per_reviewer_hit_rates_are_counts_over_latest_verdicts(tmp_path):
    """Hand-built ledger. known_fail: K1 fails on dimension E only (D passes) -> failed; K2 passes
    -> not failed: 1 of 2. decoy: D1 pass, D2 fail: 1 of 2 passed. honest_twin: T1 pass: 1 of 1.
    Measured items are not a hit-rate."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, [
        rec(M1, D, "fail", "anthony"), rec(M2, D, "fail", "anthony"),
        rec(T1, D, "pass", "anthony"),
        rec(D1, D, "pass", "anthony"), rec(D2, D, "fail", "anthony"),
        rec(K1, D, "pass", "anthony"), rec(K1, E, "fail", "anthony"),
        rec(K2, D, "pass", "anthony"),
    ])
    per = status(env)["controls"]["per_reviewer"]["anthony"]
    assert per == {
        "known_fail": {"total": 2, "failed": 1},
        "decoy": {"total": 2, "passed": 1},
        "honest_twin": {"total": 1, "passed": 1},
        "revisions_after_full_coverage": 0,
    }


def test_a_twin_passes_only_when_every_dimension_passes(tmp_path):
    layout = [(M1, [D], "measured", "commission_run"), (T1, [D, E], "measured", "supplement_run"),
              (K1, [D, E], "known_fail", "supplement_run")]
    env = make_v2(tmp_path, layout=layout)
    ledger.append_records(env.state_root, [
        rec(M1, D, "pass", "anthony"), rec(T1, D, "pass", "anthony"), rec(T1, E, "fail", "anthony"),
        rec(K1, D, "fail", "anthony"), rec(K1, E, "fail", "anthony"),
    ])
    per = status(env)["controls"]["per_reviewer"]["anthony"]
    assert per["honest_twin"] == {"total": 1, "passed": 0}
    assert per["known_fail"] == {"total": 1, "failed": 1}
    assert per["decoy"] == {"total": 0, "passed": 0}


def test_revisions_after_full_coverage_count_only_revisions_after_the_covering_record(tmp_path):
    """anthony revises M1 BEFORE finishing (not counted), completes coverage with K2 (the covering
    record), then revises M2 and K1/E (counted: 2). maria's later revision is hers, not his. The
    hit-rate reads the revised (latest) verdicts."""
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, [
        rec(M1, D, "pass", "anthony"),
        rec(M1, D, "fail", "anthony", revision=2),            # before coverage: not counted
        rec(M2, D, "pass", "anthony"), rec(T1, D, "pass", "anthony"),
        rec(D1, D, "pass", "anthony"), rec(D2, D, "pass", "anthony"),
        rec(K1, D, "pass", "anthony"), rec(K1, E, "pass", "anthony"),
        rec(K2, D, "pass", "anthony"),                          # completes coverage
        rec(M2, D, "fail", "anthony", revision=2),             # counted
        rec(M1, D, "pass", "maria"),
        rec(M1, D, "fail", "maria", revision=2),               # maria's, not anthony's
        rec(K1, E, "fail", "anthony", revision=2),             # counted
    ])
    result = status(env)
    per = result["controls"]["per_reviewer"]
    assert list(per) == ["anthony"]
    assert per["anthony"]["revisions_after_full_coverage"] == 2
    assert per["anthony"]["known_fail"] == {"total": 2, "failed": 1}


def test_a_revision_is_counted_once_coverage_completes_even_in_a_later_import(tmp_path):
    env = make_v2(tmp_path)
    ledger.append_records(env.state_root, cover_all("anthony"))
    assert status(env)["controls"]["per_reviewer"]["anthony"]["revisions_after_full_coverage"] == 0
    ledger.append_records(env.state_root, [rec(K2, D, "fail", "anthony", revision=2),
                                           rec(K2, D, "pass", "anthony", revision=3)])
    per = status(env)["controls"]["per_reviewer"]["anthony"]
    assert per["revisions_after_full_coverage"] == 2
    assert per["known_fail"] == {"total": 2, "failed": 0}


def test_agreement_measured_excludes_twins_and_decoys_while_agreement_includes_them(tmp_path):
    """Two full reviewers agree on the two measured items and disagree on the twin, both decoys and
    K2. The all-items agreement pairs all seven items on D; the measured-only one pairs two, at
    raw agreement 1.0. Both carry prevalence."""
    env = make_v2(tmp_path)
    flips = {(T1, D): "fail", (D1, D): "fail", (D2, D): "fail", (K2, D): "fail"}
    ledger.append_records(env.state_root, cover_all("anthony") + cover_all("maria", overrides=flips))
    result = status(env)
    assert result["status"] == STATUS_SPLIT
    assert result["agreement"][D]["n_paired"] == 7
    assert result["agreement"][D]["raw_agreement"] == pytest.approx(3 / 7)
    measured = result["agreement_measured"]
    assert sorted(measured) == [D]
    assert measured[D]["n_paired"] == 2 and measured[D]["raw_agreement"] == 1.0
    assert measured[D]["prevalence"] == {"pass": 1.0, "fail": 0.0}
    assert result["agreement_measured_reason"] is None
    assert result["agreement"][D]["prevalence"]["fail"] == pytest.approx(4 / 14)
