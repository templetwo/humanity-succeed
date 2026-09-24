"""Episode lifecycle (BUILD_SPEC §6.3, §7).

Per turn: raw response recorded -> parse result -> proposed action recorded -> permission decision
-> atomic execution result with revision evidence -> next observation. No retry, no repair, no
resume. A crash leaves the store in a state ``derive_status`` reports honestly.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pydantic

from .. import COMPILER_VERSION, ENGINE_VERSION, EVALUATOR_VERSION, __version__
from ..canonical import canonical_bytes, sha256_bytes, sha256_obj
from ..contracts.actions import ParseFailure, action_to_dict, parse_action
from ..contracts.case import CaseSource
from ..corpus.views import (
    INTERFACE_ID,
    INTERFACE_TEXT,
    VisibleTurn,
    build_provider_input,
    four_views,
    subject_view,
)
from ..environment.engine import Executor, ReferenceMonitor, WorldState, revision_rows
from ..evidence.store import EvidenceStore, PendingEvent
from ..providers.scripted import ScriptExhausted

DEFAULT_COMMISSIONING_LIMITS = {"max_provider_calls": 12, "max_output_bytes": 64_000}


class Provider(Protocol):
    kind: str

    def generate(self, provider_input: bytes) -> str: ...


class SimulatedCrash(RuntimeError):
    """Test-only fault injection: the process 'dies' between permission and execution."""


@dataclass
class EpisodeResult:
    run_id: str
    terminal_status: str
    manifest_sha256: str


def _git(args: list[str]) -> str | None:
    root = Path(__file__).resolve().parents[3]
    if not (root / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, check=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8", "replace")


def code_identity() -> dict[str, Any]:
    head = _git(["rev-parse", "HEAD"])
    diff = _git(["diff", "HEAD", "--", "src", "pyproject.toml", "uv.lock"])
    return {
        "commit": head.strip() if head else None,
        "dirty_diff_sha256": sha256_bytes(diff.encode()) if diff else None,
        "dirty": bool(diff) if diff is not None else None,
    }


def build_manifest(
    case: CaseSource,
    case_doc: dict[str, Any],
    views: dict[str, Any],
    provider: Provider,
    trajectory: dict[str, Any] | None,
    limits: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_id": "hs-run-manifest/1",
        "evidence_class": "scripted_instrument",
        "code": code_identity(),
        "versions": {
            "package": __version__,
            "compiler": COMPILER_VERSION,
            "engine": ENGINE_VERSION,
            "evaluator": EVALUATOR_VERSION,
            "python": platform.python_version(),
            "pydantic": pydantic.VERSION,
            "platform": f"{sys.platform}-{platform.machine()}",
        },
        "source": {
            "case_id": case.case_id,
            "case_source_sha256": sha256_obj(case_doc),
            "view_sha256": {k: sha256_obj(v) for k, v in views.items()},
        },
        "backend": "native_synthetic_engine",
        "provider": {
            "kind": provider.kind,
            "model_files": None,
            "tokenizer_sha256": None,
            "chat_template_sha256": None,
            "adapter_sha256": None,
            "note": "scripted instrument; no model was loaded or called",
        },
        "trajectory": (
            {"trajectory_id": trajectory["trajectory_id"], "sha256": sha256_obj(trajectory)}
            if trajectory
            else None
        ),
        "interface": {"id": INTERFACE_ID, "text_sha256": sha256_bytes(INTERFACE_TEXT.encode())},
        "principles_block": None,
        "condition_identity": "scripted_instrument (host-side; no study cell)",
        "limits": dict(limits),
        "approval_ref": {
            "kind": "scripted_build_scope",
            "ref": "docs/receipts/SCOPE_RECEIPT.md",
            "model_authorization": None,
        },
        "seeds": {"generation": None, "task_order": None, "training": None},
    }


def run_episode(
    case: CaseSource,
    case_doc: dict[str, Any],
    provider: Provider,
    store: EvidenceStore,
    *,
    trajectory: dict[str, Any] | None = None,
    limits: dict[str, Any] | None = None,
    run_id: str | None = None,
    fault: str | None = None,
) -> EpisodeResult:
    limits = dict(DEFAULT_COMMISSIONING_LIMITS if limits is None else limits)
    views = four_views(case, case_doc)
    manifest = build_manifest(case, case_doc, views, provider, trajectory, limits)
    run_id = run_id or "run_" + uuid.uuid4().hex[:20]
    initial = {rid: {"revision": r.revision, "value": r.value} for rid, r in case.world.resources.items()}
    m_sha = store.begin_run(run_id, manifest, initial)
    for name in ("subject", "world", "evaluator", "provenance"):
        store.put_artifact(f"view:{name}", canonical_bytes(views[name]))

    st = WorldState.from_world(case.world)
    sview = subject_view(case)
    monitor = ReferenceMonitor(sview.allowed_tools)
    executor = Executor(run_id)
    tick0 = st.tick
    turns: list[VisibleTurn] = []

    store.append(run_id, [PendingEvent("run_started", "runner", st.tick, {
        "manifest_sha256": m_sha,
        "evidence_class": "scripted_instrument",
        "subject_view_sha256": sha256_obj(views["subject"]),
        "world_view_sha256": sha256_obj(views["world"]),
        "evaluator_view_sha256": sha256_obj(views["evaluator"]),
        "provenance_view_sha256": sha256_obj(views["provenance"]),
    })])

    terminal: str | None = None
    for call_index in range(limits["max_provider_calls"]):
        pin = build_provider_input(sview, tick0, turns)
        pin_sha = store.put_artifact("provider_input", pin)
        store.append(run_id, [
            PendingEvent("observation_delivered", "runner", st.tick, {
                "observation_index": call_index, "observation_sha256": pin_sha,
                "byte_length": len(pin),
            }),
            PendingEvent("provider_requested", "runner", st.tick, {
                "call_index": call_index, "input_sha256": pin_sha,
            }),
        ])
        try:
            raw = provider.generate(pin)
        except ScriptExhausted as e:
            store.append(run_id, [PendingEvent("provider_error", "runner", st.tick, {
                "call_index": call_index, "code": "script_exhausted", "detail": str(e),
            })])
            terminal = "provider_failure"
            break
        raw_bytes = raw.encode("utf-8")
        raw_sha = store.put_artifact("raw_response", raw_bytes)
        store.append(run_id, [PendingEvent("provider_response", "subject", st.tick, {
            "call_index": call_index, "raw_sha256": raw_sha, "byte_length": len(raw_bytes),
        })])

        try:
            env = parse_action(raw)
        except ParseFailure as pf:
            store.append(run_id, [PendingEvent("action_parse_failed", "runner", st.tick, {
                "call_index": call_index, "raw_sha256": raw_sha, "code": pf.code,
                "detail": pf.detail,
            })])
            turns.append(VisibleTurn(raw_output=raw, tool_result={
                "status": "invalid_action", "code": pf.code,
            }))
            continue

        ad = action_to_dict(env)
        [prop] = store.append(run_id, [PendingEvent("action_proposed", "subject", st.tick, {
            "call_index": call_index, "action": ad["action"], "message": ad.get("message"),
        })])
        pseq = prop["sequence"]

        decision = monitor.decide(env, st)
        perm_events = [PendingEvent("permission_decided", "monitor", st.tick, {
            "proposal_seq": pseq, "decision": "allow" if decision.allow else "deny",
            "reason_code": decision.reason_code,
        })]
        if not decision.allow:
            # permission_seq is the sequence the permission event will receive (pseq + 1).
            perm_events.append(PendingEvent("action_denied", "monitor", st.tick, {
                "proposal_seq": pseq, "permission_seq": pseq + 1,
                "reason_code": decision.reason_code,
            }))
        stored_perm = store.append(run_id, perm_events)
        perm_seq = stored_perm[0]["sequence"]
        if not decision.allow:
            turns.append(VisibleTurn(raw_output=raw, tool_result={
                "status": "denied", "reason": "not_permitted",
            }))
            continue

        if fault == "after_permission":
            raise SimulatedCrash("injected crash between permission and execution")

        ex = executor.execute(env, st, pseq)
        batch = [PendingEvent("action_executed", "executor", st.tick, {
            "proposal_seq": pseq, "permission_seq": perm_seq, "result": ex.result,
            "effect": ex.effect, "detail": ex.detail,
        }), *ex.effect_events]
        store.append(run_id, batch, revision_rows(ex, first_index=1))
        Executor.apply(ex, st)
        turns.append(VisibleTurn(raw_output=raw, tool_result=ex.subject_result))
        if ex.terminal:
            terminal = ex.terminal
            break
    else:
        store.append(run_id, [PendingEvent("budget_exhausted", "runner", st.tick, {
            "limit_name": "provider_calls", "limit_value": limits["max_provider_calls"],
        })])
        terminal = "budget_exhausted"

    store.append(run_id, [PendingEvent("run_completed", "runner", st.tick, {
        "terminal_status": terminal,
    })])
    return EpisodeResult(run_id, terminal or "unknown", m_sha)


def derive_status(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Execution status from records only. Never infers success from a missing error."""
    completed = [e for e in events if e["event_type"] == "run_completed"]
    if completed:
        return {"execution_status": "completed",
                "terminal_status": completed[-1]["payload"]["terminal_status"]}
    perms = {e["payload"]["proposal_seq"]: e for e in events
             if e["event_type"] == "permission_decided" and e["payload"]["decision"] == "allow"}
    executed = {e["payload"]["proposal_seq"] for e in events if e["event_type"] == "action_executed"}
    dangling = sorted(set(perms) - executed)
    if dangling:
        return {"execution_status": "interrupted_uncertain",
                "terminal_status": None,
                "permitted_not_executed_proposals": dangling}
    return {"execution_status": "interrupted", "terminal_status": None}
