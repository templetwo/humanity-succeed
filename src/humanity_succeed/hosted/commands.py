"""Explicit hosted command paths; offline commands retain their defaults."""

from __future__ import annotations

from pathlib import Path

from ..canonical import canonical_bytes, load_document, sha256_obj, strict_json_loads, write_new_file
from ..evidence.bundle import export_bundle
from ..evidence.store import EvidenceStore
from ..runner.episode import run_episode
from ..runner.scripted import evaluate_and_record, load_case
from .contracts import Authorization, HostedPlan
from .provider import DeepSeekProvider, make_plan
from .transport import HostedFailure


def plan_command(a):
    from ..cli import emit, envelope

    case, doc = load_case(a.case)
    plan = make_plan(case, doc, model=a.model, allowed=a.allowed_returned_model, simulation=False)
    write_new_file(a.out, canonical_bytes(plan.model_dump(mode="json")))
    return emit(
        envelope(
            "planned",
            plan.model_dump(mode="json"),
            limitations=[
                "Not authorized. Separate hosted authorization and credential selection are required."
            ],
        ),
        0,
    )


def execute_command(a):
    from ..cli import emit, envelope

    # Missing gates are refused before credential access or creation of a provider worker.
    if not a.enable_cloud or not a.authorization or not a.credential_file:
        return emit(
            envelope(
                "blocked",
                error={
                    "code": "hosted_gates_missing",
                    "message": "Explicit cloud selection, authorization and credential file are required.",
                },
            ),
            3,
        )
    result = None
    try:
        case, doc = load_case(a.case)
        plan = HostedPlan.model_validate(load_document(a.plan), strict=True)
        authorization = Authorization.model_validate(load_document(a.authorization), strict=True)
        if plan.simulation:
            raise HostedFailure("simulation_plan_not_live_executable")
        provider = DeepSeekProvider(
            plan,
            authorization,
            cloud_enabled=a.enable_cloud,
            credential_file=a.credential_file,
            ledger=a.ledger,
        )
        store = EvidenceStore(a.store)
        try:
            result = run_episode(case, doc, provider, store, evaluator_version=plan.evaluator)
            evaluation = evaluate_and_record(store, result.run_id, case)
            export_bundle(store, result.run_id, doc, evaluation, a.bundle)
        finally:
            store.close()
        return emit(envelope("completed", {"run_id": result.run_id, "evaluation": evaluation}), 0)
    except Exception as error:
        # Never echo input paths, remote text, validation values, or exception text.
        return emit(
            envelope(
                "blocked",
                result={"retained_run_id": result.run_id} if result is not None else None,
                error={
                    "code": error.code
                    if isinstance(error, HostedFailure)
                    else "hosted_input_or_execution_error",
                    "message": "Hosted operation refused or failed; inspect retained local evidence.",
                },
            ),
            3,
        )


def export_command(a):
    """Recovery from an already bound evaluation; no provider, evaluation or replay call."""
    from ..cli import emit, envelope

    _, doc = load_case(a.case)
    store = EvidenceStore.open_readonly(a.store)
    try:
        manifest, _ = store.manifest(a.run_id)
        if sha256_obj(doc) != manifest["source"]["case_source_sha256"]:
            raise HostedFailure("export_case_mismatch")
        bindings = [e for e in store.events(a.run_id) if e["event_type"] == "evaluation_recorded"]
        if not bindings:
            raise HostedFailure("recorded_evaluation_absent")
        evaluation = strict_json_loads(store.artifact(bindings[-1]["payload"]["evaluation_sha256"]))
        export_bundle(store, a.run_id, doc, evaluation, a.bundle)
    finally:
        store.close()
    return emit(envelope("exported", {"run_id": a.run_id, "new_provider_requests": 0}), 0)


def register(subparsers):
    hosted = subparsers.add_parser("hosted", help="Explicit optional hosted engineering commands")
    commands = hosted.add_subparsers(dest="sub", required=True)
    plan = commands.add_parser("plan", help="Plan only; no credential or network access")
    plan.add_argument("--case", type=Path, required=True)
    plan.add_argument("--model", required=True)
    plan.add_argument("--allowed-returned-model", action="append", required=True)
    plan.add_argument("--out", type=Path, required=True)
    plan.set_defaults(fn=plan_command)
    execute = commands.add_parser("execute")
    for name in ("case", "plan", "store", "bundle", "ledger"):
        execute.add_argument("--" + name, type=Path, required=True)
    for name in ("authorization", "credential-file"):
        execute.add_argument("--" + name, type=Path)
    execute.add_argument("--enable-cloud", action="store_true")
    execute.set_defaults(fn=execute_command)
    export = commands.add_parser("export", help="Export retained execution, without provider access")
    for name in ("case", "store", "bundle"):
        export.add_argument("--" + name, type=Path, required=True)
    export.add_argument("--run-id", required=True)
    export.set_defaults(fn=export_command)
