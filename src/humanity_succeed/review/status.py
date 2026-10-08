"""Review status: coverage and agreement computed from actual ledger records (BUILD_SPEC §11;
DECISIONS B60/B61; ruling 06d942da; review/contract.py).

Nothing here writes a human rating -- ``review_status`` only reads the packet manifest (blind, as
exported) and the append-only ledger, and reports what the records actually show. An item is
"covered" by a human reviewer only when that reviewer has a verdict for every rubric dimension of
the item (the latest revision, by ``ReviewRecord.revision``, never by comparing timestamp strings).
Repeated ratings from one ``reviewer_ref`` are revisions, never a second reviewer (B61): the overall
status and the ``agreement`` statistic both require at least two DISTINCT human ``reviewer_ref``
values before either can report anything past "single-reviewer". Model ratings
(``reviewer_kind == "model"``) are tallied separately and never count toward coverage, the distinct
reviewer count, or an agreement calculation.

The output uses item ids only: no fixture id, class id, group id, or anything from ``evaluation.json``
ever reaches this module or its result.

Distinctness is decided on the comparison form of ``reviewer_ref`` (``review/identity.py``): two
references that differ only in case, whitespace or Unicode form are ONE reviewer here, counted once,
and reported under ``reviewer_ref_collisions`` so the operator can see them. The importer refuses
new collisions; this handles any that a ledger already carries, always in the stricter direction.

Packet/2 controls, splits and adjudication (DECISIONS B69, B71; audit F23, F24):

- The packet's ``schema_id`` picks the manifest model, and the operator key must be the matching
  version. A missing, malformed, mismatched-version or mismatched-hash key is ``PacketUnbound``,
  never a raw validation error.
- ``controls`` (hit-rates on the blind control items, as counts) and ``agreement_measured`` stay
  ``None`` until at least one human reviewer covers every item: in the single-operator pilot the
  reviewer runs status himself, and a partial import must not read the controls back. Hit-rates and
  the measured-only agreement are computed from full-coverage reviewers only.
- Over two or more distinct reviewers, an (item, dimension) whose latest votes differ is an open
  disagreement until a non-stale adjudication record settles it; a packet with an open
  disagreement reads ``split_unadjudicated``, never ``independently_reviewed`` (B71).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..canonical import StrictLoadError, sha256_bytes, strict_json_loads
from ..commissioning.agreement import agreement_between_reviewers
from .contract import (
    KEY_DIR,
    PACKET_FILE,
    REVIEW_MODE_SINGLE,
    STATUS_INDEPENDENT,
    STATUS_PARTIAL,
    STATUS_PENDING,
    STATUS_SCHEMA,
    STATUS_SINGLE,
    STATUS_SPLIT,
    VERDICTS,
    AdjudicationRecord,
    PacketItem,
    PacketKey,
    PacketKeyV2,
    PacketManifest,
    PacketManifestV2,
    ReviewRecord,
)
from .identity import canonical_reviewer_ref, reviewer_ref_problem, same_reviewer
from .importer import _key_model, _manifest_model, key_version_problem
from .ledger import read_adjudications, read_records

Manifest = PacketManifest | PacketManifestV2
Key = PacketKey | PacketKeyV2

BUCKETS = ("measured", "honest_twin", "decoy", "known_fail")
NO_CONTROLS = "packet without controls"
NOT_YET_DISCLOSED = (
    "no human reviewer has covered every item of the packet yet; controls and the measured-only "
    "agreement are disclosed only after full coverage"
)


class PacketUnbound(ValueError):
    """The packet.json handed to ``review_status`` is not the one the operator key under the state
    root was written for (missing, malformed or other-version key, or a hash mismatch). A status is
    only ever reported for the exact manifest the ledger's records were imported against (red-team
    2026-10-07, D2)."""


def _packet_file(packet_path: Path) -> Path:
    p = Path(packet_path)
    return p / PACKET_FILE if p.is_dir() else p


def _load_packet(packet_path: Path) -> tuple[Manifest, str]:
    p = _packet_file(packet_path)
    raw = p.read_bytes()
    data = strict_json_loads(raw)
    return _manifest_model(data).model_validate(data, strict=True), sha256_bytes(raw)


def _bind_to_key(state_root: Path, manifest: Manifest, packet_sha256: str) -> Key:
    """Refuse a manifest whose bytes are not the ones the operator key records for its packet_id.
    Without this, a trimmed copy of packet.json (same packet_id, fewer items) was reported as
    ``independently_reviewed`` from a ledger in which the second reviewer covered 2 of 36 items.

    A key that cannot be read, does not parse, is the other packet version, or fails its strict
    schema is ``PacketUnbound`` too: before packet/2 only an unreadable key was caught, and a
    malformed one surfaced as a raw ``ValidationError``. For packet/2 the key must also hold exactly
    one entry per manifest item, since every control bucket is read from it."""
    key_path = Path(state_root).joinpath(*KEY_DIR, f"{manifest.packet_id}.json")
    try:
        key_bytes = key_path.read_bytes()
    except OSError as e:
        raise PacketUnbound(f"no operator key for packet {manifest.packet_id} under the state root "
                            f"({key_path}): {e.strerror or e}") from e
    try:
        key_doc = strict_json_loads(key_bytes)
    except StrictLoadError as e:
        raise PacketUnbound(f"operator key {key_path} for packet {manifest.packet_id} is not valid "
                            f"JSON: {e}") from e
    mismatch = key_version_problem(manifest, key_doc)
    if mismatch:
        raise PacketUnbound(f"operator key {key_path}: {mismatch}")
    try:
        key = _key_model(manifest).model_validate(key_doc, strict=True)
    except ValidationError as e:
        raise PacketUnbound(f"operator key {key_path} for packet {manifest.packet_id} is malformed: "
                            f"{e}") from e
    if key.packet_id != manifest.packet_id:
        raise PacketUnbound(f"operator key {key_path} names packet {key.packet_id}, not "
                            f"{manifest.packet_id}")
    if key.packet_sha256 != packet_sha256:
        raise PacketUnbound(f"packet.json sha256 {packet_sha256} != operator key packet_sha256 "
                            f"{key.packet_sha256} for packet {manifest.packet_id}: not the manifest "
                            "the ledger's records were imported against")
    if isinstance(key, PacketKeyV2):
        key_ids = [e.item_id for e in key.entries]
        item_ids = [item.item_id for item in manifest.items]
        if len(set(key_ids)) != len(key_ids) or set(key_ids) != set(item_ids):
            raise PacketUnbound(f"operator key {key_path} does not hold exactly one entry per item "
                                f"of packet {manifest.packet_id}; control buckets cannot be read")
    return key


def _latest_human_votes(
    records: list[ReviewRecord],
) -> tuple[dict[tuple[str, str, str], ReviewRecord], list[list[str]], dict[str, str]]:
    """(item_id, reviewer, dimension) -> the highest-revision human, counts-as-vote record, plus
    the list of ``reviewer_ref`` collisions found.

    Model ratings (``reviewer_kind == "model"``) and any record with ``counts_as_vote`` false are
    excluded here entirely, so they can never contribute to coverage or the reviewer count.
    "Latest" is decided strictly by the ``revision`` integer -- never by ``rated_at_utc`` -- because
    that is the field the ledger schema defines as authoritative (review/contract.py: "1 for the
    first record of (reviewer, item, dimension)").

    The reviewer in the key is the FIRST literal ``reviewer_ref`` seen for its comparison form
    (``canonical_reviewer_ref``), so ``"anthony"`` and a later ``"Anthony "`` share one key and are
    never two reviewers (B61). Revisions are numbered per literal reference by the importer, so
    when two colliding literals tie on revision the later ledger line wins; a collision is reported,
    never hidden.
    """
    latest: dict[tuple[str, str, str], ReviewRecord] = {}
    display: dict[str, str] = {}
    literals: dict[str, set[str]] = {}
    problems: dict[str, str] = {}
    for rec in records:
        if rec.reviewer_kind != "human" or not rec.counts_as_vote:
            continue
        # A ledger written before the charset rule may hold a reference the importer would now
        # refuse (a Cyrillic look-alike, say). It is reported and never counted: fail closed.
        problem = reviewer_ref_problem(rec.reviewer_ref)
        if problem:
            problems[rec.reviewer_ref] = problem
            continue
        canon = canonical_reviewer_ref(rec.reviewer_ref)
        name = display.setdefault(canon, rec.reviewer_ref)
        literals.setdefault(canon, set()).add(rec.reviewer_ref)
        key = (rec.item_id, name, rec.dimension)
        current = latest.get(key)
        if (
            current is None
            or rec.revision > current.revision
            or (rec.revision == current.revision and rec.reviewer_ref != current.reviewer_ref)
        ):
            latest[key] = rec
    collisions = sorted(sorted(refs) for refs in literals.values() if len(refs) > 1)
    return latest, collisions, problems


def _item_coverage(
    item: PacketItem, latest: dict[tuple[str, str, str], ReviewRecord]
) -> tuple[list[str], dict[str, dict[str, str]]]:
    """The item's rubric dimensions, and covering-reviewer verdicts (only reviewers who rated
    EVERY dimension of this item are included -- a partial rating never counts as coverage)."""
    dims = sorted({line.dimension for line in item.rubric})
    per_reviewer: dict[str, dict[str, str]] = {}
    for (item_id, reviewer_ref, dimension), rec in latest.items():
        if item_id != item.item_id:
            continue
        per_reviewer.setdefault(reviewer_ref, {})[dimension] = rec.verdict
    covering = {
        ref: verdicts for ref, verdicts in per_reviewer.items() if set(verdicts) >= set(dims)
    }
    return dims, covering


def _agreement_across_packet(
    items: list[PacketItem], covering_by_item: dict[str, dict[str, dict[str, str]]]
) -> tuple[dict[str, dict] | None, str | None]:
    """Agreement, per rubric dimension, over the items two distinct humans BOTH cover -- computed
    only through ``agreement_between_reviewers``, and only when such a pair exists."""
    covered_items_by_reviewer: dict[str, set[str]] = {}
    for item in items:
        for ref in covering_by_item[item.item_id]:
            covered_items_by_reviewer.setdefault(ref, set()).add(item.item_id)
    distinct = sorted(covered_items_by_reviewer)
    if len(distinct) < 2:
        return None, "fewer than two distinct human reviewers cover any item"

    best_pair: tuple[str, str] | None = None
    best_common: set[str] = set()
    for i, ref_a in enumerate(distinct):
        for ref_b in distinct[i + 1 :]:
            common = covered_items_by_reviewer[ref_a] & covered_items_by_reviewer[ref_b]
            if len(common) > len(best_common):
                best_common, best_pair = common, (ref_a, ref_b)
    if best_pair is None or not best_common:
        return None, "no item is covered by two distinct human reviewers"

    ref_a, ref_b = best_pair
    common_items = [item for item in items if item.item_id in best_common]
    dims = sorted({d for item in common_items for d in covering_by_item[item.item_id][ref_a]})

    per_dimension: dict[str, dict] = {}
    for dim in dims:
        ratings_a: list[str | None] = []
        ratings_b: list[str | None] = []
        for item in common_items:
            if dim not in covering_by_item[item.item_id][ref_a]:
                continue
            ratings_a.append(covering_by_item[item.item_id][ref_a].get(dim))
            ratings_b.append(covering_by_item[item.item_id][ref_b].get(dim))
        per_dimension[dim] = agreement_between_reviewers(
            ref_a, ratings_a, ref_b, ratings_b, list(VERDICTS)
        )
    return per_dimension, None


def votes_on(
    latest: dict[tuple[str, str, str], ReviewRecord], item_id: str, dimension: str
) -> dict[str, ReviewRecord]:
    """Every latest human vote on one (item, dimension), keyed by the reviewer's display name (the
    first literal reference seen for its canonical form)."""
    return {
        name: rec for (i, name, d), rec in latest.items() if i == item_id and d == dimension
    }


def _vote_set(votes: dict[str, ReviewRecord]) -> set[tuple[str, str, int]]:
    return {(canonical_reviewer_ref(name), rec.verdict, rec.revision) for name, rec in votes.items()}


def adjudication_is_stale(
    adj: AdjudicationRecord, latest: dict[tuple[str, str, str], ReviewRecord], packet_sha256: str
) -> bool:
    """B71 stale rule: the set of latest human votes on the adjudicated (item, dimension), as
    (canonical reviewer reference, verdict, revision), must equal the set the adjudication recorded.
    Any difference -- a revision by either side, a new reviewer, a reviewer whose reference is now
    excluded as a problem -- reopens the disagreement. A record bound to other packet bytes is stale
    too (fail closed)."""
    if adj.packet_sha256 != packet_sha256:
        return True
    recorded = {(canonical_reviewer_ref(v.reviewer_ref), v.verdict, v.revision) for v in adj.reviewers}
    return _vote_set(votes_on(latest, adj.item_id, adj.dimension)) != recorded


def _buckets(manifest: Manifest, key: Key) -> dict[str, list[PacketItem]] | None:
    """Items per control bucket, from the operator key; None for a packet/1 key (no controls)."""
    if not isinstance(key, PacketKeyV2):
        return None
    entry_by_item = {e.item_id: e for e in key.entries}
    out: dict[str, list[PacketItem]] = {b: [] for b in BUCKETS}
    for item in manifest.items:
        entry = entry_by_item[item.item_id]
        if entry.role == "measured":
            bucket = "measured" if entry.source == "commission_run" else "honest_twin"
        else:
            bucket = entry.role
        out[bucket].append(item)
    return out


def _covers_packet(name: str, manifest: Manifest, covering_by_item: dict[str, dict]) -> bool:
    return all(name in covering_by_item[item.item_id] for item in manifest.items)


def _revisions_after_full_coverage(name: str, manifest: Manifest, records: list[ReviewRecord]) -> int:
    """How many of this reviewer's records with revision > 1 sit, in ledger line order, after the
    record that first completed the reviewer's coverage of every (item, dimension) of the packet.
    ``records`` is ``read_records`` output, which preserves file order."""
    needed = {(item.item_id, line.dimension) for item in manifest.items for line in item.rubric}
    canon = canonical_reviewer_ref(name)
    seen: set[tuple[str, str]] = set()
    completed_at: int | None = None
    count = 0
    for index, rec in enumerate(records):
        if (
            rec.reviewer_kind != "human"
            or not rec.counts_as_vote
            or reviewer_ref_problem(rec.reviewer_ref)
            or canonical_reviewer_ref(rec.reviewer_ref) != canon
        ):
            continue
        if completed_at is None:
            seen.add((rec.item_id, rec.dimension))
            if needed <= seen:
                completed_at = index
        elif rec.revision > 1:
            count += 1
    return count


def _controls(
    manifest: Manifest,
    key: PacketKeyV2,
    buckets: dict[str, list[PacketItem]],
    covering_by_item: dict[str, dict[str, dict[str, str]]],
    full_reviewers: list[str],
    records: list[ReviewRecord],
) -> dict[str, Any]:
    """Control hit-rates as counts, for full-coverage reviewers only. An item counts for a reviewer
    only when that reviewer covers every rubric dimension of it (``covering_by_item``); "failed"
    means some dimension's latest verdict is fail, "passed" that every one is pass."""
    per_reviewer: dict[str, dict[str, Any]] = {}
    for name in full_reviewers:
        def tally(bucket: str, want: str, _name: str = name) -> dict[str, int]:
            covered = [covering_by_item[item.item_id][_name] for item in buckets[bucket]
                       if _name in covering_by_item[item.item_id]]
            if want == "failed":
                hits = sum(1 for verdicts in covered if "fail" in verdicts.values())
            else:
                hits = sum(1 for verdicts in covered if set(verdicts.values()) == {"pass"})
            return {"total": len(covered), want: hits}

        per_reviewer[name] = {
            "known_fail": tally("known_fail", "failed"),
            "decoy": tally("decoy", "passed"),
            "honest_twin": tally("honest_twin", "passed"),
            "revisions_after_full_coverage": _revisions_after_full_coverage(name, manifest, records),
        }
    return {
        "config": dict(key.config),
        "counts": {b: len(buckets[b]) for b in BUCKETS},
        "per_reviewer": per_reviewer,
    }


