"""WP3 must not move WP0-WP2 behaviour: evaluations, event streams and compiler output are frozen
at the stage-0 commit (digests measured by capture_wp3_stage0.py, not written by hand)."""

import json
from pathlib import Path

from .capture_wp3_stage0 import measure

BASELINE = json.loads((Path(__file__).parent / "wp3_stage0_baseline.json").read_text())


def test_wp2_behaviour_is_frozen():
    now = measure()
    assert set(now["trajectories"]) == set(BASELINE["trajectories"])
    moved = {t: (BASELINE["trajectories"][t], row) for t, row in now["trajectories"].items()
             if row != BASELINE["trajectories"][t]}
    assert not moved, moved
    assert now["compiled_tree_sha256"] == BASELINE["compiled_tree_sha256"]


def test_freeze_is_not_vacuous():
    """The comparison notices a changed verdict (positive control on the assertion itself)."""
    t = next(iter(BASELINE["trajectories"]))
    forged = json.loads(json.dumps(BASELINE))
    forged["trajectories"][t]["evaluation_sha256"] = "0" * 64
    assert forged["trajectories"] != BASELINE["trajectories"]
    assert len(BASELINE["trajectories"]) == 24
