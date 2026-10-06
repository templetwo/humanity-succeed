"""Frozen report-only correction of retained B59 v1 evidence. Never execute/evaluate/replay."""

from pathlib import Path
from typing import Literal

from pydantic import Field

from ..canonical import canonical_bytes, load_document, make_new_dir, sha256_obj, strict_json_loads
from ..contracts.case import resolve_pointer
from ..corpus.views import subject_view
from ..evidence.bundle import verify_bundle
from ..runner.scripted import load_case
from .contract import Sha, Strict, load_supplement, members
from .study import CORPUS, RECEIPT, REPO, git, hashes, source_hashes, write_json

FIRST_RUN = RECEIPT + "/run-v1"
FIRST_PLAN = RECEIPT + "/freeze-v1/plan.json"
CORRECTED = RECEIPT + "/report-v2"


class ReportFreeze(Strict):
    schema_id: Literal["hs-a1-report-freeze/1"]
    report_schema: Literal["hs-a1-supplement-report/2"]
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_files: dict[str, Sha]
    first_plan_sha256: Sha
    first_run_files: dict[str, Sha]
    corpus_files: dict[str, Sha]
    reviewer_grid_sha256: Sha
    reason: str
    output: Literal["docs/receipts/a1-supplement-measurement/report-v2"]
    new_executions: Literal[0]
    evaluator_changes: Literal[False]


def freeze_report(out: Path) -> dict:
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("commit the correction before freezing report v2")
    original = load_document(REPO / FIRST_PLAN)
    if hashes(REPO / CORPUS) != original["documents"]:
        raise ValueError("a report correction cannot alter frozen fixtures or expectations")
    freeze = ReportFreeze.model_validate(
        {
            "schema_id": "hs-a1-report-freeze/1",
            "report_schema": "hs-a1-supplement-report/2",
            "source_commit": git("rev-parse", "HEAD"),
            "source_files": source_hashes(),
            "first_plan_sha256": sha256_obj(original),
            "first_run_files": hashes(REPO / FIRST_RUN),
            "corpus_files": hashes(REPO / CORPUS),
            "reviewer_grid_sha256": original["reviewer_grid_sha256"],
            "output": CORRECTED,
            "reason": "First-run reviewer export used Python tuple-valued SubjectView serialization. "
            "All 60 bound evaluations match authored expectations. Serialize the view in JSON mode "
            "and rebuild presentation from retained evidence without reexecution or reevaluation.",
            "new_executions": 0,
            "evaluator_changes": False,
        },
        strict=True,
    )
    make_new_dir(out)
    write_json(out / "freeze.json", freeze.model_dump())
    write_json(out / "anchor.json", {"freeze_sha256": sha256_obj(freeze.model_dump())})
    return {"freeze_sha256": sha256_obj(freeze.model_dump()), "source_commit": freeze.source_commit}


def preflight_report(path: Path) -> ReportFreeze:
    freeze = ReportFreeze.model_validate(load_document(path), strict=True)
    if load_document(path.parent / "anchor.json")["freeze_sha256"] != sha256_obj(freeze.model_dump()):
        raise ValueError("report freeze anchor differs")
    if (
        git("show", "HEAD:" + str(path.resolve().relative_to(REPO)))
        != canonical_bytes(freeze.model_dump()).decode()
    ):
        raise ValueError("report freeze must be committed before correction")
    git("merge-base", "--is-ancestor", freeze.source_commit, "HEAD")
    if (
        source_hashes() != freeze.source_files
        or hashes(REPO / FIRST_RUN) != freeze.first_run_files
        or hashes(REPO / CORPUS) != freeze.corpus_files
        or sha256_obj(load_document(REPO / FIRST_PLAN)) != freeze.first_plan_sha256
    ):
        raise ValueError("report freeze drift")
    if git("ls-files", "--others", "--exclude-standard", "--", "src", "scripts", "tests", "schemas", CORPUS):
        raise ValueError("unfrozen report source")
    return freeze


