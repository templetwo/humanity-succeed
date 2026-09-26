"""CLI envelopes and exit codes (BUILD_SPEC §12). All state under the per-test temp root."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ..conftest import DEV_CASES, EXAMPLES, REPO, TRAJ


def hs(*args, cwd=REPO):
    r = subprocess.run([sys.executable, "-m", "humanity_succeed.cli", *map(str, args)],
                       capture_output=True, text=True, cwd=cwd, env=os.environ.copy())
    return r.returncode, json.loads(r.stdout) if r.stdout.strip() else None, r.stderr


def test_doctor_makes_no_model_calls():
    code, env, _ = hs("doctor", "--json")
    assert code == 0 and env["status"] == "ok"
    assert env["result"]["model_calls_made"] == 0
    assert env["result"]["mlx_imported_by_core"] is False


def test_doctor_models_is_unsupported_at_checkpoint(tmp_path):
    code, env, _ = hs("doctor", "--models", tmp_path)
    assert code == 4 and env["error"]["code"] == "unsupported_at_checkpoint"


@pytest.mark.parametrize("args", [
    ("run", "execute", "--plan", "p", "--approval", "a", "--out", "o"),
    ("training", "execute", "--plan", "p", "--approval", "a"),
    ("study", "plan", "--config", "c", "--out", "o"),
    ("review", "export", "b"),
    ("analyze",),
    ("acceptance", "--json"),
])
def test_later_work_packages_answer_unsupported_and_do_nothing(tmp_path, args):
    code, env, _ = hs(*args, cwd=tmp_path)
    assert code == 4 and env["status"] == "unsupported"
    assert list(tmp_path.iterdir()) == []


def test_validate_audit_lint():
    code, env, _ = hs("cases", "validate", EXAMPLES, DEV_CASES)
    assert code == 0 and env["status"] == "ok"
    code, env, _ = hs("cases", "audit-splits", EXAMPLES, DEV_CASES)
    assert code == 0 and env["result"]["status"] == "ok"
    code, env, _ = hs("cases", "lint-leaks", "--cases", EXAMPLES, DEV_CASES,
                      "--principles", REPO / "configs" / "principles.draft.md")
    assert code == 0 and "flag_count" in env["result"]


def test_validate_invalid_exit_2(tmp_path):
    (tmp_path / "bad.yaml").write_text("a: 1\na: 2\n")
    code, env, _ = hs("cases", "validate", tmp_path)
    assert code == 2 and env["status"] == "invalid"


def test_run_verify_replay_roundtrip_and_refuse_overwrite(tmp_path):
    out = tmp_path / "bundle"
    code, env, _ = hs("run", "scripted", "--case", EXAMPLES / "correction.yaml",
                      "--trajectory", TRAJ / "t-correction-claim-warm.yaml", "--out", out)
    assert code == 0 and env["result"]["mechanical_verdict"] == "fail"
    assert Path(env["result"]["store"]).is_relative_to(tmp_path)
    assert any("not a behavioral result" in x for x in env["limitations"])
    code, env, _ = hs("evidence", "verify", out)
    assert code == 0 and env["result"]["anchor"] == "external_anchor_absent"
    code, env, _ = hs("evidence", "anchor", out, "--out", tmp_path / "anchor.json")
    assert code == 0
    code, env, _ = hs("evidence", "verify", out, "--anchor", tmp_path / "anchor.json")
    assert code == 0 and env["result"]["anchor"] == "verified_against_anchor"
    code, env, _ = hs("evidence", "replay", out, "--out", tmp_path / "rep")
    assert code == 0 and env["result"]["replay"]["status"] == "reproduced"
    code, env, _ = hs("run", "scripted", "--case", EXAMPLES / "correction.yaml",
                      "--demo", "correction_effect", "--out", out)
    assert code == 2 and env["error"]["code"] == "refuse_overwrite"


def test_corrupt_bundle_exit_5(tmp_path):
    out = tmp_path / "bundle"
    hs("run", "scripted", "--case", EXAMPLES / "correction.yaml", "--demo",
       "correction_effect", "--out", out)
    (out / "extra.txt").write_text("x")
    code, env, _ = hs("evidence", "verify", out)
    assert code == 5 and env["status"] == "failed"


def test_demo_end_to_end(tmp_path):
    code, env, _ = hs("demo", "--repo", REPO, "--out", tmp_path / "demo",
                      "--state-root", tmp_path / "state")
    assert code == 0 and env["result"]["all_assertions_hold"] is True
    assert (tmp_path / "demo" / "comparison.html").is_file()


def _traj(tmp_path, **over):
    import yaml
    doc = {"schema_id": "hs-scripted-trajectory/1", "trajectory_id": "t-x",
           "case_id": "commissioning-correction-001", "provenance": {}, "description": "d",
           "raw_outputs": ['{"action":{"type":"finish","summary":"x","delivered_resource_ids":[]}}']}
    doc.update(over)
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


@pytest.mark.parametrize("over", [
    {"trajectory_id": "../../../escaped"},
    {"trajectory_id": "/tmp/abs"},
    {"trajectory_id": 7},
    {"case_id": ["x"]},
    {"description": None},
    {"raw_outputs": []},
    {"extra": 1},
])
def test_malformed_trajectory_is_invalid_input(tmp_path, over):
    """Red-team #12/#13: trajectory IDs reached a filesystem path; types were unchecked."""
    code, env, err = hs("run", "scripted", "--case", EXAMPLES / "correction.yaml",
                        "--trajectory", _traj(tmp_path, **over), "--out", tmp_path / "b",
                        "--state-root", tmp_path / "state")
    assert code == 2 and env["error"]["code"] == "invalid_input", err
    assert not (tmp_path / "b").exists()
    runs = tmp_path / "state" / "runs"
    assert not runs.exists() or not any(runs.iterdir())


