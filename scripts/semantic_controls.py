"""Generate, check, plan and run the A1 semantic controls supplement (DECISIONS B68).

    uv run python scripts/semantic_controls.py generate --out cases/supplement_a1_semantic_controls_v1
    uv run python scripts/semantic_controls.py check --out cases/supplement_a1_semantic_controls_v1
    uv run python scripts/semantic_controls.py plan --supplement DIR --out DIR [--state-root DIR]
    uv run python scripts/semantic_controls.py run --plan PLAN.json --out DIR [--state-root DIR]

``generate`` refuses to overwrite and refuses to write anything the contract reports a problem
with. ``check`` exits 1 on any byte drift (a stray file is drift). ``plan`` and ``run`` print a
JSON result and exit 3 when they refuse. ``--state-root`` defaults as ``cli.state_root`` does:
the flag, else ``$HS_STATE_ROOT``, else ``~/.local/share/humanity-succeed`` (precedent:
scripts/seal_holdback.py). Nothing here exports a review packet.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from humanity_succeed.semantic_controls import generator
from humanity_succeed.semantic_controls.study import plan_supplement, run_supplement

# scripts/semantic_controls.py sits one directory below the repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
assert (REPO_ROOT / "pyproject.toml").is_file(), (
    f"semantic_controls.py: unexpected repo root {REPO_ROOT} (pyproject.toml not found there)")

EXIT_OK, EXIT_DRIFT, EXIT_INVALID, EXIT_REFUSED = 0, 1, 2, 3


def _resolve_state_root(arg: str | None) -> Path:
    """``cli.state_root``'s precedence, without importing cli.py and without creating anything
    (``run_supplement`` creates ``<state_root>/runs`` only after its pre-flight checks pass)."""
    return Path(arg or os.environ.get("HS_STATE_ROOT")
                or Path.home() / ".local" / "share" / "humanity-succeed")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="semantic_controls.py",
                                description="A1 semantic controls supplement (DECISIONS B68).")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write the supplement into a NEW directory")
    g.add_argument("--out", required=True)
    c = sub.add_parser("check", help="byte-compare a directory with a fresh render")
    c.add_argument("--out", required=True)
    pl = sub.add_parser("plan", help="freeze a supplement into plan.json")
    pl.add_argument("--supplement", required=True)
    pl.add_argument("--out", required=True)
    pl.add_argument("--state-root", default=None)
    r = sub.add_parser("run", help="run a frozen plan; writes report.json and bundles/")
    r.add_argument("--plan", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--state-root", default=None)
    return p.parse_args(argv)


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    a = parse_args(argv)
    if a.cmd == "generate":
        try:
            generator.write(Path(a.out))
        except FileExistsError as e:
            print(f"refusing: {e}")
            return EXIT_INVALID
        except ValueError as e:
            print(str(e))
            return EXIT_REFUSED
        print(f"wrote {len(generator.render())} files to {a.out}")
        return EXIT_OK
    if a.cmd == "check":
        drift = generator.check(Path(a.out))
        if drift:
            print("supplement drift:\n  " + "\n  ".join(drift[:50]))
            return EXIT_DRIFT
        print(f"{a.out} matches the generator ({len(generator.render())} files)")
        return EXIT_OK
    state_root = _resolve_state_root(a.state_root)
    if a.cmd == "plan":
        res = plan_supplement(Path(a.supplement), Path(a.out), state_root=state_root,
                              repo_root=REPO_ROOT)
        _emit({"status": res["status"], "plan_sha256": res["plan_sha256"],
               "problems": res["problems"], "out": a.out})
        return EXIT_OK if res["status"] == "ok" else EXIT_REFUSED
    res = run_supplement(Path(a.plan), Path(a.out), state_root=state_root, repo_root=REPO_ROOT)
    rep = res["report"] or {}
    _emit({"status": res["status"], "problems": res["problems"], "out": a.out,
           "mechanical": rep.get("mechanical", {}).get("status"),
           "lifecycle_state": rep.get("lifecycle_state")})
    return EXIT_OK if res["status"] == "completed" else EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
