"""CLI envelopes and exit codes for ``hs commission plan`` / ``hs commission run`` (BUILD_SPEC
§12; docs/WP3_DESIGN.md 'Commands'). Reuses ``test_cli.py``'s real-subprocess ``hs()`` helper --
these commands are exercised as a real subprocess here, never through ``cli.main()`` in-process,
and every call passes an explicit ``--state-root`` under ``tmp_path`` so no test can read or write
the developer's real ``~/.local/share/humanity-succeed``.
"""

from __future__ import annotations

import json

import pytest
import yaml

from humanity_succeed.canonical import canonical_bytes, strict_json_loads

from ..commissioning.test_partition_custody import _build_holdback_suite, _custody_record, _write_custody
from ..conftest import REPO
from .test_cli import hs

SUITE = REPO / "cases" / "commissioning_suite_v1"


@pytest.fixture(scope="module")
def commissioned_cli(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """One real ``hs commission plan`` + ``hs commission run`` subprocess pair, in development
    mode. Every test in this module that only needs to read an already-completed run reuses this,
    per the assignment's instruction to keep the (tens-of-seconds) full run to a minimum."""
    root = tmp_path_factory.mktemp("cli_commission")
    state_root = root / "state"
    out_plan = root / "plan"
    out_run = root / "run"

    code, plan_env, err = hs("commission", "plan", "--suite", SUITE, "--out", out_plan,
                             "--state-root", state_root)
    assert code == 0 and plan_env["status"] == "ok", (code, plan_env, err)

    code, run_env, err = hs("commission", "run", "--plan", out_plan, "--out", out_run,
                            "--state-root", state_root)
    assert code == 0 and run_env["status"] == "ok", (code, run_env, err)

    return {"state_root": state_root, "out_plan": out_plan, "out_run": out_run,
           "plan_env": plan_env, "run_env": run_env}


# ==================================================================== plan: ok


def test_commission_plan_ok_envelope(commissioned_cli):
    env = commissioned_cli["plan_env"]
    assert env["status"] == "ok"
    assert env["result"]["mode"] == "development"
    assert env["result"]["counts"] == {"suite_fixtures": 160, "development": 120,
                                       "holdback_designate": 40, "holdback_fixtures": 0}
    assert env["artifacts"] == [str(commissioned_cli["out_plan"])]
    assert any("scripted instrument" in x for x in env["limitations"])
    assert (commissioned_cli["out_plan"] / "plan.json").is_file()


def test_commission_plan_refuses_to_overwrite_existing_out(commissioned_cli):
    code, env, _ = hs("commission", "plan", "--suite", SUITE, "--out",
                      commissioned_cli["out_plan"], "--state-root", commissioned_cli["state_root"])
    assert code == 2 and env["status"] == "invalid"
    assert env["error"]["code"] == "refuse_overwrite"


# ==================================================================== run: ok


def test_commission_run_ok_envelope(commissioned_cli):
    env = commissioned_cli["run_env"]
    assert env["status"] == "ok"
    result = env["result"]
    assert result["schema_id"] == "hs-commission-report/1"
    assert result["formal_commissioning"] == "blocked_no_independent_holdback"
    assert result["lifecycle_state"] != "instrument_commissioned"
    assert len(result["fixtures"]) == 160
    assert env["artifacts"] == [str(commissioned_cli["out_run"])]
    assert any("scripted instrument" in x for x in env["limitations"])
    assert any("population error bound" in x for x in env["limitations"])
    assert (commissioned_cli["out_run"] / "report.json").is_file()
    assert (commissioned_cli["out_run"] / "report.html").is_file()


def test_commission_run_refuses_to_overwrite_existing_out(commissioned_cli):
    code, env, _ = hs("commission", "run", "--plan", commissioned_cli["out_plan"], "--out",
                      commissioned_cli["out_run"], "--state-root", commissioned_cli["state_root"])
    assert code == 2 and env["status"] == "invalid"
    assert env["error"]["code"] == "refuse_overwrite"


# ==================================================================== plan: blocked_input


def test_commission_plan_missing_suite_is_blocked_input(tmp_path):
    code, env, _ = hs("commission", "plan", "--suite", tmp_path / "does_not_exist", "--out",
                      tmp_path / "plan", "--state-root", tmp_path / "state")
    assert code == 2 and env["status"] == "invalid"
    assert env["error"]["code"] == "blocked_input"
    assert not (tmp_path / "plan").exists()


def test_commission_plan_holdback_without_custody_is_blocked_input(tmp_path):
    code, env, _ = hs("commission", "plan", "--suite", SUITE, "--out", tmp_path / "plan",
                      "--holdback", tmp_path / "holdback", "--state-root", tmp_path / "state")
    assert code == 2 and env["status"] == "invalid"
    assert not (tmp_path / "plan").exists()


def test_commission_plan_custody_without_holdback_is_blocked_input(tmp_path):
    code, env, _ = hs("commission", "plan", "--suite", SUITE, "--out", tmp_path / "plan",
                      "--custody", tmp_path / "custody.json", "--state-root", tmp_path / "state")
    assert code == 2 and env["status"] == "invalid"
    assert not (tmp_path / "plan").exists()


# ==================================================================== plan: blocked_custody


def test_commission_plan_invalid_custody_record_is_blocked_custody(tmp_path):
    """Exercises the same blocked_custody CLI branch as an exposed holdback does, but through an
    invalid CustodyRecord instead -- entirely under tmp_path, never inside the real checkout (the
    'inside repo_root' refusal itself is already covered directly against a fake repo_root in
    tests/commissioning/test_plan_run.py and tests/commissioning/test_partition_custody.py)."""
    holdback_root = tmp_path / "holdback"
    _build_holdback_suite(holdback_root)
    custody_file = tmp_path / "custody.json"
    # Missing required fields (statement, sealed_at_utc): fails CustodyRecord's strict schema,
    # as test_partition_custody.py's own test_invalid_custody_record_is_reported does.
    custody_file.write_text(json.dumps({
        "schema_id": "hs-holdback-custody/1",
        "custodian": "Someone",
        "holdback_suite_sha256": "0" * 64,
    }))

    code, env, _ = hs("commission", "plan", "--suite", SUITE, "--out", tmp_path / "plan",
                      "--holdback", holdback_root, "--custody", custody_file,
                      "--state-root", tmp_path / "state")
    assert code == 3 and env["status"] == "blocked"
    assert env["error"]["code"] == "blocked_custody"
    assert not (tmp_path / "plan").exists()


# ==================================================================== run: unsupported_provider


def test_commission_run_unsupported_provider_creates_nothing(commissioned_cli, tmp_path):
    out_run = tmp_path / "run"
    code, env, _ = hs("commission", "run", "--plan", commissioned_cli["out_plan"], "--provider",
                      "mlx", "--out", out_run, "--state-root", tmp_path / "state")
    assert code == 4 and env["status"] == "unsupported"
    assert env["error"]["code"] == "unsupported_provider"
    assert not out_run.exists()


# ==================================================================== run: plan_invalid


def test_commission_run_missing_plan_is_plan_invalid(tmp_path):
    out_run = tmp_path / "run"
    code, env, _ = hs("commission", "run", "--plan", tmp_path / "does_not_exist", "--out",
                      out_run, "--state-root", tmp_path / "state")
    assert code == 2 and env["status"] == "invalid"
    assert env["error"]["code"] == "plan_invalid"
    assert not out_run.exists()


# ==================================================================== run: plan_tampered


def test_commission_run_tampered_trajectory_is_plan_tampered(tmp_path):
    import shutil

    suite_copy = tmp_path / "suite_copy"
    shutil.copytree(SUITE, suite_copy)
    state_root = tmp_path / "state"
    out_plan = tmp_path / "plan"
    code, plan_env, _ = hs("commission", "plan", "--suite", suite_copy, "--out", out_plan,
                           "--state-root", state_root)
    assert code == 0 and plan_env["status"] == "ok"

    target_rel = plan_env["result"]["fixtures"][0]["trajectory"]
    target = suite_copy / target_rel
    doc = yaml.safe_load(target.read_text())
    doc["description"] = doc["description"] + " (tampered by CLI test)"
    target.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))

    out_run = tmp_path / "run"
    code, env, _ = hs("commission", "run", "--plan", out_plan, "--out", out_run,
                      "--state-root", state_root)
    assert code == 5 and env["status"] == "failed"
    assert env["error"]["code"] == "plan_tampered"
    assert not out_run.exists()


