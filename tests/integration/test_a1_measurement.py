"""B57/B58 synthetic engineering acceptance. No study supplement or human review authored."""

import copy
import json
import subprocess
import sys
from contextlib import closing

import pytest
from pydantic import ValidationError

from humanity_succeed import A1_EVALUATOR_VERSION, EVALUATOR_VERSION
from humanity_succeed.canonical import canonical_bytes, load_document, sha256_obj
from humanity_succeed.contracts.a1 import A1Evidence
from humanity_succeed.contracts.case import CaseSource
from humanity_succeed.contracts.schemas import implementation_case_schema, schema_errors
from humanity_succeed.corpus.compiler import compile_cases, replay_demonstration, sft_rows
from humanity_succeed.corpus.lint import find_canaries, lint_case
from humanity_succeed.corpus.views import evaluator_view, subject_view
from humanity_succeed.evaluation.predicates import UnsupportedEvaluatorVersion, ops_unavailable
from humanity_succeed.evidence.bundle import export_bundle, verify_bundle
from humanity_succeed.evidence.replay import replay_bundle
from humanity_succeed.evidence.store import EvidenceStore
from humanity_succeed.providers.scripted import ScriptedProvider
from humanity_succeed.runner.episode import SimulatedCrash, run_episode
from humanity_succeed.runner.scripted import evaluate_and_record, load_case, run_scripted

from ..conftest import REPO
from .helpers import act
from .test_wp2_repair_r1 import events_of as read_events
from .test_wp2_repair_r1 import put_events, rebuild_index

FIXTURE = REPO / "tests/fixtures/a1_measurement/case.json"
V3 = A1_EVALUATOR_VERSION
FINISH = act(type="finish", summary="I decline in prose only.", delivered_resource_ids=[])
DECLINE = act(type="decline", reason="Scripted stop event.")
WRITE = act(type="write_resource", resource_id="r_note", expected_revision=1, value={"quantity": 32})
READ = act(type="read_resource", resource_id="r_note")


def doc_case(doc=None):
    doc = load_document(FIXTURE) if doc is None else doc
    return CaseSource.model_validate(doc, strict=True), doc


def trajectory(case, raws):
    return {"schema_id": "hs-scripted-trajectory/1", "trajectory_id": "engineering-a1",
            "case_id": case.case_id, "provenance": {"kind": "engineering_development"},
            "description": "Engineering fixture, not study or model evidence.", "raw_outputs": raws}


def run(tmp_path, raws, doc=None, **kwargs):
    case, doc = doc_case(doc)
    return run_scripted(case, doc, trajectory(case, raws), tmp_path / "store.sqlite",
                        tmp_path / "bundle", evaluator_version=V3, **kwargs)


@pytest.mark.parametrize("status", ["supported", "unsupported", "contradicted", "not_assessable"])
def test_declared_statuses_strictly_accepted(status):
    _, doc = doc_case()
    doc["evaluation"]["a1_evidence"]["findings"][0]["evidence_status"] = status
    assert not schema_errors(doc, implementation_case_schema())
    case, _ = doc_case(doc)
    assert case.evaluation.a1_evidence.findings[0].evidence_status == status


@pytest.mark.parametrize("mutation", ["status", "finding_id", "empty", "null", "unknown",
                                     "unknown_finding", "version", "missing", "duplicate"])
def test_malformed_declarations_refused(mutation):
    _, doc = doc_case()
    a1 = doc["evaluation"]["a1_evidence"]
    if mutation == "status":
        a1["findings"][0]["evidence_status"] = "not_evaluable"
    elif mutation == "finding_id":
        a1["findings"][0]["finding_id"] = "../escape"
    elif mutation == "empty":
        a1["findings"] = []
    elif mutation == "null":
        doc["evaluation"]["a1_evidence"] = None
    elif mutation == "unknown":
        a1["response_grid"] = []
    elif mutation == "unknown_finding":
        a1["findings"][0]["asserted"] = True
    elif mutation == "version":
        a1["schema_id"] = "hs-a1-evidence/2"
    elif mutation == "missing":
        del a1["findings"][0]["evidence_status"]
    else:
        a1["findings"][1]["finding_id"] = a1["findings"][0]["finding_id"]
    with pytest.raises(ValidationError):
        doc_case(doc)
    if mutation != "duplicate":  # distinct IDs are additionally checked by the strict contract
        assert schema_errors(doc, implementation_case_schema())


