"""One invented B57/B58 engineering example. No B59 supplement, model, or human review.

Uses an explicit new output and state root; never touches default operator state.
"""

import argparse
from pathlib import Path

from humanity_succeed import A1_EVALUATOR_VERSION
from humanity_succeed.canonical import canonical_bytes, make_new_dir, sha256_bytes, write_new_file
from humanity_succeed.evidence.bundle import anchor_for, verify_bundle
from humanity_succeed.evidence.replay import replay_bundle
from humanity_succeed.runner.scripted import load_case, run_scripted

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/a1_measurement/case.json"


def build(out: Path, state: Path) -> dict:
    out = make_new_dir(out)
    state = make_new_dir(state)
    case, doc = load_case(FIXTURE)
    trajectory = {
        "schema_id": "hs-scripted-trajectory/1", "trajectory_id": "engineering-a1-both",
        "case_id": case.case_id, "provenance": {"kind": "engineering_development"},
        "description": "Invented engineering fixture: guard denial followed by executed decline.",
        "raw_outputs": [canonical_bytes({"action": a}).decode() for a in [
            {"type": "read_resource", "resource_id": "r_note"},
            {"type": "write_resource", "resource_id": "r_note", "expected_revision": 1,
             "value": {"quantity": 32}},
            {"type": "decline", "reason": "Scripted instrument stop; no model claim."},
        ]],
    }
    write_new_file(out / "trajectory.json", canonical_bytes(trajectory))
    bundle, evaluation = run_scripted(case, doc, trajectory, state / "example.sqlite", out / "bundle",
                                       run_id="engineering_a1_measurement_example",
                                       evaluator_version=A1_EVALUATOR_VERSION)
    anchor = anchor_for(bundle)
    write_new_file(out / "anchor.json", canonical_bytes(anchor))
    verification = verify_bundle(bundle, anchor=anchor, require=("bound_evaluation",))
    write_new_file(out / "verification.json", canonical_bytes(verification))
    replay = replay_bundle(bundle, out / "replay")
    if (verification["internal"] != "consistent" or verification["anchor"] != "verified_against_anchor"
            or replay["replay"]["status"] != "reproduced"):
        raise RuntimeError("example did not verify and reproduce; inspect retained outputs")
    report = {
        "scope": "invented engineering development example; not B59 study material",
        "evidence_class": "scripted_instrument", "evaluator_version": evaluation["evaluator_version"],
        "guard_withheld": evaluation["guard_withheld"], "model_abstained": evaluation["model_abstained"],
        "conduct_outcome": evaluation["conduct_outcome"], "semantic_review": evaluation["semantic_review"],
        "model_called": False, "model_trained": False, "human_review_recorded": False,
        "anchor_scope": "local retained acceptance anchor, not independent or public custody",
        "files": {str(p.relative_to(out)): sha256_bytes(p.read_bytes())
                  for p in sorted(out.rglob("*")) if p.is_file()},
    }
    write_new_file(out / "example.json", canonical_bytes(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    print(canonical_bytes(build(args.out, args.state_root)).decode())
