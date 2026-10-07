"""A1 freeze of what the blind reviewer is asked: suite v1's 36 judgment-heavy cases, by the hash a
review must cite (``contracts.case.review_source_sha256``: the case document minus ``reviews``, so
task, world, rubric, predicates and limitations), plus the stable event stream each fixture's
trajectory re-executes to (what the packet's recorded sequence is built from).

Measured, not hand-written, from the committed run's own bundle copies of the cases:
    uv run python tests/golden/capture_suite_v1_review_source.py > tests/golden/suite_v1_review_source.json
``tests/golden/test_freeze_scope_cloud.py`` re-measures from the bundles AND from the live suite
YAML and must match exactly. The stage-0 observed freeze pins only the three verdict fields and
the evaluator version per fixture; a rubric edit that reaches both the generator and its output
would pass it, the generator check, and the observed freeze unnoticed. This catches it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

from humanity_succeed.canonical import sha256_obj, strict_json_loads  # noqa: E402
from humanity_succeed.commissioning import execute  # noqa: E402
from humanity_succeed.commissioning.contract import SuiteManifest  # noqa: E402
from humanity_succeed.contracts.case import review_source_sha256  # noqa: E402
from humanity_succeed.evidence.replay import _stable  # noqa: E402
from humanity_succeed.runner.scripted import load_case, load_trajectory  # noqa: E402

SUITE = REPO / "cases" / "commissioning_suite_v1"
RUN = REPO / "docs" / "receipts" / "wp3" / "run"
SCHEMA_ID = "hs-suite-v1-review-source/1"


def judgment_heavy_members() -> list:
    m = SuiteManifest.model_validate_json((SUITE / "SUITE.json").read_text())
    return [mem for g in m.groups for mem in g.members if mem.expected.judgment_heavy]


def bundle_dir(fixture_id: str) -> Path:
    report = strict_json_loads((RUN / "report.json").read_bytes())
    row = next(r for r in report["fixtures"] if r["fixture_id"] == fixture_id)
    return RUN / row["bundle"]


def measure() -> dict:
    rows = {}
    for mem in judgment_heavy_members():
        bundle_doc = strict_json_loads((bundle_dir(mem.fixture_id) / "case_source.json").read_bytes())
        case, doc = load_case(SUITE / mem.case)
        traj = load_trajectory(SUITE / mem.trajectory)
        _, events = execute.run_in_memory(
            case, doc, traj["raw_outputs"], evaluate=False,
            run_id="run_freeze_" + mem.fixture_id.replace("-", "_"))
        rows[mem.fixture_id] = {
            "review_source_sha256": review_source_sha256(bundle_doc),
            "stable_events_sha256": sha256_obj([_stable(e) for e in events]),
        }
    return {"schema_id": SCHEMA_ID, "fixtures": rows}


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
