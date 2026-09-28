"""Commissioning plan builder (BUILD_SPEC §9/§12; docs/WP3_DESIGN.md 'Commands').

``plan_commissioning`` proves the suite (and, when supplied, a custodian holdback) are
structurally sound, partitions the suite, hashes every referenced file, and freezes the result as
``plan.json``. Nothing here runs a trajectory -- that is ``run.py``'s job, against a plan this
module has already written and fixed. A blocked plan writes nothing (``out`` is only created on
``status == 'ok'``), so a caller can retry after fixing the reported problem without cleanup.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .. import COMPILER_VERSION, ENGINE_VERSION, EVALUATOR_VERSION, __version__
from ..canonical import canonical_bytes, make_new_dir, sha256_bytes, write_new_file
from ..corpus.compiler import load_cases
from ..corpus.splits import audit_splits
from ..runner.episode import DEFAULT_COMMISSIONING_LIMITS, code_identity
from . import custody as custody_mod
from . import mutations
from .contract import CLAIM_BOUNDARY, PLAN_SCHEMA, SUITE_MANIFEST_NAME, SuiteManifest, suite_problems
from .partition import PartitionError, partition


def _blocked(status: str, problems: list[str]) -> dict[str, Any]:
    return {"status": status, "plan": None, "problems": problems}


def _load_manifest(root: Path) -> tuple[SuiteManifest | None, list[str]]:
    path = root / SUITE_MANIFEST_NAME
    try:
        text = path.read_text()
    except OSError as e:
        return None, [f"cannot read {path}: {e.strerror or e}"]
    try:
        manifest = SuiteManifest.model_validate_json(text)
    except (ValidationError, ValueError) as e:
        return None, [f"invalid {path}: {e}"]
    return manifest, []


def _load_cases_or_problems(cases_root: Path) -> tuple[list[Any], list[str]]:
    loaded, errors = load_cases(cases_root)
    if errors:
        return [], [f"{e['file']}: {e.get('error', e.get('errors'))}" for e in errors]
    return [c for _, c, _ in loaded], []


def _hash_files(root: Path, manifest: SuiteManifest) -> dict[str, str]:
    """sha256 of ``SUITE.json`` and every case/trajectory file the manifest references, keyed by
    the same relative path the manifest itself uses. Structural validation (``suite_problems`` for
    the suite root, ``load_custody`` for a holdback root) must already have passed, so every path
    here is known to exist, stay inside ``root``, and not be a symlink."""
    files = {SUITE_MANIFEST_NAME: sha256_bytes((root / SUITE_MANIFEST_NAME).read_bytes())}
    for g in manifest.groups:
        for m in g.members:
            for rel in (m.case, m.trajectory):
                if rel not in files:
                    files[rel] = sha256_bytes((root / rel).read_bytes())
    return files


def _fixture_rows(manifest: SuiteManifest, *, partition_map: dict[str, str],
                  source: str) -> list[dict[str, Any]]:
    rows = []
    for g in manifest.groups:
        for m in g.members:
            rows.append({
                "fixture_id": m.fixture_id,
                "group_id": g.group_id,
                "class_id": g.class_id,
                "partition": partition_map[m.fixture_id],
                "source": source,
                "case": m.case,
                "trajectory": m.trajectory,
                "expected": m.expected.model_dump(mode="json"),
            })
    return rows


def plan_commissioning(suite: Path, out: Path, *, repo_root: Path, state_root: Path,
                       holdback: Path | None = None, custody: Path | None = None
                       ) -> dict[str, Any]:
    suite_root = Path(suite)
    repo_root = Path(repo_root)
    state_root = Path(state_root)

    if (holdback is None) != (custody is None):
        return _blocked("blocked_input",
                        ["--holdback and --custody must be given together (one without the "
                         "other is not a valid plan input)"])

    manifest, problems = _load_manifest(suite_root)
    if manifest is None:
        return _blocked("blocked_input", problems)

    struct_problems = suite_problems(manifest, suite_root, fragment=False)
    if struct_problems:
        return _blocked("blocked_input", struct_problems)

    suite_cases, load_problems = _load_cases_or_problems(suite_root / "cases")
    if load_problems:
        return _blocked("blocked_input", load_problems)

    suite_audit = audit_splits(suite_cases)
    if suite_audit["status"] != "ok":
        return _blocked("blocked_input", [str(p) for p in suite_audit["problems"]])

    try:
        partition_result = partition(manifest)
    except PartitionError as e:
        return _blocked("blocked_input", [str(e)])

    suite_files = _hash_files(suite_root, manifest)
    fixtures = _fixture_rows(manifest, partition_map=partition_result["fixture_partition"],
                             source="suite")

    holdback_block: dict[str, Any] | None = None
    custody_problems: list[str] = []
    exposure: dict[str, Any] = {"checked": False}
    mode = "development"
    independent_holdback = False

    if holdback is not None:
        holdback_root = Path(holdback)
        custody_path = Path(custody)
        custody_result = custody_mod.load_custody(custody_path, holdback_root,
                                                   repo_root=repo_root, state_root=state_root)
        custody_problems = list(custody_result["problems"])

        hb_manifest, hb_manifest_problems = _load_manifest(holdback_root)
        if hb_manifest is None:
            custody_problems += hb_manifest_problems
        else:
            hb_cases, hb_load_problems = _load_cases_or_problems(holdback_root / "cases")
            if hb_load_problems:
                custody_problems += hb_load_problems
            else:
                combined_audit = audit_splits(suite_cases + hb_cases)
                if combined_audit["status"] != "ok":
                    custody_problems += [str(p) for p in combined_audit["problems"]]

        if custody_problems:
            return _blocked("blocked_custody", custody_problems)

        independent_holdback = custody_result["independent_holdback"]
        holdback_sha = custody_result["holdback_suite_sha256"]
        exposure_result = custody_mod.exposure_status(state_root, holdback_sha)
        if exposure_result["exposed"]:
            return _blocked("blocked_exposed",
                            [f"holdback {holdback_sha} was already exposed by a prior formal "
                             "commissioning run (docs/WP3_DESIGN.md: 'a fixed evaluator needs a "
                             "fresh holdback')"])
        exposure = {"checked": True, **exposure_result}

        holdback_files = _hash_files(holdback_root, hb_manifest)
        holdback_fixtures = _fixture_rows(
            hb_manifest,
            partition_map={m.fixture_id: "holdback" for g in hb_manifest.groups
                          for m in g.members},
            source="holdback")
        fixtures += holdback_fixtures
        holdback_block = {
            "path": str(holdback),
            "custody_path": str(custody),
            "suite_sha256": holdback_sha,
            "custody_file_sha256": sha256_bytes(custody_path.read_bytes()),
            "custodian": custody_result["custodian"],
            "files": holdback_files,
        }
        mode = "formal"

    fixtures.sort(key=lambda r: r["fixture_id"])

    plan = {
        "schema_id": PLAN_SCHEMA,
        "suite": {
            "path": str(suite),
            "suite_id": manifest.suite_id,
            "authorship": manifest.authorship,
            "manifest_sha256": suite_files[SUITE_MANIFEST_NAME],
        },
        "files": suite_files,
        "holdback": holdback_block,
        "mode": mode,
        "independent_holdback": independent_holdback,
        "custody_problems": custody_problems,
        "exposure": exposure,
        "partition": partition_result,
        "split_audit": {
            "status": suite_audit["status"],
            "problems": suite_audit["problems"],
            "warnings_count": len(suite_audit["warnings"]),
        },
        "fixtures": fixtures,
        "versions": {
            "evaluator": EVALUATOR_VERSION,
            "engine": ENGINE_VERSION,
            "compiler": COMPILER_VERSION,
            "package": __version__,
        },
        "code_identity": code_identity(),
        "mutation_operators": list(mutations.OPERATORS),
        "limits": dict(DEFAULT_COMMISSIONING_LIMITS),
        "counts": {
            "suite_fixtures": sum(1 for r in fixtures if r["source"] == "suite"),
            "development": sum(1 for r in fixtures if r["partition"] == "development"),
            "holdback_designate": sum(1 for r in fixtures if r["partition"] == "holdback_designate"),
            "holdback_fixtures": sum(1 for r in fixtures if r["partition"] == "holdback"),
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }

    out_dir = make_new_dir(Path(out))
    write_new_file(out_dir / "plan.json", canonical_bytes(plan))
    return {"status": "ok", "plan": plan, "problems": []}


__all__ = ["plan_commissioning"]
