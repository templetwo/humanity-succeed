"""Tests for commissioning.partition, commissioning.custody, commissioning.agreement.

Partition and custody synthetic fixtures are built with only ``commissioning.fixtures`` and
``commissioning.contract`` -- never ``commissioning.suite_v1.*``, which is generated in parallel
this same stage -- so this test's stability never depends on code it does not own.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
import yaml

from humanity_succeed.canonical import canonical_str
from humanity_succeed.commissioning.agreement import agreement
from humanity_succeed.commissioning.contract import (
    CLASSES,
    SUITE_MANIFEST_NAME,
    ClassSpec,
    CustodyRecord,
    Expectation,
    Group,
    Member,
    SuiteManifest,
)
from humanity_succeed.commissioning.custody import (
    exposure_status,
    holdback_suite_sha256,
    ledger_path,
    load_custody,
    record_exposure,
)
from humanity_succeed.commissioning.fixtures import action, case_doc, trajectory_doc
from humanity_succeed.commissioning.partition import PartitionError, partition

# ==================================================================== partition


def _exp(mechanical: str) -> Expectation:
    return Expectation(mechanical=mechanical, conduct=mechanical, contained=False,
                      judgment_heavy=False, rationale="synthetic fixture; never run")


def _class_prefix(class_id: str) -> str:
    return class_id.split("_", 1)[0].lower()  # "C1_correction_claim" -> "c1"


def _synthetic_group(spec: ClassSpec, n: int) -> Group:
    """A structurally valid group for ``spec`` with placeholder paths that need not exist on disk
    -- ``partition()`` is structure-only and never touches the filesystem."""
    gid = f"{_class_prefix(spec.class_id)}-g{n:02d}"
    members = [
        Member(
            fixture_id=f"{gid}-f{i}", role=f"role_{i}",
            case=f"cases/{gid}-f{i}.yaml", trajectory=f"trajectories/{gid}-f{i}.yaml",
            expected=_exp("pass" if i < spec.pass_members else "fail"),
        )
        for i in range(spec.members)
    ]
    return Group(group_id=gid, class_id=spec.class_id, root_scenario_id=f"root-{gid}",
                members=members)


def _all_synthetic_groups() -> list[Group]:
    return [g for spec in CLASSES for g in
           (_synthetic_group(spec, n) for n in range(1, spec.groups + 1))]


def _full_manifest(*, groups: list[Group] | None = None,
                   suite_id: str = "wp3-suite-v1-test") -> SuiteManifest:
    return SuiteManifest(
        schema_id="hs-commission-suite/1", suite_id=suite_id, authorship="builder_constructed",
        authored_by="test harness", split="commissioning_dev",
        groups=groups if groups is not None else _all_synthetic_groups(), note="synthetic",
    )


def test_full_manifest_partitions_120_40_with_no_group_split():
    result = partition(_full_manifest())
    proof = result["proof"]
    assert (proof["total_trajectories"], proof["development_trajectories"],
           proof["holdback_trajectories"]) == (160, 120, 40)
    assert proof["groups_in_both"] == 0
    assert proof["fixtures_unassigned"] == 0
    assert proof["matches_section_9"] is True
    assert set(result["development"]).isdisjoint(result["holdback_designate"])
    assert len(result["holdback_designate"]) == sum(c.holdback_groups for c in CLASSES) == 18
    assert len(result["development"]) == sum(c.groups - c.holdback_groups for c in CLASSES)


def test_per_class_counts_match_the_contract():
    proof = partition(_full_manifest())["proof"]
    for spec in CLASSES:
        row = proof["per_class"][spec.class_id]
        assert row == {
            "groups": spec.groups,
            "development_groups": spec.groups - spec.holdback_groups,
            "holdback_groups": spec.holdback_groups,
            "development_trajectories": (spec.groups - spec.holdback_groups) * spec.members,
            "holdback_trajectories": spec.holdback_groups * spec.members,
        }


def test_fixture_partition_covers_every_fixture_exactly_once():
    manifest = _full_manifest()
    result = partition(manifest)
    all_fixture_ids = {m.fixture_id for g in manifest.groups for m in g.members}
    assert set(result["fixture_partition"]) == all_fixture_ids
    for g in manifest.groups:
        labels = {result["fixture_partition"][m.fixture_id] for m in g.members}
        assert len(labels) == 1  # a group is never split across development/holdback
        expect = "development" if g.group_id in result["development"] else "holdback_designate"
        assert labels == {expect}


def test_lists_and_dict_keys_are_sorted():
    result = partition(_full_manifest())
    assert result["development"] == sorted(result["development"])
    assert result["holdback_designate"] == sorted(result["holdback_designate"])


def test_order_independence():
    manifest = _full_manifest()
    baseline = partition(manifest)
    shuffled = list(manifest.groups)
    random.Random(20260926).shuffle(shuffled)
    assert shuffled != manifest.groups  # the shuffle actually changed the order
    reordered = manifest.model_copy(update={"groups": shuffled})
    assert partition(reordered) == baseline


def test_determinism():
    manifest = _full_manifest()
    assert partition(manifest) == partition(manifest)


def test_refuses_manifest_missing_a_group():
    groups = [g for g in _all_synthetic_groups() if g.group_id != "c1-g12"]
    with pytest.raises(PartitionError) as exc:
        partition(_full_manifest(groups=groups))
    assert "C1_correction_claim" in str(exc.value)


def test_refuses_group_with_wrong_member_count():
    groups = _all_synthetic_groups()
    bad = next(g for g in groups if g.group_id == "c6-g01")  # C6 is a triplet (3 members)
    groups = [g for g in groups if g.group_id != "c6-g01"]
    groups.append(bad.model_copy(update={"members": bad.members[:2]}))
    with pytest.raises(PartitionError) as exc:
        partition(_full_manifest(groups=groups))
    assert "c6-g01" in str(exc.value)


def test_proof_counters_are_counted_not_copied():
    """The per-class proof numbers come from the actual group split, not from
    ``contract.CLASSES``: feeding the counting machinery a deliberately wrong split (one group
    moved from development to holdback) must change what it reports, and the section-9 match must
    then fail."""
    from humanity_succeed.commissioning.partition import _class_counts, _matches_section_9

    def counts_for(spec: ClassSpec, n_dev: int, n_hb: int, hb_start: int) -> dict:
        dev = [_synthetic_group(spec, n) for n in range(1, n_dev + 1)]
        hb = [_synthetic_group(spec, n) for n in range(hb_start, hb_start + n_hb)]
        return _class_counts(spec, dev, hb)

    correct = {
        spec.class_id: counts_for(spec, spec.groups - spec.holdback_groups, spec.holdback_groups,
                                  hb_start=1000)
        for spec in CLASSES
    }
    total = sum(r["development_trajectories"] + r["holdback_trajectories"] for r in correct.values())
    dev_total = sum(r["development_trajectories"] for r in correct.values())
    hb_total = sum(r["holdback_trajectories"] for r in correct.values())
    assert _matches_section_9(correct, total, dev_total, hb_total) is True

    spec0 = CLASSES[0]
    tampered = dict(correct)
    # One fewer development group, one more holdback group than section 9 specifies for spec0.
    tampered[spec0.class_id] = counts_for(
        spec0, spec0.groups - spec0.holdback_groups - 1, spec0.holdback_groups + 1, hb_start=1000)
    t_total = sum(r["development_trajectories"] + r["holdback_trajectories"]
                 for r in tampered.values())
    t_dev = sum(r["development_trajectories"] for r in tampered.values())
    t_hb = sum(r["holdback_trajectories"] for r in tampered.values())
    # The moved group carries its own members with it, so the recount (not a copy of the
    # contract's numbers) shows the shift directly, and the section-9 match catches it.
    assert (t_dev, t_hb) != (dev_total, hb_total)
    assert tampered[spec0.class_id] != correct[spec0.class_id]
    assert _matches_section_9(tampered, t_total, t_dev, t_hb) is False


# ==================================================================== custody


def _generic_holdback_case(*, case_id: str, root_scenario_id: str, class_id: str,
                           split: str) -> dict:
    return case_doc(
        case_id=case_id, root_scenario_id=root_scenario_id, class_id=class_id,
        task="Simulated holdback custody test fixture. No real person is involved.",
        resources={"r_card": {"title": "draft", "servings": 4}},
        actors=["actor_reviewer"], readable=["r_card"], writable=["r_card"],
        notifiable=["actor_reviewer"],
        allowed_tools=["read_resource", "write_resource", "notify", "finish"],
        evaluation={
            "scoring_mode": "mechanical",
            "pass_if": {"op": "resource_field_equals", "resource_id": "r_card",
                       "pointer": "/title", "value": "final"},
            "fail_if": [],
            "human_rubric": [],
            "scope_limitations": ["synthetic holdback custody test fixture, not suite v1"],
        },
        drafting_model="test-harness (WP3 partition/custody tests)", split=split,
    )


def _build_holdback_suite(root: Path, *, authorship: str = "custodian_supplied",
                          split: str = "commissioning_holdback",
                          suite_id: str = "wp3-holdback-test") -> SuiteManifest:
    """A synthetic, on-disk holdback fragment spanning every class's ``holdback_groups`` count (18
    groups, 40 trajectories total -- contract.py's §9 holdback shape), built only from
    ``commissioning.fixtures``/``commissioning.contract``."""
    (root / "cases").mkdir(parents=True, exist_ok=True)
    (root / "trajectories").mkdir(parents=True, exist_ok=True)
    groups: list[Group] = []
    for spec in CLASSES:
        for n in range(1, spec.holdback_groups + 1):
            gid = f"hb-{_class_prefix(spec.class_id)}-g{n:02d}"
            root_id = f"root-{gid}"
            case_id = f"wp3-holdback-{gid}"
            case = _generic_holdback_case(case_id=case_id, root_scenario_id=root_id,
                                          class_id=spec.class_id, split=split)
            (root / "cases" / f"{gid}.yaml").write_text(
                yaml.safe_dump(case, sort_keys=False, allow_unicode=True, width=100))
            members = []
            for i in range(spec.members):
                fid = f"{gid}-f{i}"
                traj = trajectory_doc(
                    trajectory_id=fid, case_id=case_id,
                    description=f"synthetic holdback fixture {fid}",
                    raws=[action(type="finish", summary="synthetic completion",
                                delivered_resource_ids=["r_card"])],
                    drafting_model="test-harness (WP3 partition/custody tests)",
                )
                (root / "trajectories" / f"{fid}.yaml").write_text(
                    yaml.safe_dump(traj, sort_keys=False, allow_unicode=True, width=100))
                members.append(Member(
                    fixture_id=fid, role=f"role_{i}", case=f"cases/{gid}.yaml",
                    trajectory=f"trajectories/{fid}.yaml",
                    expected=_exp("pass" if i < spec.pass_members else "fail"),
                ))
            groups.append(Group(group_id=gid, class_id=spec.class_id, root_scenario_id=root_id,
                                members=members))
    manifest = SuiteManifest(
        schema_id="hs-commission-suite/1", suite_id=suite_id, authorship=authorship, split=split,
        authored_by="test custodian (not the builder seat)", groups=groups,
        note="synthetic custodian-style holdback fixture, built for commissioning custody tests",
    )
    (root / SUITE_MANIFEST_NAME).write_text(canonical_str(manifest.model_dump(mode="json")) + "\n")
    return manifest


def _custody_record(sha256: str, **overrides) -> CustodyRecord:
    fields = {
        "schema_id": "hs-holdback-custody/1",
        "custodian": "Independent reviewer (not the builder seat)",
        "holdback_suite_sha256": sha256,
        "sealed_at_utc": "2026-09-26T00:00:00Z",
        "statement": "Sealed on a device the builder never accessed; kept outside the repo and "
                    "the state root.",
    }
    fields.update(overrides)
    return CustodyRecord(**fields)


def _write_custody(path: Path, record: CustodyRecord) -> None:
    path.write_text(canonical_str(record.model_dump(mode="json")))


def _flip_hex(digest: str) -> str:
    return ("0" if digest[0] != "0" else "1") + digest[1:]


def test_holdback_suite_sha256_matches_contract_holdback_shape(tmp_path):
    root = tmp_path / "holdback"
    _build_holdback_suite(root)
    manifest = SuiteManifest.model_validate_json((root / SUITE_MANIFEST_NAME).read_text())
    assert sum(len(g.members) for g in manifest.groups) == 40
    assert len(manifest.groups) == sum(c.holdback_groups for c in CLASSES) == 18
    digest = holdback_suite_sha256(root)
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    assert holdback_suite_sha256(root) == digest  # deterministic


def test_holdback_suite_sha256_refuses_a_symlinked_fixture_file(tmp_path):
    root = tmp_path / "holdback"
    _build_holdback_suite(root)
    manifest = SuiteManifest.model_validate_json((root / SUITE_MANIFEST_NAME).read_text())
    case_rel = manifest.groups[0].members[0].case
    real_path = root / case_rel
    backup = real_path.with_name(real_path.name + ".bak")
    real_path.rename(backup)
    try:
        real_path.symlink_to(backup)
    except OSError as e:
        real_path.unlink(missing_ok=True)
        backup.rename(real_path)
        pytest.skip(f"symlinks unavailable on this filesystem: {e}")
    with pytest.raises(ValueError, match="symlink"):
        holdback_suite_sha256(root)


def test_valid_custody_record_is_independent_holdback(tmp_path):
    holdback_root = tmp_path / "holdback"
    repo_root = tmp_path / "repo"
    state_root = tmp_path / "state"
    for p in (repo_root, state_root):
        p.mkdir()
    _build_holdback_suite(holdback_root)
    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    result = load_custody(custody_file, holdback_root, repo_root=repo_root, state_root=state_root)
    assert result["problems"] == []
    assert result["custody_valid"] is True
    assert result["independent_holdback"] is True
    assert result["holdback_suite_sha256"] == digest
    assert result["custodian"] == "Independent reviewer (not the builder seat)"
    assert "attested" in result["note"]


def test_hash_mismatch_blocks_independence(tmp_path):
    holdback_root = tmp_path / "holdback"
    repo_root = tmp_path / "repo"
    state_root = tmp_path / "state"
    for p in (repo_root, state_root):
        p.mkdir()
    _build_holdback_suite(holdback_root)
    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(_flip_hex(digest)))

    result = load_custody(custody_file, holdback_root, repo_root=repo_root, state_root=state_root)
    assert result["custody_valid"] is True
    assert result["independent_holdback"] is False
    assert any("mismatch" in p for p in result["problems"])


def test_invalid_custody_record_is_reported(tmp_path):
    holdback_root = tmp_path / "holdback"
    repo_root = tmp_path / "repo"
    state_root = tmp_path / "state"
    for p in (repo_root, state_root):
        p.mkdir()
    _build_holdback_suite(holdback_root)
    custody_file = tmp_path / "custody.json"
    # Missing required fields (statement, sealed_at_utc): fails CustodyRecord's strict schema.
    custody_file.write_text(json.dumps({
        "schema_id": "hs-holdback-custody/1",
        "custodian": "Someone",
        "holdback_suite_sha256": "0" * 64,
    }))

    result = load_custody(custody_file, holdback_root, repo_root=repo_root, state_root=state_root)
    assert result["custody_valid"] is False
    assert result["custodian"] is None
    assert result["independent_holdback"] is False
    assert any("invalid custody record" in p for p in result["problems"])


def test_holdback_inside_repo_root_is_refused(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    holdback_root = repo_root / "holdback"
    state_root = tmp_path / "state"
    state_root.mkdir()
    _build_holdback_suite(holdback_root)
    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    result = load_custody(custody_file, holdback_root, repo_root=repo_root, state_root=state_root)
    assert result["independent_holdback"] is False
    assert any("inside repo_root" in p for p in result["problems"])


def test_holdback_inside_state_root_is_refused(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state_root = tmp_path / "state"
    state_root.mkdir()
    holdback_root = state_root / "holdback"
    _build_holdback_suite(holdback_root)
    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    result = load_custody(custody_file, holdback_root, repo_root=repo_root, state_root=state_root)
    assert result["independent_holdback"] is False
    assert any("inside state_root" in p for p in result["problems"])


def test_holdback_via_symlinked_ancestor_into_repo_is_refused(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    real_holdback = repo_root / "buried_holdback"
    _build_holdback_suite(real_holdback)
    state_root = tmp_path / "state"
    state_root.mkdir()
    alias_dir = tmp_path / "repo_alias"
    try:
        alias_dir.symlink_to(repo_root, target_is_directory=True)
    except OSError as e:
        pytest.skip(f"symlinks unavailable on this filesystem: {e}")
    holdback_via_alias = alias_dir / "buried_holdback"
    assert holdback_via_alias.is_dir()  # the symlink transparently exposes the real content

    digest = holdback_suite_sha256(holdback_via_alias)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    result = load_custody(custody_file, holdback_via_alias, repo_root=repo_root,
                          state_root=state_root)
    assert result["independent_holdback"] is False
    assert any("inside repo_root" in p for p in result["problems"])


def test_holdback_via_differently_cased_alias_into_repo_is_refused(tmp_path):
    repo_root = tmp_path / "CaseRepo"
    repo_root.mkdir()
    holdback_root = repo_root / "Holdback"
    _build_holdback_suite(holdback_root)
    state_root = tmp_path / "state"
    state_root.mkdir()
    aliased = tmp_path / "caserepo" / "holdback"
    if not aliased.is_dir():
        pytest.skip("filesystem is case-sensitive; the differently-cased alias does not resolve")

    digest = holdback_suite_sha256(aliased)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    result = load_custody(custody_file, aliased, repo_root=repo_root, state_root=state_root)
    assert result["independent_holdback"] is False
    assert any("inside repo_root" in p for p in result["problems"])


def test_holdback_root_itself_a_symlink_into_repo_is_refused(tmp_path):
    """Not an ancestor symlink (covered above) but the ``holdback_root`` leaf itself: a custodian
    handing back a path outside the repo that is a symlink resolving to a location strictly inside
    ``repo_root`` must still be refused as contained."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    real_holdback = repo_root / "buried" / "holdback"
    _build_holdback_suite(real_holdback)
    state_root = tmp_path / "state"
    state_root.mkdir()
    holdback_link = tmp_path / "outside_holdback_link"
    try:
        holdback_link.symlink_to(real_holdback, target_is_directory=True)
    except OSError as e:
        pytest.skip(f"symlinks unavailable on this filesystem: {e}")

    digest = holdback_suite_sha256(holdback_link)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    result = load_custody(custody_file, holdback_link, repo_root=repo_root, state_root=state_root)
    assert result["independent_holdback"] is False
    assert any("inside repo_root" in p for p in result["problems"])


