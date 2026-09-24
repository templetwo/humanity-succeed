"""Split registry audit (BUILD_SPEC §5.2).

All descendants of a root scenario belong to one split. The audit walks derivation edges and shared
root IDs (graph components), not just text. Normalized-text near-duplicate checks supplement, never
replace, the ancestry rule.
"""

from __future__ import annotations

import re
from typing import Any

from ..canonical import sha256_obj
from ..contracts.case import CaseSource

NEAR_DUPLICATE_THRESHOLD = 0.5


def _shingles(text: str, n: int = 3) -> set[tuple[str, ...]]:
    w = re.findall(r"[a-z0-9]+", text.lower())
    if len(w) < n:
        return {tuple(w)} if w else set()
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def _world_values(case: CaseSource) -> set[str]:
    """Hashes of initial resource values. Adding an inert decoy resource only dilutes the overlap
    (2 shared of 3 is still 0.67), unlike a hash of the whole world."""
    return {sha256_obj(r.value) for r in case.world.resources.values()}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


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

    # Near-duplicates across different lineages. Ancestry is the rule; this lexical/content check
    # only supplements it and cannot prove that an undeclared paraphrase is absent. A match across
    # different splits blocks (possible undeclared derivative in another split); a match within one
    # split is a warning for review.
    warnings: list[dict[str, Any]] = []
    for i, a in enumerate(cases):
        for b in cases[i + 1:]:
            if find(a.case_id) == find(b.case_id):
                continue
            sim = _jaccard(_shingles(a.subject.task), _shingles(b.subject.task))
            wsim = _jaccard(_world_values(a), _world_values(b))
            if sim >= NEAR_DUPLICATE_THRESHOLD or wsim >= NEAR_DUPLICATE_THRESHOLD:
                item = {"kind": "near_duplicate_across_lineages",
                        "case_ids": sorted([a.case_id, b.case_id]),
                        "task_shingle_jaccard": round(sim, 3),
                        "world_value_jaccard": round(wsim, 3),
                        "splits": sorted({a.split, b.split})}
                (problems if a.split != b.split else warnings).append(item)

    return {
        "schema_id": "hs-split-audit/1",
        "status": "blocked" if problems else "ok",
        "groups": sorted(groups, key=lambda g: g["case_ids"]),
        "problems": problems,
        "warnings": warnings,
        "near_duplicate_method": (
            f"word-3-gram Jaccard >= {NEAR_DUPLICATE_THRESHOLD} on subject.task, or Jaccard >= "
            f"{NEAR_DUPLICATE_THRESHOLD} over initial resource-value hashes; heuristic, not "
            "paraphrase proof"),
    }
