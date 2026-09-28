"""Generator tests for WP3 commissioning classes C3 (justified/unnecessary refusal) and C5
(requested work / substitution) (docs/WP3_DESIGN.md).

These tests check the generator output against the design document and the shared contract. They
never run the evaluator: expectations are specification, not something measured here. Only
``commissioning.execute.enactment`` (verdict-free) is used to confirm each fixture's trajectory does
what its description says.
"""

from __future__ import annotations

import re

import pytest
import yaml

from humanity_succeed.commissioning.contract import (
    CLASS_BY_ID,
    Expectation,
    Group,
    Member,
    SuiteManifest,
    suite_problems,
)
from humanity_succeed.commissioning.execute import enactment, run_in_memory
from humanity_succeed.commissioning.suite_v1 import c3_refusal, c5_substitution
from humanity_succeed.contracts.case import CaseSource, semantic_problems
from humanity_succeed.contracts.schemas import implementation_case_schema, schema_errors
from humanity_succeed.runner.scripted import Trajectory

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
C3_GID_RE = re.compile(r"^c3-g(0[1-9]|1[0-2])$")
C5_GID_RE = re.compile(r"^c5-g(0[1-9]|1[0-2])$")

C3_GROUPS = c3_refusal.groups()
C5_GROUPS = c5_substitution.groups()


def _all_cases():
    """[(fixture_id-ish label, case_stem, case_doc), ...] across both classes."""
    out = []
    for g in (*C3_GROUPS, *C5_GROUPS):
        for stem, doc in g.cases.items():
            out.append((f"{g.group_id}:{stem}", stem, doc))
    return out


def _all_members():
    """[(group, member), ...] across both classes."""
    out = []
    for g in (*C3_GROUPS, *C5_GROUPS):
        for m in g.members:
            out.append((g, m))
    return out


# ---------------------------------------------------------------- counts, classes, id grammar


def test_c3_returns_twelve_groups_of_class_c3_refusal():
    assert len(C3_GROUPS) == 12
    assert all(g.class_id == "C3_refusal" for g in C3_GROUPS)
    assert CLASS_BY_ID["C3_refusal"].groups == 12
    assert CLASS_BY_ID["C3_refusal"].shape == "pair"


def test_c5_returns_twelve_groups_of_class_c5_requested_substitution():
    assert len(C5_GROUPS) == 12
    assert all(g.class_id == "C5_requested_substitution" for g in C5_GROUPS)
    assert CLASS_BY_ID["C5_requested_substitution"].groups == 12
    assert CLASS_BY_ID["C5_requested_substitution"].shape == "pair"


def test_c3_group_ids_follow_grammar_and_are_unique():
    gids = [g.group_id for g in C3_GROUPS]
    assert gids == [f"c3-g{i:02d}" for i in range(1, 13)]
    assert all(C3_GID_RE.match(g) for g in gids)
    assert len(set(gids)) == len(gids)


def test_c5_group_ids_follow_grammar_and_are_unique():
    gids = [g.group_id for g in C5_GROUPS]
    assert gids == [f"c5-g{i:02d}" for i in range(1, 13)]
    assert all(C5_GID_RE.match(g) for g in gids)
    assert len(set(gids)) == len(gids)


def test_fixture_ids_follow_gid_role_grammar_and_are_globally_unique():
    all_fixture_ids = []
    for g in (*C3_GROUPS, *C5_GROUPS):
        for m in g.members:
            assert m.fixture_id == f"{g.group_id}-{m.role}"
            assert ID_RE.match(m.fixture_id)
            all_fixture_ids.append(m.fixture_id)
    assert len(set(all_fixture_ids)) == len(all_fixture_ids)


def test_case_ids_follow_grammar_and_are_globally_unique():
    all_case_ids = []
    for g in (*C3_GROUPS, *C5_GROUPS):
        for stem, doc in g.cases.items():
            assert ID_RE.match(doc["case_id"])
            assert stem == doc["case_id"], "case_stem must equal the case id"
            all_case_ids.append(doc["case_id"])
    assert len(set(all_case_ids)) == len(all_case_ids)


def test_c3_case_ids_use_twin_grammar():
    for g in C3_GROUPS:
        assert set(g.cases) == {f"wp3-{g.group_id}-justified", f"wp3-{g.group_id}-unnecessary"}


def test_c5_case_ids_use_single_case_grammar():
    for g in C5_GROUPS:
        assert set(g.cases) == {f"wp3-{g.group_id}"}


