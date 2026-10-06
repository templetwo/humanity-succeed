"""Read-only preservation check; reuses previously verified/replayed historical evidence."""

import subprocess
from collections import Counter
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, load_document, sha256_bytes, write_new_file

REPO = Path(__file__).resolve().parents[4]
PACKET = REPO / "docs/receipts/a1-supplement-measurement"
DEPENDENCY = REPO / "docs/receipts/a1-measurement-v030"
OLD = load_document(DEPENDENCY / "legacy.json")


def digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout


def check() -> dict:
    checksums = []
    for line in (DEPENDENCY / "SHA256SUMS").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        checksums.append({"file": relative, "matches": digest(DEPENDENCY / relative) == expected})
    historical = []
    for row in OLD["bundles"]:
        bundle = REPO / row["bundle"]
        historical.append({"bundle": row["bundle"], "version": row["evaluator_version"],
                           "events_match": digest(bundle / "events.jsonl") == row["events_sha256"],
                           "evaluation_match": digest(bundle / "evaluation.json") == row["evaluation_sha256"],
                           "retained_replay": row["replay"]["status"],
                           "retained_verification": row["verification"]})
    paths = OLD["historical_paths"] + ["docs/receipts/a1-measurement-v030"]
    diff = git("diff", "3f304a14da78ef29165254a574d2f015aecd7d20", "--", *OLD["historical_paths"])
    extension_diff = git("diff", "555b1b299bc9f78c90227f348c9fc1d91acc3a45", "--",
                         "docs/receipts/a1-measurement-v030", "src/humanity_succeed/__init__.py",
                         "src/humanity_succeed/contracts", "src/humanity_succeed/corpus",
                         "src/humanity_succeed/evaluation", "src/humanity_succeed/runner",
                         "src/humanity_succeed/evidence", "src/humanity_succeed/commissioning",
                         "src/humanity_succeed/review", "src/humanity_succeed/cli.py")
    untracked = git("ls-files", "--others", "--exclude-standard", "--", *paths)
    versions = Counter(row["version"] for row in historical)
    report = {"schema_id": "hs-b59-preservation/1", "historical_diff_empty": not diff,
              "dependency_code_and_receipt_preserved": not extension_diff,
              "no_untracked_historical_material": not untracked,
              "dependency_checksum_inventory_sha256": digest(DEPENDENCY / "SHA256SUMS"),
              "dependency_packet_files": checksums,
              "historical_bundles": historical, "historical_version_counts": dict(versions),
              "event_evaluation_digests_checked": len(historical) * 2,
              "golden_hashes": {name: digest(REPO / name) for name in OLD["golden_files"]},
              "reuse": "All 190 prior faithful replay/verification receipts reused; actual hashes and "
                       "frozen historical tree equality checked. "
                       "New B59 evidence verified and replayed separately."}
    report["passed"] = (not diff and not extension_diff and not untracked and len(checksums) == 41
                        and all(row["matches"] for row in checksums) and len(historical) == 190
                        and all(row["events_match"] and row["evaluation_match"]
                                and row["retained_replay"] == "reproduced"
                                and row["retained_verification"] == "consistent" for row in historical)
                        and report["golden_hashes"] == OLD["golden_files"])
    write_new_file(PACKET / "historical-preservation.json", canonical_bytes(report))
    print(canonical_bytes({k: v for k, v in report.items()
                           if k not in ("historical_bundles", "dependency_packet_files")}).decode())
    return report


if __name__ == "__main__":
    raise SystemExit(int(not check()["passed"]))
