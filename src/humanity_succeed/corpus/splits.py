"""Split registry audit (BUILD_SPEC §5.2).

All descendants of a root scenario belong to one split. The audit walks derivation edges and shared
root IDs (graph components), not just text. Normalized-text near-duplicate checks supplement, never
replace, the ancestry rule.
"""

from __future__ import annotations

import re
from typing import Any

from ..contracts.case import CaseSource


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def audit_splits(cases: list[CaseSource]) -> dict[str, Any]:
    problems: list[dict[str, Any]] = []
    ids = [c.case_id for c in cases]
    by_id = {c.case_id: c for c in cases}
    for cid in {i for i in ids if ids.count(i) > 1}:
        problems.append({"kind": "duplicate_case_id", "case_id": cid})

    parent: dict[str, str] = {c.case_id: c.case_id for c in cases}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_root: dict[str, list[str]] = {}
    for c in cases:
        by_root.setdefault(c.root_scenario_id, []).append(c.case_id)
        for d in c.derivation_ids:
            if d not in by_id:
                problems.append({"kind": "unresolved_derivation", "case_id": c.case_id,
                                 "derivation_id": d})
                continue
            union(c.case_id, d)
            if by_id[d].root_scenario_id != c.root_scenario_id:
                problems.append({"kind": "derivation_crosses_roots", "case_id": c.case_id,
                                 "derivation_id": d})
    for members in by_root.values():
        for m in members[1:]:
            union(members[0], m)

    comps: dict[str, list[CaseSource]] = {}
    for c in cases:
        comps.setdefault(find(c.case_id), []).append(c)
    groups = []
    for members in comps.values():
        splits = sorted({m.split for m in members})
        g = {"case_ids": sorted(m.case_id for m in members),
             "root_scenario_ids": sorted({m.root_scenario_id for m in members}),
             "splits": splits}
        groups.append(g)
        if len(splits) > 1:
            problems.append({"kind": "lineage_spans_splits", **g})

    seen: dict[str, CaseSource] = {}
    for c in cases:
        key = _norm(c.subject.task)
        if key in seen and find(seen[key].case_id) != find(c.case_id):
            problems.append({"kind": "near_duplicate_across_lineages",
                             "case_ids": sorted([seen[key].case_id, c.case_id])})
        seen.setdefault(key, c)

    return {
        "schema_id": "hs-split-audit/1",
        "status": "blocked" if problems else "ok",
        "groups": sorted(groups, key=lambda g: g["case_ids"]),
        "problems": problems,
    }
