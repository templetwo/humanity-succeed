"""Read-only WP2/WP3 historical verification and faithful replay into a new receipt directory."""

import argparse
import subprocess
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, load_document, make_new_dir, sha256_bytes
from humanity_succeed.evidence.bundle import verify_bundle
from humanity_succeed.evidence.replay import replay_bundle

REPO = Path(__file__).resolve().parents[1]
START = "3f304a14da78ef29165254a574d2f015aecd7d20"
FROZEN_PATHS = [
    "tests/golden/suite_v1_observed.json", "tests/golden/wp3_stage0_baseline.json",
    "cases/commissioning_suite_v1", "schemas/case.schema.json",
    "src/humanity_succeed/contracts/packet_schemas",
    "docs/receipts/wp2-demo", "docs/receipts/wp2-anchors", "docs/receipts/wp2r1",
    "docs/receipts/wp2r2", "docs/receipts/wp2-repair-r1", "docs/receipts/wp3",
]


def tree_hashes(root: Path) -> dict:
    return {str(p.relative_to(root)): sha256_bytes(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def check(out: Path) -> dict:
    out = make_new_dir(out)
    changes = subprocess.run(["git", "diff", START, "--", *FROZEN_PATHS], cwd=REPO,
                             capture_output=True, check=True).stdout
    rows = []
    for folder, anchors in [
        ("wp2-demo/bundles", "wp2-anchors"), ("wp2r1/demo/bundles", "wp2r1/anchors"),
        ("wp3/run/bundles", None),
    ]:
        root = REPO / "docs/receipts" / folder
        for bundle in sorted(root.iterdir()):
            if not bundle.is_dir():
                continue
            before = tree_hashes(bundle)
            anchor = (load_document(REPO / "docs/receipts" / anchors / f"{bundle.name}.anchor.json")
                      if anchors else None)
            verification = verify_bundle(bundle, anchor=anchor, require=("bound_evaluation",))
            replay = replay_bundle(bundle, out / f"replay-{folder.split('/')[0]}-{bundle.name}")
            recorded = load_document(bundle / "evaluation.json")
            manifest = load_document(bundle / "manifest.json")
            rows.append({
                "bundle": str(bundle.relative_to(REPO)), "evaluator_version": recorded["evaluator_version"],
                "manifest_evaluator_version": manifest["versions"]["evaluator"],
                "verification": verification["internal"], "anchor": verification["anchor"],
                "replay": replay["replay"], "files_unchanged": before == tree_hashes(bundle),
                "evaluation_sha256": before["evaluation.json"], "events_sha256": before["events.jsonl"],
                "verification_report_sha256": sha256_bytes(canonical_bytes(verification)),
            })
    ok = (not changes and len(rows) == 190 and all(
        r["verification"] == "consistent" and r["replay"]["status"] == "reproduced"
        and r["files_unchanged"] and r["replay"]["evaluator_version_used"] == r["evaluator_version"]
        and r["evaluator_version"] == r["manifest_evaluator_version"]
        and (r["anchor"] == "verified_against_anchor" if "wp3/" not in r["bundle"] else True)
        for r in rows))
    report = {"schema_id": "hs-a1-legacy-receipt/1", "reference_commit": START,
              "historical_paths": FROZEN_PATHS, "historical_diff_empty": not changes,
              "total": len(rows), "all_passed": ok, "bundles": rows,
              "golden_files": {p: sha256_bytes((REPO / p).read_bytes()) for p in FROZEN_PATHS[:2]},
              "claim_boundary": "Faithful replay of development evidence, not rescoring or human review."}
    (out / "legacy.json").write_bytes(canonical_bytes(report))
    print(canonical_bytes({k: v for k, v in report.items() if k != "bundles"}).decode())
    if not ok:
        raise RuntimeError("historical preservation check failed; see legacy.json")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    check(parser.parse_args().out)
