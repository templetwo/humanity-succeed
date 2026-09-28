"""WP3 commissioning: the shared contract (BUILD_SPEC §5.2, §9, §12, WP3; docs/WP3_DESIGN.md).

Written by the lead before fan-out. Builders must NOT edit this file; report defects instead.
Every module in ``humanity_succeed.commissioning`` and the suite generator depend on it.

Commissioning checks the *evaluator* against constructed trajectories whose expected outcomes are
written as specification before any run. A golden expectation here is the author's statement of
what the evaluator should conclude; it is never measured from the evaluator (that would make
commissioning circular). A miss stays in the record; it is not "fixed" by editing the expectation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

SUITE_SCHEMA = "hs-commission-suite/1"
PLAN_SCHEMA = "hs-commission-plan/1"
REPORT_SCHEMA = "hs-commission-report/1"
CUSTODY_SCHEMA = "hs-holdback-custody/1"
SUITE_MANIFEST_NAME = "SUITE.json"  # at the suite root; cases/ and trajectories/ sit beside it

ID = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
RelPath = Annotated[str, Field(pattern=r"^(cases|trajectories)/[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
                                      r"\.yaml$")]
NonEmpty = Annotated[str, Field(min_length=1)]

ClassId = Literal[
    "C1_correction_claim",
    "C2_blocked_chosen",
    "C3_refusal",
    "C4_error_false_alarm",
    "C5_requested_substitution",
    "C6_multiple_paths",
    "C7_reversed_goal",
]


@dataclass(frozen=True)
class ClassSpec:
    class_id: str
    title: str
    shape: Literal["pair", "triplet"]
    groups: int            # groups in the full 160-trajectory suite
    holdback_groups: int   # groups held back (BUILD_SPEC §9)
    members: int           # trajectories per group
    pass_members: int      # members per group whose expected mechanical verdict is "pass"


# BUILD_SPEC §9: 24 correction/claim, 24 blocked/chosen, 24 justified/unnecessary refusal, 24
# real-error/false-alarm, 24 requested-work/substitution (12 matched pairs each), 24 multiple-paths
# (8 cases x 2 valid + 1 invalid), 16 reversed-goal (8 pairs). Hold back 2 pairs of each of the
# first five, 4 triplets, 4 feature pairs: 120 development + 40 held back.
CLASSES: tuple[ClassSpec, ...] = (
    ClassSpec("C1_correction_claim", "correction / claim", "pair", 12, 2, 2, 1),
    ClassSpec("C2_blocked_chosen", "blocked / chosen", "pair", 12, 2, 2, 1),
    ClassSpec("C3_refusal", "justified / unnecessary refusal", "pair", 12, 2, 2, 1),
    ClassSpec("C4_error_false_alarm", "real error / false alarm", "pair", 12, 2, 2, 1),
    ClassSpec("C5_requested_substitution", "requested work / substitution", "pair", 12, 2, 2, 1),
    ClassSpec("C6_multiple_paths", "multiple acceptable paths", "triplet", 8, 4, 3, 2),
    ClassSpec("C7_reversed_goal", "reversed-goal feature preservation", "pair", 8, 4, 2, 1),
)
CLASS_BY_ID = {c.class_id: c for c in CLASSES}
TOTAL_TRAJECTORIES = sum(c.groups * c.members for c in CLASSES)
HOLDBACK_TRAJECTORIES = sum(c.holdback_groups * c.members for c in CLASSES)
DEVELOPMENT_TRAJECTORIES = TOTAL_TRAJECTORIES - HOLDBACK_TRAJECTORIES
assert (TOTAL_TRAJECTORIES, DEVELOPMENT_TRAJECTORIES, HOLDBACK_TRAJECTORIES) == (160, 120, 40)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Expectation(_Strict):
    """What the evaluator SHOULD conclude, written before any run."""

    mechanical: Literal["pass", "fail", "not_evaluable"]
    conduct: Literal["pass", "fail", "pending_review", "not_evaluable"]
    contained: bool          # a monitor denial is expected in the record
    judgment_heavy: bool     # semantic commissioning needs two independent human reviews
    rationale: NonEmpty


class Member(_Strict):
    fixture_id: ID
    role: ID                 # e.g. real_correction, claim_only, path_a, invalid
    case: RelPath            # posix path relative to the suite root
    trajectory: RelPath
    expected: Expectation


class Group(_Strict):
    group_id: ID
    class_id: ClassId
    root_scenario_id: ID
    members: Annotated[list[Member], Field(min_length=2, max_length=3)]


class SuiteManifest(_Strict):
    schema_id: Literal["hs-commission-suite/1"]
    suite_id: ID
    authorship: Literal["builder_constructed", "custodian_supplied"]
    authored_by: NonEmpty
    split: Literal["commissioning_dev", "commissioning_holdback"]
    groups: list[Group]
    note: NonEmpty


class CustodyRecord(_Strict):
    """Written and kept by a named holdback custodian who is not the builder (BUILD_SPEC §5.2)."""

    schema_id: Literal["hs-holdback-custody/1"]
    custodian: NonEmpty                      # a person or role, never the builder seat
    holdback_suite_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    sealed_at_utc: NonEmpty
    statement: NonEmpty                      # how the custodian kept it out of builder reach


# Statuses the report may use. Nothing else is allowed in these fields.
MECHANICAL_STATUSES = ("development_all_expectations_met", "development_expectations_missed")
FORMAL_STATUSES = ("blocked_no_independent_holdback", "blocked_holdback_exposed",
                   "blocked_custody_invalid", "passed", "failed")
SEMANTIC_STATUSES = ("pending_no_human_reviews",)
# BUILD_SPEC §9 lifecycle; commissioning can reach at most instrument_commissioned, and only with
# formal=passed AND semantic review complete. Without both it stays mechanically_validated or below.
LIFECYCLE_STATES = ("draft", "mechanically_validated", "instrument_commissioned")
CLAIM_BOUNDARY = (
    "Constructed, related, development-influenced trajectories. A result here reports exactly "
    "which fixtures met their written expectations; it is not a population error bound and not "
    "a behavioral result about any model. No model was called."
)


# ---------------------------------------------------------------- validation (shared)


def manifest_path(suite_root: Path) -> Path:
    return Path(suite_root) / SUITE_MANIFEST_NAME


def suite_problems(manifest: SuiteManifest, suite_root: Path, *, fragment: bool = False) -> list[str]:
    """Structural problems in a suite. ``fragment=False``: the full 160-trajectory builder suite.
    ``fragment=True``: a custodian holdback suite with exactly ``holdback_groups`` per class.

    Checks counts and shapes, per-group pass counts, unique ids, relative paths that stay inside
    the suite, files that exist, and that every trajectory is bound to its member's case, every
    case carries the manifest's split, and every case in a group shares the group's root.
    Loading uses the project's strict loaders; nothing here runs a trajectory.
    """
    from ..contracts.case import semantic_problems
    from ..runner.scripted import load_case, load_trajectory

    probs: list[str] = []
    root = Path(suite_root)
    want_field = "holdback_groups" if fragment else "groups"
    by_class: dict[str, list[Group]] = {}
    for g in manifest.groups:
        by_class.setdefault(g.class_id, []).append(g)
    for spec in CLASSES:
        n = len(by_class.get(spec.class_id, []))
        if n != getattr(spec, want_field):
            probs.append(f"{spec.class_id}: {n} groups, expected {getattr(spec, want_field)}")
    seen_groups, seen_fixtures, seen_files = set(), set(), set()
    for g in manifest.groups:
        spec = CLASS_BY_ID[g.class_id]
        if g.group_id in seen_groups:
            probs.append(f"duplicate group_id {g.group_id}")
        seen_groups.add(g.group_id)
        if len(g.members) != spec.members:
            probs.append(f"{g.group_id}: {len(g.members)} members, {spec.shape} needs "
                         f"{spec.members}")
        passes = sum(m.expected.mechanical == "pass" for m in g.members)
        if passes != spec.pass_members:
            probs.append(f"{g.group_id}: {passes} pass-expected members, expected "
                         f"{spec.pass_members}")
        for m in g.members:
            if m.fixture_id in seen_fixtures:
                probs.append(f"duplicate fixture_id {m.fixture_id}")
            seen_fixtures.add(m.fixture_id)
            if m.trajectory in seen_files:
                probs.append(f"{m.fixture_id}: trajectory file reused")
            seen_files.add(m.trajectory)
            for rel in (m.case, m.trajectory):
                p = PurePosixPath(rel)
                if p.is_absolute() or ".." in p.parts:
                    probs.append(f"{m.fixture_id}: path {rel!r} escapes the suite")
            cpath, tpath = root / m.case, root / m.trajectory
            if cpath.is_symlink() or tpath.is_symlink():
                probs.append(f"{m.fixture_id}: symlinked fixture file refused")
                continue
            if not cpath.is_file() or not tpath.is_file():
                probs.append(f"{m.fixture_id}: missing {m.case if not cpath.is_file() else m.trajectory}")
                continue
            try:
                case, _ = load_case(cpath)
                traj = load_trajectory(tpath)
            except Exception as e:  # noqa: BLE001 - report every broken fixture, do not stop
                probs.append(f"{m.fixture_id}: unloadable fixture: {e}")
                continue
            probs += [f"{m.fixture_id}: {p}" for p in semantic_problems(case)]
            if traj["case_id"] != case.case_id:
                probs.append(f"{m.fixture_id}: trajectory bound to {traj['case_id']!r}, case is "
                             f"{case.case_id!r}")
            if case.split != manifest.split:
                probs.append(f"{m.fixture_id}: case split {case.split!r} != suite split "
                             f"{manifest.split!r}")
            if case.root_scenario_id != g.root_scenario_id:
                probs.append(f"{m.fixture_id}: case root {case.root_scenario_id!r} != group root "
                             f"{g.root_scenario_id!r}")
    return probs


__all__ = [
    "CLASSES", "CLASS_BY_ID", "ClassSpec", "Expectation", "Member", "Group", "SuiteManifest",
    "CustodyRecord", "SUITE_SCHEMA", "PLAN_SCHEMA", "REPORT_SCHEMA", "CUSTODY_SCHEMA",
    "SUITE_MANIFEST_NAME", "TOTAL_TRAJECTORIES", "DEVELOPMENT_TRAJECTORIES",
    "HOLDBACK_TRAJECTORIES", "MECHANICAL_STATUSES", "FORMAL_STATUSES", "SEMANTIC_STATUSES",
    "LIFECYCLE_STATES", "CLAIM_BOUNDARY", "manifest_path", "suite_problems",
]
