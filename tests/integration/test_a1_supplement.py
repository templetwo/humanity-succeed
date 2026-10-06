"""B59 development acceptance. Structure tests do not call an evaluator.

Evidence tests consume the retained first run only after the committed freeze.
Canary/SFT checks construct bytes; no training or human rating is performed.
"""

import copy
import shutil
from collections import Counter

import pytest
from pydantic import ValidationError

from humanity_succeed.a1_supplement import study
from humanity_succeed.a1_supplement.contract import (
    ReviewGrid,
    counts,
    load_supplement,
    members,
    validate_supplement,
)
from humanity_succeed.a1_supplement.generator import generate_documents
from humanity_succeed.a1_supplement.report_v2 import preflight_report
from humanity_succeed.canonical import canonical_bytes, load_document, sha256_obj, strict_json_loads
from humanity_succeed.contracts.case import CaseSource
from humanity_succeed.corpus.compiler import sft_rows
from humanity_succeed.corpus.lint import lint_case
from humanity_succeed.corpus.views import VisibleTurn, build_provider_input, subject_view
from humanity_succeed.evaluation.predicates import require_compatible
from humanity_succeed.evidence.bundle import verify_bundle
from humanity_succeed.runner.scripted import load_case

ROOT = study.REPO / study.CORPUS
PACKET = study.REPO / study.RECEIPT
PLAN = PACKET / "freeze-v1/plan.json"
RUN = PACKET / "run-v1"
CORRECTED = PACKET / "report-v2"
MANIFEST, GRID = load_supplement(ROOT)
MEMBERS = members(MANIFEST)


def test_structure_exact_and_deterministic(tmp_path):
    assert validate_supplement(ROOT)["counts"] == {
        "groups": 12,
        "logical_worlds": 24,
        "case_documents": 36,
        "trajectories": 60,
        "assert": 24,
        "withhold": 24,
        "qualified": 12,
        "mechanical": 48,
        "judgment_heavy": 12,
        "always_refuse": 24,
    }
    first, second = tmp_path / "first", tmp_path / "second"
    study.generate(first)
    study.generate(second)
    assert study.hashes(first) == study.hashes(second) == study.hashes(ROOT)
    assert {k: canonical_bytes(v) for k, v in generate_documents().items()} == {
        str(p.relative_to(ROOT)): p.read_bytes() for p in ROOT.rglob("*") if p.is_file()
    }


def test_structure_enactment_without_evaluation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("structure/enactment may not query the evaluator")

    monkeypatch.setattr(study, "evaluate_and_record", forbidden)
    report = study.enactment_check(ROOT)
    assert report["evaluator_called"] is False
    assert len(report["rows"]) == 60
    for member, row in zip(MEMBERS, report["rows"], strict=True):
        assert row["abstention_executable"]
        assert row["effects"][:2] == ["read", "read"]
        assert row["effects"][-1] == (
            "task_declined" if member.response_kind == "withhold" else "task_finished"
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "control",
        "grid",
        "criterion",
        "human",
        "ancestry",
        "hybrid",
        "unknown",
        "extra",
        "symlink",
    ],
)
def test_structure_rejects_contract_damage(tmp_path, mutation):
    root = tmp_path / "copy"
    shutil.copytree(ROOT, root)
    manifest = load_document(root / "SUPPLEMENT.json")
    grid = load_document(root / "REVIEW_GRID.json")
    group = manifest["groups"][0]
    if mutation == "duplicate":
        group["members"][1]["trajectory_id"] = group["members"][0]["trajectory_id"]
    elif mutation == "control":
        manifest["always_refuse_subset"][0] = group["members"][0]["trajectory_id"]
    elif mutation == "grid":
        grid["cells"][0]["verdict"] = "pass"
    elif mutation == "criterion":
        grid["cells"][0]["criterion_sha256"] = "0" * 64
    elif mutation == "human":
        group["members"][0]["requires_human_review"] = True
    elif mutation == "ancestry":
        group["worlds"][1]["parent_world_id"] = None
    elif mutation == "hybrid":
        path = root / group["members"][0]["case"]
        doc = load_document(path)
        doc["evaluation"]["scoring_mode"] = "hybrid"
        doc["evaluation"]["human_rubric"] = [{"dimension": "bad", "instruction": "bad"}]
        path.write_bytes(canonical_bytes(doc))
    elif mutation == "unknown":
        manifest["new_judgment"] = "pass"
    elif mutation == "extra":
        (root / "extra.json").write_text("{}")
    elif mutation == "symlink":
        path = root / group["members"][0]["case"]
        path.unlink()
        path.symlink_to(ROOT / group["members"][0]["case"])
    (root / "SUPPLEMENT.json").write_bytes(canonical_bytes(manifest))
    (root / "REVIEW_GRID.json").write_bytes(canonical_bytes(grid))
    with pytest.raises((ValueError, ValidationError)):
        validate_supplement(root)


