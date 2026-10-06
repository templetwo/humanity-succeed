"""Read-only historical check and replay of retained responses; no new commissioning runs."""

from __future__ import annotations

import argparse
import subprocess
from collections import Counter
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, load_document, sha256_bytes, write_new_file
from humanity_succeed.evidence.bundle import verify_bundle
from humanity_succeed.evidence.replay import replay_bundle

REPO = Path(__file__).resolve().parents[1]


def check(out: Path, replay_out: Path) -> dict:
    old = load_document(REPO / "docs/receipts/a1-measurement-v030/legacy.json")
    checksum_counts = {}
    for name in ("a1-measurement-v030", "a1-supplement-measurement"):
        packet = REPO / "docs/receipts" / name
        lines = (packet / "SHA256SUMS").read_text().splitlines()
        for line in lines:
            digest, rel = line.split("  ", 1)
            assert sha256_bytes((packet / rel).read_bytes()) == digest, rel
        checksum_counts[name] = {
            "files": len(lines),
            "inventory_sha256": sha256_bytes((packet / "SHA256SUMS").read_bytes()),
        }
    frozen = old["historical_paths"] + [
        "docs/receipts/a1-measurement-v030",
        "docs/receipts/a1-supplement-measurement",
        "cases/supplement_a1_measurement_v1",
        "src/humanity_succeed/evaluation",
        "src/humanity_succeed/corpus",
        "src/humanity_succeed/__init__.py",
    ]
    diff = subprocess.run(
        ["git", "diff", "677949fd07aebd0c852beb10de5d9887b081f344", "--", *frozen],
        cwd=REPO,
        check=True,
        capture_output=True,
    ).stdout
    assert not diff
    rows = []
    for index, prior in enumerate(old["bundles"]):
        bundle = REPO / prior["bundle"]
        assert sha256_bytes((bundle / "events.jsonl").read_bytes()) == prior["events_sha256"]
        assert sha256_bytes((bundle / "evaluation.json").read_bytes()) == prior["evaluation_sha256"]
        verified = verify_bundle(bundle)
        replay = replay_bundle(bundle, replay_out / f"legacy-{index}")
        assert verified["internal"] == "consistent" and replay["replay"]["status"] == "reproduced"
        rows.append(
            {
                "bundle": prior["bundle"],
                "version": prior["evaluator_version"],
                "digests_unchanged": True,
                "verification": "consistent",
                "replay": replay["replay"],
            }
        )
    packet = REPO / "docs/receipts/a1-supplement-measurement"
    for bundle in sorted((packet / "run-v1/bundles").iterdir()):
        verified = verify_bundle(bundle, load_document(packet / "run-v1/anchors" / (bundle.name + ".json")))
        replay = replay_bundle(bundle, replay_out / ("b59-" + bundle.name))
        assert verified["internal"] == "consistent" and verified["anchor"] == "verified_against_anchor"
        assert replay["replay"]["status"] == "reproduced"
        rows.append(
            {
                "bundle": str(bundle.relative_to(REPO)),
                "version": "hs-evaluator/0.3.0",
                "verification": "consistent",
                "retained_anchor": verified["anchor"],
                "replay": replay["replay"],
            }
        )
    result = {
        "schema_id": "hs-deepseek-preservation/1",
        "dependency_packets": checksum_counts,
        "frozen_paths": frozen,
        "diff_empty": not diff,
        "bundles": rows,
        "version_counts": dict(Counter(row["version"] for row in rows)),
        "passed": True,
        "note": "Recorded-response replay only; no new commissioning, provider request or human judgment.",
    }
    write_new_file(out, canonical_bytes(result))
    print(f"{len(rows)} retained bundles verify and replay; frozen inventories and paths unchanged")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--replay-out", type=Path, required=True)
    a = parser.parse_args()
    check(a.out, a.replay_out)