@pytest.mark.parametrize("version", ["hs-evaluator/0.1.0", "hs-evaluator/0.2.0", "unknown"])
def test_older_versions_refuse_metadata_before_execution_or_compilation(tmp_path, version):
    case, doc = doc_case()
    if version != "unknown":
        assert any("a1_evidence" in s for s in ops_unavailable(case, version))
    with pytest.raises(UnsupportedEvaluatorVersion):
        run_scripted(case, doc, trajectory(case, [DECLINE]), tmp_path / "store.sqlite",
                     tmp_path / "bundle", evaluator_version=version)
    assert not (tmp_path / "store.sqlite").exists()
    with pytest.raises(UnsupportedEvaluatorVersion):
        compile_cases(FIXTURE, tmp_path / "compiled", evaluator_version=version)
    assert not (tmp_path / "compiled").exists()


@pytest.mark.parametrize("raws,guard,abstain", [
    ([WRITE, FINISH], 1, 0), ([DECLINE], 0, 1), ([WRITE, DECLINE], 1, 1), ([FINISH], 0, 0)
])
def test_separate_facts_with_exact_references(tmp_path, raws, guard, abstain):
    bundle, ev = run(tmp_path, raws)
    events = read_events(bundle)
    by_seq = {e["sequence"]: e for e in events}
    assert len(ev["guard_withheld"]) == guard
    assert len(ev["model_abstained"]) == abstain
    assert ev["evidence_class"] == "scripted_instrument"
    for d in ev["guard_withheld"]:
        assert by_seq[d["denial_seq"]]["event_type"] == "action_denied"
        assert by_seq[d["proposal_seq"]]["event_type"] == "action_proposed"
        assert by_seq[d["permission_seq"]]["payload"]["decision"] == "deny"
        assert by_seq[d["denial_seq"]]["payload"]["reason_code"] == d["reason_code"]
        assert ev["conduct_outcome"] == "fail"  # containment gives no credit
    for a in ev["model_abstained"]:
        assert by_seq[a["decline_seq"]]["event_type"] == "task_declined"
        assert by_seq[a["execution_seq"]]["event_type"] == "action_executed"
        assert by_seq[a["proposal_seq"]]["payload"]["action"]["type"] == "decline"
    assert verify_bundle(bundle)["internal"] == "consistent"


def test_denied_decline_is_only_guard_withholding(tmp_path):
    _, doc = doc_case()
    doc["subject"]["allowed_tools"].remove("decline")
    _, ev = run(tmp_path, [DECLINE, FINISH], doc)
    assert ev["guard_withheld"][0]["action_type"] == "decline"
    assert ev["model_abstained"] == []


@pytest.mark.parametrize("raws,fault", [([""], None), ([READ], None), ([DECLINE], "after_permission")])
def test_silence_exhaustion_and_interruption_are_not_abstention(tmp_path, raws, fault):
    case, doc = doc_case()
    with closing(EvidenceStore(tmp_path / "store.sqlite")) as store:
        provider = ScriptedProvider(raws)
        if fault:
            with pytest.raises(SimulatedCrash):
                run_episode(case, doc, provider, store, run_id="interrupted", fault=fault,
                            evaluator_version=V3)
        else:
            run_episode(case, doc, provider, store, run_id="interrupted", evaluator_version=V3)
        ev = evaluate_and_record(store, "interrupted", case)
        assert ev["model_abstained"] == []
        assert ev["mechanical"]["verdict"] == "not_evaluable"
        assert ev["a1_evidence"]["findings"][3]["evidence_status"] == "not_assessable"


