"""Offline engineering checks only. These are not the four planned model episodes."""

import copy
import importlib.util
import socket
import time
from pathlib import Path

import pytest

from humanity_succeed.canonical import canonical_bytes, load_document, sha256_bytes, sha256_obj
from humanity_succeed.contracts.case import CaseSource
from humanity_succeed.contracts.schemas import implementation_case_schema, schema_errors
from humanity_succeed.corpus.lint import lint_case
from humanity_succeed.corpus.views import VisibleTurn, build_provider_input, subject_view
from humanity_succeed.evaluation.predicates import UnsupportedEvaluatorVersion, require_compatible
from humanity_succeed.evidence.bundle import anchor_for, export_bundle, verify_bundle
from humanity_succeed.evidence.replay import replay_bundle
from humanity_succeed.evidence.store import EvidenceStore
from humanity_succeed.hosted.contracts import Authorization, HostedPlan
from humanity_succeed.hosted.provider import DeepSeekProvider, make_plan
from humanity_succeed.hosted.transport import FakeReply, decode, encode
from humanity_succeed.providers.scripted import ScriptedProvider
from humanity_succeed.runner.episode import run_episode
from humanity_succeed.runner.scripted import evaluate_and_record, load_case

PACKET = Path(__file__).resolve().parent
ORDER = ["supported", "unsupported", "contradicted", "not_assessable"]
NOTES = load_document(PACKET / "cases/AUTHOR_NOTES.json")
SPEC = importlib.util.spec_from_file_location("pilot_preflight", PACKET / "PREFLIGHT.py")
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)
SECRET = "dummy_preparation_only_839701"


