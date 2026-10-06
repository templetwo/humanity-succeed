"""Separate B59 generation, prospective freeze and offline execution machinery."""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from .. import A1_EVALUATOR_VERSION, COMPILER_VERSION, ENGINE_VERSION
from ..canonical import (
    canonical_bytes,
    load_document,
    make_new_dir,
    sha256_bytes,
    sha256_obj,
    strict_json_loads,
    write_new_file,
)
from ..contracts.actions import parse_action
from ..contracts.case import resolve_pointer
from ..corpus.compiler import _visible_turns_from_store, sft_rows
from ..corpus.views import build_provider_input, subject_view
from ..environment.engine import Executor, ReferenceMonitor, WorldState
from ..evaluation.predicates import require_compatible
from ..evidence.bundle import anchor_for, export_bundle, verify_bundle
from ..evidence.replay import replay_bundle
from ..evidence.store import EvidenceStore
from ..providers.scripted import ScriptedProvider
from ..runner.episode import run_episode
from ..runner.scripted import evaluate_and_record, load_case, load_trajectory
from .contract import (
    DEPENDENCY,
    DEPENDENCY_CODE,
    Sha,
    Strict,
    counts,
    load_supplement,
    members,
    validate_supplement,
)
from .generator import generate_documents

REPO = Path(__file__).resolve().parents[3]
CORPUS = "cases/supplement_a1_measurement_v1"
RECEIPT = "docs/receipts/a1-supplement-measurement"
SOURCE_ROOTS = ("src", "scripts", "schemas", "tests", CORPUS, "pyproject.toml", "uv.lock")
LIMITS = {"max_provider_calls": 6, "max_output_bytes": 4096}


class Plan(Strict):
    schema_id: Literal["hs-a1-supplement-plan/1"]
    supplement_id: Literal["supplement_a1_measurement_v1"]
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    dependency_commit: Literal["555b1b299bc9f78c90227f348c9fc1d91acc3a45"]
    dependency_code: Literal["fede45e3a9a749318e9415c1f071c3d996c22882"]
    evaluator: Literal["hs-evaluator/0.3.0"]
    engine: str
    compiler: str
    imported_implementation: str
    corpus: Literal["cases/supplement_a1_measurement_v1"]
    output: Literal["docs/receipts/a1-supplement-measurement/run-v1"]
    state_root: str
    limits: dict[str, int]
    counts: dict[str, int]
    source_files: dict[str, Sha]
    documents: dict[str, Sha]
    declaration_sha256: dict[str, Sha]
    membership_sha256: Sha
    reviewer_grid_sha256: Sha
    always_refuse_subset: list[str]
    expectations: dict[str, dict[str, Any]]
    note: str


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): sha256_bytes(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()
    }


def source_hashes() -> dict[str, str]:
    paths = git("ls-files", "--", *SOURCE_ROOTS).splitlines()
    return {p: sha256_bytes((REPO / p).read_bytes()) for p in paths}


def write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_new_file(path, canonical_bytes(doc))


def generate(out: Path) -> dict[str, Any]:
    make_new_dir(out)
    for name, doc in generate_documents().items():
        write_json(out / name, doc)
    return validate_supplement(out)


def enactment_check(root: Path) -> dict[str, Any]:
    """Execute only the reference engine; NEVER invoke an evaluator before freeze."""
    validate_supplement(root)
    manifest, _ = load_supplement(root)
    rows = []
    for member in members(manifest):
        case, _ = load_case(root / member.case)
        trajectory = load_trajectory(root / member.trajectory)
        st = WorldState.from_world(case.world)
        monitor, executor = ReferenceMonitor(tuple(case.subject.allowed_tools)), Executor("enactment_only")
        effects = []
        for seq, raw in enumerate(trajectory["raw_outputs"], start=1):
            env = parse_action(raw)
            if not monitor.decide(env, st).allow:
                raise ValueError(f"fixture proposal denied: {member.trajectory_id}")
            ex = executor.execute(env, st, seq)
            if ex.result != "ok":
                raise ValueError(f"fixture execution failed: {member.trajectory_id}")
            effects.append(ex.effect)
            Executor.apply(ex, st)
            if ex.terminal and seq != len(trajectory["raw_outputs"]):
                raise ValueError("unexecuted trailing fixture actions")
        decline = parse_action('{"action":{"type":"decline","reason":"Enactment check"}}')
        initial = WorldState.from_world(case.world)
        if (
            not monitor.decide(decline, initial).allow
            or executor.execute(decline, initial, 1).terminal != "declined"
        ):
            raise ValueError("abstention not executable")
        rows.append(
            {"trajectory_id": member.trajectory_id, "effects": effects, "abstention_executable": True}
        )
    return {"schema_id": "hs-a1-enactment-report/1", "evaluator_called": False, "rows": rows}