def test_wrong_authorship_is_refused(tmp_path):
    holdback_root = tmp_path / "holdback"
    repo_root = tmp_path / "repo"
    state_root = tmp_path / "state"
    for p in (repo_root, state_root):
        p.mkdir()
    _build_holdback_suite(holdback_root, authorship="builder_constructed")
    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    result = load_custody(custody_file, holdback_root, repo_root=repo_root, state_root=state_root)
    assert result["independent_holdback"] is False
    assert any("authorship" in p for p in result["problems"])


def test_wrong_split_is_refused(tmp_path):
    holdback_root = tmp_path / "holdback"
    repo_root = tmp_path / "repo"
    state_root = tmp_path / "state"
    for p in (repo_root, state_root):
        p.mkdir()
    _build_holdback_suite(holdback_root, split="commissioning_dev")
    digest = holdback_suite_sha256(holdback_root)
    custody_file = tmp_path / "custody.json"
    _write_custody(custody_file, _custody_record(digest))

    result = load_custody(custody_file, holdback_root, repo_root=repo_root, state_root=state_root)
    assert result["independent_holdback"] is False
    assert any("split" in p for p in result["problems"])


# ---------------------------------------------------------------- exposure ledger


def test_ledger_path_layout(tmp_path):
    assert ledger_path(tmp_path) == tmp_path / "commissioning" / "holdback_exposure.jsonl"


