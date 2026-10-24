"""One supervised approved pilot, existing CLI only; never retry or modify frozen material."""

import importlib.util
import json
import os
import signal
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, load_document, sha256_bytes, sha256_obj
from humanity_succeed.evidence.bundle import anchor_for, verify_bundle
from humanity_succeed.evidence.replay import replay_bundle
from humanity_succeed.hosted.contracts import Authorization, HostedPlan
from humanity_succeed.hosted.provider import implementation_identity

ROOT = Path("/Users/vaquez/Desktop/🔬 Active_Research/humanity-succeed-deepseek-offline")
PACKET = ROOT / "docs/receipts/deepseek-evidence-response-pilot-001"
OUT = ROOT / "output/deepseek-evidence-response-pilot-001"
PLAN_HASH = "fb2f9f8c11dbf09353f5c68443367fe54eeac8ad02f4f3283f2911467c069c4d"
APPROVAL_TEXT = """I approve one supervised execution of the frozen DeepSeek
evidence-response pilot in PILOT_PLAN.v2.json with plan hash:

fb2f9f8c11dbf09353f5c68443367fe54eeac8ad02f4f3283f2911467c069c4d

Before credential access or inference, verify the plan hash,
bound code/task identities, and all required preconditions.
Do not fill unresolved fields or change the frozen plan.

Scope:
- Four related episodes.
- At most two inference requests per episode and eight total.
- Zero metadata requests, retries, model substitutions,
  or automatic continuation.
- At most 4,096 generated tokens per request and 32,768 total.
- Respect the frozen 45-second request and 90-second episode limits.
- Run only while I am available to supervise the manual
  360-second whole-pilot ceiling.
- Use only the model, settings, credential location, input limits,
  and synthetic outbound information specified in the plan.

Preserve every attempt and outcome. If a stopping condition,
identity mismatch, or unresolved prerequisite occurs, stop and
report it; do not repair and restart under this approval.

Export, verify, and replay the recorded evidence without
additional API calls. Leave semantic judgments blank for actual
human review. Preserve B59 and all earlier evidence unchanged.

This approves only this exploratory execution—not training,
formal commissioning, publication, push, merge, Stack writes,
or another experiment."""


def write_new(path, obj):
    with path.open("xb") as stream:
        stream.write(canonical_bytes(obj))


def denied(*args, **kwargs):
    raise RuntimeError("Evidence processing cannot contact a provider or read credentials")


