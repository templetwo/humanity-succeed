"""New disposable engineering fixtures. Every provider response is simulated, network denied."""

from __future__ import annotations

import json
import socket
import time
from pathlib import Path

import pytest

from humanity_succeed.canonical import canonical_bytes, load_document, sha256_obj
from humanity_succeed.contracts.case import CaseSource
from humanity_succeed.corpus.lint import lint_case
from humanity_succeed.corpus.views import VisibleTurn, build_provider_input, subject_view
from humanity_succeed.evidence.bundle import anchor_for, export_bundle, verify_bundle
from humanity_succeed.evidence.replay import replay_bundle
from humanity_succeed.evidence.store import EvidenceStore
from humanity_succeed.hosted.contracts import Authorization, HostedPlan, Settings
from humanity_succeed.hosted.provider import DeepSeekProvider, make_plan, read_credential
from humanity_succeed.hosted.transport import FakeReply, HostedFailure, decode, encode
from humanity_succeed.runner.episode import run_episode
from humanity_succeed.runner.scripted import evaluate_and_record, load_case

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "examples/deepseek_offline/case.json"
SECRET = "dummy_offline_secret_93281"
ACTIONS = [
    {"action": {"type": "read_resource", "resource_id": "r_source"}},
    {
        "action": {
            "type": "write_resource",
            "resource_id": "r_result",
            "expected_revision": 1,
            "value": {"tag": "CAL-7"},
        }
    },
    {
        "action": {
            "type": "finish",
            "summary": "Synthetic tag copied.",
            "delivered_resource_ids": ["r_result"],
        }
    },
]


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("unmocked network attempt")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def reply(raw, finish="stop", **extra):
    return FakeReply(
        body=canonical_bytes(
            {
                "id": "fake-response",
                "model": "simulation-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": raw,
                            "reasoning_content": "Simulated reasoning, separate from the action.",
                        },
                        "finish_reason": finish,
                    }
                ],
                "usage": {"prompt_tokens": 13, "completion_tokens": 20, "total_tokens": 33},
                **extra,
            }
        )
    )


def provider(tmp, doc, replies, **options):
    case = CaseSource.model_validate(doc, strict=True)
    plan = make_plan(
        case, doc, model="simulation-model", allowed=["simulation-model"], simulation=True, **options
    )
    auth = Authorization(
        schema_id="hs-hosted-authorization/1",
        authorization_id="fake-approval",
        ledger_root=str((tmp / "ledger").resolve()),
        plan_sha256=sha256_obj(plan.model_dump(mode="json")),
        issued_at=int(time.time()) - 1,
        expires_at=int(time.time()) + 600,
        allow_cloud=True,
        simulation=True,
        approver="engineering simulation; no human live approval",
    )
    credential = tmp / "dummy-credential.txt"
    credential.write_text("DEEPSEEK_API_KEY=" + SECRET + "\n")
    credential.chmod(0o600)
    return DeepSeekProvider(
        plan,
        auth,
        cloud_enabled=True,
        credential_file=credential,
        ledger=tmp / "ledger",
        fake_replies=replies,
    )


def execute(tmp, replies, **options):
    case, doc = load_case(CASE)
    p = provider(tmp, doc, replies, **options)
    store = EvidenceStore(tmp / "store.sqlite")
    result = run_episode(
        case, doc, p, store, run_id="engineering_fake", evaluator_version="hs-evaluator/0.3.0"
    )
    evaluation = evaluate_and_record(store, result.run_id, case)
    return p, store, result, evaluation, doc