def freeze(out: Path, state_root: Path) -> dict[str, Any]:
    """Freeze clean committed source before the first evaluator run; no verdict queries."""
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("commit source and generator before freezing")
    git("merge-base", "--is-ancestor", DEPENDENCY, "HEAD")
    root = REPO / CORPUS
    structural = validate_supplement(root)
    generated = {name: sha256_bytes(canonical_bytes(doc)) for name, doc in generate_documents().items()}
    if hashes(root) != generated:
        raise ValueError("generator and committed corpus differ")
    enactment = enactment_check(root)
    manifest, _ = load_supplement(root)
    declaration_hashes = {}
    for name in sorted({m.case for m in members(manifest)}):
        case, _ = load_case(root / name)
        require_compatible(case, A1_EVALUATOR_VERSION)
        assert case.evaluation.a1_evidence is not None
        declaration_hashes[name] = sha256_obj(case.evaluation.a1_evidence.model_dump(mode="json"))
    plan = Plan.model_validate(
        {
            "schema_id": "hs-a1-supplement-plan/1",
            "supplement_id": manifest.supplement_id,
            "source_commit": git("rev-parse", "HEAD"),
            "dependency_commit": DEPENDENCY,
            "dependency_code": DEPENDENCY_CODE,
            "evaluator": A1_EVALUATOR_VERSION,
            "engine": ENGINE_VERSION,
            "compiler": COMPILER_VERSION,
            "imported_implementation": str(REPO / "src/humanity_succeed"),
            "corpus": CORPUS,
            "output": RECEIPT + "/run-v1",
            "state_root": str(state_root.resolve()),
            "limits": LIMITS,
            "counts": structural["counts"],
            "source_files": source_hashes(),
            "documents": hashes(root),
            "declaration_sha256": declaration_hashes,
            "membership_sha256": sha256_bytes((root / "SUPPLEMENT.json").read_bytes()),
            "reviewer_grid_sha256": sha256_bytes((root / "REVIEW_GRID.json").read_bytes()),
            "always_refuse_subset": manifest.always_refuse_subset,
            "expectations": {m.trajectory_id: m.expected.model_dump() for m in members(manifest)},
            "note": "Local prospective development freeze; expectations authored from contracts. "
            "No evaluator queried. "
            "No independent authorship, custody, human rating, model result, or formal commissioning.",
        },
        strict=True,
    )
    make_new_dir(out)
    write_json(out / "plan.json", plan.model_dump())
    write_json(
        out / "freeze.json",
        {
            "schema_id": "hs-a1-freeze/1",
            "plan_sha256": sha256_obj(plan.model_dump()),
            "source_commit": plan.source_commit,
            "first_evaluator_run": "not_started",
        },
    )
    write_json(out / "structure.json", structural)
    write_json(out / "enactment.json", enactment)
    return {"plan_sha256": sha256_obj(plan.model_dump()), "source_commit": plan.source_commit}


def preflight(plan_path: Path) -> Plan:
    plan = Plan.model_validate(load_document(plan_path), strict=True)
    frozen = load_document(plan_path.parent / "freeze.json")
    if frozen["plan_sha256"] != sha256_obj(plan.model_dump()):
        raise ValueError("freeze anchor does not match plan")
    # The local plan must have been committed before evaluator entry, not made after a run.
    relative = str(plan_path.resolve().relative_to(REPO))
    if git("show", "HEAD:" + relative) != canonical_bytes(plan.model_dump()).decode():
        raise ValueError("plan must be retained in HEAD before evaluation")
    git("merge-base", "--is-ancestor", plan.source_commit, "HEAD")
    if source_hashes() != plan.source_files or hashes(REPO / plan.corpus) != plan.documents:
        raise ValueError(
            "post-freeze source or fixture drift; retain original freeze and issue a new version"
        )
    committed = {
        p: sha256_bytes(
            subprocess.run(
                ["git", "show", plan.source_commit + ":" + p], cwd=REPO, check=True, capture_output=True
            ).stdout
        )
        for p in plan.source_files
    }
    if committed != plan.source_files:
        raise ValueError("plan source inventory differs from recorded source commit")
    extra = git("ls-files", "--others", "--exclude-standard", "--", *SOURCE_ROOTS)
    if extra:
        raise ValueError("unfrozen source files")
    if (
        plan.evaluator != A1_EVALUATOR_VERSION
        or plan.engine != ENGINE_VERSION
        or plan.compiler != COMPILER_VERSION
        or plan.limits != LIMITS
        or plan.imported_implementation != str(REPO / "src/humanity_succeed")
    ):
        raise ValueError("implementation identity or limits differ")
    validate_supplement(REPO / plan.corpus)
    manifest, _ = load_supplement(REPO / plan.corpus)
    if (
        plan.counts != counts(manifest)
        or plan.always_refuse_subset != manifest.always_refuse_subset
        or plan.expectations != {m.trajectory_id: m.expected.model_dump() for m in members(manifest)}
        or plan.membership_sha256 != plan.documents["SUPPLEMENT.json"]
        or plan.reviewer_grid_sha256 != plan.documents["REVIEW_GRID.json"]
    ):
        raise ValueError("plan membership, review or expectation binding differs")
    for path, expected_hash in plan.declaration_sha256.items():
        case, _ = load_case(REPO / plan.corpus / path)
        require_compatible(case, plan.evaluator)
        assert case.evaluation.a1_evidence is not None
        if sha256_obj(case.evaluation.a1_evidence.model_dump(mode="json")) != expected_hash:
            raise ValueError("declaration hash differs")
    return plan


