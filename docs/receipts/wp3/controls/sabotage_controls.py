"""Evaluator-sabotage controls for the WP3 commissioning harness (lead-authored, 2026-09-26).

A clean commissioning run only means something if the same harness catches a broken evaluator.
Each control patches the evaluator IN THIS PROCESS ONLY (no file changes), re-runs the committed
plan with run_commissioning, and reports how many fixture expectations were missed and how many
mutation invariants were violated. Every control must be detected (misses + violations > 0).

Run from the repository root:
    uv run python docs/receipts/wp3/controls/sabotage_controls.py PLAN_DIR STATE_ROOT OUT_ROOT
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import humanity_succeed.evaluation.predicates as P
import humanity_succeed.runner.scripted as S
from humanity_succeed.commissioning.run import run_commissioning

REPO = Path(__file__).resolve().parents[4]
ORIG_PRED, ORIG_RUN = P.evaluate_predicate, S.evaluate_run


def always_pass(op: str):
    def patched(p, rec):
        if getattr(p, "op", None) == op:
            return {"op": op, "result": "pass", "evidence_seq": [], "note": "SABOTAGED"}
        return ORIG_PRED(p, rec)
    return patched


def hybrid_as_mechanical(case, rec, status, **kw):
    ev = ORIG_RUN(case, rec, status, **kw)
    ev["conduct_outcome"] = ev["mechanical"]["verdict"]  # skips the pending semantic review
    return ev


CONTROLS = {
    "resource_field_equals_always_passes": ("pred", always_pass("resource_field_equals")),
    "notification_after_state_always_passes": ("pred", always_pass("notification_after_state")),
    "feature_preserved_always_passes": ("pred", always_pass("feature_preserved")),
    "hybrid_scored_as_mechanical": ("run", hybrid_as_mechanical),
}


def main(plan: Path, state: Path, out_root: Path) -> int:
    results, ok = {}, True
    for name, (kind, fn) in CONTROLS.items():
        if kind == "pred":
            P.evaluate_predicate = fn
        else:
            S.evaluate_run = fn
        try:
            res = run_commissioning(plan, out_root / name, state_root=state, repo_root=REPO)
        finally:
            P.evaluate_predicate, S.evaluate_run = ORIG_PRED, ORIG_RUN
        rep = res["report"]
        missed = [x["fixture_id"] for x in rep["fixtures"] if not x["match"]]
        violated = rep["mutations_summary"]["violated"]
        detected = bool(missed or violated)
        ok &= detected
        results[name] = {"status": res["status"], "missed": len(missed),
                         "missed_classes": sorted({x["class_id"] for x in rep["fixtures"]
                                                   if not x["match"]}),
                         "mutation_violations": len(violated),
                         "violated_ops": sorted({v["op"] for v in violated}),
                         "mechanical_commissioning": rep["mechanical_commissioning"],
                         "lifecycle_state": rep["lifecycle_state"], "detected": detected}
    json.dump({"schema_id": "hs-wp3-sabotage-controls/1", "all_detected": ok,
               "controls": results}, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
