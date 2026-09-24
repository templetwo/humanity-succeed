"""``hs`` command line (BUILD_SPEC §12), WP0–WP2 subset.

Exit codes: 0 command completed (read the behavioral result separately); 2 invalid input/contract;
3 missing approval/precondition; 4 unsupported/unavailable; 5 corrupt or unverifiable evidence;
6 interrupted/resource failure. Output is a JSON envelope with ``status``, ``result``,
``limitations``, ``artifacts`` and, on error, ``error.code``. Commands from later work packages are
registered and answer ``unsupported`` (exit 4); none fakes success. No command calls a model.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sys
import uuid
from pathlib import Path
from typing import Any

from . import __version__
from .canonical import StrictLoadError, canonical_bytes, load_document, sha256_obj, write_new_file

EXIT_OK, EXIT_INVALID, EXIT_PRECONDITION, EXIT_UNSUPPORTED, EXIT_CORRUPT, EXIT_INTERRUPTED = (
    0, 2, 3, 4, 5, 6)

SCRIPTED_LIMITATION = ("scripted instrument only; no model was called or trained; "
                       "not a behavioral result about any model")

LATER_WORK_PACKAGES = {
    ("commission", "plan"): "WP3",
    ("commission", "run"): "WP3",
    ("run", "plan"): "WP4/WP5",
    ("run", "execute"): "WP5",
    ("training", "audit-match"): "WP5",
    ("training", "plan"): "WP5",
    ("training", "execute"): "WP5",
    ("study", "plan"): "WP4",
    ("study", "execute"): "WP4",
    ("review", "export"): "WP4",
    ("review", "import"): "WP4",
    ("analyze", None): "WP6",
    ("acceptance", None): "WP7",
}


def envelope(status: str, result: Any = None, *, limitations: list[str] | None = None,
             artifacts: list[str] | None = None, error: dict[str, Any] | None = None) -> dict:
    env = {"status": status, "result": result, "limitations": limitations or [],
           "artifacts": artifacts or []}
    if error:
        env["error"] = error
    return env


def emit(env: dict[str, Any], code: int) -> int:
    sys.stdout.write(json.dumps(env, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return code


def state_root(arg: str | None) -> Path:
    root = Path(arg or os.environ.get("HS_STATE_ROOT")
                or Path.home() / ".local" / "share" / "humanity-succeed")
    (root / "runs").mkdir(parents=True, exist_ok=True)
    return root


def _paths(values: list[str]) -> list[Path]:
    return [Path(v) for v in values]


# ------------------------------------------------------------------ commands


def cmd_doctor(a: argparse.Namespace) -> int:
    if a.models:
        return emit(envelope("unsupported", None, error={
            "code": "unsupported_at_checkpoint",
            "message": "model inventory is WP5; no directory was read"}), EXIT_UNSUPPORTED)
    mlx_present = importlib.util.find_spec("mlx") is not None  # does not import mlx
    return emit(envelope("ok", {
        "package": __version__,
        "python": platform.python_version(),
        "platform": f"{sys.platform}-{platform.machine()}",
        "mlx_importable_without_import": mlx_present,
        "mlx_imported_by_core": "mlx" in sys.modules,
        "model_calls_made": 0,
    }, limitations=["doctor makes no model calls and reads no model directories"]), EXIT_OK)


def cmd_cases_validate(a: argparse.Namespace) -> int:
    from .corpus.compiler import validate_path

    reports = [validate_path(p) for p in _paths(a.path)]
    ok = all(r["status"] == "valid" for r in reports)
    return emit(envelope("ok" if ok else "invalid", reports,
                         limitations=["structural/reference validation only; not a review"]),
                EXIT_OK if ok else EXIT_INVALID)


def _load_all(paths: list[Path]):
    from .corpus.compiler import load_cases

    loaded, errors = [], []
    for p in paths:
        l_, e_ = load_cases(p)
        loaded += l_
        errors += e_
    return loaded, errors


def cmd_cases_audit(a: argparse.Namespace) -> int:
    from .corpus.splits import audit_splits

    loaded, errors = _load_all(_paths(a.path))
    if errors:
        return emit(envelope("invalid", {"errors": errors}), EXIT_INVALID)
    rep = audit_splits([c for _, c, _ in loaded])
    return emit(envelope(rep["status"], rep), EXIT_OK if rep["status"] == "ok" else EXIT_INVALID)


def cmd_cases_lint(a: argparse.Namespace) -> int:
    from .corpus.lint import extract_principles_text, lint_case

    loaded, errors = _load_all(_paths(a.cases))
    if errors:
        return emit(envelope("invalid", {"errors": errors}), EXIT_INVALID)
    principles = extract_principles_text(Path(a.principles).read_text()) if a.principles else None
    flags = {c.case_id: lint_case(c, principles) for _, c, _ in loaded}
    return emit(envelope("ok", {"flags": flags, "flag_count": sum(map(len, flags.values()))},
                         limitations=["phrase lint is not semantic leakage proof; every flag "
                                      "needs a reviewed disposition"]), EXIT_OK)


def cmd_cases_compile(a: argparse.Namespace) -> int:
    from .corpus.compiler import compile_many
    from .corpus.lint import extract_principles_text

    principles = extract_principles_text(Path(a.principles).read_text()) if a.principles else None
    rep = compile_many(_paths(a.path), Path(a.out), principles)
    if rep["status"] == "blocked":
        return emit(envelope("blocked", rep), EXIT_INVALID)
    return emit(envelope("ok", rep, artifacts=[rep["out_dir"]],
                         limitations=["no tokenizer selected: token and label-mask audits "
                                      "against a real tokenizer are blocked"]), EXIT_OK)


def cmd_run_scripted(a: argparse.Namespace) -> int:
    from .contracts.case import CaseSemanticError
    from .runner.scripted import load_case, load_trajectory, run_scripted, trajectory_from_demo

    try:
        case, doc = load_case(Path(a.case))
        traj = (trajectory_from_demo(case, a.demo) if a.demo
                else load_trajectory(Path(a.trajectory)))
    except (StrictLoadError, CaseSemanticError, ValueError) as e:
        return emit(envelope("invalid", None, error={"code": "invalid_input", "message": str(e)}),
                    EXIT_INVALID)
    if traj["case_id"] != case.case_id:
        return emit(envelope("invalid", None, error={
            "code": "invalid_input",
            "message": f"trajectory is bound to case {traj['case_id']!r}, not {case.case_id!r}"}),
            EXIT_INVALID)
    root = state_root(a.state_root)
    # The store name derives from a hash, never from a user-supplied ID.
    store_name = f"traj-{sha256_obj(traj['trajectory_id'])[:16]}-{uuid.uuid4().hex[:8]}.sqlite"
    store_path = root / "runs" / store_name
    bundle, evaluation = run_scripted(case, doc, traj, store_path, Path(a.out))
    return emit(envelope("ok", {
        "bundle": str(bundle),
        "store": str(store_path),
        "execution": evaluation["execution"],
        "mechanical_verdict": evaluation["mechanical"]["verdict"],
        "conduct_outcome": evaluation["conduct_outcome"],
        "containment": evaluation["containment"]["denied_proposals"],
    }, limitations=[SCRIPTED_LIMITATION], artifacts=[str(bundle), str(store_path)]), EXIT_OK)


def cmd_evidence_verify(a: argparse.Namespace) -> int:
    from .evidence.bundle import verify_bundle

    anchor = load_document(Path(a.anchor)) if a.anchor else None
    rep = verify_bundle(Path(a.bundle), anchor)
    bad = rep["internal"] != "consistent" or rep["anchor"] in ("failed", "partial")
    return emit(envelope("failed" if bad else "ok", rep), EXIT_CORRUPT if bad else EXIT_OK)


def cmd_evidence_anchor(a: argparse.Namespace) -> int:
    from .evidence.bundle import anchor_for, verify_bundle

    rep = verify_bundle(Path(a.bundle))
    if rep["internal"] != "consistent":
        return emit(envelope("failed", rep), EXIT_CORRUPT)
    anc = anchor_for(Path(a.bundle))
    write_new_file(Path(a.out), canonical_bytes(anc))
    return emit(envelope("ok", anc, artifacts=[a.out], limitations=[
        "a local anchor file is only as trustworthy as where the operator retains it"]), EXIT_OK)


def cmd_evidence_replay(a: argparse.Namespace) -> int:
    from .evidence.replay import replay_bundle

    rep = replay_bundle(Path(a.bundle), Path(a.out))
    ok = rep.get("replay", {}).get("status") == "reproduced"
    return emit(envelope("ok" if ok else "failed", rep, artifacts=[a.out],
                         limitations=[SCRIPTED_LIMITATION]), EXIT_OK if ok else EXIT_CORRUPT)


def cmd_demo(a: argparse.Namespace) -> int:
    from .demo import run_first_demonstration

    root = state_root(a.state_root)
    rep = run_first_demonstration(Path(a.repo), Path(a.out), root)
    ok = rep["all_assertions_hold"]
    return emit(envelope("ok" if ok else "failed", rep["summary"],
                         artifacts=[str(Path(a.out))], limitations=[SCRIPTED_LIMITATION]),
                EXIT_OK if ok else EXIT_INVALID)


def cmd_unsupported(a: argparse.Namespace) -> int:
    sub = getattr(a, "sub", None)
    wp = LATER_WORK_PACKAGES.get((a.group, sub), "a later work package")
    name = f"{a.group} {sub}" if sub else a.group
    return emit(envelope("unsupported", None, error={
        "code": "unsupported_at_checkpoint",
        "message": f"'hs {name}' belongs to {wp}; the WP2 checkpoint does not implement it and "
                   "performed no action"}),
        EXIT_UNSUPPORTED)


# ------------------------------------------------------------------ parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hs", description="humanity-succeed offline instrument")
    p.add_argument("--version", action="version", version=__version__)
    g = p.add_subparsers(dest="group", required=True)

    d = g.add_parser("doctor")
    d.add_argument("--models")
    d.add_argument("--json", action="store_true")
    d.set_defaults(fn=cmd_doctor)

    cases = g.add_parser("cases").add_subparsers(dest="sub", required=True)
    c = cases.add_parser("validate")
    c.add_argument("path", nargs="+")
    c.set_defaults(fn=cmd_cases_validate)
    c = cases.add_parser("audit-splits")
    c.add_argument("path", nargs="+")
    c.set_defaults(fn=cmd_cases_audit)
    c = cases.add_parser("lint-leaks")
    c.add_argument("--cases", nargs="+", required=True)
    c.add_argument("--principles")
    c.set_defaults(fn=cmd_cases_lint)
    c = cases.add_parser("compile")
    c.add_argument("path", nargs="+")
    c.add_argument("--out", required=True)
    c.add_argument("--principles")
    c.set_defaults(fn=cmd_cases_compile)

    run = g.add_parser("run").add_subparsers(dest="sub", required=True)
    r = run.add_parser("scripted", help="scripted instrument episode (never a model)")
    r.add_argument("--case", required=True)
    src = r.add_mutually_exclusive_group(required=True)
    src.add_argument("--trajectory")
    src.add_argument("--demo")
    r.add_argument("--out", required=True)
    r.add_argument("--state-root")
    r.set_defaults(fn=cmd_run_scripted)
    for sub in ("plan", "execute"):
        x = run.add_parser(sub)
        x.set_defaults(fn=cmd_unsupported)

    ev = g.add_parser("evidence").add_subparsers(dest="sub", required=True)
    e = ev.add_parser("verify")
    e.add_argument("bundle")
    e.add_argument("--anchor")
    e.set_defaults(fn=cmd_evidence_verify)
    e = ev.add_parser("anchor")
    e.add_argument("bundle")
    e.add_argument("--out", required=True)
    e.set_defaults(fn=cmd_evidence_anchor)
    e = ev.add_parser("replay")
    e.add_argument("bundle")
    e.add_argument("--out", required=True)
    e.set_defaults(fn=cmd_evidence_replay)

    dm = g.add_parser("demo", help="WP2 first runnable demonstration (scripted)")
    dm.add_argument("--repo", default=".")
    dm.add_argument("--out", required=True)
    dm.add_argument("--state-root")
    dm.set_defaults(fn=cmd_demo)

    for group, subs in (("commission", ("plan", "run")), ("training", ("audit-match", "plan",
                        "execute")), ("study", ("plan", "execute")), ("review", ("export",
                        "import"))):
        sp = g.add_parser(group).add_subparsers(dest="sub", required=True)
        for s in subs:
            x = sp.add_parser(s)
            x.set_defaults(fn=cmd_unsupported)
    for group in ("analyze", "acceptance"):
        x = g.add_parser(group)
        x.set_defaults(fn=cmd_unsupported, sub=None)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        a, extra = parser.parse_known_args(argv)
        # Later-work-package commands accept and ignore any arguments: they do nothing.
        if extra and a.fn is not cmd_unsupported:
            parser.error(f"unrecognized arguments: {' '.join(extra)}")
    except SystemExit as e:
        return EXIT_INVALID if e.code else EXIT_OK
    try:
        return a.fn(a)
    except FileExistsError as e:
        return emit(envelope("invalid", None, error={"code": "refuse_overwrite",
                                                     "message": str(e)}), EXIT_INVALID)
    except (ValueError, FileNotFoundError) as e:  # StrictLoadError is a ValueError
        return emit(envelope("invalid", None, error={"code": "invalid_input",
                                                     "message": str(e)}), EXIT_INVALID)
    except KeyboardInterrupt:
        return emit(envelope("interrupted", None, error={"code": "interrupted",
                                                         "message": "interrupted"}),
                    EXIT_INTERRUPTED)


if __name__ == "__main__":
    raise SystemExit(main())