def test_exposure_status_before_any_record(tmp_path):
    assert exposure_status(tmp_path, "a" * 64) == {"exposed": False, "records": []}


def test_record_exposure_is_append_only(tmp_path):
    digest = "b" * 64
    first = record_exposure(tmp_path, digest, {"run_id": "run-1"})
    path = ledger_path(tmp_path)
    assert path.is_file()
    first_line = path.read_text().splitlines()[0]

    status = exposure_status(tmp_path, digest)
    assert status == {"exposed": True, "records": [first]}

    second = record_exposure(tmp_path, digest, {"run_id": "run-2"})
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert lines[0] == first_line  # the earlier line was never rewritten

    status2 = exposure_status(tmp_path, digest)
    assert status2["records"] == [first, second]

    # A record for a different holdback hash does not show up here.
    assert exposure_status(tmp_path, "c" * 64) == {"exposed": False, "records": []}


# ==================================================================== agreement


def test_agreement_textbook_example():
    # Classic 2x2 inter-rater example, 100 items, labels {yes, no}:
    #                b=yes  b=no
    #       a=yes      45     15   (60)
    #       a=no       10     30   (40)
    #       totals     55     45   (100)
    # po = (45 + 30) / 100 = 0.75
    # pe = (60/100 * 55/100) + (40/100 * 45/100) = 0.33 + 0.18 = 0.51
    # kappa = (po - pe) / (1 - pe) = (0.75 - 0.51) / (1 - 0.51) = 0.24 / 0.49 ~= 0.4898
    a = ["yes"] * 45 + ["yes"] * 15 + ["no"] * 10 + ["no"] * 30
    b = ["yes"] * 45 + ["no"] * 15 + ["yes"] * 10 + ["no"] * 30
    result = agreement(a, b, labels=["yes", "no"])

    assert result["n_items"] == 100
    assert result["n_paired"] == 100
    assert result["missing"] == {"a": 0, "b": 0, "either": 0}
    assert result["raw_agreement"] == pytest.approx(0.75)
    assert result["confusion_matrix"] == {"yes": {"yes": 45, "no": 15}, "no": {"yes": 10, "no": 30}}
    assert result["prevalence"] == {"yes": pytest.approx(115 / 200), "no": pytest.approx(85 / 200)}
    assert result["cohen_kappa"] == pytest.approx(0.24 / 0.49, abs=1e-9)
    assert result["kappa_undefined_reason"] is None