def preflight(fresh):
    spec = importlib.util.spec_from_file_location("approved_pilot_preflight", PACKET / "PREFLIGHT_v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Guard only this operator process. Live execution is a fresh CLI subprocess.
    module.deny_external_access()
    result = module.check(PLAN_HASH, fresh_locations=fresh)
    for line in (PACKET / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert sha256_bytes((PACKET / name).read_bytes()) == digest, "sealed preparation changed"
    return result


def main():
    initial = preflight(True)
    plan = load_document(PACKET / "PILOT_PLAN.v2.json")
    assert sha256_obj(plan) == PLAN_HASH and implementation_identity() == plan["source"]
    assert not OUT.exists(), "pilot output already exists; do not repeat"
    OUT.mkdir(mode=0o700)
    approval = {
        "schema_id": "hs-explicit-pilot-execution-decision/1",
        "plan_sha256": PLAN_HASH,
        "approver": "Anthony",
        "approval_verbatim": APPROVAL_TEXT,
        "supervision_confirmation_verbatim": "Available now",
        "supervision_question": "Are you available now to supervise the pilot's manual 360-second ceiling?",
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "operator_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "plan_and_unresolved_fields_not_modified": True,
        "semantic_judgment": None,
        "not_a_human_semantic_rating": True,
        "authorization_records": (
            "Separate existing contract records derived only from this actual approval; "
            "frozen plan fields remain null."
        ),
    }
    write_new(OUT / "APPROVAL.json", approval)
    write_new(OUT / "INITIAL_PREFLIGHT.json", initial)
    write_new(OUT / "FROZEN_PLAN.json", plan)
    (OUT / "operator.py").write_bytes(Path(__file__).read_bytes())
    report = {
        "schema_id": "hs-live-evidence-response-pilot-attempts/1",
        "plan_sha256": PLAN_HASH,
        "source": implementation_identity(),
        "operator_sha256": approval["operator_sha256"],
        "episodes": [
            {
                "episode_id": e["episode_id"],
                "evidence_status": e["evidence_status"],
                "status": "not_started",
                "reason": None,
            }
            for e in plan["episodes"]
        ],
        "metadata_requests": 0,
        "retries": 0,
        "new_api_calls_for_evidence": 0,
        "human_reviews_recorded": 0,
        "status": "in_progress",
        "stop_reason": None,
    }
    # Start before the first permitted credential read; the CLI reads the designated file.
    started = time.monotonic()
    report["started_at_utc"] = datetime.now(UTC).isoformat()
    total_attempts = 0
    total_reserved = 0
    current = None
    try:
        for index, row in enumerate(plan["episodes"]):
            current = report["episodes"][index]
            assert time.monotonic() - started < 360, "whole_pilot_time_limit"
            check = preflight(index == 0)
            # Earlier planned locations are now expected to exist; remaining ones must be fresh.
            for future in plan["episodes"][index:]:
                for key in ("output_root", "ledger_root", "authorization_file"):
                    assert not Path(future["locations"][key]).exists(), "single_use_location_not_fresh"
            assert total_attempts + 2 <= 8 and total_reserved + 8192 <= 32768
            hosted = HostedPlan.model_validate(load_document(PACKET / row["hosted_plan"]), strict=True)
            assert sha256_obj(hosted.model_dump(mode="json")) == row["hosted_plan_sha256"]
            assert hosted.simulation is False and hosted.settings.max_tokens == 4096
            locations = row["locations"]
            output = Path(locations["output_root"])
            output.mkdir(mode=0o700)
            write_new(output / "PREFLIGHT.json", check)
            issued = int(time.time())
            auth = Authorization(
                schema_id="hs-hosted-authorization/1",
                authorization_id=row["episode_id"],
                plan_sha256=row["hosted_plan_sha256"],
                ledger_root=locations["ledger_root"],
                issued_at=issued,
                expires_at=issued + 180,
                allow_cloud=True,
                simulation=False,
                approver="Anthony; explicit approval of pilot plan " + PLAN_HASH,
            )
            auth_path = Path(locations["authorization_file"])
            auth_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            write_new(auth_path, auth.model_dump(mode="json"))
            auth_path.chmod(0o600)
            write_new(output / "AUTHORIZATION.json", auth.model_dump(mode="json"))
            current["authorization_sha256"] = sha256_obj(auth.model_dump(mode="json"))
            current["hosted_plan_sha256"] = row["hosted_plan_sha256"]
            current["status"] = "attempt_started"
            command = [
                str(ROOT / ".venv/bin/hs"),
                "hosted",
                "execute",
                "--case",
                str(PACKET / row["case"]),
                "--plan",
                str(PACKET / row["hosted_plan"]),
                "--store",
                locations["store"],
                "--bundle",
                locations["bundle"],
                "--ledger",
                locations["ledger_root"],
                "--authorization",
                str(auth_path),
                "--credential-file",
                plan["credential"]["proposed_path"],
                "--enable-cloud",
            ]
            write_new(output / "COMMAND.json", command)
            episode_start = time.monotonic()
            with (
                (output / "execute.stdout.json").open("xb") as stdout,
                (output / "execute.stderr.log").open("xb") as stderr,
            ):
                process = subprocess.Popen(
                    command, cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True
                )
                timeout = min(90, 360 - (time.monotonic() - started))
                timed_out = False
                try:
                    exit_code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        exit_code = process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        exit_code = process.wait(timeout=5)
            current["cli_exit_code"] = exit_code
            current["operator_timeout"] = timed_out
            current["execution_seconds"] = round(time.monotonic() - episode_start, 3)
            ledger_file = Path(locations["ledger_root"]) / (auth.authorization_id + ".jsonl")
            reservations = []
            if ledger_file.exists():
                reservations = [
                    json.loads(line) for line in ledger_file.read_text().splitlines() if '"attempt"' in line
                ]
            attempts = len(reservations)
            reserved = sum(r["reserved_output_tokens"] for r in reservations)
            total_attempts += attempts
            total_reserved += reserved
            current["reserved_requests"] = attempts
            current["reserved_output_tokens"] = reserved
            write_new(output / "REQUEST_RESERVATIONS.json", reservations)
            assert attempts <= 2 and reserved <= 8192 and total_attempts <= 8 and total_reserved <= 32768
            assert exit_code == 0 and not timed_out, "execution_or_export_failed"
            bundle = Path(locations["bundle"])
            manifest = load_document(bundle / "manifest.json")
            evaluation = load_document(bundle / "evaluation.json")
            events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
            current.update(
                run_id=events[0]["run_id"],
                evidence_class=manifest["evidence_class"],
                evaluator=evaluation["evaluator_version"],
                mechanical=evaluation["mechanical"],
                conduct_outcome=evaluation["conduct_outcome"],
                semantic_review=evaluation["semantic_review"],
                guard_withheld=evaluation["guard_withheld"],
                model_abstained=evaluation["model_abstained"],
                terminal_status=next(
                    e["payload"]["terminal_status"] for e in events if e["event_type"] == "run_completed"
                ),
                responses=[e["payload"]["hosted"] for e in events if e["event_type"] == "provider_response"],
                provider_errors=[e["payload"] for e in events if e["event_type"] == "provider_error"],
                manifest_sha256=sha256_obj(manifest),
                evaluation_sha256=sha256_obj(evaluation),
                events_sha256=sha256_bytes((bundle / "events.jsonl").read_bytes()),
            )
            proposals = {
                e["sequence"]: e["payload"]["action"] for e in events if e["event_type"] == "action_proposed"
            }
            current["executed_actions"] = [
                {
                    "action": proposals[e["payload"]["proposal_seq"]],
                    "execution": e["payload"],
                    "event_sequence": e["sequence"],
                }
                for e in events
                if e["event_type"] == "action_executed"
            ]
            assert manifest["evidence_class"] == "model_observation"
            assert manifest["provider"]["hosted"]["plan"] == hosted.model_dump(mode="json")
            assert manifest["code"]["commit"] == plan["source"]["source_commit"]
            assert manifest["code"]["dirty"] is False
            assert manifest["versions"]["evaluator"] == evaluation["evaluator_version"] == hosted.evaluator
            assert evaluation["semantic_review"]["reviews_received"] == 0
            # Evidence handling is offline; all actual responses were already recorded by the CLI.
            socket.socket.connect = denied
            socket.create_connection = denied
            import humanity_succeed.hosted.provider as provider
            import humanity_succeed.hosted.transport as transport

            provider.dispatch = transport.dispatch = transport._https = denied
            anchor = anchor_for(bundle)
            write_new(Path(locations["anchor"]), anchor)
            verification = verify_bundle(bundle, anchor, require=("bound_evaluation",))
            write_new(Path(locations["verification"]), verification)
            assert verification["internal"] == "consistent"
            assert verification["anchor"] == "verified_against_anchor"
            assert verification["requirements"]["bound_evaluation"]["met"]
            remaining = 360 - (time.monotonic() - started)
            assert remaining > 0, "whole_pilot_time_limit"

            def stop(*_):
                raise TimeoutError("whole_pilot_time_limit")

            signal.signal(signal.SIGALRM, stop)
            signal.setitimer(signal.ITIMER_REAL, remaining)
            replay = replay_bundle(bundle, Path(locations["replay"]))
            signal.setitimer(signal.ITIMER_REAL, 0)
            assert replay["replay"]["status"] == "reproduced" and replay["replay"]["evaluation_reproduced"]
            assert replay["api_calls"] == 0 and replay["replay"]["evaluator_version_used"] == hosted.evaluator
            current["verification"] = "consistent_anchor_verified_bound_evaluation"
            current["replay"] = "reproduced_zero_api_calls"
            current["status"] = "recorded_verified_replayed"
            write_new(output / "ATTEMPT_REPORT.json", current)
            # Preserve behavioral failures; stop for the frozen infrastructure/enactment conditions.
            assert current["terminal_status"] in ("finished", "declined"), "terminal_stopping_condition"
            assert not current["provider_errors"], "provider_stopping_condition"
            assert all(r["finish_reason"] == "stop" for r in current["responses"]), "api_termination"
            assert time.monotonic() - started < 360, "whole_pilot_time_limit"
            print(
                canonical_bytes(
                    {
                        "episode": row["evidence_status"],
                        "run_id": current["run_id"],
                        "status": current["status"],
                        "requests": attempts,
                        "mechanical": evaluation["mechanical"]["verdict"],
                        "conduct": evaluation["conduct_outcome"],
                    }
                ).decode(),
                flush=True,
            )
        report["status"] = "four_episodes_recorded_verified_replayed"
    except Exception as error:
        signal.setitimer(signal.ITIMER_REAL, 0)
        report["status"] = "stopped_no_repair_no_retry"
        # This operator never reads a secret or stores remote exception text. Local assertion code only.
        report["stop_reason"] = (
            str(error) if isinstance(error, (AssertionError, TimeoutError)) else type(error).__name__
        )
        if current is not None:
            current["reason"] = report["stop_reason"]
        for episode in report["episodes"]:
            if episode["status"] == "not_started":
                episode["reason"] = "earlier_stop; not executed under this approval"
    report.update(
        reserved_requests_total=total_attempts,
        reserved_output_tokens_total=total_reserved,
        whole_pipeline_seconds=round(time.monotonic() - started, 3),
        finished_at_utc=datetime.now(UTC).isoformat(),
    )
    write_new(OUT / "ATTEMPT_REPORT.json", report)
    final_check = preflight(False)
    write_new(OUT / "PRESERVATION.json", final_check)
    print(
        canonical_bytes(
            {
                "status": report["status"],
                "stop_reason": report["stop_reason"],
                "requests": total_attempts,
                "seconds": report["whole_pipeline_seconds"],
                "historical_entries_unchanged": final_check["preserved_entries"],
            }
        ).decode(),
        flush=True,
    )


if __name__ == "__main__":
    main()
