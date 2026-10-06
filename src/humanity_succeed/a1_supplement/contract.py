"""B59 membership and blank human checklist contracts. No evaluator calls here."""

from collections import Counter
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..canonical import load_document, sha256_obj
from ..contracts.case import resolve_pointer
from ..runner.scripted import load_case, load_trajectory

SUPPLEMENT_ID = "supplement_a1_measurement_v1"
DEPENDENCY = "555b1b299bc9f78c90227f348c9fc1d91acc3a45"
DEPENDENCY_CODE = "fede45e3a9a749318e9415c1f071c3d996c22882"
ID = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
CasePath = Annotated[str, Field(pattern=r"^cases/[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json$")]
TrajectoryPath = Annotated[str, Field(pattern=r"^trajectories/[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json$")]
Contrast = Literal["unsupported", "contradicted", "not_assessable"]
Status = Literal["supported", "unsupported", "contradicted", "not_assessable"]
Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Expected(Strict):
    mechanical: Literal["pass", "fail"]
    conduct: Literal["pass", "fail", "pending_review"]
    rationale: Annotated[str, Field(min_length=1)]


class Member(Strict):
    trajectory_id: ID
    world_id: ID
    case: CasePath
    trajectory: TrajectoryPath
    response_kind: Literal["assert", "withhold", "qualified"]
    expected: Expected
    requires_human_review: bool
    criterion_refs: Annotated[list[str], Field(min_length=1)]


class World(Strict):
    world_id: ID
    evidence_status: Status
    mechanical_case: CasePath
    qualified_case: CasePath | None
    parent_world_id: ID | None


class Group(Strict):
    group_id: ID
    contrast_status: Contrast
    root_scenario_id: ID
    worlds: Annotated[list[World], Field(min_length=2, max_length=2)]
    members: Annotated[list[Member], Field(min_length=5, max_length=5)]


class Supplement(Strict):
    schema_id: Literal["hs-a1-supplement/1"]
    supplement_id: Literal["supplement_a1_measurement_v1"]
    authorship: dict[str, Any]
    groups: Annotated[list[Group], Field(min_length=12, max_length=12)]
    always_refuse_subset: Annotated[list[ID], Field(min_length=24, max_length=24)]
    note: Annotated[str, Field(min_length=1)]


class Cell(Strict):
    cell_id: ID
    trajectory_id: ID
    case: CasePath
    criterion_ref: Annotated[str, Field(pattern=r"^/evaluation/human_rubric/[0-9]+$")]
    criterion_sha256: Sha
    finding_id: ID
    status: Literal["pending_human_review"]
    verdict: None
    rationale: None
    reviewer: None
    adjudication: None


class ReviewGrid(Strict):
    schema_id: Literal["hs-a1-review-grid/1"]
    cells: Annotated[list[Cell], Field(min_length=12, max_length=12)]


def members(manifest: Supplement) -> list[Member]:
    return [m for g in manifest.groups for m in g.members]


def counts(manifest: Supplement) -> dict[str, int]:
    ms = members(manifest)
    return {
        "groups": len(manifest.groups),
        "logical_worlds": sum(len(g.worlds) for g in manifest.groups),
        "case_documents": len({m.case for m in ms}),
        "trajectories": len(ms),
        "assert": sum(m.response_kind == "assert" for m in ms),
        "withhold": sum(m.response_kind == "withhold" for m in ms),
        "qualified": sum(m.response_kind == "qualified" for m in ms),
        "mechanical": sum(not m.requires_human_review for m in ms),
        "judgment_heavy": sum(m.requires_human_review for m in ms),
        "always_refuse": len(manifest.always_refuse_subset),
    }


def load_supplement(root: Path) -> tuple[Supplement, ReviewGrid]:
    return (
        Supplement.model_validate(load_document(root / "SUPPLEMENT.json"), strict=True),
        ReviewGrid.model_validate(load_document(root / "REVIEW_GRID.json"), strict=True),
    )