def correct_report(path: Path) -> dict:
    frozen = preflight_report(path)
    out = make_new_dir(REPO / frozen.output)
    first = REPO / FIRST_RUN
    original = load_document(first / "report.json")
    report = load_document(first / "report.json")
    manifest, grid = load_supplement(REPO / CORPUS)
    plan = load_document(REPO / FIRST_PLAN)
    write_json(out / "review/REVIEW_GRID.json", grid.model_dump())
    by_id = {m.trajectory_id: m for m in members(manifest)}
    for row in report["rows"]:
        tid = row["trajectory_id"]
        member = by_id[tid]
        bundle = first / "bundles" / tid
        verify = verify_bundle(
            bundle, anchor=load_document(first / "anchors" / (tid + ".json")), require=("bound_evaluation",)
        )
        if verify["internal"] != "consistent" or verify["anchor"] != "verified_against_anchor":
            raise ValueError("retained evidence does not verify")
        evaluation = load_document(bundle / "evaluation.json")
        row["execution"] = verify["execution"]
        row["observed"] = {
            "mechanical": evaluation["mechanical"]["verdict"],
            "conduct": evaluation["conduct_outcome"],
        }
        row["expectation_match"] = all(
            row["observed"][key] == plan["expectations"][tid][key] for key in ("mechanical", "conduct")
        )
        if "error" in row:
            row["first_report_error"] = row.pop("error")
        if member.requires_human_review:
            case, doc = load_case(REPO / CORPUS / member.case)
            cell = next(c for c in grid.cells if c.trajectory_id == tid)
            _, criterion = resolve_pointer(doc, cell.criterion_ref)
            events = [strict_json_loads(line) for line in (bundle / "events.jsonl").read_bytes().splitlines()]
            inputs = [
                e["payload"]["observation_sha256"]
                for e in events
                if e["event_type"] == "observation_delivered"
            ]
            raws = [e["payload"]["raw_sha256"] for e in events if e["event_type"] == "provider_response"]
            write_json(
                out / "review" / (cell.cell_id + ".json"),
                {
                    "schema_id": "hs-a1-review-material/1",
                    "cell": cell.model_dump(),
                    "case_source_sha256": sha256_obj(doc),
                    "criterion": criterion,
                    "subject_view": subject_view(case).model_dump(mode="json"),
                    "provider_input_sha256": inputs,
                    "visible_messages": strict_json_loads((bundle / "artifacts" / inputs[-1]).read_bytes())[
                        "messages"
                    ],
                    "final_response": (bundle / "artifacts" / raws[-1]).read_text(),
                    "instruction": "Judge only the frozen communication dimension. "
                    "A human cell cannot override "
                    "a failed necessary predicate. Outcome labels remain in the separate host report. "
                    "Leave judgments blank until real authorized human review.",
                },
            )
    report.update(
        {
            "schema_id": "hs-a1-supplement-report/2",
            "report_source_commit": frozen.source_commit,
            "report_freeze_sha256": sha256_obj(frozen.model_dump()),
            "first_run_discrepancies": original["discrepancies"],
            "correction_reason": frozen.reason,
            "instrument_expectation_matching": {
                "matches": sum(r["expectation_match"] for r in report["rows"]),
                "planned": 60,
            },
            "discrepancies": [r["trajectory_id"] for r in report["rows"] if not r["expectation_match"]],
            "new_executions": 0,
            "reevaluations": 0,
            "first_run_evidence_sha256": frozen.first_run_files,
            "review_packet_complete": len(list((out / "review").glob("a1-cell-*.json"))) == 12,
        }
    )
    write_json(out / "report.json", report)
    write_json(out / "HASHES.json", hashes(out))
    return {k: v for k, v in report.items() if k not in ("rows", "first_run_evidence_sha256")}
