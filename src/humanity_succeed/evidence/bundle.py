"""Evidence bundle export and read-only verification (BUILD_SPEC §7.1).

Verification levels are reported separately and never merged:
- ``internal``: hash chain, payload contracts, manifest binding, artifact and revision correspondence,
  view recomputation and evaluation binding all check out.
- ``anchor``: ``external_anchor_absent`` unless an anchor file is supplied; then
  ``verified_against_anchor``, ``partial`` (anchor covers a prefix only) or ``failed``.
A locally consistent chain is never called historically authentic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..canonical import (
    StrictLoadError,
    canonical_bytes,
    make_new_dir,
    sha256_bytes,
    sha256_obj,
    strict_json_loads,
    write_new_file,
)
from ..contracts.case import CaseSource
from ..contracts.events import GENESIS_PREV_HASH, EventEnvelope, validate_payload
from ..corpus.views import four_views
from .store import EvidenceStore, compute_event_hash

BUNDLE_SCHEMA = "hs-evidence-bundle/1"
MAX_BUNDLE_FILE_BYTES = 64 * 1024 * 1024
# The only names a bundle may list: fixed top-level files and content-addressed artifacts.
_ALLOWED_NAME = re.compile(
    r"(?:manifest\.json|events\.jsonl|revisions\.json|case_source\.json|trajectory\.json"
    r"|evaluation\.json|artifacts/[0-9a-f]{64})", re.ASCII)


def export_bundle(
    store: EvidenceStore,
    run_id: str,
    case_doc: dict[str, Any],
    evaluation: dict[str, Any] | None,
    out_dir: Path,
    trajectory: dict[str, Any] | None = None,
) -> Path:
    out = make_new_dir(Path(out_dir))
    (out / "artifacts").mkdir()
    files: dict[str, bytes] = {}
    manifest, _ = store.manifest(run_id)
    files["manifest.json"] = canonical_bytes(manifest)
    events = store.events(run_id)
    files["events.jsonl"] = b"".join(canonical_bytes(e) + b"\n" for e in events)
    files["revisions.json"] = canonical_bytes(store.revisions(run_id))
    files["case_source.json"] = canonical_bytes(case_doc)
    if trajectory is not None:
        files["trajectory.json"] = canonical_bytes(trajectory)
    if evaluation is not None:
        files["evaluation.json"] = canonical_bytes(evaluation)
    wanted = _referenced_artifacts(events) | {
        sha256_obj(v) for v in four_views(_case(case_doc), case_doc).values()
    }
    for sha, _kind, body in store.artifacts():
        if sha in wanted:
            files[f"artifacts/{sha}"] = body
    index = {
        "schema_id": BUNDLE_SCHEMA,
        "run_id": run_id,
        "evidence_class": manifest["evidence_class"],
        "files": {k: sha256_bytes(v) for k, v in sorted(files.items())},
        "note": "A locally consistent hash chain is not an externally anchored record.",
    }
    for name, body in files.items():
        write_new_file(out / name, body)
    write_new_file(out / "bundle.json", canonical_bytes(index))
    sums = "".join(f"{sha256_bytes(b)}  {n}\n" for n, b in sorted(
        {**files, "bundle.json": canonical_bytes(index)}.items()))
    write_new_file(out / "SHA256SUMS", sums.encode())
    return out


def _case(doc: dict[str, Any]) -> CaseSource:
    return CaseSource.model_validate(doc, strict=True)


def _referenced_artifacts(events: list[dict[str, Any]]) -> set[str]:
    refs = set()
    for e in events:
        p = e["payload"]
        if e["event_type"] == "observation_delivered":
            refs.add(p["observation_sha256"])
        elif e["event_type"] == "provider_response":
            refs.add(p["raw_sha256"])
    return refs


def anchor_for(bundle: Path) -> dict[str, Any]:
    events = _read_events(bundle / "events.jsonl")
    head = events[-1]
    return {"schema_id": "hs-anchor/1", "run_id": head["run_id"],
            "head_sequence": head["sequence"], "head_event_hash": head["event_hash"]}


def _read_events(path: Path) -> list[dict[str, Any]]:
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise StrictLoadError("jsonl_newline", "events.jsonl must end with a newline")
    return [strict_json_loads(line) for line in data.split(b"\n") if line]


def verify_bundle(bundle: Path, anchor: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read-only. Returns a report; never modifies the bundle."""
    bundle = Path(bundle)
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> bool:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        return bool(ok)

    # 0. layout safety before reading any content: no symlinks anywhere, only expected names,
    #    nothing that resolves outside the bundle, bounded sizes.
    if bundle.is_symlink() or not bundle.is_dir():
        check("bundle_is_plain_directory", False, "bundle path is a symlink or not a directory")
        return _report(checks, None, anchor, None)
    links = [str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_symlink()]
    if not check("no_symlinks", not links, ", ".join(sorted(links))):
        return _report(checks, None, anchor, None)
    hard = [str(p.relative_to(bundle)) for p in bundle.rglob("*")
            if p.is_file() and p.stat(follow_symlinks=False).st_nlink > 1]
    if not check("no_hard_links", not hard, ", ".join(sorted(hard))):
        return _report(checks, None, anchor, None)
    big = [str(p.relative_to(bundle)) for p in bundle.rglob("*")
           if p.is_file() and p.stat().st_size > MAX_BUNDLE_FILE_BYTES]
    if not check("file_sizes_bounded", not big, ", ".join(big)):
        return _report(checks, None, anchor, None)
    try:
        index = strict_json_loads((bundle / "bundle.json").read_bytes())
    except (OSError, StrictLoadError) as e:
        check("bundle_index_readable", False, str(e))
        return _report(checks, None, anchor, None)
    files = index.get("files") if isinstance(index, dict) else None
    bad_names = sorted(n for n in (files or {}) if not _ALLOWED_NAME.fullmatch(n)) if isinstance(
        files, dict) else ["<files is not an object>"]
    if not check("file_names_well_formed", not bad_names, ", ".join(bad_names)):
        return _report(checks, None, anchor, None)

    # 1. file inventory and hashes
    listed = dict(files)
    present = {
        str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()
    } - {"bundle.json", "SHA256SUMS"}
    check("no_unlisted_files", present <= set(listed), ", ".join(sorted(present - set(listed))))
    check("no_missing_files", set(listed) <= present, ", ".join(sorted(set(listed) - present)))
    bad = [n for n, h in listed.items() if (bundle / n).is_file()
           and sha256_bytes((bundle / n).read_bytes()) != h]
    check("file_hashes_match_index", not bad, ", ".join(bad))
    sums_ok = False
    if (bundle / "SHA256SUMS").is_file():
        lines = (bundle / "SHA256SUMS").read_text().splitlines()
        want = {ln.split("  ", 1)[1]: ln.split("  ", 1)[0] for ln in lines if "  " in ln}
        # Names come from an untrusted file: compare as a set BEFORE touching the filesystem, so
        # only names already validated through bundle.json are ever opened.
        sums_ok = set(want) == set(listed) | {"bundle.json"} and all(
            sha256_bytes((bundle / n).read_bytes()) == h for n, h in want.items()
        )
    check("sha256sums_consistent", sums_ok)

    # 2. event chain and contracts
    try:
        events = _read_events(bundle / "events.jsonl")
    except (OSError, StrictLoadError) as e:
        check("events_readable", False, str(e))
        return _report(checks, index, anchor, None)
    chain_ok, detail = True, ""
    prev = GENESIS_PREV_HASH
    for i, e in enumerate(events):
        try:
            EventEnvelope.model_validate(e, strict=True)
            validate_payload(e["event_type"], e["payload"])
        except Exception as ex:  # noqa: BLE001 - report, never raise
            chain_ok, detail = False, f"seq {i}: contract: {ex.__class__.__name__}"
            break
        body = {k: v for k, v in e.items() if k != "event_hash"}
        if e["sequence"] != i:
            chain_ok, detail = False, f"sequence gap at index {i}"
            break
        if e["run_id"] != index.get("run_id"):
            chain_ok, detail = False, f"seq {i}: foreign run_id"
            break
        if e["prev_hash"] != prev:
            chain_ok, detail = False, f"seq {i}: prev_hash mismatch"
            break
        if compute_event_hash(body) != e["event_hash"]:
            chain_ok, detail = False, f"seq {i}: event_hash mismatch"
            break
        prev = e["event_hash"]
    check("event_chain_consistent", chain_ok and bool(events), detail)

    # 3. manifest binding
    try:
        manifest = strict_json_loads((bundle / "manifest.json").read_bytes())
        m_ok = bool(events) and events[0]["event_type"] == "run_started" and (
            events[0]["payload"]["manifest_sha256"] == sha256_obj(manifest)
        )
    except (OSError, StrictLoadError, KeyError):
        manifest, m_ok = None, False
    check("manifest_bound_to_first_event", m_ok)

    # 4. artifacts referenced by events
    refs = _referenced_artifacts(events)
    missing = [r for r in refs if not (bundle / "artifacts" / r).is_file()]
    corrupt = [r for r in refs if (bundle / "artifacts" / r).is_file()
               and sha256_bytes((bundle / "artifacts" / r).read_bytes()) != r]
    check("referenced_artifacts_present", not missing, ", ".join(missing))
    check("artifact_content_addresses_match", not corrupt, ", ".join(corrupt))

    # 5. case source, views
    case = None
    try:
        case_doc = strict_json_loads((bundle / "case_source.json").read_bytes())
        case = _case(case_doc)
        views = four_views(case, case_doc)
        vs = {k: sha256_obj(v) for k, v in views.items()}
        rs = events[0]["payload"] if events else {}
        v_ok = (
            manifest is not None
            and manifest["source"]["case_source_sha256"] == sha256_obj(case_doc)
            and manifest["source"]["view_sha256"] == vs
            and rs.get("subject_view_sha256") == vs["subject"]
            and rs.get("world_view_sha256") == vs["world"]
            and rs.get("evaluator_view_sha256") == vs["evaluator"]
            and rs.get("provenance_view_sha256") == vs["provenance"]
        )
    except Exception:  # noqa: BLE001
        v_ok = False
    check("case_and_views_bound", v_ok)

    # 6. revision history corresponds to resource_revised events
    rev_ok, rdetail = True, ""
    try:
        revisions = strict_json_loads((bundle / "revisions.json").read_bytes())
        revised = [e for e in events if e["event_type"] == "resource_revised"]
        by_seq = {e["sequence"]: e for e in events}
        bound = [r for r in revisions if r["event_sequence"] is not None]
        if len(bound) != len(revised):
            rev_ok, rdetail = False, "revision rows and resource_revised events differ in count"
        for r in revisions:
            if sha256_obj(r["value"]) != r["value_sha256"]:
                rev_ok, rdetail = False, f"{r['resource_id']}@{r['revision']}: value hash"
            if r["event_sequence"] is None:
                if case is None or case.world.resources.get(r["resource_id"]) is None or (
                    sha256_obj(case.world.resources[r["resource_id"]].value) != r["value_sha256"]
                ):
                    rev_ok, rdetail = False, f"{r['resource_id']}: initial revision not in world"
                continue
            ev = by_seq.get(r["event_sequence"])
            if ev is None or ev["event_type"] != "resource_revised" or (
                ev["payload"]["new_value_sha256"] != r["value_sha256"]
                or ev["payload"]["new_revision"] != r["revision"]
                or ev["payload"]["resource_id"] != r["resource_id"]
            ):
                rev_ok, rdetail = False, f"{r['resource_id']}@{r['revision']}: unbound"
    except (OSError, StrictLoadError, KeyError, TypeError) as e:
        rev_ok, rdetail = False, str(e)
    check("revisions_correspond_to_events", rev_ok, rdetail)

    # 7. evaluation binding
    ev_events = [e for e in events if e["event_type"] == "evaluation_recorded"]
    if (bundle / "evaluation.json").is_file():
        ev_doc = strict_json_loads((bundle / "evaluation.json").read_bytes())
        check("evaluation_bound_to_chain", bool(ev_events) and
              ev_events[-1]["payload"]["evaluation_sha256"] == sha256_obj(ev_doc))
    else:
        check("evaluation_bound_to_chain", not ev_events, "evaluation.json absent")

    return _report(checks, index, anchor, events)


def _report(checks, index, anchor, events) -> dict[str, Any]:
    internal = all(c["passed"] for c in checks) and bool(checks)
    if anchor is None:
        anchor_status = "external_anchor_absent"
    elif not events:
        anchor_status = "failed"
    else:
        a_seq, a_hash = anchor.get("head_sequence"), anchor.get("head_event_hash")
        if anchor.get("run_id") != (index or {}).get("run_id"):
            anchor_status = "failed"
        elif not isinstance(a_seq, int) or a_seq >= len(events) or a_seq < 0:
            anchor_status = "failed"
        elif events[a_seq]["event_hash"] != a_hash:
            anchor_status = "failed"
        elif a_seq == len(events) - 1:
            anchor_status = "verified_against_anchor"
        else:
            anchor_status = "partial"
    return {
        "schema_id": "hs-verify-report/1",
        "run_id": (index or {}).get("run_id"),
        "internal": "consistent" if internal else "failed",
        "anchor": anchor_status,
        "checks": checks,
        "note": (
            "internal=consistent means the bundle agrees with itself. Without a retained external "
            "anchor it does not establish that the history was never rewritten."
        ),
    }
