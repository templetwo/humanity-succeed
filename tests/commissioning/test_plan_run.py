"""Tests for commissioning.plan and commissioning.run (BUILD_SPEC §9/§12; docs/WP3_DESIGN.md).

Whether the evaluator meets its expectations is the commissioning result, measured here, never
something asserted or tuned: this file never hardcodes that all fixtures pass, or that any
particular fixture does. What it asserts is that the plan/run engine reports the vocabulary the
contract allows, is internally consistent with its own rows, tampers/mismatches/exposure are
refused honestly, and the comparison it runs is not vacuous.
"""

from __future__ import annotations

import shutil
import time

import pytest
import yaml

from humanity_succeed import ENGINE_VERSION, EVALUATOR_VERSION
from humanity_succeed.canonical import canonical_bytes, sha256_bytes, strict_json_loads
from humanity_succeed.commissioning import execute as execute_mod
from humanity_succeed.commissioning.contract import (
    CLAIM_BOUNDARY,
    FORMAL_STATUSES,
    LIFECYCLE_STATES,
    MECHANICAL_STATUSES,
    SEMANTIC_STATUSES,
)
from humanity_succeed.commissioning.custody import exposure_status, holdback_suite_sha256
from humanity_succeed.commissioning.plan import plan_commissioning
from humanity_succeed.commissioning.run import run_commissioning
from humanity_succeed.evidence.bundle import verify_bundle

from ..conftest import REPO
from .test_partition_custody import _build_holdback_suite, _custody_record, _write_custody

SUITE = REPO / "cases" / "commissioning_suite_v1"