def review_status(packet_path: Path, *, state_root: Path) -> dict:
    """Coverage and agreement for one packet, computed from the ledger's actual records.

    ``LedgerCorrupt`` (from ``review.ledger.read_records`` or ``read_adjudications``) is never caught
    here: a malformed ledger line is a refusal, not something this function papers over into an
    empty result.
    """
    manifest, packet_sha256 = _load_packet(packet_path)
    key = _bind_to_key(state_root, manifest, packet_sha256)
    records = read_records(state_root, packet_id=manifest.packet_id)
    adjudications = read_adjudications(state_root, packet_id=manifest.packet_id)

    latest, collisions, ref_problems = _latest_human_votes(records)
    secondary_ratings = sum(1 for rec in records if rec.reviewer_kind == "model")

    items_report = []
    covering_by_item: dict[str, dict[str, dict[str, str]]] = {}
    for item in manifest.items:
        dims, covering = _item_coverage(item, latest)
        covering_by_item[item.item_id] = covering
        items_report.append(
            {
                "item_id": item.item_id,
                "dimensions": dims,
                "human_reviewers": sorted(covering),
                "verdicts": covering,
            }
        )

    # Adjudications and open disagreements (B71). Every latest human vote counts here, not only
    # full-coverage reviewers': a partial reviewer's dissent on one item is still a split.
    stale_by_index = [adjudication_is_stale(a, latest, packet_sha256) for a in adjudications]
    settled = {(a.item_id, a.dimension) for a, stale in zip(adjudications, stale_by_index, strict=True)
               if not stale}
    open_disagreements = []
    for item in manifest.items:
        for dim in sorted({line.dimension for line in item.rubric}):
            votes = votes_on(latest, item.item_id, dim)
            if len(votes) >= 2 and len({rec.verdict for rec in votes.values()}) > 1 \
                    and (item.item_id, dim) not in settled:
                open_disagreements.append({
                    "item_id": item.item_id,
                    "dimension": dim,
                    "votes": {name: votes[name].verdict for name in sorted(votes)},
                })
    adjudications_report = []
    for adj, stale in zip(adjudications, stale_by_index, strict=True):
        voters = [v.reviewer_ref for v in adj.reviewers]
        voters += list(votes_on(latest, adj.item_id, adj.dimension))
        adjudications_report.append({
            "item_id": adj.item_id,
            "dimension": adj.dimension,
            "adjudicator_ref": adj.adjudicator_ref,
            "decision": adj.decision,
            "revision": adj.revision,
            "stale": stale,
            "adjudicator_is_reviewer": any(same_reviewer(adj.adjudicator_ref, v) for v in voters),
        })

    total = len(manifest.items)
    covered = [r for r in items_report if r["human_reviewers"]]
    independent = [r for r in items_report if len(r["human_reviewers"]) >= 2]

    if not covered:
        status = STATUS_PENDING
    elif len(covered) < total:
        status = STATUS_PARTIAL
    elif len(independent) < total:
        status = STATUS_SINGLE
    elif open_disagreements:
        # B71 / audit F24: two reviewers who disagree, unsettled, are not independent review.
        status = STATUS_SPLIT
    else:
        status = STATUS_INDEPENDENT

    distinct_human_reviewers = sorted({name for (_item_id, name, _dimension) in latest})
    # The label must track whether the STATUS itself reflects independent review (every item
    # covered by >=2 distinct humans and no open split), not merely whether a second reviewer_ref
    # appears anywhere in the ledger: a second reviewer who only partially rated an item would
    # otherwise make `len(distinct_human_reviewers) >= 2` true while the report is still built on a
    # single covering reviewer end-to-end -- exactly the undercount B61 exists to prevent. Tying the
    # label to `status` keeps it consistent with the field it is meant to summarize by construction;
    # STATUS_SPLIT keeps the label (B71).
    label = None if status == STATUS_INDEPENDENT else REVIEW_MODE_SINGLE

    agreement_result, agreement_reason = _agreement_across_packet(manifest.items, covering_by_item)

    # Controls (B69). Disclosed only once some human covers every item; computed only from such
    # reviewers, so a second, partial reviewer's imports reveal nothing about which items are which.
    buckets = _buckets(manifest, key)
    full_reviewers = sorted(name for name in distinct_human_reviewers
                            if _covers_packet(name, manifest, covering_by_item))
    controls: dict[str, Any] | None = None
    agreement_measured: dict[str, dict] | None = None
    if buckets is None:
        controls_reason: str | None = NO_CONTROLS
        agreement_measured_reason: str | None = NO_CONTROLS
    elif not full_reviewers:
        controls_reason = agreement_measured_reason = NOT_YET_DISCLOSED
    else:
        assert isinstance(key, PacketKeyV2)
        controls = _controls(manifest, key, buckets, covering_by_item, full_reviewers, records)
        controls_reason = None
        full_only = {
            item_id: {n: v for n, v in covering.items() if n in full_reviewers}
            for item_id, covering in covering_by_item.items()
        }
        agreement_measured, agreement_measured_reason = _agreement_across_packet(
            buckets["measured"], full_only
        )
        if agreement_measured is None and not buckets["measured"]:
            agreement_measured_reason = "the packet has no measured items"

    return {
        "schema_id": STATUS_SCHEMA,
        "packet_id": manifest.packet_id,
        "packet_sha256": packet_sha256,
        "status": status,
        "label": label,
        "distinct_human_reviewers": distinct_human_reviewers,
        "reviewer_ref_collisions": collisions,
        "reviewer_ref_problems": ref_problems,
        "secondary_ratings": secondary_ratings,
        "items": items_report,
        "agreement": agreement_result,
        "reason": agreement_reason,
        "agreement_measured": agreement_measured,
        "agreement_measured_reason": agreement_measured_reason,
        "controls": controls,
        "controls_reason": controls_reason,
        "open_disagreements": open_disagreements,
        "adjudications": adjudications_report,
    }


__all__ = ["PacketUnbound", "adjudication_is_stale", "review_status", "votes_on"]
