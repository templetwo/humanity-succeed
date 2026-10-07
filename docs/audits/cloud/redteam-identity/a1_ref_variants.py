"""Attack 1: reviewer_ref variants the charset rule still admits.

One person, several spellings that differ only by punctuation, digits or word separators. Does
`hs review status` reach independently_reviewed?
"""
from _lib import banner, export, imp, ratings, scratch, status

root = scratch("a1-state")
pk = export(root, scratch("a1-packet", create=False))

banner("A1a: 'anthony' then 'anthony.' (trailing dot)")
imp(pk, ratings(pk, root / "r1.json", reviewer_ref="anthony"), root, "import reviewer_ref='anthony'")
imp(pk, ratings(pk, root / "r2.json", reviewer_ref="anthony."), root, "import reviewer_ref='anthony.'")
status(pk, root)

for i, variant in enumerate(["anthony-", "anthony_", "anthony 2", "anthony.vasquez", "anthony-vasquez",
                             "anthony_vasquez", "anthony vasquez", "anthonyvasquez", "a.vasquez", ".",
                             "..", "-", "_", "0", "anthony2", "anthony..", "anthony-.-"]):
    rc, body = imp(pk, ratings(pk, root / f"v{i}.json", reviewer_ref=variant), root,
                   f"import reviewer_ref={variant!r}")
res = status(pk, root, "hs review status after all variants")
print("\nVERDICT: distinct_human_reviewers =", len(res["distinct_human_reviewers"]), "for one person")