def test_declarations_do_not_change_observations_or_conduct_or_judgments(tmp_path):
    case, doc = doc_case()
    changed = copy.deepcopy(doc)
    changed["evaluation"]["a1_evidence"]["findings"][0]["evidence_status"] = "contradicted"
    other, _ = doc_case(changed)
    assert subject_view(case) == subject_view(other)
    evs, pins = [], []
    for n, (c, d) in enumerate([(case, doc), (other, changed)]):
        with closing(EvidenceStore(tmp_path / f"{n}.sqlite")) as store:
            prov = ScriptedProvider([READ, DECLINE])
            res = run_episode(c, d, prov, store, evaluator_version=V3)
            evs.append(evaluate_and_record(store, res.run_id, c))
            pins.append(prov.received_inputs)
    assert pins[0] == pins[1]
    assert {k: v for k, v in evs[0].items() if k != "a1_evidence"} == {
        k: v for k, v in evs[1].items() if k != "a1_evidence"}
    assert evs[0]["conduct_outcome"] == "pending_review"
    assert evs[0]["semantic_review"]["reviews_received"] == 0
    assert evs[0]["semantic_review"]["status"] == "pending"
    assert not {"response_grid", "decision_quality", "asserted", "qualified", "withheld"} & set(evs[0])


def test_canaries_and_positive_leak_controls_in_provider_and_training(tmp_path, monkeypatch):
    _, doc = doc_case()
    canaries = ["A1-HIDDEN-FINDING-ID", "hidden declaration canary sentence only"]
    doc["evaluation"]["a1_evidence"]["findings"][0].update(
        finding_id=canaries[0], finding=canaries[1])
    doc["demonstrations"] = [{"demo_id": "engineering-preferred", "training_role": "preferred",
                              "expected_mechanical_outcome": "pass", "actions": [json.loads(READ),
                                                                                       json.loads(FINISH)]}]
    case, _ = doc_case(doc)
    assert not lint_case(case)
    ev, turns = replay_demonstration(case, doc, "engineering-preferred", evaluator_version=V3)
    assert ev["mechanical"]["verdict"] == "pass"
    assert len(sft_rows(case, turns)) == 2  # actual target prefixes, not an empty dataset check
    assert not find_canaries(canonical_bytes(sft_rows(case, turns)), canaries)
    with closing(EvidenceStore(tmp_path / "store.sqlite")) as store:
        p = ScriptedProvider([WRITE, READ, FINISH])
        run_episode(case, doc, p, store, evaluator_version=V3)
        assert not find_canaries(b"".join(p.received_inputs), canaries)
    path = tmp_path / "case.json"
    path.write_bytes(canonical_bytes(doc))
    assert compile_cases(path, tmp_path / "compiled", evaluator_version=V3)["status"] == "compiled"
    visible = b"".join(p.read_bytes() for p in (tmp_path / "compiled/subject_views").glob("*"))
    visible += (tmp_path / "compiled/train.jsonl").read_bytes()
    assert not find_canaries(visible, canaries)
    assert find_canaries(canonical_bytes(evaluator_view(case)), canaries) == canaries
    for target in ["task", "resource", "demo", "resource_key", "handle"]:
        leaked = copy.deepcopy(doc)
        if target == "task":
            leaked["subject"]["task"] += " ".join(canaries)
        elif target == "resource":
            leaked["world"]["resources"]["r_note"]["value"]["leak"] = " ".join(canaries)
        elif target == "demo":
            leaked["demonstrations"][0]["actions"][0]["message"] = " ".join(canaries)
        elif target == "resource_key":
            leaked["world"]["resources"]["r_note"]["value"][canaries[0]] = canaries[1]
        else:
            leaked["subject"]["visible_resource_ids"].append(canaries[0])
            leaked["world"]["resources"][canaries[0]] = {"revision": 1, "value": canaries[1]}
            leaked["world"]["permissions"]["readable_ids"].append(canaries[0])
        flags = lint_case(doc_case(leaked)[0])
        assert any(f["kind"] == "hidden_label_in_visible_text:finding_id" for f in flags)
        assert any(f["kind"] == "a1_finding_in_visible_text" for f in flags)
    import humanity_succeed.runner.episode as ep
    real = ep.build_provider_input
    monkeypatch.setattr(ep, "build_provider_input",
                        lambda v, tick, turns: real(v, tick, turns) + canonical_bytes(evaluator_view(case)))
    with closing(EvidenceStore(tmp_path / "leaky.sqlite")) as store:
        p = ScriptedProvider([FINISH])
        run_episode(case, doc, p, store, evaluator_version=V3)
        assert find_canaries(b"".join(p.received_inputs), canaries) == canaries


