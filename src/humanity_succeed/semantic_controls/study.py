"""Plan and run the semantic controls supplement (DECISIONS B68; ``contract.py`` is authoritative).

Why its own plan/run: ``hs commission plan`` refuses any suite that does not carry every suite v1
class in its exact count, and the supplement is one case shape (see ``contract.py``). The run
mirrors ``commissioning.run.run_commissioning`` step for step (pre-flight tamper and version checks
before anything is created, a store under ``state_root/"runs"``, a derived ``run_id``, one bundle
per fixture under ``out/"bundles"/<fixture_id>``, ``verify_bundle``, ``execute.observed`` /
``matches``, ``mutations.run_all``), so ``review.export`` reads the report rows and bundles
unchanged. It writes no HTML report: ``commissioning.report.render_html`` is for suite runs.

Nothing here is a result about any model: the provider is scripted and no model is called.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .. import COMPILER_VERSION, ENGINE_VERSION, EVALUATOR_VERSION, __version__
from ..canonical import (
    StrictLoadError,
    canonical_bytes,
    make_new_dir,
    sha256_bytes,
    strict_json_loads,
    write_new_file,
)
from ..commissioning import execute, mutations
from ..commissioning.contract import Expectation
from ..evidence.bundle import verify_bundle
from ..runner.scripted import load_case, load_trajectory, run_scripted
from .contract import (
    HONEST_ROLE,
    MANIFEST_FILE,
    PLAN_SCHEMA,
    REPORT_SCHEMA,
    ControlExpectation,
    SupplementManifest,
    supplement_problems,
)

MODE = "development"
PARTITION = "development"
SOURCE = "supplement"

CLAIM_BOUNDARY = (
    "Constructed, builder-authored semantic controls: wrong-on-purpose notices beside honest "
    "twins, each with its expected human verdict written before any run. A run reports exactly "
    "which fixtures met their written mechanical expectations; the human side is pending until a "
    "human reviews. Not a population error bound and not a behavioral result about any model. No "
    "model was called."
)
SCRIPTED_LIMITATION = ("scripted instrument only; no model was called or trained; not a "
                       "behavioral result about any model")


def _blocked_plan(status: str, problems: list[str]) -> dict[str, Any]:
    return {"status": status, "plan": None, "plan_sha256": None, "problems": problems}


def _blocked_run(status: str, problems: list[str]) -> dict[str, Any]:
    return {"status": status, "report": None, "problems": problems}


def _derived_hex(*parts: str) -> str:
    """Same derivation as ``commissioning.run._derived_hex``."""
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


def _hash_tree(root: Path) -> tuple[dict[str, str], list[str]]:
    """sha256 of every regular file under ``root``, keyed by posix relative path. Symlinks are
    refused as problems, never followed."""
    files: dict[str, str] = {}
    problems: list[str] = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            problems.append(f"{rel}: symlink under the supplement root")
        elif p.is_file():
            files[rel] = sha256_bytes(p.read_bytes())
    return files, problems


def _load_manifest(root: Path) -> tuple[SupplementManifest | None, list[str]]:
    path = root / MANIFEST_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, [f"cannot read {path}: {e.strerror or e}"]
    try:
        return SupplementManifest.model_validate_json(text), []
    except (ValidationError, ValueError) as e:
        return None, [f"invalid {path}: {e}"]


def plan_supplement(root: Path, out: Path, *, state_root: Path, repo_root: Path) -> dict[str, Any]:
    """Freeze the supplement at ``root`` into ``out/plan.json``. Refuses (``blocked_input``) unless
    ``contract.supplement_problems`` is empty, including the no-collision checks against
    ``repo_root/cases/commissioning_suite_v1``. A blocked plan writes nothing. ``state_root`` is
    accepted for signature symmetry with ``run_supplement``; planning touches no state."""
    del state_root
    root = Path(root)
    repo_root = Path(repo_root)

    manifest, problems = _load_manifest(root)
    if manifest is None:
        return _blocked_plan("blocked_input", problems)

    suite_v1_root = repo_root / "cases" / "commissioning_suite_v1"
    if not (suite_v1_root / "SUITE.json").is_file():
        return _blocked_plan("blocked_input", [
            f"suite v1 not found at {suite_v1_root}; the no-collision check cannot run"])
    problems = supplement_problems(manifest, root, suite_v1_root=suite_v1_root)
    if problems:
        return _blocked_plan("blocked_input", problems)

    files, tree_problems = _hash_tree(root)
    if tree_problems:
        return _blocked_plan("blocked_input", tree_problems)

    fixtures = []
    for g in manifest.groups:
        for m in g.members:
            fixtures.append({
                "fixture_id": m.fixture_id,
                "group_id": g.group_id,
                "class_id": g.class_id,
                "role": m.role,
                "case": m.case,
                "trajectory": m.trajectory,
                "expected": m.expected.model_dump(mode="json"),
            })
    fixtures.sort(key=lambda r: r["fixture_id"])

    plan = {
        "schema_id": PLAN_SCHEMA,
        "supplement": {
            "path": str(root),
            "supplement_id": manifest.supplement_id,
            "manifest_sha256": files[MANIFEST_FILE],
        },
        "files": files,
        "fixtures": fixtures,
        "versions": {
            "evaluator": EVALUATOR_VERSION,
            "engine": ENGINE_VERSION,
            "compiler": COMPILER_VERSION,
            "package": __version__,
        },
        "mode": MODE,
        "mutation_operators": list(mutations.OPERATORS),
        "counts": {
            "fixtures": len(fixtures),
            "honest": sum(1 for f in fixtures if f["role"] == HONEST_ROLE),
            "known_fail": sum(1 for f in fixtures if f["role"] != HONEST_ROLE),
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }
    plan_bytes = canonical_bytes(plan)
    out_dir = make_new_dir(Path(out))
    write_new_file(out_dir / "plan.json", plan_bytes)
    return {"status": "ok", "plan": plan, "plan_sha256": sha256_bytes(plan_bytes), "problems": []}


def _read_plan(plan_path: Path) -> tuple[bytes | None, dict[str, Any] | None, list[str]]:
    plan_path = Path(plan_path)
    plan_file = plan_path / "plan.json" if plan_path.is_dir() else plan_path
    try:
        plan_bytes = plan_file.read_bytes()
    except OSError as e:
        return None, None, [f"cannot read {plan_file}: {e.strerror or e}"]
    try:
        plan = strict_json_loads(plan_bytes)
    except StrictLoadError as e:
        return None, None, [str(e)]
    if not isinstance(plan, dict) or plan.get("schema_id") != PLAN_SCHEMA:
        return None, None, [f"{plan_file}: not a {PLAN_SCHEMA} document"]
    required = ("supplement", "files", "fixtures", "versions", "mode")
    missing = [k for k in required if k not in plan]
    if missing:
        return None, None, [f"{plan_file}: missing plan field(s): {', '.join(missing)}"]
    return plan_bytes, plan, []


def _tamper_check(root: Path, files: dict[str, str]) -> list[str]:
    """Every planned file must still hash as planned, and no file may have been added under the
    supplement root since the plan was written."""
    problems = []
    for rel, want in sorted(files.items()):
        p = root / rel
        if p.is_symlink():
            problems.append(f"{rel}: is now a symlink")
            continue
        try:
            got = sha256_bytes(p.read_bytes())
        except OSError as e:
            problems.append(f"{rel}: missing or unreadable ({e.strerror or e})")
            continue
        if got != want:
            problems.append(f"{rel}: hash changed since the plan was written")
    if root.is_dir():
        present = {p.relative_to(root).as_posix() for p in root.rglob("*")
                   if p.is_file() or p.is_symlink()}
        for rel in sorted(present - set(files)):
            problems.append(f"{rel}: not in the plan (added since the plan was written)")
    return problems


def run_supplement(plan_path: Path, out: Path, *, state_root: Path, repo_root: Path
                   ) -> dict[str, Any]:
    """Run every planned fixture through the scripted provider and write ``out/report.json``.
    Nothing is created (no output directory, no store) unless every pre-flight check passes."""
    del repo_root  # accepted for signature symmetry; the plan carries every path the run needs
    state_root = Path(state_root)

    plan_bytes, plan, problems = _read_plan(Path(plan_path))
    if plan is None:
        return _blocked_run("plan_invalid", problems)
    plan_sha = sha256_bytes(plan_bytes)
    root = Path(plan["supplement"]["path"])

    tamper_problems = _tamper_check(root, plan["files"])
    if tamper_problems:
        return _blocked_run("plan_tampered", tamper_problems)

    versions = plan.get("versions", {})
    if versions.get("evaluator") != EVALUATOR_VERSION or versions.get("engine") != ENGINE_VERSION:
        return _blocked_run("evaluator_mismatch", [
            f"plan was written under evaluator={versions.get('evaluator')!r} "
            f"engine={versions.get('engine')!r}; this build is evaluator={EVALUATOR_VERSION!r} "
            f"engine={ENGINE_VERSION!r}"])

    # Every pre-flight check passed: from here on, run and create output.
    runs_dir = state_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    out_dir = make_new_dir(Path(out))

    rows: list[dict[str, Any]] = []
    for fx in sorted(plan["fixtures"], key=lambda r: r["fixture_id"]):
        case, doc = load_case(root / fx["case"])
        traj = load_trajectory(root / fx["trajectory"])
        expected = ControlExpectation.model_validate(fx["expected"])
        suite_expected = Expectation(**expected.as_suite_expectation())

        store_base = _derived_hex(plan_sha, fx["fixture_id"], "store")
        store_path = runs_dir / f"controls-{store_base[:16]}-{uuid.uuid4().hex[:8]}.sqlite"
        run_id = "run_" + _derived_hex(plan_sha, fx["fixture_id"], "run")[:20]
        bundle_out = out_dir / "bundles" / fx["fixture_id"]

        bundle, evaluation = run_scripted(case, doc, traj, store_path, bundle_out, run_id=run_id)
        verify_report = verify_bundle(bundle)
        observed = execute.observed(evaluation)
        match = execute.matches(suite_expected, observed) and verify_report["internal"] == "consistent"
        mut_result = mutations.run_all(case, doc, traj["raw_outputs"], suite_expected)

        rows.append({
            "fixture_id": fx["fixture_id"],
            "group_id": fx["group_id"],
            "class_id": fx["class_id"],
            "partition": PARTITION,
            "source": SOURCE,
            "role": fx["role"],
            "angle": expected.angle,
            "expected": fx["expected"],
            "observed": observed,
            "match": match,
            "verify_internal": verify_report["internal"],
            "bundle": f"bundles/{fx['fixture_id']}",
            "mutations": mut_result,
        })

    mechanical_met = all(r["match"] for r in rows)
    all_mutations_held = all(c["held"] for r in rows for c in r["mutations"]["checks"])
    all_bundles_verified = all(r["verify_internal"] == "consistent" for r in rows)
    lifecycle_state = ("mechanically_validated"
                       if mechanical_met and all_mutations_held and all_bundles_verified
                       else "draft")

    all_checks = [(r["fixture_id"], c) for r in rows for c in r["mutations"]["checks"]]
    report = {
        "schema_id": REPORT_SCHEMA,
        "plan_sha256": plan_sha,
        "mode": plan["mode"],
        "supplement": dict(plan["supplement"]),
        "versions": dict(plan["versions"]),
        "fixtures": rows,
        "mutations_summary": {
            "checks": len(all_checks),
            "held": sum(1 for _, c in all_checks if c["held"]),
            "violated": [
                {"fixture_id": fid, "op": c["op"], "invariant": c["invariant"],
                 "original_mechanical": c["original_mechanical"],
                 "mutated_mechanical": c["mutated_mechanical"]}
                for fid, c in all_checks if not c["held"]
            ],
        },
        "mechanical": {
            "status": ("development_all_expectations_met" if mechanical_met
                       else "development_expectations_missed"),
            "met_fixture_ids": sorted(r["fixture_id"] for r in rows if r["match"]),
            "missed_fixture_ids": sorted(r["fixture_id"] for r in rows if not r["match"]),
        },
        "semantic": {
            "status": "pending_no_human_reviews",
            "known_fail_fixture_ids": sorted(r["fixture_id"] for r in rows
                                             if r["role"] != HONEST_ROLE),
            "honest_fixture_ids": sorted(r["fixture_id"] for r in rows if r["role"] == HONEST_ROLE),
            "reviews_received": 0,
            "reason": "the expected human verdicts are the operator's written expectation; no "
                      "human has reviewed any item yet",
        },
        "lifecycle_state": lifecycle_state,
        "limitations": [
            SCRIPTED_LIMITATION,
            "builder-constructed controls; the expected human verdicts are operator-side only and "
            "never enter a review packet (DECISIONS B69)",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }

    write_new_file(out_dir / "report.json", canonical_bytes(report))
    return {"status": "completed", "report": report, "problems": []}


__all__ = ["plan_supplement", "run_supplement", "CLAIM_BOUNDARY"]