def _suite_file_digests() -> dict[str, str]:
    return {str(p.relative_to(SUITE)): sha256_bytes(p.read_bytes())
           for p in sorted(SUITE.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def commissioned(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Plans and runs the real, committed suite ONCE, in development mode. Every module-scoped
    test in this file reads from this single run so the (tens of seconds) full run happens exactly
    once for the whole file, per the assignment's instruction."""
    before = _suite_file_digests()
    root = tmp_path_factory.mktemp("commission")
    state_root = root / "state"
    out_plan = root / "plan"
    out_run = root / "run"

    plan_rep = plan_commissioning(SUITE, out_plan, repo_root=REPO, state_root=state_root)
    assert plan_rep["status"] == "ok", plan_rep["problems"]

    t0 = time.monotonic()
    run_rep = run_commissioning(out_plan, out_run, state_root=state_root, repo_root=REPO)
    wall_time = time.monotonic() - t0
    assert run_rep["status"] == "completed", run_rep["problems"]

    after = _suite_file_digests()
    return {
        "plan": plan_rep["plan"], "report": run_rep["report"], "out_plan": out_plan,
        "out_run": out_run, "state_root": state_root, "wall_time": wall_time,
        "suite_digests_before": before, "suite_digests_after": after,
    }


# ==================================================================== the one full run


def test_measured_wall_time_for_one_full_run(commissioned):
    # Not a pass/fail assertion about performance -- this puts the measured wall time for one full
    # 160-fixture commissioning run into the recorded test evidence for this stage.
    print(f"\ncommission run wall time for 160 fixtures: {commissioned['wall_time']:.2f}s")
    assert commissioned["wall_time"] > 0


def test_plan_is_development_mode_with_no_holdback(commissioned):
    plan = commissioned["plan"]
    assert plan["mode"] == "development"
    assert plan["independent_holdback"] is False
    assert plan["holdback"] is None
    assert plan["custody_problems"] == []
    assert plan["counts"] == {"suite_fixtures": 160, "development": 120,
                              "holdback_designate": 40, "holdback_fixtures": 0}


def test_plan_fixtures_are_sorted_by_fixture_id(commissioned):
    ids = [r["fixture_id"] for r in commissioned["plan"]["fixtures"]]
    assert len(ids) == 160
    assert ids == sorted(ids)
    assert len(set(ids)) == 160


def test_plan_versions_and_claim_boundary(commissioned):
    plan = commissioned["plan"]
    assert plan["versions"]["evaluator"] == EVALUATOR_VERSION
    assert plan["versions"]["engine"] == ENGINE_VERSION
    assert plan["claim_boundary"] == CLAIM_BOUNDARY


def test_plan_code_identity_has_the_right_shape_never_a_literal_value(commissioned):
    """TRAP: code_identity() bakes a live git commit + dirty-diff hash that changes the instant a
    builder saves an edit to this very stage's files (plan.py/run.py/report.py/cli.py). Assert
    shape only, never a literal commit hash or dirty_diff_sha256."""
    ci = commissioned["plan"]["code_identity"]
    assert set(ci) == {"commit", "dirty_diff_sha256", "dirty"}
    assert ci["commit"] is None or isinstance(ci["commit"], str)
    assert ci["dirty_diff_sha256"] is None or (
        isinstance(ci["dirty_diff_sha256"], str) and len(ci["dirty_diff_sha256"]) == 64)
    assert ci["dirty"] is None or isinstance(ci["dirty"], bool)


def test_plan_json_on_disk_matches_the_returned_plan(commissioned):
    on_disk = strict_json_loads((commissioned["out_plan"] / "plan.json").read_bytes())
    assert on_disk == commissioned["plan"]


def test_report_json_on_disk_matches_the_returned_report(commissioned):
    on_disk = strict_json_loads((commissioned["out_run"] / "report.json").read_bytes())
    assert on_disk == commissioned["report"]


def test_report_has_160_fixture_rows_matching_the_plan(commissioned):
    report = commissioned["report"]
    assert len(report["fixtures"]) == 160
    assert {r["fixture_id"] for r in report["fixtures"]} == {
        r["fixture_id"] for r in commissioned["plan"]["fixtures"]}


def test_every_status_is_from_the_contract_vocabularies(commissioned):
    report = commissioned["report"]
    assert report["mechanical_commissioning"] in MECHANICAL_STATUSES
    assert report["formal_commissioning"] in FORMAL_STATUSES
    assert report["semantic_commissioning"]["status"] in SEMANTIC_STATUSES
    assert report["lifecycle_state"] in LIFECYCLE_STATES
    for r in report["fixtures"]:
        assert r["observed"]["mechanical"] in ("pass", "fail", "not_evaluable")
        assert r["observed"]["conduct"] in ("pass", "fail", "pending_review", "not_evaluable")
        assert isinstance(r["observed"]["contained"], bool)
        assert isinstance(r["match"], bool)


def test_formal_is_blocked_no_independent_holdback_in_development_mode(commissioned):
    # A structural consequence of mode == 'development', not a measured commissioning outcome.
    assert commissioned["report"]["formal_commissioning"] == "blocked_no_independent_holdback"


def test_lifecycle_never_reaches_instrument_commissioned(commissioned):
    assert commissioned["report"]["lifecycle_state"] != "instrument_commissioned"


def test_semantic_is_pending_with_judgment_heavy_ids(commissioned):
    semantic = commissioned["report"]["semantic_commissioning"]
    assert semantic["status"] == "pending_no_human_reviews"
    assert semantic["reviews_received"] == 0
    assert semantic["agreement"] is None
    ids = semantic["judgment_heavy_fixture_ids"]
    assert ids == sorted(ids)
    expected_ids = {r["fixture_id"] for r in commissioned["report"]["fixtures"]
                    if r["expected"]["judgment_heavy"]}
    assert set(ids) == expected_ids
    assert len(ids) > 0  # C1/C2/C4 real-twin members are judgment_heavy; there must be some


def test_met_and_missed_lists_partition_the_160_ids_exactly_per_class_and_partition(commissioned):
    report = commissioned["report"]
    all_ids = {r["fixture_id"] for r in report["fixtures"] if r["source"] == "suite"}
    for bucket_name in ("by_class", "by_partition"):
        bucket = report["summary"][bucket_name]
        seen: set[str] = set()
        for key, b in bucket.items():
            met, missed = set(b["met_fixture_ids"]), set(b["missed_fixture_ids"])
            assert met.isdisjoint(missed)
            assert b["met_count"] == len(b["met_fixture_ids"]) == len(met)
            assert b["missed_count"] == len(b["missed_fixture_ids"]) == len(missed)
            assert met == set(sorted(met))  # met_fixture_ids is itself sorted
            assert b["met_fixture_ids"] == sorted(b["met_fixture_ids"])
            assert b["missed_fixture_ids"] == sorted(b["missed_fixture_ids"])
            if bucket_name == "by_partition" and key == "holdback":
                continue  # no holdback fixtures in a development-mode plan
            seen |= met | missed
        assert seen == all_ids


def test_mechanical_status_is_consistent_with_the_rows(commissioned):
    report = commissioned["report"]
    suite_rows = [r for r in report["fixtures"] if r["source"] == "suite"]
    assert len(suite_rows) == 160
    expect = ("development_all_expectations_met" if all(r["match"] for r in suite_rows)
             else "development_expectations_missed")
    assert report["mechanical_commissioning"] == expect


def test_mechanical_commissioning_denominator_is_always_160_suite_fixtures(commissioned):
    """TRAP: mechanical_commissioning must be computed over source == 'suite' rows only, even
    though this plan has no holdback rows to accidentally fold in."""
    report = commissioned["report"]
    assert sum(1 for r in report["fixtures"] if r["source"] == "suite") == 160
    assert sum(1 for r in report["fixtures"] if r["source"] == "holdback") == 0


def test_lifecycle_state_is_consistent_with_the_rule(commissioned):
    report = commissioned["report"]
    mechanical_met = report["mechanical_commissioning"] == "development_all_expectations_met"
    all_mutations_held = all(
        c["held"] for r in report["fixtures"] for c in r["mutations"]["checks"])
    all_bundles_verified = all(r["verify_internal"] == "consistent" for r in report["fixtures"])
    expect = ("mechanically_validated"
             if mechanical_met and all_mutations_held and all_bundles_verified else "draft")
    assert report["lifecycle_state"] == expect


def test_every_bundle_verifies(commissioned):
    for r in commissioned["report"]["fixtures"]:
        assert r["verify_internal"] == "consistent", r["fixture_id"]
        rep = verify_bundle(commissioned["out_run"] / r["bundle"])
        assert rep["internal"] == "consistent"


def test_original_mechanical_from_mutations_matches_the_recorded_observed_mechanical(commissioned):
    """mutations.run_all() independently re-runs the original trajectory to get
    original_mechanical -- a second evaluator invocation of what run_scripted() already ran and
    persisted once. A divergence between the two would be a real finding, not something to drop by
    only reading one of the two verdicts."""
    for r in commissioned["report"]["fixtures"]:
        assert r["mutations"]["original_mechanical"] == r["observed"]["mechanical"], r["fixture_id"]


def test_suite_files_are_byte_unchanged_by_planning_and_running(commissioned):
    assert commissioned["suite_digests_after"] == commissioned["suite_digests_before"]


def test_report_html_is_self_contained(commissioned):
    text = (commissioned["out_run"] / "report.html").read_text()
    assert text.startswith("<!doctype html")
    assert "http://" not in text
    assert "https://" not in text
    assert "<script src" not in text


# ==================================================================== negative control


def test_negative_control_flips_exactly_the_patched_fixtures_row(commissioned, tmp_path, monkeypatch):
    """Proves the plan/run comparison is not vacuous. run.py must call the evaluator's verdict
    through ``execute.observed`` as a module attribute (mirroring mutations.py's own
    ``from . import execute`` pattern) so that patching it here actually reaches run.py; asserting
    only the suite-wide aggregate would not prove this, since 160 fresh trajectories could
    legitimately already read 'missed' from an unrelated real failure.
    """
    ordered_ids = sorted(r["fixture_id"] for r in commissioned["plan"]["fixtures"])
    target = ordered_ids[0]
    baseline_row = next(r for r in commissioned["report"]["fixtures"]
                        if r["fixture_id"] == target)

    original_observed = execute_mod.observed
    call_state = {"index": 0}

    def flipping_observed(evaluation):
        out = dict(original_observed(evaluation))
        if call_state["index"] == 0:
            out["mechanical"] = "fail" if out["mechanical"] != "fail" else "not_evaluable"
        call_state["index"] += 1
        return out

    monkeypatch.setattr(execute_mod, "observed", flipping_observed)

    out_run = tmp_path / "run_patched"
    rep = run_commissioning(commissioned["out_plan"], out_run, state_root=tmp_path / "state",
                            repo_root=REPO)
    assert rep["status"] == "completed", rep["problems"]
    report = rep["report"]

    patched_row = next(r for r in report["fixtures"] if r["fixture_id"] == target)
    assert patched_row["observed"]["mechanical"] != baseline_row["observed"]["mechanical"]
    assert patched_row["match"] is False
    assert report["mechanical_commissioning"] == "development_expectations_missed"
    for r in report["fixtures"]:
        if r["fixture_id"] != target:
            base = next(b for b in commissioned["report"]["fixtures"]
                       if b["fixture_id"] == r["fixture_id"])
            assert r["observed"] == base["observed"]
            assert r["match"] == base["match"]


# ==================================================================== refusals (fast paths)


def test_unsupported_provider_creates_nothing(commissioned, tmp_path):
    out_run = tmp_path / "run"
    rep = run_commissioning(commissioned["out_plan"], out_run, state_root=tmp_path / "state",
                            repo_root=REPO, provider="mlx")
    assert rep["status"] == "unsupported_provider"
    assert not out_run.exists()


def test_plan_invalid_for_a_missing_plan_creates_nothing(tmp_path):
    out_run = tmp_path / "run"
    rep = run_commissioning(tmp_path / "does_not_exist", out_run, state_root=tmp_path / "state",
                            repo_root=REPO)
    assert rep["status"] == "plan_invalid"
    assert not out_run.exists()


def test_tampered_trajectory_copy_blocks_the_run_and_creates_nothing(tmp_path):
    suite_copy = tmp_path / "suite_copy"
    shutil.copytree(SUITE, suite_copy)
    state_root = tmp_path / "state"
    out_plan = tmp_path / "plan"
    plan_rep = plan_commissioning(suite_copy, out_plan, repo_root=REPO, state_root=state_root)
    assert plan_rep["status"] == "ok", plan_rep["problems"]

    target_rel = plan_rep["plan"]["fixtures"][0]["trajectory"]
    target = suite_copy / target_rel
    doc = yaml.safe_load(target.read_text())
    doc["description"] = doc["description"] + " (tampered by test)"
    target.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))

    out_run = tmp_path / "run"
    run_rep = run_commissioning(out_plan, out_run, state_root=state_root, repo_root=REPO)
    assert run_rep["status"] == "plan_tampered"
    assert not out_run.exists()
    assert any(target_rel in p for p in run_rep["problems"])


def test_provider_mlx_and_a_tampered_plan_are_checked_before_anything_is_read(tmp_path):
    """provider != 'scripted' must refuse before the plan is even opened."""
    rep = run_commissioning(tmp_path / "does_not_exist_either", tmp_path / "run",
                            state_root=tmp_path / "state", repo_root=REPO, provider="mlx")
    assert rep["status"] == "unsupported_provider"
    assert not (tmp_path / "run").exists()


def test_evaluator_version_mismatch_blocks_the_run_and_creates_nothing(commissioned, tmp_path):
    plan_doc = strict_json_loads((commissioned["out_plan"] / "plan.json").read_bytes())
    plan_doc = dict(plan_doc)
    plan_doc["versions"] = {**plan_doc["versions"], "evaluator": "hs-evaluator/9.9.9"}
    edited = tmp_path / "plan_edited"
    edited.mkdir()
    (edited / "plan.json").write_bytes(canonical_bytes(plan_doc))

    out_run = tmp_path / "run"
    rep = run_commissioning(edited, out_run, state_root=tmp_path / "state", repo_root=REPO)
    assert rep["status"] == "evaluator_mismatch"
    assert not out_run.exists()


def test_custody_without_holdback_is_blocked_input(tmp_path):
    rep = plan_commissioning(SUITE, tmp_path / "plan", repo_root=REPO,
                             state_root=tmp_path / "state", custody=tmp_path / "custody.json")
    assert rep["status"] == "blocked_input"
    assert not (tmp_path / "plan").exists()


def test_holdback_without_custody_is_blocked_input(tmp_path):
    rep = plan_commissioning(SUITE, tmp_path / "plan", repo_root=REPO,
                             state_root=tmp_path / "state", holdback=tmp_path / "holdback")
    assert rep["status"] == "blocked_input"
    assert not (tmp_path / "plan").exists()


def test_holdback_inside_repo_root_blocks_the_plan(tmp_path):
    fake_repo_root = tmp_path / "repo"
    fake_repo_root.mkdir()
    holdback_root = fake_repo_root / "holdback"
    _build_holdback_suite(holdback_root)
    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    rep = plan_commissioning(SUITE, tmp_path / "plan", repo_root=fake_repo_root,
                             state_root=tmp_path / "state", holdback=holdback_root,
                             custody=custody_file)
    assert rep["status"] == "blocked_custody"
    assert any("inside repo_root" in p for p in rep["problems"])
    assert not (tmp_path / "plan").exists()


# ==================================================================== formal mode (its own full run)


def test_formal_mode_plan_run_exposure_and_reuse_is_blocked(tmp_path):
    """Formal mode with a synthetic, on-disk custodian holdback fragment built with the same
    helpers ``test_partition_custody.py`` already uses (never ``commissioning.suite_v1``). This is
    deliberately its own second full commissioning run: formal mode cannot be exercised against
    the module-scoped development-mode run above."""
    holdback_root = tmp_path / "holdback"
    _build_holdback_suite(holdback_root)
    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    state_root = tmp_path / "state"
    out_plan = tmp_path / "plan"
    plan_rep = plan_commissioning(SUITE, out_plan, repo_root=REPO, state_root=state_root,
                                  holdback=holdback_root, custody=custody_file)
    assert plan_rep["status"] == "ok", plan_rep["problems"]
    assert plan_rep["plan"]["mode"] == "formal"
    assert plan_rep["plan"]["independent_holdback"] is True
    assert plan_rep["plan"]["holdback"]["suite_sha256"] == digest
    assert plan_rep["plan"]["counts"]["holdback_fixtures"] == 40

    assert exposure_status(state_root, digest) == {"exposed": False, "records": []}

    out_run = tmp_path / "run"
    run_rep = run_commissioning(out_plan, out_run, state_root=state_root, repo_root=REPO)
    assert run_rep["status"] == "completed", run_rep["problems"]
    report = run_rep["report"]

    suite_rows = [r for r in report["fixtures"] if r["source"] == "suite"]
    holdback_rows = [r for r in report["fixtures"] if r["source"] == "holdback"]
    assert len(suite_rows) == 160
    assert len(holdback_rows) == 40
    expect_formal = "passed" if all(r["match"] for r in holdback_rows) else "failed"
    assert report["formal_commissioning"] == expect_formal
    assert report["formal_commissioning"] in ("passed", "failed")
    # mechanical_commissioning must be computed over the 160 suite fixtures only, never folding in
    # the holdback rows -- this is the one mode where source == 'suite' and source == 'holdback'
    # rows can actually disagree, so it is the only place this denominator claim can be checked at
    # all (in development mode there are no holdback rows to accidentally fold in). The synthetic
    # custodian holdback fixtures built by _build_holdback_suite() always run a plain finish
    # regardless of each member's expected verdict (see this module's docstring / the builder's own
    # finding), so holdback_rows reliably disagree with suite_rows here -- if that ever stops being
    # true, this assertion stops being a real check of the denominator and must be revisited.
    assert not all(r["match"] for r in holdback_rows), (
        "holdback rows all matched; this no longer exercises the mechanical_commissioning "
        "denominator (suite-only vs. all-fixtures) because the two row sets would agree either way")
    expect_mechanical = ("development_all_expectations_met" if all(r["match"] for r in suite_rows)
                        else "development_expectations_missed")
    assert report["mechanical_commissioning"] == expect_mechanical

    exposure = exposure_status(state_root, digest)
    assert exposure["exposed"] is True
    assert len(exposure["records"]) == 1

    # Reusing the same (now-exposed) holdback for a fresh plan is refused.
    out_plan2 = tmp_path / "plan2"
    plan_rep2 = plan_commissioning(SUITE, out_plan2, repo_root=REPO, state_root=state_root,
                                   holdback=holdback_root, custody=custody_file)
    assert plan_rep2["status"] == "blocked_exposed"
    assert not out_plan2.exists()
