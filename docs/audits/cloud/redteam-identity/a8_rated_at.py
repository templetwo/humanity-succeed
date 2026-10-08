"""Attack 8: rated_at_utc edge cases. The importer requires datetime.fromisoformat() to parse."""
from _lib import banner, export, imp, ratings, scratch, status

root = scratch("a8-state")
pk = export(root, scratch("a8-packet", create=False))
cases = [
    "2026-10-07T14:03:00Z", "2026-10-07T14:03:00+05:30", "2026-10-07T14:03:00-12:00",
    "2026-10-07", "2026-10-07T14:03:00", "20261007T140300", "9999-12-31T23:59:59Z",
    "0001-01-01T00:00:00Z", "2026-10-07T14:03:00+23:59", "2026-10-07T14:03:00+24:00",
    "2026-02-30T00:00:00Z", "2026-10-07T24:00:00Z", "2026-10-07 14:03:00Z", "2026-W41-3",
    "now", "1759845780", "2026-10-07T14:03:00.123456789Z",
]
banner("A8: which rated_at_utc values import?")
for i, ts in enumerate(cases):
    rc, body = imp(pk, ratings(pk, root / f"t{i}.json", reviewer_ref=f"r{i}", rated_at=ts), root,
                   f"import rated_at_utc={ts!r}")
res = status(pk, root)
