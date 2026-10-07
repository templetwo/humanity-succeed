"""One canonical form for ``reviewer_ref`` wherever a distinctness claim is made (DECISIONS B61).

B61 says one person is never counted as two reviewers. Before this module the check compared
``reviewer_ref`` byte for byte, so ``"anthony"`` and ``"Anthony "`` were two independent reviewers:
measured on 2026-10-07 against the real packet export, ``hs review status`` moved to
``independently_reviewed``, dropped the ``single-reviewer`` label and emitted an agreement block
(``docs/audits/2026-10-07_human_side_audit_a1_review.md``).

The rule here is fail-closed and never silent:

- ``canonical_reviewer_ref`` folds case (Unicode casefold after NFKC) and collapses whitespace. It
  is used for *comparison only*; the literal reference the reviewer typed is what the ledger stores.
- ``hs review import`` refuses a new reference that is untidy (stray whitespace) or that collides
  with a reference already in the ledger without matching it exactly. The operator reuses the
  recorded reference or chooses a clearly distinct one; nothing is merged for them.
- ``hs review status`` counts colliding references already in a ledger as ONE reviewer and reports
  the collision, so a label can only ever be too strict, never inflated.

Identity is still attested by the operator, not verified: two genuinely different people who type
the same reference are still one reviewer to this code, and a reviewer registry remains a separate
decision (BUILD_SPEC §4 "human review identity keys").
"""

from __future__ import annotations

import unicodedata


def canonical_reviewer_ref(ref: str) -> str:
    """The comparison form of a reviewer reference: NFKC, casefolded, whitespace collapsed."""
    folded = unicodedata.normalize("NFKC", ref).casefold()
    return " ".join(folded.split())


def same_reviewer(ref_a: str, ref_b: str) -> bool:
    """True when two references denote the same reviewer under ``canonical_reviewer_ref``."""
    return canonical_reviewer_ref(ref_a) == canonical_reviewer_ref(ref_b)


def is_tidy_reviewer_ref(ref: str) -> bool:
    """A reference with no leading, trailing or repeated whitespace. A stable identity reference
    should be typed the same way every time; stray whitespace is refused rather than normalised."""
    return bool(ref) and ref == " ".join(ref.split())


__all__ = ["canonical_reviewer_ref", "same_reviewer", "is_tidy_reviewer_ref"]
