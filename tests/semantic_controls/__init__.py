"""Tests for the A1 semantic controls supplement (DECISIONS B68).

CONTRACT DEFECT, reported to the lead and not patched here (semantic_controls/contract.py is
off limits to builders): ``supplement_problems`` checks ``doc.get("class_id") != CLASS_ID`` on
each loaded case document, but a case document has no ``class_id`` field and ``CaseSource``
(extra="forbid") refuses one. Every member of every valid supplement therefore reports
``"<fixture_id>: class_id None != 'C1_correction_claim'"``, so the raw function is never empty.

``without_class_id_defect`` removes exactly those lines and nothing else. Tests use it only where
they need a clean baseline (negative controls compare a perturbed tree against it; the plan/run
end-to-end tests install it in place of the contract function, explicitly, per test). The raw
behaviour is pinned by strict xfail tests, which turn into failures the moment the contract is
fixed, so this helper cannot outlive the defect unnoticed.
"""

from __future__ import annotations

CLASS_ID_DEFECT_SUFFIX = ": class_id None != 'C1_correction_claim'"


def without_class_id_defect(problems: list[str]) -> list[str]:
    return [p for p in problems if not p.endswith(CLASS_ID_DEFECT_SUFFIX)]