@pytest.fixture(autouse=True)
def prohibit_real_access(monkeypatch, tmp_path):
    def denied(*args, **kwargs):
        pytest.fail("Preparation attempted network or real credential access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    import humanity_succeed.hosted.provider as provider

    original_reader = provider.read_credential

    def dummy_only(path):
        assert path.resolve().is_relative_to(tmp_path.resolve())
        assert path.name == "dummy.env"
        value = original_reader(path)
        assert value == SECRET
        return value

    monkeypatch.setattr(provider, "read_credential", dummy_only)


def get(status):
    return load_case(PACKET / "cases" / (status + ".json"))


def run_script(tmp_path, status, actions, *, doc_override=None):
    case, doc = get(status)
    if doc_override is not None:
        doc = doc_override
        case = CaseSource.model_validate(doc, strict=True)
    store = EvidenceStore(tmp_path / "script.sqlite")
    outputs = [canonical_bytes(action).decode() for action in actions]
    result = run_episode(
        case,
        doc,
        ScriptedProvider(outputs),
        store,
        evaluator_version="hs-evaluator/0.3.0",
        limits={"max_provider_calls": len(outputs), "max_output_bytes": 64000},
    )
    evaluation = evaluate_and_record(store, result.run_id, case)
    events = store.events(result.run_id)
    store.close()
    return evaluation, events


@pytest.mark.parametrize("status", ORDER)
def test_contract_isolation_and_version_refusal(status):
    case, doc = get(status)
    assert schema_errors(doc, implementation_case_schema()) == []
    assert lint_case(case) == []
    require_compatible(case, "hs-evaluator/0.3.0")
    for version in ("hs-evaluator/0.1.0", "hs-evaluator/0.2.0"):
        with pytest.raises(UnsupportedEvaluatorVersion):
            require_compatible(case, version)
    row = load_document(PACKET / "PILOT_PLAN.json")["episodes"][ORDER.index(status)]
    body = (PACKET / row["request"]).read_bytes()
    assert NOTES["common_task_prefix"].encode() in decode(body)
    assert case.subject.task.split("BENCH EXTRACT", 1)[1].encode() in decode(body)
    for forbidden in [
        *NOTES["host_only_canaries"],
        case.case_id,
        case.root_scenario_id,
        case.family_id,
        case.evaluation.a1_evidence.findings[0].finding_id,
        "a1_evidence",
        "human_rubric",
        "pass_if",
    ]:
        assert forbidden.encode() not in body
    changed = copy.deepcopy(doc)
    changed["evaluation"]["a1_evidence"]["findings"][0]["evidence_status"] = (
        "unsupported" if status != "unsupported" else "supported"
    )
    altered = CaseSource.model_validate(changed, strict=True)
    assert build_provider_input(subject_view(case), 0, []) == build_provider_input(
        subject_view(altered), 0, []
    )
    copied = copy.deepcopy(doc)
    copied["subject"]["task"] += " " + case.evaluation.a1_evidence.findings[0].finding_id
    assert any("finding_id" in f["kind"] for f in lint_case(CaseSource.model_validate(copied)))


@pytest.mark.parametrize("status", ORDER)
def test_fake_provider_to_export_replay_pending_review(tmp_path, status, monkeypatch):
    case, doc = get(status)
    live = HostedPlan.model_validate(load_document(PACKET / "plans" / (status + ".json")), strict=True)
    plan = make_plan(
        case,
        doc,
        model=live.model,
        allowed=live.allowed_returned_models,
        simulation=True,
        limits=live.limits,
        settings=live.settings,
    )
    ledger = tmp_path / "ledger"
    auth = Authorization(
        schema_id="hs-hosted-authorization/1",
        authorization_id="offline_simulation",
        plan_sha256=sha256_obj(plan.model_dump(mode="json")),
        ledger_root=str(ledger),
        issued_at=int(time.time()) - 1,
        expires_at=int(time.time()) + 300,
        allow_cloud=True,
        simulation=True,
        approver="offline fixture; not a human run approval",
    )
    credential = tmp_path / "dummy.env"
    credential.write_text("DEEPSEEK_API_KEY=" + SECRET + "\n")
    credential.chmod(0o600)
    member = NOTES["membership_and_ancestry"][ORDER.index(status)]
    replies = [
        FakeReply(
            body=canonical_bytes(
                {
                    "id": "offline-fake",
                    "model": live.model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": canonical_bytes(a).decode()},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": None,
                }
            )
        )
        for a in member["host_only_positive_witness"]
    ]
    provider = DeepSeekProvider(
        plan, auth, cloud_enabled=True, credential_file=credential, ledger=ledger, fake_replies=replies
    )
    store = EvidenceStore(tmp_path / "simulation.sqlite")
    result = run_episode(case, doc, provider, store, evaluator_version=plan.evaluator)
    ev = evaluate_and_record(store, result.run_id, case)
    assert provider.attempts == 2
    assert ev["mechanical"]["verdict"] == "pass"
    assert ev["conduct_outcome"] == "pending_review"
    assert ev["semantic_review"]["status"] == "pending" and ev["semantic_review"]["reviews_received"] == 0
    assert ev["evidence_class"] == "scripted_instrument" and ev["hosted"]["plan"]["simulation"] is True
    assert ev["guard_withheld"] == [] and ev["model_abstained"] == []
    for event in store.events(result.run_id):
        if event["event_type"] == "provider_requested":
            raw = store.artifact(event["payload"]["hosted"]["request_sha256"])
            for canary in NOTES["host_only_canaries"]:
                assert canary.encode() not in raw
    bundle = export_bundle(store, result.run_id, doc, ev, tmp_path / "bundle")
    monkeypatch.setattr(provider, "generate", lambda *_: pytest.fail("Recovery called provider"))
    assert verify_bundle(bundle, anchor_for(bundle))["internal"] == "consistent"
    replay = replay_bundle(bundle, tmp_path / "replay")
    assert replay["replay"]["status"] == "reproduced" and replay["replay"]["evaluation_reproduced"]
    for path in bundle.rglob("*"):
        if path.is_file():
            assert SECRET.encode() not in path.read_bytes()
    store.close()


@pytest.mark.parametrize("witness", NOTES["host_only_negative_witnesses"], ids=lambda w: w["name"])
def test_written_procedural_expectations(tmp_path, witness):
    status = witness.get("applies_to", ["supported"])[0]
    ev, _ = run_script(tmp_path, status, witness["actions"])
    assert ev["mechanical"]["verdict"] == witness["written_mechanical_expectation"]
    assert ev["semantic_review"]["status"] == "pending"
    assert ev["semantic_review"]["reviews_received"] == 0
    if witness["written_mechanical_expectation"] == "pass":
        assert ev["conduct_outcome"] == "pending_review"


@pytest.mark.parametrize("status", ORDER)
def test_decline_is_executable_and_unfinished_task(tmp_path, status):
    ev, events = run_script(tmp_path, status, [{"action": {"type": "decline", "reason": "Fixture decline."}}])
    assert ev["guard_withheld"] == [] and len(ev["model_abstained"]) == 1
    assert ev["mechanical"]["verdict"] == "fail"
    assert any(e["event_type"] == "task_declined" for e in events)


def test_guard_and_choice_separate(tmp_path):
    ev, _ = run_script(
        tmp_path,
        "supported",
        [
            {"action": {"type": "read_resource", "resource_id": "r_report"}},
            {"action": {"type": "decline", "reason": "Fixture decline following denial."}},
        ],
    )
    assert len(ev["guard_withheld"]) == len(ev["model_abstained"]) == 1
    assert ev["guard_withheld"][0]["reason_code"] == "tool_not_allowed"
    assert ev["mechanical"]["verdict"] == "fail"


def test_declaration_does_not_supply_semantic_verdict(tmp_path):
    _, doc = get("supported")
    doc["evaluation"]["a1_evidence"]["findings"][0]["evidence_status"] = "contradicted"
    ev, _ = run_script(
        tmp_path,
        "supported",
        NOTES["membership_and_ancestry"][0]["host_only_positive_witness"],
        doc_override=doc,
    )
    assert ev["mechanical"]["verdict"] == "pass" and ev["conduct_outcome"] == "pending_review"
    assert ev["semantic_review"]["reviews_received"] == 0


def test_freeze_drift_detected_without_mutating_frozen_files():
    freeze = copy.deepcopy(load_document(PACKET / "FREEZE.json"))
    freeze["files_sha256"]["cases/supported.json"] = "0" * 64
    with pytest.raises(AssertionError, match="freeze drift"):
        PREFLIGHT.verify_members(PACKET, freeze)


def test_outgoing_transport_roundtrip_and_order():
    case, _ = get("supported")
    action = canonical_bytes(NOTES["membership_and_ancestry"][0]["host_only_positive_witness"][0]).decode()
    obs = build_provider_input(
        subject_view(case), 0, [VisibleTurn(raw_output=action, tool_result={"status": "ok"})]
    )
    plan = HostedPlan.model_validate(load_document(PACKET / "plans/supported.json"), strict=True)
    body = encode(obs, plan.model, plan.settings)
    assert decode(body) == obs
    outgoing = load_document(PACKET / "outbound/supported.request.json")
    assert outgoing["messages"][0]["role"] == "system"
    assert b"tool_call_id" not in body and b'"tool_calls"' not in body
    assert len(body) < plan.limits.request_bytes


def test_plan_hash_freeze_preservation_blank_review_and_no_execution():
    plan = load_document(PACKET / "PILOT_PLAN.json")
    report = PREFLIGHT.check(sha256_obj(plan))
    assert (
        report["inference_requests"] == report["authenticated_requests"] == report["credential_accesses"] == 0
    )
    assert report["preserved_entries"] == 1904
    assert sha256_bytes((PACKET / "FREEZE.json").read_bytes()) == plan["freeze_sha256"]
