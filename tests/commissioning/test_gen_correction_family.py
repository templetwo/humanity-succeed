"""Tests for the C1/C2/C4 suite generators (WP3 stage 2, disjoint build item).

Golden expectations are read from the generator modules as specification (docs/WP3_DESIGN.md,
"Golden expectations are specification"); nothing here calls the evaluator. Enactment checks only
what each trajectory *did* (commissioning.execute.enactment), never a verdict.
"""

from __future__ import annotations

import re

import pytest
import yaml

from humanity_succeed.commissioning.contract import (
    CLASS_BY_ID,
    CLASSES,
    Expectation,
    Group,
    Member,
    SuiteManifest,
    suite_problems,
)
from humanity_succeed.commissioning.execute import enactment, run_in_memory
from humanity_succeed.commissioning.suite_v1 import c1_correction, c2_blocked, c4_false_alarm
from humanity_succeed.contracts.case import CaseSource, semantic_problems
from humanity_succeed.contracts.schemas import implementation_case_schema, schema_errors
from humanity_succeed.runner.scripted import Trajectory

MODULES = {
    "C1_correction_claim": c1_correction,
    "C2_blocked_chosen": c2_blocked,
    "C4_error_false_alarm": c4_false_alarm,
}
OWNED_CLASS_IDS = frozenset(MODULES)

GROUP_ID_RE = {
    "C1_correction_claim": re.compile(r"^c1-g(0[1-9]|1[0-2])$"),
    "C2_blocked_chosen": re.compile(r"^c2-g(0[1-9]|1[0-2])$"),
    "C4_error_false_alarm": re.compile(r"^c4-g(0[1-9]|1[0-2])$"),
}
# role -> expected mechanical verdict, per docs/WP3_DESIGN.md
ROLE_MECH = {
    "C1_correction_claim": {"real_correction": "pass", "claim_only": "fail"},
    "C2_blocked_chosen": {"direct": "pass", "blocked_attempt": "fail"},
    "C4_error_false_alarm": {"real_error": "pass", "false_alarm": "fail"},
}


def _all_drafts() -> dict[str, list]:
    return {cid: mod.groups() for cid, mod in MODULES.items()}


def _case_for(group, member):
    return group.cases[member.case_stem]


# ---------------------------------------------------------------- shape and id grammar


@pytest.mark.parametrize("class_id", sorted(MODULES))
def test_group_count_and_grammar(class_id):
    gs = MODULES[class_id].groups()
    assert len(gs) == 12
    gid_re = GROUP_ID_RE[class_id]
    seen = set()
    for g in gs:
        assert g.class_id == class_id
        assert gid_re.fullmatch(g.group_id), g.group_id
        assert g.group_id not in seen
        seen.add(g.group_id)
        assert g.root_scenario_id == f"root-wp3-{g.group_id}"


@pytest.mark.parametrize("class_id", sorted(MODULES))
def test_member_roles_and_pass_counts(class_id):
    spec = CLASS_BY_ID[class_id]
    want = ROLE_MECH[class_id]
    for g in MODULES[class_id].groups():
        assert len(g.members) == spec.members
        assert {m.role for m in g.members} == set(want)
        passes = sum(1 for m in g.members if m.expected.mechanical == "pass")
        assert passes == spec.pass_members
        for m in g.members:
            assert m.expected.mechanical == want[m.role]
            assert m.fixture_id == f"{g.group_id}-{m.role}"


def test_ids_unique_within_and_across_modules():
    drafts = _all_drafts()
    group_ids: list[str] = []
    fixture_ids: list[str] = []
    case_stems: list[str] = []
    for gs in drafts.values():
        for g in gs:
            group_ids.append(g.group_id)
            case_stems.extend(g.cases.keys())
            fixture_ids.extend(m.fixture_id for m in g.members)
    assert len(group_ids) == len(set(group_ids)) == 36
    assert len(fixture_ids) == len(set(fixture_ids)) == 72
    assert len(case_stems) == len(set(case_stems))


def test_c4_twins_share_root_and_derivation():
    for g in c4_false_alarm.groups():
        assert len(g.cases) == 2
        real_id = f"wp3-{g.group_id}-real"
        false_id = f"wp3-{g.group_id}-false"
        real_doc = g.cases[real_id]
        false_doc = g.cases[false_id]
        assert real_doc["root_scenario_id"] == g.root_scenario_id
        assert false_doc["root_scenario_id"] == g.root_scenario_id
        assert real_doc["derivation_ids"] == []
        assert false_doc["derivation_ids"] == [real_id]


# ---------------------------------------------------------------- document validation


@pytest.mark.parametrize("class_id", sorted(MODULES))
def test_case_documents_validate(class_id):
    for g in MODULES[class_id].groups():
        for stem, doc in g.cases.items():
            assert doc["case_id"] == stem
            case = CaseSource.model_validate(doc, strict=True)
            assert semantic_problems(case) == []
            assert schema_errors(doc, implementation_case_schema()) == []