# ==================================================================== run: evaluator_mismatch


def test_commission_run_evaluator_mismatch_is_blocked(commissioned_cli, tmp_path):
    plan_doc = strict_json_loads((commissioned_cli["out_plan"] / "plan.json").read_bytes())
    plan_doc = dict(plan_doc)
    plan_doc["versions"] = {**plan_doc["versions"], "evaluator": "hs-evaluator/9.9.9"}
    edited = tmp_path / "plan_edited"
    edited.mkdir()
    (edited / "plan.json").write_bytes(canonical_bytes(plan_doc))

    out_run = tmp_path / "run"
    code, env, _ = hs("commission", "run", "--plan", edited, "--out", out_run,
                      "--state-root", tmp_path / "state")
    assert code == 3 and env["status"] == "blocked"
    assert env["error"]["code"] == "evaluator_mismatch"
    assert not out_run.exists()


# ==================================================================== formal mode (its own full run)


def test_commission_plan_and_run_formal_mode_then_reuse_is_blocked_exposed(tmp_path):
    """Its own full 160+40-fixture commissioning run through the real CLI, in formal mode, with a
    synthetic on-disk custodian holdback built the same way test_partition_custody.py does."""
    holdback_root = tmp_path / "holdback"
    _build_holdback_suite(holdback_root)
    from humanity_succeed.commissioning.custody import holdback_suite_sha256

    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    state_root = tmp_path / "state"
    out_plan = tmp_path / "plan"
    code, plan_env, _ = hs("commission", "plan", "--suite", SUITE, "--out", out_plan,
                           "--holdback", holdback_root, "--custody", custody_file,
                           "--state-root", state_root)
    assert code == 0 and plan_env["status"] == "ok"
    assert plan_env["result"]["mode"] == "formal"
    assert plan_env["result"]["independent_holdback"] is True

    out_run = tmp_path / "run"
    code, run_env, _ = hs("commission", "run", "--plan", out_plan, "--out", out_run,
                          "--state-root", state_root)
    assert code == 0 and run_env["status"] == "ok"
    assert run_env["result"]["formal_commissioning"] in ("passed", "failed")

    out_plan2 = tmp_path / "plan2"
    code, env2, _ = hs("commission", "plan", "--suite", SUITE, "--out", out_plan2,
                       "--holdback", holdback_root, "--custody", custody_file,
                       "--state-root", state_root)
    assert code == 3 and env2["status"] == "blocked"
    assert env2["error"]["code"] == "blocked_exposed"
    assert not out_plan2.exists()
