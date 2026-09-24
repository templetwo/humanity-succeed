from __future__ import annotations

from pathlib import Path

from humanity_succeed.canonical import canonical_str
from humanity_succeed.evidence.store import EvidenceStore
from humanity_succeed.providers.scripted import ScriptedProvider
from humanity_succeed.runner.episode import derive_status, run_episode
from humanity_succeed.runner.scripted import (
    evaluate_and_record,
    load_case,
    load_trajectory,
    run_scripted,
)

from ..conftest import DEV_CASES, EXAMPLES, TRAJ

CASE_FILES = {
    "commissioning-correction-001": EXAMPLES / "correction.yaml",
    "commissioning-feature-preserve-001": EXAMPLES / "feature-preserve.yaml",
    "commissioning-feature-standardize-001": EXAMPLES / "feature-standardize.yaml",
    "commissioning-correction-guard-001": DEV_CASES / "correction-source-guard.yaml",
    "commissioning-ordinary-title-001": DEV_CASES / "ordinary-request.yaml",
}


def act(**action) -> str:
    return canonical_str({"action": action})


def run_trajectory_file(tid: str, tmp: Path):
    t = load_trajectory(TRAJ / f"{tid}.yaml")
    case, doc = load_case(CASE_FILES[t["case_id"]])
    return run_scripted(case, doc, t, tmp / f"{tid}.sqlite", tmp / f"bundle-{tid}")


def run_raw(case_id: str, raws: list[str], tmp: Path, name: str = "raw", **kw):
    """Run raw outputs; returns (store, run_id, evaluation, provider). Store left open."""
    case, doc = load_case(CASE_FILES[case_id])
    store = EvidenceStore(tmp / f"{name}.sqlite")
    prov = ScriptedProvider(raws)
    res = run_episode(case, doc, prov, store, **kw)
    ev = evaluate_and_record(store, res.run_id, case)
    return store, res.run_id, ev, prov


__all__ = ["act", "run_trajectory_file", "run_raw", "derive_status", "CASE_FILES"]
