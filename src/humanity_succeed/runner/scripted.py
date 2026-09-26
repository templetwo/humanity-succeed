"""Scripted run orchestration: run -> evaluate -> record evaluation -> export bundle.

Scripted trajectories are instrument fixtures. Their bundles carry evidence_class
``scripted_instrument`` and must never be presented as model results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..canonical import canonical_bytes, load_document, sha256_obj
from ..contracts.case import CaseSemanticError, CaseSource, semantic_problems
from ..evaluation.predicates import RunRecord, evaluate_run
from ..evidence.bundle import export_bundle
from ..evidence.store import EvidenceStore, PendingEvent
from ..providers.scripted import ScriptedProvider
from .episode import derive_status, run_episode

TRAJECTORY_SCHEMA = "hs-scripted-trajectory/1"


def load_case(path: Path) -> tuple[CaseSource, dict[str, Any]]:
    doc = load_document(Path(path))
    case = CaseSource.model_validate(doc, strict=True)
    probs = semantic_problems(case)
    if probs:
        raise CaseSemanticError(probs)
    return case, doc


class Trajectory(BaseModel):
    """A scripted instrument input. IDs follow the case identifier grammar (no paths)."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_id: Literal["hs-scripted-trajectory/1"]
    trajectory_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._#-]{0,127}$")]
    case_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    provenance: dict[str, Any]
    description: str
    raw_outputs: Annotated[list[str], Field(min_length=1)]


def load_trajectory(path: Path) -> dict[str, Any]:
    doc = load_document(Path(path))
    try:
        Trajectory.model_validate(doc, strict=True)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(p) for p in first.get("loc", ()))
        raise ValueError(f"{path}: invalid {TRAJECTORY_SCHEMA} document at {loc}: "
                         f"{first.get('type')}") from e
    return doc


def trajectory_from_demo(case: CaseSource, demo_id: str) -> dict[str, Any]:
    """Serialize a case demonstration's actions to raw strings (one JSON object per turn)."""
    [demo] = [d for d in case.demonstrations if d.demo_id == demo_id]
    return {
        "schema_id": TRAJECTORY_SCHEMA,
        "trajectory_id": f"{case.case_id}#{demo_id}",
        "case_id": case.case_id,
        "provenance": {"kind": "case_demonstration", "demo_id": demo_id},
        "description": f"Demonstration {demo_id} ({demo.training_role})",
        "raw_outputs": [
            canonical_bytes(a.model_dump(mode="json", exclude_none=True)).decode()
            for a in demo.actions
        ],
    }


def evaluate_and_record(store: EvidenceStore, run_id: str, case: CaseSource, *,
                        evaluator_version: str | None = None) -> dict[str, Any]:
    events = store.events(run_id)
    rec = RunRecord(
        events=events,
        revisions=store.revisions(run_id),
        initial_resources={rid: {"revision": r.revision, "value": r.value}
                           for rid, r in case.world.resources.items()},
    )
    kw = {} if evaluator_version is None else {"evaluator_version": evaluator_version}
    evaluation = evaluate_run(case, rec, derive_status(events), **kw)
    store.put_artifact("evaluation", canonical_bytes(evaluation))
    store.append(run_id, [PendingEvent("evaluation_recorded", "evaluator", events[-1]["tick"], {
        "evaluation_sha256": sha256_obj(evaluation),
        "evaluator_version": evaluation["evaluator_version"],
    })])
    return evaluation


def run_scripted(
    case: CaseSource,
    case_doc: dict[str, Any],
    trajectory: dict[str, Any],
    store_path: Path,
    bundle_out: Path,
    *,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    if trajectory["case_id"] != case.case_id:
        raise ValueError("trajectory is bound to a different case")
    store = EvidenceStore(Path(store_path))
    try:
        provider = ScriptedProvider(trajectory["raw_outputs"])
        res = run_episode(case, case_doc, provider, store, trajectory=trajectory, run_id=run_id)
        evaluation = evaluate_and_record(store, res.run_id, case)
        bundle = export_bundle(store, res.run_id, case_doc, evaluation, bundle_out, trajectory)
    finally:
        store.close()
    return bundle, evaluation