def test_end_to_end_and_recovery(tmp_path, monkeypatch):
    p, store, result, ev, doc = execute(tmp_path, [reply(canonical_bytes(a).decode()) for a in ACTIONS])
    assert ev["mechanical"]["verdict"] == "pass"
    assert ev["schema_id"] == "hs-evaluation/2"
    assert ev["evidence_class"] == "scripted_instrument"
    assert ev["hosted"]["plan"]["simulation"] is True
    assert ev["evaluator_version"] == "hs-evaluator/0.3.0"
    assert p.attempts == 3
    # Export failure followed by recovery uses the retained store, never another generate call.
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    with pytest.raises((ValueError, FileExistsError)):
        export_bundle(store, result.run_id, doc, ev, blocked)
    monkeypatch.setattr(p, "generate", lambda *_: pytest.fail("export invoked provider"))
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    anchor = anchor_for(bundle)
    assert verify_bundle(bundle, anchor)["internal"] == "consistent"
    assert verify_bundle(bundle, anchor)["anchor"] == "verified_against_anchor"
    report = replay_bundle(bundle, tmp_path / "replay")
    assert report["replay"]["status"] == "reproduced", report["replay"]
    assert report["replay"]["evaluation_reproduced"]
    for file in bundle.rglob("*"):
        if file.is_file():
            assert SECRET.encode() not in file.read_bytes()
    for e in store.events(result.run_id):
        if e["event_type"] == "provider_requested":
            data = store.artifact(e["payload"]["hosted"]["request_sha256"])
            assert b"hostonly_canary_8192" not in data
            assert b"violet kettle" not in data
    store.close()


def test_reversible_multi_turn_isolation():
    case, doc = load_case(CASE)
    turns = [
        VisibleTurn(
            raw_output=canonical_bytes(ACTIONS[0]).decode(),
            tool_result={"value": {"tag": "CAL-7"}, "revision": 1},
        )
    ]
    obs = build_provider_input(subject_view(case), 0, turns)
    request = encode(obs, "simulation-model", Settings())
    assert decode(request) == obs
    parsed = json.loads(request)
    assert parsed["messages"][0] == json.loads(obs)["messages"][0]
    assert parsed["messages"][2] == json.loads(obs)["messages"][2]
    assert all(m["role"] != "tool" and "tool_calls" not in m for m in parsed["messages"])
    doc["evaluation"]["a1_evidence"]["findings"][0]["evidence_status"] = "contradicted"
    changed = CaseSource.model_validate(doc, strict=True)
    assert obs == build_provider_input(subject_view(changed), 0, turns)
    doc["subject"]["task"] += " violet kettle canary stays exclusively evaluator side hostonly_canary_8192"
    assert lint_case(CaseSource.model_validate(doc, strict=True))


@pytest.mark.parametrize(
    ("reply_value", "code"),
    [
        (FakeReply(status=401, body=SECRET.encode()), "authentication_error"),
        (FakeReply(status=429), "rate_limited"),
        (FakeReply(status=500), "server_error"),
        (FakeReply(status=503), "server_unavailable"),
        (FakeReply(status=302), "redirect_refused"),
        (FakeReply(error="timeout"), "timeout"),
        (FakeReply(error="tls_error"), "tls_error"),
        (FakeReply(body=b"{malformed"), "api_protocol_error"),
        (reply(SECRET), "credential_echo"),
        (FakeReply(body=b'{"x":"dummy_offline_secret_9328\\u0031"}'), "credential_echo"),
        (reply("{}", model="different-model"), "api_protocol_error"),
    ],
)
def test_failures_distinct_recorded_and_replayed(tmp_path, reply_value, code):
    p, store, result, ev, doc = execute(tmp_path, [reply_value])
    assert result.terminal_status == "provider_failure"
    errors = [e["payload"] for e in store.events(result.run_id) if e["event_type"] == "provider_error"]
    assert errors[0]["code"] == code
    assert errors[0]["hosted"]["attempted"] is True
    assert errors[0]["hosted"]["completion_unknown"] is (code == "timeout")
    assert ev["mechanical"]["verdict"] == "not_evaluable"
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    assert verify_bundle(bundle)["internal"] == "consistent"
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "reproduced"
    assert p.attempts == 1
    assert SECRET.encode() not in canonical_bytes(errors)
    store.close()


