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
"""

from __future__ import annotations

from pathlib import Path

from ..canonical import sha256_bytes, strict_json_loads
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
    VERDICTS,
    PacketItem,
    PacketKey,
    PacketManifest,
    ReviewRecord,
)
from .identity import canonical_reviewer_ref, reviewer_ref_problem
from .ledger import read_records


class PacketUnbound(ValueError):
    """The packet.json handed to ``review_status`` is not the one the operator key under the state
    root was written for (missing key, or a hash mismatch). A status is only ever reported for the
    exact manifest the ledger's records were imported against (red-team 2026-10-07, D2)."""


def _packet_file(packet_path: Path) -> Path:
    p = Path(packet_path)
    return p / PACKET_FILE if p.is_dir() else p


def _load_packet(packet_path: Path) -> tuple[PacketManifest, str]:
    p = _packet_file(packet_path)
    raw = p.read_bytes()
    data = strict_json_loads(raw)
    return PacketManifest.model_validate(data, strict=True), sha256_bytes(raw)


def _bind_to_key(state_root: Path, manifest: PacketManifest, packet_sha256: str) -> None:
    """Refuse a manifest whose bytes are not the ones the operator key records for its packet_id.
    Without this, a trimmed copy of packet.json (same packet_id, fewer items) was reported as
    ``independently_reviewed`` from a ledger in which the second reviewer covered 2 of 36 items."""
    key_path = Path(state_root).joinpath(*KEY_DIR, f"{manifest.packet_id}.json")
    try:
        key = PacketKey.model_validate(strict_json_loads(key_path.read_bytes()), strict=True)
    except OSError as e:
        raise PacketUnbound(f"no operator key for packet {manifest.packet_id} under the state root "
                            f"({key_path}): {e.strerror or e}") from e
    if key.packet_sha256 != packet_sha256:
        raise PacketUnbound(f"packet.json sha256 {packet_sha256} != operator key packet_sha256 "
                            f"{key.packet_sha256} for packet {manifest.packet_id}: not the manifest "
                            "the ledger's records were imported against")


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


def review_status(packet_path: Path, *, state_root: Path) -> dict:
    """Coverage and agreement for one packet, computed from the ledger's actual records.

    ``LedgerCorrupt`` (from ``review.ledger.read_records``) is never caught here: a malformed
    ledger line is a refusal, not something this function papers over into an empty result.
    """
    manifest, packet_sha256 = _load_packet(packet_path)
    _bind_to_key(state_root, manifest, packet_sha256)
    records = read_records(state_root, packet_id=manifest.packet_id)

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

    total = len(manifest.items)
    covered = [r for r in items_report if r["human_reviewers"]]
    independent = [r for r in items_report if len(r["human_reviewers"]) >= 2]

    if not covered:
        status = STATUS_PENDING
    elif len(covered) < total:
        status = STATUS_PARTIAL
    elif len(independent) < total:
        status = STATUS_SINGLE
    else:
        status = STATUS_INDEPENDENT

    distinct_human_reviewers = sorted({name for (_item_id, name, _dimension) in latest})
    # The label must track whether the STATUS itself reflects independent review (every item
    # covered by >=2 distinct humans), not merely whether a second reviewer_ref appears anywhere
    # in the ledger: a second reviewer who only partially rated an item (never achieving full
    # coverage of any item's rubric) would otherwise make `len(distinct_human_reviewers) >= 2`
    # true while the report is still built on a single covering reviewer end-to-end (status stays
    # STATUS_PENDING/PARTIAL/SINGLE and agreement stays null) -- exactly the undercount B61 exists
    # to prevent. Tying the label to `status` keeps it consistent with the field it is meant to
    # summarize by construction.
    label = None if status == STATUS_INDEPENDENT else REVIEW_MODE_SINGLE

    agreement_result, agreement_reason = _agreement_across_packet(manifest.items, covering_by_item)

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
    }


__all__ = ["PacketUnbound", "review_status"]
