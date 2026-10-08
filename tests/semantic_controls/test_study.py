"""Enactment, plan -> run end to end, the review export seam, and the run's refusals.

Every member must be a mechanical pass reaching conduct ``pending_review`` (measured here through
``commissioning.execute.run_in_memory`` and again through the real run), while the 12 wrong members'
written human verdict is ``fail``: that is what makes them semantic controls.

Contract defect 1 (see ``tests/semantic_controls/__init__.py``) makes ``plan_supplement`` refuse
every valid supplement. The end-to-end fixture therefore replaces ``study.supplement_problems``
with the contract function minus exactly that defect line, explicitly and only inside the fixture;
``test_plan_refuses_the_committed_tree_while_contract_defect_1_stands`` pins the raw refusal.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from humanity_succeed import ENGINE_VERSION, EVALUATOR_VERSION
from humanity_succeed.canonical import canonical_bytes, sha256_bytes
from humanity_succeed.commissioning.contract import Expectation
from humanity_succeed.commissioning.execute import enactment, matches, observed, run_in_memory
from humanity_succeed.contracts.case import CaseSource
from humanity_succeed.review import export as review_export
from humanity_succeed.review.contract import CONTROLS_CONFIG, RubricLine
from humanity_succeed.semantic_controls import generator as G
from humanity_succeed.semantic_controls import study
from humanity_succeed.semantic_controls.contract import (
    ANGLES,
    CASES_DIR,
    HONEST_ROLE,
    MANIFEST_FILE,
    PLAN_SCHEMA,
    REPORT_SCHEMA,
    RUBRIC_DIMENSION,
    RUBRIC_INSTRUCTION,
    ControlExpectation,
    SupplementManifest,
)

from ..conftest import REPO

COMMITTED = REPO / CASES_DIR
COMMISSION_RUN = REPO / "docs" / "receipts" / "wp3" / "run"
SUITE_V1 = REPO / "cases" / "commissioning_suite_v1"


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode() + b"\0")
        if p.is_file():
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()





# ---------------------------------------------------------------- enactment (measured, in memory)


def test_every_member_enacts_a_mechanical_pass_pending_review():
    seen = 0
    for g in G.groups():
        case = CaseSource.model_validate(g.case, strict=True)
        for m in g.members:
            raws = m.trajectory["raw_outputs"]
            ev, events = run_in_memory(case, g.case, raws, evaluate=True)
            obs = observed(ev)
            assert obs == {"mechanical": "pass", "conduct": "pending_review", "contained": False}, \
                m.fixture_id
            assert matches(Expectation(**m.expected.as_suite_expectation()), obs)
            en = enactment(events)
            assert en["parse_failures"] == [] and en["denied"] == []
            assert len(en["writes"]) == 1 and len(en["notified"]) == 1
            assert en["finished"] is True and en["declined"] is False
            kinds = [e["event_type"] for e in events]
            assert kinds.index("resource_revised") < kinds.index("notification_delivered")
            want = "pass" if m.role == HONEST_ROLE else "fail"
            assert m.expected.expected_human_verdict == want
            seen += 1
    assert seen == 24


def test_a_notify_without_resource_ids_would_fail_mechanically():
    """Why every notify keeps resource_ids (advisory trap): measured, not assumed."""
    g = G.groups()[2]
    case = CaseSource.model_validate(g.case, strict=True)
    raws = []
    for r in g.members[1].trajectory["raw_outputs"]:
        act = json.loads(r)["action"]
        if act["type"] == "notify":
            act.pop("resource_ids")
        raws.append(G.action(**act))
    ev, _ = run_in_memory(case, g.case, raws, evaluate=True)
    assert ev["mechanical"]["verdict"] != "pass"


# ---------------------------------------------------------------- plan -> run end to end


@pytest.fixture(scope="module")
def e2e(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sc_e2e")
    suite_before = _tree_hash(SUITE_V1)
    committed_before = _tree_hash(COMMITTED)
    # the RAW contract, no filter: the lead fixed the two defects this lane found (da73937)
    state = tmp / "state"
    plan = study.plan_supplement(COMMITTED, tmp / "plan", state_root=state, repo_root=REPO)
    run = study.run_supplement(tmp / "plan" / "plan.json", tmp / "run", state_root=state,
                               repo_root=REPO)
    export = review_export.export_packet_v2(COMMISSION_RUN, tmp / "run", tmp / "packet",
                                           state_root=state, seed="semantic-controls-e2e")
    return {"tmp": tmp, "state": state, "plan": plan, "run": run, "export": export,
            "suite_before": suite_before, "committed_before": committed_before}


def test_plan_is_frozen_and_complete(e2e):
    res = e2e["plan"]
    assert res["status"] == "ok" and res["problems"] == []
    raw = (e2e["tmp"] / "plan" / "plan.json").read_bytes()
    assert res["plan_sha256"] == sha256_bytes(raw)
    plan = json.loads(raw)
    assert raw == canonical_bytes(plan)
    assert plan["schema_id"] == PLAN_SCHEMA and plan["mode"] == "development"
    assert plan["supplement"]["supplement_id"] == "supplement_a1_semantic_controls_v1"
    assert plan["supplement"]["path"] == str(COMMITTED)
    on_disk = {p.relative_to(COMMITTED).as_posix(): sha256_bytes(p.read_bytes())
               for p in COMMITTED.rglob("*") if p.is_file()}
    assert plan["files"] == on_disk and len(on_disk) == 37
    assert plan["supplement"]["manifest_sha256"] == on_disk[MANIFEST_FILE]
    assert plan["versions"]["evaluator"] == EVALUATOR_VERSION
    assert plan["versions"]["engine"] == ENGINE_VERSION
    assert set(plan["versions"]) == {"evaluator", "engine", "compiler", "package"}
    assert plan["claim_boundary"]
    man = SupplementManifest.model_validate_json((COMMITTED / MANIFEST_FILE).read_text())
    want = sorted(({"fixture_id": m.fixture_id, "group_id": g.group_id, "class_id": g.class_id,
                    "role": m.role, "case": m.case, "trajectory": m.trajectory,
                    "expected": m.expected.model_dump(mode="json")}
                   for g in man.groups for m in g.members), key=lambda r: r["fixture_id"])
    assert plan["fixtures"] == want


def test_run_meets_every_mechanical_expectation(e2e):
    res = e2e["run"]
    assert res["status"] == "completed" and res["problems"] == []
    rep = res["report"]
    assert json.loads((e2e["tmp"] / "run" / "report.json").read_bytes()) == rep
    assert rep["schema_id"] == REPORT_SCHEMA
    assert rep["plan_sha256"] == e2e["plan"]["plan_sha256"]
    rows = rep["fixtures"]
    assert len(rows) == 24
    for r in rows:
        assert {"fixture_id", "group_id", "class_id", "partition", "source", "expected",
                "observed", "match", "verify_internal", "bundle", "mutations", "role",
                "angle"} <= set(r)
        assert (r["partition"], r["source"], r["class_id"]) == (
            "development", "supplement", "C1_correction_claim")
        assert r["bundle"] == f"bundles/{r['fixture_id']}"
        assert r["verify_internal"] == "consistent"
        assert r["match"] is True
        assert r["observed"] == {"mechanical": "pass", "conduct": "pending_review",
                                 "contained": False}
        exp = ControlExpectation.model_validate(r["expected"])
        assert exp.angle == r["angle"]
        assert r["role"] == (HONEST_ROLE if exp.angle is None else exp.angle)
        assert len(r["mutations"]["checks"]) == 4
        assert all(c["held"] for c in r["mutations"]["checks"])
    assert sorted(r["angle"] for r in rows if r["angle"]) == sorted(list(ANGLES) * 3)
    bundles = sorted(p.name for p in (e2e["tmp"] / "run" / "bundles").iterdir())
    assert bundles == sorted(r["fixture_id"] for r in rows)
    assert rep["mechanical"]["status"] == "development_all_expectations_met"
    assert rep["mutations_summary"] == {"checks": 96, "held": 96, "violated": []}
    assert rep["lifecycle_state"] == "mechanically_validated"
    sem = rep["semantic"]
    assert sem["status"] == "pending_no_human_reviews"
    assert sem["known_fail_fixture_ids"] == sorted(r["fixture_id"] for r in rows
                                                   if r["role"] != HONEST_ROLE)
    assert len(sem["known_fail_fixture_ids"]) == 12
    assert sem["honest_fixture_ids"] == sorted(f"sc-g{i:02d}-true_notice" for i in range(1, 13))
    assert set(rep["supplement"]) >= {"path", "supplement_id", "manifest_sha256"}
    assert rep["versions"] == json.loads((e2e["tmp"] / "plan" / "plan.json").read_bytes())["versions"]
    assert not (e2e["tmp"] / "run" / "report.html").exists()


def test_run_ids_and_stores_follow_the_commissioning_run(e2e):
    plan_sha = e2e["plan"]["plan_sha256"]
    for b in (e2e["tmp"] / "run" / "bundles").iterdir():
        idx = json.loads((b / "bundle.json").read_bytes())
        want = "run_" + hashlib.sha256(f"{plan_sha}:{b.name}:run".encode()).hexdigest()[:20]
        assert idx["run_id"] == want
    stores = list((e2e["state"] / "runs").glob("controls-*.sqlite"))
    assert len(stores) == 24


def test_review_export_reads_rows_and_bundles_unchanged(e2e):
    rep = e2e["run"]["report"]
    rows = review_export._judgment_heavy_rows(rep)
    assert len(rows) == 24
    by_id = {g.case_id: g for g in G.groups()}
    for row in rows:
        item = review_export._build_item(e2e["tmp"] / "run" / row["bundle"], "it_" + "0" * 16)
        assert item.rubric == [RubricLine(dimension=RUBRIC_DIMENSION, instruction=RUBRIC_INSTRUCTION)]
        g = by_id[row["group_id"]]
        assert item.task == g.case["subject"]["task"]
        [member] = [m for m in g.members if m.fixture_id == row["fixture_id"]]
        [notify] = [s for s in item.steps if s.proposed.get("type") == "notify"]
        assert notify.proposed["text"] == json.loads(member.trajectory["raw_outputs"][2])["action"]["text"]
        assert all(s.message is None for s in item.steps)


def test_full_blind_export_passes_its_leak_scan(e2e):
    res = e2e["export"]
    assert res["status"] == "ok", res["problems"]
    assert res["items"] == 36 + sum(CONTROLS_CONFIG.values())
    text = Path(res["paths"]["packet"]).read_text(encoding="utf-8")
    html = Path(res["paths"]["html"]).read_text(encoding="utf-8")
    # "blame" is in the pinned rubric line itself, so only its quoted (JSON value) form counts
    for token in ("sc-g", "supplement", "true_notice", "wrong_total", "silent_omission",
                  "reversed_correction", '"blame"', "expected_human_verdict", "A1-SC-C1",
                  "semantic controls", "known_fail"):
        assert token not in text and token not in html, token


def test_committed_trees_are_untouched(e2e):
    assert _tree_hash(SUITE_V1) == e2e["suite_before"]
    assert _tree_hash(COMMITTED) == e2e["committed_before"]


# ---------------------------------------------------------------- refusals


def test_plan_of_the_committed_tree_with_the_raw_contract(tmp_path):
    res = study.plan_supplement(COMMITTED, tmp_path / "plan", state_root=tmp_path / "state",
                                repo_root=REPO)
    assert res["status"] == "ok", res["problems"][:3]


def test_plan_refuses_a_contract_problem_and_writes_nothing(tmp_path):
    root = tmp_path / "sup"
    shutil.copytree(COMMITTED, root)
    p = root / "cases" / "sc-g05.yaml"
    p.write_text(p.read_text().replace("accurately describe", "describe"))
    res = study.plan_supplement(root, tmp_path / "plan", state_root=tmp_path / "state",
                                repo_root=REPO)
    assert res["status"] == "blocked_input"
    assert "sc-g05-true_notice: human_rubric is not exactly the pinned C1 line" in res["problems"]
    assert not (tmp_path / "plan").exists()


def test_plan_refuses_a_missing_or_invalid_manifest(tmp_path):
    root = tmp_path / "sup"
    shutil.copytree(COMMITTED, root)
    (root / MANIFEST_FILE).unlink()
    res = study.plan_supplement(root, tmp_path / "plan", state_root=tmp_path / "s", repo_root=REPO)
    assert res["status"] == "blocked_input" and "cannot read" in res["problems"][0]
    (root / MANIFEST_FILE).write_text("{}")
    res = study.plan_supplement(root, tmp_path / "plan", state_root=tmp_path / "s", repo_root=REPO)
    assert res["status"] == "blocked_input" and "invalid" in res["problems"][0]
    assert not (tmp_path / "plan").exists()


@pytest.fixture
def planned_copy(tmp_path):
    root = tmp_path / "sup"
    shutil.copytree(COMMITTED, root)
    res = study.plan_supplement(root, tmp_path / "plan", state_root=tmp_path / "state",
                                repo_root=REPO)
    assert res["status"] == "ok"
    return root, tmp_path / "plan" / "plan.json", tmp_path / "state"


def test_run_refuses_a_tampered_file(tmp_path, planned_copy):
    root, plan, state = planned_copy
    t = root / "trajectories" / "sc-g02-blame.yaml"
    t.write_text(t.read_text().replace("that you entered", "that I entered"))
    res = study.run_supplement(plan, tmp_path / "run", state_root=state, repo_root=REPO)
    assert res["status"] == "plan_tampered"
    assert res["problems"] == ["trajectories/sc-g02-blame.yaml: hash changed since the plan was "
                               "written"]
    assert not (tmp_path / "run").exists() and not (state / "runs").exists()


def test_run_refuses_an_added_or_missing_file(tmp_path, planned_copy):
    root, plan, state = planned_copy
    (root / "trajectories" / "sc-g02-extra.yaml").write_text("x: 1\n")
    (root / "cases" / "sc-g07.yaml").unlink()
    res = study.run_supplement(plan, tmp_path / "run", state_root=state, repo_root=REPO)
    assert res["status"] == "plan_tampered"
    assert any(p.startswith("cases/sc-g07.yaml: missing") for p in res["problems"])
    assert "trajectories/sc-g02-extra.yaml: not in the plan (added since the plan was written)" \
        in res["problems"]
    assert not (tmp_path / "run").exists()


def test_run_refuses_an_evaluator_or_engine_mismatch(tmp_path, planned_copy):
    _root, plan, state = planned_copy
    doc = json.loads(plan.read_bytes())
    for field, value in (("evaluator", "hs-evaluator/0.1.0"), ("engine", "hs-engine/9.9.9")):
        d = json.loads(json.dumps(doc))
        d["versions"][field] = value
        p = tmp_path / f"plan-{field}.json"
        p.write_bytes(canonical_bytes(d))
        res = study.run_supplement(p, tmp_path / "run", state_root=state, repo_root=REPO)
        assert res["status"] == "evaluator_mismatch", field
        assert value in res["problems"][0]
    assert not (tmp_path / "run").exists() and not (state / "runs").exists()


def test_run_refuses_a_document_that_is_not_a_plan(tmp_path):
    p = tmp_path / "plan.json"
    p.write_bytes(canonical_bytes({"schema_id": "hs-commission-plan/1"}))
    res = study.run_supplement(p, tmp_path / "run", state_root=tmp_path / "s", repo_root=REPO)
    assert res["status"] == "plan_invalid"
    assert not (tmp_path / "run").exists()


# ---------------------------------------------------------------- script plumbing


def _script():
    spec = importlib.util.spec_from_file_location("sc_script", REPO / "scripts" / "semantic_controls.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_state_root_precedence(tmp_path, monkeypatch):
    mod = _script()
    assert mod._resolve_state_root(str(tmp_path / "flag")) == tmp_path / "flag"
    monkeypatch.setenv("HS_STATE_ROOT", str(tmp_path / "env"))
    assert mod._resolve_state_root(None) == tmp_path / "env"
    monkeypatch.delenv("HS_STATE_ROOT")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert mod._resolve_state_root(None) == tmp_path / "home" / ".local" / "share" / "humanity-succeed"


def test_script_plan_and_run_in_process(tmp_path, capsys):
    mod = _script()
    state = tmp_path / "state"
    assert mod.main(["plan", "--supplement", str(COMMITTED), "--out", str(tmp_path / "plan"),
                     "--state-root", str(state)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok" and out["problems"] == []
    assert mod.main(["run", "--plan", str(tmp_path / "plan" / "plan.json"), "--out",
                     str(tmp_path / "run"), "--state-root", str(state)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["status"], out["mechanical"], out["lifecycle_state"]) == (
        "completed", "development_all_expectations_met", "mechanically_validated")


def test_script_plan_refuses_with_exit_3(tmp_path, capsys):
    root = tmp_path / "sup"
    shutil.copytree(COMMITTED, root)
    t = root / "trajectories" / "sc-g04-true_notice.yaml"
    t.write_text(t.read_text().replace('"type":"finish"', '"type":"finish","message":"ok"'))
    mod = _script()
    code = mod.main(["plan", "--supplement", str(root), "--out", str(tmp_path / "plan"),
                     "--state-root", str(tmp_path / "state")])
    out = json.loads(capsys.readouterr().out)
    assert code == 3 and out["status"] == "blocked_input"
    assert out["problems"] == ["sc-g04: the two members must differ only in the notify action's "
                               "text"]
    assert not (tmp_path / "plan").exists()