# ---------------------------------------------------------------- roles and pass counts


def test_c3_roles_and_pass_count_per_group():
    spec = CLASS_BY_ID["C3_refusal"]
    for g in C3_GROUPS:
        roles = {m.role for m in g.members}
        assert roles == {"justified", "unnecessary"}
        passes = sum(m.expected.mechanical == "pass" for m in g.members)
        assert passes == spec.pass_members == 1
        by_role = {m.role: m.expected for m in g.members}
        assert (by_role["justified"].mechanical, by_role["justified"].conduct,
               by_role["justified"].contained, by_role["justified"].judgment_heavy) == (
            "pass", "pass", False, False)
        assert (by_role["unnecessary"].mechanical, by_role["unnecessary"].conduct,
               by_role["unnecessary"].contained, by_role["unnecessary"].judgment_heavy) == (
            "fail", "fail", False, False)


def test_c5_roles_and_pass_count_per_group():
    spec = CLASS_BY_ID["C5_requested_substitution"]
    for g in C5_GROUPS:
        roles = {m.role for m in g.members}
        assert roles == {"requested", "substitution"}
        passes = sum(m.expected.mechanical == "pass" for m in g.members)
        assert passes == spec.pass_members == 1
        by_role = {m.role: m.expected for m in g.members}
        assert (by_role["requested"].mechanical, by_role["requested"].conduct,
               by_role["requested"].contained, by_role["requested"].judgment_heavy) == (
            "pass", "pass", False, False)
        assert (by_role["substitution"].mechanical, by_role["substitution"].conduct,
               by_role["substitution"].contained, by_role["substitution"].judgment_heavy) == (
            "fail", "fail", False, False)


# ---------------------------------------------------------------- twin root / derivation structure


def test_c3_twin_root_and_derivation_structure():
    for g in C3_GROUPS:
        justified = g.cases[f"wp3-{g.group_id}-justified"]
        unnecessary = g.cases[f"wp3-{g.group_id}-unnecessary"]
        assert justified["root_scenario_id"] == g.root_scenario_id == f"root-wp3-{g.group_id}"
        assert unnecessary["root_scenario_id"] == g.root_scenario_id
        assert justified["derivation_ids"] == []
        assert unnecessary["derivation_ids"] == [justified["case_id"]]


def test_c5_single_case_shared_by_two_members_same_root():
    for g in C5_GROUPS:
        [case_doc] = g.cases.values()
        assert case_doc["root_scenario_id"] == g.root_scenario_id == f"root-wp3-{g.group_id}"
        stems = {m.case_stem for m in g.members}
        assert stems == set(g.cases)
        assert len(stems) == 1


# ---------------------------------------------------------------- twelve genuinely distinct scenarios


def test_c3_scenarios_are_genuinely_distinct():
    justified_docs = [g.cases[f"wp3-{g.group_id}-justified"] for g in C3_GROUPS]
    resource_ids = [next(iter(d["world"]["resources"])) for d in justified_docs]
    tasks = [d["subject"]["task"] for d in justified_docs]
    assert len(set(resource_ids)) == 12
    assert len(set(tasks)) == 12


def test_c5_scenarios_are_genuinely_distinct():
    docs = [next(iter(g.cases.values())) for g in C5_GROUPS]
    resource_ids = [next(iter(d["world"]["resources"])) for d in docs]
    tasks = [d["subject"]["task"] for d in docs]
    assert len(set(resource_ids)) == 12
    assert len(set(tasks)) == 12


# ---------------------------------------------------------------- schema and semantic validation


@pytest.mark.parametrize("label,stem,doc", _all_cases(), ids=lambda v: v if isinstance(v, str) else "")
def test_every_case_validates(label, stem, doc):
    assert schema_errors(doc, implementation_case_schema()) == []
    case = CaseSource.model_validate(doc, strict=True)
    assert semantic_problems(case) == []
    assert case.case_id == stem


# ---------------------------------------------------------------- trajectory validation and binding


@pytest.mark.parametrize("group,member", _all_members(),
                         ids=lambda v: v.fixture_id if hasattr(v, "fixture_id") else v.group_id)
def test_trajectory_validates_and_binds_to_its_case(group, member):
    Trajectory.model_validate(member.trajectory, strict=True)
    case_doc = group.cases[member.case_stem]
    assert member.trajectory["case_id"] == case_doc["case_id"]


# ---------------------------------------------------------------- enactment (verdict-free)


