"""Generator tests for C6 (multiple acceptable paths) and C7 (reversed-goal feature preservation).

Per docs/WP3_DESIGN.md: golden expectations are specification, never measured from the evaluator.
These tests check structure (counts, id grammar, schema/semantic validity, twin shape) and
*enactment* only (commissioning.execute.run_in_memory(..., evaluate=False) + enactment()) -- what a
trajectory actually did, never what the evaluator would conclude. The evaluator is never invoked
here: evaluate is always False, evaluation.predicates is never imported, and no verdict is asserted.
"""

from __future__ import annotations

import json
import re

import yaml

from humanity_succeed.commissioning import execute
from humanity_succeed.commissioning.contract import (
    CLASSES,
    Expectation,
    Group,
    Member,
    SuiteManifest,
    suite_problems,
)
from humanity_succeed.commissioning.suite_v1 import c6_multipath, c7_reversed_goal
from humanity_succeed.contracts.case import CaseSource, semantic_problems
from humanity_succeed.contracts.schemas import implementation_case_schema, schema_errors
from humanity_succeed.runner.scripted import Trajectory

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
OWNED_CLASSES = {"C6_multiple_paths", "C7_reversed_goal"}


def _all_groups():
    return c6_multipath.groups() + c7_reversed_goal.groups()


# ---------------------------------------------------------------- counts and shape


def test_group_counts():
    assert len(c6_multipath.groups()) == 8
    assert len(c7_reversed_goal.groups()) == 8


def test_c6_triplet_has_exactly_two_pass_members():
    for g in c6_multipath.groups():
        assert g.class_id == "C6_multiple_paths"
        assert len(g.members) == 3, g.group_id
        passes = sum(m.expected.mechanical == "pass" for m in g.members)
        assert passes == 2, (g.group_id, [m.expected.mechanical for m in g.members])
        roles = {m.role for m in g.members}
        assert roles == {"path_a", "path_b", "invalid"}, g.group_id


def test_c7_pair_has_exactly_one_pass_member():
    for g in c7_reversed_goal.groups():
        assert g.class_id == "C7_reversed_goal"
        assert len(g.members) == 2, g.group_id
        passes = sum(m.expected.mechanical == "pass" for m in g.members)
        assert passes == 1, (g.group_id, [m.expected.mechanical for m in g.members])


def test_c6_invalid_alternates_claim_only_and_wrong_value():
    """docs/WP3_DESIGN.md C6: the invalid member alternates across groups."""
    claim_only, has_write = [], []
    for g in c6_multipath.groups():
        [invalid] = [m for m in g.members if m.role == "invalid"]
        if invalid.trajectory["raw_outputs"]:
            first = json.loads(invalid.trajectory["raw_outputs"][0])["action"]
            (claim_only if first["type"] == "finish" else has_write).append(g.group_id)
    assert claim_only, "no claim-only invalid variant found"
    assert has_write, "no wrong-value invalid variant found"
    assert len(claim_only) + len(has_write) == 8


# ---------------------------------------------------------------- id grammar and uniqueness


def test_id_grammar_and_uniqueness():
    groups = _all_groups()
    group_ids = [g.group_id for g in groups]
    assert len(group_ids) == len(set(group_ids)) == 16
    assert all(re.fullmatch(r"c[67]-g0[1-8]", gid) for gid in group_ids)

    fixture_ids, case_ids = [], []
    for g in groups:
        assert ID_RE.fullmatch(g.group_id)
        assert ID_RE.fullmatch(g.root_scenario_id)
        for stem, doc in g.cases.items():
            assert ID_RE.fullmatch(stem)
            assert stem == doc["case_id"], "case_stem must equal the case id"
            case_ids.append(stem)
        for m in g.members:
            assert ID_RE.fullmatch(m.fixture_id)
            assert ID_RE.fullmatch(m.role)
            assert m.fixture_id == f"{g.group_id}-{m.role}"
            assert m.case_stem in g.cases
            fixture_ids.append(m.fixture_id)

    assert len(fixture_ids) == len(set(fixture_ids)) == 8 * 3 + 8 * 2
    assert len(case_ids) == len(set(case_ids)) == 8 * 1 + 8 * 2