def validate_supplement(root: Path) -> dict[str, Any]:
    """Structure, ancestry, criterion and count validation only; never query verdicts."""
    root = Path(root)
    if root.is_symlink():
        raise ValueError("symlinked supplement root refused")
    manifest, grid = load_supplement(root)
    want = {
        "groups": 12,
        "logical_worlds": 24,
        "case_documents": 36,
        "trajectories": 60,
        "assert": 24,
        "withhold": 24,
        "qualified": 12,
        "mechanical": 48,
        "judgment_heavy": 12,
        "always_refuse": 24,
    }
    if counts(manifest) != want:
        raise ValueError("supplement counts do not match B59")
    if Counter(g.contrast_status for g in manifest.groups) != {
        "unsupported": 4,
        "contradicted": 4,
        "not_assessable": 4,
    }:
        raise ValueError("four groups per contrast required")
    ms = members(manifest)
    if len({m.trajectory_id for m in ms}) != 60 or len({m.trajectory for m in ms}) != 60:
        raise ValueError("duplicate trajectory membership or file")
    if (
        len({g.group_id for g in manifest.groups}) != 12
        or len({g.root_scenario_id for g in manifest.groups}) != 12
    ):
        raise ValueError("duplicate group/root")
    worlds = [w for g in manifest.groups for w in g.worlds]
    if len({w.world_id for w in worlds}) != 24:
        raise ValueError("duplicate world")
    withholds = {m.trajectory_id for m in ms if m.response_kind == "withhold"}
    if set(manifest.always_refuse_subset) != withholds or len(set(manifest.always_refuse_subset)) != 24:
        raise ValueError("always-refuse subset must equal the 24 existing withhold trajectories")
    declared = {m.case for m in ms} | {m.trajectory for m in ms} | {"SUPPLEMENT.json", "REVIEW_GRID.json"}
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if actual != declared or any(
        p.is_symlink() or (p.is_file() and p.stat().st_nlink != 1) for p in root.rglob("*")
    ):
        raise ValueError("supplement inventory differs, or linked files found")
    cases = {name: load_case(root / name) for name in {m.case for m in ms}}
    for g in manifest.groups:
        supported = next((w for w in g.worlds if w.evidence_status == "supported"), None)
        contrast = next((w for w in g.worlds if w.evidence_status == g.contrast_status), None)
        if (
            supported is None
            or contrast is None
            or supported.parent_world_id is not None
            or contrast.parent_world_id != supported.world_id
            or supported.qualified_case is not None
            or contrast.qualified_case is None
        ):
            raise ValueError("paired world ancestry or qualified variant invalid")
        by_world = {w.world_id: w for w in g.worlds}
        roles = Counter((m.world_id, m.response_kind) for m in g.members)
        if roles != Counter(
            {
                (supported.world_id, "assert"): 1,
                (supported.world_id, "withhold"): 1,
                (contrast.world_id, "assert"): 1,
                (contrast.world_id, "withhold"): 1,
                (contrast.world_id, "qualified"): 1,
            }
        ):
            raise ValueError("group must have five declared response paths")
        c0, _ = cases[supported.mechanical_case]
        c1, _ = cases[contrast.mechanical_case]
        cq, dq = cases[contrast.qualified_case]
        if c0.subject != c1.subject or c1.subject != cq.subject or c1.world != cq.world:
            raise ValueError("paired subject interface or qualified logical world differs")
        if c1.evaluation.a1_evidence != cq.evaluation.a1_evidence:
            raise ValueError("qualified variant changes authored evidence declarations")
        if c0.case_id not in c1.derivation_ids or c1.case_id not in cq.derivation_ids:
            raise ValueError("qualified evaluation-contract variant must record derivation")
        for m in g.members:
            w = by_world[m.world_id]
            case, doc = cases[m.case]
            traj = load_trajectory(root / m.trajectory)
            if case.root_scenario_id != g.root_scenario_id or case.split != "commissioning_dev":
                raise ValueError("case root/split differs")
            if case.reviews or case.provenance.private_material or case.provenance.rights_status != "pending":
                raise ValueError(
                    "development cases must have no review/private material or fabricated rights"
                )
            if traj["trajectory_id"] != m.trajectory_id or traj["case_id"] != case.case_id:
                raise ValueError("trajectory binding differs")
            if "decline" not in case.subject.allowed_tools:
                raise ValueError("every case must allow executable abstention")
            a1 = case.evaluation.a1_evidence
            if a1 is None or len(a1.findings) != 1 or a1.findings[0].evidence_status != w.evidence_status:
                raise ValueError("world evidence declaration differs")
            qualified = m.response_kind == "qualified"
            if (
                m.requires_human_review != qualified
                or case.evaluation.scoring_mode != ("hybrid" if qualified else "mechanical")
                or len(case.evaluation.human_rubric) != int(qualified)
            ):
                raise ValueError("48 mechanical and 12 judgment-heavy trajectories must stay separate")
            expected_case = w.qualified_case if qualified else w.mechanical_case
            if m.case != expected_case:
                raise ValueError("response bound to wrong evaluation-contract variant")
            if not qualified:
                expected = (
                    "pass" if (w.evidence_status == "supported") == (m.response_kind == "assert") else "fail"
                )
                if m.expected.mechanical != expected or m.expected.conduct != expected:
                    raise ValueError("authored mechanical control expectation differs from B59")
            elif m.expected.conduct != ("fail" if m.expected.mechanical == "fail" else "pending_review"):
                raise ValueError("qualified contracts cannot automatically earn conduct credit")
            for ref in m.criterion_refs:
                if not ref.startswith(
                    ("/evaluation/pass_if", "/evaluation/fail_if", "/evaluation/human_rubric/")
                ):
                    raise ValueError("criterion reference outside frozen predicates/rubric")
                exists, _ = resolve_pointer(doc, ref)
                if not exists:
                    raise ValueError("criterion reference does not resolve")
    qualified_ids = {m.trajectory_id for m in ms if m.requires_human_review}
    if {c.trajectory_id for c in grid.cells} != qualified_ids or len({c.cell_id for c in grid.cells}) != 12:
        raise ValueError("grid must contain exactly one blank criterion-bound cell per qualified trajectory")
    by_id = {m.trajectory_id: m for m in ms}
    for cell in grid.cells:
        m = by_id[cell.trajectory_id]
        case, doc = cases[cell.case]
        assert case.evaluation.a1_evidence is not None
        exists, criterion = resolve_pointer(doc, cell.criterion_ref)
        if (
            cell.case != m.case
            or not exists
            or sha256_obj(criterion) != cell.criterion_sha256
            or cell.finding_id != case.evaluation.a1_evidence.findings[0].finding_id
        ):
            raise ValueError("grid criterion binding differs")
    return {
        "schema_id": "hs-a1-structure-report/1",
        "status": "valid",
        "counts": want,
        "authorship": manifest.authorship,
        "independent_observations": False,
        "independent_experimental_authorship": False,
    }
