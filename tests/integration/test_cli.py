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
    ("commission", "run", "--plan", "p"),
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
