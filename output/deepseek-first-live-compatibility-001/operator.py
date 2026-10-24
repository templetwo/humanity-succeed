"""Operator orchestration for the explicitly approved single checkpoint; never retry."""

import json
import os
import signal
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from humanity_succeed.canonical import (
    canonical_bytes,
    load_document,
    sha256_bytes,
    sha256_obj,
    write_new_file,
)
from humanity_succeed.evidence.bundle import anchor_for, verify_bundle
from humanity_succeed.evidence.replay import replay_bundle
from humanity_succeed.hosted.contracts import Authorization
from humanity_succeed.hosted.provider import implementation_identity

ROOT = Path("/Users/vaquez/Desktop/🔬 Active_Research/humanity-succeed-deepseek-offline")
PACKET = ROOT / "docs/receipts/deepseek-live-compatibility-preparation"
DECISION = "411bbeea00a61aba55b671b476b21f2bc0bbb625c23c4c591e805433aac0be3d"


def forbidden(*args, **kwargs):
    raise RuntimeError("Offline evidence processing cannot contact a provider")


def main():
    decision = load_document(PACKET / "LIVE_PROPOSAL.v2.json")
    assert sha256_obj(decision) == DECISION
    assert implementation_identity() == decision["source"]
    locations = decision["locations"]
    output = Path(locations["output_root"])
    ledger = Path(locations["ledger_root"])
    authorization_path = Path(locations["future_authorization_file"])
    assert not output.exists() and not ledger.exists() and not authorization_path.exists()
    issued = int(time.time())
    authorization = Authorization(
        schema_id="hs-hosted-authorization/1",
        authorization_id="deepseek-first-live-compatibility-001",
        plan_sha256=decision["hosted_plan_sha256"],
        ledger_root=str(ledger), issued_at=issued, expires_at=issued + 300,
        allow_cloud=True, simulation=False, approver="Anthony; explicit chat approval",
    )
    authorization_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_new_file(authorization_path, canonical_bytes(authorization.model_dump(mode="json")))
    authorization_path.chmod(0o600)
    # Separate process: the preflight's network/credential denial cannot affect live execution.
    preflight_command = [str(ROOT / ".venv/bin/python"), str(PACKET / "PREFLIGHT.py"),
                         "--decision-sha256", DECISION, "--authorization", str(authorization_path)]
    preflight = subprocess.run(preflight_command, cwd=ROOT, capture_output=True, timeout=30)
    assert preflight.returncode == 0, "Preflight refused; no credential access or execution"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    write_new_file(Path(locations["preflight_report"]), preflight.stdout)
    approval = {
        "schema_id": "hs-explicit-live-decision-record/1", "decision_plan_sha256": DECISION,
        "hosted_plan_sha256": decision["hosted_plan_sha256"],
        "prompt_scope": "One disposable lantern episode, deepseek-flash, thinking enabled/high, "
                        "at most four inference requests, max_tokens=4096 each, no retries; "
                        "published cost/deadline/capture limitations explicitly disclosed.",
        "user_answer_verbatim": "- Approve this exact plan and scope; run it once",
        "approver": "Anthony", "recorded_at": datetime.now(UTC).isoformat(),
        "scope_document": str(PACKET / "LIVE_PROPOSAL.v2.json"),
        "operator_script_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "authorization_sha256": sha256_obj(authorization.model_dump(mode="json")),
        "not_a_human_semantic_rating": True,
    }
    write_new_file(output / "APPROVAL.json", canonical_bytes(approval))
    write_new_file(output / "HOSTED_PLAN.json", canonical_bytes(decision["hosted_plan"]))
    write_new_file(output / "DECISION_PLAN.json", canonical_bytes(decision))
    command = [str(ROOT / ".venv/bin/hs"), "hosted", "execute",
               "--case", str(ROOT / decision["case"]),
               "--plan", str(PACKET / "HOSTED_PLAN.json"),
               "--store", locations["store"], "--bundle", locations["bundle"],
               "--ledger", str(ledger), "--authorization", str(authorization_path),
               "--credential-file", decision["credential"]["path"], "--enable-cloud"]
    write_new_file(output / "COMMAND.json", canonical_bytes(command))
    started = time.monotonic()
    start_utc = datetime.now(UTC).isoformat()
    with (output / "execute.stdout.json").open("xb") as stdout, \
         (output / "execute.stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True)
        timed_out = False
        try:
            exit_code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            exit_code = process.wait(timeout=10)
    report = {
        "schema_id": "hs-live-compatibility-attempt/1", "decision_plan_sha256": DECISION,
        "hosted_plan_sha256": decision["hosted_plan_sha256"],
        "started_at": start_utc, "source": implementation_identity(),
        "operator_script_sha256": approval["operator_script_sha256"],
        "execute_exit_code": exit_code, "operator_timeout": timed_out,
        "operator_seconds_after_execution": round(time.monotonic() - started, 3),
        "metadata_requests_during_checkpoint": 0, "retries": 0,
        "new_api_calls_for_evidence_processing": 0,
        "no_weight_or_tokenizer_identity_claim": True,
    }
    ledger_file = ledger / (authorization.authorization_id + ".jsonl")
    reservations = []
    if ledger_file.exists():
        reservations = [json.loads(line) for line in ledger_file.read_text().splitlines()
                        if '"attempt"' in line]
    report["reserved_inference_attempts"] = len(reservations)
    assert len(reservations) <= 4
    bundle = Path(locations["bundle"])
    if exit_code != 0 or timed_out or not bundle.exists():
        report["status"] = "execution_or_export_failed_preserved_no_retry"
        write_new_file(Path(locations["attempt_report"]), canonical_bytes(report))
        print(canonical_bytes(report).decode())
        return
    manifest = load_document(bundle / "manifest.json")
    evaluation = load_document(bundle / "evaluation.json")
    events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
    report["run_id"] = events[0]["run_id"]
    report["evidence_class"] = manifest["evidence_class"]
    report["simulation"] = manifest["provider"]["hosted"]["plan"]["simulation"]
    report["terminal_status"] = next(e["payload"]["terminal_status"] for e in events
                                     if e["event_type"] == "run_completed")
    report["mechanical"] = evaluation["mechanical"]
    report["conduct_outcome"] = evaluation["conduct_outcome"]
    report["model_abstained"] = evaluation["model_abstained"]
    report["guard_withheld"] = evaluation["guard_withheld"]
    report["responses"] = [e["payload"]["hosted"] for e in events
                           if e["event_type"] == "provider_response"]
    report["failures"] = [e["payload"] for e in events if e["event_type"] == "provider_error"]
    proposals = {e["sequence"]: e["payload"]["action"] for e in events
                 if e["event_type"] == "action_proposed"}
    report["proposed_actions"] = list(proposals.values())
    report["executed_actions"] = [
        {"action": proposals[e["payload"]["proposal_seq"]], "execution": e["payload"]}
        for e in events if e["event_type"] == "action_executed"
    ]
    report["manifest_sha256"] = sha256_obj(manifest)
    report["evaluation_sha256"] = sha256_obj(evaluation)
    report["events_sha256"] = sha256_bytes((bundle / "events.jsonl").read_bytes())
    report["evaluator_version"] = evaluation["evaluator_version"]
    assert manifest["evidence_class"] == "model_observation" and report["simulation"] is False
    assert manifest["versions"]["evaluator"] == evaluation["evaluator_version"] == "hs-evaluator/0.3.0"
    # From here, make network/provider dispatch fail visibly; verification/replay are recorded only.
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    import humanity_succeed.hosted.provider as provider_module
    import humanity_succeed.hosted.transport as transport_module
    provider_module.dispatch = forbidden
    transport_module.dispatch = forbidden
    transport_module._https = forbidden
    try:
        anchor = anchor_for(bundle)
        write_new_file(Path(locations["anchor"]), canonical_bytes(anchor))
        verification = verify_bundle(bundle, anchor, require=("bound_evaluation",))
        write_new_file(Path(locations["verification"]), canonical_bytes(verification))
        assert verification["internal"] == "consistent"
        assert verification["anchor"] == "verified_against_anchor"
        assert verification["requirements"]["bound_evaluation"]["met"]
        remaining = 180 - (time.monotonic() - started)
        assert remaining > 0, "Operator full-pipeline deadline exhausted"
        def stop(*_):
            raise TimeoutError("Operator replay deadline")
        signal.signal(signal.SIGALRM, stop)
        signal.setitimer(signal.ITIMER_REAL, remaining)
        replay = replay_bundle(bundle, Path(locations["replay"]))
        signal.setitimer(signal.ITIMER_REAL, 0)
        assert replay["replay"]["status"] == "reproduced"
        assert replay["api_calls"] == 0
        assert replay["replay"]["evaluator_version_used"] == "hs-evaluator/0.3.0"
        report["verification"] = "consistent_and_retained_anchor_verified"
        report["replay"] = "faithfully_reproduced"
        report["status"] = "recorded_verified_replayed"
    except Exception:
        signal.setitimer(signal.ITIMER_REAL, 0)
        report["status"] = "offline_evidence_step_failed_preserved_no_retry"
    report["whole_pipeline_elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["finished_at"] = datetime.now(UTC).isoformat()
    write_new_file(Path(locations["attempt_report"]), canonical_bytes(report))
    print(canonical_bytes({key: report.get(key) for key in (
        "status", "run_id", "terminal_status", "reserved_inference_attempts", "conduct_outcome",
        "verification", "replay", "whole_pipeline_elapsed_seconds",
        "metadata_requests_during_checkpoint", "new_api_calls_for_evidence_processing",
    )}).decode())


if __name__ == "__main__":
    main()
