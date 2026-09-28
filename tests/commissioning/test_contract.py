"""The WP3 shared contract (lead-authored): §9 totals and structural validation."""

import pytest
from pydantic import ValidationError

from humanity_succeed.commissioning.contract import (
    CLASSES,
    DEVELOPMENT_TRAJECTORIES,
    HOLDBACK_TRAJECTORIES,
    TOTAL_TRAJECTORIES,
    Expectation,
    Member,
    SuiteManifest,
    suite_problems,
)


def test_section_9_distribution():
    assert (TOTAL_TRAJECTORIES, DEVELOPMENT_TRAJECTORIES, HOLDBACK_TRAJECTORIES) == (160, 120, 40)
    per_class = {c.class_id: c.groups * c.members for c in CLASSES}
    assert list(per_class.values()) == [24, 24, 24, 24, 24, 24, 16]
    held = {c.class_id: c.holdback_groups * c.members for c in CLASSES}
    assert list(held.values()) == [4, 4, 4, 4, 4, 12, 8]


def _exp(**kw):
    base = {"mechanical": "pass", "conduct": "pass", "contained": False,
            "judgment_heavy": False, "rationale": "r"}
    return Expectation.model_validate({**base, **kw})


def test_member_paths_cannot_escape_or_be_absolute():
    for bad in ("../x.yaml", "/abs/x.yaml", "cases/../../x.yaml", "other/x.yaml"):
        with pytest.raises(ValidationError):
            Member(fixture_id="f", role="r", case=bad, trajectory="trajectories/t.yaml",
                   expected=_exp())


def test_empty_manifest_reports_every_class_count(tmp_path):
    m = SuiteManifest(schema_id="hs-commission-suite/1", suite_id="s",
                      authorship="builder_constructed", authored_by="x",
                      split="commissioning_dev", groups=[], note="n")
    probs = suite_problems(m, tmp_path)
    assert len(probs) == len(CLASSES) and all("0 groups" in p for p in probs)
    frag = suite_problems(m.model_copy(update={"split": "commissioning_holdback"}), tmp_path,
                          fragment=True)
    assert "C6_multiple_paths: 0 groups, expected 4" in frag


def test_expectation_vocabulary_is_closed():
    with pytest.raises(ValidationError):
        _exp(mechanical="mostly_pass")
    with pytest.raises(ValidationError):
        _exp(conduct="pass_pending")