@pytest.mark.parametrize("raw", ["", "I decline.", "{}", '{"action":{"type":"invented"}}'])
def test_invalid_content_is_observed_action_failure(tmp_path, raw):
    p, store, result, ev, doc = execute(tmp_path, [reply(raw)])
    assert result.terminal_status == "invalid_action"
    types = [e["event_type"] for e in store.events(result.run_id)]
    assert "provider_response" in types and "action_parse_failed" in types and "provider_error" not in types
    assert not ev["model_abstained"] and not ev["guard_withheld"]
    assert ev["mechanical"]["verdict"] == "fail"
    assert p.attempts == 1
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "reproduced"
    store.close()


@pytest.mark.parametrize("finish", ["length", "content_filter", "aborted", "insufficient_system_resource"])
def test_terminated_api_content_has_no_effect(tmp_path, finish):
    _, store, result, ev, doc = execute(tmp_path, [reply(canonical_bytes(ACTIONS[1]).decode(), finish)])
    assert result.terminal_status == "api_terminated"
    assert not any(e["event_type"] == "action_proposed" for e in store.events(result.run_id))
    assert not ev["model_abstained"]
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "reproduced"
    store.close()


@pytest.mark.parametrize("change", ["expired", "future", "mismatch", "source", "cloud", "transport"])
def test_invalid_gates_before_dispatch_or_credentials(tmp_path, monkeypatch, change):
    case, doc = load_case(CASE)
    plan = make_plan(case, doc, model="simulation-model", allowed=["simulation-model"], simulation=True)
    auth_doc = {
        "authorization_id": "test",
        "ledger_root": str((tmp_path / "ledger").resolve()),
        "plan_sha256": sha256_obj(plan.model_dump(mode="json")),
        "issued_at": int(time.time()) - 1,
        "expires_at": int(time.time()) + 600,
        "allow_cloud": True,
        "simulation": True,
        "approver": "simulation",
    }
    if change == "expired":
        auth_doc.update(issued_at=1, expires_at=2)
    if change == "future":
        auth_doc.update(issued_at=int(time.time()) + 100, expires_at=int(time.time()) + 200)
    if change == "mismatch":
        auth_doc["plan_sha256"] = "0" * 64
    if change == "source":
        plan = plan.model_copy(update={"implementation_sha256": "0" * 64})
        auth_doc["plan_sha256"] = sha256_obj(plan.model_dump(mode="json"))

    def forbidden(*_):
        pytest.fail("invalid gate read credential")

    monkeypatch.setattr("humanity_succeed.hosted.provider.read_credential", forbidden)
    with pytest.raises((ValueError, HostedFailure)):
        DeepSeekProvider(
            plan,
            Authorization(schema_id="hs-hosted-authorization/1", **auth_doc),
            cloud_enabled=change != "cloud",
            credential_file=tmp_path / "no-key",
            ledger=tmp_path / "ledger",
            fake_replies=None if change == "transport" else [],
        )


def test_single_use_and_request_budget(tmp_path):
    _, doc = load_case(CASE)
    p = provider(tmp_path, doc, [reply(canonical_bytes(ACTIONS[0]).decode())], limits={"requests": 1})
    case = CaseSource.model_validate(doc, strict=True)
    obs = build_provider_input(subject_view(case), 0, [])
    p.validate_case(doc, subject_view(case).model_dump(mode="json"), "hs-evaluator/0.3.0")
    p.prepare(obs)
    p.generate(obs)
    with pytest.raises(HostedFailure, match="budget"):
        p.prepare(obs)
    second = provider(tmp_path, doc, [], limits={"requests": 1})
    with pytest.raises(HostedFailure, match="already_claimed"):
        second.validate_case(doc, subject_view(case).model_dump(mode="json"), "hs-evaluator/0.3.0")
    assert p.attempts == 1 and second.attempts == 0


@pytest.mark.parametrize(
    "content",
    [
        "export DEEPSEEK_API_KEY=x",
        "DEEPSEEK_API_KEY=$(echo x)",
        "DEEPSEEK_API_KEY=validdummy\nDEEPSEEK_API_KEY=second",
        "x" * 65537,
    ],
)
def test_literal_dummy_credential_only(tmp_path, content):
    path = tmp_path / "dummy"
    path.write_text(content)
    with pytest.raises(HostedFailure, match="credential_file_invalid"):
        read_credential(path)


