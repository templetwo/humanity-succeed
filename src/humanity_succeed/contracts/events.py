"""Event envelope (packet event schema 1.0) plus event-type-specific payload contracts.

The packet schema's generic ``payload: object`` is refined here: every registered event type has an
exact payload model, unknown payload keys are rejected, and an event type outside the registered
enum cannot be stored or referenced by a predicate.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EVENT_TYPES = (
    "run_started",
    "observation_delivered",
    "provider_requested",
    "provider_response",
    "provider_error",
    "action_parse_failed",
    "action_proposed",
    "permission_decided",
    "action_executed",
    "action_denied",
    "resource_revised",
    "notification_delivered",
    "clarification_delivered",
    "awaiting_input",
    "task_finished",
    "task_declined",
    "context_overflow",
    "budget_exhausted",
    "run_interrupted",
    "run_completed",
    "evaluation_recorded",
)
ACTOR_KINDS = ("subject", "runner", "monitor", "executor", "evaluator", "operator")
GENESIS_PREV_HASH = "0" * 64

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Seq = Annotated[int, Field(ge=0)]


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RunStarted(_P):
    manifest_sha256: Sha256
    evidence_class: Literal["scripted_instrument", "model_observation", "synthetic_statistical_fixture"]
    subject_view_sha256: Sha256
    world_view_sha256: Sha256
    evaluator_view_sha256: Sha256
    provenance_view_sha256: Sha256


class ObservationDelivered(_P):
    observation_index: Seq
    observation_sha256: Sha256
    byte_length: Seq


class ProviderRequested(_P):
    call_index: Seq
    input_sha256: Sha256


class ProviderResponse(_P):
    call_index: Seq
    raw_sha256: Sha256
    byte_length: Seq


class ProviderError(_P):
    call_index: Seq
    code: str
    detail: str


class ActionParseFailed(_P):
    call_index: Seq
    raw_sha256: Sha256
    code: str
    detail: str


class ActionProposed(_P):
    call_index: Seq
    action: dict[str, Any]
    message: str | None


class PermissionDecided(_P):
    proposal_seq: Seq
    decision: Literal["allow", "deny"]
    reason_code: str


class ActionExecuted(_P):
    proposal_seq: Seq
    permission_seq: Seq
    result: Literal["ok", "revision_conflict", "type_mismatch"]
    effect: Literal[
        "none",
        "read",
        "resource_revised",
        "notification_delivered",
        "clarification_delivered",
        "awaiting_input",
        "clock_advanced",
        "task_finished",
        "task_declined",
    ]
    detail: dict[str, Any]


class ActionDenied(_P):
    proposal_seq: Seq
    permission_seq: Seq
    reason_code: str


class ResourceRevised(_P):
    proposal_seq: Seq
    resource_id: str
    old_revision: Seq
    new_revision: Seq
    old_value_sha256: Sha256
    new_value_sha256: Sha256
    new_value: Any


class NotificationDelivered(_P):
    proposal_seq: Seq
    receipt_id: str
    actor_id: str
    resource_ids: list[str]
    text: str


class ClarificationDelivered(_P):
    proposal_seq: Seq
    reply_sha256: Sha256


class AwaitingInput(_P):
    proposal_seq: Seq


class TaskFinished(_P):
    proposal_seq: Seq
    summary: str
    delivered_resource_ids: list[str]


class TaskDeclined(_P):
    proposal_seq: Seq
    reason: str
    alternative: str | None


class ContextOverflow(_P):
    call_index: Seq
    input_tokens: Seq
    reserved_output_tokens: Seq
    limit_tokens: Seq


class BudgetExhausted(_P):
    limit_name: Literal["provider_calls"]
    limit_value: Seq


class RunInterrupted(_P):
    reason: str


class RunCompleted(_P):
    terminal_status: Literal[
        "finished",
        "declined",
        "awaiting_input",
        "budget_exhausted",
        "provider_failure",
        "context_overflow",
    ]


class EvaluationRecorded(_P):
    evaluation_sha256: Sha256
    evaluator_version: str


PAYLOAD_MODELS: dict[str, type[_P]] = {
    "run_started": RunStarted,
    "observation_delivered": ObservationDelivered,
    "provider_requested": ProviderRequested,
    "provider_response": ProviderResponse,
    "provider_error": ProviderError,
    "action_parse_failed": ActionParseFailed,
    "action_proposed": ActionProposed,
    "permission_decided": PermissionDecided,
    "action_executed": ActionExecuted,
    "action_denied": ActionDenied,
    "resource_revised": ResourceRevised,
    "notification_delivered": NotificationDelivered,
    "clarification_delivered": ClarificationDelivered,
    "awaiting_input": AwaitingInput,
    "task_finished": TaskFinished,
    "task_declined": TaskDeclined,
    "context_overflow": ContextOverflow,
    "budget_exhausted": BudgetExhausted,
    "run_interrupted": RunInterrupted,
    "run_completed": RunCompleted,
    "evaluation_recorded": EvaluationRecorded,
}
assert set(PAYLOAD_MODELS) == set(EVENT_TYPES)

EVENT_ACTORS: dict[str, tuple[str, ...]] = {
    "run_started": ("runner",),
    "observation_delivered": ("runner",),
    "provider_requested": ("runner",),
    "provider_response": ("subject",),
    "provider_error": ("runner",),
    "action_parse_failed": ("runner",),
    "action_proposed": ("subject",),
    "permission_decided": ("monitor",),
    "action_executed": ("executor",),
    "action_denied": ("monitor",),
    "resource_revised": ("executor",),
    "notification_delivered": ("executor",),
    "clarification_delivered": ("executor",),
    "awaiting_input": ("executor",),
    "task_finished": ("executor",),
    "task_declined": ("executor",),
    "context_overflow": ("runner",),
    "budget_exhausted": ("runner",),
    "run_interrupted": ("runner", "operator"),
    "run_completed": ("runner",),
    "evaluation_recorded": ("evaluator",),
}


def actor_permitted(event_type: str, actor_kind: str) -> bool:
    """The one event-to-actor contract. The store applies it on write and bundle verification
    applies it again on read, so a re-hashed chain cannot move an effect to another actor."""
    return actor_kind in EVENT_ACTORS.get(event_type, ())


def validate_payload(event_type: str, payload: dict[str, Any]) -> None:
    if event_type not in PAYLOAD_MODELS:
        raise ValueError(f"unregistered event type {event_type!r}")
    PAYLOAD_MODELS[event_type].model_validate(payload, strict=True)


class EventEnvelope(_P):
    schema_version: Literal["1.0"]
    run_id: Annotated[str, Field(min_length=1)]
    sequence: Seq
    event_type: Literal[
        "run_started",
        "observation_delivered",
        "provider_requested",
        "provider_response",
        "provider_error",
        "action_parse_failed",
        "action_proposed",
        "permission_decided",
        "action_executed",
        "action_denied",
        "resource_revised",
        "notification_delivered",
        "clarification_delivered",
        "awaiting_input",
        "task_finished",
        "task_declined",
        "context_overflow",
        "budget_exhausted",
        "run_interrupted",
        "run_completed",
        "evaluation_recorded",
    ]
    timestamp_utc: str
    tick: Seq
    actor_kind: Literal["subject", "runner", "monitor", "executor", "evaluator", "operator"]
    payload: dict[str, Any]
    prev_hash: Sha256
    event_hash: Sha256
