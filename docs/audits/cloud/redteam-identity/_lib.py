"""Shared helpers for the reviewer-identity red-team reproducers (2026-10-07).

Everything here runs against a SCRATCH state root and a SCRATCH packet export; nothing touches the
default HS_STATE_ROOT, cases/, docs/receipts/ or any frozen artifact. No model is called.

Usage from a reproducer:  python docs/audits/cloud/redteam-identity/<attack>.py  (run under `uv run`).
Environment: HS_RT_SCRATCH points at a writable scratch directory (default: a mkdtemp).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(os.environ.get("HS_RT_REPO") or Path(__file__).resolve().parents[4])
RUN = REPO / "docs" / "receipts" / "wp3" / "run"


def scratch(name: str, *, create: bool = True) -> Path:
    """A fresh scratch directory. ``create=False`` returns a path that does not exist yet (for
    ``hs review export``, which refuses to overwrite)."""
    base = Path(os.environ.get("HS_RT_SCRATCH") or tempfile.mkdtemp(prefix="hs-redteam-"))
    d = base / name
    if d.exists():
        shutil.rmtree(d)
    if create:
        d.mkdir(parents=True)
    else:
        d.parent.mkdir(parents=True, exist_ok=True)
    return d


def hs(*args: str, state_root: Path) -> tuple[int, dict]:
    """Run `uv run hs ...` with --state-root forced to the scratch root. Never the default root."""
    cmd = ["uv", "run", "--quiet", "hs", *args, "--state-root", str(state_root)]
    env = {k: v for k, v in os.environ.items() if k != "HS_STATE_ROOT"}
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    out = p.stdout.strip()
    try:
        body = json.loads(out)
    except json.JSONDecodeError:
        body = {"raw_stdout": out, "raw_stderr": p.stderr.strip()}
    return p.returncode, body


def export(state_root: Path, out: Path) -> Path:
    rc, rep = hs("review", "export", str(RUN), "--out", str(out), state_root=state_root)
    assert rc == 0, rep
    return out


def template(packet_dir: Path) -> dict:
    return json.loads((packet_dir / "ratings-template.json").read_text())


def ratings(packet_dir: Path, path: Path, *, reviewer_ref: str, verdict: str = "pass",
            words: str = "synthetic red-team words, not a review", kind: str = "human",
            rated_at: str = "2026-10-07T12:00:00Z", only_items: list[str] | None = None,
            verdict_by_item: dict[str, str] | None = None, tweak=None) -> Path:
    t = template(packet_dir)
    t["reviewer_ref"] = reviewer_ref
    t["reviewer_kind"] = kind
    t["rated_at_utc"] = rated_at
    rows = []
    for r in t["ratings"]:
        if only_items is not None and r["item_id"] not in only_items:
            continue
        r = dict(r)
        r["verdict"] = (verdict_by_item or {}).get(r["item_id"], verdict)
        r["words"] = words
        rows.append(r)
    t["ratings"] = rows
    if tweak:
        tweak(t)
    path.write_text(json.dumps(t, indent=1))
    return path


def show(label: str, rc: int, body: dict, keys: tuple[str, ...] = ()) -> None:
    print(f"\n$ {label}\n  exit {rc}")
    if keys:
        res = body.get("result") or {}
        for k in keys:
            print(f"  {k}: {json.dumps(res.get(k), sort_keys=True)}")
        if body.get("error"):
            print(f"  error: {body['error'].get('message')}")
    else:
        print(json.dumps(body, indent=1, sort_keys=True))


STATUS_KEYS = ("status", "label", "distinct_human_reviewers", "reviewer_ref_collisions",
               "secondary_ratings", "reason")


def status(packet_dir: Path, state_root: Path, label: str = "hs review status") -> dict:
    rc, body = hs("review", "status", "--packet", str(packet_dir), state_root=state_root)
    show(label, rc, body, STATUS_KEYS)
    res = body.get("result") or {}
    if res.get("agreement"):
        for dim, block in res["agreement"].items():
            print(f"  agreement[{dim}]: reviewers={block['reviewers']} n_items={block['n_items']} "
                  f"n_paired={block['n_paired']} raw={block['raw_agreement']} kappa={block['cohen_kappa']}")
    return res


def imp(packet_dir: Path, ratings_path: Path, state_root: Path, label: str) -> tuple[int, dict]:
    rc, body = hs("review", "import", "--packet", str(packet_dir), "--ratings", str(ratings_path),
                  state_root=state_root)
    show(label, rc, body, ("recorded", "votes", "secondary", "problems"))
    return rc, body


def banner(text: str) -> None:
    print("\n" + "=" * 78 + f"\n{text}\n" + "=" * 78)


if __name__ == "__main__":
    print(REPO, RUN.exists(), file=sys.stderr)
