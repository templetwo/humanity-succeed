"""Attack 7: anything in packet.json / index.html that leaks class or condition beyond the task
wording? Independent scan: tokens, structure, and whether source_sha256 can be joined back to the
committed cases/ bundles by anyone holding the repository."""
import json, re, hashlib, collections
from _lib import banner, export, scratch, REPO
import sys
sys.path.insert(0, str(REPO / "src"))
from humanity_succeed.canonical import strict_json_loads
from humanity_succeed.contracts.case import review_source_sha256

root = scratch("a7-state")
pk = export(root, scratch("a7-packet", create=False))
m = json.loads((pk / "packet.json").read_text())
html = (pk / "index.html").read_text()
raw = (pk / "packet.json").read_text()

banner("A7a: suspicious tokens in packet.json / index.html")
pat = re.compile(r"(fixture|fx[-_]|case_id|class|condition|C[1-6]\b|group|expected|evaluator|verdict|predicate|judgment|hybrid|scripted|adapter|gen_|suite_v)", re.I)
for name, text in (("packet.json", raw), ("index.html", html)):
    hits = collections.Counter(mm.group(0).lower() for mm in pat.finditer(text))
    print(f"  {name}: {dict(hits)}")
banner("A7b: non-manifest content in index.html (comments, meta, scripts, links)")
print("  <script>:", html.count("<script"), " <!--:", html.count("<!--"), " <meta:", html.count("<meta"), " href=:", html.count("href="))
print("  head:", re.sub(r"\s+", " ", html[:400]))
banner("A7c: structural fingerprints across items (task-wording classes, visible_resources keys, step shapes)")
def mask(t): return re.sub(r"\d+", "N", re.sub(r"'[^']*'|\"[^\"]*\"", "Q", t))
groups = collections.defaultdict(list)
for it in m["items"]:
    sig = (tuple(sorted(it["visible_resources"])), tuple(s["proposed"].get("type") for s in it["steps"]), len(it["steps"]))
    groups[sig].append(it["item_id"])
print("  distinct (visible_resource_ids, step-type sequence) signatures:", len(groups))
for sig, ids in groups.items(): print("   ", len(ids), "items:", sig)
banner("A7d: source_sha256 join to the committed run bundles (anyone with the repo)")
run = REPO / "docs/receipts/wp3/run"
report = json.loads((run / "report.json").read_text())
by_hash = {}
for row in report["fixtures"]:
    cs = run / row["bundle"] / "case_source.json"
    if cs.exists():
        doc = strict_json_loads(cs.read_bytes())
        by_hash.setdefault(review_source_sha256(doc), []).append((row["fixture_id"], doc.get("case_id")))
joined = {it["item_id"]: by_hash.get(it["source_sha256"]) for it in m["items"]}
print("  items resolvable to a committed case by source_sha256:", sum(1 for v in joined.values() if v), "of", len(m["items"]))
print("  example:", next(iter(joined.items())))
print("  hashes mapping to >1 fixture:", sum(1 for v in by_hash.values() if len(v) > 1))
banner("A7e: does the ledger/status output carry fixture ids? (status output keys per item)")
