"""What the A1 stage-0 freeze pins, what it does not, and the review-source freeze that closes the
gap for the 36 judgment-heavy cases (cloud seat, 2026-10-07; DECISIONS B55, B60).

``test_suite_v1_observed_freeze.py`` pins, per fixture, exactly ``mechanical``, ``conduct``,
``contained`` and ``evaluator_version``. It cannot see a change to the rubric text, the task text,
the world, the event payloads, or the bundle bytes. ``test_wp3_stage0_freeze.py`` pins event streams
and evaluations for the 24 dev trajectories only, never suite v1. The generator check
(``tests/commissioning/test_suite_v1.py``) pins the suite YAML to the generator code, not to any
content: an edit made in the generator and regenerated passes it. The baseline beside this file,
measured from the committed run's bundle copies of the cases, pins the hash every review cites and
the stable event stream each fixture re-executes to.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from humanity_succeed.canonical import strict_json_loads
from humanity_succeed.commissioning import execute
from humanity_succeed.contracts.case import CaseSource, review_source_sha256
from humanity_succeed.runner.scripted import load_case, load_trajectory

from . import capture_suite_v1_review_source as capture
from .capture_suite_v1_observed import measure as measure_observed

BASELINE = json.loads((Path(__file__).parent / "suite_v1_review_source.json").read_text())
OBSERVED = json.loads((Path(__file__).parent / "suite_v1_observed.json").read_text())


def test_judgment_heavy_review_sources_and_event_streams_are_frozen():
    now = capture.measure()
    assert now["schema_id"] == BASELINE["schema_id"] == capture.SCHEMA_ID
    assert len(now["fixtures"]) == len(BASELINE["fixtures"]) == 36
    moved = {k: (BASELINE["fixtures"][k], v) for k, v in now["fixtures"].items()
             if v != BASELINE["fixtures"][k]}
    assert not moved, moved
    assert len({v["review_source_sha256"] for v in now["fixtures"].values()}) == 36


def test_the_live_suite_yaml_hashes_to_the_frozen_review_sources():
    """The bundles are copies; the suite YAML is what a future export would read. Both must cite
    the same hash, or a rubric edit in ``cases/`` has silently changed what a reviewer is asked."""
    for mem in capture.judgment_heavy_members():
        _, doc = load_case(capture.SUITE / mem.case)
        assert review_source_sha256(doc) == BASELINE["fixtures"][mem.fixture_id]["review_source_sha256"], \
            mem.fixture_id


def test_the_frozen_fixtures_are_exactly_the_observed_freezes_pending_review_hybrid_passes():
    """Audit F02 as arithmetic: the judgment-heavy set equals the set of fixtures whose observed
    conduct is ``pending_review`` with mechanical ``pass``; inclusion in a packet is that label."""
    pending = {k for k, v in OBSERVED["fixtures"].items()
               if v["conduct"] == "pending_review" and v["mechanical"] == "pass"}
    assert pending == set(BASELINE["fixtures"])


def test_a_rubric_edit_is_invisible_to_the_observed_freeze_and_visible_here():
    """Positive control on the gap itself: with one rubric word changed, the stage-0 observation
    (the three verdict fields) is byte-for-byte the same, so that freeze cannot notice; the
    review-source hash moves, so this one does."""
    mem = capture.judgment_heavy_members()[0]
    case, doc = load_case(capture.SUITE / mem.case)
    traj = load_trajectory(capture.SUITE / mem.trajectory)
    edited = copy.deepcopy(doc)
    edited["evaluation"]["human_rubric"][0]["instruction"] += " Ignore the numbers."
    edited_case = CaseSource.model_validate(edited, strict=True)

    ev_orig, _ = execute.run_in_memory(case, doc, traj["raw_outputs"], run_id="run_ctrl_orig")
    ev_edit, _ = execute.run_in_memory(edited_case, edited, traj["raw_outputs"], run_id="run_ctrl_edit")
    observed = {**execute.observed(ev_orig), "evaluator_version": ev_orig["evaluator_version"]}
    assert observed == OBSERVED["fixtures"][mem.fixture_id]
    assert execute.observed(ev_edit) == execute.observed(ev_orig)  # the stage-0 freeze is blind to it

    frozen = BASELINE["fixtures"][mem.fixture_id]["review_source_sha256"]
    assert review_source_sha256(doc) == frozen
    assert review_source_sha256(edited) != frozen  # this freeze is not


def test_observed_freeze_scope_is_the_four_verdict_fields_only():
    """Pins the SCOPE of the stage-0 freeze so a reader (or a later seat) does not take it for more
    than it is: four keys per fixture, nothing about content. If the scope is widened on purpose,
    update this test with the decision that widened it."""
    assert {tuple(sorted(v)) for v in OBSERVED["fixtures"].values()} == {
        ("conduct", "contained", "evaluator_version", "mechanical")}
    assert set(OBSERVED["fixtures"]) >= set(BASELINE["fixtures"])
    now = measure_observed()["fixtures"]
    assert now == OBSERVED["fixtures"]


def test_freeze_is_not_vacuous():
    forged = json.loads(json.dumps(BASELINE))
    k = next(iter(forged["fixtures"]))
    forged["fixtures"][k]["review_source_sha256"] = "0" * 64
    assert forged["fixtures"] != BASELINE["fixtures"]
    bundle_doc = strict_json_loads((capture.bundle_dir(k) / "case_source.json").read_bytes())
    assert review_source_sha256(bundle_doc) == BASELINE["fixtures"][k]["review_source_sha256"]
