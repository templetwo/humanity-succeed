"""review/importer.py: strict import of a reviewer's own-words ratings (BUILD_SPEC §11; B60/B61).

Fixtures are built only through the real contract models (PacketManifest, PacketKey, RatingsFile,
Rating, ...), never as hand-written dicts, so a schema mistake in a fixture fails loudly at
construction time rather than silently proving nothing. Where a test needs a document the real
models would refuse to construct (a blank template field, a corrupted hash), it starts from a
valid model's ``model_dump`` and mutates exactly the one field under test.

The export module is not depended on here: packets and keys are built directly from
review/contract.py, matching "do NOT depend on the export module being written in parallel."
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from humanity_succeed.review.contract import (
    KEY_DIR,
    KEY_SCHEMA,
    PACKET_FILE,
    PACKET_SCHEMA,
    RATINGS_SCHEMA,
    RECORD_SCHEMA,
    KeyEntry,
    PacketItem,
    PacketKey,
    PacketManifest,
    Rating,
    RatingsFile,
    ReviewRecord,
    RubricLine,
    VisibleStep,
)
from humanity_succeed.review.importer import import_ratings
from humanity_succeed.review.ledger import append_records, ledger_path, read_records

ITEM_A = "it_" + "a" * 16
ITEM_B = "it_" + "b" * 16
PACKET_ID = "pk_" + "1" * 16
OTHER_PACKET_ID = "pk_" + "2" * 16
DIM_A = "truthful_notification"
DIM_B = "calibrated_disclosure"


def _sha(tag: str) -> str:
    return hashlib.sha256(tag.encode()).hexdigest()


def _item(item_id: str, dimension: str, source_tag: str) -> PacketItem:
    return PacketItem(
        item_id=item_id,
        task="Read the resource and respond to the subject's task.",
        visible_resources={"r1": {"value": "42"}},
        steps=[
            VisibleStep(
                turn=0,
                proposed={"tool": "notify", "args": {}},
                message="Corrected and notified.",
                outcome="allowed: resource revised, notice delivered",
            )
        ],
        rubric=[RubricLine(dimension=dimension, instruction=f"Judge {dimension} on the record above.")],
        question=f"Does the record satisfy {dimension}?",
        allowed_verdicts=["pass", "fail"],
        source_sha256=_sha(source_tag),
    )


def _manifest(packet_id: str) -> PacketManifest:
    return PacketManifest(
        schema_id=PACKET_SCHEMA,
        packet_id=packet_id,
        mode="single-reviewer",
        created_from={"run_report_sha256": _sha("report"), "plan_sha256": _sha("plan")},
        instructions="Read each item, then answer its rubric question in your own words.",
        items=[_item(ITEM_A, DIM_A, "item-a"), _item(ITEM_B, DIM_B, "item-b")],
        claim_boundary="Constructed fixtures; not a population claim.",
    )


def _key_entries() -> list[KeyEntry]:
    return [
        KeyEntry(item_id=ITEM_A, fixture_id="c1-g01-real_correction", case="cases/c1-g01.yaml",
                 bundle="bundles/c1-g01-real_correction"),
        KeyEntry(item_id=ITEM_B, fixture_id="c2-g01-direct", case="cases/c2-g01.yaml",
                 bundle="bundles/c2-g01-direct"),
    ]


@dataclass
class Env:
    state_root: Path
    export_dir: Path
    packet_path: Path
    packet_sha256: str
    manifest: PacketManifest
    key: PacketKey


def make_env(tmp_path: Path, name: str = "pkt", packet_id: str = PACKET_ID) -> Env:
    manifest = _manifest(packet_id)
    export_dir = tmp_path / name / "export"
    export_dir.mkdir(parents=True)
    # Deliberately non-canonical formatting (indented, insertion order) on disk: if the importer
    # ever hashed a re-dump of the validated model instead of these literal bytes, this would
    # produce a different hash and every "should succeed" test below would fail loudly.
    raw = (json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=False) + "\n").encode()
    packet_path = export_dir / PACKET_FILE
    packet_path.write_bytes(raw)
    packet_sha256 = hashlib.sha256(raw).hexdigest()

    state_root = tmp_path / name / "state"
    key = PacketKey(
        schema_id=KEY_SCHEMA,
        packet_id=packet_id,
        packet_sha256=packet_sha256,
        order_note="ordered by sha256(packet_id, item_id)",
        entries=_key_entries(),
    )
    key_file = Path(state_root).joinpath(*KEY_DIR, f"{packet_id}.json")
    key_file.parent.mkdir(parents=True)
    key_file.write_bytes(json.dumps(key.model_dump(mode="json")).encode())

    return Env(state_root, export_dir, packet_path, packet_sha256, manifest, key)


def _ratings(env: Env, ratings: list[Rating], *, reviewer_ref: str = "anthony-vasquez-sr",
             reviewer_kind: str = "human", rated_at: str = "2026-09-28T00:00:00Z") -> RatingsFile:
    return RatingsFile(
        schema_id=RATINGS_SCHEMA,
        packet_id=env.manifest.packet_id,
        packet_sha256=env.packet_sha256,
        reviewer_ref=reviewer_ref,
        reviewer_kind=reviewer_kind,
        rated_at_utc=rated_at,
        ratings=ratings,
    )


def _write_json(path: Path, doc: dict) -> Path:
    path.write_bytes(json.dumps(doc).encode())
    return path


def _write_ratings(env: Env, ratings: RatingsFile, filename: str = "ratings.json") -> Path:
    return _write_json(env.export_dir.parent / filename, ratings.model_dump(mode="json"))


def _ledger_bytes(env: Env) -> bytes:
    p = ledger_path(env.state_root)
    return p.read_bytes() if p.exists() else b""


# ---------------------------------------------------------------------------------- happy paths


def test_valid_human_import_appends_records_with_counts_as_vote_true(tmp_path):
    env = make_env(tmp_path)
    ratings = _ratings(env, [
        Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="Notice matched the state."),
        Rating(item_id=ITEM_B, dimension=DIM_B, verdict="fail", words="Too vague to be calibrated."),
    ])
    ratings_path = _write_ratings(env, ratings)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result == {"status": "ok", "recorded": 2, "votes": 2, "secondary": 0, "problems": []}
    records = read_records(env.state_root, packet_id=env.manifest.packet_id)
    assert len(records) == 2
    by_item = {r.item_id: r for r in records}
    assert by_item[ITEM_A].fixture_id == "c1-g01-real_correction"
    assert by_item[ITEM_A].source_sha256 == env.manifest.items[0].source_sha256
    assert by_item[ITEM_B].fixture_id == "c2-g01-direct"
    for r in records:
        assert r.counts_as_vote is True
        assert r.revision == 1
        assert r.reviewer_ref == "anthony-vasquez-sr"
        assert r.ratings_file_sha256 == hashlib.sha256(ratings_path.read_bytes()).hexdigest()


def test_packet_path_may_be_the_packet_json_file_itself(tmp_path):
    env = make_env(tmp_path)
    ratings = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="ok")])
    ratings_path = _write_ratings(env, ratings)

    result = import_ratings(env.packet_path, ratings_path, state_root=env.state_root)

    assert result["status"] == "ok"
    assert result["recorded"] == 1


def test_ratings_file_may_be_yaml(tmp_path):
    env = make_env(tmp_path, name="yaml")
    ratings = _ratings(env, [
        Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass",
               words="Delivered before the mutation window closed."),
    ])
    ratings_path = env.export_dir.parent / "ratings.yaml"
    ratings_path.write_text(yaml.safe_dump(ratings.model_dump(mode="json"), sort_keys=False))

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "ok"
    assert result["recorded"] == 1


def test_model_ratings_are_recorded_secondary_not_a_vote(tmp_path):
    env = make_env(tmp_path, name="model-reviewer")
    ratings = _ratings(
        env,
        [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="Model judges this a pass.")],
        reviewer_ref="critique-model-x",
        reviewer_kind="model",
    )
    ratings_path = _write_ratings(env, ratings)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result == {"status": "ok", "recorded": 1, "votes": 0, "secondary": 1, "problems": []}
    records = read_records(env.state_root, packet_id=env.manifest.packet_id)
    assert records[0].counts_as_vote is False
    assert records[0].reviewer_kind == "model"


# ---------------------------------------------------------------------------------- refusals


def test_blank_words_after_strip_refuses_the_whole_file(tmp_path):
    env = make_env(tmp_path, name="blank-strip")
    ratings = _ratings(env, [
        Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="fine"),
        Rating(item_id=ITEM_B, dimension=DIM_B, verdict="fail", words="   "),  # non-empty, blank after strip
    ])
    ratings_path = _write_ratings(env, ratings)
    before = _ledger_bytes(env)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "refused"
    assert result["recorded"] == 0
    assert any("blank words" in p for p in result["problems"])
    assert _ledger_bytes(env) == before == b""


def test_schema_level_blank_words_template_is_refused_not_raised(tmp_path):
    """A hand-edited template that left ``words`` empty fails RatingsFile's own strict schema
    (min_length=1); the importer must turn that into a refusal, never an uncaught exception."""
    env = make_env(tmp_path, name="blank-template")
    valid = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="placeholder")])
    doc = valid.model_dump(mode="json")
    doc["ratings"][0]["words"] = ""
    ratings_path = _write_json(env.export_dir.parent / "ratings.json", doc)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "refused"
    assert result["recorded"] == 0
    assert result["problems"]
    assert not ledger_path(env.state_root).exists()


def test_unknown_item_id_refused(tmp_path):
    env = make_env(tmp_path, name="unknown-item")
    ratings = _ratings(env, [Rating(item_id="it_" + "9" * 16, dimension=DIM_A, verdict="pass", words="ok")])
    ratings_path = _write_ratings(env, ratings)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "refused"
    assert any("unknown item_id" in p for p in result["problems"])
    assert not ledger_path(env.state_root).exists()


def test_unknown_dimension_refused(tmp_path):
    env = make_env(tmp_path, name="unknown-dim")
    ratings = _ratings(env, [Rating(item_id=ITEM_A, dimension="not_a_rubric_dimension",
                                     verdict="pass", words="ok")])
    ratings_path = _write_ratings(env, ratings)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "refused"
    assert any("unknown dimension" in p for p in result["problems"])
    assert not ledger_path(env.state_root).exists()


def test_duplicate_item_dimension_in_one_file_refused(tmp_path):
    env = make_env(tmp_path, name="dup-pair")
    ratings = _ratings(env, [
        Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="first"),
        Rating(item_id=ITEM_A, dimension=DIM_A, verdict="fail", words="second"),
    ])
    ratings_path = _write_ratings(env, ratings)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "refused"
    assert any("duplicate" in p for p in result["problems"])
    assert not ledger_path(env.state_root).exists()


def test_wrong_packet_sha256_refused(tmp_path):
    env = make_env(tmp_path, name="wrong-hash")
    ratings = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="ok")])
    bad = ratings.model_copy(update={"packet_sha256": "0" * 64})
    ratings_path = _write_ratings(env, bad)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "refused"
    assert any("packet_sha256" in p for p in result["problems"])
    assert not ledger_path(env.state_root).exists()


def test_missing_key_refused(tmp_path):
    env = make_env(tmp_path, name="missing-key")
    key_file = Path(env.state_root).joinpath(*KEY_DIR, f"{env.manifest.packet_id}.json")
    key_file.unlink()
    ratings = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="ok")])
    ratings_path = _write_ratings(env, ratings)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "refused"
    assert any("key" in p.lower() for p in result["problems"])
    assert not ledger_path(env.state_root).exists()


def test_key_hash_mismatch_refused(tmp_path):
    env = make_env(tmp_path, name="key-hash-mismatch")
    key_file = Path(env.state_root).joinpath(*KEY_DIR, f"{env.manifest.packet_id}.json")
    bad_key = env.key.model_copy(update={"packet_sha256": "f" * 64})
    key_file.write_bytes(json.dumps(bad_key.model_dump(mode="json")).encode())
    ratings = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="ok")])
    ratings_path = _write_ratings(env, ratings)

    result = import_ratings(env.export_dir, ratings_path, state_root=env.state_root)

    assert result["status"] == "refused"
    assert any("operator key" in p for p in result["problems"])
    assert not ledger_path(env.state_root).exists()


# ---------------------------------------------------------------------------------- revisions


def test_second_import_same_reviewer_gives_revision_2_scoped_to_this_packet(tmp_path):
    env = make_env(tmp_path, name="scoped-revision")
    # Seed the ledger with an UNRELATED packet's records for the very same reviewer/item/dimension.
    # A bug that scoped revision-counting by (item_id, dimension, reviewer_ref) alone -- ignoring
    # packet_id -- would still coincidentally produce revision 2 below; this seed catches it.
    unrelated_1 = ReviewRecord(
        schema_id=RECORD_SCHEMA, packet_id=OTHER_PACKET_ID, item_id=ITEM_A,
        fixture_id="other-fixture", source_sha256=_sha("other-source"), dimension=DIM_A,
        verdict="pass", words="unrelated packet, revision 1", reviewer_ref="anthony-vasquez-sr",
        reviewer_kind="human", counts_as_vote=True, revision=1, rated_at_utc="2026-01-01T00:00:00Z",
        ratings_file_sha256=_sha("other-ratings-1"),
    )
    unrelated_2 = unrelated_1.model_copy(update={
        "words": "unrelated packet, revision 2", "revision": 2,
        "ratings_file_sha256": _sha("other-ratings-2"),
    })
    append_records(env.state_root, [unrelated_1, unrelated_2])

    ratings1 = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="first pass")])
    r1_path = _write_ratings(env, ratings1, "r1.json")
    first = import_ratings(env.export_dir, r1_path, state_root=env.state_root)
    assert first["status"] == "ok"
    recs = read_records(env.state_root, packet_id=env.manifest.packet_id)
    assert len(recs) == 1
    assert recs[0].revision == 1

    ratings2 = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass",
                                      words="revised wording, same verdict")])
    r2_path = _write_ratings(env, ratings2, "r2.json")
    second = import_ratings(env.export_dir, r2_path, state_root=env.state_root)
    assert second["status"] == "ok"

    recs = read_records(env.state_root, packet_id=env.manifest.packet_id)
    assert sorted(r.revision for r in recs) == [1, 2]
    # Still exactly one reviewer_ref for this packet: a re-review is a revision, never a new reviewer.
    assert {r.reviewer_ref for r in recs} == {"anthony-vasquez-sr"}


def test_ledger_is_append_only_earlier_lines_survive_a_later_import(tmp_path):
    env = make_env(tmp_path, name="append-only")
    r1 = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="first review")])
    first = import_ratings(env.export_dir, _write_ratings(env, r1, "r1.json"), state_root=env.state_root)
    assert first["status"] == "ok"
    before = _ledger_bytes(env)

    r2 = _ratings(env, [Rating(item_id=ITEM_B, dimension=DIM_B, verdict="fail", words="second reviewer")],
                  reviewer_ref="second-reviewer")
    second = import_ratings(env.export_dir, _write_ratings(env, r2, "r2.json"), state_root=env.state_root)
    assert second["status"] == "ok"

    after = _ledger_bytes(env)
    assert after.startswith(before)
    assert len(after) > len(before)


def test_corrupted_ledger_line_refuses_naming_the_line_number(tmp_path):
    env = make_env(tmp_path, name="corrupt-ledger")
    r1 = _ratings(env, [Rating(item_id=ITEM_A, dimension=DIM_A, verdict="pass", words="first review")])
    first = import_ratings(env.export_dir, _write_ratings(env, r1, "r1.json"), state_root=env.state_root)
    assert first["status"] == "ok"

    lp = ledger_path(env.state_root)
    assert len(lp.read_bytes().splitlines()) == 1
    lp.write_bytes(b"not valid json at all\n")

    r2 = _ratings(env, [Rating(item_id=ITEM_B, dimension=DIM_B, verdict="pass", words="second review")])
    result = import_ratings(env.export_dir, _write_ratings(env, r2, "r2.json"), state_root=env.state_root)

    assert result["status"] == "refused"
    assert result["recorded"] == 0
    assert any("line 1" in p for p in result["problems"])
