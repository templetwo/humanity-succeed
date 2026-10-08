"""Adjudication of a split between two reviewers' latest votes (DECISIONS B71; audit F24; PROTOCOL
§9 "adjudicated by a named procedure"; review/contract.py ``AdjudicationRecord``).

``record_adjudication`` appends ONE ``AdjudicationRecord`` to its own append-only file
(``ADJUDICATIONS_PATH``). It never opens the review ledger for writing and never rewrites a
reviewer's verdict: an adjudication is a separate, named decision, not a third rating. It records
every latest human vote on the (item, dimension) it settles; ``review/status.py`` treats it as stale
the moment that set of votes changes in any way (a revision by either side, a new reviewer), and the
split is open again.

Anthony is the named adjudicator (B71), and for the pilot he may also be one of the reviewers ("for
the pilot it can be you"): a reference literally identical to a recorded reviewer is allowed and
status reports ``adjudicator_is_reviewer``. A reference that names a recorded reviewer only after
case, whitespace or Unicode normalisation is refused, as the importer refuses it for ratings (B61):
one person is one reference.

Everything is checked before anything is appended (all-or-nothing). No code path here fabricates a
decision or words; both come from the caller, who is the operator typing the adjudicator's own.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..canonical import StrictLoadError
from .contract import ADJUDICATION_SCHEMA, VERDICTS, AdjudicatedVote, AdjudicationRecord
from .identity import reviewer_ref_problem, same_reviewer
from .importer import _RATED_AT_UTC
from .ledger import LedgerCorrupt, append_adjudications, read_adjudications, read_records
from .status import PacketUnbound, _bind_to_key, _latest_human_votes, _load_packet, votes_on


def _refused(problems: list[str]) -> dict[str, Any]:
    return {"status": "refused", "record": None, "problems": list(problems)}


def record_adjudication(
    packet_path: Path,
    *,
    state_root: Path,
    item_id: str,
    dimension: str,
    adjudicator_ref: str,
    decision: str,
    words: str,
    adjudicated_at_utc: str,
) -> dict[str, Any]:
    """Record one adjudication of a disagreeing (item, dimension). Returns
    ``{"status": "ok"|"refused", "record": <the appended record as JSON> | None, "problems"}``."""
    # 1. The packet, bound to its operator key (same binding as status; a malformed, missing or
    #    other-version key is refused by name).
    try:
        manifest, packet_sha256 = _load_packet(packet_path)
    except OSError as e:
        return _refused([f"cannot read packet {packet_path}: {e.strerror or e}"])
    except (StrictLoadError, ValidationError) as e:
        return _refused([f"invalid packet manifest {packet_path}: {e}"])
    try:
        key = _bind_to_key(state_root, manifest, packet_sha256)
    except PacketUnbound as e:
        return _refused([f"packet not bound to its operator key: {e}"])

    # 2. The caller's own inputs. Every input and identity problem is named together (steps 2-5);
    #    the split itself is checked only once the inputs are sound.
    problems: list[str] = []
    ref_problem = reviewer_ref_problem(adjudicator_ref)
    if ref_problem:
        problems.append(f"adjudicator {ref_problem}")
    if decision not in VERDICTS:
        problems.append(f"decision {decision!r} is not one of {', '.join(VERDICTS)} (B70)")
    if not words.strip():
        problems.append("blank words: the adjudicator's decision is recorded in their own words")
    try:
        if not _RATED_AT_UTC.fullmatch(adjudicated_at_utc):
            raise ValueError(adjudicated_at_utc)
        datetime.fromisoformat(adjudicated_at_utc)
    except ValueError:
        problems.append(
            f"adjudicated_at_utc {adjudicated_at_utc!r} is not an ISO 8601 UTC timestamp "
            "(for example 2026-10-07T14:03:00Z)"
        )

    # 3. The item and dimension exist in this packet.
    item = next((i for i in manifest.items if i.item_id == item_id), None)
    entry = next((e for e in key.entries if e.item_id == item_id), None)
    if item is None:
        problems.append(f"unknown item_id {item_id!r}")
    elif dimension not in {line.dimension for line in item.rubric}:
        problems.append(f"unknown dimension {dimension!r} for item {item_id!r}")
    elif entry is None:
        problems.append(f"no operator-key entry for item {item_id!r}")

    # 4. The ledgers. A corrupt line in either is a named refusal, never a skip.
    try:
        all_records = read_records(state_root)
        all_adjudications = read_adjudications(state_root)
    except LedgerCorrupt as e:
        return _refused([f"ledger corrupt: {e}"])

    # 5. Adjudicator identity is ledger-wide (B61), as the importer's reviewer check is.
    recorded_refs = {rec.reviewer_ref for rec in all_records}
    recorded_refs |= {a.adjudicator_ref for a in all_adjudications}
    colliding = sorted(r for r in recorded_refs if r != adjudicator_ref and same_reviewer(r, adjudicator_ref))
    if colliding:
        problems.append(
            f"adjudicator_ref {adjudicator_ref!r} collides with recorded reference "
            f"{', '.join(repr(c) for c in colliding)}: the same person once case, whitespace and "
            "Unicode form are normalised. Reuse the recorded reference exactly, or choose a clearly "
            "distinct one (B61)"
        )
    model_kind = sorted({rec.reviewer_ref for rec in all_records
                         if rec.reviewer_ref == adjudicator_ref and rec.reviewer_kind != "human"})
    if model_kind:
        problems.append(
            f"adjudicator_ref {adjudicator_ref!r} is recorded as a model reviewer; an adjudicator is "
            "a named human (B71, PROTOCOL §9)"
        )

    if problems:
        return _refused(problems)
    assert item is not None and entry is not None

    # 6. There must be a split to settle: >= 2 distinct humans' latest votes, and they differ.
    packet_records = [rec for rec in all_records if rec.packet_id == manifest.packet_id]
    latest, _collisions, _ref_problems = _latest_human_votes(packet_records)
    votes = votes_on(latest, item_id, dimension)
    if len(votes) < 2:
        problems.append(
            f"item {item_id!r} dimension {dimension!r} has {len(votes)} distinct human reviewer(s); "
            "adjudication needs at least two whose latest votes disagree"
        )
    elif len({rec.verdict for rec in votes.values()}) < 2:
        problems.append(
            f"the latest human votes on item {item_id!r} dimension {dimension!r} agree "
            f"({', '.join(sorted(votes))}); there is no disagreement to adjudicate"
        )
    if problems:
        return _refused(problems)

    revision = 1 + sum(1 for a in all_adjudications if a.packet_id == manifest.packet_id
                       and a.item_id == item_id and a.dimension == dimension)
    record = AdjudicationRecord(
        schema_id=ADJUDICATION_SCHEMA,
        packet_id=manifest.packet_id,
        packet_sha256=packet_sha256,
        item_id=item_id,
        fixture_id=entry.fixture_id,
        source_sha256=item.source_sha256,
        dimension=dimension,
        adjudicator_ref=adjudicator_ref,
        adjudicator_kind="human",
        reviewers=[
            AdjudicatedVote(reviewer_ref=name, verdict=votes[name].verdict,
                            revision=votes[name].revision)
            for name in sorted(votes)
        ],
        decision=decision,
        words=words,
        adjudicated_at_utc=adjudicated_at_utc,
        revision=revision,
    )
    append_adjudications(state_root, [record])
    return {"status": "ok", "record": record.model_dump(mode="json"), "problems": []}


__all__ = ["record_adjudication"]