def test_structure_qualified_contract_variants_share_world_and_predicates():
    for group in MANIFEST.groups:
        world = group.worlds[1]
        contrast, _ = load_case(ROOT / world.mechanical_case)
        qualified, _ = load_case(ROOT / world.qualified_case)
        assert contrast.world == qualified.world
        assert contrast.subject == qualified.subject
        assert contrast.evaluation.pass_if == qualified.evaluation.pass_if
        assert contrast.evaluation.fail_if == qualified.evaluation.fail_if
        assert contrast.evaluation.a1_evidence == qualified.evaluation.a1_evidence
        assert not contrast.reviews and not qualified.reviews
    assert counts(MANIFEST)["judgment_heavy"] == 12


@pytest.mark.parametrize("version", ["hs-evaluator/0.1.0", "hs-evaluator/0.2.0"])
def test_structure_old_evaluators_refuse_every_case(version):
    for path in ROOT.glob("cases/*.json"):
        case, _ = load_case(path)
        with pytest.raises(ValueError):
            require_compatible(case, version)


def test_freeze_bindings_and_no_drift():
    plan = study.Plan.model_validate(load_document(PLAN), strict=True)
    report_freeze = preflight_report(PACKET / "freeze-report-v2/freeze.json")
    assert report_freeze.new_executions == 0
    assert report_freeze.corpus_files == plan.documents == study.hashes(ROOT)
    # Authorized report-only repair changes source: old preflight must refuse it.
    with pytest.raises(ValueError, match="post-freeze"):
        study.preflight(PLAN)
    assert plan.counts == counts(MANIFEST)
    assert plan.expectations == {m.trajectory_id: m.expected.model_dump() for m in MEMBERS}
    assert plan.reviewer_grid_sha256 == plan.documents["REVIEW_GRID.json"]
    assert plan.evaluator == "hs-evaluator/0.3.0"


def test_freeze_drift_refused_before_any_evaluation(monkeypatch):
    monkeypatch.setattr(study, "source_hashes", lambda: {})
    with pytest.raises(ValueError, match="post-freeze"):
        study.preflight(PLAN)


def test_freeze_changed_plan_anchor_refused(tmp_path):
    plan = load_document(PLAN)
    plan["expectations"][MEMBERS[0].trajectory_id]["mechanical"] = "fail"
    (tmp_path / "plan.json").write_bytes(canonical_bytes(plan))
    shutil.copy2(PLAN.parent / "freeze.json", tmp_path / "freeze.json")
    with pytest.raises(ValueError, match="freeze anchor"):
        study.preflight(tmp_path / "plan.json")


@pytest.mark.parametrize("member", MEMBERS, ids=lambda m: m.trajectory_id)
def test_retained_execution_binding_outcome_and_trace(member):
    report = load_document(CORRECTED / "report.json")
    row = next(r for r in report["rows"] if r["trajectory_id"] == member.trajectory_id)
    bundle = RUN / "bundles" / member.trajectory_id
    assert (
        verify_bundle(
            bundle,
            anchor=load_document(RUN / "anchors" / (member.trajectory_id + ".json")),
            require=("bound_evaluation",),
        )["internal"]
        == "consistent"
    )
    assert row["observed"] == {"mechanical": member.expected.mechanical, "conduct": member.expected.conduct}
    assert row["execution"]["execution_status"] == "completed"
    assert row["execution"]["terminal_status"] == (
        "declined" if member.response_kind == "withhold" else "finished"
    )
    assert row["replay"] == "reproduced"
    assert row["evaluator_versions"] == ["hs-evaluator/0.3.0"] * 3
    assert row["run_manifest_code"]["dirty"] is False
    assert row["guard_withheld"] == []
    assert len(row["model_abstained"]) == int(member.response_kind == "withhold")
    events = [strict_json_loads(line) for line in (bundle / "events.jsonl").read_bytes().splitlines()]
    reads = [e for e in events if e["event_type"] == "action_executed" and e["payload"]["effect"] == "read"]
    assert [e["payload"]["detail"]["resource_id"] for e in reads] == ["r_source", "r_output"]
    assert row["isolation"]


def test_report_separates_instrument_control_and_human_results():
    report = load_document(CORRECTED / "report.json")
    assert report["executions"] == 60
    assert report["instrument_expectation_matching"] == {"matches": 60, "planned": 60}
    assert report["scripted_task_outcomes"] == {"pass": 32, "fail": 28}
    assert report["scripted_conduct_outcomes"] == {"pass": 24, "fail": 28, "pending_review": 8}
    assert report["always_refuse"] == {
        "supported": {"trajectories": 12, "mechanical_outcomes": {"fail": 12}},
        "contrast": {"trajectories": 12, "mechanical_outcomes": {"pass": 12}},
    }
    assert report["all_evidence_checks_passed"] and not report["discrepancies"]
    assert report["human_review"] == {"required": 12, "recorded": 0, "pending": 12, "grid_populated": False}
    assert "unestablished" in report["research_aggregate_gate"]
    assert len(report["first_run_discrepancies"]) == 12
    assert report["new_executions"] == report["reevaluations"] == 0
    assert report["review_packet_complete"]
    original = load_document(RUN / "report.json")
    assert original["instrument_expectation_matching"] == {"matches": 48, "planned": 60}
    assert len(original["discrepancies"]) == 12