def test_case_trajectory_mismatch_is_invalid_input(tmp_path):
    """Red-team #14: a mismatch crashed with a traceback."""
    code, env, err = hs("run", "scripted", "--case", EXAMPLES / "feature-preserve.yaml",
                        "--trajectory", TRAJ / "t-correction-actual.yaml", "--out", tmp_path / "b")
    assert code == 2 and env["error"]["code"] == "invalid_input" and "Traceback" not in err


def test_store_name_never_uses_trajectory_id(tmp_path):
    code, env, _ = hs("run", "scripted", "--case", EXAMPLES / "correction.yaml", "--trajectory",
                      TRAJ / "t-correction-actual.yaml", "--out", tmp_path / "b",
                      "--state-root", tmp_path / "state")
    assert code == 0
    assert Path(env["result"]["store"]).parent == tmp_path / "state" / "runs"
    assert "t-correction-actual" not in Path(env["result"]["store"]).name


def test_replay_into_bundle_is_invalid_input(tmp_path):
    out = tmp_path / "bundle"
    hs("run", "scripted", "--case", EXAMPLES / "correction.yaml", "--demo", "correction_effect",
       "--out", out)
    code, env, _ = hs("evidence", "replay", out, "--out", out / "r")
    assert code == 2 and not (out / "r").exists()


def test_unusable_state_root_is_a_resource_failure(tmp_path):
    """Red-team round 2 (#14): an OSError from the state root escaped as a traceback."""
    blocker = tmp_path / "state"
    blocker.write_text("not a directory")
    code, env, err = hs("run", "scripted", "--case", EXAMPLES / "correction.yaml", "--demo",
                        "correction_effect", "--out", tmp_path / "b", "--state-root", blocker)
    assert code == 6 and env["error"]["code"] == "resource_failure" and "Traceback" not in err


def test_directory_as_case_is_invalid_input(tmp_path):
    (tmp_path / "c.yaml").mkdir()
    code, env, err = hs("run", "scripted", "--case", tmp_path / "c.yaml", "--demo", "x",
                        "--out", tmp_path / "b")
    assert code == 2 and "Traceback" not in err
