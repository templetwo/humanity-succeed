"""Attacks 3, 4, 5.
3: cross-packet identity -- same person, two packets (two exports of the same run), two refs.
4: a model rating relabelled human in the ratings file; and a ledger line hand-edited from model to human.
5: operator-key tampering (fixture_id swap, entry order) and packet re-export."""
import json
from _lib import banner, export, imp, ratings, scratch, status, REPO, hs, show
import sys
sys.path.insert(0, str(REPO / "src"))
from humanity_succeed.review.ledger import read_records

root = scratch("a3-state")
pkA = export(root, scratch("a3-packetA", create=False))
pkB = export(root, scratch("a3-packetB", create=False))
mA = json.loads((pkA / "packet.json").read_text()); mB = json.loads((pkB / "packet.json").read_text())

banner("A3a: two exports of one run: packet ids / item ids / source hashes")
print("  packet ids:", mA["packet_id"], mB["packet_id"])
print("  item id overlap:", len({i["item_id"] for i in mA["items"]} & {i["item_id"] for i in mB["items"]}))
print("  source_sha256 sets equal:", {i["source_sha256"] for i in mA["items"]} == {i["source_sha256"] for i in mB["items"]})
banner("A3b: 'anthony' rates packet A; 'tony' rates packet B; status of each")
imp(pkA, ratings(pkA, root / "a.json", reviewer_ref="anthony"), root, "import anthony -> packet A")
imp(pkB, ratings(pkB, root / "b.json", reviewer_ref="tony"), root, "import tony -> packet B")
status(pkA, root, "status A"); status(pkB, root, "status B")
banner("A3c: ratings written for packet A imported against packet B (same run, re-exported)")
imp(pkB, root / "a.json", root, "import A's ratings file against packet B")
banner("A3d: cross-packet collision: 'Tony' on packet A (tony exists only on packet B)")
imp(pkA, ratings(pkA, root / "c.json", reviewer_ref="Tony"), root, "import 'Tony' -> packet A")

banner("A4a: ratings file with reviewer_kind=human written by 'a model' -- indistinguishable")
imp(pkA, ratings(pkA, root / "m.json", reviewer_ref="claude-seat", kind="model"), root, "import claude-seat as model")
status(pkA, root, "status A (model secondary)")
imp(pkA, ratings(pkA, root / "m2.json", reviewer_ref="claude-seat", kind="human"), root, "import SAME ref claude-seat as human")
status(pkA, root, "status A (same ref now human)")
banner("A4b: hand-edit the ledger: flip one reviewer's model lines to human + counts_as_vote true")
root4 = scratch("a4-state"); pk4 = export(root4, scratch("a4-packet", create=False))
imp(pk4, ratings(pk4, root4 / "h.json", reviewer_ref="anthony"), root4, "import anthony human")
imp(pk4, ratings(pk4, root4 / "m.json", reviewer_ref="gpt-x", kind="model"), root4, "import gpt-x model")
lp = root4 / "reviews" / "ledger.jsonl"
lines = lp.read_text().splitlines()
edited = [l.replace('"reviewer_kind":"model"', '"reviewer_kind":"human"').replace('"counts_as_vote":false', '"counts_as_vote":true') for l in lines]
lp.write_text("\n".join(edited) + "\n")
print("  ledger lines rewritten:", sum(1 for a, b in zip(lines, edited) if a != b))
status(pk4, root4, "status after hand-edit")
print("  read_records raised? no ->", len(read_records(root4)), "records read cleanly")

banner("A5a: operator key: swap two entries' fixture_id, then import")
root5 = scratch("a5-state"); pk5 = export(root5, scratch("a5-packet", create=False))
m5 = json.loads((pk5 / "packet.json").read_text())
kp = root5 / "reviews" / "keys" / f"{m5['packet_id']}.json"
key = json.loads(kp.read_text())
e0, e1 = key["entries"][0], key["entries"][1]
print("  before:", e0["item_id"], e0["fixture_id"], "|", e1["item_id"], e1["fixture_id"])
e0["fixture_id"], e1["fixture_id"] = e1["fixture_id"], e0["fixture_id"]
key["entries"].reverse()
kp.write_text(json.dumps(key, sort_keys=True, separators=(",", ":")))
imp(pk5, ratings(pk5, root5 / "r.json", reviewer_ref="anthony"), root5, "import against tampered key")
recs = {r.item_id: r for r in read_records(root5)}
print("  recorded fixture_id for item0:", recs[e0["item_id"]].fixture_id, "(was", e1["fixture_id"], ")")
status(pk5, root5, "status with tampered key")
banner("A5b: key with an entry removed -> import names the missing item")
key["entries"] = key["entries"][1:]
kp.write_text(json.dumps(key, sort_keys=True, separators=(",", ":")))
imp(pk5, ratings(pk5, root5 / "r2.json", reviewer_ref="bob"), root5, "import against key missing one entry")
banner("A5c: key packet_sha256 edited -> refused; packet.json edited (one char in instructions) -> refused")
key2 = json.loads(kp.read_text()); key2["packet_sha256"] = "0" * 64
kp.write_text(json.dumps(key2, sort_keys=True, separators=(",", ":")))
imp(pk5, ratings(pk5, root5 / "r3.json", reviewer_ref="bob"), root5, "import with key packet_sha256 zeroed")
pk5b = scratch("a5-packet-edited"); import shutil
for f in pk5.iterdir(): shutil.copy(f, pk5b / f.name)
pb = (pk5b / "packet.json").read_bytes().replace(b"For each item below", b"For each item below,")
(pk5b / "packet.json").write_bytes(pb)
imp(pk5b, ratings(pk5, root5 / "r4.json", reviewer_ref="bob"), root5, "import edited packet.json with original ratings sha")
