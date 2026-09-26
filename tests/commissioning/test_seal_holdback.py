"""Tests for scripts/seal_holdback.py (docs/HOLDBACK_CUSTODY.md; BUILD_SPEC §5.2, §9).

Runs the script as a real subprocess -- the way a human custodian actually invokes it -- against a
synthetic holdback built with ``test_partition_custody``'s own helpers, never with
``commissioning.suite_v1``. Never runs the evaluator: this only checks that the script validates,
hashes and seals a holdback correctly, and refuses exactly what it must refuse.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid

import pytest

from humanity_succeed.commissioning.contract import CustodyRecord
from humanity_succeed.commissioning.custody import load_custody

from ..conftest import REPO
from .test_partition_custody import _build_holdback_suite

SCRIPT = REPO / "scripts" / "seal_holdback.py"
EXIT_OK, EXIT_INVALID, EXIT_PRECONDITION = 0, 2, 3


def run_seal(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=REPO, env=os.environ.copy(),
    )


def _envelope(proc: subprocess.CompletedProcess) -> dict:
    assert proc.stdout.strip(), f"no stdout from seal_holdback.py; stderr:\n{proc.stderr}"
    return json.loads(proc.stdout)


def test_seals_a_valid_synthetic_holdback(tmp_path):
    holdback = tmp_path / "holdback"
    _build_holdback_suite(holdback)
    out = tmp_path / "custody.json"

    proc = run_seal(
        "--holdback", str(holdback),
        "--custodian", "Test Custodian (not the builder seat)",
        "--statement", "Sealed in an isolated pytest tmp_path the builder's tooling never scans.",
        "--out", str(out),
    )
    env = _envelope(proc)
    assert proc.returncode == EXIT_OK, proc.stderr
    assert env["status"] == "ok"
    assert out.is_file()

    # The written file validates strictly as a CustodyRecord -- not just "some JSON".
    record = CustodyRecord.model_validate(json.loads(out.read_text()))
    assert record.schema_id == "hs-holdback-custody/1"
    assert record.custodian == "Test Custodian (not the builder seat)"
    assert record.holdback_suite_sha256 == env["result"]["holdback_suite_sha256"]
    # sealed_at_utc legitimately uses the real wall clock (a script, not the instrument): assert
    # only its shape, never a literal value.
    assert isinstance(record.sealed_at_utc, str) and record.sealed_at_utc.endswith("Z")

    result = load_custody(out, holdback, repo_root=REPO, state_root=tmp_path / "state")
    assert result["problems"] == []
    assert result["custody_valid"] is True
    assert result["independent_holdback"] is True
    assert result["holdback_suite_sha256"] == record.holdback_suite_sha256


def test_refuses_to_overwrite_existing_out_file(tmp_path):
    holdback = tmp_path / "holdback"
    _build_holdback_suite(holdback)
    out = tmp_path / "custody.json"
    out.write_text("not a custody record")

    proc = run_seal(
        "--holdback", str(holdback), "--custodian", "Someone",
        "--statement", "kept it out of reach", "--out", str(out),
    )
    env = _envelope(proc)
    assert proc.returncode == EXIT_INVALID
    assert env["status"] == "invalid"
    assert env["error"]["code"] == "refuse_overwrite"
    assert out.read_text() == "not a custody record"  # the existing file was never touched


def test_refuses_a_holdback_inside_the_repository(tmp_path):
    # This one genuinely needs bytes physically inside the live worktree, since the script's own
    # containment check resolves real paths against this repository's actual root -- not a
    # tmp_path stand-in. Built and removed in one try/finally so nothing survives a failed
    # assertion; the directory name is unique per run so concurrent sessions in this shared
    # worktree cannot collide with it.
    holdback = REPO / f".tmp_seal_holdback_test_{uuid.uuid4().hex}"
    assert not holdback.exists()
    try:
        _build_holdback_suite(holdback)
        out = tmp_path / "custody.json"

        proc = run_seal(
            "--holdback", str(holdback), "--custodian", "Someone",
            "--statement", "kept it out of reach", "--out", str(out),
        )
        env = _envelope(proc)
        assert proc.returncode == EXIT_PRECONDITION
        assert env["status"] == "blocked"
        assert env["error"]["code"] == "custody_shape_invalid"
        assert "inside this repository" in env["error"]["message"]
        assert not out.exists()  # sealing never happened
    finally:
        shutil.rmtree(holdback, ignore_errors=True)
    assert not holdback.exists()


def test_refuses_a_holdback_inside_the_state_root(tmp_path):
    # docs/HOLDBACK_CUSTODY.md promises this script refuses a holdback inside the hs state root,
    # the same as load_custody does later at plan time -- not only a holdback inside the
    # repository. ``--state-root`` makes the check explicit and reproducible here rather than
    # relying on whatever $HS_STATE_ROOT happens to be set to in the test environment.
    state_root = tmp_path / "state"
    holdback = state_root / "holdback"
    _build_holdback_suite(holdback)
    out = tmp_path / "custody.json"

    proc = run_seal(
        "--holdback", str(holdback), "--custodian", "Someone",
        "--statement", "kept it out of reach", "--out", str(out),
        "--state-root", str(state_root),
    )
    env = _envelope(proc)
    assert proc.returncode == EXIT_PRECONDITION
    assert env["status"] == "blocked"
    assert env["error"]["code"] == "custody_shape_invalid"
    assert "state root" in env["error"]["message"]
    assert not out.exists()


def test_state_root_flag_defaults_to_hs_state_root_env_var(tmp_path):
    # No --state-root given: the script must fall back to $HS_STATE_ROOT (matching cli.py's own
    # state_root() precedence), not silently skip the check.
    state_root = tmp_path / "state-from-env"
    holdback = state_root / "holdback"
    _build_holdback_suite(holdback)
    out = tmp_path / "custody.json"

    env_vars = os.environ.copy()
    env_vars["HS_STATE_ROOT"] = str(state_root)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--holdback", str(holdback), "--custodian", "Someone",
         "--statement", "kept it out of reach", "--out", str(out)],
        capture_output=True, text=True, cwd=REPO, env=env_vars,
    )
    env = _envelope(proc)
    assert proc.returncode == EXIT_PRECONDITION
    assert env["status"] == "blocked"
    assert env["error"]["code"] == "custody_shape_invalid"
    assert "state root" in env["error"]["message"]
    assert not out.exists()


@pytest.mark.parametrize("authorship,split,needle", [
    ("builder_constructed", "commissioning_holdback", "authorship"),
    ("custodian_supplied", "commissioning_dev", "split"),
])
def test_refuses_wrong_authorship_or_split(tmp_path, authorship, split, needle):
    holdback = tmp_path / "holdback"
    _build_holdback_suite(holdback, authorship=authorship, split=split)
    out = tmp_path / "custody.json"

    proc = run_seal(
        "--holdback", str(holdback), "--custodian", "Someone",
        "--statement", "kept it out of reach", "--out", str(out),
    )
    env = _envelope(proc)
    assert proc.returncode == EXIT_PRECONDITION
    assert env["status"] == "blocked"
    assert env["error"]["code"] == "custody_shape_invalid"
    assert needle in env["error"]["message"]
    assert not out.exists()


def test_refuses_a_structurally_invalid_fragment(tmp_path):
    holdback = tmp_path / "holdback"
    manifest = _build_holdback_suite(holdback)
    # Delete one referenced trajectory file: contract.suite_problems(fragment=True) now reports it
    # missing, without needing to hand-build a broken manifest.
    victim = holdback / manifest.groups[0].members[0].trajectory
    assert victim.is_file()
    victim.unlink()
    out = tmp_path / "custody.json"

    proc = run_seal(
        "--holdback", str(holdback), "--custodian", "Someone",
        "--statement", "kept it out of reach", "--out", str(out),
    )
    env = _envelope(proc)
    assert proc.returncode == EXIT_PRECONDITION
    assert env["status"] == "blocked"
    assert env["error"]["code"] == "custody_shape_invalid"
    assert "missing" in env["error"]["message"]
    assert not out.exists()


def test_seal_script_never_prints_fixture_task_text(tmp_path):
    """The script's own promise (docs/HOLDBACK_CUSTODY.md): it reports messages and hashes, never
    fixture contents. This is a smoke check, not a proof -- it only confirms the one distinctive
    string this suite's synthetic case bodies always carry never reaches stdout."""
    holdback = tmp_path / "holdback"
    _build_holdback_suite(holdback)
    out = tmp_path / "custody.json"

    proc = run_seal(
        "--holdback", str(holdback), "--custodian", "Someone",
        "--statement", "kept it out of reach", "--out", str(out),
    )
    assert proc.returncode == EXIT_OK, proc.stderr
    assert "Simulated holdback custody test fixture" not in proc.stdout