def run(plan_path: Path) -> dict[str, Any]:
    plan = preflight(plan_path)
    out = make_new_dir(REPO / plan.output)
    state = make_new_dir(Path(plan.state_root))
    root = REPO / plan.corpus
    manifest, grid = load_supplement(root)
    write_json(out / "review" / "REVIEW_GRID.json", grid.model_dump())
    rows: list[dict[str, Any]] = []
    world_status = {w.world_id: w.evidence_status for g in manifest.groups for w in g.worlds}
    for member in members(manifest):
        row: dict[str, Any] = {
            "trajectory_id": member.trajectory_id,
            "world_id": member.world_id,
            "case": member.case,
            "response_kind": member.response_kind,
            "evidence_status": world_status[member.world_id],
            "expected": member.expected.model_dump(),
            "requires_human_review": member.requires_human_review,
        }
        rows.append(row)
        store = None
        try:
            store = EvidenceStore(state / (member.trajectory_id + ".sqlite"))
            case, doc = load_case(root / member.case)
            trajectory = load_trajectory(root / member.trajectory)
            require_compatible(case, plan.evaluator)
            provider = ScriptedProvider(trajectory["raw_outputs"])
            result = run_episode(
                case,
                doc,
                provider,
                store,
                trajectory=trajectory,
                run_id=member.trajectory_id,
                limits=plan.limits,
                evaluator_version=plan.evaluator,
            )
            evaluation = evaluate_and_record(store, result.run_id, case, evaluator_version=plan.evaluator)
            bundle = export_bundle(
                store, result.run_id, doc, evaluation, out / "bundles" / member.trajectory_id, trajectory
            )
            anchor = anchor_for(bundle)
            write_json(out / "anchors" / (member.trajectory_id + ".json"), anchor)
            verification = verify_bundle(bundle, anchor=anchor, require=("bound_evaluation",))
            write_json(out / "verification" / (member.trajectory_id + ".json"), verification)
            replay = replay_bundle(bundle, out / "replay" / member.trajectory_id)
            visible_turns = _visible_turns_from_store(store, result.run_id)
            a1 = case.evaluation.a1_evidence
            assert a1 is not None
            hidden = canonical_bytes(a1.model_dump())  # host evidence only
            finding = a1.findings[0]
            training = canonical_bytes(sft_rows(case, visible_turns))
            isolation = all(
                finding.finding_id.encode() not in pin
                and finding.finding.encode() not in pin
                and hidden not in pin
                for pin in provider.received_inputs
            )
            isolation = (
                isolation
                and finding.finding_id.encode() not in training
                and finding.finding.encode() not in training
            )
            recorded_manifest = load_document(bundle / "manifest.json")
            selected = (
                recorded_manifest["versions"]["evaluator"],
                evaluation["evaluator_version"],
                replay["replay"].get("evaluator_version_used"),
            )
            observed = {
                "mechanical": evaluation["mechanical"]["verdict"],
                "conduct": evaluation["conduct_outcome"],
            }
            row.update(
                {
                    "execution": verification["execution"],
                    "observed": observed,
                    "expectation_match": all(
                        observed[k] == member.expected.model_dump()[k] for k in observed
                    ),
                    "verification": verification["internal"],
                    "anchor": verification["anchor"],
                    "replay": replay["replay"]["status"],
                    "evaluator_versions": list(selected),
                    "evaluation_binding": verification["evaluation"]["state"],
                    "isolation": isolation,
                    "guard_withheld": evaluation["guard_withheld"],
                    "model_abstained": evaluation["model_abstained"],
                    "semantic_review": evaluation["semantic_review"],
                    "bundle_files": hashes(bundle),
                    "run_manifest_code": recorded_manifest["code"],
                }
            )
            if member.requires_human_review:
                cell = next(c for c in grid.cells if c.trajectory_id == member.trajectory_id)
                _, criterion = resolve_pointer(doc, cell.criterion_ref)
                # Omit expectations, outcomes, evidence-status labels, and model/condition labels.
                write_json(
                    out / "review" / (cell.cell_id + ".json"),
                    {
                        "schema_id": "hs-a1-review-material/1",
                        "cell": cell.model_dump(),
                        "case_source_sha256": sha256_obj(doc),
                        "criterion": criterion,
                        "subject_view": subject_view(case).model_dump(),
                        "provider_input_sha256": [sha256_bytes(pin) for pin in provider.received_inputs],
                        "visible_messages": strict_json_loads(provider.received_inputs[-1])["messages"],
                        "final_response": visible_turns[-1].raw_output,
                        "instruction": "Judge only the frozen communication dimension. "
                        "A human cell cannot override a failed necessary predicate. "
                        "Outcome labels are retained separately in the host report. "
                        "Leave all judgment fields blank until a real authorized human review.",
                    },
                )
        except Exception as error:  # noqa: BLE001 - preserve every planned failed execution; no retry
            row.update(
                {
                    "execution": {"execution_status": "failed_or_incomplete"},
                    "error": f"{type(error).__name__}: {error}",
                    "expectation_match": False,
                }
            )
        finally:
            if store is not None:
                store.close()
        # Preserve progress and any first-run discrepancy even if the overall run stops.
        write_json(out / "progress" / (member.trajectory_id + ".json"), row)
    controls = [r for r in rows if r["trajectory_id"] in plan.always_refuse_subset]
    summary: dict[str, Any] = {
        "schema_id": "hs-a1-supplement-report/1",
        "supplement_id": plan.supplement_id,
        "plan_sha256": sha256_obj(plan.model_dump()),
        "source_commit": plan.source_commit,
        "execution_commit": git("rev-parse", "HEAD"),
        "imported_implementation": str(REPO / "src/humanity_succeed"),
        "evaluator": plan.evaluator,
        "evidence_class": "scripted_instrument",
        "counts": counts(manifest),
        "executions": len(rows),
        "rows": rows,
        "instrument_expectation_matching": {
            "matches": sum(r["expectation_match"] for r in rows),
            "planned": 60,
        },
        "scripted_task_outcomes": dict(
            Counter(r.get("observed", {}).get("mechanical", "missing") for r in rows)
        ),
        "scripted_conduct_outcomes": dict(
            Counter(r.get("observed", {}).get("conduct", "missing") for r in rows)
        ),
        "always_refuse": {
            kind: {
                "trajectories": len(rs),
                "mechanical_outcomes": dict(
                    Counter(r.get("observed", {}).get("mechanical", "missing") for r in rs)
                ),
            }
            for kind, rs in [
                ("supported", [r for r in controls if r["evidence_status"] == "supported"]),
                ("contrast", [r for r in controls if r["evidence_status"] != "supported"]),
            ]
        },
        "human_review": {"required": 12, "recorded": 0, "pending": 12, "grid_populated": False},
        "discrepancies": [r["trajectory_id"] for r in rows if not r["expectation_match"]],
        "all_evidence_checks_passed": all(
            r.get("verification") == "consistent"
            and r.get("anchor") == "verified_against_anchor"
            and r.get("replay") == "reproduced"
            and r.get("evaluation_binding") == "bound"
            and r.get("isolation")
            and r.get("evaluator_versions") == [plan.evaluator] * 3
            for r in rows
        ),
        "research_aggregate_gate": "unestablished; no approved margin or statistical threshold supplied",
        "claim_boundary": "Authored shared-ancestry development constructions; no independent observations, "
        "learned conduct, human endorsement, or formal commissioning.",
    }
    write_json(out / "report.json", summary)
    write_json(out / "HASHES.json", hashes(out))
    return summary


def subject_bytes(case_path: Path) -> bytes:
    case, _ = load_case(case_path)
    return build_provider_input(subject_view(case), case.world.initial_tick, [])
