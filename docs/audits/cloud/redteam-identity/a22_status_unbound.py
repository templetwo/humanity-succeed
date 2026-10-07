"""Attack 22 (found while reading status.py): `hs review status` does not bind the packet.json it is
handed to the operator key or to the ledger. Hand it a TRIMMED copy of packet.json (same packet_id,
only the items the second reviewer happened to cover) and it reports independently_reviewed for
that packet_id, with no packet_sha256 in the output to show which manifest was used."""
import json, shutil
from _lib import banner, export, imp, ratings, scratch, status

root = scratch("a22-state")
pk = export(root, scratch("a22-packet", create=False))
m = json.loads((pk / "packet.json").read_text())
ids = [i["item_id"] for i in m["items"]]
imp(pk, ratings(pk, root / "a.json", reviewer_ref="anthony"), root, "import anthony (36/36)")
imp(pk, ratings(pk, root / "b.json", reviewer_ref="bob", only_items=ids[:2]), root, "import bob (2/36)")
banner("A22a: status on the real packet")
status(pk, root, "status (real packet.json)")
banner("A22b: status on a trimmed packet.json: same packet_id, only the 2 items bob covered")
trimmed = scratch("a22-trimmed")
m2 = dict(m); m2["items"] = [i for i in m["items"] if i["item_id"] in ids[:2]]
(trimmed / "packet.json").write_text(json.dumps(m2, sort_keys=True, separators=(",", ":")))
res = status(trimmed, root, "status (trimmed packet.json, 2 items)")
print("  output mentions packet_sha256?", "packet_sha256" in json.dumps(res))
print("  output keys:", sorted(res))
banner("A22c: status on a packet.json with a FOREIGN item swapped in (item id not in the ledger)")
m3 = dict(m); m3["items"] = [dict(m["items"][0], item_id="it_" + "f" * 16)] + m["items"][1:]
foreign = scratch("a22-foreign")
(foreign / "packet.json").write_text(json.dumps(m3, sort_keys=True, separators=(",", ":")))
status(foreign, root, "status (one foreign item)")