def test_strict_plans_no_custom_endpoint_or_unknown_fields():
    case, doc = load_case(CASE)
    plan = make_plan(case, doc, model="simulation-model", allowed=["simulation-model"], simulation=True)
    for change in [
        {"destination": "https://example.com"},
        {"retry": True},
        {"settings": {"thinking": "disabled"}},
        {"limits": {"requests": 5}},
        {"encoding": "other"},
    ]:
        with pytest.raises(ValueError):
            HostedPlan.model_validate({**plan.model_dump(mode="json"), **change}, strict=True)


def test_compiled_messages_isolated_without_evaluation():
    from humanity_succeed.corpus.compiler import sft_rows

    case, doc = load_case(CASE)
    turns = [VisibleTurn(raw_output=canonical_bytes(ACTIONS[0]).decode(), tool_result={"tag": "CAL-7"})]
    before = canonical_bytes(sft_rows(case, turns))
    doc["evaluation"]["a1_evidence"]["findings"][0]["finding"] = "new evaluator only hidden canary words"
    after = canonical_bytes(sft_rows(CaseSource.model_validate(doc, strict=True), turns))
    assert before == after
    assert b"hostonly_canary_8192" not in before and b"violet kettle" not in before


@pytest.mark.parametrize(
    ("options", "fake", "code", "attempts"),
    [
        ({"limits": {"request_bytes": 1}}, reply("{}"), "request_size_limit", 0),
        ({"limits": {"response_bytes": 1}}, reply("{}"), "response_size_limit", 1),
        ({"limits": {"request_seconds": 1}}, FakeReply(delay_seconds=2), "timeout", 1),
    ],
)
def test_limits_recorded_and_replayed(tmp_path, options, fake, code, attempts):
    p, store, result, ev, doc = execute(tmp_path, [fake], **options)
    errors = [e["payload"] for e in store.events(result.run_id) if e["event_type"] == "provider_error"]
    assert errors[0]["code"] == code and p.attempts == attempts
    assert errors[0]["hosted"]["attempted"] is bool(attempts)
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    assert verify_bundle(bundle)["internal"] == "consistent"
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "reproduced"
    store.close()


def test_episode_expiry_and_changed_authorization_before_dispatch(tmp_path, monkeypatch):
    case, doc = load_case(CASE)
    p = provider(tmp_path, doc, [reply("{}")])
    p.validate_case(doc, subject_view(case).model_dump(mode="json"), "hs-evaluator/0.3.0")
    obs = build_provider_input(subject_view(case), 0, [])
    p.prepare(obs)
    p._start -= 181
    with pytest.raises(HostedFailure, match="episode_budget"):
        p.generate(obs)
    assert p.attempts == 0
    p._start += 181
    p.authorization = p.authorization.model_copy(update={"expires_at": 1})
    with pytest.raises(HostedFailure, match="authorization_changed"):
        p.generate(obs)
    assert p.attempts == 0


@pytest.mark.parametrize("location", ["source", "observation", "configuration"])
def test_secret_inputs_refused_before_persistence(tmp_path, location):
    case, doc = load_case(CASE)
    if location == "source":
        doc["subject"]["task"] += SECRET
    p = provider(tmp_path, doc, [reply("{}")])
    if location == "configuration":
        altered = p.plan.model_dump(mode="json")
        altered["model"] = SECRET
        p.plan = HostedPlan.model_validate(altered, strict=True)
        p.authorization = p.authorization.model_copy(update={"plan_sha256": sha256_obj(altered)})
        # Reconstruct identity to test configuration screening, not authorization-change screening.
        from humanity_succeed.hosted.contracts import HostedIdentity

        p.hosted = HostedIdentity(
            schema_id="hs-hosted-provider/1",
            plan=p.plan,
            authorization=p.authorization,
            plan_sha256=sha256_obj(altered),
            authorization_sha256=sha256_obj(p.authorization.model_dump(mode="json")),
        ).model_dump(mode="json")
    if location in ("source", "configuration"):
        with pytest.raises(HostedFailure, match="credential_in"):
            p.validate_case(
                doc,
                subject_view(CaseSource.model_validate(doc, strict=True)).model_dump(mode="json"),
                "hs-evaluator/0.3.0",
            )
    else:
        p.validate_case(doc, subject_view(case).model_dump(mode="json"), "hs-evaluator/0.3.0")
        obs = build_provider_input(subject_view(case), 0, [VisibleTurn(raw_output=SECRET, tool_result={})])
        with pytest.raises(HostedFailure, match="credential_in_observation"):
            p.prepare(obs)
    assert p.attempts == 0


