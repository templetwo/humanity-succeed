"""Case source contract (packet schema case 1.0 + one recorded local extension).

Local extension (docs/DECISIONS.md B03): predicate ``proposal_exists`` so a case can deny
integrity credit for a *chosen* bad proposal even when the monitor contained it. Cases that use it
do not validate against the unmodified packet schema; `contracts.schemas` reports that honestly.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..canonical import sha256_obj
from .actions import TOOL_NAMES, ActionEnvelope, _check_json_value
from .events import EVENT_TYPES

SPLITS = (
    "commissioning_dev",
    "commissioning_holdback",
    "train",
    "dev",
    "pilot",
    "confirmatory",
    "external_regression",
)
MEASUREMENT_MODES = ("end_to_end_discovery", "after_supplied_evidence", "direct_task")
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def _json(v: Any) -> Any:
    _check_json_value(v)
    return v


# ---------------------------------------------------------------- predicates


class ResourceFieldEquals(_Strict):
    op: Literal["resource_field_equals"]
    resource_id: NonEmpty
    pointer: str
    value: Any

    @field_validator("value")
    @classmethod
    def _json_value(cls, v: Any) -> Any:
        return _json(v)


class ResourceRevisionAtLeast(_Strict):
    op: Literal["resource_revision_at_least"]
    resource_id: NonEmpty
    revision: Annotated[int, Field(ge=0)]


class NotificationExists(_Strict):
    op: Literal["notification_exists"]
    actor_id: NonEmpty
    resource_id: NonEmpty


class EventExists(_Strict):
    op: Literal["event_exists"]
    event_type: NonEmpty


class EventAbsent(_Strict):
    op: Literal["event_absent"]
    event_type: NonEmpty


class FeaturePreserved(_Strict):
    op: Literal["feature_preserved"]
    resource_id: NonEmpty
    pointer: str


class GoalCompleted(_Strict):
    op: Literal["goal_completed"]
    goal_id: NonEmpty


class EventPrecedes(_Strict):
    op: Literal["event_precedes"]
    first_event_type: NonEmpty
    second_event_type: NonEmpty


class ProposalExists(_Strict):
    """Local extension B03: a subject proposed this action type (optionally on this resource)."""

    op: Literal["proposal_exists"]
    action_type: Literal[
        "read_resource",
        "write_resource",
        "notify",
        "request_clarification",
        "decline",
        "wait",
        "finish",
    ]
    resource_id: NonEmpty | None = None


class AllOf(_Strict):
    op: Literal["all"]
    args: Annotated[list[Predicate], Field(min_length=1)]


class AnyOf(_Strict):
    op: Literal["any"]
    args: Annotated[list[Predicate], Field(min_length=1)]


class Not(_Strict):
    op: Literal["not"]
    arg: Predicate


Predicate = Annotated[
    ResourceFieldEquals
    | ResourceRevisionAtLeast
    | NotificationExists
    | EventExists
    | EventAbsent
    | FeaturePreserved
    | GoalCompleted
    | EventPrecedes
    | ProposalExists
    | AllOf
    | AnyOf
    | Not,
    Field(discriminator="op"),
]

AllOf.model_rebuild()
AnyOf.model_rebuild()
Not.model_rebuild()

LOCAL_EXTENSION_OPS = frozenset({"proposal_exists"})

# ---------------------------------------------------------------- case parts


class Provenance(_Strict):
    kind: Literal["human_authored", "ai_drafted", "ai_drafted_human_reviewed"]
    drafting_model: str | None
    source_refs: list[str]
    rights_status: Literal["pending", "approved_for_local_use", "approved_for_distribution"]
    rights_receipt: str | None
    private_material: Literal[False]


class Review(_Strict):
    reviewer_ref: NonEmpty
    reviewer_kind: Literal["human", "model"]
    role: Literal["author", "reviewer", "adjudicator"]
    source_sha256: Sha256
    timestamp_utc: NonEmpty
    verdict: Literal["approve", "revise", "reject"]
    reason: NonEmpty


class Subject(_Strict):
    task: NonEmpty
    visible_resource_ids: list[NonEmpty]
    visible_actor_ids: list[NonEmpty]
    allowed_tools: Annotated[
        list[
            Literal[
                "read_resource",
                "write_resource",
                "notify",
                "request_clarification",
                "decline",
                "wait",
                "finish",
            ]
        ],
        Field(min_length=1),
    ]


class ResourceState(_Strict):
    revision: Annotated[int, Field(ge=0)]
    value: Any

    @field_validator("value")
    @classmethod
    def _json_value(cls, v: Any) -> Any:
        return _json(v)


class Permissions(_Strict):
    readable_ids: list[NonEmpty]
    writable_ids: list[NonEmpty]
    notifiable_actor_ids: list[NonEmpty]


class ScheduledObservation(_Strict):
    at_tick: Annotated[int, Field(ge=0)]
    observation: str


class World(_Strict):
    resources: dict[str, ResourceState]
    actors: list[NonEmpty]
    permissions: Permissions
    initial_tick: Annotated[int, Field(ge=0)]
    scheduled_observations: list[ScheduledObservation]
    clarification_reply: str | None


class RubricItem(_Strict):
    dimension: NonEmpty
    instruction: NonEmpty


class Evaluation(_Strict):
    scoring_mode: Literal["mechanical", "hybrid", "human"]
    pass_if: Predicate
    fail_if: list[Predicate]
    human_rubric: list[RubricItem]
    scope_limitations: list[NonEmpty]


class Demonstration(_Strict):
    demo_id: NonEmpty
    training_role: Literal["preferred", "counterexample"]
    expected_mechanical_outcome: Literal["pass", "fail", "not_evaluable"]
    actions: Annotated[list[ActionEnvelope], Field(min_length=1)]


class CaseSource(_Strict):
    schema_version: Literal["1.0"]
    case_id: NonEmpty
    root_scenario_id: NonEmpty
    derivation_ids: list[NonEmpty]
    family_id: NonEmpty
    split: Literal[
        "commissioning_dev",
        "commissioning_holdback",
        "train",
        "dev",
        "pilot",
        "confirmatory",
        "external_regression",
    ]
    measurement_mode: Literal["end_to_end_discovery", "after_supplied_evidence", "direct_task"]
    provenance: Provenance
    reviews: list[Review]
    subject: Subject
    world: World
    evaluation: Evaluation
    demonstrations: list[Demonstration] = []


# ---------------------------------------------------------------- semantic checks


class CaseSemanticError(ValueError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


_INDEX = re.compile(r"0|[1-9][0-9]*", re.ASCII)
# Identifiers become file and directory names (compiler, demo, stores) and must never act as paths.
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)


def invalid_ids(case: CaseSource) -> list[str]:
    ids = [("case_id", case.case_id), ("root_scenario_id", case.root_scenario_id),
           ("family_id", case.family_id)]
    ids += [("derivation_ids", d) for d in case.derivation_ids]
    ids += [("world.resources", r) for r in case.world.resources]
    ids += [("world.actors", a) for a in case.world.actors]
    ids += [("demonstrations.demo_id", d.demo_id) for d in case.demonstrations]
    return [f"{where}: {v!r} is not a valid identifier ({ID_PATTERN.pattern})"
            for where, v in ids if not ID_PATTERN.fullmatch(v)]


def resolve_pointer(doc: Any, pointer: str) -> tuple[bool, Any]:
    """RFC 6901. Returns (found, value). Array indices must be canonical decimal."""
    if pointer == "":
        return True, doc
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer {pointer!r}")
    cur = doc
    for raw in pointer[1:].split("/"):
        tok = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if tok not in cur:
                return False, None
            cur = cur[tok]
        elif isinstance(cur, list):
            # RFC 6901 array index: ASCII "0" or a nonzero ASCII digit run. str.isdigit() would
            # accept Unicode digits such as "²" that int() then rejects.
            if not _INDEX.fullmatch(tok):
                return False, None
            i = int(tok)
            if i >= len(cur):
                return False, None
            cur = cur[i]
        else:
            return False, None
    return True, cur


def iter_predicates(p: Any):
    yield p
    if isinstance(p, (AllOf, AnyOf)):
        for a in p.args:
            yield from iter_predicates(a)
    elif isinstance(p, Not):
        yield from iter_predicates(p.arg)


def uses_local_extension(case: CaseSource) -> bool:
    preds = [*iter_predicates(case.evaluation.pass_if)]
    for f in case.evaluation.fail_if:
        preds.extend(iter_predicates(f))
    return any(p.op in LOCAL_EXTENSION_OPS for p in preds)


def semantic_problems(case: CaseSource) -> list[str]:
    """Reference and invariant checks the JSON Schema cannot express."""
    probs: list[str] = invalid_ids(case)
    w = case.world
    res = set(w.resources)
    actors = set(w.actors)
    if len(actors) != len(w.actors):
        probs.append("world.actors contains duplicates")
    for rid in case.subject.visible_resource_ids:
        if rid not in res:
            probs.append(f"subject.visible_resource_ids: unknown resource {rid!r}")
    for aid in case.subject.visible_actor_ids:
        if aid not in actors:
            probs.append(f"subject.visible_actor_ids: unknown actor {aid!r}")
    for name, ids, universe in (
        ("readable_ids", w.permissions.readable_ids, res),
        ("writable_ids", w.permissions.writable_ids, res),
        ("notifiable_actor_ids", w.permissions.notifiable_actor_ids, actors),
    ):
        for i in ids:
            if i not in universe:
                probs.append(f"world.permissions.{name}: unknown id {i!r}")
    for i in w.permissions.writable_ids:
        if i not in w.permissions.readable_ids:
            probs.append(f"world.permissions: writable {i!r} is not readable")
    for rid, st in w.resources.items():
        if st.revision < 1:
            probs.append(f"world.resources.{rid}: initial revision must be >= 1")
    if len(set(case.subject.allowed_tools)) != len(case.subject.allowed_tools):
        probs.append("subject.allowed_tools contains duplicates")
    ticks = [o.at_tick for o in w.scheduled_observations]
    if any(t <= w.initial_tick for t in ticks):
        probs.append("world.scheduled_observations must fire after initial_tick")

    preds = [*iter_predicates(case.evaluation.pass_if)]
    for f in case.evaluation.fail_if:
        preds.extend(iter_predicates(f))
    for p in preds:
        rid = getattr(p, "resource_id", None)
        if rid is not None and rid not in res:
            probs.append(f"predicate {p.op}: unknown resource {rid!r}")
        if isinstance(p, NotificationExists) and p.actor_id not in actors:
            probs.append(f"predicate notification_exists: unknown actor {p.actor_id!r}")
        for attr in ("event_type", "first_event_type", "second_event_type"):
            et = getattr(p, attr, None)
            if et is not None and et not in EVENT_TYPES:
                probs.append(f"predicate {p.op}: unregistered event type {et!r}")
        if isinstance(p, GoalCompleted):
            probs.append(
                "predicate goal_completed: unsupported — world schema 1.0 defines no goal "
                "registry (docs/DECISIONS.md B04)"
            )
        if isinstance(p, (ResourceFieldEquals, FeaturePreserved)) and p.resource_id in res:
            try:
                found, _ = resolve_pointer(w.resources[p.resource_id].value, p.pointer)
            except ValueError as e:
                probs.append(f"predicate {p.op}: {e}")
                continue
            if isinstance(p, FeaturePreserved) and not found:
                probs.append(
                    f"predicate feature_preserved: pointer {p.pointer!r} absent in initial "
                    f"{p.resource_id!r}"
                )

    demo_ids = [d.demo_id for d in case.demonstrations]
    if len(set(demo_ids)) != len(demo_ids):
        probs.append("demonstrations: duplicate demo_id")
    for d in case.demonstrations:
        if d.training_role == "preferred" and d.expected_mechanical_outcome != "pass":
            probs.append(
                f"demonstration {d.demo_id}: a preferred trajectory must expect a mechanical pass"
            )
    if case.case_id in case.derivation_ids:
        probs.append("derivation_ids: a case cannot derive from itself")
    if case.provenance.kind == "ai_drafted_human_reviewed" and not any(
        r.reviewer_kind == "human" for r in case.reviews
    ):
        probs.append("provenance.kind claims human review but no human review record exists")
    return probs


def review_source_sha256(case_doc: dict[str, Any]) -> str:
    """The hash a review must cite: the case document with its reviews array removed."""
    return sha256_obj({k: v for k, v in case_doc.items() if k != "reviews"})


def review_status(case: CaseSource, case_doc: dict[str, Any]) -> dict[str, Any]:
    """Derive review state from actual records. Model reviews never count as human reviews."""
    src = review_source_sha256(case_doc)
    current_human = [
        r
        for r in case.reviews
        if r.reviewer_kind == "human" and r.role in ("reviewer", "adjudicator")
        and r.source_sha256 == src
    ]
    stale = [r.reviewer_ref for r in case.reviews if r.source_sha256 != src]
    approvals = sorted({r.reviewer_ref for r in current_human if r.verdict == "approve"})
    rejections = sorted({r.reviewer_ref for r in current_human if r.verdict != "approve"})
    if rejections:
        state = "human_review_not_approved"
    elif approvals:
        state = "human_reviewed_approved"
    else:
        state = "draft"
    return {
        "state": state,
        "review_source_sha256": src,
        "human_approvals": approvals,
        "human_non_approvals": rejections,
        "stale_review_refs": stale,
        "model_reviews_counted_as_human": 0,
    }


__all__ = [
    "CaseSource",
    "CaseSemanticError",
    "Predicate",
    "SPLITS",
    "MEASUREMENT_MODES",
    "TOOL_NAMES",
    "resolve_pointer",
    "semantic_problems",
    "review_status",
    "review_source_sha256",
    "uses_local_extension",
    "iter_predicates",
]
