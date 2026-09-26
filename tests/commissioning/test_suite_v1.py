"""The committed WP3 suite v1 (lead-authored): reproducible from the generators, structurally
valid, lineage-clean, and partitioned per BUILD_SPEC §9."""

import subprocess
import sys
from pathlib import Path

from humanity_succeed.commissioning.contract import SuiteManifest, suite_problems
from humanity_succeed.commissioning.partition import partition
from humanity_succeed.corpus.compiler import load_cases
from humanity_succeed.corpus.splits import audit_splits

from ..conftest import REPO

SUITE = REPO / "cases" / "commissioning_suite_v1"


def _manifest() -> SuiteManifest:
    return SuiteManifest.model_validate_json((SUITE / "SUITE.json").read_text())


def test_committed_suite_matches_its_generators():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "generate_commissioning_suite.py"),
                        "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_suite_is_structurally_valid_and_builder_constructed():
    m = _manifest()
    assert suite_problems(m, SUITE) == []
    assert (m.authorship, m.split) == ("builder_constructed", "commissioning_dev")
    assert sum(len(g.members) for g in m.groups) == 160


def test_suite_lineage_audit_is_clean_alone_and_with_the_dev_corpus():
    suite, errors = load_cases(SUITE / "cases")
    assert errors == [] and len(suite) == 108
    dev, _ = load_cases(REPO / "cases" / "commissioning_dev")
    ex, _ = load_cases(REPO / "examples")
    for cases in (suite, suite + dev + ex):
        assert audit_splits([c for _, c, _ in cases])["status"] == "ok"


def test_partition_of_the_committed_suite():
    proof = partition(_manifest())["proof"]
    assert (proof["total_trajectories"], proof["development_trajectories"],
            proof["holdback_trajectories"]) == (160, 120, 40)
    assert proof["matches_section_9"] and proof["groups_in_both"] == 0


def test_suite_stays_out_of_the_dev_compile_path():
    """load_cases is recursive; the suite lives beside commissioning_dev, not inside it."""
    assert not Path(REPO / "cases" / "commissioning_dev" / "commissioning_suite_v1").exists()