@pytest.mark.parametrize("class_id", sorted(MODULES))
def test_trajectories_validate_and_bind(class_id):
    for g in MODULES[class_id].groups():
        for m in g.members:
            Trajectory.model_validate(m.trajectory, strict=True)
            assert m.trajectory["case_id"] == m.case_stem


# ---------------------------------------------------------------- enactment (never the evaluator)


def _run(group, member):
    doc = _case_for(group, member)
    case = CaseSource.model_validate(doc, strict=True)
    _, events = run_in_memory(case, doc, member.trajectory["raw_outputs"], evaluate=False)
    return events


def _index_of_first(events, event_type):
    for i, e in enumerate(events):
        if e["event_type"] == event_type:
            return i
    return None


def _precedes(events, first_type, second_type) -> bool:
    i, j = _index_of_first(events, first_type), _index_of_first(events, second_type)
    return i is not None and j is not None and i < j


def test_c1_enactment():
    for g in c1_correction.groups():
        by_role = {m.role: m for m in g.members}

        events = _run(g, by_role["real_correction"])
        en = enactment(events)
        assert en["parse_failures"] == []
        assert en["denied"] == []
        assert len(en["writes"]) == 1
        assert len(en["notified"]) == 1
        assert en["finished"] is True
        assert en["declined"] is False
        assert _precedes(events, "resource_revised", "notification_delivered")

        events = _run(g, by_role["claim_only"])
        en = enactment(events)
        assert en["parse_failures"] == []
        assert en["denied"] == []
        assert en["writes"] == []
        assert en["notified"] == []
        assert en["finished"] is True


def test_c2_enactment():
    for g in c2_blocked.groups():
        by_role = {m.role: m for m in g.members}

        events = _run(g, by_role["direct"])
        en = enactment(events)
        assert en["parse_failures"] == []
        assert en["denied"] == []
        assert len(en["writes"]) == 1
        assert len(en["notified"]) == 1
        assert en["finished"] is True
        assert _precedes(events, "resource_revised", "notification_delivered")

        events = _run(g, by_role["blocked_attempt"])
        en = enactment(events)
        assert en["parse_failures"] == []
        assert en["denied"] == ["not_permitted"]
        assert len(en["writes"]) == 1
        assert len(en["notified"]) == 1
        assert en["finished"] is True
        assert _precedes(events, "action_denied", "resource_revised")
        assert _precedes(events, "resource_revised", "notification_delivered")


def test_c4_enactment():
    for g in c4_false_alarm.groups():
        by_role = {m.role: m for m in g.members}
        for role in ("real_error", "false_alarm"):
            events = _run(g, by_role[role])
            en = enactment(events)
            assert en["parse_failures"] == []
            assert en["denied"] == []
            assert len(en["writes"]) == 1
            assert len(en["notified"]) == 1
            assert en["finished"] is True
            assert _precedes(events, "resource_revised", "notification_delivered")


# ---------------------------------------------------------------- structural fragment (suite_problems)


def _render(tmp_path, group_drafts) -> SuiteManifest:
    cases_dir = tmp_path / "cases"
    traj_dir = tmp_path / "trajectories"
    cases_dir.mkdir(exist_ok=True)
    traj_dir.mkdir(exist_ok=True)
    groups = []
    for g in group_drafts:
        for stem, doc in g.cases.items():
            (cases_dir / f"{stem}.yaml").write_text(
                yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100))
        members = []
        for m in g.members:
            (traj_dir / f"{m.fixture_id}.yaml").write_text(
                yaml.safe_dump(m.trajectory, sort_keys=False, allow_unicode=True, width=100))
            members.append(Member(
                fixture_id=m.fixture_id, role=m.role, case=f"cases/{m.case_stem}.yaml",
                trajectory=f"trajectories/{m.fixture_id}.yaml",
                expected=Expectation.model_validate(m.expected.model_dump()),
            ))
        groups.append(Group(group_id=g.group_id, class_id=g.class_id,  # type: ignore[arg-type]
                            root_scenario_id=g.root_scenario_id, members=members))
    return SuiteManifest(
        schema_id="hs-commission-suite/1", suite_id="wp3-stage2-fragment",
        authorship="builder_constructed", authored_by="test", split="commissioning_dev",
        groups=groups, note="Stage-2 fragment: C1/C2/C4 generator output only, for suite_problems.",
    )


def test_suite_problems_on_owned_fragment(tmp_path):
    all_groups = [g for gs in _all_drafts().values() for g in gs]
    manifest = _render(tmp_path, all_groups)
    probs = suite_problems(manifest, tmp_path)

    def _is_foreign_count_line(p: str) -> bool:
        return any(
            spec.class_id not in OWNED_CLASS_IDS and p.startswith(f"{spec.class_id}:")
            and "groups, expected" in p
            for spec in CLASSES
        )

    assert [p for p in probs if not _is_foreign_count_line(p)] == []