def test_guard_denial_then_actual_decline(tmp_path):
    deny = {
        "action": {
            "type": "write_resource",
            "resource_id": "r_source",
            "expected_revision": 1,
            "value": {"tag": "changed"},
        }
    }
    decline = {"action": {"type": "decline", "reason": "Scripted engineering decline."}}
    p, store, result, ev, doc = execute(
        tmp_path, [reply(canonical_bytes(a).decode()) for a in [deny, decline]]
    )
    assert len(ev["guard_withheld"]) == len(ev["model_abstained"]) == 1
    assert ev["mechanical"]["verdict"] == "fail"
    assert result.terminal_status == "declined" and p.attempts == 2
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "reproduced"
    store.close()


def test_fixed_https_contract_no_proxy_or_redirect(monkeypatch):
    import ssl

    from humanity_succeed.hosted.transport import _https

    calls = []

    class Connection:
        def __init__(self, host, timeout, context):
            assert host == "api.deepseek.com" and timeout == 2
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            calls.append("connection")

        def request(self, method, path, body, headers):
            assert method == "POST" and path == "/chat/completions" and body == b"{}"
            assert headers["Authorization"] == "Bearer " + SECRET
            calls.append("request")

        def getresponse(self):
            return self

        status = 302

        def close(self):
            calls.append("close")

    monkeypatch.setenv("HTTPS_PROXY", "https://untrusted.invalid")
    monkeypatch.setattr("http.client.HTTPSConnection", Connection)
    assert _https(b"{}", SECRET, 2, 100) == (302, b"")
    assert calls == ["connection", "request", "close"]


def test_missing_hosted_gates_never_access_credentials(tmp_path, monkeypatch, capsys):
    from humanity_succeed.cli import main

    monkeypatch.setattr(
        "humanity_succeed.hosted.provider.read_credential", lambda *_: pytest.fail("credential access")
    )
    args = [
        "hosted",
        "execute",
        "--case",
        str(CASE),
        "--plan",
        str(tmp_path / "absent"),
        "--store",
        str(tmp_path / "store"),
        "--bundle",
        str(tmp_path / "bundle"),
        "--ledger",
        str(tmp_path / "ledger"),
    ]
    assert main(args) == 3
    assert "hosted_gates_missing" in capsys.readouterr().out


def test_static_tamper_detection(tmp_path):
    _, store, result, ev, doc = execute(tmp_path, [reply(canonical_bytes(a).decode()) for a in ACTIONS])
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    anchor = anchor_for(bundle)
    file = bundle / "evaluation.json"
    changed = load_document(file)
    del changed["hosted"]
    file.write_bytes(canonical_bytes(changed))
    assert verify_bundle(bundle, anchor)["internal"] == "failed"
    store.close()


def test_oversized_action_is_observed_not_transport_failure(tmp_path):
    p, store, result, ev, doc = execute(tmp_path, [reply("{}")], limits={"action_bytes": 1})
    assert result.terminal_status == "invalid_action" and p.attempts == 1
    events = store.events(result.run_id)
    assert not any(e["event_type"] == "provider_error" for e in events)
    assert (
        next(e["payload"]["code"] for e in events if e["event_type"] == "action_parse_failed")
        == "action_size_limit"
    )
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "reproduced"
    store.close()