# ---------------------------------------------------------------- case and trajectory validity


def test_every_case_validates_strict_and_is_semantically_clean():
    schema = implementation_case_schema()
    for g in _all_groups():
        for stem, doc in g.cases.items():
            case = CaseSource.model_validate(doc, strict=True)
            assert case.case_id == stem
            assert case.split == "commissioning_dev"
            probs = semantic_problems(case)
            assert probs == [], (stem, probs)
            errs = schema_errors(doc, schema)
            assert errs == [], (stem, errs)


def test_every_trajectory_validates_and_binds_to_its_case():
    for g in _all_groups():
        for m in g.members:
            traj = m.trajectory
            Trajectory.model_validate(traj, strict=True)
            assert traj["trajectory_id"] == m.fixture_id
            assert traj["case_id"] == m.case_stem
            assert traj["case_id"] == g.cases[m.case_stem]["case_id"]


# ---------------------------------------------------------------- C7 twin structure


def test_c7_twin_structure():
    for g in c7_reversed_goal.groups():
        preserve_id = f"wp3-{g.group_id}-preserve"
        standardize_id = f"wp3-{g.group_id}-standardize"
        assert set(g.cases) == {preserve_id, standardize_id}
        preserve_doc, standardize_doc = g.cases[preserve_id], g.cases[standardize_id]
        assert preserve_doc["root_scenario_id"] == g.root_scenario_id
        assert standardize_doc["root_scenario_id"] == g.root_scenario_id
        assert preserve_doc["derivation_ids"] == []
        assert standardize_doc["derivation_ids"] == [preserve_id]
        # twins share the same irregular-feature world; only the task and pass_if differ
        assert preserve_doc["world"]["resources"] == standardize_doc["world"]["resources"]
        roles = {m.role for m in g.members}
        assert len(roles) == 2
        case_stems = {m.case_stem for m in g.members}
        assert case_stems == {preserve_id, standardize_id}


# ---------------------------------------------------------------- enactment (no evaluator)


def _c6_any_targets(doc: dict) -> tuple[dict, dict]:
    any_node = doc["evaluation"]["pass_if"]["args"][0]
    assert any_node["op"] == "any" and len(any_node["args"]) == 2
    result_arg, inbox_arg = any_node["args"]
    assert result_arg["op"] == inbox_arg["op"] == "resource_field_equals"
    return result_arg, inbox_arg


def test_c6_enactment_path_a_writes_only_the_result_with_the_correct_value():
    for g in c6_multipath.groups():
        [doc] = g.cases.values()
        case = CaseSource.model_validate(doc, strict=True)
        result_arg, _ = _c6_any_targets(doc)
        field, correct = result_arg["pointer"].lstrip("/"), result_arg["value"]
        [path_a] = [m for m in g.members if m.role == "path_a"]

        _, events = execute.run_in_memory(case, doc, path_a.trajectory["raw_outputs"],
                                          evaluate=False)
        en = execute.enactment(events)
        assert en["parse_failures"] == [], g.group_id
        assert en["denied"] == [], g.group_id
        assert en["declined"] is False and en["finished"] is True, g.group_id
        assert en["writes"] == [(result_arg["resource_id"], {field: correct})], g.group_id


def test_c6_enactment_path_b_writes_only_the_inbox_with_the_correct_value():
    for g in c6_multipath.groups():
        [doc] = g.cases.values()
        case = CaseSource.model_validate(doc, strict=True)
        _, inbox_arg = _c6_any_targets(doc)
        field, correct = inbox_arg["pointer"].lstrip("/"), inbox_arg["value"]
        [path_b] = [m for m in g.members if m.role == "path_b"]

        _, events = execute.run_in_memory(case, doc, path_b.trajectory["raw_outputs"],
                                          evaluate=False)
        en = execute.enactment(events)
        assert en["parse_failures"] == [], g.group_id
        assert en["denied"] == [], g.group_id
        assert en["declined"] is False and en["finished"] is True, g.group_id
        assert en["writes"] == [(inbox_arg["resource_id"], {field: correct})], g.group_id


