"""Tests for review/status.py and commissioning.agreement.agreement_between_reviewers
(BUILD_SPEC §11; DECISIONS B60/B61; ruling 06d942da).

All packets and ledger records here are synthetic, built directly through
``review.ledger.append_records`` -- these tests do not depend on a packet exporter or ratings
importer existing yet. The real committed run (docs/receipts/wp3/run) has 36 judgment-heavy
fixtures that are each single-dimension and every event permission=allow/result=ok, so it cannot
exercise multi-dimension coverage or a genuine two-distinct-humans path; both are built here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from humanity_succeed.canonical import canonical_bytes, sha256_bytes
from humanity_succeed.commissioning.agreement import agreement_between_reviewers
from humanity_succeed.review import ledger
from humanity_succeed.review.contract import (
    KEY_DIR,
    PACKET_FILE,
    REVIEW_MODE_SINGLE,
    STATUS_INDEPENDENT,
    STATUS_PARTIAL,
    STATUS_PENDING,
    STATUS_SCHEMA,
    STATUS_SINGLE,
    STATUS_SPLIT,
    KeyEntry,
    PacketItem,
    PacketKey,
    PacketManifest,
    ReviewRecord,
    RubricLine,
    VisibleStep,
)
from humanity_succeed.review.ledger import LedgerCorrupt
from humanity_succeed.review.status import PacketUnbound, review_status

PACKET_ID = "pk_" + "a" * 16
ITEM_1 = "it_" + "1" * 16
ITEM_2 = "it_" + "2" * 16
SHA = "0" * 64


def _step() -> VisibleStep:
    return VisibleStep(turn=0, proposed={"type": "notify"}, message=None, outcome="allowed: ok")


def _item(item_id: str, dims: list[str]) -> PacketItem:
    return PacketItem(
        item_id=item_id,
        task="do the thing without leaking anything",
        visible_resources={},
        steps=[_step()],
        rubric=[RubricLine(dimension=d, instruction=f"judge {d}") for d in dims],
        question="does the visible sequence satisfy the rubric?",
        allowed_verdicts=["pass", "fail"],
        source_sha256=SHA,
    )


def _manifest(items: list[PacketItem]) -> PacketManifest:
    return PacketManifest(
        schema_id="hs-review-packet/1",
        packet_id=PACKET_ID,
        mode="single-reviewer",
        created_from={"run_report_sha256": SHA, "plan_sha256": SHA},
        instructions="rate each dimension pass or fail, in your own words",
        items=items,
        claim_boundary="single-operator pilot; not independently reviewed unless stated",
    )


def _write_packet(tmp_path, manifest: PacketManifest, state_root=None):
    """Write packet.json AND the operator key under the state root (default ``tmp_path/state``):
    since the 2026-10-07 red-team's D2, ``review_status`` refuses a manifest whose bytes are not the
    ones the key records for its packet_id."""
    packet_dir = tmp_path / "packet"
    packet_dir.mkdir()
    raw = canonical_bytes(manifest.model_dump(mode="json"))
    (packet_dir / PACKET_FILE).write_bytes(raw)
    key = PacketKey(
        schema_id="hs-review-key/1",
        packet_id=manifest.packet_id,
        packet_sha256=sha256_bytes(raw),
        order_note="test helper: manifest order",
        entries=[
            KeyEntry(item_id=item.item_id, fixture_id=f"fx-{n:02d}", case=f"cases/fx-{n:02d}.yaml",
                     bundle=f"bundles/fx-{n:02d}")
            for n, item in enumerate(manifest.items)
        ],
    )
    key_path = Path(state_root or tmp_path / "state").joinpath(*KEY_DIR, f"{manifest.packet_id}.json")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(canonical_bytes(key.model_dump(mode="json")))
    return packet_dir


def _record(
    *,
    item_id: str,
    dimension: str,
    verdict: str,
    reviewer_ref: str,
    reviewer_kind: str = "human",
    counts_as_vote: bool | None = None,
    revision: int = 1,
    rated_at_utc: str = "2026-01-01T00:00:00Z",
) -> ReviewRecord:
    if counts_as_vote is None:
        counts_as_vote = reviewer_kind == "human"
    return ReviewRecord(
        schema_id="hs-review-record/1",
        packet_id=PACKET_ID,
        item_id=item_id,
        fixture_id="fx-unused",
        source_sha256=SHA,
        dimension=dimension,
        verdict=verdict,
        words="my own words, bound to the case hash",
        reviewer_ref=reviewer_ref,
        reviewer_kind=reviewer_kind,
        counts_as_vote=counts_as_vote,
        revision=revision,
        rated_at_utc=rated_at_utc,
        ratings_file_sha256=SHA,
    )


# --------------------------------------------------------------------------------- status states


def test_pending_no_human_reviews(tmp_path):
    manifest = _manifest([_item(ITEM_1, ["truthful_notification"])])
    packet_dir = _write_packet(tmp_path, manifest)
    result = review_status(packet_dir, state_root=tmp_path / "state")

    assert result["schema_id"] == STATUS_SCHEMA
    assert result["status"] == STATUS_PENDING
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["distinct_human_reviewers"] == []
    assert result["agreement"] is None
    assert result["reason"]
    assert result["items"][0]["human_reviewers"] == []


def test_single_reviewer_partial(tmp_path):
    manifest = _manifest(
        [_item(ITEM_1, ["truthful_notification"]), _item(ITEM_2, ["truthful_notification"])]
    )
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [_record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                  reviewer_ref="anthony")],
    )

    result = review_status(packet_dir, state_root=state_root)

    assert result["status"] == STATUS_PARTIAL
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["agreement"] is None


def test_single_reviewer_reviewed(tmp_path):
    manifest = _manifest(
        [_item(ITEM_1, ["truthful_notification"]), _item(ITEM_2, ["truthful_notification"])]
    )
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="fail",
                     reviewer_ref="anthony"),
        ],
    )

    result = review_status(packet_dir, state_root=state_root)

    assert result["status"] == STATUS_SINGLE
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["distinct_human_reviewers"] == ["anthony"]
    assert result["agreement"] is None
    assert result["reason"]


def test_independent_review_two_distinct_humans_positive_control(tmp_path):
    """Proves the independent path can fire at all -- trust the key-safeguard negative test below
    only once this positive control is known to pass (see the advisory on this build item)."""
    manifest = _manifest(
        [_item(ITEM_1, ["truthful_notification"]), _item(ITEM_2, ["truthful_notification"])]
    )
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="fail",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="maria"),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="maria"),
        ],
    )

    result = review_status(packet_dir, state_root=state_root)

    # B71 (audit F24): ITEM_2 is fail/pass with no adjudication, so the split is open and the
    # packet is not independently reviewed; the independent positive control now lives in
    # tests/review/test_status_v2.py (two reviewers who agree on everything).
    assert result["status"] == STATUS_SPLIT
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["distinct_human_reviewers"] == ["anthony", "maria"]
    assert result["agreement"] is not None
    dim_result = result["agreement"]["truthful_notification"]
    assert sorted(dim_result["reviewers"]) == ["anthony", "maria"]
    assert dim_result["n_paired"] == 2
    assert dim_result["raw_agreement"] == 0.5  # item1 pass/pass matches, item2 fail/pass does not


def test_repeated_reviewer_never_becomes_independent_key_safeguard(tmp_path):
    """THE KEY SAFEGUARD: one reviewer_ref rating every item twice (as a revision) must never be
    counted as two reviewers. Also proves 'latest' is decided by the revision integer, never by
    comparing rated_at_utc strings: revision 2 here carries an EARLIER-looking timestamp than
    revision 1, and its verdict must still win."""
    manifest = _manifest(
        [_item(ITEM_1, ["truthful_notification"]), _item(ITEM_2, ["truthful_notification"])]
    )
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="fail",
                     reviewer_ref="anthony", revision=1, rated_at_utc="2026-05-01T00:00:00Z"),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="fail",
                     reviewer_ref="anthony", revision=1, rated_at_utc="2026-05-01T00:00:00Z"),
            # revision 2: the actual revision by number, but its timestamp string sorts BEFORE
            # revision 1's -- a timestamp-based "latest" bug would keep revision 1 here.
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony", revision=2, rated_at_utc="2020-01-01T00:00:00Z"),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony", revision=2, rated_at_utc="2020-01-01T00:00:00Z"),
        ],
    )

    result = review_status(packet_dir, state_root=state_root)

    assert result["status"] == STATUS_SINGLE
    assert result["status"] != STATUS_INDEPENDENT
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["distinct_human_reviewers"] == ["anthony"]
    assert result["agreement"] is None
    item1 = next(r for r in result["items"] if r["item_id"] == ITEM_1)
    assert item1["verdicts"]["anthony"]["truthful_notification"] == "pass"


def test_partial_dimension_coverage_does_not_count_as_covering(tmp_path):
    """An item with two rubric dimensions is covered only when a reviewer answered BOTH; the real
    36-fixture dataset is single-dimension throughout and cannot exercise this branch at all."""
    manifest = _manifest([_item(ITEM_1, ["truthful_notification", "clarity"])])
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [_record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                  reviewer_ref="anthony")],
    )

    result = review_status(packet_dir, state_root=state_root)

    assert result["status"] == STATUS_PENDING
    item1 = result["items"][0]
    assert item1["human_reviewers"] == []
    assert "anthony" not in item1["verdicts"]


def test_non_covering_second_reviewer_still_labels_single_reviewer(tmp_path):
    """A second, distinct human reviewer_ref who never fully covers ANY item (here: rates only one
    of item2's two rubric dimensions) must not suppress the single-reviewer label. The label tracks
    the STATUS (every item covered by only one human end-to-end -> STATUS_SINGLE), never a bare
    count of reviewer_ref values seen anywhere in the ledger -- otherwise an incomplete second
    reviewer could make a single-reviewer result look independently reviewed."""
    manifest = _manifest(
        [_item(ITEM_1, ["truthful_notification"]), _item(ITEM_2, ["truthful_notification", "clarity"])]
    )
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_2, dimension="clarity", verdict="pass",
                     reviewer_ref="anthony"),
            # maria only partially rates item2 (one of its two dimensions) -- never covers
            # anything, and must not count as a second reviewer for the label.
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="fail",
                     reviewer_ref="maria"),
        ],
    )

    result = review_status(packet_dir, state_root=state_root)

    assert result["status"] == STATUS_SINGLE
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["agreement"] is None


def test_model_ratings_never_count_toward_coverage_or_reviewers(tmp_path):
    manifest = _manifest([_item(ITEM_1, ["truthful_notification"])])
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="gpt-judge", reviewer_kind="model", counts_as_vote=False),
        ],
    )

    result = review_status(packet_dir, state_root=state_root)

    assert result["status"] == STATUS_PENDING
    assert result["distinct_human_reviewers"] == []
    assert result["items"][0]["human_reviewers"] == []
    assert result["secondary_ratings"] == 1
    assert result["agreement"] is None


def test_ledger_corrupt_propagates_never_a_silent_empty_result(tmp_path):
    manifest = _manifest([_item(ITEM_1, ["truthful_notification"])])
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger_file = ledger.ledger_path(state_root)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)  # the helper already wrote the key beside it
    ledger_file.write_text("not json at all\n", encoding="utf-8")

    with pytest.raises(LedgerCorrupt):
        review_status(packet_dir, state_root=state_root)


# ------------------------------------------------------------------- agreement_between_reviewers


def test_agreement_between_reviewers_matches_agreement_plus_reviewers():
    result = agreement_between_reviewers(
        "anthony", ["pass", "fail"], "maria", ["pass", "pass"], ["pass", "fail"]
    )

    assert result["reviewers"] == ["anthony", "maria"]
    assert result["n_paired"] == 2
    assert result["raw_agreement"] == 0.5


def test_agreement_between_reviewers_refuses_equal_reviewer_ref():
    with pytest.raises(ValueError, match="refuses equal reviewer_ref"):
        agreement_between_reviewers("anthony", ["pass"], "anthony", ["pass"], ["pass", "fail"])


def test_agreement_between_reviewers_refuses_empty_reviewer_ref():
    with pytest.raises(ValueError, match="non-empty reviewer_ref"):
        agreement_between_reviewers("", ["pass"], "maria", ["pass"], ["pass", "fail"])
    with pytest.raises(ValueError, match="non-empty reviewer_ref"):
        agreement_between_reviewers("anthony", ["pass"], "", ["pass"], ["pass", "fail"])


def test_agreement_between_reviewers_shape_bug_distinguishable_from_refusal():
    """A mismatched-length shape bug raises a ValueError from agreement() itself, with a message
    that must not be confused with the same-reviewer / empty-reviewer refusal above."""
    with pytest.raises(ValueError, match="equal length") as exc_info:
        agreement_between_reviewers(
            "anthony", ["pass", "fail"], "maria", ["pass"], ["pass", "fail"]
        )
    assert "refuses equal reviewer_ref" not in str(exc_info.value)


# ------------------------------------------------- reviewer identity (B61; audit of 2026-10-07)


def test_case_and_whitespace_variants_of_one_reviewer_never_become_independent(tmp_path):
    """Measured on 2026-10-07 against the real packet: a ledger holding 'anthony' and 'Anthony '
    reported independently_reviewed with no label and an agreement block. Colliding references are
    one reviewer here, the status stays single-reviewer, and the collision is reported, not hidden."""
    manifest = _manifest(
        [_item(ITEM_1, ["truthful_notification"]), _item(ITEM_2, ["truthful_notification"])]
    )
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="fail",
                     reviewer_ref="Anthony "),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="fail",
                     reviewer_ref="ANTHONY"),
        ],
    )

    result = review_status(packet_dir, state_root=state_root)

    assert result["status"] == STATUS_SINGLE
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["distinct_human_reviewers"] == ["anthony"]
    assert result["agreement"] is None
    # "ANTHONY" collides with "anthony" (one reviewer, reported); "Anthony " is untidy and, since
    # the red-team's D3, is excluded from votes and named as a problem rather than merged
    assert result["reviewer_ref_collisions"] == [["ANTHONY", "anthony"]]
    assert list(result["reviewer_ref_problems"]) == ["Anthony "]
    # the later ledger line wins a same-revision tie between colliding literals, under the first name
    item2 = next(r for r in result["items"] if r["item_id"] == ITEM_2)
    assert item2["human_reviewers"] == ["anthony"]
    assert item2["verdicts"]["anthony"]["truthful_notification"] == "fail"
    item1 = next(r for r in result["items"] if r["item_id"] == ITEM_1)
    assert item1["verdicts"]["anthony"]["truthful_notification"] == "pass"


def test_distinct_reviewers_report_no_collisions(tmp_path):
    manifest = _manifest([_item(ITEM_1, ["truthful_notification"])])
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="maria"),
        ],
    )
    result = review_status(packet_dir, state_root=state_root)
    assert result["status"] == STATUS_INDEPENDENT
    assert result["reviewer_ref_collisions"] == []


@pytest.mark.parametrize("variant", ["Anthony", "anthony ", "ANTHONY", "Ａnthony"])
def test_agreement_between_reviewers_refuses_canonically_equal_reviewer_refs(variant):
    with pytest.raises(ValueError, match="same reviewer"):
        agreement_between_reviewers("anthony", ["pass"], variant, ["pass"], ["pass", "fail"])


# ----------------------------------------------- red-team 2026-10-07 (docs/audits/cloud/redteam-identity)


def test_status_is_bound_to_the_operator_key_and_refuses_a_trimmed_or_altered_manifest(tmp_path):
    """D2: a trimmed copy of packet.json (same packet_id, fewer items) was reported as
    independently_reviewed from a ledger in which the second reviewer covered a fraction of the
    items. Status now binds the manifest bytes to the key's packet_sha256 and reports the hash."""
    manifest = _manifest(
        [_item(ITEM_1, ["truthful_notification"]), _item(ITEM_2, ["truthful_notification"])]
    )
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_2, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="bob"),
        ],
    )
    full = review_status(packet_dir, state_root=state_root)
    assert full["status"] == STATUS_SINGLE
    assert full["packet_sha256"] == sha256_bytes((packet_dir / PACKET_FILE).read_bytes())

    trimmed_dir = tmp_path / "trimmed"
    trimmed_dir.mkdir()
    trimmed = manifest.model_copy(update={"items": [manifest.items[0]]})
    (trimmed_dir / PACKET_FILE).write_bytes(canonical_bytes(trimmed.model_dump(mode="json")))
    with pytest.raises(PacketUnbound, match="sha256"):
        review_status(trimmed_dir, state_root=state_root)

    with pytest.raises(PacketUnbound, match="no operator key"):
        review_status(packet_dir, state_root=tmp_path / "elsewhere")


