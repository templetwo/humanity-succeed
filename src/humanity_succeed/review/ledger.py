"""The append-only review ledger (lead-authored shared module; builders use it, never edit it).

One canonical-JSON ReviewRecord per line under state_root/reviews/ledger.jsonl. Lines are only ever
appended; nothing here rewrites or deletes. A malformed line is reported, never skipped silently.

Adjudications (B71) live in a SEPARATE append-only file, state_root/reviews/adjudications.jsonl
(``ADJUDICATIONS_PATH``), so a review ledger line never gains a field (audit F28). They are read with
the same strictness: a malformed line, or two lines claiming the same revision of one
(packet, item, dimension) adjudication, is ``LedgerCorrupt``.
"""

from __future__ import annotations

from pathlib import Path

from ..canonical import canonical_str, strict_json_loads
from .contract import ADJUDICATIONS_PATH, LEDGER_PATH, AdjudicationRecord, ReviewRecord


class LedgerCorrupt(ValueError):
    """A ledger line failed to parse or validate. The ledger is evidence: do not guess past it."""


def ledger_path(state_root: Path) -> Path:
    return Path(state_root).joinpath(*LEDGER_PATH)


def read_records(state_root: Path, packet_id: str | None = None) -> list[ReviewRecord]:
    p = ledger_path(state_root)
    if not p.exists():
        return []
    out: list[ReviewRecord] = []
    seen: dict[tuple[str, str, str, str, int], int] = {}
    for n, line in enumerate(p.read_bytes().split(b"\n"), start=1):
        if not line.strip():
            continue
        try:
            rec = ReviewRecord.model_validate(strict_json_loads(line), strict=True)
        except Exception as e:  # noqa: BLE001 - any failure is corruption of evidence
            raise LedgerCorrupt(f"{p}: line {n}: {e}") from e
        ident = (rec.packet_id, rec.item_id, rec.dimension, rec.reviewer_ref, rec.revision)
        if ident in seen:
            raise LedgerCorrupt(f"{p}: line {n}: revision {rec.revision} of {rec.reviewer_ref!r} on "
                                f"{rec.item_id}/{rec.dimension} already appears at line {seen[ident]}; "
                                "two lines with equal authority cannot both be the latest verdict")
        seen[ident] = n
        if packet_id is None or rec.packet_id == packet_id:
            out.append(rec)
    return out


def append_records(state_root: Path, records: list[ReviewRecord]) -> None:
    """Append records in one write. Existing lines are never touched."""
    if not records:
        return
    p = ledger_path(state_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(canonical_str(r.model_dump(mode="json")) + "\n" for r in records)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(data)


def adjudications_path(state_root: Path) -> Path:
    return Path(state_root).joinpath(*ADJUDICATIONS_PATH)


def read_adjudications(state_root: Path, packet_id: str | None = None) -> list[AdjudicationRecord]:
    """Every adjudication record in file order (optionally one packet's). Strict per line, as
    ``read_records``: any line that fails to parse or validate is ``LedgerCorrupt`` naming the line,
    and so is a second line with the same (packet, item, dimension, revision)."""
    p = adjudications_path(state_root)
    if not p.exists():
        return []
    out: list[AdjudicationRecord] = []
    seen: dict[tuple[str, str, str, int], int] = {}
    for n, line in enumerate(p.read_bytes().split(b"\n"), start=1):
        if not line.strip():
            continue
        try:
            rec = AdjudicationRecord.model_validate(strict_json_loads(line), strict=True)
        except Exception as e:  # noqa: BLE001 - any failure is corruption of evidence
            raise LedgerCorrupt(f"{p}: line {n}: {e}") from e
        ident = (rec.packet_id, rec.item_id, rec.dimension, rec.revision)
        if ident in seen:
            raise LedgerCorrupt(f"{p}: line {n}: adjudication revision {rec.revision} on "
                                f"{rec.item_id}/{rec.dimension} already appears at line {seen[ident]}; "
                                "two lines with equal authority cannot both be the latest decision")
        seen[ident] = n
        if packet_id is None or rec.packet_id == packet_id:
            out.append(rec)
    return out


def append_adjudications(state_root: Path, records: list[AdjudicationRecord]) -> None:
    """Append adjudication records in one write. Existing lines are never touched; the review
    ledger (``LEDGER_PATH``) is never opened."""
    if not records:
        return
    p = adjudications_path(state_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(canonical_str(r.model_dump(mode="json")) + "\n" for r in records)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(data)
