"""WP3 stage 0 freeze: measure current WP0-WP2 behaviour before any WP3 change.

Run once, at the freeze commit, to write wp3_stage0_baseline.json:
    uv run python tests/golden/capture_wp3_stage0.py > tests/golden/wp3_stage0_baseline.json
tests/golden/test_wp3_stage0_freeze.py recomputes the same digests and must match exactly. The
digests are measured, never written by hand. A later stage that moves one has changed WP2
behaviour, which WP3 must not do without a recorded decision.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

from humanity_succeed.canonical import sha256_obj  # noqa: E402
from humanity_succeed.corpus.compiler import compile_many  # noqa: E402
from humanity_succeed.evidence.replay import _stable  # noqa: E402
from humanity_succeed.runner.scripted import load_case, load_trajectory, run_scripted  # noqa: E402

DEV = REPO / "cases" / "commissioning_dev"
CASE_DIRS = (REPO / "examples", DEV)


def _cases() -> dict[str, tuple[Any, dict]]:
    out = {}
    for d in CASE_DIRS:
        for f in sorted(d.glob("*.yaml")):
            c, doc = load_case(f)
            out[c.case_id] = (c, doc)
    return out


def measure() -> dict[str, Any]:
    from humanity_succeed.evidence.store import EvidenceStore

    cases = _cases()
    rows = {}
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for tf in sorted((DEV / "trajectories").glob("*.yaml")):
            t = load_trajectory(tf)
            case, doc = cases[t["case_id"]]
            run_id = "run_freeze_" + sha256_obj(t["trajectory_id"])[:12]
            bundle, ev = run_scripted(case, doc, t, tmp / f"{tf.stem}.sqlite", tmp / tf.stem,
                                      run_id=run_id)
            store = EvidenceStore.open_readonly(tmp / f"{tf.stem}.sqlite")
            try:
                events = [_stable(e) for e in store.events(run_id)]
            finally:
                store.close()
            rows[t["trajectory_id"]] = {
                "evaluation_sha256": sha256_obj(ev),
                "stable_events_sha256": sha256_obj(events),
                "mechanical": ev["mechanical"]["verdict"],
                "conduct": ev["conduct_outcome"],
            }
        compile_many(list(CASE_DIRS), tmp / "compiled")
        tree = hashlib.sha256()
        for p in sorted((tmp / "compiled").rglob("*")):
            if p.is_file():
                tree.update(str(p.relative_to(tmp / "compiled")).encode() + b"\0" + p.read_bytes())
    return {"schema_id": "hs-wp3-stage0-freeze/1", "trajectories": rows,
            "compiled_tree_sha256": tree.hexdigest()}


if __name__ == "__main__":
    json.dump(measure(), sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
