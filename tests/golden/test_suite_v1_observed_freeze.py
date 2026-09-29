"""Suite v1 is never rescored (B55): its observed verdicts under hs-evaluator/0.2.0 stay exactly as
measured at the A1 stage-0 freeze."""

import json
from pathlib import Path

from .capture_suite_v1_observed import measure

BASELINE = json.loads((Path(__file__).parent / "suite_v1_observed.json").read_text())


def test_suite_v1_observations_are_frozen():
    now = measure()["fixtures"]
    assert len(now) == len(BASELINE["fixtures"]) == 160
    moved = {k: (BASELINE["fixtures"][k], v) for k, v in now.items() if v != BASELINE["fixtures"][k]}
    assert not moved, moved
    assert {v["evaluator_version"] for v in now.values()} == {"hs-evaluator/0.2.0"}
