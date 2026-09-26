"""Holdback custody: hashing a custodian-supplied suite, validating a CustodyRecord against it, and
an append-only exposure ledger (docs/WP3_DESIGN.md; BUILD_SPEC §5.2, §9).

No holdback custodian has been named for this build (WP3_DESIGN.md). Nothing here can make one
exist: it only lets a future custodian's record be checked, honestly, against what is actually on
disk. Custodian *identity* is attested by the ``CustodyRecord`` the custodian writes; this module
never verifies who wrote it, only whether the record and the bytes it claims to fix agree, and
whether the holdback lives somewhere the builder could not have reached.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..canonical import canonical_str, load_document, strict_json_loads
from .contract import SUITE_MANIFEST_NAME, CustodyRecord, SuiteManifest, suite_problems

LEDGER_NAME = "holdback_exposure.jsonl"


# ---------------------------------------------------------------- hashing


def _referenced_paths(manifest: SuiteManifest) -> set[str]:
    rels = {SUITE_MANIFEST_NAME}
    for g in manifest.groups:
        for m in g.members:
            rels.add(m.case)
            rels.add(m.trajectory)
    return rels


def holdback_suite_sha256(suite_root: Path) -> str:
    """sha256 over ``SUITE.json`` plus every case/trajectory file the manifest references, in
    sorted relative-path order, each as ``path bytes + NUL + file bytes + NUL``. A symlinked file
    anywhere in that set is refused rather than silently hashed through."""
    import hashlib

    suite_root = Path(suite_root)
    manifest = SuiteManifest.model_validate_json((suite_root / SUITE_MANIFEST_NAME).read_text())
    h = hashlib.sha256()
    for rel in sorted(_referenced_paths(manifest)):
        p = suite_root / rel
        if p.is_symlink():
            raise ValueError(f"{rel}: symlinked fixture file refused")
        data = p.read_bytes()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return h.hexdigest()


# ---------------------------------------------------------------- containment


def _inside(target: Path, root: Path) -> bool:
    """True if ``target`` is ``root`` or below it. Compares existing ancestors by inode (as
    ``evidence/replay.py``'s ``_inside`` does), so a differently-cased alias on a case-insensitive
    filesystem (APFS, NTFS) or a symlinked ancestor directory cannot evade the check. ``target`` is
    fully resolved first (not just made absolute), so a symlink at the leaf itself -- not only an
    ancestor -- that points inside ``root`` is caught too; realpath does not touch case, so the
    inode-based ancestor walk below still catches a case-only alias on a case-insensitive fs."""
    target = Path(os.path.realpath(target))
    if not root.exists():
        return False
    return any(p.exists() and os.path.samefile(p, root) for p in (target, *target.parents))


# ---------------------------------------------------------------- custody record


def load_custody(custody_file: Path, holdback_root: Path, *, repo_root: Path,
                 state_root: Path) -> dict[str, Any]:
    """Validate a ``CustodyRecord`` against the holdback suite it claims to fix.

    ``independent_holdback`` is true only when ``problems`` is empty. Custodian identity is
    attested by the record, never verified by this tool -- a strict, hash-matching record from an
    unnamed or self-declared custodian is exactly what the record format allows.
    """
    custody_file = Path(custody_file)
    holdback_root = Path(holdback_root)
    repo_root = Path(repo_root)
    state_root = Path(state_root)

    problems: list[str] = []

    record: CustodyRecord | None = None
    try:
        doc = load_document(custody_file)
        record = CustodyRecord.model_validate(doc, strict=True)
    except (OSError, ValidationError, ValueError) as e:
        problems.append(f"invalid custody record: {e}")

    if _inside(holdback_root, repo_root):
        problems.append(f"holdback_root {holdback_root} is inside repo_root {repo_root}")
    if _inside(holdback_root, state_root):
        problems.append(f"holdback_root {holdback_root} is inside state_root {state_root}")

    computed_hash: str | None = None
    try:
        computed_hash = holdback_suite_sha256(holdback_root)
    except (OSError, ValidationError, ValueError) as e:
        problems.append(f"cannot hash holdback suite at {holdback_root}: {e}")

    if record is not None and computed_hash is not None:
        if record.holdback_suite_sha256 != computed_hash:
            problems.append(
                f"holdback_suite_sha256 mismatch: record has {record.holdback_suite_sha256}, "
                f"computed {computed_hash}")

    manifest: SuiteManifest | None = None
    try:
        manifest = SuiteManifest.model_validate_json(
            (holdback_root / SUITE_MANIFEST_NAME).read_text())
    except (OSError, ValidationError, ValueError) as e:
        problems.append(f"cannot load holdback manifest at {holdback_root}: {e}")

    if manifest is not None:
        if manifest.authorship != "custodian_supplied":
            problems.append(
                f"holdback manifest authorship is {manifest.authorship!r}, expected "
                "'custodian_supplied'")
        if manifest.split != "commissioning_holdback":
            problems.append(
                f"holdback manifest split is {manifest.split!r}, expected "
                "'commissioning_holdback'")
        problems += suite_problems(manifest, holdback_root, fragment=True)

    return {
        "custodian": record.custodian if record is not None else None,
        "custody_valid": record is not None,
        "independent_holdback": not problems,
        "holdback_suite_sha256": computed_hash,
        "problems": problems,
        "note": ("custodian identity is attested by the CustodyRecord's 'custodian' field; this "
                "tool verifies the record against the bytes on disk, never who wrote it"),
    }


# ---------------------------------------------------------------- exposure ledger


def ledger_path(state_root: Path) -> Path:
    return Path(state_root) / "commissioning" / LEDGER_NAME


def exposure_status(state_root: Path, holdback_sha256: str) -> dict[str, Any]:
    """Whether ``holdback_sha256`` has an exposure record, and every matching record."""
    path = ledger_path(state_root)
    records: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = strict_json_loads(line)
            if rec.get("holdback_suite_sha256") == holdback_sha256:
                records.append(rec)
    return {"exposed": bool(records), "records": records}


def record_exposure(state_root: Path, holdback_sha256: str, run_ref: dict[str, Any]
                    ) -> dict[str, Any]:
    """Append one canonical-JSON exposure record. Never rewrites or removes an earlier line."""
    path = ledger_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "schema_id": "hs-holdback-exposure/1",
        "holdback_suite_sha256": holdback_sha256,
        "run_ref": run_ref,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(canonical_str(entry) + "\n")
    return entry


__all__ = [
    "holdback_suite_sha256", "load_custody", "ledger_path", "exposure_status", "record_exposure",
]
