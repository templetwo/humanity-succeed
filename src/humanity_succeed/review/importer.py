"""Strict import of a reviewer's own-words ratings into the append-only ledger.

BUILD_SPEC §11; DECISIONS B60, B61; ruling 06d942da; review/contract.py.

All validation happens BEFORE any append (all-or-nothing): a malformed packet, ratings file,
operator key, or rating refuses the whole ratings file and appends nothing. No code path here
fabricates or defaults a verdict or words -- every ``ReviewRecord`` is built only from what the
reviewer actually wrote, bound to the exact packet and operator key that were checked.

``packet_sha256`` is always computed from the raw bytes read off disk for ``packet.json``, never
from re-serializing the validated ``PacketManifest``, so an export that ever drifted from its own
manifest bytes would be caught here rather than silently accepted.

Revisions are numbered per ``(packet_id, item_id, dimension, reviewer_ref)`` from what the ledger
already holds; nothing here rewrites or removes an existing line. A corrupt ledger line is a named
refusal, never a silent skip past the evidence.

Reviewer identity (B61, ``review/identity.py``): a ``reviewer_ref`` with stray whitespace, or one
that names an already-recorded reviewer under case/whitespace/Unicode normalisation without
matching it exactly, is refused before anything is appended. The 2026-10-07 audit measured that
``"anthony"`` followed by ``"Anthony "`` reached ``independently_reviewed``; this closes that.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..canonical import StrictLoadError, load_document, sha256_bytes, strict_json_loads
from .contract import (
    KEY_DIR,
    PACKET_FILE,
    RECORD_SCHEMA,
    PacketKey,
    PacketManifest,
    RatingsFile,
    ReviewRecord,
)
from .identity import is_tidy_reviewer_ref, same_reviewer
from .ledger import LedgerCorrupt, append_records, read_records


def _refused(problems: list[str]) -> dict[str, Any]:
    return {"status": "refused", "recorded": 0, "votes": 0, "secondary": 0, "problems": list(problems)}


def _key_path(state_root: Path, packet_id: str) -> Path:
    return Path(state_root).joinpath(*KEY_DIR, f"{packet_id}.json")


def import_ratings(packet_path: Path, ratings_path: Path, *, state_root: Path) -> dict[str, Any]:
    """Validate a reviewer's ratings against their packet and operator key, then append one
    ``ReviewRecord`` per rating to the append-only ledger.

    ``packet_path`` may be the export directory (its ``packet.json`` is read) or the
    ``packet.json`` file itself. ``ratings_path`` may be JSON or YAML.

    Returns ``{"status": "ok"|"refused", "recorded", "votes", "secondary", "problems"}``. On
    refusal, ``problems`` names every reason found and nothing is appended.
    """
    packet_path = Path(packet_path)
    packet_json_path = packet_path / PACKET_FILE if packet_path.is_dir() else packet_path

    # 1. The packet manifest: hash the RAW bytes read off disk, then validate those same bytes.
    try:
        packet_bytes = packet_json_path.read_bytes()
    except OSError as e:
        return _refused([f"cannot read packet {packet_json_path}: {e.strerror or e}"])
    packet_sha256 = sha256_bytes(packet_bytes)
    try:
        manifest = PacketManifest.model_validate(strict_json_loads(packet_bytes), strict=True)
    except (StrictLoadError, ValidationError) as e:
        return _refused([f"invalid packet manifest {packet_json_path}: {e}"])

    # 2. The ratings file (JSON or YAML). A template with a blank verdict/words literal fails
    #    RatingsFile's strict schema here and is refused, never silently coerced.
    ratings_path = Path(ratings_path)
    try:
        ratings_bytes = ratings_path.read_bytes()
    except OSError as e:
        return _refused([f"cannot read ratings file {ratings_path}: {e.strerror or e}"])
    ratings_file_sha256 = sha256_bytes(ratings_bytes)
    try:
        ratings = RatingsFile.model_validate(load_document(ratings_path), strict=True)
    except (StrictLoadError, ValidationError) as e:
        return _refused([f"invalid ratings file {ratings_path}: {e}"])

    problems: list[str] = []
    if not is_tidy_reviewer_ref(ratings.reviewer_ref):
        problems.append(
            f"reviewer_ref {ratings.reviewer_ref!r} has leading, trailing or repeated whitespace; "
            "type the stable identity reference exactly (B61)"
        )
    try:
        datetime.fromisoformat(ratings.rated_at_utc)
    except ValueError:
        problems.append(
            f"rated_at_utc {ratings.rated_at_utc!r} is not an ISO 8601 timestamp "
            "(for example 2026-10-07T14:03:00Z)"
        )
    if ratings.packet_id != manifest.packet_id:
        problems.append(
            f"ratings packet_id {ratings.packet_id!r} != packet manifest packet_id "
            f"{manifest.packet_id!r}"
        )
    if ratings.packet_sha256 != packet_sha256:
        problems.append(
            f"ratings packet_sha256 {ratings.packet_sha256!r} != computed packet hash "
            f"{packet_sha256!r}"
        )
    if problems:
        return _refused(problems)

    # 3. The operator key: never in the export directory, always under state_root.
    key_path = _key_path(state_root, manifest.packet_id)
    try:
        key_bytes = key_path.read_bytes()
    except OSError as e:
        return _refused([f"missing operator key {key_path}: {e.strerror or e}"])
    try:
        key = PacketKey.model_validate(strict_json_loads(key_bytes), strict=True)
    except (StrictLoadError, ValidationError) as e:
        return _refused([f"invalid operator key {key_path}: {e}"])
    if key.packet_id != manifest.packet_id:
        problems.append(
            f"operator key packet_id {key.packet_id!r} != packet manifest packet_id "
            f"{manifest.packet_id!r}"
        )
    if key.packet_sha256 != packet_sha256:
        problems.append(
            f"operator key packet_sha256 {key.packet_sha256!r} != computed packet hash "
            f"{packet_sha256!r}"
        )
    if problems:
        return _refused(problems)

    # 4. Every rating: known item, known dimension for that item, no duplicate (item, dimension)
    #    in this file, non-blank words after stripping, and a key entry to resolve fixture_id from.
    items_by_id = {item.item_id: item for item in manifest.items}
    key_by_item = {entry.item_id: entry for entry in key.entries}
    seen_pairs: set[tuple[str, str]] = set()
    for r in ratings.ratings:
        item = items_by_id.get(r.item_id)
        if item is None:
            problems.append(f"unknown item_id {r.item_id!r}")
            continue
        if r.dimension not in {line.dimension for line in item.rubric}:
            problems.append(f"unknown dimension {r.dimension!r} for item {r.item_id!r}")
            continue
        pair = (r.item_id, r.dimension)
        if pair in seen_pairs:
            problems.append(f"duplicate rating for item {r.item_id!r} dimension {r.dimension!r}")
            continue
        seen_pairs.add(pair)
        if not r.words.strip():
            problems.append(f"blank words for item {r.item_id!r} dimension {r.dimension!r}")
            continue
        if r.item_id not in key_by_item:
            problems.append(f"no operator-key entry for item {r.item_id!r}")
            continue
    if problems:
        return _refused(problems)

    # 5. Existing ledger state for this packet, to number revisions. A corrupt line anywhere in
    #    the ledger is a named refusal, never a silent skip (ledger.py: "do not guess past it").
    try:
        all_records = read_records(state_root)
    except LedgerCorrupt as e:
        return _refused([f"ledger corrupt: {e}"])
    existing = [rec for rec in all_records if rec.packet_id == manifest.packet_id]

    # 5b. Reviewer identity is ledger-wide, not per packet (B61). A reference that names an
    #     already-recorded reviewer once case, whitespace and Unicode form are normalised, without
    #     matching it byte for byte, is ambiguous: refuse it and name the collision. The operator
    #     reuses the recorded reference or chooses a clearly distinct one; nothing is merged for
    #     them (review/identity.py).
    colliding = sorted({
        rec.reviewer_ref for rec in all_records
        if rec.reviewer_ref != ratings.reviewer_ref
        and same_reviewer(rec.reviewer_ref, ratings.reviewer_ref)
    })
    if colliding:
        return _refused([
            f"reviewer_ref {ratings.reviewer_ref!r} collides with recorded reviewer_ref "
            f"{', '.join(repr(c) for c in colliding)}: the same reviewer once case, whitespace and "
            "Unicode form are normalised. Reuse the recorded reference exactly, or choose a clearly "
            "distinct one (B61)"
        ])

    counts_as_vote = ratings.reviewer_kind == "human"
    records: list[ReviewRecord] = []
    for r in ratings.ratings:
        entry = key_by_item[r.item_id]
        item = items_by_id[r.item_id]
        prior = sum(
            1
            for rec in existing
            if rec.item_id == r.item_id
            and rec.dimension == r.dimension
            and rec.reviewer_ref == ratings.reviewer_ref
        )
        records.append(
            ReviewRecord(
                schema_id=RECORD_SCHEMA,
                packet_id=manifest.packet_id,
                item_id=r.item_id,
                fixture_id=entry.fixture_id,
                source_sha256=item.source_sha256,
                dimension=r.dimension,
                verdict=r.verdict,
                words=r.words,
                reviewer_ref=ratings.reviewer_ref,
                reviewer_kind=ratings.reviewer_kind,
                counts_as_vote=counts_as_vote,
                revision=prior + 1,
                rated_at_utc=ratings.rated_at_utc,
                ratings_file_sha256=ratings_file_sha256,
            )
        )

    # 6. Append all at once; nothing above this line ever touched the ledger.
    append_records(state_root, records)
    votes = sum(1 for rec in records if rec.counts_as_vote)
    secondary = len(records) - votes
    return {
        "status": "ok",
        "recorded": len(records),
        "votes": votes,
        "secondary": secondary,
        "problems": [],
    }


__all__ = ["import_ratings"]
