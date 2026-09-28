"""Commissioning run engine (BUILD_SPEC §9/§12; docs/WP3_DESIGN.md 'Commands').

``run_commissioning`` re-verifies a frozen plan against the bytes on disk right now, refuses to run
anything if the plan was tampered with or was written under a different evaluator/engine, runs every
planned fixture through the scripted provider, checks it against its golden expectation, runs the
controlled mutations, and writes a report that says exactly which fixtures met their expectations
(never a population error rate; BUILD_SPEC §9). Nothing is created -- no output directory, no
SQLite store -- unless every pre-flight check passes.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION, EVALUATOR_VERSION
from ..canonical import (
    StrictLoadError,
    canonical_bytes,
    make_new_dir,
    sha256_bytes,
    strict_json_loads,
    write_new_file,
)
from ..evidence.bundle import verify_bundle
from ..runner.scripted import load_case, load_trajectory, run_scripted
from . import custody as custody_mod
from . import execute, mutations
from .contract import CLAIM_BOUNDARY, PLAN_SCHEMA, REPORT_SCHEMA, Expectation
from .report import render_html

SCRIPTED_LIMITATION = ("scripted instrument only; no model was called or trained; not a "
                       "behavioral result about any model")


def _blocked(status: str, problems: list[str]) -> dict[str, Any]:
    return {"status": status, "report": None, "problems": problems}


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
    required = ("suite", "files", "holdback", "mode", "fixtures", "versions")
    missing = [k for k in required if k not in plan]
    if missing:
        return None, None, [f"{plan_file}: missing plan field(s): {', '.join(missing)}"]
    return plan_bytes, plan, []


def _tamper_check(root: Path, files: dict[str, str]) -> list[str]:
    problems = []
    for rel, want in sorted(files.items()):
        p = root / rel
        try:
            got = sha256_bytes(p.read_bytes())
        except OSError as e:
            problems.append(f"{rel}: missing or unreadable ({e.strerror or e})")
            continue
        if got != want:
            problems.append(f"{rel}: hash changed since the plan was written")
    return problems


def _derived_hex(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


def _summarize(rows: list[dict[str, Any]], key_fn) -> dict[str, Any]:
    buckets: dict[str, dict[str, list[str]]] = {}
    for r in rows:
        b = buckets.setdefault(key_fn(r), {"met": [], "missed": []})
        (b["met"] if r["match"] else b["missed"]).append(r["fixture_id"])
    out = {}
    for k, b in buckets.items():
        met, missed = sorted(b["met"]), sorted(b["missed"])
        out[k] = {"met_count": len(met), "missed_count": len(missed),
                  "met_fixture_ids": met, "missed_fixture_ids": missed}
    return out


def run_commissioning(plan_path: Path, out: Path, *, state_root: Path, repo_root: Path,
                      provider: str = "scripted") -> dict[str, Any]:
    if provider != "scripted":
        return {"status": "unsupported_provider", "report": None,
                "problems": [f"provider {provider!r} is not supported; only 'scripted' runs "
                            "at this checkpoint"]}

    state_root = Path(state_root)
    repo_root = Path(repo_root)

    plan_bytes, plan, problems = _read_plan(Path(plan_path))
    if plan is None:
        return _blocked("plan_invalid", problems)
    plan_sha = sha256_bytes(plan_bytes)

    tamper_problems = _tamper_check(Path(plan["suite"]["path"]), plan["files"])
    if plan.get("holdback") is not None:
        hb = plan["holdback"]
        tamper_problems += _tamper_check(Path(hb["path"]), hb["files"])
        try:
            custody_bytes = Path(hb["custody_path"]).read_bytes()
        except OSError as e:
            tamper_problems.append(f"{hb['custody_path']}: missing or unreadable "
                                   f"({e.strerror or e})")
        else:
            if sha256_bytes(custody_bytes) != hb["custody_file_sha256"]:
                tamper_problems.append(f"{hb['custody_path']}: hash changed since the plan was "
                                       "written")
    if tamper_problems:
        return _blocked("plan_tampered", tamper_problems)

    versions = plan.get("versions", {})
    if versions.get("evaluator") != EVALUATOR_VERSION or versions.get("engine") != ENGINE_VERSION:
        return _blocked("evaluator_mismatch", [
            f"plan was written under evaluator={versions.get('evaluator')!r} "
            f"engine={versions.get('engine')!r}; this build is evaluator={EVALUATOR_VERSION!r} "
            f"engine={ENGINE_VERSION!r}"])

    if plan["mode"] == "formal":
        hb = plan["holdback"]
        custody_result = custody_mod.load_custody(Path(hb["custody_path"]), Path(hb["path"]),
                                                   repo_root=repo_root, state_root=state_root)
        if custody_result["problems"]:
            return _blocked("blocked_custody", custody_result["problems"])
        exposure_result = custody_mod.exposure_status(state_root, hb["suite_sha256"])
        if exposure_result["exposed"]:
            return _blocked("blocked_exposed",
                            [f"holdback {hb['suite_sha256']} was already exposed by a prior "
                             "formal commissioning run"])

    # Every pre-flight check passed: from here on, run and create output.
    runs_dir = state_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    out_dir = make_new_dir(Path(out))

    fixture_rows: list[dict[str, Any]] = []
    for fx in sorted(plan["fixtures"], key=lambda r: r["fixture_id"]):
        root = Path(plan["suite"]["path"]) if fx["source"] == "suite" else Path(plan["holdback"]["path"])
        case, doc = load_case(root / fx["case"])
        traj = load_trajectory(root / fx["trajectory"])
        expected = Expectation.model_validate(fx["expected"])

        store_base = _derived_hex(plan_sha, fx["fixture_id"], "store")
        store_path = runs_dir / f"commission-{store_base[:16]}-{uuid.uuid4().hex[:8]}.sqlite"
        run_id = "run_" + _derived_hex(plan_sha, fx["fixture_id"], "run")[:20]
        bundle_out = out_dir / "bundles" / fx["fixture_id"]

        bundle, evaluation = run_scripted(case, doc, traj, store_path, bundle_out, run_id=run_id)
        verify_report = verify_bundle(bundle)
        observed = execute.observed(evaluation)
        match = execute.matches(expected, observed) and verify_report["internal"] == "consistent"
        mut_result = mutations.run_all(case, doc, traj["raw_outputs"], expected)

        fixture_rows.append({
            "fixture_id": fx["fixture_id"],
            "group_id": fx["group_id"],
            "class_id": fx["class_id"],
            "partition": fx["partition"],
            "source": fx["source"],
            "expected": fx["expected"],
            "observed": observed,
            "match": match,
            "verify_internal": verify_report["internal"],
            "bundle": f"bundles/{fx['fixture_id']}",
            "mutations": mut_result,
        })

    suite_rows = [r for r in fixture_rows if r["source"] == "suite"]
    mechanical_met = all(r["match"] for r in suite_rows)
    mechanical_status = ("development_all_expectations_met" if mechanical_met
                         else "development_expectations_missed")

    if plan["mode"] == "development":
        formal_status = "blocked_no_independent_holdback"
    else:
        holdback_rows = [r for r in fixture_rows if r["source"] == "holdback"]
        formal_status = "passed" if all(r["match"] for r in holdback_rows) else "failed"
        custody_mod.record_exposure(state_root, plan["holdback"]["suite_sha256"], {
            "plan_sha256": plan_sha, "out": str(out_dir), "formal_commissioning": formal_status,
        })

    judgment_ids = sorted(r["fixture_id"] for r in fixture_rows if r["expected"]["judgment_heavy"])
    semantic = {
        "status": "pending_no_human_reviews",
        "judgment_heavy_fixture_ids": judgment_ids,
        "reviews_received": 0,
        "agreement": None,
        "reason": "two independent human reviews are required for judgment-heavy fixtures before "
                  "semantic commissioning can proceed (WP4); none exist yet",
    }

    all_mutations_held = all(c["held"] for r in fixture_rows for c in r["mutations"]["checks"])
    all_bundles_verified = all(r["verify_internal"] == "consistent" for r in fixture_rows)
    lifecycle_state = ("mechanically_validated"
                       if mechanical_met and all_mutations_held and all_bundles_verified
                       else "draft")

    all_checks = [(r["fixture_id"], c) for r in fixture_rows for c in r["mutations"]["checks"]]
    mutations_summary = {
        "checks": len(all_checks),
        "held": sum(1 for _, c in all_checks if c["held"]),
        "violated": [
            {"fixture_id": fid, "op": c["op"], "invariant": c["invariant"],
             "original_mechanical": c["original_mechanical"],
             "mutated_mechanical": c["mutated_mechanical"]}
            for fid, c in all_checks if not c["held"]
        ],
    }

    limitations = [
        SCRIPTED_LIMITATION,
        "160 constructed, related, development-influenced trajectories are an engineering "
        "commissioning target, not a population error bound (BUILD_SPEC §9)",
        f"formal_commissioning is {formal_status!r}; lifecycle_state can reach at most "
        "mechanically_validated at this checkpoint, never instrument_commissioned, because "
        "semantic review has not occurred",
    ]

    report = {
        "schema_id": REPORT_SCHEMA,
        "plan_sha256": plan_sha,
        "mode": plan["mode"],
        "independent_holdback": plan["independent_holdback"],
        "custodian": plan["holdback"]["custodian"] if plan.get("holdback") else None,
        "fixtures": fixture_rows,
        "summary": {
            "by_class": _summarize(fixture_rows, lambda r: r["class_id"]),
            "by_partition": _summarize(fixture_rows, lambda r: r["partition"]),
        },
        "mutations_summary": mutations_summary,
        "mechanical_commissioning": mechanical_status,
        "formal_commissioning": formal_status,
        "semantic_commissioning": semantic,
        "lifecycle_state": lifecycle_state,
        "holdback_designate_note": (
            "The holdback_designate fixtures are builder-authored and were exposed to the "
            "builder before any run; they are not independent holdback and never count toward "
            "formal_commissioning (docs/WP3_DESIGN.md)."
        ),
        "limitations": limitations,
        "claim_boundary": CLAIM_BOUNDARY,
    }

    write_new_file(out_dir / "report.json", canonical_bytes(report))
    write_new_file(out_dir / "report.html", render_html(report).encode("utf-8"))
    return {"status": "completed", "report": report, "problems": []}


__all__ = ["run_commissioning"]
