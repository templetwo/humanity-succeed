"""Deterministic partition of a commissioning suite manifest (docs/WP3_DESIGN.md; BUILD_SPEC §9).

Structural only: this module never touches the filesystem and never runs a trajectory. It takes an
already-loaded ``SuiteManifest`` and deterministically designates whole groups as
``holdback_designate`` (builder-authored, exposed, never independent holdback) versus
``development``, then proves the §9 totals by counting the actual assignment rather than repeating
the contract's constants.
"""

from __future__ import annotations

import hashlib

from .contract import (
    CLASSES,
    DEVELOPMENT_TRAJECTORIES,
    HOLDBACK_TRAJECTORIES,
    TOTAL_TRAJECTORIES,
    ClassSpec,
    Group,
    SuiteManifest,
)


class PartitionError(ValueError):
    """The manifest's structure does not match contract.CLASSES; refuse to partition."""


def _group_key(suite_id: str, group_id: str) -> str:
    """The deterministic ordering key for one group: sha256(f"{suite_id}:{group_id}") hex."""
    return hashlib.sha256(f"{suite_id}:{group_id}".encode()).hexdigest()


def _class_counts(spec: ClassSpec, dev_groups: list[Group], hb_groups: list[Group]) -> dict[str, int]:
    """Counted directly from the given group lists -- never from ``spec`` -- so a caller that hands
    this a tampered split gets a proof that reflects the tampering, not the contract's numbers."""
    return {
        "groups": len(dev_groups) + len(hb_groups),
        "development_groups": len(dev_groups),
        "holdback_groups": len(hb_groups),
        "development_trajectories": sum(len(g.members) for g in dev_groups),
        "holdback_trajectories": sum(len(g.members) for g in hb_groups),
    }


def _matches_section_9(per_class: dict[str, dict[str, int]], total: int, development: int,
                       holdback: int) -> bool:
    """True iff the counted totals and every counted per-class row equal what contract.CLASSES
    (BUILD_SPEC §9) specifies. Comparing against the contract's own numbers here, not assuming
    them, is what lets this catch a per-class row that was tampered or miscounted."""
    if (total, development, holdback) != (TOTAL_TRAJECTORIES, DEVELOPMENT_TRAJECTORIES,
                                          HOLDBACK_TRAJECTORIES):
        return False
    for spec in CLASSES:
        want = {
            "groups": spec.groups,
            "development_groups": spec.groups - spec.holdback_groups,
            "holdback_groups": spec.holdback_groups,
            "development_trajectories": (spec.groups - spec.holdback_groups) * spec.members,
            "holdback_trajectories": spec.holdback_groups * spec.members,
        }
        if per_class.get(spec.class_id) != want:
            return False
    return True


def partition(manifest: SuiteManifest) -> dict:
    """Deterministically split ``manifest`` into development / holdback-designate groups.

    Refuses (``PartitionError``) unless the manifest has exactly ``contract.CLASSES``' ``groups``
    per class, each with the right member count. Structure only; no file access. Per class, groups
    are ordered by ``sha256(f"{manifest.suite_id}:{group_id}")`` hex and the first
    ``holdback_groups`` in that order are designated ``holdback_designate``; the rest are
    ``development``. Deterministic and independent of the manifest's own group order.
    """
    by_class: dict[str, list[Group]] = {}
    for g in manifest.groups:
        by_class.setdefault(g.class_id, []).append(g)

    problems: list[str] = []
    for spec in CLASSES:
        groups = by_class.get(spec.class_id, [])
        if len(groups) != spec.groups:
            problems.append(f"{spec.class_id}: {len(groups)} groups, expected {spec.groups}")
            continue
        for g in groups:
            if len(g.members) != spec.members:
                problems.append(
                    f"{g.group_id}: {len(g.members)} members, expected {spec.members}")
    if problems:
        raise PartitionError("; ".join(problems))

    development: list[str] = []
    holdback_designate: list[str] = []
    fixture_partition: dict[str, str] = {}
    per_class: dict[str, dict[str, int]] = {}

    for spec in CLASSES:
        ordered = sorted(by_class[spec.class_id],
                         key=lambda g: _group_key(manifest.suite_id, g.group_id))
        hb_groups = ordered[: spec.holdback_groups]
        dev_groups = ordered[spec.holdback_groups:]
        for g in hb_groups:
            holdback_designate.append(g.group_id)
            for m in g.members:
                fixture_partition[m.fixture_id] = "holdback_designate"
        for g in dev_groups:
            development.append(g.group_id)
            for m in g.members:
                fixture_partition[m.fixture_id] = "development"
        per_class[spec.class_id] = _class_counts(spec, dev_groups, hb_groups)

    development.sort()
    holdback_designate.sort()

    total_trajectories = sum(v["development_trajectories"] + v["holdback_trajectories"]
                             for v in per_class.values())
    development_trajectories = sum(v["development_trajectories"] for v in per_class.values())
    holdback_trajectories = sum(v["holdback_trajectories"] for v in per_class.values())
    all_members = sum(len(g.members) for g in manifest.groups)

    return {
        "schema_id": "hs-commission-partition/1",
        "method": (
            "Per class, groups are ordered by the hex digest of "
            "sha256(f'{suite_id}:{group_id}') and the first holdback_groups groups in that order "
            "are designated holdback_designate; the remaining groups in the class are development."
        ),
        "development": development,
        "holdback_designate": holdback_designate,
        "fixture_partition": fixture_partition,
        "proof": {
            "per_class": per_class,
            "total_trajectories": total_trajectories,
            "development_trajectories": development_trajectories,
            "holdback_trajectories": holdback_trajectories,
            "groups_in_both": len(set(development) & set(holdback_designate)),
            "fixtures_unassigned": all_members - len(fixture_partition),
            "matches_section_9": _matches_section_9(per_class, total_trajectories,
                                                    development_trajectories,
                                                    holdback_trajectories),
        },
    }


__all__ = ["PartitionError", "partition"]
