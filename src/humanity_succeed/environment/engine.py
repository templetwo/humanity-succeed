"""Native synthetic workroom: world state, reference monitor, executor (BUILD_SPEC §6).

Proposal, permission, execution and effect are four distinct records. The monitor decides
permission only; it is not the moral scorer. The executor owns every effect. No shell, file,
network, real message or device operation exists here.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from ..canonical import sha256_obj
from ..contracts.actions import (
    ActionEnvelope,
    Decline,
    Finish,
    Notify,
    ReadResource,
    RequestClarification,
    Wait,
    WriteResource,
)
from ..contracts.case import World
from ..evidence.store import PendingEvent, PendingRevision


@dataclass
class WorldState:
    resources: dict[str, dict[str, Any]]  # rid -> {"revision": int, "value": Any}
    actors: tuple[str, ...]
    readable: frozenset[str]
    writable: frozenset[str]
    notifiable: frozenset[str]
    tick: int
    scheduled: list[tuple[int, str]]
    released: set[int] = field(default_factory=set)
    clarification_reply: str | None = None
    inbox: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    @classmethod
    def from_world(cls, w: World) -> WorldState:
        return cls(
            resources={
                rid: {"revision": st.revision, "value": copy.deepcopy(st.value)}
                for rid, st in w.resources.items()
            },
            actors=tuple(w.actors),
            readable=frozenset(w.permissions.readable_ids),
            writable=frozenset(w.permissions.writable_ids),
            notifiable=frozenset(w.permissions.notifiable_actor_ids),
            tick=w.initial_tick,
            scheduled=[(o.at_tick, o.observation) for o in w.scheduled_observations],
            clarification_reply=w.clarification_reply,
            inbox={a: [] for a in w.actors},
        )


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason_code: str


class ReferenceMonitor:
    """Permission from trusted world state only; never from model text."""

    def __init__(self, allowed_tools: tuple[str, ...], max_wait: int = 100) -> None:
        self.allowed_tools = frozenset(allowed_tools)
        self.max_wait = max_wait

    def decide(self, env: ActionEnvelope, st: WorldState) -> Decision:
        a = env.action
        if a.type not in self.allowed_tools:
            return Decision(False, "tool_not_allowed")
        if isinstance(a, ReadResource):
            # Unknown and unreadable are indistinguishable to the subject.
            ok = a.resource_id in st.readable and a.resource_id in st.resources
            return Decision(ok, "ok" if ok else "not_permitted")
        if isinstance(a, WriteResource):
            ok = a.resource_id in st.writable and a.resource_id in st.resources
            return Decision(ok, "ok" if ok else "not_permitted")
        if isinstance(a, Notify):
            ok = all(x in st.notifiable for x in a.actor_ids) and all(
                r in st.readable for r in a.resource_ids
            )
            if len(set(a.actor_ids)) != len(a.actor_ids):
                return Decision(False, "duplicate_recipient")
            return Decision(ok, "ok" if ok else "not_permitted")
        if isinstance(a, Finish):
            ok = all(r in st.readable for r in a.delivered_resource_ids)
            return Decision(ok, "ok" if ok else "not_permitted")
        if isinstance(a, Wait):
            ok = a.ticks <= self.max_wait
            return Decision(ok, "ok" if ok else "limit_exceeded")
        if isinstance(a, (RequestClarification, Decline)):
            return Decision(True, "ok")
        return Decision(False, "unregistered_action")  # pragma: no cover - union is closed


@dataclass
class Execution:
    """What one allowed action did. ``events`` are appended in one transaction with ``revisions``."""

    result: str
    effect: str
    detail: dict[str, Any]
    effect_events: list[PendingEvent]
    revisions: list[tuple[str, int, Any]]  # (rid, revision, value)
    subject_result: dict[str, Any]
    terminal: str | None = None


class Executor:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    def execute(self, env: ActionEnvelope, st: WorldState, proposal_seq: int) -> Execution:
        a = env.action
        t = st.tick
        if isinstance(a, ReadResource):
            r = st.resources[a.resource_id]
            return Execution(
                "ok", "read", {"resource_id": a.resource_id, "revision": r["revision"]}, [], [],
                {"status": "ok", "resource_id": a.resource_id, "revision": r["revision"],
                 "value": copy.deepcopy(r["value"])},
            )
        if isinstance(a, WriteResource):
            r = st.resources[a.resource_id]
            if a.expected_revision != r["revision"]:
                return Execution(
                    "revision_conflict", "none",
                    {"resource_id": a.resource_id, "current_revision": r["revision"]}, [], [],
                    {"status": "revision_conflict", "resource_id": a.resource_id,
                     "current_revision": r["revision"]},
                )
            if _json_kind(a.value) != _json_kind(r["value"]):
                return Execution(
                    "type_mismatch", "none", {"resource_id": a.resource_id}, [], [],
                    {"status": "type_mismatch", "resource_id": a.resource_id},
                )
            new_rev = r["revision"] + 1
            ev = PendingEvent("resource_revised", "executor", t, {
                "proposal_seq": proposal_seq,
                "resource_id": a.resource_id,
                "old_revision": r["revision"],
                "new_revision": new_rev,
                "old_value_sha256": sha256_obj(r["value"]),
                "new_value_sha256": sha256_obj(a.value),
                "new_value": copy.deepcopy(a.value),
            })
            return Execution(
                "ok", "resource_revised",
                {"resource_id": a.resource_id, "new_revision": new_rev}, [ev],
                [(a.resource_id, new_rev, copy.deepcopy(a.value))],
                {"status": "ok", "resource_id": a.resource_id, "revision": new_rev},
            )
        if isinstance(a, Notify):
            evs, receipts = [], []
            for actor in a.actor_ids:
                rid = "rcpt_" + sha256_obj([self.run_id, proposal_seq, actor])[:16]
                receipts.append({"actor_id": actor, "receipt_id": rid})
                evs.append(PendingEvent("notification_delivered", "executor", t, {
                    "proposal_seq": proposal_seq,
                    "receipt_id": rid,
                    "actor_id": actor,
                    "resource_ids": list(a.resource_ids),
                    "text": a.text,
                }))
            return Execution(
                "ok", "notification_delivered", {"receipts": receipts}, evs, [],
                {"status": "ok", "receipts": receipts},
            )
        if isinstance(a, RequestClarification):
            if st.clarification_reply is None:
                ev = PendingEvent("awaiting_input", "executor", t, {"proposal_seq": proposal_seq})
                return Execution("ok", "awaiting_input", {}, [ev], [],
                                 {"status": "awaiting_input"}, terminal="awaiting_input")
            ev = PendingEvent("clarification_delivered", "executor", t, {
                "proposal_seq": proposal_seq,
                "reply_sha256": sha256_obj(st.clarification_reply),
            })
            return Execution("ok", "clarification_delivered", {}, [ev], [],
                             {"status": "ok", "reply": st.clarification_reply})
        if isinstance(a, Decline):
            ev = PendingEvent("task_declined", "executor", t, {
                "proposal_seq": proposal_seq, "reason": a.reason, "alternative": a.alternative,
            })
            return Execution("ok", "task_declined", {}, [ev], [], {"status": "ok"},
                             terminal="declined")
        if isinstance(a, Wait):
            new_tick = st.tick + a.ticks
            released = [
                (i, text) for i, (at, text) in enumerate(st.scheduled)
                if at <= new_tick and i not in st.released
            ]
            return Execution(
                "ok", "clock_advanced",
                {"from_tick": st.tick, "to_tick": new_tick, "released": [i for i, _ in released]},
                [], [],
                {"status": "ok", "tick": new_tick, "observations": [x for _, x in released]},
            )
        if isinstance(a, Finish):
            ev = PendingEvent("task_finished", "executor", t, {
                "proposal_seq": proposal_seq,
                "summary": a.summary,
                "delivered_resource_ids": list(a.delivered_resource_ids),
            })
            return Execution("ok", "task_finished", {}, [ev], [], {"status": "ok"},
                             terminal="finished")
        raise AssertionError("closed action union")  # pragma: no cover

    @staticmethod
    def apply(ex: Execution, st: WorldState) -> None:
        """Mirror a committed execution into in-memory state (after the SQLite commit)."""
        for rid, rev, value in ex.revisions:
            st.resources[rid] = {"revision": rev, "value": value}
        for ev in ex.effect_events:
            if ev.event_type == "notification_delivered":
                st.inbox[ev.payload["actor_id"]].append(ev.payload)
        if ex.effect == "clock_advanced":
            st.tick = ex.detail["to_tick"]
            st.released.update(ex.detail["released"])


def revision_rows(ex: Execution, first_index: int) -> list[PendingRevision]:
    """Bind each revision to its resource_revised event within one append batch."""
    rows = []
    idx = first_index
    for ev in ex.effect_events:
        if ev.event_type == "resource_revised":
            rid = ev.payload["resource_id"]
            match = [r for r in ex.revisions if r[0] == rid]
            rows.append(PendingRevision(rid, match[0][1], match[0][2], idx))
        idx += 1
    return rows


def _json_kind(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    return type(v).__name__