def test_ledger_relocation_requires_new_authorization(tmp_path):
    case, doc = load_case(CASE)
    p = provider(tmp_path, doc, [])
    with pytest.raises(HostedFailure, match="ledger_mismatch"):
        DeepSeekProvider(
            p.plan,
            p.authorization,
            cloud_enabled=True,
            credential_file=tmp_path / "not-a-real-key",
            ledger=tmp_path / "different-ledger",
            fake_replies=[],
        )


def test_unknown_usage_and_identity_remain_unknown(tmp_path):
    fake = reply(canonical_bytes(ACTIONS[-1]).decode())
    data = load_document(CASE)  # Only the disposable fixture is read.
    import json

    envelope = json.loads(fake.body)
    for key in ("id", "usage"):
        del envelope[key]
    _, store, result, ev, doc = execute(tmp_path, [FakeReply(body=canonical_bytes(envelope))])
    response = next(
        e["payload"]["hosted"] for e in store.events(result.run_id) if e["event_type"] == "provider_response"
    )
    assert response["usage"] is None and response["response_id"] is None
    assert ev["hosted"]["weights_sha256"] is None and ev["hosted"]["tokenizer_identity"] is None
    assert data["case_id"] == doc["case_id"]
    store.close()


def test_hybrid_judgment_remains_pending(tmp_path):
    _, doc = load_case(CASE)
    doc["evaluation"].update(
        scoring_mode="hybrid",
        human_rubric=[
            {
                "dimension": "communication_quality",
                "instruction": "Human reviewer judges clarity in the synthetic task.",
            }
        ],
    )
    case = CaseSource.model_validate(doc, strict=True)
    p = provider(tmp_path, doc, [reply(canonical_bytes(a).decode()) for a in ACTIONS])
    store = EvidenceStore(tmp_path / "store")
    result = run_episode(case, doc, p, store, evaluator_version="hs-evaluator/0.3.0")
    ev = evaluate_and_record(store, result.run_id, case)
    assert ev["mechanical"]["verdict"] == "pass" and ev["conduct_outcome"] == "pending_review"
    assert ev["semantic_review"]["status"] == "pending" and ev["semantic_review"]["reviews_received"] == 0
    store.close()


def test_export_cli_reuses_recorded_evaluation(tmp_path, monkeypatch, capsys):
    from humanity_succeed.cli import main

    _, store, result, ev, doc = execute(tmp_path, [reply(canonical_bytes(a).decode()) for a in ACTIONS])
    store.close()
    monkeypatch.setattr(
        "humanity_succeed.hosted.provider.dispatch", lambda *_: pytest.fail("recovery invoked transport")
    )
    assert (
        main(
            [
                "hosted",
                "export",
                "--case",
                str(CASE),
                "--store",
                str(tmp_path / "store.sqlite"),
                "--run-id",
                result.run_id,
                "--bundle",
                str(tmp_path / "recovered"),
            ]
        )
        == 0
    )
    assert '"new_provider_requests": 0' in capsys.readouterr().out
    assert verify_bundle(tmp_path / "recovered")["internal"] == "consistent"


@pytest.mark.parametrize("bad", [None, [], {"schema_id": "hs-evaluation/2"}, "broken"])
def test_malformed_hosted_evaluation_returns_failure_report(tmp_path, bad):
    _, store, result, ev, doc = execute(
        tmp_path, [reply(canonical_bytes(ACTIONS[0]).decode())], limits={"requests": 1}
    )
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    (bundle / "evaluation.json").write_bytes(canonical_bytes(bad))
    assert verify_bundle(bundle)["internal"] == "failed"
    store.close()


def test_versioned_records_require_schema_identifier():
    from humanity_succeed.hosted.contracts import FailureRecord, RequestRecord, ResponseRecord

    for cls in (FailureRecord, RequestRecord, ResponseRecord):
        with pytest.raises(ValueError):
            cls.model_validate({}, strict=True)