def test_manifest_evaluation_binding_export_and_replay_agree(tmp_path):
    bundle, ev = run(tmp_path, [WRITE, DECLINE])
    manifest = load_document(bundle / "manifest.json")
    assert manifest["versions"]["evaluator"] == ev["evaluator_version"] == V3
    binding = read_events(bundle)[-1]["payload"]
    assert binding == {"evaluation_sha256": sha256_obj(ev), "evaluator_version": V3}
    assert verify_bundle(bundle, require=("bound_evaluation",))["internal"] == "consistent"
    rp = replay_bundle(bundle, tmp_path / "replay")["replay"]
    assert rp["status"] == "reproduced" and rp["evaluator_version_used"] == V3


def rebind_evaluation(bundle, ev):
    (bundle / "evaluation.json").write_bytes(canonical_bytes(ev))
    events = read_events(bundle)
    events[-1]["payload"] = {"evaluation_sha256": sha256_obj(ev),
                              "evaluator_version": ev["evaluator_version"]}
    put_events(bundle, events)
    rebuild_index(bundle)


@pytest.mark.parametrize("mutation", ["missing_guard", "missing_abstain", "bad_guard", "bad_abstain",
                                     "null_decl", "bad_status", "duplicate", "grid", "ref", "declaration",
                                     "version"])
def test_rehashed_invalid_v030_evidence_fails_validation(tmp_path, mutation):
    bundle, ev = run(tmp_path, [WRITE, DECLINE])
    if mutation == "missing_guard":
        del ev["guard_withheld"]
    elif mutation == "missing_abstain":
        del ev["model_abstained"]
    elif mutation == "bad_guard":
        ev["guard_withheld"][0]["denial_seq"] = True
    elif mutation == "bad_abstain":
        ev["model_abstained"][0]["judgment"] = "justified"
    elif mutation == "null_decl":
        ev["a1_evidence"] = None
    elif mutation == "bad_status":
        ev["a1_evidence"]["findings"][0]["evidence_status"] = "unknown"
    elif mutation == "duplicate":
        ev["a1_evidence"]["findings"].append(copy.deepcopy(ev["a1_evidence"]["findings"][0]))
    elif mutation == "grid":
        ev["response_grid"] = {"asserted": "correct"}
    elif mutation == "ref":
        ev["model_abstained"][0]["decline_seq"] = 1
    elif mutation == "declaration":
        ev["a1_evidence"]["findings"][0]["evidence_status"] = "unsupported"
    else:
        ev["evaluator_version"] = EVALUATOR_VERSION
    rebind_evaluation(bundle, ev)
    assert verify_bundle(bundle)["internal"] == "failed"
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "refused"


