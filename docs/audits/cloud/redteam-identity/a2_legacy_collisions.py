"""Attack 2: legacy-ledger collisions. Hand-append records with colliding literals (as a ledger
written before 17860e0 could hold) and check the tie-break / latest-revision rule in status.py
against its docstring, plus a legacy non-ASCII look-alike reference."""
import json
from _lib import banner, export, imp, ratings, scratch, status, REPO
import sys
sys.path.insert(0, str(REPO / "src"))
from humanity_succeed.review.contract import ReviewRecord
from humanity_succeed.review.ledger import append_records, read_records

root = scratch("a2-state")
pk = export(root, scratch("a2-packet", create=False))
manifest = json.loads((pk / "packet.json").read_text())
item0 = manifest["items"][0]
others = [it["item_id"] for it in manifest["items"][1:]]


def rec(ref, verdict, revision, item=item0, rated="2026-10-07T00:00:00Z"):
    return ReviewRecord(schema_id="hs-review-record/1", packet_id=manifest["packet_id"],
                        item_id=item["item_id"], fixture_id="fx-unknown", source_sha256=item["source_sha256"],
                        dimension=item["rubric"][0]["dimension"], verdict=verdict, words="legacy line",
                        reviewer_ref=ref, reviewer_kind="human", counts_as_vote=True, revision=revision,
                        rated_at_utc=rated, ratings_file_sha256="0" * 64)


def item_verdicts(res):
    row = next(r for r in res["items"] if r["item_id"] == item0["item_id"])
    return row["human_reviewers"], row["verdicts"]


banner("A2a: 'anthony' rev1 pass, then 'Anthony' rev1 fail (later line, same revision)")
append_records(root, [rec("anthony", "pass", 1), rec("Anthony", "fail", 1)])
res = status(pk, root); print("  item0:", item_verdicts(res))

banner("A2b: then 'anthony' rev2 pass (later line, higher revision)")
append_records(root, [rec("anthony", "pass", 2)])
res = status(pk, root); print("  item0:", item_verdicts(res))

banner("A2c: then 'Anthony' rev2 fail -- chronologically newest, ties rev 2")
append_records(root, [rec("Anthony", "fail", 2)])
res = status(pk, root); print("  item0:", item_verdicts(res))

banner("A2d: then 'ANTHONY' rev1 pass -- chronologically newest, LOWER revision (per-literal numbering)")
append_records(root, [rec("ANTHONY", "pass", 1, rated="2026-12-01T00:00:00Z")])
res = status(pk, root); print("  item0:", item_verdicts(res))
print("  -> the newest ledger line (ANTHONY rev1 pass) does NOT win; rev2 fail stands")

banner("A2e: duplicate (literal, revision) lines with contradicting verdicts: 'bob' rev1 pass, 'bob' rev1 fail")
append_records(root, [rec("bob", "pass", 1), rec("bob", "fail", 1)])
res = status(pk, root); print("  item0:", item_verdicts(res))

banner("A2f: import 'anthony' again via CLI now that the ledger holds anthony/Anthony/ANTHONY")
imp(pk, ratings(pk, root / "r.json", reviewer_ref="anthony"), root, "import 'anthony' (exact literal present)")
imp(pk, ratings(pk, root / "r2.json", reviewer_ref="AnThOnY"), root, "import 'AnThOnY' (new literal)")

banner("A2g: legacy non-ASCII look-alike: ledger holds Cyrillic 'аnthony' (U+0430) covering ALL items; then import ASCII 'anthony'")
root2 = scratch("a2g-state"); pk2 = export(root2, scratch("a2g-packet", create=False))
m2 = json.loads((pk2 / "packet.json").read_text())
cyr = "аnthony"
append_records(root2, [ReviewRecord(schema_id="hs-review-record/1", packet_id=m2["packet_id"], item_id=it["item_id"],
    fixture_id="fx", source_sha256=it["source_sha256"], dimension=it["rubric"][0]["dimension"], verdict="pass",
    words="legacy", reviewer_ref=cyr, reviewer_kind="human", counts_as_vote=True, revision=1,
    rated_at_utc="2026-10-01T00:00:00Z", ratings_file_sha256="0"*64) for it in m2["items"]])
imp(pk2, ratings(pk2, root2 / "r.json", reviewer_ref="anthony"), root2, "import ASCII 'anthony'")
res = status(pk2, root2)
print("  distinct refs (repr):", [repr(r) for r in res["distinct_human_reviewers"]])
