"""Seal a custodian-prepared holdback suite into a ``CustodyRecord`` (docs/HOLDBACK_CUSTODY.md;
BUILD_SPEC §5.2, §9; docs/WP3_DESIGN.md).

    uv run python scripts/seal_holdback.py \\
        --holdback PATH --custodian NAME --statement TEXT --out FILE

Run this from wherever the holdback suite actually lives -- never from inside this repository's
working tree, and never inside the ``hs`` state root either (``--state-root``, else
``$HS_STATE_ROOT``, else ``~/.local/share/humanity-succeed`` -- the same precedence ``cli.py``'s
own ``state_root()`` uses). It validates the suite's shape (a strict ``SuiteManifest`` with
``authorship: custodian_supplied``, ``split: commissioning_holdback``, and no problems from
``contract.suite_problems(fragment=True)``), refuses a holdback that sits inside either of those two
locations (the same samefile-ancestor rule ``commissioning.custody.load_custody`` uses for a
holdback root), computes ``holdback_suite_sha256`` over the sealed bytes, and writes a
canonical-JSON ``CustodyRecord`` to ``--out`` -- refusing to overwrite an existing file. It never
reads or prints fixture contents; only validation messages, counts, and the computed hash reach
stdout.

Exit codes:
  0  sealed: the custody record was written.
  2  invalid input: a bad argument, an unreadable or unparsable holdback manifest, or ``--out``
     already exists (matching ``canonical.write_new_file``'s refuse-to-overwrite convention).
  3  refused precondition: the holdback is not a valid, independent custody submission -- it sits
     inside this repository or the hs state root, or it fails the custody-shape checks (wrong
     ``authorship``, wrong ``split``, or any problem from ``contract.suite_problems(fragment=True)``).
     This mirrors ``hs commission plan``'s own exit 3 for "invalid custody" (docs/WP3_DESIGN.md,
     Commands).

This is a script, not the CLI: ``sealed_at_utc`` uses the real wall clock (BUILD_SPEC's "no silent
conveniences" ban on hidden clocks governs the *instrument*, not a one-shot custodian tool that
never touches evidence, scoring, or the evaluator).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from humanity_succeed.canonical import canonical_bytes, write_new_file
from humanity_succeed.commissioning.contract import (
    SUITE_MANIFEST_NAME,
    CustodyRecord,
    SuiteManifest,
    suite_problems,
)
from humanity_succeed.commissioning.custody import _inside, holdback_suite_sha256

# scripts/seal_holdback.py sits one directory below the repo root (unlike src/humanity_succeed/
# cli.py, two levels down, or runner/episode.py, three levels down -- each needs its own parents[N]
# offset; copying either of theirs here would silently compute the wrong root). Verified, not
# assumed: a script run from a moved or vendored copy fails loudly instead of mis-scoping the
# containment check.
REPO_ROOT = Path(__file__).resolve().parents[1]
assert (REPO_ROOT / "pyproject.toml").is_file(), (
    f"seal_holdback.py: unexpected repo root {REPO_ROOT} (pyproject.toml not found there)")

EXIT_OK, EXIT_INVALID, EXIT_PRECONDITION = 0, 2, 3


class CustodyShapeError(ValueError):
    """The holdback is not a valid, independent custody submission (exit 3): it sits inside this
    repository, or it fails the authorship/split/structural checks a holdback fragment must meet.
    Distinct from a plain invalid-input error (exit 2, e.g. an unreadable or unparsable manifest,
    or a bad statement/custodian value) precisely because these are about the holdback's *fitness
    as custody*, not about whether the command line or the file could be read at all.
    """


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="seal_holdback.py",
        description="Seal a custodian-supplied holdback suite into a CustodyRecord.")
    p.add_argument("--holdback", required=True,
                   help="path to the holdback suite root (SUITE.json plus cases/ and "
                        "trajectories/), prepared per docs/HOLDBACK_CUSTODY.md")
    p.add_argument("--custodian", required=True,
                   help="the custodian's name or role -- never the builder seat; this tool "
                        "attests nothing about identity, it only records what is typed here")
    p.add_argument("--statement", required=True,
                   help="how the custodian kept the suite out of the builder's reach")
    p.add_argument("--out", required=True,
                   help="path to write the new CustodyRecord JSON file (must not already exist)")
    p.add_argument("--state-root", default=None,
                   help="the hs state root to also refuse as a holdback location (matches "
                        "cli.py's own state_root() resolution: this flag, else $HS_STATE_ROOT, "
                        "else ~/.local/share/humanity-succeed). A holdback inside it is exposed "
                        "to load_custody's own scan of that directory and is not custody either.")
    return p.parse_args(argv)


def _resolve_state_root(arg: str | None) -> Path:
    """Mirrors ``cli.state_root``'s precedence (arg, then $HS_STATE_ROOT, then the default under
    the home directory) without importing ``cli.py`` -- this script must run from outside the
    repository, and creates no directories on disk (unlike ``cli.state_root``, which is invoked at
    command time inside a live checkout)."""
    return Path(arg or os.environ.get("HS_STATE_ROOT")
                or Path.home() / ".local" / "share" / "humanity-succeed")


def _load_manifest(holdback: Path) -> SuiteManifest:
    """Read and strictly parse ``holdback``'s SuiteManifest. Raises ``ValueError`` (exit 2) when
    the file cannot even be read or does not parse as a ``SuiteManifest`` -- a problem with the
    input, not with whether it has the right custody shape."""
    manifest_path = holdback / SUITE_MANIFEST_NAME
    try:
        text = manifest_path.read_text()
    except OSError as e:
        raise ValueError(f"cannot read {manifest_path}: {e.strerror or e}") from e
    try:
        return SuiteManifest.model_validate_json(text)
    except ValidationError as e:
        raise ValueError(f"{manifest_path}: does not parse as a SuiteManifest: {e}") from e


def _custody_shape_problems(manifest: SuiteManifest, holdback: Path) -> list[str]:
    """Every way ``manifest``/``holdback`` fails to be a valid custodian holdback fragment. Empty
    means the shape is fine; it says nothing about whether the bytes are independent of the
    builder (that is what ``_inside`` and, later, ``commissioning.custody.load_custody`` check)."""
    problems: list[str] = []
    if manifest.authorship != "custodian_supplied":
        problems.append(
            f"authorship is {manifest.authorship!r}, expected 'custodian_supplied'")
    if manifest.split != "commissioning_holdback":
        problems.append(f"split is {manifest.split!r}, expected 'commissioning_holdback'")
    problems += suite_problems(manifest, holdback, fragment=True)
    return problems


def seal(holdback: Path, custodian: str, statement: str, out: Path, *, state_root: Path) -> dict:
    """Validate ``holdback`` and write a ``CustodyRecord`` to ``out``. Returns the JSON-serializable
    summary this script prints. Raises ``CustodyShapeError`` (exit 3), ``ValueError``/``OSError``
    (exit 2), or lets ``FileExistsError`` (exit 2, ``out`` already exists) propagate.
    """
    if _inside(holdback, REPO_ROOT):
        raise CustodyShapeError(
            f"holdback path {holdback} is inside this repository at {REPO_ROOT}; a location the "
            "builder can reach is not custody (BUILD_SPEC §5.2, §9)")
    if _inside(holdback, state_root):
        raise CustodyShapeError(
            f"holdback path {holdback} is inside the hs state root at {state_root}; a location "
            "the builder's own tooling scans is not custody (BUILD_SPEC §5.2, §9)")

    manifest = _load_manifest(holdback)
    shape_problems = _custody_shape_problems(manifest, holdback)
    if shape_problems:
        raise CustodyShapeError(
            "holdback is not a valid custody submission:\n  " + "\n  ".join(shape_problems))

    # suite_problems(fragment=True) already confirmed every referenced file exists, is a file (not
    # a symlink), and belongs to this manifest, so hashing should not fail here -- but if it does
    # (e.g. a race, or a symlink outside what suite_problems checks), that is a defect in the bytes
    # on disk, not a CLI usage error, so it is reported the same way as any other shape problem.
    try:
        digest = holdback_suite_sha256(holdback)
    except (OSError, ValueError) as e:
        raise CustodyShapeError(f"cannot hash holdback suite at {holdback}: {e}") from e

    try:
        record = CustodyRecord(
            schema_id="hs-holdback-custody/1",
            custodian=custodian,
            holdback_suite_sha256=digest,
            sealed_at_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            statement=statement,
        )
    except ValidationError as e:
        raise ValueError(f"cannot build CustodyRecord: {e}") from e

    write_new_file(out, canonical_bytes(record.model_dump(mode="json")))

    return {
        "schema_id": "hs-seal-holdback-summary/1",
        "custody_record": str(out),
        "holdback": str(holdback),
        "holdback_suite_sha256": digest,
        "custodian": record.custodian,
        "sealed_at_utc": record.sealed_at_utc,
        "group_count": len(manifest.groups),
        "trajectory_count": sum(len(g.members) for g in manifest.groups),
        "note": ("this summary only says the record was written and matches the bytes on disk; "
                 "it certifies nothing about the evaluator and nothing about who the custodian "
                 "actually is -- see docs/HOLDBACK_CUSTODY.md"),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    holdback = Path(args.holdback)
    out = Path(args.out)
    state_root = _resolve_state_root(args.state_root)
    try:
        summary = seal(holdback, args.custodian, args.statement, out, state_root=state_root)
    except CustodyShapeError as e:
        print(json.dumps({"status": "blocked", "error": {
            "code": "custody_shape_invalid", "message": str(e)}}, indent=2, sort_keys=True))
        return EXIT_PRECONDITION
    except FileExistsError as e:
        print(json.dumps({"status": "invalid", "error": {
            "code": "refuse_overwrite", "message": str(e)}}, indent=2, sort_keys=True))
        return EXIT_INVALID
    except (ValueError, OSError) as e:
        print(json.dumps({"status": "invalid", "error": {
            "code": "invalid_input", "message": str(e)}}, indent=2, sort_keys=True))
        return EXIT_INVALID
    print(json.dumps({"status": "ok", "result": summary}, indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