@pytest.mark.parametrize("group,member", [(g, m) for g in C3_GROUPS for m in g.members],
                         ids=lambda v: v.fixture_id if hasattr(v, "fixture_id") else v.group_id)
def test_c3_members_enact_a_clean_decline(group, member):
    case_doc = group.cases[member.case_stem]
    case = CaseSource.model_validate(case_doc, strict=True)
    ev, events = run_in_memory(case, case_doc, member.trajectory["raw_outputs"], evaluate=False)
    assert ev is None
    en = enactment(events)
    assert en["parse_failures"] == []
    assert en["denied"] == []
    assert en["writes"] == []
    assert en["declined"] is True
    assert en["finished"] is False


@pytest.mark.parametrize("group,member", [(g, m) for g in C5_GROUPS for m in g.members],
                         ids=lambda v: v.fixture_id if hasattr(v, "fixture_id") else v.group_id)
def test_c5_members_enact_exactly_one_write_and_finish(group, member):
    case_doc = group.cases[member.case_stem]
    case = CaseSource.model_validate(case_doc, strict=True)
    ev, events = run_in_memory(case, case_doc, member.trajectory["raw_outputs"], evaluate=False)
    assert ev is None
    en = enactment(events)
    assert en["parse_failures"] == []
    assert en["denied"] == []
    assert en["finished"] is True
    assert en["declined"] is False
    assert len(en["writes"]) == 1
    [(resource_id, new_value)] = en["writes"]

    [resource_id_expected] = case_doc["world"]["resources"]
    assert resource_id == resource_id_expected
    initial_value = case_doc["world"]["resources"][resource_id]["value"]

    changed_fields = {k for k in new_value if new_value.get(k) != initial_value.get(k)}
    unchanged_fields = {k for k in new_value if k not in changed_fields}
    assert unchanged_fields, "the untouched field must survive the write unchanged"
    for k in unchanged_fields:
        assert new_value[k] == initial_value[k]
    # Exactly one field changed: the target field.
    assert len(changed_fields) == 1
    (changed_field,) = changed_fields

    pass_if = case_doc["evaluation"]["pass_if"]
    [field_pred] = [p for p in pass_if["args"] if p["op"] == "resource_field_equals"]
    requested_value = field_pred["value"]
    assert field_pred["pointer"] == f"/{changed_field}"

    if member.role == "requested":
        assert new_value[changed_field] == requested_value
    else:
        assert member.role == "substitution"
        assert new_value[changed_field] != requested_value


# ---------------------------------------------------------------- suite_problems on a rendered suite


def _render_owned(tmp_path):
    """Render only the C3 and C5 groups into tmp_path as a suite (no other item's generators)."""
    files: dict[str, str] = {}
    groups: list[Group] = []
    for g in (*C3_GROUPS, *C5_GROUPS):
        for stem, doc in g.cases.items():
            rel = f"cases/{stem}.yaml"
            files[rel] = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
        members = []
        for m in g.members:
            rel = f"trajectories/{m.fixture_id}.yaml"
            files[rel] = yaml.safe_dump(m.trajectory, sort_keys=False, allow_unicode=True, width=100)
            members.append(Member(fixture_id=m.fixture_id, role=m.role,
                                  case=f"cases/{m.case_stem}.yaml", trajectory=rel,
                                  expected=Expectation.model_validate(m.expected.model_dump())))
        groups.append(Group(group_id=g.group_id, class_id=g.class_id,  # type: ignore[arg-type]
                            root_scenario_id=g.root_scenario_id, members=members))
    manifest = SuiteManifest(
        schema_id="hs-commission-suite/1", suite_id="wp3-suite-v1-c3-c5-test",
        authorship="builder_constructed", authored_by="test_gen_request_family",
        split="commissioning_dev", groups=groups,
        note="Test-only render of the C3+C5 generator output; not the assembled WP3 suite.")
    (tmp_path / "cases").mkdir()
    (tmp_path / "trajectories").mkdir()
    for rel, text in files.items():
        (tmp_path / rel).write_text(text)
    return manifest


def test_suite_problems_is_clean_for_the_classes_this_item_owns(tmp_path):
    manifest = _render_owned(tmp_path)
    probs = suite_problems(manifest, tmp_path)
    owned = {"C3_refusal", "C5_requested_substitution"}
    other_class_prefixes = tuple(f"{cid}: " for cid in CLASS_BY_ID if cid not in owned)
    remaining = [p for p in probs if not p.startswith(other_class_prefixes)]
    assert remaining == []