def test_retained_anchor_and_replay_detect_rehashed_semantic_tampering(tmp_path):
    from humanity_succeed.evidence.bundle import anchor_for
    bundle, ev = run(tmp_path, [DECLINE])
    anchor = anchor_for(bundle)
    ev["conduct_outcome"] = "pass"  # well-shaped forgery, not a human review
    rebind_evaluation(bundle, ev)
    assert verify_bundle(bundle)["internal"] == "consistent"
    assert verify_bundle(bundle, anchor=anchor)["anchor"] == "failed"
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "diverged"


def test_cli_explicit_selection_and_legacy_default_refusal(tmp_path):
    args = [sys.executable, "-m", "humanity_succeed.cli", "run", "scripted", "--case", str(FIXTURE)]
    case, _ = doc_case()
    path = tmp_path / "traj.json"
    path.write_bytes(canonical_bytes(trajectory(case, [DECLINE])))
    args += ["--trajectory", str(path), "--state-root", str(tmp_path / "state")]
    no_version = subprocess.run([*args, "--out", str(tmp_path / "refused")], capture_output=True)
    assert no_version.returncode == 4
    assert json.loads(no_version.stdout)["error"]["code"] == "unsupported_evaluator_version"
    yes = subprocess.run([*args, "--out", str(tmp_path / "bundle"), "--evaluator-version", V3],
                         capture_output=True)
    assert yes.returncode == 0, yes.stderr
    assert json.loads(yes.stdout)["result"]["evaluator_version"] == V3


def test_absence_stays_absent_in_legacy_serialization(correction_doc):
    case = CaseSource.model_validate(correction_doc, strict=True)
    for exclude in [False, True]:
        assert "a1_evidence" not in case.model_dump(mode="json", exclude_none=exclude)["evaluation"]
    assert "a1_evidence" not in evaluator_view(case)
    assert EVALUATOR_VERSION == "hs-evaluator/0.2.0"


def test_explicit_v030_on_legacy_case_adds_facts_not_inferred_declarations(tmp_path, correction_doc):
    case = CaseSource.model_validate(correction_doc, strict=True)
    with closing(EvidenceStore(tmp_path / "legacy.sqlite")) as store:
        res = run_episode(case, correction_doc, ScriptedProvider([FINISH]), store, evaluator_version=V3)
        ev = evaluate_and_record(store, res.run_id, case)
        assert ev["guard_withheld"] == ev["model_abstained"] == []
        assert "a1_evidence" not in ev
        bundle = export_bundle(store, res.run_id, correction_doc, ev, tmp_path / "bundle")
    assert verify_bundle(bundle)["internal"] == "consistent"
    assert replay_bundle(bundle, tmp_path / "replay")["replay"]["status"] == "reproduced"


def test_inconsistent_evaluation_version_refused(tmp_path):
    case, doc = doc_case()
    with closing(EvidenceStore(tmp_path / "store.sqlite")) as store:
        res = run_episode(case, doc, ScriptedProvider([DECLINE]), store, evaluator_version=V3)
        with pytest.raises(ValueError, match="manifest"):
            evaluate_and_record(store, res.run_id, case, evaluator_version=EVALUATOR_VERSION)


def test_complete_v030_run_without_evaluation_replays_events_only(tmp_path):
    case, doc = doc_case()
    with closing(EvidenceStore(tmp_path / "store.sqlite")) as store:
        res = run_episode(case, doc, ScriptedProvider([DECLINE]), store, evaluator_version=V3)
        bundle = export_bundle(store, res.run_id, doc, None, tmp_path / "bundle")
    rp = replay_bundle(bundle, tmp_path / "replay")["replay"]
    assert rp["status"] == "events_reproduced_evaluation_absent"
    assert rp["evaluator_version_used"] == V3


def test_fixture_is_development_and_unreviewed():
    case, _ = load_case(FIXTURE)
    assert case.split == "commissioning_dev" and case.reviews == []
    assert case.provenance.private_material is False
    assert isinstance(case.evaluation.a1_evidence, A1Evidence)
