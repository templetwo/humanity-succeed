"""Helpers the suite generators share (lead-authored; builders must not edit, only use).

A generator module (``commissioning.suite_v1.cN_*``) returns ``GroupDraft`` objects. The assembler
(scripts/generate_commissioning_suite.py) turns drafts into files and a SuiteManifest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_str
from .contract import Expectation

SUITE_ID = "wp3-suite-v1"
SOURCE_REF = "constructed for the WP3 commissioning suite v1 (docs/WP3_DESIGN.md); invented"


def action(message: str | None = None, **a: Any) -> str:
    """One raw scripted output: canonical JSON of {"action": {...}} (plus an optional message)."""
    doc: dict[str, Any] = {"action": a}
    if message is not None:
        doc["message"] = message
    return canonical_str(doc)


def case_doc(*, case_id: str, root_scenario_id: str, class_id: str, task: str,
             resources: dict[str, Any], actors: list[str], readable: list[str],
             writable: list[str], notifiable: list[str], allowed_tools: list[str],
             evaluation: dict[str, Any], drafting_model: str,
             measurement_mode: str = "direct_task", derivation_ids: tuple[str, ...] = (),
             visible_resource_ids: list[str] | None = None,
             visible_actor_ids: list[str] | None = None,
             split: str = "commissioning_dev") -> dict[str, Any]:
    """A packet-schema case 1.0 document. ``resources`` maps id -> initial value (revision 1)."""
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "root_scenario_id": root_scenario_id,
        "derivation_ids": list(derivation_ids),
        "family_id": class_id.split("_", 1)[0].replace("C", "WP3-C"),
        "split": split,
        "measurement_mode": measurement_mode,
        "provenance": {
            "kind": "ai_drafted",
            "drafting_model": drafting_model,
            "source_refs": [SOURCE_REF],
            "rights_status": "pending",
            "rights_receipt": None,
            "private_material": False,
        },
        "reviews": [],
        "subject": {
            "task": task,
            "visible_resource_ids": list(visible_resource_ids if visible_resource_ids is not None
                                         else readable),
            "visible_actor_ids": list(visible_actor_ids if visible_actor_ids is not None
                                      else actors),
            "allowed_tools": list(allowed_tools),
        },
        "world": {
            "resources": {rid: {"revision": 1, "value": v} for rid, v in resources.items()},
            "actors": list(actors),
            "permissions": {"readable_ids": list(readable), "writable_ids": list(writable),
                            "notifiable_actor_ids": list(notifiable)},
            "initial_tick": 0,
            "scheduled_observations": [],
            "clarification_reply": None,
        },
        "evaluation": evaluation,
        "demonstrations": [],
    }


def trajectory_doc(*, trajectory_id: str, case_id: str, description: str, raws: list[str],
                   drafting_model: str) -> dict[str, Any]:
    return {
        "schema_id": "hs-scripted-trajectory/1",
        "trajectory_id": trajectory_id,
        "case_id": case_id,
        "provenance": {
            "kind": "ai_drafted_instrument_fixture",
            "drafting_model": drafting_model,
            "reviews": [],
            "note": "Scripted instrument input, not model output. WP3 commissioning suite v1.",
        },
        "description": description,
        "raw_outputs": list(raws),
    }


@dataclass(frozen=True)
class MemberDraft:
    fixture_id: str
    role: str
    case_stem: str               # key into GroupDraft.cases; file becomes cases/<stem>.yaml
    trajectory: dict[str, Any]   # from trajectory_doc(); file becomes trajectories/<fixture_id>.yaml
    expected: Expectation


@dataclass(frozen=True)
class GroupDraft:
    group_id: str
    class_id: str
    root_scenario_id: str
    cases: dict[str, dict[str, Any]]      # stem -> case document
    members: list[MemberDraft] = field(default_factory=list)
