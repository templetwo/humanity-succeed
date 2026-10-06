"""Build the local offline receipt inventory from actual retained results."""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from humanity_succeed.a1_supplement.report_v2 import preflight_report
from humanity_succeed.canonical import canonical_bytes, load_document, sha256_bytes, write_new_file

REPO = Path(__file__).resolve().parents[4]
PACKET = REPO / "docs/receipts/a1-supplement-measurement"
DEPENDENCY = "555b1b299bc9f78c90227f348c9fc1d91acc3a45"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def test_results(name: str) -> dict:
    suites = list(ET.parse(PACKET / "checks" / name).getroot().iter("testsuite"))
    result = {key: sum(int(suite.attrib[key]) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    assert result["failures"] == result["errors"] == result["skipped"] == 0
    return result


def finalize() -> dict:
    report = load_document(PACKET / "report-v2/report.json")
    frozen = preflight_report(PACKET / "freeze-report-v2/freeze.json")
    historical = load_document(PACKET / "historical-preservation.json")
    types = load_document(PACKET / "checks/mypy-report-v2-comparison.json")
    grid = load_document(PACKET / "report-v2/review/REVIEW_GRID.json")
    assert all(cell[field] is None for cell in grid["cells"]
               for field in ("verdict", "rationale", "reviewer", "adjudication"))
    assert len(grid["cells"]) == 12 and historical["passed"] and types["all_diagnostics_preexisting"]
    assert report["instrument_expectation_matching"] == {"matches": 60, "planned": 60}
    assert report["all_evidence_checks_passed"] and report["review_packet_complete"]
    assert report["new_executions"] == report["reevaluations"] == 0
    for row in report["rows"]:
        assert row["execution"]["execution_status"] == "completed"
        assert row["evaluator_versions"] == ["hs-evaluator/0.3.0"] * 3
        assert row["replay"] == "reproduced" and row["evaluation_binding"] == "bound"
    artifact_names = ["freeze-v1/plan.json", "freeze-report-v2/freeze.json", "run-v1/HASHES.json",
                      "report-v2/report.json", "report-v2/HASHES.json", "report-v2/review/REVIEW_GRID.json",
                      "QUALIFIED_REVIEW_PACKET.md", "historical-preservation.json"]
    receipt = {
        "schema_id": "hs-b59-local-acceptance/1", "branch": git("branch", "--show-current"),
        "starting_commit": DEPENDENCY, "dependency_code": "fede45e3a9a749318e9415c1f071c3d996c22882",
        "study_source": report["source_commit"], "study_freeze_execution_commit": report["execution_commit"],
        "first_run_evidence_commit": "f98ee823083e4f57e7080d21b304340c11c2d03a",
        "tested_repair_source": frozen.source_commit,
        "report_freeze_commit": "631323c3aad6c96ab11582db46f6287229fe81d4",
        "final_receipt_commit": "Resolved as delivered branch HEAD; full SHA supplied in handoff",
        "evaluator": report["evaluator"], "imported_implementation": report["imported_implementation"],
        "counts": report["counts"], "executions": 60, "replays": 60,
        "new_executions_for_report_repair": 0, "independent_observations": False,
        "instrument_expectation_matching": report["instrument_expectation_matching"],
        "scripted_task_outcomes": report["scripted_task_outcomes"],
        "scripted_conduct_outcomes": report["scripted_conduct_outcomes"],
        "always_refuse": report["always_refuse"], "human_review": report["human_review"],
        "preserved_first_discrepancies": report["first_run_discrepancies"], "unresolved_discrepancies": [],
        "tests": {"supplement": test_results("supplement.xml"), "offline": test_results("offline.xml")},
        "type_check": types, "historical_preservation": True,
        "artifact_sha256": {name: sha256_bytes((PACKET / name).read_bytes()) for name in artifact_names},
        "completion": "B59’s development supplement was built and executed against the pinned "
                      "v0.3.0 evaluator. Mechanical outcomes and control results are recorded; "
                      "qualified-communication judgments "
                      "remain pending human review.",
        "scope": "Local scripted development only. No human ratings, model calls/training, private holdback, "
                 "custody, formal commissioning, Stack writes, cross-repository integration or publication.",
    }
    write_new_file(PACKET / "acceptance.json", canonical_bytes(receipt))
    changes = set(git("diff", "--name-only", DEPENDENCY, "HEAD").splitlines())
    changes.update(git("diff", "--name-only").splitlines())
    changes.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    changes.update(str(p.relative_to(REPO)) for p in
                   (PACKET / "FILES_CHANGED.txt", PACKET / "SHA256SUMS"))
    write_new_file(PACKET / "FILES_CHANGED.txt", ("\n".join(sorted(changes)) + "\n").encode())
    inventory = [(sha256_bytes(path.read_bytes()), str(path.relative_to(PACKET)))
                 for path in sorted(PACKET.rglob("*")) if path.is_file() and path != PACKET / "SHA256SUMS"]
    checksum_bytes = ("".join(f"{digest}  {name}\n" for digest, name in inventory)).encode()
    write_new_file(PACKET / "SHA256SUMS", checksum_bytes)
    assert all(sha256_bytes((PACKET / name).read_bytes()) == digest for digest, name in inventory)
    return {"status": "passed", "receipt_files_checked": len(inventory),
            "packet_inventory_sha256": sha256_bytes((PACKET / "SHA256SUMS").read_bytes()),
            "tested_source_commit": frozen.source_commit, "tests": receipt["tests"]}


if __name__ == "__main__":
    print(canonical_bytes(finalize()).decode())
