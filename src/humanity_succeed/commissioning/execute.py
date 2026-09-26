"""Run one scripted trajectory in memory and describe what it did (lead-authored; do not edit).

``enactment`` describes what the trajectory *did* (parse failures, denials, revision conflicts,
terminal status) without looking at any verdict, so a generator test can check that a fixture
enacts its description without peeking at the evaluator it is meant to commission.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts.case import CaseSource
from ..evidence.store import EvidenceStore
from ..providers.scripted import ScriptedProvider
from ..runner.episode import derive_status, run_episode
from .contract import Expectation


def run_in_memory(case: CaseSource, case_doc: dict[str, Any], raws: list[str], *,
                  run_id: str = "run_commission", evaluate: bool = True
                  ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Returns (evaluation or None, events). Nothing is written to disk."""
    from ..runner.scripted import evaluate_and_record

    store = EvidenceStore(Path(":memory:"))
    try:
        run_episode(case, case_doc, ScriptedProvider(list(raws)), store, run_id=run_id)
        ev = evaluate_and_record(store, run_id, case) if evaluate else None
        events = store.events(run_id)
    finally:
        store.close()
    return ev, events


def enactment(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Verdict-free description of a run."""
    executed = [e for e in events if e["event_type"] == "action_executed"]
    return {
        "execution": derive_status(events),
        "parse_failures": [e["payload"]["code"] for e in events
                           if e["event_type"] == "action_parse_failed"],
        "denied": [e["payload"]["reason_code"] for e in events
                   if e["event_type"] == "action_denied"],
        "results": [e["payload"]["result"] for e in executed],
        "effects": [e["payload"]["effect"] for e in executed],
        "writes": [(e["payload"]["resource_id"], e["payload"]["new_value"]) for e in events
                   if e["event_type"] == "resource_revised"],
        "notified": [(e["payload"]["actor_id"], e["payload"]["resource_ids"]) for e in events
                     if e["event_type"] == "notification_delivered"],
        "declined": any(e["event_type"] == "task_declined" for e in events),
        "finished": any(e["event_type"] == "task_finished" for e in events),
    }


def observed(evaluation: dict[str, Any]) -> dict[str, Any]:
    return {"mechanical": evaluation["mechanical"]["verdict"],
            "conduct": evaluation["conduct_outcome"],
            "contained": evaluation["containment"]["contained"]}


def matches(expected: Expectation, obs: dict[str, Any]) -> bool:
    return (expected.mechanical, expected.conduct, expected.contained) == (
        obs["mechanical"], obs["conduct"], obs["contained"])
