"""Attack 9: direct Python against the modules (no CLI). agreement_between_reviewers with
punctuation-only variants; canonical_reviewer_ref on the admitted charset; identical ratings files
under two refs; a manifest whose source_sha256 no longer matches the ledger's records."""
import json
from _lib import banner, export, imp, ratings, scratch, status, REPO
import sys
sys.path.insert(0, str(REPO / "src"))
from humanity_succeed.commissioning.agreement import agreement_between_reviewers
from humanity_succeed.review.identity import canonical_reviewer_ref, reviewer_ref_problem, same_reviewer

banner("A9a: agreement_between_reviewers on punctuation-only variants")
for a, b in [("anthony", "anthony."), ("anthony", "anthony-"), ("anthony", "anthony 2"), ("a.vasquez", "a-vasquez"),
             ("anthony", "Anthony"), ("anthony", "anthony "), (".", ".."), ("anthony", "anthony2")]:
    try:
        r = agreement_between_reviewers(a, ["pass"], b, ["pass"], ["pass", "fail"])
        print(f"  {a!r} vs {b!r}: ACCEPTED raw_agreement={r['raw_agreement']}")
    except ValueError as e:
        print(f"  {a!r} vs {b!r}: refused ({str(e)[:60]}...)")
banner("A9b: canonical forms and problems for admitted references")
for ref in ["anthony", "anthony.", "anthony-", "anthony_", "anthony 2", ".", "-", "0", "anthony vasquez", "anthonyvasquez"]:
    print(f"  {ref!r:20} canonical={canonical_reviewer_ref(ref)!r:20} problem={reviewer_ref_problem(ref)}")

banner("A9c: two refs, byte-identical ratings (same words, same timestamp): any signal?")
root = scratch("a9-state"); pk = export(root, scratch("a9-packet", create=False))
imp(pk, ratings(pk, root / "a.json", reviewer_ref="anthony", words="looks right to me"), root, "import anthony")
imp(pk, ratings(pk, root / "b.json", reviewer_ref="reviewer-two", words="looks right to me"), root, "import reviewer-two, same words/timestamp")
res = status(pk, root)
from humanity_succeed.review.ledger import read_records
recs = read_records(root)
pairs = {(r.item_id, r.dimension): {} for r in recs}
for r in recs: pairs[(r.item_id, r.dimension)][r.reviewer_ref] = (r.verdict, r.words, r.rated_at_utc)
same = sum(1 for v in pairs.values() if len(set(v.values())) == 1)
print(f"  items where both refs have identical (verdict, words, rated_at): {same}/{len(pairs)}; status reports nothing about it")

banner("A9d: manifest copy with one item's source_sha256 changed (rubric 'edited' after rating): status still reports the verdict")
m = json.loads((pk / "packet.json").read_text())
m["items"][0]["source_sha256"] = "e" * 64
alt = scratch("a9-altpacket"); (alt / "packet.json").write_text(json.dumps(m, sort_keys=True, separators=(",", ":")))
res = status(alt, root, "status (source_sha256 of item0 altered in the manifest)")
print("  item0 reviewers reported:", res["items"][0]["human_reviewers"], "(ledger records carry the ORIGINAL hash)")