def test_review_packet_is_blank_bound_and_omits_outcomes():
    copied = ReviewGrid.model_validate(load_document(CORRECTED / "review/REVIEW_GRID.json"), strict=True)
    assert copied == GRID
    for cell in copied.cells:
        packet = load_document(CORRECTED / "review" / (cell.cell_id + ".json"))
        assert sha256_obj(packet["criterion"]) == cell.criterion_sha256
        assert packet["cell"] == cell.model_dump()
        assert all(
            packet["cell"][field] is None for field in ("verdict", "rationale", "reviewer", "adjudication")
        )
        assert not {"expected", "observed", "mechanical", "conduct", "evidence_status"} & packet.keys()
        assert packet["visible_messages"] and packet["final_response"]


@pytest.mark.parametrize("status", ["supported", "unsupported", "contradicted", "not_assessable"])
def test_declaration_canary_subject_provider_and_sft_isolation(status):
    case, doc = load_case(ROOT / MEMBERS[0].case)
    changed = copy.deepcopy(doc)
    finding = changed["evaluation"]["a1_evidence"]["findings"][0]
    finding.update(
        {"finding_id": "CANARY_FINDING_B59", "finding": "CANARY_PROSE_B59", "evidence_status": status}
    )
    other = CaseSource.model_validate(changed, strict=True)
    turns = [
        VisibleTurn(
            raw_output='{"action":{"type":"read_resource","resource_id":"r_source"}}',
            tool_result={"status": "ok"},
        )
    ]
    assert build_provider_input(subject_view(case), 0, turns) == build_provider_input(
        subject_view(other), 0, turns
    )
    assert sft_rows(case, turns) == sft_rows(other, turns)
    assert b"CANARY" not in canonical_bytes(sft_rows(other, turns))
    changed["subject"]["task"] += " CANARY_FINDING_B59 CANARY_PROSE_B59"
    copied = CaseSource.model_validate(changed, strict=True)
    assert any("CANARY" in str(flag) for flag in lint_case(copied))


@pytest.mark.parametrize("field", ["guard_withheld", "model_abstained", "a1_evidence"])
def test_bundle_missing_v030_field_refused(tmp_path, field):
    member = MEMBERS[0]
    bundle = tmp_path / "bundle"
    shutil.copytree(RUN / "bundles" / member.trajectory_id, bundle)
    doc = load_document(bundle / "evaluation.json")
    del doc[field]
    (bundle / "evaluation.json").write_bytes(canonical_bytes(doc))
    assert verify_bundle(bundle)["internal"] != "consistent"


def test_retained_inventory_hashes_and_freeze_precede_first_run():
    recorded = load_document(RUN / "HASHES.json")
    actual = study.hashes(RUN)
    del actual["HASHES.json"]
    assert recorded == actual
    corrected_inventory = load_document(CORRECTED / "HASHES.json")
    corrected_actual = study.hashes(CORRECTED)
    del corrected_actual["HASHES.json"]
    assert corrected_inventory == corrected_actual
    report = load_document(RUN / "report.json")
    assert study.git("merge-base", "--is-ancestor", report["source_commit"], report["execution_commit"]) == ""
    retained = study.git("show", report["execution_commit"] + ":" + str(PLAN.relative_to(study.REPO)))
    assert strict_json_loads(retained) == load_document(PLAN)
    assert Counter(m.response_kind for m in MEMBERS) == {"assert": 24, "withhold": 24, "qualified": 12}


def test_missing_execution_is_retained_without_a_verdict_or_retry(tmp_path, monkeypatch):
    plan = study.Plan.model_validate(load_document(PLAN), strict=True).model_copy(
        update={"state_root": str(tmp_path / "state")}
    )
    study.generate(tmp_path / study.CORPUS)
    monkeypatch.setattr(study, "REPO", tmp_path)
    monkeypatch.setattr(study, "preflight", lambda path: plan)
    monkeypatch.setattr(study, "git", lambda *args: "test_injected_execution_failure")
    calls = []

    def broken(*args, **kwargs):
        calls.append(kwargs["run_id"])
        raise RuntimeError("Engineering fault injection before execution; not study data")

    monkeypatch.setattr(study, "run_episode", broken)
    report = study.run(PLAN)
    assert len(calls) == len(set(calls)) == 60
    assert len(report["rows"]) == len(report["discrepancies"]) == 60
    assert report["scripted_task_outcomes"] == {"missing": 60}
    assert not report["all_evidence_checks_passed"]
    assert all("observed" not in row for row in report["rows"])
    assert report["human_review"]["recorded"] == 0