def test_a_legacy_lookalike_reference_is_excluded_and_reported_never_counted(tmp_path):
    """D3: a ledger holding a Cyrillic look-alike reference (admitted before the charset rule)
    counted it as a human; an ASCII reference then imported as a second one. Such records are now
    excluded from votes and named under reviewer_ref_problems."""
    manifest = _manifest([_item(ITEM_1, ["truthful_notification"])])
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="\u0430nthony"),
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
        ],
    )
    result = review_status(packet_dir, state_root=state_root)
    assert result["status"] == STATUS_SINGLE
    assert result["label"] == REVIEW_MODE_SINGLE
    assert result["distinct_human_reviewers"] == ["anthony"]
    assert result["agreement"] is None
    assert list(result["reviewer_ref_problems"]) == ["\u0430nthony"]
    assert "outside ASCII" in result["reviewer_ref_problems"]["\u0430nthony"]


def test_punctuation_variants_of_one_reviewer_are_one_reviewer_in_status(tmp_path):
    """D1 at the status layer: 'anthony' and 'anthony.' in a ledger are one reviewer."""
    manifest = _manifest([_item(ITEM_1, ["truthful_notification"])])
    packet_dir = _write_packet(tmp_path, manifest)
    state_root = tmp_path / "state"
    ledger.append_records(
        state_root,
        [
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="pass",
                     reviewer_ref="anthony"),
            _record(item_id=ITEM_1, dimension="truthful_notification", verdict="fail",
                     reviewer_ref="anthony."),
        ],
    )
    result = review_status(packet_dir, state_root=state_root)
    assert result["status"] == STATUS_SINGLE
    assert result["distinct_human_reviewers"] == ["anthony"]
    assert result["reviewer_ref_collisions"] == [["anthony", "anthony."]]
    assert result["agreement"] is None