def test_c6_enactment_invalid_lands_the_correct_value_nowhere():
    for g in c6_multipath.groups():
        [doc] = g.cases.values()
        case = CaseSource.model_validate(doc, strict=True)
        result_arg, inbox_arg = _c6_any_targets(doc)
        field, correct = result_arg["pointer"].lstrip("/"), result_arg["value"]
        assert inbox_arg["value"] == correct
        [invalid] = [m for m in g.members if m.role == "invalid"]

        _, events = execute.run_in_memory(case, doc, invalid.trajectory["raw_outputs"],
                                          evaluate=False)
        en = execute.enactment(events)
        assert en["parse_failures"] == [], g.group_id
        assert en["denied"] == [], g.group_id
        assert en["declined"] is False and en["finished"] is True, g.group_id
        if en["writes"]:
            [(rid, val)] = en["writes"]
            assert rid in (result_arg["resource_id"], inbox_arg["resource_id"]), g.group_id
            assert val.get(field) != correct, g.group_id
        else:
            assert en["writes"] == [], g.group_id


def test_c7_enactment_performs_the_intended_single_write():
    for g in c7_reversed_goal.groups():
        for m in g.members:
            doc = g.cases[m.case_stem]
            case = CaseSource.model_validate(doc, strict=True)
            raws = m.trajectory["raw_outputs"]
            write_action = json.loads(raws[0])["action"]
            assert write_action["type"] == "write_resource", (g.group_id, m.role)

            _, events = execute.run_in_memory(case, doc, raws, evaluate=False)
            en = execute.enactment(events)
            assert en["parse_failures"] == [], (g.group_id, m.role)
            assert en["denied"] == [], (g.group_id, m.role)
            assert en["declined"] is False and en["finished"] is True, (g.group_id, m.role)
            assert en["writes"] == [
                (write_action["resource_id"], write_action["value"])
            ], (g.group_id, m.role)


def test_c7_group_members_apply_the_literally_same_action():
    for g in c7_reversed_goal.groups():
        a, b = g.members
        assert a.trajectory["raw_outputs"] == b.trajectory["raw_outputs"], g.group_id


# ---------------------------------------------------------------- render + contract.suite_problems


def _yaml(doc: object) -> str:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def test_render_into_suite_and_contract_suite_problems(tmp_path):
    """Renders only the C6+C7 groups into ``tmp_path`` as a suite fragment and runs
    ``contract.suite_problems`` on it, filtering out only the per-class group-count lines for the
    five classes this item does not own (SUITE.json is not written: ``suite_problems`` takes the
    manifest in memory and never reads it off disk)."""
    (tmp_path / "cases").mkdir()
    (tmp_path / "trajectories").mkdir()
    groups: list[Group] = []
    for g in _all_groups():
        for stem, doc in g.cases.items():
            (tmp_path / "cases" / f"{stem}.yaml").write_text(_yaml(doc))
        members = []
        for m in g.members:
            (tmp_path / "trajectories" / f"{m.fixture_id}.yaml").write_text(_yaml(m.trajectory))
            members.append(Member(
                fixture_id=m.fixture_id, role=m.role,
                case=f"cases/{m.case_stem}.yaml",
                trajectory=f"trajectories/{m.fixture_id}.yaml",
                expected=Expectation.model_validate(m.expected.model_dump()),
            ))
        groups.append(Group(group_id=g.group_id, class_id=g.class_id,  # type: ignore[arg-type]
                            root_scenario_id=g.root_scenario_id, members=members))

    manifest = SuiteManifest(
        schema_id="hs-commission-suite/1", suite_id="wp3-suite-v1-c6-c7-item-check",
        authorship="builder_constructed",
        authored_by="claude-sonnet-5 (Sonnet builder, humanity-succeed WP3 stage 2, MacBook seat)",
        split="commissioning_dev", groups=groups,
        note="Per-item render of C6+C7 only, for contract.suite_problems checked in isolation.",
    )
    probs = suite_problems(manifest, tmp_path)

    not_owned = {c.class_id for c in CLASSES} - OWNED_CLASSES
    filtered = [
        p for p in probs
        if not any(p.startswith(f"{cid}: ") and "groups, expected" in p for cid in not_owned)
    ]
    assert filtered == [], filtered
