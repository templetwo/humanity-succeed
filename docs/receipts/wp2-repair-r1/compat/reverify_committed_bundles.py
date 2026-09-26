"""Verify and faithfully replay every committed pre-repair bundle, untouched (WP2 repair R1).

Run from the repository root: uv run python docs/receipts/wp2-repair-r1/compat/reverify_committed_bundles.py
Replay output goes to a temporary directory; the committed bundles are hashed before and after.
"""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from humanity_succeed.canonical import load_document
from humanity_succeed.evidence.bundle import verify_bundle
from humanity_succeed.evidence.replay import replay_bundle

SETS = (("docs/receipts/wp2-demo/bundles", "docs/receipts/wp2-anchors", "365090d"),
        ("docs/receipts/wp2r1/demo/bundles", "docs/receipts/wp2r1/anchors", "e6c5d7c"))


def digest(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


rows = []
with tempfile.TemporaryDirectory() as d:
    for broot, aroot, made_at in SETS:
        for b in sorted(Path(broot).iterdir()):
            before = digest(b)
            v = verify_bundle(b, load_document(Path(aroot) / f"{b.name}.anchor.json"))
            r = replay_bundle(b, Path(d) / f"{made_at}-{b.name}")["replay"]
            rows.append({
                "bundle": str(b), "recorded_at_commit": made_at,
                "internal": v["internal"], "anchor": v["anchor"],
                "failed_checks": [c["check"] for c in v["checks"] if not c["passed"]],
                "execution_status": v["execution"]["execution_status"],
                "evaluation_state": v["evaluation"]["state"],
                "recorded_evaluator_version": v["evaluation"]["evaluator_version"],
                "replay_status": r["status"], "evaluator_version_used": r.get("evaluator_version_used"),
                "evaluation_reproduced": r.get("evaluation_reproduced"),
                "bundle_digest_before": before, "bundle_bytes_unchanged": digest(b) == before,
            })
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
ok = all(x["internal"] == "consistent" and x["anchor"] == "verified_against_anchor"
         and x["replay_status"] == "reproduced" and x["bundle_bytes_unchanged"] for x in rows)
json.dump({"schema_id": "hs-compat-receipt/1", "code_head": head, "bundles": len(rows),
           "all_verify_anchor_replay_and_unchanged": ok, "rows": rows},
          sys.stdout, indent=1, sort_keys=True)
sys.stdout.write("\n")
raise SystemExit(0 if ok else 1)
