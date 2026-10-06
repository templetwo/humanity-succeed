"""Fake-only engineering evidence. No selectable live transport and no B59 fixtures."""

from __future__ import annotations

import argparse
import socket
import time
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, make_new_dir, sha256_bytes, sha256_obj, write_new_file
from humanity_succeed.evidence.bundle import anchor_for, export_bundle, verify_bundle
from humanity_succeed.evidence.replay import replay_bundle
from humanity_succeed.evidence.store import EvidenceStore
from humanity_succeed.hosted.contracts import Authorization
from humanity_succeed.hosted.provider import DeepSeekProvider, make_plan
from humanity_succeed.hosted.transport import FakeReply
from humanity_succeed.runner.episode import run_episode
from humanity_succeed.runner.scripted import evaluate_and_record, load_case

REPO = Path(__file__).resolve().parents[1]


def body(raw: str, finish: str = "stop") -> FakeReply:
    return FakeReply(
        body=canonical_bytes(
            {
                "id": "fake-engineering-response",
                "model": "simulation-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": raw,
                            "reasoning_content": "Simulated reasoning only.",
                        },
                        "finish_reason": finish,
                    }
                ],
                "usage": {"prompt_tokens": 13, "completion_tokens": 20, "total_tokens": 33},
            }
        )
    )


def action(value: dict) -> FakeReply:
    return body(canonical_bytes({"action": value}).decode())


def run(out: Path, state: Path) -> dict:
    def deny(*args, **kwargs):
        raise RuntimeError("unmocked network denied")

    socket.socket.connect = deny  # type: ignore[method-assign]
    socket.create_connection = deny
    make_new_dir(out)
    make_new_dir(state)
    (out / "anchors").mkdir()
    (out / "verification").mkdir()
    case, doc = load_case(REPO / "engineering/deepseek_offline/case.json")
    # Fresh dummy credential only; this command has no real credential argument/discovery path.
    secret = "dummy_acceptance_only_43109"
    key = state / "dummy-credential.txt"
    key.write_text("DEEPSEEK_API_KEY=" + secret + "\n")
    key.chmod(0o600)
    scenarios = {
        "copy": [
            action({"type": "read_resource", "resource_id": "r_source"}),
            action(
                {
                    "type": "write_resource",
                    "resource_id": "r_result",
                    "expected_revision": 1,
                    "value": {"tag": "CAL-7"},
                }
            ),
            action(
                {
                    "type": "finish",
                    "summary": "Synthetic calibration tag copied.",
                    "delivered_resource_ids": ["r_result"],
                }
            ),
        ],
        "denial_then_decline": [
            action(
                {
                    "type": "write_resource",
                    "resource_id": "r_source",
                    "expected_revision": 1,
                    "value": {"tag": "changed"},
                }
            ),
            action({"type": "decline", "reason": "Scripted engineering control decline."}),
        ],
        "empty": [body("")],
        "malformed_action": [body("I decline.")],
        "truncated": [body('{"action":', "length")],
        "authentication": [FakeReply(status=401, body=secret.encode())],
        "rate_limit": [FakeReply(status=429)],
        "timeout": [FakeReply(error="timeout")],
        "server_error": [FakeReply(status=500)],
        "malformed_api": [FakeReply(body=b"{bad")],
        "credential_echo": [body(secret)],
    }
    rows = []
    for name, replies in scenarios.items():
        plan = make_plan(case, doc, model="simulation-model", allowed=["simulation-model"], simulation=True)
        authorization = Authorization(
            schema_id="hs-hosted-authorization/1",
            authorization_id="offline-" + name,
            ledger_root=str((state / "ledger").resolve()),
            plan_sha256=sha256_obj(plan.model_dump(mode="json")),
            issued_at=int(time.time()) - 1,
            expires_at=int(time.time()) + 600,
            allow_cloud=True,
            simulation=True,
            approver="programmatic engineering simulation; no human live approval",
        )
        provider = DeepSeekProvider(
            plan,
            authorization,
            cloud_enabled=True,
            credential_file=key,
            ledger=state / "ledger",
            fake_replies=replies,
        )
        store = EvidenceStore(state / (name + ".sqlite"))
        try:
            result = run_episode(
                case, doc, provider, store, run_id="fake_" + name, evaluator_version="hs-evaluator/0.3.0"
            )
            evaluation = evaluate_and_record(store, result.run_id, case)
            recovery = None
            if name == "copy":
                blocked = out / "export-failure-target"
                blocked.mkdir()
                try:
                    export_bundle(store, result.run_id, doc, evaluation, blocked)
                except FileExistsError:
                    recovery = {"failure": "output already exists", "attempts_before": provider.attempts}
                blocked.rmdir()
            before = provider.attempts
            bundle = export_bundle(store, result.run_id, doc, evaluation, out / "bundles" / name)
            anchor = anchor_for(bundle)
            verification = verify_bundle(bundle, anchor, require=("bound_evaluation",))
            replay = replay_bundle(bundle, out / "replays" / name)
            assert provider.attempts == before
            assert verification["internal"] == "consistent"
            assert verification["anchor"] == "verified_against_anchor"
            assert replay["replay"]["status"] == "reproduced"
            write_new_file(out / "anchors" / (name + ".json"), canonical_bytes(anchor))
            write_new_file(out / "verification" / (name + ".json"), canonical_bytes(verification))
            if recovery:
                recovery.update(attempts_after=provider.attempts, new_requests=0)
            events = store.events(result.run_id)
            rows.append(
                {
                    "scenario": name,
                    "run_id": result.run_id,
                    "terminal": result.terminal_status,
                    "mechanical": evaluation["mechanical"]["verdict"],
                    "conduct": evaluation["conduct_outcome"],
                    "simulation": True,
                    "evidence_class": evaluation["evidence_class"],
                    "evaluator": evaluation["evaluator_version"],
                    "attempts": provider.attempts,
                    "request_budget": plan.limits.requests,
                    "reserved_output_tokens_per_attempt": 4096,
                    "requests": [
                        e["payload"]["hosted"] for e in events if e["event_type"] == "provider_requested"
                    ],
                    "responses": [
                        e["payload"]["hosted"] for e in events if e["event_type"] == "provider_response"
                    ],
                    "errors": [e["payload"] for e in events if e["event_type"] == "provider_error"],
                    "manifest_sha256": result.manifest_sha256,
                    "evaluation_sha256": sha256_obj(evaluation),
                    "events_sha256": sha256_bytes((bundle / "events.jsonl").read_bytes()),
                    "verification": "consistent, retained anchor matches",
                    "replay": "reproduced",
                    "export_recovery": recovery,
                }
            )
        finally:
            store.close()
    report = {
        "schema_id": "hs-deepseek-offline-acceptance/1",
        "simulation": True,
        "authenticated_network_requests": 0,
        "model_inferences": 0,
        "training_runs": 0,
        "case_sha256": sha256_obj(doc),
        "rows": rows,
        "note": "Shared authored engineering fixture; not independent model observations.",
    }
    write_new_file(out / "report.json", canonical_bytes(report))
    assert all(secret.encode() not in p.read_bytes() for p in out.rglob("*") if p.is_file())
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.out, args.state)
    print(
        f"{len(report['rows'])} fake runs verified and faithfully replayed; no authenticated network requests"
    )
