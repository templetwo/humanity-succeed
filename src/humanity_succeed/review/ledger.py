"""The append-only review ledger (lead-authored shared module; builders use it, never edit it).

One canonical-JSON ReviewRecord per line under state_root/reviews/ledger.jsonl. Lines are only ever
appended; nothing here rewrites or deletes. A malformed line is reported, never skipped silently.
"""

from __future__ import annotations

from pathlib import Path

from ..canonical import canonical_str, strict_json_loads
from .contract import LEDGER_PATH, ReviewRecord


class LedgerCorrupt(ValueError):
    """A ledger line failed to parse or validate. The ledger is evidence: do not guess past it."""


def ledger_path(state_root: Path) -> Path:
    return Path(state_root).joinpath(*LEDGER_PATH)


def read_records(state_root: Path, packet_id: str | None = None) -> list[ReviewRecord]:
    p = ledger_path(state_root)
    if not p.exists():
        return []
    out: list[ReviewRecord] = []
    for n, line in enumerate(p.read_bytes().split(b"\n"), start=1):
        if not line.strip():
            continue
        try:
            rec = ReviewRecord.model_validate(strict_json_loads(line), strict=True)
        except Exception as e:  # noqa: BLE001 - any failure is corruption of evidence
            raise LedgerCorrupt(f"{p}: line {n}: {e}") from e
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