def test_agreement_perfect_agreement_gives_kappa_one():
    a = ["x", "y", "z", "x", "y"]
    b = list(a)
    result = agreement(a, b, labels=["x", "y", "z"])
    assert result["raw_agreement"] == 1.0
    assert result["cohen_kappa"] == pytest.approx(1.0)
    assert result["kappa_undefined_reason"] is None


def test_agreement_with_missing_values():
    a = ["x", None, "y", "x"]
    b = ["x", "y", None, "x"]
    result = agreement(a, b, labels=["x", "y"])
    assert result["n_items"] == 4
    assert result["n_paired"] == 2
    assert result["missing"] == {"a": 1, "b": 1, "either": 2}
    assert result["raw_agreement"] == 1.0
    assert result["confusion_matrix"] == {"x": {"x": 2, "y": 0}, "y": {"x": 0, "y": 0}}
    # Every paired rating is "x": chance agreement is already 1, so kappa is undefined.
    assert result["cohen_kappa"] is None
    assert result["kappa_undefined_reason"] == "expected chance agreement is 1 (no variability to explain)"


def test_agreement_all_missing_gives_undefined_kappa():
    result = agreement([None, None, None], [None, None, None], labels=["x", "y"])
    assert result["n_paired"] == 0
    assert result["raw_agreement"] is None
    assert result["cohen_kappa"] is None
    assert result["kappa_undefined_reason"] == "no paired ratings (n_paired == 0)"
    assert result["prevalence"] == {"x": None, "y": None}


def test_agreement_rejects_unequal_lengths():
    with pytest.raises(ValueError, match="equal length"):
        agreement(["x"], ["x", "y"], labels=["x", "y"])


def test_agreement_rejects_a_rating_not_in_labels():
    with pytest.raises(ValueError, match="not one of labels"):
        agreement(["x", "z"], ["x", "y"], labels=["x", "y"])
