"""Attack 6: partial-coverage games. Does status ever say independently_reviewed with fewer than
two full covering humans? And what does the agreement block say when the second human covers one
item of 36?"""
import json
from _lib import banner, export, imp, ratings, scratch, status, REPO
import sys
sys.path.insert(0, str(REPO / "src"))
from humanity_succeed.canonical import canonical_bytes
from humanity_succeed.review.contract import PacketItem, PacketManifest, ReviewRecord, RubricLine, VisibleStep
from humanity_succeed.review.ledger import append_records

root = scratch("a6-state")
pk = export(root, scratch("a6-packet", create=False))
manifest = json.loads((pk / "packet.json").read_text())
ids = [it["item_id"] for it in manifest["items"]]

banner("A6a: 'anthony' covers 36/36, 'bob' covers 1/36")
imp(pk, ratings(pk, root / "a.json", reviewer_ref="anthony"), root, "import anthony (36)")
imp(pk, ratings(pk, root / "b.json", reviewer_ref="bob", only_items=ids[:1], verdict="fail"), root, "import bob (1)")
res = status(pk, root)
print("  items with >=2 reviewers:", sum(1 for r in res["items"] if len(r["human_reviewers"]) >= 2), "of", len(res["items"]))

banner("A6b: three partial humans whose union covers everything but no pair covers all: bob 1-18, carol 19-36")
imp(pk, ratings(pk, root / "c.json", reviewer_ref="carol", only_items=ids[18:]), root, "import carol (18-36)")
imp(pk, ratings(pk, root / "b2.json", reviewer_ref="bob", only_items=ids[:18]), root, "import bob (1-18)")
res = status(pk, root)
print("  items with >=2 reviewers:", sum(1 for r in res["items"] if len(r["human_reviewers"]) >= 2), "of", len(res["items"]))
print("  -> every item now has two distinct covering humans; no single pair covers the packet")

banner("A6c: synthetic 2-dimension item: A rates both dims; B rates dim1 only; C rates dim2 only")
PID = "pk_" + "b" * 16; IT = "it_" + "3" * 16; SHA = "1" * 64
item = PacketItem(item_id=IT, task="t", visible_resources={}, steps=[VisibleStep(turn=0, proposed={}, message=None, outcome="allowed: ok")],
                  rubric=[RubricLine(dimension="d1", instruction="i1"), RubricLine(dimension="d2", instruction="i2")],
                  question="q?", allowed_verdicts=["pass", "fail"], source_sha256=SHA)
man = PacketManifest(schema_id="hs-review-packet/1", packet_id=PID, mode="single-reviewer",
                     created_from={"run_report_sha256": SHA, "plan_sha256": SHA}, instructions="i", items=[item], claim_boundary="c")
root3 = scratch("a6c-state"); pk3 = scratch("a6c-packet")
(pk3 / "packet.json").write_bytes(canonical_bytes(man.model_dump(mode="json")))
def r(ref, dim, verdict="pass", rev=1):
    return ReviewRecord(schema_id="hs-review-record/1", packet_id=PID, item_id=IT, fixture_id="fx", source_sha256=SHA,
                        dimension=dim, verdict=verdict, words="w", reviewer_ref=ref, reviewer_kind="human",
                        counts_as_vote=True, revision=rev, rated_at_utc="2026-10-07T00:00:00Z", ratings_file_sha256=SHA)
append_records(root3, [r("A", "d1"), r("A", "d2"), r("B", "d1"), r("C", "d2")])
res = status(pk3, root3)
print("  item:", res["items"][0]["human_reviewers"], res["items"][0]["verdicts"])

banner("A6d: legacy colliding literals jointly cover: 'B' rated d1 (above), 'b' rated d2 (one person, two spellings)")
append_records(root3, [r("b", "d2")])
res = status(pk3, root3)
print("  item:", res["items"][0]["human_reviewers"], res["items"][0]["verdicts"])

banner("A6e: model-kind record with counts_as_vote=True (hand-edited ledger), ref 'M', covering both dims")
append_records(root3, [ReviewRecord(schema_id="hs-review-record/1", packet_id=PID, item_id=IT, fixture_id="fx", source_sha256=SHA,
                        dimension=d, verdict="pass", words="w", reviewer_ref="M", reviewer_kind="model",
                        counts_as_vote=True, revision=1, rated_at_utc="2026-10-07T00:00:00Z", ratings_file_sha256=SHA) for d in ("d1", "d2")])
res = status(pk3, root3)
print("  item:", res["items"][0]["human_reviewers"])

banner("A6f: human-kind record with counts_as_vote=False (hand-edited), ref 'H2'")
append_records(root3, [ReviewRecord(schema_id="hs-review-record/1", packet_id=PID, item_id=IT, fixture_id="fx", source_sha256=SHA,
                        dimension=d, verdict="pass", words="w", reviewer_ref="H2", reviewer_kind="human",
                        counts_as_vote=False, revision=1, rated_at_utc="2026-10-07T00:00:00Z", ratings_file_sha256=SHA) for d in ("d1", "d2")])
res = status(pk3, root3)
print("  item:", res["items"][0]["human_reviewers"])
