"""A1 stage 0 freeze: suite v1's observed verdicts under hs-evaluator/0.2.0 (B55).

Measured, not hand-written:
    uv run python tests/golden/capture_suite_v1_observed.py > tests/golden/suite_v1_observed.json
Later A1 stages add evaluator 0.3.0; suite v1 must keep replaying to exactly these observations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

from humanity_succeed.commissioning import execute  # noqa: E402
from humanity_succeed.commissioning.contract import SuiteManifest  # noqa: E402
from humanity_succeed.runner.scripted import load_case, load_trajectory  # noqa: E402

SUITE = REPO / "cases" / "commissioning_suite_v1"


def measure() -> dict:
    m = SuiteManifest.model_validate_json((SUITE / "SUITE.json").read_text())
    rows = {}
    for g in m.groups:
        for mem in g.members:
            case, doc = load_case(SUITE / mem.case)
            traj = load_trajectory(SUITE / mem.trajectory)
            ev, _ = execute.run_in_memory(case, doc, traj["raw_outputs"],
                                          run_id="run_freeze_" + mem.fixture_id.replace("-", "_"))
            rows[mem.fixture_id] = {**execute.observed(ev),
                                    "evaluator_version": ev["evaluator_version"]}
    return {"schema_id": "hs-suite-v1-observed/1", "fixtures": rows}


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
